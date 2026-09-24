# 把 CAN-FD 移到 Cortex-M0（bus_mcu）

> 目标：RK3576 的 CAN-FD 由 M0 独占（实时收发电机/底盘帧），Linux 侧不再驱动 CAN；
> Linux 应用经 rpmsg（后续可换 UIO 共享内存）与 M0 交换 CAN 帧。

## 1. 现状盘点（已在树内核实）

### 硬件 / Linux 侧
- RK3576 有 **两个 CAN-FD 控制器**：
  - `can0@0x2ac00000`（GIC SPI 121）、`can1@0x2ac10000`（GIC SPI 122），
  - compatible = `rockchip,rk3576-canfd`。
- `rk3576.dtsi` 中两个节点都是 `status = "disabled"`；`rk3576-lubancat-3.dts` 未引用 CAN。
  → **Linux 当前完全不占用 CAN，正是交给 M0 的窗口期。**
- Linux 驱动为 `drivers/net/can/rockchip/rockchip_canfd.c`（我们不用它）。
- LubanCat 提供的 Linux DT overlay（供参考引脚/时钟）：
  - `overlay/rk3576-lubancat-can0-m2-overlay.dts` → `pinctrl-0 = <&can0m2_pins>`，`CLK_CAN0 = 100 MHz`
  - `overlay/rk3576-lubancat-can1-m3-overlay.dts` → `pinctrl-0 = <&can1m3_pins>`，`CLK_CAN1 = 100 MHz`

### M0（rk3576-rtos / rk3576-hal）侧
- **RT-Thread 驱动已存在**：`bsp/rockchip/common/drivers/drv_canfd.c`
  - 通过 RT-Thread CAN framework（`#ifdef RT_USING_CAN`）注册 `rk_can0/rk_can1/rk_can2`；
  - 收/发走 `HAL_CANFD_Receive/Transmit`，中断里 `rt_hw_can_isr(...)`。
- **HAL 完整**：`lib/hal/src/hal_canfd.c`、`lib/hal/inc/hal_canfd.h`。
- **per-SoC BSP 描述符已就绪**：`lib/bsp/RK3576/hal_bsp.c`
  ```c
  const struct HAL_CANFD_DEV g_can0Dev = {
      .pReg = CAN0, .sclkID = CLK_CAN0,
      .sclkGateID = CLK_CAN0_GATE, .pclkGateID = HCLK_CAN0_GATE,
      .irqNum = CAN0_IRQn,
  };
  /* g_can1Dev 同理 */
  ```
- **地址映射自动处理**：`rk3576.h` 中 `#ifdef HAL_MCU_CORE` → `MCU_OFFSET = 0x20000000`，
  故 M0 视角 `CAN0_BASE = 0x4AC00000`（Linux 视角同物理地址 0x2AC00000）。
- **引脚**（沿用 LubanCat overlay 的 mux）：
  | 控制器 | mux | RX | TX | iomux |
  |---|---|---|---|---|
  | can0 | `can0m2` | GPIO4_A6 | GPIO4_A4 | FUNC 13 |
  | can1 | `can1m3` | GPIO3_A3 | GPIO3_A2 | FUNC 11 |
- **当前未启用**：`bsp/rockchip/rk3576-mcu/board/evb/defconfig` 里 `# CONFIG_RT_USING_CAN is not set`；
  BSP 的 `rt_hw_iomux_config()`（`board/evb/iomux.c`）里也没有 CAN 引脚配置。
- BSP 的 `drivers/` 目录是空的（仅 Kconfig/SConscript），驱动都在 `common/drivers/`，
  由 `common/drivers/SConscript` 的 `Glob("*.c")` 收集 → `drv_canfd.c` 会参与编译（`RT_USING_CAN` 打开后生效）。

## 2. 方案

### 阶段 1：M0 单机 CAN-FD（先不接 Linux）
1. **打开开关**：`board/evb/defconfig` 增加 `CONFIG_RT_USING_CAN=y`（RT-Thread CAN framework）。
2. **引脚**：在 `board/evb/iomux.c` 的 `rt_hw_iomux_config()` 里新增
   `can0_m2_iomux_config()` / `can1_m3_iomux_config()`，照 HAL iomux 风格：
   ```c
   RT_WEAK void can0_m2_iomux_config(void)
   {
       HAL_PINCTRL_SetIOMUX(GPIO_BANK4,
                            GPIO_PIN_A6 |  /* can0_rx_m2 */
                            GPIO_PIN_A4,   /* can0_tx_m2 */
                            PIN_CONFIG_MUX_FUNC13);
   }
   ```
   （can1m3：`GPIO_BANK3`，`GPIO_PIN_A3|GPIO_PIN_A2`，FUNC11。）
