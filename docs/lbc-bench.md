# LubanCat-3 AMP 运行基线 & 变体对比（短测法）

板子无散热片，长负载会降频污染对照。因此统一用 **< 40 秒**的短测：开始前等冷却到最热 zone ≤ 48°C，`cyclictest` 每段 10s（10000×1ms），负载段用 `stress-ng`。

## 方法（`tools/lbc-bench.sh`，板端自包含）

1. env：`uname -r`、`CONFIG_CC_VERSION_TEXT`、`CONFIG_LTO_*`、governor、nproc。
2. `wait_cool`：等到 `max(thermal_zone*) ≤ 48°C`（最多 150s），记录起始温度。
3. phase A 空载：`cyclictest -m -p99 -i1000 -l10000 -t1 -a4 -q`。
4. phase B 负载：`stress-ng --cpu 6` 下，`cyclictest ... -a7`。
5. phase C 吞吐：`stress-ng --cpu 8 --cpu-method matrixprod --timeout 5s --metrics-brief`。
6. phase D 调度：`hackbench -s 100 -l 200 -g 5 -f 10 -P`。
7. after 温度。
- `oslat` 在本镜像不可用（缺 libnuma），暂缺该项；后续可补。

指标：`cyclictest` 的 Min/Avg/**Max**（尾延迟主指标）+ 吞吐 + hackbench + 温升。
注意：基线 Max 已在 **1–3 µs** 量级（接近 `cyclictest` 1ms 间隔下的噪声底），
LTO 若只比较这个 Max，差异可能淹没在 ~1µs 的 run-to-run 抖动里；尺寸/吞吐更能区分。

## 变体

| 变体 | 编译器 | LTO | 状态 |
|---|---|---|---|
| V0 | GCC 10.3.1（SDK 工具链） | 无 | 已测（round2 镜像） |
| V1 | Clang 15.0.7 | 无 | 已编过（兼容性探测），未上板 |
| V2 | Clang 15.0.7 | ThinLTO | 构建中 |
| V3 | Clang 15.0.7 | FullLTO | 待 V2 通过 |

## V0 结果（2026-09-26，round2 镜像，`v0-gcc`）

```
[env] kernel=6.1.99-rt36-rk3576  cc=GCC 10.3.1  lto=CONFIG_LTO_NONE=y  governor=performance
[idle]     Min 0  Avg 0  Max 2 us
[cpuload]  Min 0  Avg 0  Max 2 us        (stress-ng --cpu 6)
[throughput] cpu: 901 bogo ops, 176.24 ops/s real, 5.11s
[hackbench]  Time: 0.070
[th] 47.2C -> 68.4C
```

（重复一次得到 idle Max 1us / cpuload Max 3us，run-to-run 抖动 ~1us。）

## 构建侧记录

| 变体 | Image | vmlinux | 备注 |
|---|---|---|---|
| V0 (GCC) | 18821632 B (18.8M) | — | `DEBUG_INFO_NONE` |
| V1 (Clang, no LTO) | 17730048 B (17.7M) | 24783072 B | 零 error/warning，`AS_IS_LLVM=y` |
| V2 (Clang, ThinLTO) | 18186752 B (18.2M) | 28268512 B | `LTO_CLANG_THIN=y`，`vmlinux.o` 55.9M，构建 1m40s |
| V2b (Clang 16, ThinLTO) | 18188800 B (18.2M) | 28280208 B | clang 16.0.6；1 条 vendor 告警（imx415 uninitialized）；尺寸与 V2 相同 |

观察：**尺寸收益来自换 Clang（Image −5.8%），ThinLTO 反而比 Clang-无LTO 更大（+2.6%，vmlinux +14%）**，对本内核 LTO 没有尺寸收益。是否值得采用要看运行时（吞吐/尾延迟）——需把 Clang 接入 SDK 才能出可刷镜像。

## V2 真机结果（2026-09-26，Clang-15 + ThinLTO，已刷板）

功能门禁：`lbc-verify-headless.sh` **pass=91 fail=0**；LTO 模块正常加载（无 symbol 版本冲突）；AMP/M0、WiFi(rtw_8822ce)、eth0、LED、rpmsg 全在。dmesg 仅原有噪声。

| 指标 | V0 (GCC) | V2 (Clang-15+ThinLTO) | V2b (Clang-16+ThinLTO) |
|---|---|---|---|
| Image | 18,821,632 (18.8M) | 18,186,752 (18.2M) | 18,188,800 (18.2M) |
| `/lib/modules` | 5.6M (12 ko) | 1.8M (12 ko) | 1.8M |
| cyclictest idle Max | 2 µs | 1 µs | 1 µs |
| cyclictest cpuload Max | 2 µs | 4 µs | 3 µs |
| stress-ng throughput | 176.24 ops/s | 176.62 ops/s | 176.00 ops/s |
| hackbench (中位) | 0.070 (n=1) | 0.083 (n=5) | 0.081 (n=5) |
| thermal rise | 47→68°C | 43→62°C | 45→66°C |

**结论**：
- clang-15 与 clang-16 结果几乎重合 → **clang 版本这一维无差异**，没必要为"更新"而升级。
- 尾延迟与吞吐**在噪声底内，无可辨差异**（idle/cpuload Max 在 1–4µs 抖动）。
- **模块体积显著缩小 5.6M→1.8M（−68%）**，是 ThinLTO 唯一的实打实收益；`Image` 仅 −3.4%，`update.img` 基本不变（331MiB）。
- hackbench：两个 Clang 版本一致地落在 **0.080–0.083**，而 V0 单次 **0.070**；看似 ~15% 退化，但 V0 只有 1 个样本，**未定论**（要定论需切回 V0 重测 n≥5）。注意 hackbench 是调度吞吐微基准，与机器人关心的**尾延迟无关**（尾延迟未退化）。
- 总体：Clang+ThinLTO 对本内核**运行中性、镜像级尺寸中性**，只在模块占用上有收益；代价是引入 Clang 工具链依赖。


