# LBC3 普通 reboot 偶发卡住：修复交接

## 目标与当前判断

修复 RK3576 LubanCat-3 在普通 `reboot` 时偶发无法重新启动的问题，重点检查 **成功执行 Linux-only kexec 之后，再执行普通 reboot** 的路径。目标是恢复正常设备关闭与硬件重启，不把 SysRq 直接重启或看门狗超时当作修复。

目前有一份完整保留的失败关机日志：日志结束在 USB/xHCI 拆除消息，SSH 与串口调试入口随后无响应，最终由用户断电恢复。最后一条 USB 消息只能确定最后可见进度，**尚未证明卡在 USB 回调内**；后续无日志的设备、设备锁、runtime PM，以及更后面的重启阶段都需要定位标记区分。

本任务由后续修复 agent 负责内核定位、最小修复和板端验证。RPShm 数据传输无需随此任务改用缓存映射或弱化屏障。本文整理时仅做了只读状态核对，没有再次触发故障。

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

`out/` 不纳入 Git；跨机器接手时需要另取上述完整采集。两个仓库内的证据文件足以先理解失败和决定初始定位点。

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

## 接手时的板子与源码

2026-11-10 整理本文时，经 SSH 只读核对：

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
