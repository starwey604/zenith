# 用受会话保护的接收端读取 M0 状态

`amp-state-receiver` 是新的生命周期接收入口：M0 1000 Hz 发布 128 字节记录，Linux 500 Hz 读取 LATEST 并消费 FIFO。它通过 RPShm `receiver.h` 统一检查连接状态、复制后的启动代次，以及重连时的 FIFO 本地游标绑定。

原 `amp-shm-bench` 的 500/250 Hz、旧 STOP/RUN、模拟模式和统计口径保持不变。新入口需要带生命周期扩展的固件，不给旧入口增加这个前提。

## 构建与运行

沿用现有入口：

```sh
./tools/runtime-build native
./tools/runtime-build lbc3
# 板端，确认没有其他 UIO 消费者：
amp-state-receiver --cpu 4 --seconds 5
```

生命周期区须先按现有平台流程显式供应；例如冷启动后 host 区为全 1 时，先用匹配的原恢复工具核对第一代 QUIET/未确认状态再初始化。程序不会在请求耗尽或超时后自动清零。普通应用崩溃重启不重复供应。

程序需要 CPU 亲和性及 SCHED_FIFO 权限。默认按 `AmpUio` 的现有方式发现设备，也接受 `--device /dev/uioN`。使用已部署的 `amp-size-curve` 生命周期固件即可，**不要搭配独立样例的 64 字节固件**。

当前宿主机默认 Clang 已更新为 23，而交叉运行库锁定为 22.1.8。已有可用的 22.1.8 工具链位于本机 `out/runtime/amp-shm/toolchain22/usr/`；通过 PATH 和 LD_LIBRARY_PATH 选择其 bin/lib 后运行同一 `runtime-build lbc3`。无需改动版本检查或 LLVM 源码锁。

## 应用如何接入

`runtime/libs/amp_shm/include/amp_receiver.h` 是 Zenith 记录/布局的适配层。调用者先保持 `AmpUio` 的独占映射，再零初始化一个 `amp_receiver`，调用 `amp_receiver_init`；映射必须活到接收端停止且不再使用之后。

该层绑定已有 peer 偏移 48000、host 偏移 512 的生命周期区；QUIET 下清除偏移 576 的旧实验配置 magic，让当前固件采用默认完整 128 字节发布。它不协商新布局、不清活跃共享槽，不改变已有共享字段。

实际接收循环在 `runtime/apps/amp-state-receiver/main.cpp`：

1. begin/poll 到 CONNECTED。
2. 通过 `rpshm_receiver_latest/pop` 取样。
3. 仅 `RPSHM_RECEIVE_OK` 的输出可以继续做业务校验和交付。
4. `RESTART` 时丢弃临时输出，在总期限内重新连接；无需手工重绑 FIFO。
5. 退出时 stop/poll 到 STOPPED；超时则报告失败，不伪装成 M0 已停止。

所有接收端操作由一个 I/O 所有者串行执行。业务线程使用本地数据副本，不直接操作端点。带本地交付与线程退出的例子在兄弟仓库 `rpshm/examples/amp/owner.cpp`，公共 API 说明在 `rpshm/docs/receiver.md`。

## 输出与验收范围

输出包括最新读取数、已消费 FIFO 数、内容错误、重连和丢弃次数、错过期限、读取加 boot 检查耗时，以及进程 CPU 时间。正常运行固定 2 ms 读取周期；错过期限时跳过过期周期而非实时追赶。

这是状态接收程序，不是原 benchmark 的字段兼容替代品。退出时停止发布但不为统计额外排空残留 FIFO，因此输出的 FIFO 数仅表示运行期间实际消费量，不宣称等于最终发布量。跨会话未消费 FIFO 按原恢复契约丢弃。

本机适配测试检查固件标记/范围、QUIET 配置处理、完整记录读取和对端复位后的拒绝交付。

## #103 板端验收已通过

2026-11-11，正常 5 秒运行完成 2500 次 LATEST 读取，内容错误为零；应用被 SIGKILL 后重新启动成功；运行中 M0 硬复位后重连 1 次、丢弃旧会话输出 1 次，继续读取且零错误。不匹配的独立样例固件被拒绝。

RPShm 的同一接收层另通过八处崩溃注入、三次复制中途 M0 复位、Linux-only kexec、读者租约及停顿测试。64 字节 1000/500 Hz 配对比较中，LATEST＋boot 均值为原显式检查 689 ns、新封装 682 ns；FIFO 空读因增加 boot 检查从 173 ns 到 285 ns，测试进程 CPU 从 0.2858% 到 0.2951%。这些性能数字属于独立 64 字节样例，不是本程序 128 字节记录的耗时。

最终已恢复原固件和 CPU 编号，旧 `amp-shm-bench` 500/250 Hz 入口完成 500 次读取、1009 条发布/消费，零错误、丢弃和漏周期。完整条件、统计口径和原始结果见兄弟仓库 `rpshm/docs/receiver-results.md` 与 `receiver-results.json`；本机采集在 `rpshm/out/receiver/board/`。

提交整理时从 Git 暂存区单独导出源码，以现有 native preset 构建并显式启用 `RPSHM_BUILD_TESTS`，16 项 CTest 全部通过。此快照包含原共享内存基准及必要适配，不依赖尚未提交的 CAN 实验或几何研究文件。
