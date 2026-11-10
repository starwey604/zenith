# LBC3 普通 reboot 偶发卡住：定位与 LED 修复

## 当前结论（2026-11-10）

RTL8822CE 的 LED 回调会在 Wi-Fi 设备进入 D3hot 后访问 PCIe 寄存器。原版 #23 的同条件对照在第 4 轮卡死：重启进程仍在 `device_shutdown()` 内的 `optee_shutdown()` 延时处，CPU7 的 `ktimers/7` 被 RCU 报告停滞，PC 多次采样落在 `rtw_pci_read32()`。随后保留 Wi-Fi 驱动做插桩，直接抓到 `pci_set_power_state()` 成功返回约 210 ms 后，`ktimers/6` 里的 `rtw8822c_led_set()` 尝试读取 `REG_LED_CFG`（`0x4c`）。本次随后仍正常重启；它证实了关机顺序缺陷，不代表每次迟到读取都会卡死。

修复只在内核 `drivers/net/wireless/realtek/rtw88/pci.c` 的 `rtw_pci_shutdown()` 中调整 LED 生命周期：先禁止 LED sysfs 写入，再注销 LED。LED 核心会解除触发器、同步停止软件闪烁并排空亮度工作；完成后才走原来的芯片 shutdown 和 D3hot 路径。Wi-Fi 驱动未解绑，OP-TEE、PCIe 控制器、USB 和 AMP 均未修改。

使用原版 #23 Image、原 DTB 和同一 M0 固件，临时从 kexec 启动加载修复模块。无插桩的修复模块完成 **5/5** 轮 64 B A72 kexec → 普通 reboot（触发时点约 22–45 秒）；每轮 M0 重连校验通过，Wi-Fi 始终绑定，正常进入 DDR 和 #23。插桩另外验证了默认 `phy0tpt` 和 100 ms 开／关的软件闪烁；后者在进入 LED 清理时确有待执行的定时器，清理返回时触发器、定时器和亮度工作均已清空，随后才进入 D3hot，未再捕获迟到访问。

- [原版失败现场与 LED 清理前后审计](evidence/lbc-reboot-hang/led-shutdown-audit.txt)。临时模块的同条件回归原始记录保留在本机 `out/lbc-reboot-debug/rtw-led-fix-NJoc6h/matched-trials.tsv`。
- 临时模块只在 kexec 测试启动中覆盖模块路径，普通重启即回到原 #23 和原模块。之后另行做了下面的全量刷机回归。

### 全量 eMMC 刷机镜像

