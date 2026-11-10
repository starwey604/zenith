// SPDX-License-Identifier: BSD-3-Clause
#include "amp_uio.hpp"
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <csignal>
#include <cstring>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <thread>
#include <vector>
#include <sched.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t interrupted;
static void on_signal(int) { interrupted = 1; }
static uint64_t ns() {
    timespec t{}; clock_gettime(CLOCK_MONOTONIC_RAW, &t);
    return uint64_t(t.tv_sec) * 1000000000ULL + t.tv_nsec;
}
static void sleep_until(uint64_t target) {
    // Sleep deadlines use MONOTONIC, not the independently calibrated RAW clock.
    timespec t{time_t(target / 1000000000ULL), long(target % 1000000000ULL)};
    int ret;
    do { ret = clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &t, nullptr); }
    while (ret == EINTR && !interrupted);
    if (ret && ret != EINTR) throw std::runtime_error("clock_nanosleep failed");
}
static uint64_t mono_ns() {
    timespec t{}; clock_gettime(CLOCK_MONOTONIC, &t);
    return uint64_t(t.tv_sec) * 1000000000ULL + t.tv_nsec;
}
struct SimulatedM0 {
    amp_device device{}; amp_host host{};
    std::atomic<bool> quit{false}; std::thread worker;
    SimulatedM0() : worker([this] { run(); }) {}
    ~SimulatedM0() { quit = true; worker.join(); }
    void run() {
        uint32_t command = 0, seq = 0, session = 0, lc = 0, fc = 0;
        amp_store(&device.version.v, AMP_VERSION); amp_store(&device.state.v, AMP_IDLE);
        amp_store(&device.magic.v, AMP_MAGIC);
        auto next = std::chrono::steady_clock::now();
        while (!quit.load()) {
            auto cmd = amp_load(&host.command.v);
            if (cmd != command) {
                command = cmd;
                if ((cmd & 255u) == AMP_CMD_STOP) amp_store(&device.state.v, AMP_STOPPED);
                else if ((cmd & 255u) == AMP_CMD_RUN && amp_load(&device.state.v) == AMP_STOPPED) {
                    std::memset(&device.latest, 0, sizeof(device.latest));
                    std::memset(&device.fifo, 0, sizeof(device.fifo));
                    device.latest_cost = {}; device.fifo_cost = {}; device.probe_cost = {}; device.irq_cost = {};
                    amp_store(&device.fifo_drops.v, 0); amp_store(&device.final_seq.v, 0);
                    seq = lc = fc = 0; session = cmd;
                    for (auto &pair : device.latest.data) for (auto &r : pair) amp_record_make(&r, 0, session, ns(), 0, 0, 0);
                    device.session.v = session; device.timer_hz.v = 1000000000;
                    device.publish_hz.v = 500; amp_store(&device.state.v, AMP_RUNNING);
                } else amp_store(&device.state.v, AMP_ERROR);
                amp_store(&device.ack.v, cmd);
            }
            if (amp_load(&device.state.v) == AMP_RUNNING) {
                auto start = ns(); auto a = ns(); auto probe = uint32_t(ns() - a);
                amp_record r; amp_record_make(&r, ++seq, session, start, lc, fc, probe);
                a = ns(); amp_latest_publish(&device.latest, &host.reading, &r); lc = uint32_t(ns() - a);
                a = ns(); if (!amp_fifo_push(&device.fifo, &host.tail, &r)) ++device.fifo_drops.v; fc = uint32_t(ns() - a);
                amp_hist_add(&device.latest_cost, lc); amp_hist_add(&device.fifo_cost, fc);
                amp_hist_add(&device.probe_cost, probe); amp_hist_add(&device.irq_cost, uint32_t(ns() - start));
                amp_store(&device.final_seq.v, seq);
            }
            next += std::chrono::milliseconds(2); std::this_thread::sleep_until(next);
        }
    }
};
static uint32_t command(const amp_device *d, amp_host *h, uint32_t op) {
    uint32_t c = ((amp_load(&h->command.v) + 256u) & ~255u) | op;
    amp_store(&h->command.v, c);
    auto deadline = ns() + 2000000000ULL;
    while (amp_load(&d->ack.v) != c) {
        if (ns() > deadline) throw std::runtime_error("M0 command acknowledgement timed out");
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    auto expected = op == AMP_CMD_STOP ? AMP_STOPPED : AMP_RUNNING;
    if (amp_load(&d->state.v) != expected) throw std::runtime_error("M0 rejected command/state");
    return c;
}
static void vector_json(std::vector<uint64_t> &v) {
    if (v.empty()) { std::cout << "null"; return; }
    std::sort(v.begin(), v.end()); long double sum = 0;
    for (auto x : v) sum += x;
    auto q = [&](double p) { return v[size_t(std::ceil(p * v.size())) - 1]; };
    std::cout << "{\"n\":" << v.size() << ",\"min_ns\":" << v.front()
              << ",\"p50_ns\":" << q(.5) << ",\"p95_ns\":" << q(.95)
              << ",\"p99_ns\":" << q(.99) << ",\"p999_ns\":" << q(.999)
              << ",\"max_ns\":" << v.back() << ",\"mean_ns\":" << double(sum / v.size()) << "}";
}
static void hist_json(const amp_hist &h, uint32_t hz) {
    if (!h.count || !hz) { std::cout << "null"; return; }
    auto scale = 1e9 / hz;
    std::cout << "{\"n\":" << h.count << ",\"min_ns\":" << h.min * scale
              << ",\"max_ns\":" << h.max * scale << ",\"mean_ns\":" << double(h.sum) / h.count * scale
              << ",\"bin_width_ns\":" << scale << ",\"overflow_count\":" << h.bins[AMP_HIST_BINS];
    const char *names[] = {"p50_ns", "p95_ns", "p99_ns", "p999_ns"};
    double ps[] = {.5, .95, .99, .999};
    for (unsigned k = 0; k < 4; ++k) {
        uint32_t target = uint32_t(std::ceil(ps[k] * h.count)), sum = 0, i;
        for (i = 0; i < AMP_HIST_BINS; ++i) { sum += h.bins[i]; if (sum >= target) break; }
        std::cout << ",\"" << names[k] << "\":";
        if (i == AMP_HIST_BINS) std::cout << "null"; else std::cout << i * scale;
    }
    std::cout << "}";
}
int main(int argc, char **argv)
{
    const amp_device *d = nullptr; amp_host *h = nullptr; bool running = false;
    std::unique_ptr<AmpUio> uio; std::unique_ptr<SimulatedM0> sim;
    try {
        double seconds = 10; uint32_t stall_ms = 0; int cpu = -1;
        bool simulate = false, baseline = false, protect = false, status = false; std::string path;
        for (int i = 1; i < argc; ++i) {
            std::string a = argv[i];
            auto arg = [&]() -> std::string { if (++i == argc) throw std::runtime_error("missing option value"); return argv[i]; };
            if (a == "--seconds") seconds = std::stod(arg());
            else if (a == "--stall-ms") stall_ms = std::stoul(arg());
            else if (a == "--cpu") cpu = std::stoi(arg());
            else if (a == "--device") path = arg();
            else if (a == "--simulate") simulate = true;
            else if (a == "--baseline") baseline = true;
            else if (a == "--check-mapping") protect = true;
            else if (a == "--status") status = true;
            else if (a == "--help") {
                std::cout << "amp-shm-bench [--device /dev/uioN] [--seconds 10] [--cpu N] [--stall-ms 0] [--baseline] [--check-mapping] [--simulate] [--status]\n";
                return 0;
            } else throw std::runtime_error("unknown option: " + a);
        }
        if (!std::isfinite(seconds) || seconds < 1 || seconds > 3600 || stall_ms > seconds * 1000 || cpu >= CPU_SETSIZE || cpu < -1)
            throw std::runtime_error("invalid duration, stall or CPU");
        if (cpu >= 0) { cpu_set_t set; CPU_ZERO(&set); CPU_SET(cpu, &set);
            if (sched_setaffinity(0, sizeof(set), &set)) throw std::runtime_error("CPU affinity failed"); }
        if (simulate) { sim = std::make_unique<SimulatedM0>(); d = &sim->device; h = &sim->host; }
        else { uio = std::make_unique<AmpUio>(path); d = uio->device; h = uio->host; if (protect) uio->check_protection(); }
        if (status) {
            std::cout << "{\"magic\":" << amp_load(&d->magic.v) << ",\"version\":" << amp_load(&d->version.v)
                      << ",\"state\":" << amp_load(&d->state.v) << ",\"ack\":" << amp_load(&d->ack.v)
                      << ",\"command\":" << amp_load(&h->command.v) << ",\"session\":" << amp_load(&d->session.v)
                      << ",\"published\":" << amp_load(&d->final_seq.v) << "}\n";
            return 0;
        }
        auto ready_end = ns() + 2000000000ULL;
        while (amp_load(&d->magic.v) != AMP_MAGIC) {
            if (ns() > ready_end) throw std::runtime_error("M0 benchmark firmware not ready");
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
        if (amp_load(&d->version.v) != AMP_VERSION) throw std::runtime_error("wire ABI mismatch");
        command(d, h, AMP_CMD_STOP);
        amp_store(&h->reading.v, 0); amp_store(&h->tail.v, 0);
        uint32_t session = 0;
        std::vector<uint64_t> latest_cost, fifo_cost, probe_cost, wake_late;
        latest_cost.reserve(size_t(seconds * 250 + 1000)); fifo_cost.reserve(size_t(seconds * 500 + 1000));
        probe_cost.reserve(size_t(seconds * 250 + 1000)); wake_late.reserve(size_t(seconds * 250 + 1000));
        signal(SIGINT, on_signal); signal(SIGTERM, on_signal);
        // A timed-out RUN may still be consumed later: the failure path must
        // replace it with STOP even when RUN has not yet been acknowledged.
        if (!baseline) { running = true; session = command(d, h, AMP_CMD_RUN); }
        uint64_t begin = mono_ns(), deadline = begin + uint64_t(seconds * 1e9), next = begin;
        uint32_t latest_seq = 0, fifo_seq = 0, errors = 0, repeats = 0;
        uint64_t fifo_received = 0, fifo_gaps = 0, loops = 0, skipped_wakes = 0;
        uint64_t first_publish_tick = 0, last_publish_tick = 0;
        bool stalled = false;
        auto validate = [&](const amp_record &r) {
            if (!amp_record_valid(&r) || r.session != session) ++errors;
        };
        auto drain = [&] {
            for (unsigned n = 0; n < AMP_FIFO_CAP; ++n) {
                amp_record r; auto a = ns(); bool got = amp_fifo_pop(&d->fifo, &h->tail, &r); auto b = ns();
                if (!got) break;
                fifo_cost.push_back(b - a); validate(r);
                if (r.seq == 1) first_publish_tick = (uint64_t(r.tick_hi) << 32) | r.tick_lo;
                if (r.seq <= fifo_seq) ++errors;
                else fifo_gaps += r.seq - fifo_seq - 1u;
                fifo_seq = r.seq; ++fifo_received;
            }
        };
        while (!interrupted && mono_ns() < deadline) {
            next += 4000000; sleep_until(next); auto now = mono_ns();
            wake_late.push_back(now > next ? now - next : 0);
            if (now > next + 4000000) { auto missed = (now - next) / 4000000; skipped_wakes += missed; next += missed * 4000000; }
            if (stall_ms && !stalled && now >= begin + uint64_t(seconds * .5e9)) {
                std::this_thread::sleep_for(std::chrono::milliseconds(stall_ms)); stalled = true;
            }
            auto a = ns(); auto b = ns(); probe_cost.push_back(b - a); ++loops;
            if (!baseline) {
                if (amp_load(&d->state.v) != AMP_RUNNING || amp_load(&d->session.v) != session)
                    throw std::runtime_error("M0 session changed during measurement");
                amp_record r; a = ns(); amp_latest_read(&d->latest, &h->reading, &r); b = ns();
                latest_cost.push_back(b - a); validate(r);
                if (r.seq < latest_seq) ++errors; if (r.seq == latest_seq) ++repeats; latest_seq = r.seq;
                drain();
            }
        }
        uint64_t finish = mono_ns();
        uint32_t final_seq = 0, drops = 0, missed = 0, hz = 0;
        amp_hist ml{}, mf{}, mp{}, mi{};
        if (!baseline) {
            command(d, h, AMP_CMD_STOP); running = false;
            if (amp_load(&d->session.v) != session) throw std::runtime_error("M0 restarted before statistics");
            final_seq = amp_load(&d->final_seq.v); drops = amp_load(&d->fifo_drops.v); missed = amp_load(&d->timer_missed.v);
            amp_record r; amp_latest_read(&d->latest, &h->reading, &r); validate(r);
            last_publish_tick = (uint64_t(r.tick_hi) << 32) | r.tick_lo;
            if (!final_seq || r.seq != final_seq) ++errors;
            drain();
            if (fifo_received + drops != final_seq) ++errors;
            hz = amp_load(&d->timer_hz.v);
            ml = d->latest_cost; mf = d->fifo_cost; mp = d->probe_cost; mi = d->irq_cost;
        }
        std::cout << "{\"backend\":\"" << (simulate ? "host-simulation" : "rk3576-uio-normal-nc")
                  << "\",\"mode\":\"" << (baseline ? "idle-reader-250hz" : "latest-fifo-500-to-250hz")
                  << "\",\"session\":" << session << ",\"elapsed_s\":" << (finish - begin) / 1e9
                  << ",\"loops\":" << loops << ",\"published\":" << final_seq << ",\"fifo_received\":" << fifo_received
                  << ",\"reader_hz\":" << loops * 1e9 / (finish - begin)
                  << ",\"publisher_hz\":" << (last_publish_tick > first_publish_tick && first_publish_tick ?
                      double(final_seq - 1) * hz / (last_publish_tick - first_publish_tick) : 0)
                  << ",\"fifo_drops\":" << drops << ",\"fifo_gaps_observed\":" << fifo_gaps
                  << ",\"latest_repeats\":" << repeats << ",\"correctness_errors\":" << errors
                  << ",\"m0_timer_missed\":" << missed << ",\"linux_skipped_periods\":" << skipped_wakes
                  << ",\"stall_ms\":" << stall_ms << ",\"interrupted\":" << (interrupted ? "true" : "false")
                  << ",\"linux_latest_read\":"; vector_json(latest_cost);
        std::cout << ",\"linux_fifo_pop\":"; vector_json(fifo_cost);
        std::cout << ",\"linux_clock_probe\":"; vector_json(probe_cost);
        std::cout << ",\"linux_wake_lateness\":"; vector_json(wake_late);
        std::cout << ",\"m0_latest_publish\":"; hist_json(ml, hz);
        std::cout << ",\"m0_fifo_push_attempt\":"; hist_json(mf, hz);
        std::cout << ",\"m0_clock_probe\":"; hist_json(mp, hz);
        std::cout << ",\"m0_publisher_body\":"; hist_json(mi, hz);
        std::cout << "}\n";
        return errors || interrupted ? 1 : 0;
    } catch (const std::exception &e) {
        if (running && d && h) { try { command(d, h, AMP_CMD_STOP); } catch (...) {} }
        std::cerr << "amp-shm-bench: " << e.what() << '\n'; return 2;
    }
}
