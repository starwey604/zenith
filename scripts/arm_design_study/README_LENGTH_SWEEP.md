# 六轴构型／臂长完整任务批量筛选

协调器 [length_sweep.py](length_sweep.py)让每个「六轴参考轴线模板 × 关节锚点跨度 2／3 × 底盘固定泊位」候选单独在一个工作进程中完成同一套路径。默认 [length_sweep.v1.json](configs/length_sweep.v1.json)对 xArm6、UR5e 两个参考模板独立使用 0.8／0.9／1.0／1.1／1.2 倍的两个非零零位锚点跨度，在 `rear_left`、`rear_center` 两个合法泊位上共生成 100 项。任务为一至三级科技核心存矿 67 项、六矿位各 12 个放置角的取矿出口 72 项，以及基础固定场景的 8 项（其中含 2027 卡口模块装配）。没有按候选表现改变任务；它们使用同一个原始场景、存矿任务、接口和随机种子。构型参考模型、尺寸、碰撞体与泊位仍是设计假设。

从 `zenith` 目录运行：

```bash
.venv/bin/python -m scripts.arm_design_study.length_sweep \
  --spec scripts/arm_design_study/configs/length_sweep.v1.json \
  --scene scripts/arm_design_study/configs/benchmark.synthetic.json \
  --storage-task scripts/arm_design_study/configs/storage_2026.stress.synthetic.json \
  --output-dir scripts/arm_design_study/runs/length_sweep_v1
```

默认并发上限为 2 个独立 Python 工作进程，每个进程把微型矩阵库线程数限制为 1；协调器在系统可用内存少于 2 GiB 时暂停分派新任务。一个候选内部的相邻轨迹点保持连续 IK 状态，不能跨进程拆点。工作进程直接写未压缩的逐候选 JSON 到已忽略的 `runs/`，协调器仅接收小型摘要。`--limit N` 可先跑 N 个新候选，重复同命令会按输入哈希和原子写出的完整候选报告续跑。`manifest.json` 固定配置、代码及参考模型哈希；若改动输入，必须换输出目录，不能把旧结果混入新场景。

候选采样另支持固定种子准蒙特卡洛：[length_sweep.sobol.template.json](configs/length_sweep.sobol.template.json)在两个跨度比率的范围内生成 16 个 Sobol 点，另外保留原长，两个模板与两个泊位共 68 项。这个文件只是另一个可运行配置，必须使用独立的工作／结果目录。对比测试的**任务数据始终固定**；蒙特卡洛或准蒙特卡洛仅决定候选几何。规则位置／姿态范围的角点压力样本仍保留。有限候选集不能证明连续设计空间的全局最优。

全部候选完成且无错误之后，才用 [publish_length_sweep.py](publish_length_sweep.py)逐一校验报告的输入哈希和 67／72／8 项数，复制原始轨迹报告到 `results/` 并画长度热图及存矿／取矿权衡图。此时再用 Git LFS 跟踪 `results/` 中的逐候选 JSON 和 PNG 图片并提交；运行中的 `runs/` 不交给 LFS。汇总 JSON／CSV 和清单作为普通 Git 文件，便于审查差异。Git LFS 对象在本机仓库中保存；若仓库没有远端，这一步不等于上传。

图上的“跨度”是零位关节轴锚点之间的距离，不是认证的连杆长度。当前缩放保持关节轴方向、限位和粗碰撞半径，未计电机／减速器、载荷力矩、质量、结构强度、底盘行驶与返回收臂、装配接触以及采样点之间的连续碰撞。`module_complete` 和各级通过比例只代表这份合成运动学几何模型的结果。
