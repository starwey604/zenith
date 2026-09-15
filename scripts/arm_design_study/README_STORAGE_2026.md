# 2026 科技核心存矿几何场景

存矿在这里指工程机器人把已携带的能量单元装配入**一个科技核心**；路径从矿石已夹在末端、工具到达预插位置开始，取矿区到科技核心的运输不模拟。按 2026 规则第 86–89 页，一级几何动作只有沿插入方向 100 mm；二级在插入后再上移 100 mm；三级继续绕 P 轴上转 90°、绕 Q 轴转到指定角。四级要求双核心及配对限时，这个工作区不生成也不接受四级样本。裁判系统选择难度、确认、传感器检测、释放抓手和能量单元回收不在运动学报告里；`ready_for_confirmation_geometry` 只表示该级别最后一段采样运动完成。

从 `zenith` 目录运行：

```bash
.venv/bin/python -m scripts.arm_design_study.storage_2026 \
  --scene scripts/arm_design_study/configs/benchmark.synthetic.json \
  --task scripts/arm_design_study/configs/storage_2026.synthetic.json \
  --output-prefix scripts/arm_design_study/runs/storage_2026_screen
```

可加 `--robot xarm6 --variant nominal --parking rear_center` 只查看一个候选。程序对所有候选使用相同六个固定任务样本，每级两个；输出逐样本 JSON／CSV 和 JSON 内的逐候选一、二、三级完成数。每项保留关节角、首次 IK／碰撞／展开限制失败和场景、任务、规则及 `arm_opt` 参考文件的 SHA-256。

本轮另有固定压力集 [storage_2026.stress.synthetic.json](configs/storage_2026.stress.synthetic.json)，由 [storage_stress.py](storage_stress.py) 在原合成任务几何上按种子 `20260916` 生成。一级含中心、八个位置角点、六个分层内部点；二级含中心、六维各自上下界的十二个点、十二个六维分层内部点；三级复用二级的 25 个位姿，并多加两个中心位姿的 Q 轴 ±90° 端点，总数为 15／25／27。各候选共用这 67 个目标，不按结果修改样本。重建和完整筛选命令：

```bash
.venv/bin/python -m scripts.arm_design_study.storage_stress \
  --base-task scripts/arm_design_study/configs/storage_2026.synthetic.json \
  --output scripts/arm_design_study/configs/storage_2026.stress.synthetic.json \
  --seed 20260916
.venv/bin/python -m scripts.arm_design_study.storage_2026 \
  --scene scripts/arm_design_study/configs/benchmark.synthetic.json \
  --task scripts/arm_design_study/configs/storage_2026.stress.synthetic.json \
  --output-prefix scripts/arm_design_study/runs/storage_2026_stress
```

报告的 `balanced_completion_fraction` 是一、二、三级几何完成比例的简单平均，避免一级／三级样本数不同导致总通过数掩盖分级差异；`failure_phases`、`failure_reasons` 给出首次失败统计。`min_pass_clearance_proxy_m` 是粗胶囊／盒体碰撞模型的距离代理，`min_pass_joint_limit_margin_rad` 是已完成样本的最小关节限位余量。压力集用于比较目前的参考模型和臂长变体，不表示目标出现概率或赛场成功率。

目标姿态沿用 `arm_opt/traj_disp.py` 的 `Rz(theta) Ry(phi) Rz(alpha)` 约定，用 `station_world_pose` 把规则装配坐标系样本放入场地世界系；生成器校验规则表 5-10 的 x／y／z／θ／φ／α 单核心范围，以及一级固定朝向。运动按 `arm_opt` 工具局部 `-X` 插入、局部 `+Z` 上移。三级 P／Q 轴可以在每个样本直接填写实测 `p_axis_origin_world`、`p_axis_world`、`q_axis_origin_world`、`q_axis_world`；未填写时才按 `p_axis_offset_m`、`q_axis_offset_m` 从插入末端工具系构造，合成值分别取 `arm_opt` 的 0.20875 m 和 0.22375 m。**这些轴偏置和局部方向是建模假设，不是赛规尺寸或测量结论**；实物核心柱轴和工具到矿石本体的位姿须重新标定。

[storage_2026.synthetic.json](configs/storage_2026.synthetic.json)只用于验证程序：世界系装配台、六个固定姿态、核心底座盒体和抓手偏置均为合成设计假设。[storage_2026.template.json](configs/storage_2026.template.json)列出待测字段，填妥之前不能直接运行。资源站挡板仅在取矿阶段、2027 工作台支撑仅在模块阶段启用；它们在共同场景中仍会阻挡底盘占地。若替换实物场景，应填写真实科技核心位姿、P／Q 轴、装配柱碰撞体及可接受接触阶段，并保持各候选共用同一任务集。

目前的通过只覆盖采样运动学、粗盒体／胶囊碰撞与底盘泊位。插入和上移阻力、Q 轴回正力矩、对准公差、连续碰撞、抓手松开、裁判确认与时间窗口仍未验证；不能把 `ready_for_confirmation_geometry` 写成赛场装配成功率。
