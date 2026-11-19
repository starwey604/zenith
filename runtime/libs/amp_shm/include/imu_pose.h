// SPDX-License-Identifier: BSD-3-Clause
#ifndef ZENITH_IMU_POSE_H
#define ZENITH_IMU_POSE_H
#include "amp_shm.h"
#include "m0_debug.h"
#define IMU_POSE_OFFSET 48384u
#define IMU_READER_OFFSET 1024u
#define IMU_CLOCK_HZ 24000000u
/* map1: keep the existing reader word; only live viewing uses the lease. */
struct imu_reader { uint32_t reading, live_session, heartbeat; };
AMP_ASSERT(sizeof(struct imu_reader)<=sizeof(struct amp_word),"pose reader bounds");
struct imu_pose {
    uint64_t observed;
    uint32_t spi_ticks, fusion_ticks, pub_offset, seq, session, missed_est, invalid;
    float q[4];       /* w,x,y,z, sensor to initial world; yaw initially zero */
    int16_t accel[3]; /* +/-4g */
    uint16_t valid;
    uint32_t reserved; /* keep the 64-byte wire layout */
};
struct imu_channel {
    struct amp_word ready, latest, index[2]; /* ready=session after initialization */
    struct imu_pose slots[4];
};
AMP_ASSERT(sizeof(struct imu_pose) == 64, "pose ABI");
AMP_ASSERT(IMU_POSE_OFFSET + sizeof(struct imu_channel) <= M0DBG_INFO, "pose overflow");
AMP_ASSERT(IMU_READER_OFFSET + sizeof(struct amp_word) <= M0DBG_CMD, "reader overflow");
#endif
