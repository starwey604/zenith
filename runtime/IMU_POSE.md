# 读取 M0 姿态与测量帧龄

ICM-45686、M0 和 Linux 已通过同一条真实数据链：M0 观察 INT1 数据就绪，读取六轴数据，更新一次 Mahony，将 64 字节姿态记录发布到 RPShm 四槽 LATEST。Linux 直接在板上读快照，SSH 不参与计时。

## 本机实时对照：800 Hz 解算，250 Hz 看姿态

在本机运行（Python 3 + PySide6；开发机已安装）：

```sh
/home/ww/codings/zenith/tools/lbc-imu-view
```

把板子放稳约 1 秒，窗口显示“实时”后再转动。正方体与红 X、绿 Y、蓝 Z 一起转，地面网格固定；下方显示横滚、俯仰、相对航向。对照顶板 IMU 旁的轴向丝印，不以排针或屏幕边缘为准。六轴没有绝对北向；初始航向定义为零，之后可能漂移。窗口接收 250 Hz 四元数，绘图约 60 Hz、只画最新样本，不对角度再滤波。

默认一条 SSH 连接负责启停和传数据；加 `--udp` 可让同一 SSH 会话负责启停、UDP 单播到本机临时端口传姿态（需直连 IPv4，允许板端发来的 UDP）。窗口底部的 ROLL/PITCH/YAW 单位是度，图中的 IMU 和 RX 是实测速率。关闭窗口或点“断开”会让 M0 停止采样并恢复寄存器；点击“重连”开始新一轮静置校准。实时窗口独占 UIO，运行基准或 `m0ctl` 之前先断开窗口。

ICM-45686 的加速度计和陀螺仪均使用 800 Hz 原生档，邻档为 1600 Hz，无 1000 Hz 档（[TDK 寄存器定义](https://github.com/tdk-invn-oss/motion.mcu.icm45686.driver/blob/main/icm45686/imu/inv_imu_defs.h)）。2026-11-19 的 60 秒板测实测 **793.595 Hz**；Linux 取到 **15,000** 个新姿态，未错过唤醒、无无效样本，按间隔估计的漏采为 0。M0 中断入口到 Linux 读完的 P50/P99/最大值分别为 **0.853 / 1.470 / 1.486 ms**，不含网络及显示。单独实测了 SSH 与 UDP 窗口接收、断开以及 SSH 重连。

## 复测延迟

先断开姿态窗口，保持板子静止约一秒，再从宿主机运行：

```sh
ssh root@192.168.77.2 '/root/imu-pose-bench /tmp/pose.csv'
```

程序在 CPU4 每 4 ms 读取最新四元数，持续 60 秒。终端显示中位数、P99 和最大值；板端 CSV 按新帧记录序号、四元数（w,x,y,z）、六轴中的加速度分量（8192 counts/g）和计时。已有同名文件会被覆盖。校准不计入测量，结束后 M0 恢复 IMU 配置。

| 指标 | 从哪里计时 |
|---|---|
| `acquire` | M0 进入 INT1 中断 → SPI 读完同帧六轴，含线程唤醒 |
| `fusion` | SPI 读完 → Mahony 更新完成 |
| `latest_copy` | Linux 本核选槽并复制快照 |
| `first_delivery` | M0 开始发布 → Linux 首次读完该新帧 |
| `first_age` | M0 进入 INT1 中断 → Linux 首次读完该新帧 |

跨核计时共用 24 MHz TIMER11，不含传感器内部滤波、网络或绘图。250 Hz 读者只取最新值，因此 `linux_skips` 统计未取走的中间帧；`m0_missed_est` 才是按相邻中断间隔估算的漏采周期。

## 构建与板端配置

配套 RTOS：`lbc_sdk/rtos` 的本地分支 `lbc/imu-pose`，提交 `f7a3ffd`。SDK manifest 仍固定在已发布的旧版；重建时使用这次的 RTOS 提交。

从 Zenith 根目录执行 `tools/lbc-m0-deploy --build-only` 构建固件和两个 Linux 工具；去掉参数将备份 AMP 分区、安装配套程序并重启整板，见 [M0 调试与回退](M0_DEBUG.md)。只更新延迟工具时，无须重刷：先断开窗口，再把 `out/runtime/m0-debug/imu-pose-bench` 上传到板端 `/root/imu-pose-bench.new`，设为可执行并重命名为 `/root/imu-pose-bench`。未更新的旧板端程序仍使用 `periodic 800 60 /tmp/pose.csv` 参数；姿态窗口与它兼容。

SDK 的 RTOS、Zenith 和 RPShm 共用同一份传输定义。默认目录为并列的 `lbc_sdk/`、`zenith/`、`rpshm/`。固件直接包含 Zenith 的 `runtime/libs/amp_shm/include/imu_pose.h`：map0 偏移 48384 是发布区，map1 偏移 1024 是读者控制区。GPIO4_A0（排针 22）须由 M0 独占，采样时路由到 GPIO4_EXP3 的 IRQ4。SPI 请求 1 MHz，量程为 ±4 g、±500 °/s；沿用 [one-framework 的 Mahony 更新](https://github.com/RoboMaster-DLMU-CONE/one-framework/blob/main/include/OF/utils/Mahony.hpp)，Kp=1.5、Ki=0。
