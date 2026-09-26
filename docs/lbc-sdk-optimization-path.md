# LubanCat 3 SDK 实时性与裁剪路线

调查日期：2026-09-26。目标是 RK3576 LubanCat 3 v2 的 Linux + Cortex-M0 RT-Thread AMP 镜像；本文记录可实施路径和待验证条件，尚未改动配置或刷板。

## 基线与改动落点

- SDK 入口是 `../../lbc_sdk/device/rockchip/.chips/rk3576/LubanCat_rk3576_buildroot_amp_mcu_defconfig`，指定 `RK_KERNEL_CFG="lubancat_linux_rk3576_defconfig"`、`RK_KERNEL_DTS_NAME="rk3576-lubancat-3-v2-mcu"`、`RK_BUILDROOT_BASE_CFG="rk3576_lubancat"`。
- Buildroot 的项目配置在 `../../lbc_sdk/buildroot/configs/rockchip_rk3576_lubancat_defconfig`。它通过 `#include` 引入通用音视频、蓝牙、无线、Weston、Chromium 等配置片段；实际展开值可在 `../../lbc_sdk/buildroot/output/rockchip_rk3576_lubancat/.config` 核查。后者是构建产物，不能作为修改源。
- 内核源头是独立 fork `../../lbc_kernel`；源码配置为 `arch/arm64/configs/lubancat_linux_rk3576_defconfig`，实际展开配置为 `.config`。板级 DTS 继承链：`rk3576-lubancat-3-v2-mcu.dts` → `rk3576-lubancat-3-v2.dts` → `rk3576-lubancat-3.dts`，另含 `rk3576-amp.dtsi`。优化应新建项目专用 DTS/defconfig，避免把通用 LubanCat 配置改成仅适用于机器人。
- `zenith/sdk/series.tsv` 维护 Buildroot 和 `device/rockchip` 补丁；内核修改进 `lbc_kernel` fork，并同步更新 `zenith/sdk/baseline.toml` 的内核 commit。构建产物、`output/.config` 和 `lbc_kernel/.config` 不进入补丁。

## 1. 实时性：先测抖动，再调配置

当前内核已是 `CONFIG_PREEMPT_RT=y`、`CONFIG_HZ_1000=y`、`CONFIG_HIGH_RES_TIMERS=y`；默认 CPU governor 是 performance，`CONFIG_CPU_ISOLATION=y` 与 `CONFIG_RCU_NOCB_CPU=y` 也已打开。`CONFIG_HZ_PERIODIC=y`，`CONFIG_NO_HZ_FULL` 未启用。不要把这些已具备的能力当成待开启项。

建议按以下顺序做独立实验，每一步保留可回退镜像并记录同一负载下的延迟分布：

1. **建立基线。** 板上记录 `/proc/cmdline`、`uname -a`、`zcat /proc/config.gz`（若可用）、`/proc/interrupts`、CPU 频率和温度；运行 `cyclictest`（或同等周期任务），分别测空载、以太网通信、Wi‑Fi 通信、M0/RPMSG 通信和组合负载的最大值及高分位值。同时记录启动时间、内存与功耗；只看平均值会漏掉最坏情况。
2. **先处理运行时干扰。** 确认 CPU 拓扑后为关键线程指定 CPU 和 `SCHED_FIFO` 优先级，把网卡、Wi‑Fi、存储及普通服务 IRQ 留在 housekeeping CPU；检查 `irqbalance` 是否改写亲和性。可试 `rcu_nocbs=<关键CPU>`、`isolcpus=domain,managed_irq,<关键CPU>`；是否需要 `nohz_full=<关键CPU>` 要单独比较，启用它还须内核改为 `CONFIG_NO_HZ_FULL=y` 并满足运行时约束。不要在尚未测量前固定具体 CPU 号。
3. **评估省电状态。** 当前 performance governor 已避免普通动态调频，但 `CONFIG_CPU_IDLE=y`；短时 A/B 可试 `cpuidle.off=1`。若长时间负载温度或降频恶化，应保留空闲机制或限制深度空闲状态。保留 `tsadc`、风扇和调压器节点。
4. **缩减调试负担。** 当前有 `CONFIG_PM_DEBUG=y`、`CONFIG_PM_ADVANCED_DEBUG=y`、`CONFIG_SCHEDSTATS=y`、`CONFIG_DEBUG_FS=y`、`CONFIG_DEBUG_INFO=y`、`CONFIG_PRINTK_TIME=y`；可逐项评估关闭。`CONFIG_FTRACE` 已关闭。保留一份诊断配置，以便复现问题。缩减 debug info 主要影响构建产物大小，不保证改善运行时延迟。
5. **最后考虑更激进的内核设置。** 用相同负载比较 `HZ_PERIODIC` 与 tickless、IRQ 亲和性、PCIe ASPM（当前为 powersave）对尾延迟和功耗的影响。网络/Wi‑Fi 中断是实际瓶颈时，调 IRQ 与 NAPI 往往比盲目改全局 `CONFIG` 更直接。任何固定频率或禁用深度空闲的方案都须做散热稳态测试。

