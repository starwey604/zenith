# 当前可运行的运动学建模

本工作区的可运行部分是纯几何六轴模型：从本机 xArm6、UR5e MJCF 静态提取六根轴与零位法兰，统一计算 FK、雅可比和有限位 IK；将底盘平面泊位与臂座安装变换接入同一坐标链；按**工作台原有支撑固定模块**的场景生成直槽压入和法兰旋入的空间路径。MuJoCo 只执行 `mj_forward` 读取、核对静态位姿，不执行 `mj_step` 或 GoodArm 控制器。

依赖已经安装在 `zenith/.venv`。重新建环境时，在 `zenith` 目录执行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r scripts/arm_design_study/requirements-kinematics.txt
```

查看模型的零位轴关系、关节限位、轴间锚点距离与静态 FK 对照：

```bash
.venv/bin/python -m scripts.arm_design_study.cli models
.venv/bin/python -m pytest -q scripts/arm_design_study/tests
```

单姿态多逆解入口是 [ik_solutions.py](ik_solutions.py) 的 `enumerate_ik(arm, target, seeds=..., collision_free=...)`。`target` 是**臂座坐标系下的法兰** 4×4 位姿，`seeds` 可传一个 6 维关节向量或多个；求解器还会加入零位、关节中位和确定性的 Sobol 种子。默认累计尝试 32、64、128 个 Sobol 点；连续两档没有新增物理分支就停止。返回的 `branches[].canonical_q_rad` 按 2π 去重，`branches[].lifts[].q_rad` 列出限位内的各圈数，供后续轨迹图计算真实关节位移。`to_dict()` 可直接写入 JSON。

场景相关碰撞应通过 `collision_free(q)` 传入；回调返回布尔值，且会对每个提升解调用。没有回调时 `diagnostics.collision_checked` 为 `false`，结果只完成 FK 误差和限位筛选。`diagnostics.geometric_branches` 是碰撞筛选前的物理分支数，`independent_branches` 是至少保留一个无碰撞提升解的分支数；`best_position_error_m` 和 `best_angle_error_rad` 对应保留的解。`stable` 只表示这次确定性采样连续两档没有找到新分支，不能证明一般六轴机构所有逆解已经穷尽，也不能把空结果当作不可达证明。

运行**合成接口**路径检查，并把逐点关节角和失败码写到被 Git 忽略的 `runs/`：

```bash
.venv/bin/python -m scripts.arm_design_study.cli bayonet-demo --robot xarm6 --output scripts/arm_design_study/runs/xarm6.json
.venv/bin/python -m scripts.arm_design_study.cli bayonet-demo --robot ur5e --scale-span 2:1.15 --output scripts/arm_design_study/runs/ur5e_scaled.json
```

`--scale-span 2:1.15` 使第 2／3 关节的**零位锚点间距**增大 15%，并平移所有下游轴与法兰；它是保留关节轴关系的运动学构型假设，不能当成厂家改装或可制造设计。`models` 会报告每个可缩放锚点距离。底盘泊位通过 `--parking-x`、`--parking-y`、`--parking-yaw`，臂座高度通过 `--mount-z` 输入。默认示例会相对每个机器人的初始法兰放置承口，因此只能检验坐标和 IK 链。要比较**同一个固定工作台目标**下的臂长／泊位，把测得的 `T_W_D` 4×4 矩阵填入 [workbench_socket.template.json](configs/workbench_socket.template.json)，并以 `--socket` 指向该 JSON；缺少矩阵时程序会明确报 `missing_input`。

直槽尺寸模板 [bayonet_interface.template.json](configs/bayonet_interface.template.json)中的未知量一律是 `null`，直接用于求解会报出缺项。 [bayonet_interface.synthetic_example.json](configs/bayonet_interface.synthetic_example.json)所有数值仅用于回归代码，**不代表赛规、真实模块或工作台实测**。单机演示路径相位为 `approach → cone_align → key_align → straight_insert → bayonet_turn → locked`；固定场景入口另外生成 `leave_table`。过早旋转、错开键槽、未到锁角及肩面覆盖不足会返回相应失败原因。真实导向锥接触、插销与槽面完整碰撞、工作台能否承力尚未验证。

2026 核心和取矿的规则形状路径也已做成 [task_2026.py](task_2026.py)：核心依次沿工具局部 `-X` 插入 100 mm、`+Z` 升 100 mm、绕给定 P 轴向上转 90°、绕 Q 轴转到指定角；取矿针对指定矿位沿能量单元对称轴接近、抓取和外向拔出。`arm_opt` 的轴心偏置和抓取局部轴不能直接当成赛方尺寸，因此 P／Q 轴、抓取姿态、外向轴与行程必须填入 [core_2026.template.json](configs/core_2026.template.json)及 [pickup_2026.template.json](configs/pickup_2026.template.json)。填完后可执行：

按一、二、三级规则拆分后的单核心存矿固定场景和分级报告见 [README_STORAGE_2026.md](README_STORAGE_2026.md)；四级不纳入该数据集。

```bash
.venv/bin/python -m scripts.arm_design_study.cli core-2026 --task-config scripts/arm_design_study/configs/core_2026.template.json --output scripts/arm_design_study/runs/core_2026.json
.venv/bin/python -m scripts.arm_design_study.cli pickup-2026 --task-config scripts/arm_design_study/configs/pickup_2026.template.json --slot 1 --output scripts/arm_design_study/runs/pickup_slot_1.json
```

模板原样运行会报 `missing_input`，所以这些命令须在复制模板并填入实测或明确假设的数据后使用。加 `--solve-ik --robot xarm6` 或 `--solve-ik --robot ur5e` 后，单任务入口会用同一套有限位、连续多起点 IK 检查对应的工具轨迹；这时还必须填写 `flange_to_tool`，并可用 `--scale-span`、`--parking-x/y/yaw`、`--mount-z` 比较相同世界系目标。`ik_failed` 表示指定多起点求解没有收敛，不是数学不可达证明。固定场景的粗避碰见 [README_SCREENING.md](README_SCREENING.md)；时间筛选仍待实现。

UR5e 本地 MJCF 未启用 `compiler angle="radian"`，MuJoCo 原始关节限位因而把文件中写的 ±6.28319 解释成度。导入器从 `ur5e_classes.xml` 显式读取作者写下的弧度范围（肘轴为 ±3.1415）；输出来源会记录这一覆盖。当前 FK 对照只证明转换后的模型与**同一份本地 MJCF**的静态位姿一致，尚未独立核对厂家 URDF 和实物尺寸。

固定合成场景的粗碰撞、合法泊位、离台和候选报告已接在 [README_SCREENING.md](README_SCREENING.md)所述入口。下一轮应替换场地／接口实测值，检查停车误差、收纳及进出路线，并加入更完整的几何碰撞和独立厂家模型核验。接口压入力、锁后承载、质量、驱动扭矩和动态稳定性属于后续 GoodArm 复核。
