# 正交六轴轴线语法目录 v1

运行 `zenith/.venv/bin/python -m scripts.arm_design_study.topology_grammar --output scripts/arm_design_study/results/topology_grammar_v1/catalog.json` 可重新生成 [catalog.json](catalog.json)。目录按 Git LFS 存储；记录完整的轴向、关节锚点、零位法兰、关节限位、直段路线和稳定标识。

固定 J1 为竖直 Z，J2 为水平 X/Y，J6 为零位工具 X 向滚转轴；枚举 J3/J4/J5 的 X/Y/Z 方向和六种锚点布局，共 324 个原始组合。以默认 290 mm 上臂、390 mm 前臂、60 mm 小偏置为基准，筛掉相邻同轴 156 个、在三个固定姿态中不足两次达到六维满秩 18 个，再合并 16 个螺旋轴线相同的候选，剩 **134 个运动学候选**。被合并的其他锚点语法保存在 `equivalent_syntaxes`，便于未来单独比较实体路由。

| 原人工模板 | 新目录 ID | 锚点布局 | 轴向词 J1→J6 |
|---|---|---|---|
| `rm2p_offset_wrist` | `orth6r_9c26d67ce669` | 腕部上偏置 | `zyyxyx` |
| `rm2p_spherical_wrist` | `orth6r_2ffd1d63edaa` | 球腕 | `zyyxyx` |
| `rm3p_spherical_wrist` | `orth6r_d94907e07b06` | 球腕 | `zyyyzx` |
| `rm_spherical_shoulder` | `orth6r_ca186130cd66` | 球肩 | `zyxyzx` |
| `rm_offset_shoulder` | `orth6r_c3d099507842` | 肩部上偏置 | `zyxyzx` |

`topology_id` 由锚点布局和轴向词生成，臂长变化时保持不变；`geometry_id` 由规范化螺旋轴线与法兰位姿生成，尺寸变化时更新。螺旋轴线规范化会忽略轴向正负号及锚点沿轴线的移动。直段路线筛选只允许正交直段和至多一个 60 mm 的短折线；雅可比满秩仅证明抽样姿态的局部六维可动性。电机实体包络、轴承支撑、收纳、碰撞、任务成功率和结构载荷都尚未由本目录证明。现有批量任务筛选器也尚未接入新 ID 与逆解图，因此这里没有新的最优构型排名。
