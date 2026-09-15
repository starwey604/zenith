# 固定场景几何初筛

本轮把六轴模型、臂长锚点缩放、底盘泊位和三类任务接到一份**固定场景**。运行器对每个候选检查底盘完整占地、有限位连续 IK、逐采样连杆／工具／底盘／模块粗碰撞及展开包络；首个收敛 IK 分支碰撞时再搜索避碰分支，后续点限制关节跳变。卡口路径包括锁定后的模块随末端离台。所有目标对所有候选保持不变。

从 `zenith` 目录运行，无需再安装依赖：

```bash
.venv/bin/python -m scripts.arm_design_study.benchmark \
  --scene scripts/arm_design_study/configs/benchmark.synthetic.json \
  --output-prefix scripts/arm_design_study/runs/benchmark_screen
.venv/bin/python -m pytest -q scripts/arm_design_study/tests
```

运行器写出三份文件：`benchmark_screen.json` 保存场景、接口及本机参考模型 SHA-256、每项任务逐采样关节角、碰撞余量代理值、模块位姿和首次失败；`benchmark_screen.csv` 每任务一行；`benchmark_screen_candidates.csv` 每个「六轴模板／臂长假设／泊位」一行，列出六矿位、核心和模块任务的完成数量。报告的完成指**所给定样本点的几何检查完成**，不包含接触力、时限或锁后强度。

这里的六矿位成绩只覆盖单一放置角的轴向接近、抓取与拔出。整矿离开出口边沿及绕对称轴放置角样本由 [README_PICKUP_EXIT.md](README_PICKUP_EXIT.md)说明的独立检查报告给出；后续底盘驶离和收臂不计入该报告。基础 CSV 的 `pickup_complete_count` 不能解释为满足出口安全条件的矿位数。

基础 `core_2026` 是一个完整 P／Q 路径例子，没有区分装配难度。新的 [README_STORAGE_2026.md](README_STORAGE_2026.md)把科技核心存矿拆为一、二、三级固定样本，并明确排除四级双核心要求；比较存矿能力应查看这份独立报告的分级成绩。

[benchmark.synthetic.json](configs/benchmark.synthetic.json)用于审查计算链：两种本地六轴模板、两种第 2／3 关节锚点间距、三个泊位及八个固定任务，共 96 项。工作台支撑盒顶面取 400 mm，与 2027 前瞻图示高度一致；其占地实体、承口高度、模块外形、120 mm 法兰到插销距离、连杆胶囊半径、矿位、核心 P／Q 轴和泊位范围均为**合成设计假设**。赛方工作台是否能在不改造的条件下承受压入／旋入反力仍待实测。不能用这份文件给实物构型排名。

粗碰撞的规则如下：零位关节锚点之间的每段连杆成为胶囊，锚点距离缩放时胶囊同步变长；场地、底盘和携带的模块为定向盒体。相邻非零长度连杆共享真实关节体积，故跳过最近两层自碰撞配对。插销与模块承口在对接阶段的预期接触、锁定瞬间模块与原有支撑的接触，必须在配置的 `allowed_contacts` 中逐物体、逐阶段列出；其他碰撞仍会报告。盒体间的 `clearance_proxy_m` 是分离轴投影代理量，胶囊距离是解析几何距离；两者足以作粗筛，不能当作制造公差或接触深度。

基础报告中的泊位只改变接触动作开始前的 `x, y, yaw`；底盘占地四角须落在配置的**凸多边形**内，底盘盒体不能压到声明为 `blocks_chassis` 的障碍。两份取矿初筛报告都不检查泊位进出路线。停车误差、网格级碰撞、收纳体积和采样点之间的连续碰撞仍未检查。`ik_failed` 是本程序的有限多起点求解失败，`joint_jump` 是所选连续分支超过给定步长；两者都不能独自证明目标数学不可达。

替换为实测场景时，先复制合成文件并保留固定 `scenario_id`、单位、随机种子与任务 ID，然后填写真实承口 `T_W_D`、六矿位抓取位姿／外向轴、科技核心 P／Q 轴、底盘合法区域、模块及机器人碰撞包络。接口尺寸从 [bayonet_interface.template.json](configs/bayonet_interface.template.json)填写，禁止把合成卡口数字直接标成赛规。将场景来源标为 `measured` 之前，所有仍属假设的字段都应在场景说明中逐一注明。候选集可以先增加臂座高度／偏置和轴间距变化，再增加 Ned2、myCobot 等独立核验的六轴构型。
