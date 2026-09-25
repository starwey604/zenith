"""Readable three-task plots and rankings for the four-span six-axis sweep."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


plt.rcParams["font.family"] = "Noto Sans CJK SC"
plt.rcParams["axes.unicode_minus"] = False


def task_fractions(row: dict) -> tuple[float, float, float]:
    return (row["storage_balanced_fraction"], row["pickup_complete"] / 72,
            row["module_stress_complete"] / row["module_stress_total"])


def robust_fraction(row: dict) -> float:
    """Best worst-category completion, with basic module docking as a gate."""
    return min(task_fractions(row)) if row["module_complete"] else -1.0


def pareto_3d(rows: list[dict]) -> set[str]:
    feasible = [row for row in rows if row["module_complete"]]
    frontier = set()
    for row in feasible:
        score = task_fractions(row)
        if not any((all(a >= b for a, b in zip(task_fractions(other), score))
                    and any(a > b for a, b in zip(task_fractions(other), score)))
                   for other in feasible):
            frontier.add(row["candidate_id"])
    return frontier


def _render_many_robots(rows: list[dict], best_rows: list[dict],
                        frontier: set[str], output_dir: Path) -> tuple[Path, Path]:
    """Keep a large generated-topology catalog readable without a 134-item legend."""
    metrics = (("一至三级存矿均衡通过率", 0),
               ("取矿越过边沿通过率", 1))
    fig, axes = plt.subplots(1, 3, figsize=(19, 8), constrained_layout=True)
    for ax, (title, metric_index) in zip(axes[:2], metrics):
        top = sorted(best_rows, key=lambda row: task_fractions(row)[metric_index],
                     reverse=True)[:18]
        values = [task_fractions(row)[metric_index] * 100 for row in reversed(top)]
        names = [row["robot"].removeprefix("orth6r_") for row in reversed(top)]
        ax.barh(names, values, color="#31788f")
        ax.set(xlim=(0, 100), xlabel="通过率 %", title=title)
        ax.grid(axis="x", alpha=0.2)
    module_counts = np.bincount([row["module_stress_complete"] for row in best_rows],
                                minlength=10)
    axes[2].bar(range(10), module_counts, color="#31788f")
    axes[2].set(xticks=range(10), xlabel="通过的装配位姿数 / 9", ylabel="构型数",
                title="英雄头装配：各构型最佳泊位的通过数")
    axes[2].grid(axis="y", alpha=0.2)
    fig.suptitle("每个构型取四个泊位中的最佳值；左两图显示各任务前18名")
    overview = output_dir / "configuration_overview.png"
    fig.savefig(overview, dpi=170)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10.7, 7.3), constrained_layout=True)
    fractions = np.asarray([task_fractions(row) for row in rows]) * 100
    artist = ax.scatter(fractions[:, 1], fractions[:, 0], c=fractions[:, 2],
                        cmap="viridis", vmin=0, vmax=100, s=40, alpha=0.75)
    for row, (storage, pickup, _) in zip(rows, fractions):
        if row["candidate_id"] in frontier:
            ax.scatter([pickup], [storage], s=130, facecolors="none",
                       edgecolors="black", linewidths=1.4)
    ranked = sorted(rows, key=lambda row: (robust_fraction(row), sum(task_fractions(row))),
                    reverse=True)
    annotated = set()
    for row in ranked:
        if row["robot"] in annotated:
            continue
        annotated.add(row["robot"])
        storage, pickup, _ = task_fractions(row)
        ax.annotate(row["robot"].removeprefix("orth6r_"),
                    (pickup * 100, storage * 100), xytext=(4, 4),
                    textcoords="offset points", fontsize=8)
        if len(annotated) >= 8:
            break
    fig.colorbar(artist, ax=ax, label="9个位姿装配通过率 %")
    ax.set(xlabel="取矿通过率 %", ylabel="存矿均衡通过率 %",
           xlim=(-2, 102), ylim=(-2, 102),
           title="六轴构型与底盘泊位：黑圈是三任务 Pareto 候选")
    ax.grid(alpha=0.24)
    tradeoff = output_dir / "three_task_tradeoff.png"
    fig.savefig(tradeoff, dpi=175)
    plt.close(fig)
    return overview, tradeoff


def render(summary_path: Path, output_dir: Path) -> dict:
    report = json.loads(summary_path.read_text(encoding="utf-8"))
    rows = report["rows"]
    if not rows or report["complete_candidate_count"] != report["candidate_count"] or report["errors"]:
        raise ValueError("cannot plot incomplete sweep")
    output_dir.mkdir(parents=True, exist_ok=True)
    robots = report["spec"]["robots"]
    frontier = pareto_3d(rows)
    best_rows = []
    for robot in robots:
        group = [r for r in rows if r["robot"] == robot]
        best = max(group, key=lambda r:(robust_fraction(r),
                                        r["storage_balanced_fraction"],
                                        r["pickup_complete"],
                                        r["module_stress_complete"]))
        best_rows.append(best)
    with (output_dir.parent / "best_by_robot.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ("robot", "candidate_id", "parking_id", "J2_J3_mm", "J3_J4_mm",
                  "J4_J5_mm", "J5_J6_mm", "tier1", "tier2", "tier3", "pickup",
                  "module_basic", "module_stress", "module_min_clearance_mm",
                  "module_min_joint_margin_rad", "robust_fraction")
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for r in best_rows:
            writer.writerow({"robot": r["robot"], "candidate_id": r["candidate_id"],
                             "parking_id": r["parking_id"],
                             **{fields[i + 1]: round(r["span_m"][str(i)] * 1000, 2)
                                for i in range(2, 6)},
                             "tier1": f"{r['tier1_complete']}/15",
                             "tier2": f"{r['tier2_complete']}/25",
                             "tier3": f"{r['tier3_complete']}/27",
                             "pickup": f"{r['pickup_complete']}/72",
                             "module_basic": r["module_complete"],
                             "module_stress": f"{r['module_stress_complete']}/9",
                             "module_min_clearance_mm": (None if r["module_stress_min_clearance_m"] is None
                                                           else round(r["module_stress_min_clearance_m"] * 1000, 2)),
                             "module_min_joint_margin_rad": r["module_stress_min_joint_margin_rad"],
                             "robust_fraction": round(robust_fraction(r), 4)})
    with (output_dir.parent / "pareto_3tasks.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ("candidate_id", "robot", "parking_id", "storage_fraction", "pickup_fraction",
                  "module_fraction", "J2_J3_mm", "J3_J4_mm", "J4_J5_mm", "J5_J6_mm")
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            if r["candidate_id"] in frontier:
                st, pk, md = task_fractions(r)
                writer.writerow({"candidate_id": r["candidate_id"], "robot": r["robot"],
                                 "parking_id": r["parking_id"], "storage_fraction": st,
                                 "pickup_fraction": pk, "module_fraction": md,
                                 **{fields[i + 4]: round(r["span_m"][str(i)] * 1000, 2)
                                    for i in range(2, 6)}})

    if len(robots) > 12:
        overview, tradeoff = _render_many_robots(rows, best_rows, frontier, output_dir)
        return {"plots": [str(overview), str(tradeoff)],
                "pareto_candidate_count": len(frontier),
                "best_by_robot": [r["candidate_id"] for r in best_rows]}

    metrics = [("一至三级存矿（均衡通过率）", 0),
               ("取矿越过边沿（72项）", 1),
               ("英雄头装配（9个位姿）", 2)]
    fig, axes = plt.subplots(1, 3, figsize=(16.5, 5.4), constrained_layout=True)
    colors = plt.colormaps["tab10"](np.arange(len(robots)))
    for ax, (title, metric_idx) in zip(axes, metrics):
        for i, robot in enumerate(robots):
            group = [r for r in rows if r["robot"] == robot]
            vals = np.array([task_fractions(r)[metric_idx] * 100 for r in group])
            offsets = np.linspace(-0.22, 0.22, len(vals))
            ax.scatter(np.full(len(vals), i) + offsets, vals,
                       color=colors[i], s=16, alpha=0.33, linewidths=0)
            ax.scatter([i], [vals.max()], color=colors[i], s=90, edgecolor="black", zorder=3)
            ax.text(i, min(98, vals.max() + 2), f"{vals.max():.0f}%", ha="center", fontsize=9)
        ax.set_xticks(range(len(robots)), robots, rotation=35, ha="right")
        ax.set_ylim(-3, 105)
        ax.set_ylabel("通过率 %")
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("同一套固定合成任务：每个点是一组连杆长度与底盘停位；黑边点是该构型最高值")
    overview = output_dir / "configuration_overview.png"
    fig.savefig(overview, dpi=170)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10.7, 7.3), constrained_layout=True)
    cmap = plt.colormaps["viridis"]
    for i, robot in enumerate(robots):
        group = [r for r in rows if r["robot"] == robot]
        x = [task_fractions(r)[1] * 100 for r in group]
        y = [task_fractions(r)[0] * 100 for r in group]
        c = [task_fractions(r)[2] * 100 for r in group]
        artist = ax.scatter(x, y, c=c, cmap=cmap, vmin=0, vmax=100,
                            marker=["o", "s", "^", "D", "P", "v", "X"][i],
                            s=55, alpha=0.72, edgecolors="none", label=robot)
    for r in rows:
        if r["candidate_id"] in frontier:
            st, pk, _ = task_fractions(r)
            ax.scatter([pk * 100], [st * 100], s=170, facecolors="none",
                       edgecolors="black", linewidths=1.5)
    fig.colorbar(artist, ax=ax, label="9个位姿装配通过率 %")
    ax.set(xlabel="取矿通过率 %（越右越好）", ylabel="存矿均衡通过率 %（越上越好）",
           xlim=(-2, 102), ylim=(-2, 102),
           title="三任务权衡：颜色表示装配；黑圈是基础装配通过后的三指标 Pareto 候选")
    ax.grid(alpha=0.24)
    ax.legend(loc="lower left", ncol=2)
    tradeoff = output_dir / "three_task_tradeoff.png"
    fig.savefig(tradeoff, dpi=175)
    plt.close(fig)
    return {"plots": [str(overview), str(tradeoff)],
            "pareto_candidate_count": len(frontier),
            "best_by_robot": [r["candidate_id"] for r in best_rows]}
