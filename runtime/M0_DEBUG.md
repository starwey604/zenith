# 从 SSH 运行 M0 测试

在宿主机上运行：

```sh
ssh root@192.168.77.2 'm0ctl run version'
ssh root@192.168.77.2 'm0ctl run help'
ssh root@192.168.77.2 'm0ctl logs'
```

`run` 在 M0 工作线程执行一行 RT-Thread MSH 命令。Linux 把执行期间的控制台文本写到 stdout，把 MSH 原始返回值写到 stderr。返回值 0 表示成功；1–255 原样作为 Linux 退出码，其他非零值映射到 1。因此脚本可以直接用 SSH 的退出码判断结果。它执行的是 M0 命令，不是板端 Linux shell。命令行最多 79 字节；需要 MSH 引号时把整行作为一个参数传给 `m0ctl run`。

`logs` 输出本次 M0 启动以来最近的 8 KiB `rt_kprintf` 文本，`logs -f` 接着跟随。窗口满后保留最新字节并报告覆盖量。日志钩子在 RT-Thread 板级初始化时安装，不截获直接写 UART 寄存器的输出。UART5 保留原输出。SSH 断开不会停 M0；`run` 默认等待 30 秒，可用 `m0ctl run --timeout 120 命令` 延长。超时只停止等待，不取消或重发命令；前一个命令结束前不能提交下一个。

UIO 只允许一个打开者。运行命令时不必另开日志窗口，`run` 自带实时输出。先退出 `logs -f` 再运行命令、共享内存基准或部署；读日志本身不会启动测试或切换 CAN 所有权。

## 顶板 ICM-45686：先识别，再读六轴

```sh
ssh root@192.168.77.2 'm0ctl run icm45686 id'
ssh root@192.168.77.2 'm0ctl run icm45686 read'
```

U5 经 40-pin 的 19（MOSI）、21（MISO）、23（SCLK）、24（CS0）接到 M0 的 `spi1_0`，22 是 INT1；本命令不用中断。驱动在执行命令时配置四线 SPI、Mode 0，请求 1 MHz，然后读 `WHO_AM_I`（0x72），期望 0xE9。只有识别成功才允许六轴采样。`read` 在传感器空闲时临时配置 ±4 g、±500 °/s、100 Hz，读五组芯片坐标系的 mg 和毫度/秒，之后恢复原配置。[TDK 数据手册](https://invensense.tdk.com/wp-content/uploads/documentation/DS-000577_ICM-45686.pdf)。

2026-11-19 后续板测：`id` 与 `read` 均读到 0xE9。`read` 成功返回五组六轴数据，Z 轴加速度为 1013–1015 mg，各轴角速度绝对值不超过 350 毫度/秒。

实时姿态和 60 秒延迟复测见 [ICM-45686 姿态](IMU_POSE.md)。

## 新增一条 M0 测试命令

在 SDK 的 `rtos/bsp/rockchip/rk3576-mcu/applications/` 下新建 C 文件。例如：

```c
#include <rtthread.h>
#include <finsh.h>

static int top_smoke(int argc, char **argv)
{
    (void)argc;
    (void)argv;
    rt_kprintf("top_smoke: entered on M0\n");
    return 0;
}
MSH_CMD_EXPORT(top_smoke, top board smoke test);
```

该目录的 C 文件由默认应用自动编入固件。测试使用 `rt_kprintf` 写结果并返回状态；第一次先用无外设副作用的测试打通入口，再加入对应的板级操作。

## 更新固件

在 Zenith 仓库执行 `tools/lbc-m0-deploy`。它构建默认 M0 应用和 Linux 工具，用 SDK 的 `output/amp.its` 打包，检查 `bus_mcu` 加载地址，保存当前 AMP 分区到主机和板端，写后读回比对，并安装 `/usr/bin/m0ctl` 和 `/root/imu-pose-bench`。正常重启后，它等待新的 Linux boot ID，再执行 `m0ctl run version`。新增命令现在可用：`ssh root@192.168.77.2 'm0ctl run top_smoke'`。只构建不部署用 `tools/lbc-m0-deploy --build-only`。

此入口针对现有 LBC3 v2、#103 recovery DT、SDK 默认共享内存应用、已配置的 aura-sdk 容器和 LBC3 工具链；固件与单独的 64 字节样例不能混用。默认板端是 `root@192.168.77.2`。运行前结束其他测试并释放 UIO。部署会**重启整板**；只改测试参数或重复执行已编入的测试不用重启。

## 回退

每次部署打印成对的备份位置：宿主机 `out/runtime/m0-debug/<部署编号>/amp-before.img`，板端 `/root/m0-debug/<部署编号>/amp-before.img`。Linux 仍可登录时，停止测试后，在板端进入对应的备份目录，核对路径再执行：

```sh
(
  set -e
  p=/dev/disk/by-partlabel/amp
  test "$(readlink -f "$p")" = /dev/mmcblk0p3
  test "$(wc -c < amp-before.img)" -eq 8388608
  dd if=amp-before.img of="$p" bs=1M
  sync
  cmp -n 8388608 amp-before.img "$p"
  reboot
)
```

若 Linux 不能启动，让板子进入 LBC3 下载模式，用宿主机备份恢复 **amp** 分区。若恢复的固件不含 M0 控制台，`m0ctl` 也将不可用。

## 共享区布局

`m0_debug.h` 是 Linux/M0 共用的布局，SDK 编译时直接包含 Zenith 的头文件。map0 偏移 48896 为 M0 只读状态（从 Linux 视角）；map1 偏移 4096 为 Linux 命令槽；map1 最后 8192 字节为日志，物理上可写，但唯一写者是 M0。原状态、FIFO、CAN 和实验控制区不变。写日志时 M0 短暂屏蔽本核中断来串行化多来源输出，Linux 只交付发布代次一致的副本。Linux 不在线也不影响 M0 继续运行。启动时确认保留的旧请求而不执行它，后续命令携带本次 M0 boot。
