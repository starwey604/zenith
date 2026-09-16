# 六轴四段长度与多位姿装配批量测试

本轮在七个六轴参考轴线模型上比较 J2→J3、J3→J4、J4→J5、J5→J6 四个零位轴心跨度。每个模型先读取原始跨度；距离小于 `1e-8 m` 的段保持固定为零，不生成倍率。xArm6、Lite6 和 PiPER 的 J4→J5 因此不会被无效缩放。其余段使用固定种子的 Sobol 样本，在原长的 `0.75～1.25` 倍之间同时测试缩短和加长，并额外保留原型。七个模型 × 十七组长度 × 四个固定合法底盘泊位，共 476 个候选。参考模型文件及来源见 [models/menagerie/README.md](models/menagerie/README.md)。

每个候选独立运行相同的任务：一至三级科技核心存矿 67 项、六矿位十二个放置角的取矿越边沿检查 72 项、基础固定场景 8 项，以及九个合成承口位姿的英雄头直槽压入／旋入／锁定／离台装配路径。装配压力集保持原工作台支撑高度，承口分别移动 `±30 mm`（世界 X 或 Y）、斜向移动 `20 mm`（X 与 Y 同时变化），或绕世界 Z 转 `±15°`；这些偏移是几何压力假设，不是赛规公差。九项包含原位姿，与基础场景中的 `module_2027` 单例重复，用于检查数据链一致性。所有候选共享同一份原始场景、任务、位姿样本和随机种子。

从 `zenith` 根目录运行；依赖使用已有 `.venv`。协调器最多同时使用两个工作进程，内存可用量低于预留的 `2 GiB` 时暂停提交新候选。工作目录在 `runs/` 内，可以中断后用相同命令续跑：

```bash
.venv/bin/python -m scripts.arm_design_study.length_sweep_v2 \
  --output-dir scripts/arm_design_study/runs/length_sweep_v2 \
  --scratch-dir scripts/arm_design_study/runs/length_sweep_v2_scratch
```

只有全部候选完成且输入哈希和任务分母检查通过后，才发布逐候选轨迹、汇总表和图片：

```bash
.venv/bin/python -m scripts.arm_design_study.publish_length_sweep_v2 \
  --work-dir scripts/arm_design_study/runs/length_sweep_v2 \
  --result-dir scripts/arm_design_study/results/length_sweep_v2
```

发布后的 `summary.csv` 每候选一行，包含四段轴心跨度、倍率、底盘泊位、三级存矿、取矿、`module_stress_complete/9`，以及九条装配路径中的最低几何净距估计和最低关节限位余量。`best_by_robot.csv` 每参考模型选一项：先要求基础装配路径通过，再最大化存矿、取矿、九位姿装配三项通过率中的最低值；没有基础装配通过项的模型会标出 `module_basic=False` 和 `robust_fraction=-1`，不应读成可用赢家。`pareto_3tasks.csv` 列出基础装配通过后，在三项通过率上没有被另一候选同时赶超的方案。`configuration_overview.png` 的三个面板分别显示存矿、取矿、装配通过率；`three_task_tradeoff.png` 用横轴表示取矿、纵轴表示存矿、颜色表示装配。每个点是一组长度和泊位，不是一次独立装配试验。

所有跨度均为零位轴心锚点之间的距离，不是实体连杆下料长度。零轴心跨度不代表腕部外壳没有尺寸。本轮保持轴线方向和粗碰撞半径，缩放时平移下游轴与法兰；仍未计算制造约束、质量、力矩、压入力、卡扣受力、底盘泊位间行驶、撤离收臂，以及采样点之间的连续碰撞。工作台承口、矿位、底盘、工具及各参考臂的碰撞包络仍属合成设计假设，结果只能用于筛选下一批需要实测的构型。

将当前 xArm6 领先轴线改用 Willow 碳管和板件工艺实现时，需要区分产品外观、轴线拓扑与搜索尺寸。具体比较和下一轮公平测试方案见 [Willow 工艺实现 xArm 类轴线的可制造性评估](WILLOW_XARM_MANUFACTURABILITY.md)。

Willow 0907 已使用绝对跨度单独完成 136 个候选的补充扫描，详见 [Willow 0907 独立扫描结果](results/length_sweep_willow0907_v1/README.md)。该运行使用 3 个工作进程，并保留原 URDF 关节限位。