3. **时钟**：`RT_USING_CRU=y` 已开。初始化前把 `CLK_CAN0/1` 配到与驱动假设一致的频率，
   并统一 `drv_canfd.c` 里的 `ROCKCHIP_CAN_CLK_RATE`（见“待核实”）。
4. **注册**：无需改动，`drv_canfd.c` 已注册 `rk_can0/rk_can1`。
5. **验证**：写个最小 app（或 msh 命令）用 `rt_device_find("can0")` + CAN framework 收发；
   对端用 USB-CAN 分析仪（或临时在 Linux 开同控制器做对照，测完立刻关）。
   **首先确认 M0 能收到 CAN 中断**（IRQ 路由是最大不确定项）。

### 阶段 2：Linux ↔ M0 通道（rpmsg）
- 复用 `common/drivers/rpmsg-lite` + 已保留的 rpmsg 内存：
  Linux `0x47d00000` / M0 `0x27d00000`，2 MiB（见 `rk3576-amp.dtsi`、`amp_mcu_rtt.its` 的 `share`）。
- 定义协议：`CMD_MOTOR`（Linux→M0→CAN）、`EVT_CAN_RX`（M0→Linux）、状态/心跳。
- Linux 侧：`drivers/rpmsg/*` + `rpmsg_char`（用户态 char dev），或按既定路线换 UIO 共享内存。

### 阶段 3（可选）：Linux 侧看到 SocketCAN
- 若要上层用 `can-utils`/SocketCAN 透明访问，两种做法：
  - (a) 用户态网关：rpmsg ←→ `vcan`（最快，但多一层拷贝）；
  - (b) 自定义 rpmsg CAN 内核模块（对标 virtio-can 思路）。
- **红线**：同一个控制器绝不能 Linux `rockchip_canfd` 与 M0 同时驱动。

## 3. 待核实 / 风险
1. **M0 CAN 中断路由**：`CAN0_IRQn` 在 M0 的 NVIC/向量上是否真实可达（RK3576 bus_mcu 外设中断转发）。
   先实测中断计数；不行再考虑轮询或查 GRF 路由寄存器。
2. **LubanCat-3 上 CAN 的物理出口**：overlay 用了 can0m2 / can1m3，但需确认接的是 40-pin 还是端子，
   以及板载收发器是否有 `standby/EN` 脚需要拉高（Linux overlay 未提供 gpio → 疑似默认为使能）。
3. **时钟频率一致性**：Linux overlay 用 100 MHz，M0 `drv_canfd.c` 硬编码 `200000000`。
   二者决定 bitrate 分频，必须统一（否则波特率错）。
4. CAN-FD 数据段波特率、采样点，以及 RT-Thread CAN framework 对 FD 的支持程度。

## 4. 落地清单
- `rk3576-rtos`（fork）
  - `bsp/rockchip/rk3576-mcu/board/evb/defconfig`：`CONFIG_RT_USING_CAN=y`
  - `bsp/rockchip/rk3576-mcu/board/evb/iomux.c`：`can0_m2_*` / `can1_m3_*` iomux + 调用
  - `bsp/rockchip/common/drivers/drv_canfd.c`：统一 `ROCKCHIP_CAN_CLK_RATE`（按实测时钟）
  - （测试用）`applications/` 下一个 can shell/app
- `lbc_kernel`（fork）
  - 保持 `can0/can1` 为 `disabled`；确保 AMP 启动不叠加 can overlay。
    `rk3576-lubancat-3-mcu.dts` 当前已满足。
- `zenith`
  - 本文件 + 更新 `baseline.toml` 的 `[amp]`/待办记录。

## 5. 建议的下一步（最小可验证）
先只做“阶段 1 的 1~3 步 + 自环/外部收发验证”，确认 M0 能稳定收 CAN 中断并正确收发；
再进入 rpmsg 协议设计与 Linux 侧接口。
