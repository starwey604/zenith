# 取矿出口几何初筛

本阶段取矿的通过条件只有两项：给定放置角度的矿石沿旋转对称轴完成接近、抓取和拔出；**整件矿石**越过资源站装置出口平面，并留下配置的安全距离。2026 规则手册第 48–49 页要求沿能量单元对称轴取出，且实际放置角度可能绕该轴偏移。底盘驶离和机械臂收回是取出后的操作，不再计入本初筛成绩，也不在此模拟。

从 `zenith` 目录运行：

```bash
.venv/bin/python -m scripts.arm_design_study.pickup_exit \
  --scene scripts/arm_design_study/configs/benchmark.synthetic.json \
  --output-prefix scripts/arm_design_study/runs/pickup_exit_xarm6 \
  --robot xarm6 --variant nominal --parking rear_left
```

去掉候选过滤参数即可对所有模型、臂长和泊位使用同一组矿位及角度样本。程序生成逐样本 JSON 和 CSV。`exit_geometric_complete` 表示该角度的采样取矿轨迹与出口余量通过；摘要中的 `all_sampled_angles_slot_count` 是该矿位所有**配置角度样本**均通过的数量。失败保留首次发生的阶段和原因；有限多起点 IK 失败只表示程序未找到该路径。

每个矿位的 `outward_symmetry_axis_world` 指定轴向拔出方向，`exit_edge_point_world_m` 定义一张法向与它一致的出口平面。`tool_to_unit` 是抓手工具系到矿石本体中心的固定位姿。程序用矿石定向盒体最靠装置内侧的角算出出口距离，然后把拔出长度增至至少 `edge_safety_distance_m + edge_pose_guard_m`；目标长度不能超过 `max_axial_extraction_distance_m`。最后还用求出的**实际关节角 FK**重算出口余量，避免只依赖目标位姿。角度变化绕矿石本体对称轴旋转抓取姿态，保持矿石中心不动。

[benchmark.synthetic.json](configs/benchmark.synthetic.json)用六个合成矿位、每位 12 个相隔 30° 的角度、40 mm 安全距离和 1 mm 位姿计算余量验证计算链。这些尺寸、出口位置、抓手偏置及障碍包络不是赛规或实物数据。[pickup_2026.template.json](configs/pickup_2026.template.json)列出待测任务字段；填妥后把它们复制到完整场景的 `tasks.pickup_2026`，并把实测挡板碰撞体补进 `obstacles`。当前只检查离散角度与轨迹采样点；角度间和采样点间的连续避碰、夹持可靠性及克服至多 10 N 磁吸力仍待验证。基础 [README_SCREENING.md](README_SCREENING.md)里的 `pickup_complete_count` 仍是单角度、固定拔出长度的旧指标，应以本报告判断取矿出口几何条件。
