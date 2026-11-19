// SPDX-License-Identifier: BSD-3-Clause
#ifndef ZENITH_M0_DEBUG_H
#define ZENITH_M0_DEBUG_H
#include <stdint.h>
#define M0DBG_MAGIC 0x4d304431u /* M0D1 */
#define M0DBG_READY_CONSOLE_ONLY 2u /* no independent AMP benchmark producer */
#define M0DBG_INFO  48896u     /* map0: M0 publishes, Linux reads */
#define M0DBG_CMD   4096u      /* map1: Linux writes */
#define M0DBG_LOG   8192u      /* map1 upper half: M0 writes, Linux only reads */
#define M0DBG_BYTES 8192u
#define M0DBG_LINE  80u
struct m0dbg_info {
    uint32_t magic, boot, revision, end, kept, evicted, ack, ready;
    int32_t result;
};
struct m0dbg_cmd { uint32_t request, boot; char line[M0DBG_LINE]; };
#endif
