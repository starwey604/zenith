# 通用六轴几何工具

2026-10-20 清理后只保留可供新夹取搬运任务复用的数学工具。旧选型配置、商品臂参考网格、批量扫描、任务脚本、负载表和网页已删除。历史结论与局限见[头部方案演变](../../mechanical/hero_head/DESIGN_HISTORY.md)；当前目标几何见[头部设计说明](../../mechanical/hero_head/pick_place_study/README.md)。

| 文件 | 用途 |
|---|---|
| `sixr.py` | 输入六根零位轴、轴上点、法兰与限位，计算FK、雅可比及有限位数值IK |
| `frames.py`、`chassis.py` | 坐标变换、底盘泊位与臂座组合 |
| `length_design.py` | 缩放轴间锚点距离，不保留具体最优杆长 |
| `ik_solutions.py` | 多起点逆解、2π物理分支去重和限位内圈数展开 |
| `ik_graph.py` | 分层逆解图、真实关节行程和插值边检查 |
| `collision.py`、`parking.py` | 胶囊／盒体的粗几何筛选、底盘泊位边界 |

依赖：`numpy`、`scipy`；运行保留下来的通用回归检查另需`pytest`。环境已在仓库`.venv`，重建时执行：

```bash
.venv/bin/python -m pip install -r scripts/arm_design_study/requirements-kinematics.txt
.venv/bin/python -m pytest -q scripts/arm_design_study/tests
```

`SixR`使用m、rad；网页导出的目标使用mm，接入前必须转换并标定法兰到夹爪的变换。没有保留任何已定型的机械臂构型，也没有为当前直推头重新求解完整路径。

`enumerate_ik(arm, target, ...)`的target是臂座系4×4法兰位姿；`solve_ik_path(arm, mount, path, seed, ...)`的每个路径点需有`phase`与世界系`world_flange`。碰撞回调必须由真实场景提供；没有回调的成功结果不证明无碰撞。数值搜索失败也不等于数学不可达。

**粗碰撞工具的已知限制：**相邻链体和近腕附着区域有豁免，胶囊不含真实电机壳体、错层、线束或接触变形。新方案须补充实际几何后再使用通过率和关节负载结论；旧臂上射击数据不能直接转成当前搬运任务的电机规格。
