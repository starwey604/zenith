# LBC3 CAM0：AR0234 1080p / 标称 120 fps

当前 LBC3 v2 AMP 内核已接入 DECXIN-3478V1，默认 **1920×1080、RAW10、四通道**。
按寄存器时序计算为 **119.7547 fps**，保留 720p 对照模式。
源码、内核和启动分区镜像已编译验证；尚未在 LBC3 上刷写、读芯片 ID 或采集图像。

## 使用这次生成的启动镜像

- 候选启动分区镜像：
  `/home/ww/codings/zenith/out/ar0234-cam0-20261106/1080p120/boot.img`
- 修改前的**本地构建镜像**：
  `/home/ww/codings/zenith/out/ar0234-cam0-20261106/before/boot.img`
- 构建和测试日志：
  `/home/ww/codings/zenith/out/ar0234-cam0-20261106/logs/`

候选是 SDK 的 **128 MiB extboot 分区镜像**；请勿与 `/home/ww/codings/lbc_kernel/boot.img` 混用。
当前 `/home/ww/codings/lbc_sdk/output/firmware/boot.img` 指向同一版 extboot 产物。
没有重打包全盘 `update.img`，不要拿旧的 `update.img` 当作本次结果。
刷写前需核对板上的分区布局与恢复方式；本轮未操作开发板。

硬件使用修正电源后的四层转接板，插 **CAM0**，配 **22P、0.5 mm、异面接触排线**，
两端连接器同号相连。断开全部供电后核对 1→1、22→22，确认 3.3 V 与 GND 不短接。
旧实物板的 B2B CN1.2 若仍连 5 V，必须先修正为 GND；不能靠换排线解决。

## 模式与时序

| 项目 | 1080p（本次默认） | 720p（保留） |
|---|---:|---:|
| 尺寸 | 1920×1080 | 1280×720 |
| RAW / Bayer | RAW10 / GRBG | RAW10 / GRBG |
| 数据通道 / 每通道速率 | 4 / 900 Mbit/s | 4 / 900 Mbit/s |
| link frequency | 450 MHz | 450 MHz |
| 模组晶振 / 内部读出时钟 | 24 / 90 MHz | 24 / 90 MHz |
| 行长寄存器 | 612 | 612 |
| 等效 HTS / pixel_rate | 2448 / 360 MHz | 2448 / 360 MHz |
| 每行时间 | 6.8 µs | 6.8 µs |
| 默认帧长寄存器 | 1223 | 1477 |
| 最小 / 默认 VBLANK | 148 / 148 | 506 / 762 |
| 默认帧率（计算） | 119.7547 fps | 99.2300 fps |
| 最高帧率（计算） | 119.7547 fps | 119.9501 fps |
| 默认曝光 | 1028 行，6.9904 ms | 1028 行，6.9904 ms |

帧周期为 `612 × (height + VBLANK) / 90,000,000` 秒；帧长寄存器不包含额外 5 行开销。
1080p 的帧周期为 8.3504 ms，活跃行读出约 7.344 ms，帧间空闲约 1.0064 ms。
这里的时间均是寄存器模型计算，真实帧率和丢帧情况以采集时间戳为准。