修复已发布到内核 fork 的 `lbc-develop-6.1-rt36` 分支（[`93c1409fe`](https://github.com/starwey604/kernel/commit/93c1409fe8813c24371f96528619cb93424eea78)），Zenith 的 `sdk/baseline.toml` 和 `sdk/manifest.lock.xml` 锁定该提交。全量镜像使用与原板一致的内核配置和恢复 DTB，包含新内核 #103、同批构建的模块、`amp-size-curve` 固件和 64 B kexec 测试工具。#103 还包含板测工作区的 RPShm/CAN/UIO 改动；内核锁定值用于取得 LED 修复，单靠它不能重建这份板测镜像。镜像采用 SDK 的干净 Buildroot rootfs，烧录会覆盖板上旧 rootfs。

首版镜像烧录后的第一次启动在进入用户态前出现 CPU4 RCU 停滞，`mmc_rescan` 等待 RCU；一次断电冷启动后恢复，具体原因未定位。另一个独立的打包问题是 rootfs 缺少 `/boot` 挂载点，导致首次启动脚本把 `rk-kernel.dtb` 切回默认 DTB。板上恢复了回归 DTB 链接，并去掉重复的 `/boot` 挂载项；再次冷启动后初始化 M0 会话。此后，确认实际加载的 Wi-Fi 模块与烧录包一致，**5/5** 轮 64 B A72 kexec → 普通 reboot 通过。每轮 M0 重连均为 2500 次读取、零错误，重启后 Wi-Fi 重新绑定，有线网可达。板子留在 #103，M0 为 QUIET。

- [烧录后 5 轮回归记录](evidence/lbc-reboot-hang/flashed-64b-reboot-trials.tsv)、[首启 RCU 停滞现场](evidence/lbc-reboot-hang/first-flash-rcu.txt)。完整串口、调试器输出和逐轮报告保留在本机 `out/lbc-reboot-debug/release-93c1409fe/`。
- 后续烧录使用本机的 [LubanCat-3 v2 全量镜像 r2](../out/lbc-reboot-debug/release-93c1409fe/LubanCat3-v2-LED-fix-93c1409fe-r2-update.img)。r2 增加了 `/boot` 挂载点，并让厂商默认 DTB 文件名也解析到回归 DTB。已解包核对 #103 和 Wi-Fi 模块与板测版本完全相同；r2 封装本身未另行上板，当前板子不必重刷。

## 后续计划：全量刷机后的首次启动 RCU 停滞

**先区分「从下载流程自动复位」和「刷完后第一次启动」。** 已观察到一次：全量 `UF` 默认复位后，#103 在 `Run /init` 前报告 CPU4 expedited RCU stall；断电再启动恢复。当时未记录下载模式是 Loader 还是 Maskrom。CPU4 的栈经过时钟门控和 `rt_spin_unlock`，`mmc_rescan` 工作线程则在等 expedited RCU 宽限期；先把它们当作定位线索，不据此认定时钟或 eMMC 是根因。这发生在用户态加载 Wi-Fi 模块之前，与前面的 LED 关机缺陷分开跟踪。

### 第一轮：同镜像，只改变刷完后的复位方式

先约好可覆盖 eMMC rootfs 的窗口，备份需保留的数据。串口在进下载模式前开始持续录制，同时保存刷机工具输出。固定同一块板、同一份 r2 镜像、同一工具和供电/外设配置；每次用 `upgrade_tool LD` 记录实际下载模式，两组都从同一种模式进入。每轮从干净的刷写开始，不跑 kexec，不改启动参数。

| 组别 | 操作 | 对比目的 |
|---|---|---|
| A：刷完自动复位 | `upgrade_tool UF "$IMAGE"`，刷完后不拔电 | 重走历史失败路径 |
| B：刷完冷启动 | `upgrade_tool UF "$IMAGE" -noreset`，确认刷写成功且板未自动启动，再完整断电至少 5 秒后上电 | 同样是写盘后的首启，但去掉刷完直接复位 |

`-noreset` 已在本机工具帮助中确认；若 B 组仍自动启动、无法确认板子已完全断电（含 USB 反供电），或模式与 A 不同，该轮不纳入比较。先交替跑两对 A/B；若两对结果一致地分开，再补一对确认。每轮记录 `UF` 结果、实际复位方式、DDR/SPL/BL31/U-Boot、内核版本和启动参数。以刷写结束（A）或重新上电（B）起 120 秒为观察窗口：记录 eMMC 是否识别、是否执行 `/init`、串口登录是否可用；将**进入用户态前的同类 CPU4 RCU 停滞**与其它启动失败分别计数。卡住后先取证再请用户断电：串口调试器逐条取 `pcsr`、`sysrq w` 和 `kmsg`，保存原始输出。

### 第二轮：按结果决定是否还需要写盘

- **A 复现、B 不复现：** 优先查下载流程退出时的复位状态。确认该模式有可用的不写盘退出命令后，再做「进同一下载模式 → 不写盘直接退出」对照，另用已安装系统的普通重启作参照。若不写盘也复现，进入/退出下载流程就足以触发；若只有 A 复现，先比较刷写流程与不写盘退出的实际复位路径。
- **A、B 都复现同类停滞：** 自动复位不是必要条件。先比较刷写后的首启与同一镜像第二次启动，再决定是否在启动阶段对时钟门控调用点和 CPU4 的 RT 锁路径加少量标记；用匹配的 #103 符号解栈，保留 MMC 等待栈作对照。
- **只有 B 复现：** 复查 B 的刷写结果和实际断电过程；若确认有效，优先比较冷启动早期日志，而不是继续按「自动复位触发」排查。
- **都不复现或结果不稳定：** 报告各组次数和实际模式，不认定已修复。核对 r2 与历史失败样本的早期启动日志；历史下载模式保留为未知。

## 原始关机问题：目标与观察（#23）

修复 RK3576 LubanCat-3 在普通 `reboot` 时偶发无法重新启动的问题，重点检查 **成功执行 Linux-only kexec 之后，再执行普通 reboot** 的路径。目标是恢复正常设备关闭与硬件重启，不把 SysRq 直接重启或看门狗超时当作修复。

最初保留的失败关机日志结束在 USB/xHCI 拆除消息，SSH 与串口调试入口随后无响应，最终由用户断电恢复。最后一条 USB 消息仅是那次的可见进度；后续复现抓到的关机栈已经越过 USB。

RPShm 数据传输无需随此任务改用缓存映射或弱化屏障。以下保留最初交接时的证据和恢复方法。

## 先读这些证据

仓库内的稳定副本：

- [失败关机日志全文](evidence/lbc-reboot-hang/shutdown-after-kexec.txt)：来自 `rpshm/out/size-curve/serial-normal.log`，只规范化串口换行，未删除日志行。
- [失败前后与后续恢复记录](evidence/lbc-reboot-hang/context.json)：摘自 RPShm 的成本曲线、独立样例报告；关联 rpshm 提交 `f965f3c`。

本机保留的完整材料：

| 内容 | 位置 |
|---|---|
| 失败前成功的 kexec 串口 | `/home/ww/codings/rpshm/out/size-curve/serial-kexec.log` |
| 失败的普通 reboot 串口 | `/home/ww/codings/rpshm/out/size-curve/serial-normal.log` |
| 64 B Linux-only 测试结果 | `/home/ww/codings/rpshm/out/size-curve/board/size-kexec-64-1/` |
| 本轮独立样例 kexec 与直接重启串口 | `/home/ww/codings/rpshm/out/standalone/serial-kexec.log` |
| 独立样例 Linux-only 结果 | `/home/ww/codings/rpshm/out/standalone/board/kexec/` |
| 已实现的 kexec、看门狗、M0 复位工具 | `/home/ww/codings/rpshm/tests/rk3576/` |
| 最新独立样例验收说明 | `/home/ww/codings/rpshm/docs/standalone-results.md` |

`out/` 不纳入 Git；跨机器接手时需要另取上述完整采集。关机定位、修复和烧录回归的仓库内证据见本文开头。

## 已观察到的顺序

### 成本曲线轮次：失败

1. 同一 #23 内核完成 32/64/128 B 性能测试和 32 B 故障注入，包括 M0 核心单独复位。
2. 64 B Linux-only kexec 成功。新 Linux boot ID 改变，M0 boot 保持不变，重新握手前序号继续增长；重连校验通过。
3. 为恢复原逻辑 CPU 编号，执行普通 `reboot`。
4. 日志显示用户态服务停止、文件系统处理完成，随后进入设备关闭消息；最后停在：

   ```text
   rkisp_hw 27c00000.isp: rkisp_hw_shutdown
   xhci-hcd xhci-hcd.0.auto: remove, state 4
   usb usb2: USB disconnect, device number 1
   xhci-hcd xhci-hcd.0.auto: USB bus 2 deregistered
   xhci-hcd xhci-hcd.0.auto: remove, state 1
   usb usb1: USB disconnect, device number 1
   usb 1-1: USB disconnect, device number 2
   usb 1-1.5: USB disconnect, device number 3
   xhci-hcd xhci-hcd.0.auto: USB bus 1 deregistered
   ```

   没有后续 `Restarting system` 或新 DDR/U-Boot 启动日志。
5. 网口和串口调试交互均未恢复。此前尝试过串口 BREAK，以及 Rockchip FIQ 调试器触发串 `fiq`，无响应；没有成功进入调试器执行复位。
6. 用户断电重启后恢复，原 128 B、500/250 Hz 入口通过。

没有重复次数足够的故障概率统计，也没有证明 kexec 是必需条件。表中的完整前史用于保留条件，不要求每次复现先跑完性能矩阵。

### 独立样例轮次：有区别的成功路径

- 从冷启动后的系统切换测试固件，普通 reboot 成功。
- 新独立固件的 Linux-only kexec 也成功。
- 最后停止发布、恢复旧 AMP 分区、同步存储，使用 `echo b > /proc/sysrq-trigger` 直接重启，成功恢复原 CPU 编号及旧固件。
- 该直接重启绕开正常关机流程，只提供“另一条复位路径能工作”的证据，不能据此认定是某个 USB 驱动出错。

此外，之前出现过运行中 RCU 卡死和 CAN/PL330 panic，它们不是这份关机日志里的已定位原因。CAN/PL330 已有修复，见 `runtime/AMP_CAN_STATUS_20261109.md`；不要混用旧 #20 故障内核来验证当前 reboot 问题。

## 原始交接时的板子与源码

2026-11-10 首次接手关机故障时，经 SSH 只读核对（刷机后的状态见本文开头）：

- 板子：LubanCat-3 v2，RK3576；Linux `6.1.99-rt36-rk3576-amp1 #23`，PREEMPT_RT。
- `/boot/Image` → `Image-rpshm-recovery`。
- `/boot/rk-kernel.dtb` → `dtb/rk3576-lubancat-3-rpshm-recovery.dtb`。
- Linux boot ID：`51db67c6-54df-426b-aa2a-2c1f4a81c4f5`。
- CPU4 MIDR：`0x00000000411fd080`，Cortex-A72；`/sys/kernel/reboot/cpu` 为 `0`。
- RPShm peer：boot=2、request=13、ack=0、QUIET、seq=1009。ack=0 是恢复旧固件后尚未走新会话握手的状态；此前已通过旧入口完成测试并停止。
- 当前 AMP 固件为旧的 `amp-size-curve.img`，支持 `curve-run64` 与原 128 B 入口。**当前不是独立样例固件**，不要用 `/root/rpshm/standalone-1/receiver` 操作它。
- SSH：`root@192.168.77.2`。凭据走现有授权方式，文档不保存密码。
- Linux 调试串口：`/dev/ttyACM0`，1500000 baud、8N1、无流控；打开前检查是否被 minicom 或其他日志进程占用。

源码：

- 内核：`/home/ww/codings/lbc_kernel`。
- SDK：`/home/ww/codings/lbc_sdk`，M0 BSP 在 `rtos/bsp/rockchip/rk3576-mcu`。
- RPShm：`/home/ww/codings/rpshm`；恢复/研究/独立样例代码已提交为 `f965f3c`。
- Zenith：`/home/ww/codings/zenith`，含其他进行中的机械臂及 runtime 修改。

**内核、SDK 和 Zenith 工作区均有其他修改。**先读取各自 `git status/diff`，不要 reset/clean 或把其他人的修改混进修复提交。内核运行镜像 #23 不等于当前源码任意一次默认构建的产物；记录此次构建的配置与有效 Image/DTB，不仅记录 `uname -r`。

## 推荐定位顺序

### 1. 先定位在哪个阶段等住

从已有稳定内核做小范围诊断补丁，不先禁用整个 USB/PM 子系统。

当前源码路径：

```text
kernel/reboot.c
  kernel_restart_prepare → device_shutdown
  kernel_restart → do_kernel_restart_prepare
                 → migrate_to_reboot_cpu → syscore_shutdown → machine_restart

drivers/base/core.c
  device_shutdown

arch/arm64/kernel/process.c
  machine_shutdown（kexec 非启动核关闭）
  machine_restart（最终硬件重启入口）
```

建议首先在 `kernel_restart` 的阶段前后加有限的串口可见标记；在 `device_shutdown` 针对设备标识、父设备锁、设备锁、`pm_runtime_barrier`、shutdown 回调分别标记进入/返回。原有 `initcall_debug` 只在回调之前打印，无法区分“等待锁/PM”与“回调未返回”，也没有统一的返回标记。

以最后一对未闭合标记确定下一处观测点。如果设备阶段已经完成，继续检查 CPU 迁移、syscore 和 restart handler，不继续追 USB。

如果定位落在 USB 再查有效绑定关系：

- `drivers/usb/host/xhci-plat.c` 的平台 shutdown 入口。
- `drivers/usb/core/hcd.c` 的 `usb_hcd_platform_shutdown`。
- `drivers/usb/host/xhci.c` 的 `xhci_shutdown`。
- `drivers/usb/dwc3/` 下实际绑定的 glue/core 驱动，结合当前 DT/sysfs 决定；不要仅按文件名假定使用 `dwc3-of-simple`。

### 2. 再区分 kexec 前史和普通启动

保持相同 Image、DTB、M0 固件和外设连接，先做两个小组：

1. 冷启动 → 普通 reboot。
2. 冷启动 → A72 发起 Linux-only kexec → 验证新 Linux 正常 → 普通 reboot。

每次记录 Linux boot ID、所有在线 CPU 的 MIDR/逻辑编号、`/sys/kernel/reboot/cpu`、USB 拓扑和驱动绑定、M0 状态、最后关机标记。只在定位证据指向某个设备后，再做设备连接或驱动绑定的单变量比较。

kexec 必须按已有脚本选择在线 A72。默认 A53 发起曾卡在新内核读取 BIGCORE CRU，这是另一条已知限制。kexec 后逻辑 CPU 会重排，不能把旧的 CPU4 含义直接带入新系统。

### 3. 修复真实等待或生命周期问题

依据卡点检查锁顺序、运行时电源、工作队列/中断排空、父子设备关闭顺序或 CPU/复位路由。不要以删 shutdown 回调、无条件跳过同步、增加固定延时，或让普通 reboot 自动改走 SysRq 来宣称修复；若需要平台特定行为，说明为何满足设备和复位约束。

## 复现入口与恢复约束

普通 reboot 的故障复现会切断 SSH。先启动**独立于 SSH 会话存活**的串口采集，验证日志确实持续写入；原始输出保存在新的测试目录，不覆盖现有证据。

当前固件可以直接复用：

```sh
# 板端；DIR 每次选择新的绝对路径。
DIR=/root/rpshm/reboot-debug-01
RPSHM_RECOVERY_BENCH=/root/rpshm/curve-run64 \
    /root/rpshm/kexec-test reboot "$DIR"

# 新 Linux 起来后立即执行，解除脚本已启动的硬件看门狗并采集状态。
DIR=/root/rpshm/reboot-debug-01  # 新 shell 重新设置为同一个结果目录
# 若只是网口没有地址，在串口执行：
ip addr replace 192.168.77.2/24 dev eth0
RPSHM_RECOVERY_BENCH=/root/rpshm/curve-run64 \
    /root/rpshm/kexec-test verify "$DIR"
```

`kexec-test` 源码在 rpshm 仓库，加载当前 `/boot/Image` 和运行 DT。它请求 60 秒看门狗，本板实际约 89 秒；verify 必须及时执行。成功后再捕获当前状态并测试普通 reboot，不在这里重新刷 AMP 固件。

注意：该 kexec 看门狗在 verify 时已解除，**不会继续保护后面的普通 reboot**。如需保护下一次重启，必须另行启用，并核实关机过程中 watchdog 驱动是否会停表；先前 kexec 的看门狗成功不证明它能覆盖任意设备关闭死锁。

恢复顺序：

1. 若 Linux 仍有串口 shell，仅缺网络，先恢复 eth0 地址。
2. 若调试器可进入，先取栈再决定复位；Rockchip FIQ 触发串和命令以当前内核实现为准，不把 BREAK 等同于一定可用的 FIQ。相关源码在 `drivers/soc/rockchip/fiq_debugger/`。
3. 需要直接重启且 shell 仍可用时，先停止测试和存储写入、`sync`，再使用经授权的应急路径。SysRq `b` 本身不负责同步或正常卸载文件系统。
4. 看门狗/串口均无法恢复时停止板端工作，保留日志与最后部署信息，等待用户断电；不要反复写启动分区或盲目发送复位命令。用户已明确允许这种情况下停下来。

本次仅恢复了旧 AMP 固件，没有替换 #23 内核。原 `/root/rpshm/recovery-test/restore.sh` 会退回更早的抽离内核/DT，**不是当前 #23 的精确回滚**。部署新内核前保留当前 `/boot/Image`、DTB 的目标及可独立执行的回滚入口，匹配模块；不默认需要重刷 U-Boot。

## 修复验收与交付

- 给出卡点证据、根因解释、最小补丁和对应源码位置；失败样本与成功样本都保存。
- 建议先各验证 5 次冷启动路径与 kexec 后普通 reboot 路径。普通 reboot 须在约定观察期限内出现新启动日志、恢复 SSH，不能由看门狗或人工断电代替成功。
- 若仍偶发失败，报告次数与条件并继续针对证据收敛；不要把少量未复现写成确定修复。
- 修复涉及的 USB、网络、PM 功能须在启动后验证；保留 AMP 内存/时钟所有权。
- 运行原 128 B、M0 500 Hz / Linux 250 Hz 兼容入口及一次 64 B、1000/500 Hz 正确性测试。若修改改变了 IRQ/调度/时钟路径，再做匹配的性能回归。
- 最终交付 Zenith 问题文档更新、内核修复提交或补丁、有效 Image/DTB/模块路径、结果和回滚方法。把板子留在停止发布、串口释放、SSH 可用的状态。
