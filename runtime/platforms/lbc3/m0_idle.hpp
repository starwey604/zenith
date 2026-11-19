// SPDX-License-Identifier: BSD-3-Clause
#pragma once
#include "amp_receiver.h"
#include "m0_debug.h"

// Older lab images also have an independently controlled synthetic producer.
inline bool m0_producer_idle(const amp_device *device, const m0dbg_info *debug) {
    if (amp_load(&debug->magic) == M0DBG_MAGIC &&
        amp_load(&debug->ready) == M0DBG_READY_CONSOLE_ONLY)
        return true;
    auto peer = reinterpret_cast<const rpshm_session_peer *>(
        reinterpret_cast<const char *>(device) + AMP_SESSION_PEER_OFFSET);
    auto state = amp_load(&device->state.v);
    return amp_load(&device->magic.v) == AMP_MAGIC && (state == AMP_IDLE || state == AMP_STOPPED) &&
           amp_load(&peer->magic) == RPSHM_SESSION_MAGIC && amp_load(&peer->state) == RPSHM_QUIET;
}