`CONFIG_CANFD_RK3576=y` 虽然编进 Linux，但项目计划由 M0 接管 CAN；在确认 Linux 不会访问 CAN0/1 后，再从项目内核配置移除。M0 的 UART5 pinmux、AMP 保留内存、RPMSG 与 UIO 规划必须保留；详见 [现有集成方案](lbc-sdk-integration.md)。

## 2. 驱动与用户空间裁剪

| 功能 | 当前证据 | 建议与边界 |
|---|---|---|
| 显示 | 内核 defconfig 有 `CONFIG_DRM=y`、`CONFIG_DRM_ROCKCHIP=y`；板级 DTS 启用 VOP、HDMI、DP；Buildroot 包含 Weston、Chromium 和大量 GStreamer 插件，目标镜像还会启动 `S49weston`、`S99chromium-wayland.sh`。 | 在项目 DTS 禁用显示控制器、输出、路由与音频关联节点；在项目内核配置移除 DRM/面板等驱动；从项目 Buildroot 配置去掉 GUI/浏览器片段。若相机/NPU/视频编解码仍用于机器人，应保留其独立驱动与用户库，不把整个 multimedia 一次删除。无显示后确认串口和 SSH 可诊断。 |
| 音频 | `CONFIG_SND=y`，DTS 的 ES8388、HDMI/DP sound、SAI1 等启用；Buildroot 包含 ALSA、PulseAudio、BlueALSA，并启动 `S50pulseaudio`。 | 在项目 DTS 禁用声卡、codec、相关 SAI/SPDIF；在内核项目配置关 `CONFIG_SND`；Buildroot 移除 `multimedia/audio.config` 及依赖它的 demo/插件。先查摄像头或应用是否需要音频输入。 |
| 蓝牙 | 内核 `CONFIG_BT=y`，`BT_HCIBTUSB=m`；Buildroot `wifibt/bt.config` 启用 BlueZ、BlueALSA、`rkwifibt-app`，目标镜像启动 `S40bluetoothd`。`rkwifibt-app` 的 Kconfig 还会反向选中 BlueZ/ALSA。 | 去掉 BT 片段与 `rkwifibt-app`，核查 `powermanager.config` 对 BlueZ 的选择；内核关闭 `CONFIG_BT` 及 HCI 驱动；保留 `wifibt/wireless.config` 的 Wi‑Fi 认证能力。是否保留 `rkwifibt` 应看板上 Wi‑Fi 电源/初始化是否由它负责。 |
| Wi‑Fi / miniPCIe | `pcie0` 在 DTS 中启用；内核 `RTW88_8822BE=m` 和 `RTW88_8822CE=m` 均启用；目标镜像有 `rtw8822b_fw.bin`、`rtw8822c_fw.bin`。目前没有板上 PCI ID，因此不知道实际是 BE、CE 或其他变体。 | 保留 PCIe0、`CONFIG_PCI`、`CFG80211`、`MAC80211`、实际匹配的 `RTW88_*E` 和对应 `rtw88` 固件、`wpa_supplicant`/`iw`。上板用 `lspci -nnk`、`readlink /sys/class/net/wlan*/device/driver`、`dmesg` 确认型号和固件，再去掉其余 Wi‑Fi 芯片驱动。蓝牙子功能无需为 Wi‑Fi 保留 BT 协议栈：Realtek 对 RTL8822BE 标明 WLAN 走 PCIe、BT 走 USB 2.0；但组合芯片供电/复位不能随 BT 一起断掉。见 [Realtek RTL8822BE 产品说明](https://www.realtek.com/Product/Index?cate_id=194&id=583&menu_id=357)。 |
| CAN | 内核 `CONFIG_CAN=y`、`CONFIG_CANFD_RK3576=y`，AMP 设计让 M0 接管 CAN。 | Linux 项目配置关闭 SocketCAN 及 RK3576 CANFD 驱动；先核实最终 DTB 的 CAN0/1 处于 disabled、pinmux 不被 Linux 占用，M0 固件自行配置。 |
| USB | 内核启用主机、DRD、gadget、USB 网卡、串口、摄像头等大量功能；DTS 启用 Type‑C DRD0、USB2 OTG1、USB3 host DRD1；目标镜像有 `S50usbdevice.sh`。 | 先盘点实际 USB 设备、调试/刷机方式与 miniPCIe BT 的 USB 接线。若运行态完全不需 USB，可在项目 DTS 逐个禁用控制器/PHY，再去掉内核 USB 主机/设备与 Buildroot USB gadget 脚本；保留 U‑Boot/Maskrom 恢复链路的独立配置。若仅 BT 连在 USB，禁用 BT 驱动/服务即可，无须先关全局 USB。 |
| 板载 RJ45 与外接 RMII | 当前 `rk3576-lubancat-3.dts` 的 `gmac0` 为 `okay`、`gmac1` 为 `disabled`，两者现有定义均为 RGMII；`gmac0` 使用 RTL8211F PHY。内核 `STMMAC_ETH=m`、`DWMAC_ROCKCHIP=m`，还启用了 `R8169=y`。 | 保留 `gmac0`、其 MDIO/PHY、STMMAC/DWMAC 与 eth0 静态地址。`gmac1` 已禁用，项目 DTS 只需确保没有 overlay 重新启用；可裁掉不使用的 PCIe Realtek `R8169`，但先用板上 `ethtool -i eth0` 与 `readlink /sys/class/net/eth0/device/driver` 核实 RJ45 驱动。用户所说外接 RMII 与当前源码的 `gmac1` RGMII 描述有差异，需按实际转接板/最终 DTB 对照，不能凭接口名称删掉 gmac0。 |

Buildroot 配置建议另建 `rockchip_rk3576_zenith_defconfig`，只选所需 `#include`；不要直接在生成的 `.config` 末尾写 `# ... is not set` 试图压过前面的片段。板级 `RK_BUILDROOT_BASE_CFG` 指向新配置。逐步减少 `bt.config`、`audio.config`、`gui/weston.config`、`network/chromium.config` 和无关 demo，再运行 Buildroot `olddefconfig` 检查被 `select` 拉回的包。保留 `lbc-firmware` 中匹配实际 Wi‑Fi 的固件，目标镜像 `/lib/firmware/rtw88/` 与 `/lib/firmware/rtl_bt/` 可分别核对。

## 3. O2 与 LTO：现状及可试范围

| 构建对象 | 已确认状态 | 下一步 |
|---|---|---|
| Buildroot 目标包 | 展开配置 `BR2_OPTIMIZE_2=y`；`package/Makefile.in` 将其映射为 `TARGET_OPTIMIZATION=-O2`。这是默认值。 | 保持；抽查关键应用实际编译命令，单个包可能覆盖优化级别。`BR2_TARGET_OPTIMIZATION` 当前为空，无须重复写 `-O2`。 |
| Buildroot LTO | `BR2_ENABLE_LTO` 当前关闭。该选项的 Kconfig 明确说明只对显式支持它的少数包生效；本树 `rg BR2_ENABLE_LTO buildroot/package` 仅命中少量包。 | 可以做单独试验打开并比较包级命令、镜像大小、性能；不能把它视为整个 rootfs 的全局 LTO。若关键自研应用需要 LTO，在该应用 package 的编译和链接两侧单独加 `-flto`，并确认归档工具/第三方库兼容；先保持 libc、工具链及厂商闭源库原样。 |
| Linux 内核 O2 | `.config` 有 `CONFIG_CC_OPTIMIZE_FOR_PERFORMANCE=y`；内核 `Makefile` 对应 `KBUILD_CFLAGS += -O2`。 | 保持，抽查一次 `make V=1` 或 `.cmd` 文件；不必再叠加 `KCFLAGS=-O2`。 |
| Linux 内核 LTO | 当前 `CONFIG_CC_IS_GCC=y`、`CONFIG_LTO_NONE=y`。本内核 `arch/Kconfig` 只提供 Clang Full/Thin LTO，且依赖 Clang、LLD、LLVM binutils；没有可直接开启的 GCC LTO 选项。 | 若要探索，另建 LLVM/Clang 构建实验并先试 `CONFIG_LTO_CLANG_THIN`，核对 Rockchip 内核补丁、外部模块、模块加载、AMP 启动、固件打包及内存占用；再与同工具链的无 LTO 版本比较。GCC 构建上直接打开 `CONFIG_LTO` 不可行；切换编译器本身是独立变量，不能把结果归因于 LTO。Full LTO 放在 ThinLTO 通过之后。 |

LTO 的目标应是可量化收益（关键路径耗时、镜像大小），而非实时性保证。它也可能改变最坏执行时间和调试符号；需重新测周期任务尾延迟。Buildroot 选项帮助文本还提醒链接期分析会增加构建时间，且收益未必明显。

## 执行顺序与验收

1. 保存当前可启动镜像、展开 `.config`、DTB、固件清单与基线延迟数据。用 `lspci -nnk`/`lsusb -t`/`ethtool -i eth0` 确定 Wi‑Fi、BT、RJ45 的实际总线和驱动，核对最终加载的 DTB；板级启动脚本首次启动会选择 DTB，见集成文档。
2. 新建项目 DTS、内核 defconfig、Buildroot defconfig 和板级 AMP defconfig。第一轮只关显示、音频和蓝牙用户空间；逐轮验证 RJ45、Wi‑Fi、M0 UART/RPMSG、eMMC、SSH、温控与回退入口。
3. 第二轮处理 USB 和其余驱动，依设备清单细化；每次用目标镜像的 `/proc/config.gz`、`/proc/device-tree`、`lsmod`、`/proc/interrupts`、启动服务确认裁剪实际生效。
4. 单独测试 CPU/IRQ/idle 参数，再单独测试 Buildroot LTO、Clang 无 LTO、Clang ThinLTO。每个版本记录构建成功率、镜像大小、启动时间、温度及同一负载下的最大/高分位延迟。只有在功能通过且尾延迟不退化时合入。
5. 按 [SDK 集成流程](lbc-sdk-integration.md) 在子仓库提交并导出补丁；内核 fork 提交并更新 pin。项目配置名称和验证结果补记到本文，避免后续无法复现。

当前仅完成静态源码及现有构建产物调查；未取得板上设备 ID、负载基线或新配置的构建结果。以上涉及实际网卡型号、USB 依赖和延迟收益的结论须按验收步骤确认。

## 第 1 轮实施记录（2026-09-26）

范围：**显示 + 音频 + 蓝牙**。保留 DRM core / GPU(Mali) / NPU / 摄像头(ISP/CIF) / 视频(MPP/RGA) / USB / WiFi / M0(AMP/RPMSG/UART5)。

落点（新增文件与指向）：

- 内核片段 `kernel/arch/arm64/configs/lubancat_rk3576_headless.config`，经板级 `RK_KERNEL_CFG_FRAGMENTS` 应用；基线 `lubancat_linux_rk3576_defconfig` 不改。
  - 关：`SOUND/SND*`、`BT*`、`DRM_ROCKCHIP` 及其 VOP/HDMI/DP/DSI/LVDS/RGB/HDCP2、`DRM_PANEL_SIMPLE`、`RK628_MISC`、HDMI/DP/eDP PHY、`VIDEO_ROCKCHIP_HDMIRX`、`MEDIA_CEC_SUPPORT`、`TYPEC_DP_ALTMODE`、`FB/FRAMEBUFFER_CONSOLE/BACKLIGHT_*`、`RK_HEADSET`。
  - 保留：`DRM`(core，`ROCKCHIP_RKNPU` 的 `DRM_GEM` 依赖它)、`MALI_BIFROST`、`ROCKCHIP_RKNPU`、`VIDEO_ROCKCHIP_CIF/ISP`、`ROCKCHIP_MPP_*`、`RFKILL_RK`、`ROCKCHIP_AMP`、`RPMSG_*`、`CANFD_RK3576`(暂留)。
- DTS `rk3576-lubancat-3-headless.dtsi`，由 `rk3576-lubancat-3-v2-mcu.dts` include。
  - disabled：`display_subsystem/vop/vop_mmu/vdpp/vp0..2`、`hdmi/hdptxphy_hdmi/route_hdmi/hdmi_in_*`、`dp/dp0/route_dp0/dp0_in_*`、`usbdp_phy_dp`、`es8388_sound/hdmi_sound/dp0_sound`、`sai1/sai6/spdif_tx3`、`es8388`。
  - 保留：`usbdp_phy`(USB3 u3 口)、`sai*`(未启用)、M0 `uart5m0_xfer` 与 amp 保留内存。
- Buildroot 新配置 `buildroot/configs/rockchip_rk3576_zenith_defconfig`（`RK_BUILDROOT_BASE_CFG="rk3576_zenith"`）。
  - 去掉 include：`gui/weston`、`network/chromium`、`multimedia/audio`、`multimedia/gst/audio`、`wifibt/bt`、`font/chinese`、`tools/benchmark`(glmark2/whetstone)、`powermanager`(带 BlueZ，改为直接 `PM_UTILS`)。
  - 保留：`base`、`chips`、`fs/*`、`bus/{can,pci}`、`wifibt/wireless`、`multimedia/{camera,mpp,gst/{video,camera,rtsp}}`、`npu2`、`gpu`、`tools/{common,test}`(含 rt-tests/cyclictest)，另加 `LBC_FIRMWARE/RKWIFIBT/PM_UTILS/IPERF/OPENSSH/VIM`。
- 板级 `.chips/rk3576/LubanCat_rk3576_buildroot_amp_mcu_defconfig`：`RK_KERNEL_CFG_FRAGMENTS="lubancat_rk3576_headless.config"`、`RK_BUILDROOT_BASE_CFG="rk3576_zenith"`。

裁剪前基线（`/tmp/opencode/round1-baseline.txt`）：`target/` = 843M；其中 chromium 312M、kernel modules 88M、`libmali.so` 54M、perl5 38M、firmware 22M、gstreamer 8.6M、pulseaudio 3.9M。

板端验收脚本 `tools/lbc-verify-headless.sh`（ssh 后 `sh -s` 执行），核对 config.gz、`/dev/dri`、`/proc/asound`、服务残留，以及 eth0/M0 保留内存/rpmsg/NPU/摄像头节点。

注意：U-Boot 需 `python2`，主机（CachyOS）没有，加载器构建要在 `aura-sdk` distrobox 容器里完成；`build.sh all` 的 loader 钩子会 `rm -f u-boot/*.bin u-boot/*.img`，不要在没有 python2 的主机上跑 `all`。

## 第 2 轮实施记录（2026-09-26）

范围：USB gadget、CAN、WiFi 收窄、无用总线/存储/文件系统/输入/传感器/调试、GPU。板端实测 WiFi 为 **RTL8822CE**（`10ec:c822`，`rtw_8822ce`），BT 是同一组合芯片的 USB 部分（已随 BT 裁掉）。

落点：
- 内核片段 `lubancat_rk3576_headless.config` 追加第 2 轮：`USB_GADGET`、`CAN`、`SCSI`、`ATA`、`BLK_DEV_NVME`、`MD`/`DM`、`MALI*`、`R8168/8169`、`HID`/`USB_HID`、`USB_STORAGE/UAS`、`USB_SERIAL`、`USB_NET_*`、`BTRFS/XFS/NTFS/EXFAT/ISO9660/CIFS/NFS/JFFS2/UBIFS/SQUASHFS/FUSE/EFIVAR/HUGETLB`、`MEDIA_*TV/RADIO/SDR/USB/TUNER`、`INPUT_JOYSTICK/TOUCHSCREEN/KEYBOARD_{ADC,GPIO}/MOUSE_*/ROCKCHIP_REMOTECTL`、`IIO` 外部传感器、`LEDS_IS31FL32XX`、`EBF_*`、电池/充电/TPM、非本板 PMIC/regulator，以及调试项 `PM_DEBUG/SCHEDSTATS/DEBUG_INFO/PRINTK_TIME/DYNAMIC_DEBUG/DEBUG_DEVRES/DEBUG_CREDENTIALS/RK_DMABUF_DEBUG/DMABUF_SYSFS_STATS`。
  - WiFi 只留 `RTW88` + `RTW88_CORE` + `RTW88_PCI` + `RTW88_8822C` + `RTW88_8822CE`；去 `RTW89*`/`RTL_CARDS`/`MT76*`/`B43`/`IWLWIFI`/`WL_ROCKCHIP`/`RTL885xBE`。
  - 保留：摄像头链（`VIDEO_ROCKCHIP_CIF/ISP/ISPP/VPSS/RGA`）、`ROCKCHIP_RKNPU`、`DRM` core、`LEDS_CLASS/GPIO/TIMER/HEARTBEAT`（sys_led）、`INPUT_EVDEV`、`PWM_ROCKCHIP`/`SENSORS_PWM_FAN`/`THERMAL`、`USB_DWC3`(host)/`USB_XHCI_HCD`、`EXT4/VFAT`。
  - 已知残留：`CONFIG_MEDIA_TUNER=y` 被 olddefconfig 保留（无 select/imply，推测 `default y`），影响很小。
- DTS 未变（`usbdp_phy` 仍在；OTG 关 gadget 后 DWC3 退为 host）。
- Buildroot `rockchip_rk3576_zenith_defconfig`：去 `bus/can`、`fs/exfat`、`fs/ntfs`、`gpu/gpu`、`tools/{common,test,benchmark}`，改为显式保留 `IPROUTE2/I2C_TOOLS/IPUTILS/IW/COREUTILS/PROCPS_NG/STRACE/RT_TESTS/STRESS_NG/IPERF`，并覆盖 `ANDROID_ADBD/USBMOUNT/INPUT_EVENT_DAEMON` 为 off；去 `RKWIFIBT`。
- 板级 `.chips/rk3576/LubanCat_rk3576_buildroot_amp_mcu_defconfig` 加 `# RK_USB_GADGET is not set`。
- 固件瘦身 overlay `board/rockchip/common/overlays/40-zenith-slim/prepare.sh`（仅 zenith defconfig 生效）：`/lib/firmware` 只留 `rtw88/rtw8822c_*.bin`，删掉 iwlwifi/intel/rtlwifi/rtl_bt/rtl_nic/aic8800/mt7601u（约省 21M）。

裁剪前（round1）基线：`target/`=343M；大块 = modules 86M、`libmali.so` 54M、firmware 22M、gstreamer 8.2M、`librknnrt.so` 7M。

第 2 轮结果：`target/` 343M→**173M**；`lib/modules` 86M→**5.6M**（251→12 个 .ko）；`lib/firmware` 22M→**344K**；`rootfs.img` 439M→**202M**；`update.img` 573M→**335M**（相对原版 −70%）。期间修正两处遗漏：`mt76` 家族与 `MEDIA_TUNER/DVB` 需显式关闭（`MEDIA_SUPPORT_FILTER=y`）；`usbdevice`/`S50usbdevice.sh` 来自 `rkscript` 包、与 `RK_USB_GADGET` 无关，已在 `40-zenith-slim` overlay 里删除。
