// SPDX-License-Identifier: BSD-3-Clause
#include "amp_receiver.h"
#include <array>
#include <cassert>
#include <cstdio>
int main(){
    alignas(8) std::array<unsigned char,AMP_HOST_OFFSET> peer{};
    alignas(8) std::array<unsigned char,AMP_WINDOW_SIZE-AMP_HOST_OFFSET> host{};
    auto *d=reinterpret_cast<amp_device *>(peer.data());auto *h=reinterpret_cast<amp_host *>(host.data());
    auto *p=reinterpret_cast<rpshm_session_peer *>(peer.data()+AMP_SESSION_PEER_OFFSET);
    amp_receiver r{};
    assert(!amp_receiver_init(&r,d,peer.size(),h,host.size()));
    d->magic.v=AMP_MAGIC;d->version.v=AMP_VERSION;p->magic=RPSHM_SESSION_MAGIC;p->boot=1;p->state=RPSHM_QUIET;
    assert(!amp_receiver_init(&r,d,peer.size(),h,100));
    assert(amp_receiver_init(&r,d,peer.size(),h,host.size()));
    amp_record out;assert(rpshm_receiver_latest(&r.endpoint,&out)==RPSHM_RECEIVE_UNAVAILABLE);
    assert(rpshm_receiver_begin(&r.endpoint,0,100)==RPSHM_CONTROL_STARTED);
    auto *s=reinterpret_cast<rpshm_session_host *>(host.data()+AMP_SESSION_HOST_OFFSET);
    rpshm_receiver_poll(&r.endpoint,1);p->ack=s->request;
    rpshm_receiver_poll(&r.endpoint,2);
    auto *magic=reinterpret_cast<uint32_t *>(host.data()+AMP_EXPERIMENT_HOST_OFFSET);*magic=0x4e435250;
    rpshm_receiver_poll(&r.endpoint,3);assert(*magic==0&&h->reading.v==0&&h->tail.v==0);
    rpshm_receiver_poll(&r.endpoint,4);p->ack=s->request;p->state=RPSHM_ACTIVE;
    rpshm_receiver_poll(&r.endpoint,5);
    amp_record value; amp_record_make(&value,1,r.endpoint.connection.run,0,0,0,0);
    amp_latest_publish(&d->latest,&h->reading,&value);
    assert(rpshm_receiver_latest(&r.endpoint,&out)==RPSHM_RECEIVE_OK&&amp_record_valid(&out));
    ++p->boot;assert(rpshm_receiver_latest(&r.endpoint,&out)==RPSHM_RECEIVE_RESTART);
    puts("Zenith adapter: firmware gate, layout, config reset and checked delivery PASS");
}
