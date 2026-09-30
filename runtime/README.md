# Zenith 板端运行程序

这里管理 Linux 板端程序、交叉编译配置和第三方依赖配方。首轮只有
`zenith-control` 最小程序：输出版本和平台，检查 C++20 线程、单调时钟与
Linux 系统信息。它还没有控制循环、设备访问或启动服务。

## 构建

宿主机需要 Linux x86_64、CMake ≥ 3.22、Ninja、GNU tar、sha256sum，以及
Clang/LLVM/LLD 22.1.8、libc++、libc++abi。SDK 重定位脚本还需要 `file`、`grep`、`sed`、
`readlink`。当前开发机已具备这些工具，交叉编译器可直接运行。

从 zenith 根目录运行：

```bash
git lfs pull --include='runtime/toolchains/lbc3/sdk.tar.gz,runtime/third_party/sources/*.tar.xz'
./tools/runtime-build native
./tools/runtime-build lbc3
```

脚本可以从其他工作目录调用。默认并发为 2，可用 `--jobs 4` 修改。
两个目标均使用 Clang、LLD、C++20、O3、调试符号和 ThinLTO，静态库工具为
`llvm-ar`/`llvm-ranlib`。本机使用 `-march=native -mtune=native` 和 pacman
安装的 libc++；LBC3 使用 `-march=armv8-a -mtune=cortex-a72`，从固定版本源码
交叉构建 libc++、libc++abi、libunwind 和静态 libomp。目标 C++ 运行库静态
链接进应用，glibc 保持动态链接。Buildroot 快照提供 glibc、sysroot、GCC
支持文件与启动文件；应用的编译和链接由 Clang/LLD 完成。

本机构建自动运行 CTest；交叉产物不会在宿主机执行。ThinLTO 在编译和链接
阶段都启用，链接后端并发限制为 2，独立于 `--jobs` 控制的 Ninja 并发。
没有全局启用 `-ffast-math` 或额外浮点收缩选项；Boost 接入时再按 Willow
的构建配方配置 `-ffp-contract=fast`。

| 内容 | 仓库内路径 |
| --- | --- |
| 本机构建 | `out/runtime/native/build-llvm/` |
| 本机安装树 | `out/runtime/native/install/usr/bin/zenith-control` |
| LBC3 构建 | `out/runtime/lbc3/build-llvm/` |
| LBC3 安装树 | `out/runtime/lbc3/install/usr/bin/zenith-control` |
| 解压工具链与 sysroot | `out/runtime/toolchains/lbc3/<SHA256>/sdk/` |
| 受 Git LFS 管理的 SDK 快照 | `runtime/toolchains/lbc3/sdk.tar.gz` |
| 受 Git LFS 管理的 LLVM 源码 | `runtime/third_party/sources/llvm-project-22.1.8.src.tar.xz` |
| 目标 LLVM 运行库 | `out/runtime/lbc3/llvm-runtime/<缓存标识>/install/` |

`out/` 全部忽略。安装树通过 `DESTDIR` 生成，程序的目标安装路径为
`/usr/bin/zenith-control`；构建不会向宿主机 `/usr` 安装。

首次 LBC3 构建会校验 SDK 和 LLVM 源码 SHA256、解压并运行 Buildroot
重定位脚本，然后构建目标 LLVM 运行库。后续调用复用源码与构建缓存。
运行库缓存按源码、SDK 和配方区分，日志位于
`out/runtime/lbc3/llvm-runtime/<缓存标识>/build.log`。
项目配置没有固定开发机的绝对路径，也不依赖仓库外的 SDK checkout。
CMake 缓存及解压 SDK 的文本配置会记录计算出的本机路径；这些都是可重新
生成的产物。仓库搬家后，SDK 会再次重定位，已有 CMake 构建目录需重新生成。

独立使用 CMake preset 时，本机可以直接运行：

```bash
cd runtime
cmake --preset native
cmake --build --preset native
ctest --preset native
```

LBC3 建议使用统一脚本。手动 configure 时需要同时传入
`LBC_BUILDROOT_HOST_DIR` 和 `ZENITH_LLVM_RUNTIME_PREFIX`，分别指向解压的
SDK 与目标 LLVM 运行库安装目录。SDK 或运行库变化时，脚本会将原 LBC3
构建目录移到 `build-llvm.previous-*`，再重新配置。首轮 GCC 构建目录
`build/` 保留，LLVM 使用独立的 `build-llvm/`。

