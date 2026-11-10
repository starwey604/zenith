/* SPDX-License-Identifier: BSD-3-Clause */
#ifndef ZENITH_AMP_RECEIVER_H
#define ZENITH_AMP_RECEIVER_H
#include "amp_shm.h"
#include <rpshm/receiver.h>
/* Existing RK3576 recovery-firmware extension, not a new library wire format.
 * Keep these offsets consistent with rpshm/tests/rk3576/{layout,research-layout}.h.
 * The old STOP/RUN 500/250 Hz entry point remains independent. */
#define AMP_SESSION_PEER_OFFSET 48000u
#define AMP_SESSION_HOST_OFFSET 512u
#define AMP_EXPERIMENT_HOST_OFFSET 576u
AMP_ASSERT(sizeof(struct amp_device)<=AMP_SESSION_PEER_OFFSET,"session overlaps published data");
AMP_ASSERT(sizeof(struct amp_host)<=AMP_SESSION_HOST_OFFSET,"session overlaps host controls");
struct amp_receiver {
    struct rpshm_receiver endpoint;
    const struct amp_device *device;
    struct amp_host *host;
};
static inline int amp_receiver_prepare(void *context)
{
    struct amp_receiver *r=(struct amp_receiver *)context;
    /* Disable stale experimental START configuration while QUIET. The existing
     * firmware then uses its default full 128-byte/reference publication. */
    rpshm_store((uint32_t *)((unsigned char *)r->host+AMP_EXPERIMENT_HOST_OFFSET),0);
    return 1;
}
static inline int amp_receiver_init(struct amp_receiver *r,
        const struct amp_device *device,size_t peer_bytes,struct amp_host *host,size_t host_bytes)
{
    if (!r || r->endpoint.self || !rpshm_receiver_word_valid(device) || !rpshm_receiver_word_valid(host) ||
        peer_bytes<AMP_SESSION_PEER_OFFSET+sizeof(struct rpshm_session_peer) ||
        host_bytes<AMP_EXPERIMENT_HOST_OFFSET+sizeof(uint32_t)) return 0;
    const struct rpshm_session_peer *peer=(const struct rpshm_session_peer *)
        ((const unsigned char *)device+AMP_SESSION_PEER_OFFSET);
    struct rpshm_session_host *session=(struct rpshm_session_host *)
        ((unsigned char *)host+AMP_SESSION_HOST_OFFSET);
    if (amp_load(&device->magic.v)!=AMP_MAGIC || amp_load(&device->version.v)!=AMP_VERSION ||
        rpshm_load(&peer->magic)!=RPSHM_SESSION_MAGIC) return 0;
    r->device=device;r->host=host;
    struct rpshm_latest_rx latest=amp_latest_rx(&device->latest,&host->reading);
    struct rpshm_fifo_rx fifo={&device->fifo.head.v,&host->tail.v,device->fifo.data,sizeof(struct amp_record),AMP_FIFO_CAP};
    struct rpshm_receiver_config config={session,peer,&latest,sizeof(device->latest.data),
        &fifo,sizeof(device->fifo.data),amp_receiver_prepare,r};
    return rpshm_receiver_init(&r->endpoint,&config);
}
#endif
