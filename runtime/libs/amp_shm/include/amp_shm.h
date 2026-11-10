/* SPDX-License-Identifier: BSD-3-Clause */
/* Wire ABI v1. No pointers, packed fields, bitfields, or atomic RMW operations. */
#ifndef ZENITH_AMP_SHM_H
#define ZENITH_AMP_SHM_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>

#define AMP_MAGIC 0x41535031u
#define AMP_VERSION 1u
#define AMP_WINDOW_SIZE 65536u
#define AMP_HOST_OFFSET 49152u
#define AMP_FIFO_CAP 256u
#define AMP_HIST_BINS 512u
#define AMP_CMD_STOP 1u
#define AMP_CMD_RUN 2u
#define AMP_IDLE 1u
#define AMP_RUNNING 2u
#define AMP_STOPPED 3u
#define AMP_ERROR 4u

/* Legacy test wire layout and entry points; transport lives in RPShm. */
#include <rpshm/access.h>
static inline void amp_fence(void) { rpshm_fence(); }
static inline uint32_t amp_load(const uint32_t *p) { return rpshm_load(p); }
static inline void amp_store(uint32_t *p, uint32_t v) { rpshm_store(p, v); }

struct amp_word { uint32_t v, pad[15]; };
struct amp_record {
    uint32_t seq, session, tick_lo, tick_hi;
    uint32_t previous_latest_ticks, previous_fifo_ticks, probe_ticks, guard;
    uint32_t pattern[24];
};
struct amp_latest {
    struct amp_word latest, index[2];
    struct amp_record data[2][2];
};
struct amp_fifo {
    struct amp_word head;
    struct amp_record data[AMP_FIFO_CAP];
};
struct amp_hist {
    uint32_t count, min, max, reserved;
    uint64_t sum;
    uint32_t bins[AMP_HIST_BINS + 1]; /* Last bin is >= AMP_HIST_BINS. */
};
struct amp_device {
    struct amp_word magic, version, state, ack, session, final_seq, fifo_drops;
    struct amp_word timer_hz, publish_hz, timer_missed;
    struct amp_latest latest;
    struct amp_fifo fifo;
    /* Frozen before STOP ack: otherwise read only through sampled records. */
    struct amp_hist latest_cost, fifo_cost, probe_cost, irq_cost;
};
struct amp_host {
    struct amp_word command;
    struct amp_word reading; /* Written even when the value is unchanged. */
    struct amp_word tail;
};

#if defined(__cplusplus)
#define AMP_ASSERT static_assert
#else
#define AMP_ASSERT _Static_assert
#endif
AMP_ASSERT(sizeof(struct amp_record) == 128, "record ABI");
AMP_ASSERT(sizeof(struct amp_word) == 64, "control ABI");
AMP_ASSERT(sizeof(struct amp_device) <= AMP_HOST_OFFSET, "device window overflow");
AMP_ASSERT(sizeof(struct amp_host) <= AMP_WINDOW_SIZE - AMP_HOST_OFFSET, "host window overflow");
AMP_ASSERT(offsetof(struct amp_latest, data) % 64 == 0, "slot alignment");
AMP_ASSERT(offsetof(struct amp_device, latest) == 640, "latest wire offset");
AMP_ASSERT(offsetof(struct amp_device, fifo) == 1344, "FIFO wire offset");
AMP_ASSERT(offsetof(struct amp_device, latest_cost) == 34176, "statistics wire offset");
AMP_ASSERT(sizeof(struct amp_device) == 42496, "device wire size");
AMP_ASSERT(sizeof(struct amp_host) == 192, "host wire size");

static inline uint32_t amp_pattern(uint32_t seq, uint32_t session, uint32_t i)
{
    uint32_t x = seq ^ session ^ (0x9e3779b9u * (i + 1));
    x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15;
    return x;
}
static inline uint32_t amp_guard(const struct amp_record *r)
{
    return r->seq ^ r->session ^ r->tick_lo ^ r->tick_hi ^
           r->previous_latest_ticks ^ r->previous_fifo_ticks ^ r->probe_ticks ^ 0x51a7cafeu;
}
static inline void amp_record_make(struct amp_record *r, uint32_t seq, uint32_t session,
                                   uint64_t ticks, uint32_t lc, uint32_t fc, uint32_t probe)
{
    unsigned i;
    r->seq = seq; r->session = session;
    r->tick_lo = (uint32_t)ticks; r->tick_hi = (uint32_t)(ticks >> 32);
    r->previous_latest_ticks = lc; r->previous_fifo_ticks = fc; r->probe_ticks = probe;
    r->guard = amp_guard(r);
    for (i = 0; i < 24; ++i) r->pattern[i] = amp_pattern(seq, session, i);
}
static inline int amp_record_valid(const struct amp_record *r)
{
    unsigned i;
    if (r->guard != amp_guard(r)) return 0;
    for (i = 0; i < 24; ++i)
        if (r->pattern[i] != amp_pattern(r->seq, r->session, i)) return 0;
    return 1;
}