## 验证与后续部署

本机验证入口：

```bash
out/runtime/native/install/usr/bin/zenith-control --self-check
ctest --test-dir out/runtime/native/build-llvm --output-on-failure
```

交叉构建可检查 ELF，确认机器类型为 AArch64、解释器为板端 glibc 的动态
加载器，且没有宿主机 RPATH：

```bash
file out/runtime/lbc3/install/usr/bin/zenith-control
readelf -h -l -d out/runtime/lbc3/install/usr/bin/zenith-control
```

后续上板运行 `zenith-control --self-check`，确认目标 glibc 兼容与线程
创建实际成功。该检查不能代表实时延迟或控制性能。首轮未执行部署，未修改
rootfs、启动脚本或板端文件，也未增加设备权限要求。

2026-09-30 验证：native 三项 CTest 全部通过；LBC3 应用、异常处理与静态
OpenMP 检查程序均完成 AArch64 编译和链接。ELF 中确认 Clang/LLD 22.1.8，
无动态 libstdc++/libc++/libc++abi 依赖，无 RPATH/RUNPATH。重复构建复用缓存
成功；交叉程序尚未上板执行。源码使用 LLVM 官方
[22.1.8 release](https://github.com/llvm/llvm-project/releases/tag/llvmorg-22.1.8)
的归档，SHA256 与发布资产元数据一致。源码归档约 159 MiB，SDK 约 319 MiB，
均由 Git LFS 管理；构建过程中无需访问仓库外的 SDK 或在线下载源码。

## LLVM 运行库

`third_party/manifest.toml` 固定版本、下载地址和摘要；
`tools/runtime-llvm-runtimes` 是构建入口，由 `runtime-build lbc3` 自动调用。
只构建运行库，没有重新编译 Clang。libc++ 使用默认 ABI 版本 1，并保留异常
和 RTTI；libc++abi 使用 LLVM libunwind。native 使用系统 libc++，LBC3 使用
同一 LLVM 版本的目标静态运行库，两个平台的产物目录独立。

OpenMP 运行库已经构建；当前最小程序没有启用 OpenMP。后续接入 Pinocchio
时，需要在其构建配方中明确选用目标 libomp，不能使用宿主机的 x86_64 库。
更新 Clang 版本时需同步更新源码版本、校验文件、清单和运行库配方的版本
检查，避免不同版本的 ThinLTO bitcode 混用。

## SDK 快照更新

快照与 SHA256、`manifest.json` 一起纳入版本管理，压缩包用 Git LFS 保存。
清单记录 Buildroot commit、源码是否有未提交修改、配置摘要和 GCC 版本。
它描述当前构建产物的来源；若源码在编译后发生改变，更新快照前应先重建
Buildroot，让 SDK 与待部署固件保持一致。

需要更新时，从已构建的 Buildroot 导入：

```bash
./tools/runtime-sdk-import ../lbc_sdk/buildroot
git add .gitattributes runtime/toolchains/lbc3/
```

导入需要 Python ≥ 3.9。脚本复制整个 Buildroot `host/`，保留工具链和 sysroot，
修正 ELF RPATH 并附带厂商的 `relocate-sdk.sh`，随后打包。它不改动源 SDK。
归档中的中性打包路径只供重定位脚本替换，运行时不要求该目录存在。
SDK 快照更新后，重新生成 LBC3 构建目录并检查交叉产物。

## 目录演进

当前有 `apps/zenith-control/`、`cmake/toolchains/`、`toolchains/lbc3/` 和
LLVM 依赖清单 `third_party/manifest.toml`。随下一轮实现再创建以下模块：

- `libs/common/`：日志、配置等公共能力。
- `libs/control/`：运动学、轨迹和控制逻辑。
- `libs/transport/`：通信协议与抽象接口。
- `platforms/lbc3/`：RK3576 的 RPMsg/UIO、设备发现和板级适配。
- `config/lbc3/`：部署配置、机器人模型和标定数据。
- `third_party/recipes/`、`patches/`：固定版本依赖的构建配方和补丁。
- `examples/`、`tests/`：独立验证程序与业务测试。

SDK 补丁和固件版本继续由 `sdk/` 管理；机械研究保留在
`scripts/arm_design_study/`。部署工具将在上板验证阶段加入 `tools/`。
