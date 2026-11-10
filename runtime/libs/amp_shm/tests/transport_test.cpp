// SPDX-License-Identifier: BSD-3-Clause
#include <atomic>
#include <chrono>
#include <cstring>
#include <cstdlib>
#include <iostream>
#include <thread>
#include <memory>

static void copy_record(void *, const void *, size_t);
#define AMP_COPY(d, s) copy_record((d), (s), sizeof(struct amp_record))
#include "amp_shm.h"

static thread_local int role;
static std::atomic<int> pause_role{0}, entered{0}, resume_copy{0};
static void check(bool condition) { if (!condition) std::abort(); }
static void copy_record(void *d, const void *s, size_t n)
{
    std::memcpy(d, s, n / 2);
    if (role && pause_role.load() == role) {
        entered.store(1);
        while (!resume_copy.load()) std::this_thread::yield();
    }
    std::memcpy(static_cast<char *>(d) + n / 2,
                static_cast<const char *>(s) + n / 2, n - n / 2);
}
static amp_record record(uint32_t seq) {
    amp_record r; amp_record_make(&r, seq, 73, seq * 48000ULL, 17, 23, 5); return r;
}
static void seed(amp_device &d) {
    for (auto &pair : d.latest.data) for (auto &slot : pair) slot = record(0);
}
static void wait_entered() {
    auto end = std::chrono::steady_clock::now() + std::chrono::seconds(5);
    while (!entered.load()) { check(std::chrono::steady_clock::now() < end); std::this_thread::yield(); }
}
static void run(void (*read_latest)(const amp_latest *, amp_word *, amp_record *))
{
    auto d = std::make_unique<amp_device>(); amp_host h{}; seed(*d);
    // Full/empty and index rollover. Never overwrite an unread record.
    amp_store(&d->fifo.head.v, UINT32_MAX - 127); amp_store(&h.tail.v, UINT32_MAX - 127);
    for (uint32_t n = 1; n <= AMP_FIFO_CAP; ++n) { auto r = record(n); check(amp_fifo_push(&d->fifo, &h.tail, &r)); }
    auto r = record(999); check(!amp_fifo_push(&d->fifo, &h.tail, &r));
    for (uint32_t n = 1; n <= AMP_FIFO_CAP; ++n) { check(amp_fifo_pop(&d->fifo, &h.tail, &r)); check(r.seq == n && amp_record_valid(&r)); }
    check(!amp_fifo_pop(&d->fifo, &h.tail, &r));
    // Reader suspended halfway through copying; publisher must keep advancing.
    pause_role = 1; entered = 0; resume_copy = 0;
    std::thread reader([&] { role = 1; read_latest(&d->latest, &h.reading, &r); });
    wait_entered();
    for (uint32_t n = 1; n <= 10000; ++n) { auto v = record(n); amp_latest_publish(&d->latest, &h.reading, &v); }
    resume_copy = 1; reader.join(); check(amp_record_valid(&r)); pause_role = 0;
    read_latest(&d->latest, &h.reading, &r); check(r.seq == 10000);
    // Publisher suspended halfway through copying; readers retain a valid value.
    pause_role = 2; entered = 0; resume_copy = 0;
    std::thread writer([&] { role = 2; auto v = record(10001); amp_latest_publish(&d->latest, &h.reading, &v); });
    wait_entered();
    for (int n = 0; n < 10000; ++n) { read_latest(&d->latest, &h.reading, &r); check(r.seq == 10000 && amp_record_valid(&r)); }
    resume_copy = 1; writer.join(); pause_role = 0;
    read_latest(&d->latest, &h.reading, &r); check(r.seq == 10001);
    // Mixed latest/FIFO stress. Every accepted FIFO record must be received once.
    std::atomic<bool> done{false}; uint32_t drops = 0, received = 0;
    std::thread producer([&] {
        for (uint32_t n = 10002; n <= 210001; ++n) {
            auto v = record(n); amp_latest_publish(&d->latest, &h.reading, &v);
            if (!amp_fifo_push(&d->fifo, &h.tail, &v)) ++drops;
        }
        done = true;
    });
    uint32_t latest = 10001, last_fifo = 10001;
    do {
        read_latest(&d->latest, &h.reading, &r);
        check(amp_record_valid(&r) && r.seq >= latest); latest = r.seq;
        while (amp_fifo_pop(&d->fifo, &h.tail, &r)) {
            check(amp_record_valid(&r) && r.seq > last_fifo); last_fifo = r.seq; ++received;
        }
    } while (!done.load() || amp_load(&h.tail.v) != amp_load(&d->fifo.head.v));
    producer.join(); read_latest(&d->latest, &h.reading, &r);
    check(r.seq == 210001 && received + drops == 200000);
    std::cout << "PASS: FIFO full/empty/wrap, paused reader/writer, final freshness, 200000 concurrent publications\n";
}

int main() {
    // Legacy AMP_COPY is fixed at 128 bytes; unrelated generic views must still
    // copy their own size in this same translation unit.
    rpshm_word latest{}, indices[2]{}, reading{};
    uint64_t slots[4]{}, input = 0x12345678abcdefULL;
    struct { uint64_t value, guard; } out{0, 0x55aa};
    rpshm_latest_tx tx{&latest.v, {&indices[0].v, &indices[1].v}, &reading.v, slots, sizeof(input)};
    rpshm_latest_rx rx{&latest.v, {&indices[0].v, &indices[1].v}, &reading.v, slots, sizeof(input)};
    rpshm_latest_publish(&tx, &input); rpshm_latest_read(&rx, &out.value);
    check(out.value == input && out.guard == 0x55aa);
    run(amp_latest_read_reference);
    run(amp_latest_read_merged);
}
