"""Plots and compact tables for the minimum-stowage sweep."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .length_sweep_v2_plots import robust_fraction


plt.rcParams["font.family"] = "Noto Sans CJK SC"
plt.rcParams["axes.unicode_minus"] = False


def _task_robust(task: dict | None) -> float | None:
    return None if task is None else robust_fraction(task)


def _render_many_robots(rows: list[dict], robots: list[str], best: dict[str, dict],
                        baseline: dict[str, dict], output_dir: Path) -> list[str]:
    """Show distributions rather than 134 overlapping robot labels."""
    fig, ax = plt.subplots(figsize=(11, 6.2), constrained_layout=True)
    sizes = [best[robot]["worst_axis_ratio"] * 600 for robot in robots]
    ax.hist(sizes, bins=24, color="#31788f", edgecolor="white")
    ax.axvline(600, color="#c83e4d", linestyle="--", label="规则上限 600 mm")
    ax.set(xlabel="最紧张方向的最小收纳尺寸 / mm", ylabel="构型数",
           title="各构型最佳无碰撞收纳包络分布")
    ax.legend()
    dimensions_plot = output_dir / "best_dimensions_by_robot.png"
    fig.savefig(dimensions_plot, dpi=180)
    plt.close(fig)
    plots = [str(dimensions_plot)]

    if any(row["task_best"] is not None for row in rows):
        fig, ax = plt.subplots(figsize=(10.8, 7.2), constrained_layout=True)
        scorable = [row for row in rows if row["collision_free"] and row["task_best"] is not None]
        ax.scatter([row["worst_axis_ratio"] * 600 for row in scorable],
                   [max(0.0, _task_robust(row["task_best"])) * 100 for row in scorable],
                   s=30, alpha=0.55, color="#31788f")
        ax.axvline(600, color="#c83e4d", linestyle="--")
        ax.set(xlabel="最紧张方向的收纳尺寸 / mm", ylabel="三任务稳健通过率 / %",
               title="收纳尺寸与任务能力")
        ax.grid(alpha=0.22)
        tradeoff_plot = output_dir / "stowage_task_tradeoff.png"
        fig.savefig(tradeoff_plot, dpi=180)
        plt.close(fig)
        plots.append(str(tradeoff_plot))

    fig, ax = plt.subplots(figsize=(8, 7.2), constrained_layout=True)
    x = [baseline[robot]["worst_axis_ratio"] * 600 for robot in robots]
    y = [best[robot]["worst_axis_ratio"] * 600 for robot in robots]
    ax.scatter(x, y, s=34, alpha=0.6, color="#31788f")
    limit = max(600, *x, *y) * 1.02
    ax.plot([0, limit], [0, limit], color="#888888", linestyle="--")
    ax.axhline(600, color="#c83e4d", linestyle=":")
    ax.set(xlabel="名义长度收纳尺寸 / mm", ylabel="测试长度中最小尺寸 / mm",
           xlim=(0, limit), ylim=(0, limit), title="长度变化对最小收纳尺寸的影响")
    ax.grid(alpha=0.22)
    comparison_plot = output_dir / "baseline_vs_best.png"
    fig.savefig(comparison_plot, dpi=180)
    plt.close(fig)
    plots.append(str(comparison_plot))
    return plots


def render(summary_path: Path, output_dir: Path) -> dict:
    report = json.loads(summary_path.read_text(encoding="utf-8"))
    if (report["complete_candidate_count"] != report["candidate_count"] or report["errors"]):
        raise ValueError("cannot render an incomplete stowage sweep")
    rows = report["rows"]
    output_dir.mkdir(parents=True, exist_ok=True)
    robots = sorted({row["robot"] for row in rows})
    best = {robot: min((r for r in rows if r["robot"] == robot),
                       key=lambda r: (not r["collision_free"], r["worst_axis_ratio"],
                                      r["envelope_volume_m3"])) for robot in robots}
    baseline = {robot: next(r for r in rows if r["robot"] == robot and r["sample_index"] == 0)
                for robot in robots}
    table_path = output_dir.parent / "best_stowage_by_robot.csv"
    fields = ("robot", "candidate_id", "J2_J3_mm", "J3_J4_mm", "J4_J5_mm", "J5_J6_mm",
              "size_x_mm", "size_y_mm", "size_z_mm", "worst_axis_ratio", "rule_pass",
              "arm_size_x_mm", "arm_size_y_mm", "arm_size_z_mm", "clearance_mm",
              "task_best_candidate", "task_robust_fraction")
    with table_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        for robot in robots:
            row, task = best[robot], best[robot]["task_best"]
            task_score = _task_robust(task)
            writer.writerow({"robot": robot, "candidate_id": row["candidate_id"],
                             **{f"J{i}_J{i + 1}_mm": round(row["span_m"][str(i)] * 1000, 2)
                                for i in range(2, 6)},
                             **{f"size_{axis}_mm": round(row["dimensions_m"][i] * 1000, 2)
                                for i, axis in enumerate("xyz")},
                             "worst_axis_ratio": round(row["worst_axis_ratio"], 5),
                             "rule_pass": row["rule_pass"],
                             **{f"arm_size_{axis}_mm": round(row["arm_only_dimensions_m"][i] * 1000, 2)
                                for i, axis in enumerate("xyz")},
                             "clearance_mm": None if row["clearance_m"] is None else round(row["clearance_m"] * 1000, 3),
                             "task_best_candidate": None if task is None else task["candidate_id"],
                             "task_robust_fraction": None if task_score is None else round(task_score, 5)})

    if len(robots) > 12:
        plots = _render_many_robots(rows, robots, best, baseline, output_dir)
        return {"best_by_robot": {key: value["candidate_id"] for key, value in best.items()},
                "rule_pass_count": sum(row["rule_pass"] for row in rows),
                "plots": plots, "table": str(table_path)}

    x = np.arange(len(robots))
    width = 0.23
    fig, ax = plt.subplots(figsize=(12.6, 6.3), constrained_layout=True)
    for axis in range(3):
        values = [best[robot]["dimensions_m"][axis] * 1000 for robot in robots]
        bars = ax.bar(x + (axis - 1) * width, values, width, label="XYZ"[axis])
        ax.bar_label(bars, labels=[f"{v:.0f}" for v in values], padding=2, fontsize=8)
    ax.axhline(600, color="#c83e4d", linewidth=1.8, linestyle="--", label="规则上限 600 mm")
    ax.set_xticks(x, robots, rotation=25, ha="right")
    ax.set_ylabel("联合收纳包络 / mm")
    ax.set_title("每种构型在已测试臂长中的最小无碰撞收纳包络")
    ax.grid(axis="y", alpha=0.22)
    ax.legend(ncol=4)
    dimensions_plot = output_dir / "best_dimensions_by_robot.png"
    fig.savefig(dimensions_plot, dpi=180)
    plt.close(fig)

    plots = [str(dimensions_plot)]
    if any(row["task_best"] is not None for row in rows):
        fig, ax = plt.subplots(figsize=(10.8, 7.2), constrained_layout=True)
        colors = plt.colormaps["tab10"](np.arange(len(robots)))
        for index, robot in enumerate(robots):
            group = [row for row in rows if row["robot"] == robot and row["collision_free"]
                     and row["task_best"] is not None]
            ax.scatter([row["worst_axis_ratio"] * 600 for row in group],
                       [max(0.0, _task_robust(row["task_best"])) * 100 for row in group],
                       s=38, alpha=0.63, color=colors[index], label=robot)
            row = best[robot]
            if row["task_best"] is not None:
                ax.scatter([row["worst_axis_ratio"] * 600],
                           [max(0.0, _task_robust(row["task_best"])) * 100],
                           s=145, facecolors="none", edgecolors="black", linewidths=1.4)
        ax.axvline(600, color="#c83e4d", linewidth=1.8, linestyle="--")
        ax.set(xlabel="最紧张方向的收纳尺寸 / mm（越左越好）",
               ylabel="同臂长最佳泊位的三任务稳健通过率 / %（越上越好）",
               title="收纳与任务能力权衡；黑圈为每种构型最易收纳的臂长")
        ax.grid(alpha=0.22)
        ax.legend(ncol=2, fontsize=9)
        tradeoff_plot = output_dir / "stowage_task_tradeoff.png"
        fig.savefig(tradeoff_plot, dpi=180)
        plt.close(fig)
        plots.append(str(tradeoff_plot))

    fig, ax = plt.subplots(figsize=(11.5, 6.2), constrained_layout=True)
    base_values = [baseline[r]["worst_axis_ratio"] * 600 for r in robots]
    best_values = [best[r]["worst_axis_ratio"] * 600 for r in robots]
    ax.plot(x, base_values, "o-", label="产品/URDF 原始臂长", linewidth=1.8)
    ax.plot(x, best_values, "s-", label="测试臂长中的最小值", linewidth=1.8)
    ax.axhline(600, color="#c83e4d", linewidth=1.8, linestyle="--", label="规则上限")
    ax.set_xticks(x, robots, rotation=25, ha="right")
    ax.set_ylabel("最紧张方向的收纳尺寸 / mm")
    ax.set_title("原始臂长与臂长搜索后可达到的收纳尺寸")
    ax.grid(alpha=0.22)
    ax.legend()
    comparison_plot = output_dir / "baseline_vs_best.png"
    fig.savefig(comparison_plot, dpi=180)
    plt.close(fig)
    plots.append(str(comparison_plot))
    return {"best_by_robot": {key: value["candidate_id"] for key, value in best.items()},
            "rule_pass_count": sum(row["rule_pass"] for row in rows),
            "plots": plots,
            "table": str(table_path)}
