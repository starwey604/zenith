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

kernel 不做 patch series，而是 fork `https://github.com/LubanCat/kernel.git`，
把 remote 换成本人仓库，在 `lbc-develop-6.1-rt36`（PREEMPT_RT）基础上长期维护。
构建通过 SDK 根的 `kernel-6.1` 符号链接消费该 fork，因此在 `baseline.toml` 里钉住 commit
以保证可复现。注意厂商 manifest 仍固定较旧的 `95cee116`（`lbc-develop-6.1`），
如需 `repo sync` 完全复现，可加 `.repo/local_manifests/` 覆盖 `kernel-6.1` 的 revision。

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

## 待办（RK3576 方向）

- AMP / RTOS：SDK 缺 `rtos/` BSP 与 rk3576 amp 打包配置（`amp.its`/板级 defconfig/
  `parameters-amp.txt`）。framework（内核 `rk3576-amp.dtsi`+驱动、U-Boot `rk3576-amp.config`）
  已在，需从带 `rtos` 的厂商 SDK 补齐。用户可用小核为 `bus_cm0`（BL31 v1.14 已支持
  `bus_mcu` NS 配置与 AMP OS）。
- FDCAN 移交小核：CAN0/1 位于 `0x2ac00000`/`0x2ac10000`，落在 MCU 非缓存外设窗口内；
  Linux dts 保持 disabled、pin 由 MCU 固件配置。
