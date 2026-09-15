"""Plot comparable full-task length-sweep geometry results."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def pareto_2d(rows: list[dict]) -> set[str]:
    """Module-feasible nondominated candidates in storage/pickup completion."""
    feasible = [row for row in rows if row["module_complete"]]
    frontier = set()
    for row in feasible:
        sx = row["storage_balanced_fraction"]
        px = row["pickup_complete"] / row["pickup_total"]
        dominated = any((other["storage_balanced_fraction"] >= sx
                         and other["pickup_complete"] / other["pickup_total"] >= px
                         and (other["storage_balanced_fraction"] > sx
                              or other["pickup_complete"] / other["pickup_total"] > px))
                        for other in feasible)
        if not dominated:
            frontier.add(row["candidate_id"])
    return frontier


def render(summary_path: Path, output_dir: Path) -> list[Path]:
    report = json.loads(summary_path.read_text(encoding="utf-8"))
    rows = report["rows"]
    if not rows:
        raise ValueError("cannot plot an empty sweep")
    output_dir.mkdir(parents=True, exist_ok=True)
    factors = sorted({float(row["factor2"]) for row in rows}
                     | {float(row["factor3"]) for row in rows})
    robots = list(report["spec"]["robots"]) if "spec" in report else list(
        dict.fromkeys(row["robot"] for row in rows))
    parking = list(report["spec"]["parking_ids"]) if "spec" in report else list(
        dict.fromkeys(row["parking_id"] for row in rows))
    metrics = (("Tier 3 storage", lambda row: row["tier3_complete"] / row["tier3_total"]),
               ("Balanced storage", lambda row: row["storage_balanced_fraction"]),
               ("Ore exit", lambda row: row["pickup_complete"] / row["pickup_total"]))
    lookup = {(row["robot"], row["parking_id"], float(row["factor2"]),
               float(row["factor3"])): row for row in rows}
    fig, axes = plt.subplots(len(robots) * len(parking), len(metrics),
                             figsize=(13.5, 3.25 * len(robots) * len(parking)),
                             squeeze=False, constrained_layout=True)
    cmap = plt.colormaps["viridis"].copy()
    cmap.set_bad("#e3e5e8")
    for row_index, (robot, park) in enumerate((robot, park)
                                               for robot in robots for park in parking):
        for column, (title, metric) in enumerate(metrics):
            grid = np.full((len(factors), len(factors)), np.nan)
            for y, factor3 in enumerate(factors):
                for x, factor2 in enumerate(factors):
                    item = lookup.get((robot, park, factor2, factor3))
                    if item is not None:
                        grid[y, x] = metric(item)
            ax = axes[row_index, column]
            im = ax.imshow(grid, origin="lower", vmin=0, vmax=1, cmap=cmap)
            for y in range(len(factors)):
                for x in range(len(factors)):
                    if np.isfinite(grid[y, x]):
                        ax.text(x, y, f"{grid[y, x] * 100:.0f}", ha="center", va="center",
                                fontsize=8, color="white" if grid[y, x] < 0.7 else "black")
            ax.set_xticks(range(len(factors)), [f"{factor:.2f}" for factor in factors])
            ax.set_yticks(range(len(factors)), [f"{factor:.2f}" for factor in factors])
            ax.set_xlabel("span 2 / reference")
            ax.set_ylabel("span 3 / reference")
            ax.set_title(f"{robot} · {park} · {title}")
    fig.colorbar(im, ax=axes, shrink=0.55, label="sampled geometry completion fraction")
    heatmap = output_dir / "length_heatmaps.png"
    fig.savefig(heatmap, dpi=170)
    plt.close(fig)

    frontier = pareto_2d(rows)
    fig, ax = plt.subplots(figsize=(10.5, 7), constrained_layout=True)
    for robot in robots:
        for park in parking:
            group = [row for row in rows if row["robot"] == robot and row["parking_id"] == park]
            if not group:
                continue
            x = [row["pickup_complete"] / row["pickup_total"] for row in group]
            y = [row["storage_balanced_fraction"] for row in group]
            colors = [(row["span2_m"] + row["span3_m"]) * 1000 for row in group]
            artist = ax.scatter(x, y, c=colors, cmap="plasma", vmin=450, vmax=1100,
                                s=90, marker="o" if park == parking[0] else "s",
                                edgecolors="black" if robot == robots[0] else "white",
                                linewidths=0.7, alpha=0.88, label=f"{robot} · {park}")
    for row in rows:
        if row["candidate_id"] in frontier:
            x = row["pickup_complete"] / row["pickup_total"]
            y = row["storage_balanced_fraction"]
            ax.scatter([x], [y], facecolors="none", edgecolors="black", s=240, linewidths=1.6)
    fig.colorbar(artist, ax=ax, label="span 2 + span 3 (mm); zero-pose anchor proxy")
    ax.set_xlabel("Ore-exit completion fraction (72 common cases)")
    ax.set_ylabel("Balanced tier-1..3 storage completion fraction (67 common cases)")
    ax.set_xlim(0, 1.03)
    ax.set_ylim(0, 1.03)
    ax.grid(alpha=0.25)
    ax.legend(loc="lower left")
    ax.set_title("Full-task candidates; circles around module-feasible 2D Pareto front")
    pareto = output_dir / "storage_pickup_pareto.png"
    fig.savefig(pareto, dpi=180)
    plt.close(fig)
    return [heatmap, pareto]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps({"plots": [str(path) for path in render(args.summary, args.output_dir)]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
