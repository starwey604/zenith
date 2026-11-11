// SPDX-License-Identifier: BSD-3-Clause
#include "amp_uio.hpp"
#include "amp_receiver.h"
#include <rpshm/progress.h>
#include <chrono>
#include <csignal>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <thread>
#include <sched.h>
#include <time.h>
static volatile sig_atomic_t interrupted;
static void stop_signal(int){interrupted=1;}
static uint64_t now(clockid_t clock=CLOCK_MONOTONIC){timespec t{};clock_gettime(clock,&t);return uint64_t(t.tv_sec)*1000000000+t.tv_nsec;}
static rpshm_receiver_status status(const rpshm_receiver &r)
{
    rpshm_receiver_status s{};
    if(!rpshm_receiver_get_status(&r,&s))throw std::runtime_error("invalid receiver");
    return s;
}
static void wait_connection(rpshm_receiver &r,bool stop)
{
    auto result=stop?rpshm_receiver_stop(&r,now(),3000000000):rpshm_receiver_begin(&r,now(),3000000000);
    if(result<0)throw std::runtime_error("connection operation busy or invalid");
    auto end=now()+3000000000;
    while(now()<end){
        auto state=rpshm_receiver_poll(&r,now());
        if(state==(stop?RPSHM_STOPPED:RPSHM_CONNECTED))return;
        if(state==RPSHM_FAILED){
            if(status(r).error==RPSHM_CONN_PEER_RESTART){
                auto t=now();if(t>=end)throw std::runtime_error("connection deadline expired");
                if(stop)rpshm_receiver_stop(&r,t,end-t);
                else rpshm_receiver_begin(&r,t,end-t);
            }else throw std::runtime_error("connection failed: "+std::to_string(status(r).error));
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    throw std::runtime_error("connection deadline expired");
}
int main(int argc,char **argv)
{
    std::unique_ptr<AmpUio> map; amp_receiver channel{};bool initialized=false;
    try{
        unsigned seconds=5,stale_ms=20;int cpu=4;std::string device;
        for(int i=1;i<argc;++i){
            std::string arg=argv[i];
            auto value=[&]{if(++i==argc)throw std::runtime_error("missing option value");return std::string(argv[i]);};
            if(arg=="--seconds")seconds=std::stoul(value());
            else if(arg=="--stale-ms")stale_ms=std::stoul(value());
            else if(arg=="--cpu")cpu=std::stoi(value());
            else if(arg=="--device")device=value();
            else throw std::runtime_error("options: --seconds N --cpu N --device /dev/uioN --stale-ms N");
        }
        if(!seconds||seconds>3600||!stale_ms||stale_ms>3600000||cpu<0||cpu>=CPU_SETSIZE)throw std::runtime_error("invalid seconds/cpu");
        cpu_set_t set;CPU_ZERO(&set);CPU_SET(cpu,&set);if(sched_setaffinity(0,sizeof(set),&set))throw std::runtime_error("affinity");
        sched_param priority{70};if(sched_setscheduler(0,SCHED_FIFO,&priority))throw std::runtime_error("SCHED_FIFO");
        map=std::make_unique<AmpUio>(device);
        if(!amp_receiver_init(&channel,map->device,AMP_HOST_OFFSET,map->host,AMP_WINDOW_SIZE-AMP_HOST_OFFSET))
            throw std::runtime_error("requires matching lifecycle-capable 128-byte firmware/layout");
        initialized=true;auto &rx=channel.endpoint;
        signal(SIGINT,stop_signal);signal(SIGTERM,stop_signal);
        wait_connection(rx,false);
        rpshm_progress progress;rpshm_progress_init(&progress,uint64_t(stale_ms)*1000000);
        uint32_t fifo_previous=0,errors=0,reconnects=0;
        uint64_t delivered=0,waiting=0,repeats=0,stale_samples=0,stale_transitions=0,resumptions=0;
        bool was_stale=false;
        uint64_t samples=0,events=0,discarded=0,cost=0,max_cost=0,missed=0;
        uint64_t begin=now(),end=begin+uint64_t(seconds)*1000000000,next=begin,cpu_begin=now(CLOCK_PROCESS_CPUTIME_ID);
        while(!interrupted&&now()<end){
            amp_record scratch;
            auto a=now(CLOCK_MONOTONIC_RAW);auto result=rpshm_receiver_latest(&rx,&scratch);
            auto elapsed=now(CLOCK_MONOTONIC_RAW)-a;
            if(result==RPSHM_RECEIVE_OK){
                cost+=elapsed;if(elapsed>max_cost)max_cost=elapsed;
                auto identity=status(rx);++samples;
                if(!amp_record_valid(&scratch)||scratch.session!=identity.run)++errors;
                else {
                    auto observed=rpshm_progress_observe(&progress,identity.boot,identity.run,scratch.seq,now());
                    if(observed.state==RPSHM_PROGRESS_INVALID)throw std::runtime_error("invalid sequence/observation clock");
                    if(observed.state==RPSHM_PROGRESS_STALE){++stale_samples;if(!was_stale)++stale_transitions;was_stale=true;}
                    else if(observed.state==RPSHM_PROGRESS_WAITING)++waiting;
                    else if(observed.advanced){
                        if(was_stale)++resumptions;was_stale=false;++delivered;
                        // Business delivery belongs here, using the local validated sample.
                    }else ++repeats;
                    // WAITING/STALE must also invalidate any business-side cached state.
                }
                while((result=rpshm_receiver_pop(&rx,&scratch))==RPSHM_RECEIVE_OK){
                    if(!amp_record_valid(&scratch)||scratch.session!=identity.run||scratch.seq<=fifo_previous)++errors;
                    fifo_previous=scratch.seq;++events;
                }
            }
            if(result==RPSHM_RECEIVE_RESTART){
                ++discarded;++reconnects;wait_connection(rx,false);fifo_previous=0;rpshm_progress_init(&progress,uint64_t(stale_ms)*1000000);was_stale=false;next=now();continue;
            }
            if(result!=RPSHM_RECEIVE_EMPTY)throw std::runtime_error("receiver unavailable");
            next+=2000000;auto t=now();if(t>=next){auto n=(t-next)/2000000+1;missed+=n;next+=n*2000000;}
            timespec deadline{time_t(next/1000000000),long(next%1000000000)};
            int e;do{e=clock_nanosleep(CLOCK_MONOTONIC,TIMER_ABSTIME,&deadline,nullptr);}while(e==EINTR&&!interrupted);
            if(e&&e!=EINTR)throw std::runtime_error("clock_nanosleep");
        }
        auto cpu_ns=now(CLOCK_PROCESS_CPUTIME_ID)-cpu_begin,elapsed_ns=now()-begin;
        wait_connection(rx,true);
        std::cout<<"{\"record_bytes\":128,\"publish_hz\":1000,\"read_hz\":500,\"samples\":"<<samples
                 <<",\"fifo\":"<<events<<",\"errors\":"<<errors<<",\"reconnects\":"<<reconnects<<",\"discarded\":"<<discarded
                 <<",\"missed_reads\":"<<missed<<",\"checked_read_mean_ns\":"<<(samples?double(cost)/samples:0)
                 <<",\"checked_read_max_ns\":"<<max_cost<<",\"cpu_ns\":"<<cpu_ns<<",\"elapsed_ns\":"<<elapsed_ns
                 <<",\"stale_ms\":"<<stale_ms<<",\"delivered\":"<<delivered<<",\"waiting\":"<<waiting
                 <<",\"repeats\":"<<repeats<<",\"stale_samples\":"<<stale_samples<<",\"stale_transitions\":"<<stale_transitions
                 <<",\"resumptions\":"<<resumptions<<",\"boot\":"<<status(rx).boot<<",\"state\":\"stopped\"}\n";
        return errors||interrupted?1:0;
    }catch(const std::exception &e){
        if(initialized){try{wait_connection(channel.endpoint,true);}catch(const std::exception &stop){std::cerr<<"stop: "<<stop.what()<<'\n';}}
        std::cerr<<"amp-state-receiver: "<<e.what()<<'\n';return 2;
    }
}
