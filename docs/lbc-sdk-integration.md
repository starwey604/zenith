# LubanCat RK3576 SDK 集成方案

zenith 的机器人主控是 LubanCat 3（Rockchip RK3576）。厂商 SDK（`~/codings/lbc_sdk`，
Android `repo` 管理，非单一 git 仓库）不直接 fork，而是以 **补丁栈** 维护本项目对它的改动。
机制与 `luckfox-aura-teleop/sdk/` 一致。

## 目录

```text
zenith/
├── sdk/
│   ├── baseline.toml      # release/容器/版本 + 各 project 基线 commit
│   ├── manifest.lock.xml  # repo manifest -r 快照
│   ├── series.tsv         # repo-path|baseline-commit|lbc-branch（权威顺序）
│   └── patches/<repo-path>/
└── tools/lbc-sdk          # check|status|apply|export
```

## 为什么用跨子仓库补丁栈

SDK 由 `repo` 管理，改动会散布在多个独立 git 仓库（`buildroot`、`device/rockchip`、
`kernel-6.1`、`u-boot`…）。SDK 根目录一次 `git diff` 覆盖不到这些嵌套仓库，而给整套 SDK
建巨型 fork 会丢掉 manifest 对版本的管理。因此：保存 pinned manifest 与各项目基线 commit，
在 SDK 子仓库里用 `lbc/*` 分支提交，再用 `tools/lbc-sdk export` 导出补丁。

## 基线（见 baseline.toml）

| 项目 | 基线 commit | 说明 |
|---|---|---|
| buildroot | `4c038732` | Rockchip buildroot fork，`BR2_VERSION 2024.02`（rkr5） |
| device/rockchip | `1f1392c6` | 板级配置与构建脚本 |
| u-boot | `ce67cf02` | 暂未改；AMP 相关改动将落这里 |
| kernel-6.1 | `3d027a80` | **个人 fork 维护，不进补丁栈** |

## 内核策略

kernel 不做 patch series，而是维护个人 fork：

- fork（source of truth）：`https://github.com/starwey604/kernel`（remote `origin`）
- 厂商上游（用于日后合并）：`https://github.com/LubanCat/kernel.git`（remote `upstream`）
- 分支：`lbc-develop-6.1-rt36`（PREEMPT_RT）

构建通过 SDK 根的 `kernel-6.1` 符号链接消费该 fork，因此在 `baseline.toml` 里钉住 commit
以保证可复现。注意厂商 manifest 仍固定较旧的 `95cee116`（`lbc-develop-6.1`），
如需 `repo sync` 完全复现，可加 `.repo/local_manifests/` 覆盖 `kernel-6.1` 的 revision。
`.version` 是 kbuild 生成的被跟踪文件，构建后变脏属正常，`git checkout -- .version` 即可还原。

## 当前补丁栈

- `patches/buildroot/` — 5 个 `rockchip_rk35xx_lubancat_defconfig`：把残缺的 LZU 镜像源
  （缺 `gcc-12.4.0` 等）改回 `sources.buildroot.net`，并把会被 wget UA 拦截（403）的 USTC
  GNU 镜像换成 TUNA。
- `patches/device/rockchip/` — `mk-updateimg.sh`：extboot 打包时用 `debugfs` 写
  `/etc/build-release`，不再依赖容器内不可用的 loop `mount`。

## 使用

```sh
# 从干净 SDK 基线应用补丁（在 SDK 子仓库里以 lbc/* 分支开发）
./tools/lbc-sdk check  ~/codings/lbc_sdk
./tools/lbc-sdk status ~/codings/lbc_sdk
./tools/lbc-sdk apply  ~/codings/lbc_sdk
./tools/lbc-sdk export ~/codings/lbc_sdk   # 从 lbc/* 分支重新导出
```

`check`/`apply` 会拒绝脏工作树或 HEAD 不在基线的情况，绝不执行 `reset`/`clean`。

## AMP：Linux + Cortex-M0 (bus_mcu) RT-Thread（已实现骨架）

- 依赖仓库（个人 fork，Rockchip 未公开）：
  - `https://github.com/starwey604/rk3576-rtos` @ `8541f7a`（RT-Thread 4.1.1 + `bsp/rockchip`，含 `rk3576-mcu`）
  - `https://github.com/starwey604/rk3576-hal`  @ `277de3f`（RK HAL，被 rtos 的 symlink 依赖）
  - 通过 `sdk/local_manifests/01-amp.xml` 挂到 SDK 的 `rtos/`、`hal/`。
- 板级（`device/rockchip` patch）：
  - `parameter-amp.txt`：extboot 布局 + **8 MiB `amp` 分区**（`0x4000` 扇区）。
  - `package-file-amp`：打包 `amp.img`。
  - `amp_mcu_rtt.its`：Linux + M0 RT-Thread 的 FIT 描述（bus_mcu，`load=0x60000000`，`rpmsg_base=0x47d00000`）。
  - `LubanCat_rk3576_buildroot_amp_mcu_defconfig`：`RK_AMP=y` + `rk3576-mcu` + `rk-amp` u-boot fragment。
  - AMP 框架脚本同步为较新的 Forlinx/Rockchip 版（`RTT_EXEC`、`CROSS_COMPILE`、riscv/hpmcu）。
- 内核（kernel fork，`e93d23c5a`）：
  - `rk3576-amp.dtsi` 保留内存对齐 M0 BSP：`mcu@60000000`、`amp-shmem@47900000`(4MiB，页对齐，预留 UIO mmap)、`rpmsg@47d00000`、`rpmsg-dma@47f00000`。
  - 新增 `rk3576-lubancat-3-mcu.dts`（含 `rk3576-amp.dtsi`）。
  - 工具链：M0 使用公版 `arm-none-eabi`；`mk-amp.sh` 在 SDK 无预置裸机工具链时回退到主机 `arm-none-eabi-`（容器内 `apt install gcc-arm-none-eabi`，Ubuntu 22.04 为 10.3.1）。

> **需板上核对/待办**：
> - M0 控制台 UART5 已定为 **M0 mux（GPIO3_D4=RX / GPIO3_D5=TX，40pin pin16/18）**：内核 `rk3576-amp.dtsi` 用 `uart5m0_xfer`，M0 BSP 用 `uart5_m0_iomux_config()`（默认的 M1=GPIO4_B0/B1 不在 40pin，M2=GPIO2_A4/A5 与 SDMMC0 冲突）。
> - `RK_UBOOT_CFG` 默认 `rk3576`，确认 LubanCat 板实际使用的 u-boot defconfig。
> - 后续 UIO 共享消息：`amp-shmem@47900000`（4 MiB）已按页对齐预留，可绑定 UIO 驱动或经 `/dev/mem` 映射；RPMSG vring 在 `0x47d00000`。

## FDCAN 移交小核（待办）

CAN0/1 位于 `0x2ac00000`/`0x2ac10000`，落在 MCU 非缓存外设窗口 `0x20000000–0x48200000` 内；
Linux dts 保持 disabled、pin 由 MCU 固件配置。