/* Keep the existing benchmark copy hook and wire layout. Views are local,
 * constructed inline; neither their pointers nor size_t enter shared RAM. */
#ifdef AMP_COPY
/* A legacy fixed-record hook must not change copies for other RPShm users. */
#define RPSHM_COPY(d, s, n) do { \
    if ((n) == sizeof(struct amp_record)) { AMP_COPY(d, s); } \
    else { memcpy((d), (s), (n)); } \
} while (0)
#endif
#include <rpshm/rpshm.h>
#ifdef AMP_COPY
#undef RPSHM_COPY
#else
#define AMP_COPY(dst, src) memcpy((dst), (src), sizeof(struct amp_record))
#endif
static inline struct rpshm_latest_rx amp_latest_rx(const struct amp_latest *s, struct amp_word *reading)
{
    struct rpshm_latest_rx v = { &s->latest.v, {&s->index[0].v, &s->index[1].v},
        &reading->v, s->data, sizeof(struct amp_record) };
    return v;
}
static inline void amp_latest_publish(struct amp_latest *s, const struct amp_word *reading,
                                     const struct amp_record *value)
{
    struct rpshm_latest_tx v = { &s->latest.v, {&s->index[0].v, &s->index[1].v},
        &reading->v, s->data, sizeof(struct amp_record) };
    rpshm_latest_publish(&v, value);
}
static inline const struct amp_record *amp_latest_select_reference(const struct amp_latest *s,
                                                                  struct amp_word *reading)
{
    struct rpshm_latest_rx v = amp_latest_rx(s, reading);
    return (const struct amp_record *)rpshm_latest_select_reference(&v);
}
static inline const struct amp_record *amp_latest_select_merged(const struct amp_latest *s,
                                                               struct amp_word *reading)
{
    struct rpshm_latest_rx v = amp_latest_rx(s, reading);
    return (const struct amp_record *)rpshm_latest_select_merged(&v);
}
static inline void amp_latest_read_reference(const struct amp_latest *s, struct amp_word *reading,
                                             struct amp_record *out)
{
    struct rpshm_latest_rx v = amp_latest_rx(s, reading);
    rpshm_latest_read_reference(&v, out);
}
static inline void amp_latest_read_merged(const struct amp_latest *s, struct amp_word *reading,
                                          struct amp_record *out)
{
    struct rpshm_latest_rx v = amp_latest_rx(s, reading);
    rpshm_latest_read_merged(&v, out);
}
static inline void amp_latest_read(const struct amp_latest *s, struct amp_word *reading, struct amp_record *out)
{ amp_latest_read_reference(s, reading, out); }
static inline int amp_fifo_push(struct amp_fifo *q, const struct amp_word *tail, const struct amp_record *value)
{
    struct rpshm_fifo_tx v = { &q->head.v, &tail->v, q->data, sizeof(struct amp_record), AMP_FIFO_CAP };
    return rpshm_fifo_push(&v, value);
}
static inline int amp_fifo_pop(const struct amp_fifo *q, struct amp_word *tail, struct amp_record *out)
{
    struct rpshm_fifo_rx v = { &q->head.v, &tail->v, q->data, sizeof(struct amp_record), AMP_FIFO_CAP };
    return rpshm_fifo_pop(&v, out);
}
static inline void amp_hist_add(struct amp_hist *h, uint32_t ticks)
{
    if (!h->count || ticks < h->min) h->min = ticks;
    if (ticks > h->max) h->max = ticks;
    ++h->count; h->sum += ticks;
    ++h->bins[ticks < AMP_HIST_BINS ? ticks : AMP_HIST_BINS];
}
#endif
