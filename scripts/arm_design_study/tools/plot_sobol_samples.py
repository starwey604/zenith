"""Show irregular Sobol length samples as colored points, without grid interpolation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def render(summary_path: Path, output_path: Path) -> None:
    rows = json.loads(summary_path.read_text(encoding="utf-8"))["rows"]
    robots = list(dict.fromkeys(row["robot"] for row in rows))
    parking = list(dict.fromkeys(row["parking_id"] for row in rows))
    metrics = (("Tier 3 storage", lambda row: row["tier3_complete"] / row["tier3_total"]),
               ("Balanced storage", lambda row: row["storage_balanced_fraction"]),
               ("Ore exit", lambda row: row["pickup_complete"] / row["pickup_total"]))
    fig, axes = plt.subplots(len(robots) * len(parking), len(metrics),
                             figsize=(13.5, 3.1 * len(robots) * len(parking)),
                             squeeze=False, constrained_layout=True)
    artist = None
    for row_index, (robot, park) in enumerate((robot, park)
                                               for robot in robots for park in parking):
        group = [row for row in rows if row["robot"] == robot and row["parking_id"] == park]
        for column, (title, metric) in enumerate(metrics):
            ax = axes[row_index, column]
            artist = ax.scatter([row["factor2"] for row in group],
                                [row["factor3"] for row in group],
                                c=[metric(row) for row in group], cmap="viridis",
                                vmin=0, vmax=1, s=90, edgecolors="black", linewidths=0.6)
            baseline = [row for row in group if row["factor2"] == row["factor3"] == 1.0]
            if baseline:
                ax.scatter([1.0], [1.0], marker="*", facecolors="none",
                           edgecolors="red", s=360, linewidths=1.5)
            ax.set_xlim(0.73, 1.27)
            ax.set_ylim(0.73, 1.27)
            ax.set_xticks([0.75, 0.85, 0.95, 1.05, 1.15, 1.25])
            ax.set_yticks([0.75, 0.85, 0.95, 1.05, 1.15, 1.25])
            ax.set_xlabel("span 2 / reference")
            ax.set_ylabel("span 3 / reference")
            ax.grid(alpha=0.2)
            ax.set_title(f"{robot} · {park} · {title}")
    fig.colorbar(artist, ax=axes, shrink=0.58, label="sampled geometry completion fraction")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    render(args.summary, args.output)
    print(json.dumps({"plot": str(args.output)}))


if __name__ == "__main__":
    main()