商家 1080p 表使用 681 行长；直接四通道倍速、贴近 120 fps 时只剩约 0.17 ms 空白。
当前 RK3576 BSP 的 `rkcif_check_vblank_value()` 对 ISP 在线模式要求至少约 1 ms，
因此本版采用原参考驱动已有的 612 行长，并保留 148 行空白，而不把默认值硬设成精确 120。
参考驱动支持四通道 RAW10 的 1080p 高帧率模式，见
[Kurokesu 驱动模式表](https://github.com/Kurokesu/ar0234-rpi-driver#output-formats)。

1080p120 的 RAW 有效载荷约 2.488 Gbit/s，低于四通道合计 3.6 Gbit/s 的线速率。
RK3576 提供四通道 CSI 和 16M ISP，见
[Rockchip 简版规格书](https://www.rock-chips.com/uploads/pdf/2024.3.18/191/RK3576%20Brief%20Datasheet.pdf)。
这些是选型与时序依据，LBC3 的持续采集、ISP 输出及编码吞吐仍需分别验证。

## 驱动与设备树落点

内核仓库 `/home/ww/codings/lbc_kernel`：

- `drivers/media/i2c/ar0234.c`、`ar0234-decxin-3478v1.h`：从 Aura 保存的内核补丁
  0012/0013/0014/0015/0021/0022 重放得到，再增加 LBC 的 1080p 模式。
- `drivers/media/i2c/Kconfig`、`Makefile`：注册 `CONFIG_VIDEO_AR0234`。
- `arch/arm64/configs/lubancat_rk3576_headless.config`：内建驱动；有效配置仅新增该项。
- `arch/arm64/boot/dts/rockchip/rk3576-lubancat-3-ar0234-cam0.dtsi`：摄像头专用接入。
- `rk3576-lubancat-3-v2-mcu.dts`：包含上述文件，继续使用原有 AMP 启动入口，
  不改变 boot_init 的板型选择、M0 内存、UART5、网口或无显示设置。

链路为 `I²C3@0x10 → csi2_dcphy0 → mipi0_csi2 → rkcif_mipi_lvds → rkisp_vir0 → rkvpss_vir0`。
RTC `I²C3@0x51` 保留；CAM0 的其他传感器和固定焦距模组上不存在的 DW9714 不启用。
模组使用独立固定 24 MHz 时钟描述，以及转接板 5 V→3.3 V 固定稳压描述；
不绑定未连接的 reset/PWDN/MCLK GPIO，不把模组内部三路电源当成外部输入。
不需要再启用厂商 IMX415/OV8858 等 CAM0 overlay，也不能同时启用它们。

新 compatible `decxin,3478v1-1080p120` 默认选择 1080p。
原 `decxin,3478v1-fastreadout` 仍默认 720p，原两通道 `decxin,3478v1` 不变。
四通道模式使用同一份商家校正与初始化序列，在原写入位置替换裁剪、行长、帧长与曝光；
两处 `0x31AE` 均写 `0x0204`，保留软件复位、跳过 45 MHz 专用 sequencer 补丁和连续时钟。
每模式独立 VBLANK 下限，重复设置同一尺寸不会重置已选帧率。

当前改动位于内核 fork 基线 `79c7f9aadf5d17ec552f48c307802288106a822b` 之上的工作区。
本次只提交并推送 Zenith，内核 fork 尚未提交或推送，`sdk/baseline.toml` 的内核 pin 不变。
为保存本次候选源码，可重放差异归档在
[`patches/lbc3-ar0234-cam0.patch`](patches/lbc3-ar0234-cam0.patch)。
它是待上板验证的候选快照，不加入 `sdk/series.tsv`；内核仍按项目惯例由个人 fork 维护。

若在上述基线的新内核工作区重建，先应用此快照（当前已修改的工作区不用重复应用）：

```sh
git -C ../lbc_kernel apply --check "$PWD/docs/patches/lbc3-ar0234-cam0.patch"
git -C ../lbc_kernel apply "$PWD/docs/patches/lbc3-ar0234-cam0.patch"
```

以上命令在 Zenith 根目录运行。驱动逻辑测试还依赖同级 `luckfox-aura-teleop` 仓库中的
`tests/ar0234/test_vendor_profile.py` 和商家原始 INI；可用 `--aura-repo` 指定其位置。

## 重建与已完成验证

沿用当前已选择的 `LubanCat_rk3576_buildroot_amp_mcu_defconfig`：

```sh
distrobox enter aura-sdk -- bash -lc \
  'cd /home/ww/codings/lbc_sdk && taskset -c 0-3 ./build.sh kernel'

distrobox enter aura-sdk -- bash -lc \
  'cd /home/ww/codings/zenith && ./tools/test-lbc-ar0234-driver'

/home/ww/codings/zenith/tools/test-lbc-ar0234-dtb \
  /home/ww/codings/lbc_kernel/arch/arm64/boot/dts/rockchip/rk3576-lubancat-3-v2-mcu.dtb
```

- Clang 15、ThinLTO、PREEMPT_RT 完整 SDK 内核/DTB/extboot 构建通过。
- AR0234 单对象 `W=1 KCFLAGS=-Werror` 编译通过，最终内核包含驱动。
- 15 项真实驱动函数的宿主模拟测试通过：原 720p 行为、1080p vendor 序列对照、
  帧率钳制、切换模式、裁剪及每次初始化 I²C 写失败后的清理。
- 6 项有效 DTB 测试通过：双端 lane/互连、供电/时钟、单目链路、RTC、AMP 与无显示状态；
  与修改前 DTB 对照，相关非相机节点保持原配置。
- 从最终 boot 分区取出的 DTB、Image、配置与对应构建产物一致，文件系统检查通过。

完整 BSP 仍有已有的配置合并提示及 W=1 设备树警告；AR0234 源码与新增 DTSI 的
checkpatch 为零错误、零警告。所有验证均未访问开发板。

## 上板先验证 RAW，再接 ISP

新版转接板接线和供电检查完成、用户确认刷写后，先检查：

```sh
uname -a
cat /sys/bus/i2c/devices/3-0010/chip_id
dmesg | grep -Ei 'ar0234|dcphy|csi|rkcif|rkisp'
v4l2-ctl --list-devices
for m in /dev/media*; do media-ctl -d "$m" -p; done
```

彩色模组预期 ID `0x0a56`；驱动日志应为 1920×1080、4 lanes、450 MHz link。
在 media graph 中确认 `m00_b_ar0234 3-0010`，不要照搬 Aura 的 `/dev/video13`。

首次只做 **120 帧 RAW 短测**：停止占用相机的应用/3A 服务后，按设备名选择
`stream_cif_mipi_id0`，格式为 1920×1080、`BA10`（本 BSP 的 GRBG10 FourCC），
输出到 `/dev/null`，检查帧序号、约 8.3504 ms 周期及新增 CSI ECC/CRC/溢出错误。
若改过帧率，把 sensor 的 `vertical_blanking` 设回 148；短曝光可选 148 行（1.0064 ms）。
只有 RAW 稳定后，再测试 ISP NV12 与 MPP 编码，分别记录其实际帧率。

**当前 rootfs 没有这颗模组的 RK3576 ISP39 IQ 文件。** Aura 的传感器校正表已经保留，
但它不等于 RKAIQ 调校文件。RAW 链路验证不需要 IQ；正常 ISP 色彩、AE/AWB 输出需要
为 `ar0234 / DECXIN-3478V1 / DECXIN-123deg` 准备匹配的 ISP39 调校，不能把其他传感器
文件改名顶替。本次没有导入 Aura 的 ISP 用户态库或改动现有 3A 服务。
