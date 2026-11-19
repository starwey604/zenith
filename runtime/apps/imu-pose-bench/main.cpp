// SPDX-License-Identifier: BSD-3-Clause
#include "amp_uio.hpp"
#include "m0_idle.hpp"
#include "imu_pose.h"
#include <algorithm>
#include <cerrno>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <vector>
#include <time.h>
#include <sched.h>
#include <unistd.h>
static uint64_t ns(clockid_t c = CLOCK_MONOTONIC) {
    timespec t;
    if (clock_gettime(c, &t))
        throw std::runtime_error("clock_gettime");
    return uint64_t(t.tv_sec) * 1000000000 + t.tv_nsec;
}
static void until(uint64_t deadline) {
    timespec t = {time_t(deadline / 1000000000), long(deadline % 1000000000)};
    int rc;
    do {
        rc = clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &t, nullptr);
    } while (rc == EINTR);
    if (rc)
        throw std::runtime_error("clock_nanosleep");
}
// Keep every observation in a bounded histogram. Quantiles are upper bin edges;
// maxima are exact, overflow quantiles are not silently clipped.
struct Hist {
    double quantum, scale;
    std::vector<unsigned> bins = std::vector<unsigned>(65537);
    uint64_t count = 0, peak = 0;
    Hist(double q, double us) : quantum(q), scale(us) {}
    void add(uint64_t t) {
        ++bins[std::min<size_t>(65536, size_t(t / quantum))];
        ++count;
        peak = std::max(peak, t);
    }
    double pct(double p) const {
        uint64_t n = 0;
        for (size_t i = 0; i < 65536; i++) {
            n += bins[i];
            if (count && n >= std::ceil(count * p))
                return std::min(double(peak), (i + 1) * quantum - 1) * scale;
        }
        return NAN;
    }
    void print(const char *name) const {
        printf("%-20s %10llu %10.3f %10.3f %10.3f\n", name, (unsigned long long)count, pct(.5), pct(.99),
               peak * scale);
    }
};
struct Row {
    imu_pose f;
    uint64_t received;
};
#include "live.hpp"
static int bench(int argc, char **argv) {
    const bool live = argc == 5 && std::string(argv[1]) == "live";
    if ((!live && (argc != 2 || argv[1][0] == '-')) || (live && std::string(argv[2]) != "800"))
        throw std::runtime_error("usage: imu-pose-bench OUTPUT.csv");
    constexpr unsigned hz = 800, secs = 60;
    constexpr uint64_t read_period_ns = 4000000; // 250 Hz business reader
    cpu_set_t cpus;
    CPU_ZERO(&cpus);
    CPU_SET(4, &cpus);
    if (sched_setaffinity(0, sizeof(cpus), &cpus))
        throw std::runtime_error("CPU4 affinity");
    AmpUio map;
    auto ro = (const char *)map.device;
    auto rw = (char *)map.host;
    auto *dbg = (const m0dbg_info *)(ro + M0DBG_INFO);
    auto *cmd = (m0dbg_cmd *)(rw + M0DBG_CMD);
    auto *ch = (const imu_channel *)(ro + IMU_POSE_OFFSET);
    auto *reading = (uint32_t *)(rw + IMU_READER_OFFSET);
    rpshm_latest_rx rx = {
        &ch->latest.v, {&ch->index[0].v, &ch->index[1].v}, reading, ch->slots, sizeof(imu_pose)};
    uint32_t boot = amp_load(&dbg->boot), req = amp_load(&cmd->request);
    if (amp_load(&dbg->magic) != M0DBG_MAGIC || !amp_load(&dbg->ready) || amp_load(&dbg->ack) != req ||
        !m0_producer_idle(map.device, dbg))
        throw std::runtime_error("M0 not idle");
    uint64_t ca = ns(), ta = map.clock_ticks();
    until(ca + 100000000);
    uint64_t tb = map.clock_ticks(), cb = ns();
    double timer_hz = 1e9 * (tb - ta) / (cb - ca);
    if (std::abs(timer_hz / IMU_CLOCK_HZ - 1) > .01)
        throw std::runtime_error("TIMER11 rate mismatch");
    if (live)
        return live_view(argv[3], std::stoul(argv[4]), hz, dbg, cmd, ch, (imu_reader *)reading, rx,
                         boot, req);
    FILE *file = fopen(argv[1], "w");
    if (!file)
        throw std::runtime_error("open result CSV");
    std::vector<Row> rows;
    rows.reserve((secs + 1) * hz + 128);
    Hist acquire(1, 1. / 24), fusion(1, 1. / 24), delivery(2, 1. / 24),
        age(2, 1. / 24), copy(4, .001);
    uint32_t session = ++req;
    if (!session)
        session = 1;
    // Exclusive UIO open arbitrates console/bench callers. Command is finite even on SSH loss.
    amp_store(reading, 0);
    snprintf(cmd->line, sizeof(cmd->line), "icm45686 stream_irq %u %u %u", hz,
             secs + 1, session);
    amp_store(&cmd->boot, boot);
    amp_store(&cmd->request, req);
    auto check = [&] {
        if (amp_load(&dbg->boot) != boot)
            throw std::runtime_error("M0 restarted");
    };
    uint64_t limit = ns() + 6500000000ull;
    while (amp_load(&ch->ready.v) != session || amp_load(&dbg->ack) == req) {
        check();
        if (amp_load(&dbg->ack) == req || ns() > limit)
            throw std::runtime_error("stream failed to start: see m0ctl logs");
        usleep(1000);
    }
    uint64_t start = 0, cpu = 0, wall = 0, next = 0, skipped_wakes = 0;
    uint32_t prev = 0, gaps = 0;
    double norm_err = 0;
    for (;;) {
        uint64_t now = ns();
        if (start && now - start >= secs * 1000000000ull) {
            wall = now - start;
            break;
        }
        if (amp_load(&dbg->ack) == req || (!start && now > limit))
            throw std::runtime_error("producer stopped early");
        check();
        imu_pose f;
        uint64_t a = ns(CLOCK_MONOTONIC_RAW);
        rpshm_latest_read(&rx, &f);
        uint64_t b = ns(CLOCK_MONOTONIC_RAW), t = map.clock_ticks();
        if (f.seq && f.session == session && f.valid) {
            if (t < f.observed + f.pub_offset || f.pub_offset < f.spi_ticks + f.fusion_ticks ||
                f.seq < prev)
                throw std::runtime_error("invalid timestamp/sequence");
            if (!start) {
                start = now;
                cpu = ns(CLOCK_THREAD_CPUTIME_ID);
                next = start;
            }
            copy.add(b - a);
            if (prev != f.seq) {
                if (prev) gaps += f.seq - prev - 1;
                prev = f.seq;
                double n = 0;
                for (float q : f.q)
                    n += q * q;
                if (!std::isfinite(n) || std::abs(n - 1) > .002)
                    throw std::runtime_error("invalid quaternion");
                norm_err = std::max(norm_err, std::abs(sqrt(n) - 1));
                acquire.add(f.spi_ticks);
                fusion.add(f.fusion_ticks);
                age.add(t - f.observed);
                delivery.add(t - f.observed - f.pub_offset);
                rows.push_back({f, t});
            }
        }
        if (start) {
            next += read_period_ns;
            auto n = ns();
            if (n > next) {
                auto lost = (n - next) / read_period_ns + 1;
                next += lost * read_period_ns;
                skipped_wakes += lost;
            }
            until(next);
        }
    }
    double cpu_pct = 100. * (ns(CLOCK_THREAD_CPUTIME_ID) - cpu) / wall;
    limit = ns() + 3500000000ull;
    while (amp_load(&dbg->ack) != req) {
        check();
        if (ns() > limit)
            throw std::runtime_error("M0 cleanup timeout");
        usleep(10000);
    }
    if (dbg->result)
        throw std::runtime_error("M0 acquisition/restore failed");
    printf("sampling=int1-irq reader_hz=250 imu_hz=%u window_s=%.6f timer_hz=%.0f cpu4_pct=%.3f\n",
           hz, wall / 1e9, timer_hz, cpu_pct);
    auto &first = rows.front().f;
    auto &last = rows.back().f;
    printf("frames=%zu first=%u last=%u linux_skips=%u m0_missed_est=%u invalid=%u wake_skips=%llu "
           "norm_err_max=%.8f observed_hz=%.3f\n",
           rows.size(), first.seq, last.seq, gaps, last.missed_est - first.missed_est,
           last.invalid - first.invalid, (unsigned long long)skipped_wakes, norm_err,
           24e6 * (last.seq - first.seq) / (last.observed - first.observed));
    printf("metric(us)                    n        p50        p99        max\n");
    acquire.print("acquire");
    fusion.print("fusion");
    copy.print("latest_copy");
    delivery.print("first_delivery");
    age.print("first_age");
    fprintf(file, "seq,session,observed,spi_ticks,fusion_ticks,publish_offset,received,qw,qx,qy,qz,ax,ay,"
                  "az,missed_est,invalid\n");
    for (auto &[f, t] : rows)
        fprintf(file, "%u,%u,%llu,%u,%u,%u,%llu,%.9g,%.9g,%.9g,%.9g,%d,%d,%d,%u,%u\n", f.seq, f.session,
                (unsigned long long)f.observed, f.spi_ticks, f.fusion_ticks, f.pub_offset,
                (unsigned long long)t, f.q[0], f.q[1], f.q[2], f.q[3], f.accel[0], f.accel[1], f.accel[2],
                f.missed_est, f.invalid);
    if (fclose(file))
        throw std::runtime_error("write result CSV");
    return 0;
}
int main(int argc, char **argv) {
    try {
        return bench(argc, argv);
    } catch (const std::exception &e) {
        fprintf(stderr, "%s\n", e.what());
        return 1;
    }
}
