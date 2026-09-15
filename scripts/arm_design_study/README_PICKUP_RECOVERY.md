# 取矿检查范围已收敛

取矿初筛现按 [README_PICKUP_EXIT.md](README_PICKUP_EXIT.md)执行：沿轴拔出，并让整件矿石越过装置出口边沿及安全距离。底盘撤离和收臂不再影响取矿通过判定。

旧命令 `python -m scripts.arm_design_study.pickup_recovery` 仍可运行，但现在调用相同的出口检查，生成相同格式的报告。旧的 `runs/pickup_recovery_*.json` 是之前的持矿回位试验结果，不能与新的 `pickup_exit_*.json` 成绩混用。
