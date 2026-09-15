"""Generate a fixed tier-1..3 storage pressure set within 2026 rule ranges."""
from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np


NAMES = ("x", "y", "z", "theta", "phi", "alpha")
BOUNDS = np.array([[-0.1, 0.0], [0.1, 0.3], [0.5, 0.7],
                   [-np.pi / 2, np.pi / 2], [0.0, np.pi / 2],
                   [-np.pi / 4, np.pi / 4]], dtype=float)
Q_LIMIT = np.pi / 2


def _stratified_unit_cube(rng: np.random.Generator, count: int, dimension: int) -> np.ndarray:
    """Independent column permutations with a jitter inside each stratum."""
    if count < 1 or dimension < 1:
        raise ValueError("stratified sample count and dimension must be positive")
    columns = [(rng.permutation(count) + rng.random(count)) / count for _ in range(dimension)]
    return np.column_stack(columns)


def _sample(sample_id: str, tier: int, coordinates: np.ndarray,
            sample_class: str, q_target: float | None = None) -> dict:
    vector = np.asarray(coordinates, dtype=float)
    if vector.shape != (6,) or not np.isfinite(vector).all():
        raise ValueError("storage pressure sample needs six finite coordinates")
    return {"sample_id": sample_id, "sample_class": sample_class,
            "tier": tier, "xyz_m": vector[:3].tolist(),
            "theta_rad": float(vector[3]), "phi_rad": float(vector[4]),
            "alpha_rad": float(vector[5]),
            "q_target_signed_rad": None if q_target is None else float(q_target)}


def build_pressure_samples(seed: int, tier1_interior_count: int = 6,
                           pose_interior_count: int = 12) -> list[dict]:
    """15 tier-1, 25 tier-2 and 27 tier-3 fixed samples by default."""
    if (isinstance(seed, bool) or not isinstance(seed, int) or seed < 0
            or tier1_interior_count < 1 or pose_interior_count < 1):
        raise ValueError("pressure seed must be a nonnegative integer and counts positive")
    rng = np.random.default_rng(seed)
    centre = BOUNDS.mean(axis=1)
    first_orientation = np.array([0.0, np.pi / 2, 0.0])
    tier1 = []
    tier1.append(_sample("stress_t1_center", 1, np.r_[centre[:3], first_orientation], "centre"))
    for bits in itertools.product((0, 1), repeat=3):
        xyz = np.array([BOUNDS[index, bit] for index, bit in enumerate(bits)])
        tier1.append(_sample("stress_t1_corner_" + "".join(map(str, bits)), 1,
                             np.r_[xyz, first_orientation], "xyz_corner"))
    interior1 = _stratified_unit_cube(rng, tier1_interior_count, 3)
    for index, unit in enumerate(interior1):
        xyz = BOUNDS[:3, 0] + unit * (BOUNDS[:3, 1] - BOUNDS[:3, 0])
        tier1.append(_sample(f"stress_t1_interior_{index:02d}", 1,
                             np.r_[xyz, first_orientation], "stratified_interior"))

    poses: list[tuple[str, np.ndarray, str]] = [("centre", centre, "centre")]
    for axis, name in enumerate(NAMES):
        for side, label in ((0, "min"), (1, "max")):
            vector = centre.copy()
            vector[axis] = BOUNDS[axis, side]
            poses.append((f"{name}_{label}", vector, "axis_boundary"))
    interior2 = _stratified_unit_cube(rng, pose_interior_count, 6)
    for index, unit in enumerate(interior2):
        vector = BOUNDS[:, 0] + unit * (BOUNDS[:, 1] - BOUNDS[:, 0])
        poses.append((f"interior_{index:02d}", vector, "stratified_interior"))

    tier2 = [_sample(f"stress_t2_{name}", 2, vector, sample_class)
             for name, vector, sample_class in poses]
    q_cycle = (0.0, -Q_LIMIT, Q_LIMIT)
    tier3 = [_sample(f"stress_t3_{name}", 3, vector, sample_class, q_cycle[index % 3])
             for index, (name, vector, sample_class) in enumerate(poses)]
    tier3.extend((_sample("stress_t3_centre_q_min", 3, centre, "q_boundary", -Q_LIMIT),
                  _sample("stress_t3_centre_q_max", 3, centre, "q_boundary", Q_LIMIT)))
    return [*tier1, *tier2, *tier3]


def build_pressure_task(base_task_path: Path, seed: int = 20260916) -> dict:
    base_raw = base_task_path.read_bytes()
    task = copy.deepcopy(json.loads(base_raw))
    if task.get("schema_version") != 1 or task.get("source_type") != "design_assumption":
        raise ValueError("pressure generator needs a version-1 design-assumption base task")
    task["scenario_id"] = "storage_2026_tiers_1_to_3_pressure_v1"
    task["samples"] = build_pressure_samples(seed)
    task["pressure_sampling"] = {"generator": "storage_stress.py:v1",
                                  "seed": seed,
                                  "base_task_sha256": hashlib.sha256(base_raw).hexdigest(),
                                  "tier1_xyz_corners": 8,
                                  "tier1_interior": 6,
                                  "tier2_tier3_shared_pose_count": 25,
                                  "tier2_tier3_pose_interior": 12,
                                  "tier3_extra_q_boundaries": 2,
                                  "rule_range_order": list(NAMES),
                                  "rule_ranges_si": BOUNDS.tolist()}
    task["notes"] = ("一级15项、二级25项、三级27项固定合成压力样本；含范围边界与固定种子分层内部样本。"
                     "二、三级共用25个核心姿态，三级另有两个中心位姿Q轴端点样本。"
                     "目标数值落在2026一至三级单核心范围内，但核心安装位姿、姿态约定、P/Q轴偏置、"
                     "碰撞盒和抓手仍是设计假设。四级完全排除。")
    return task


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-task", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260916)
    args = parser.parse_args()
    task = build_pressure_task(args.base_task, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(task, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                           encoding="utf-8")
    counts = {str(tier): sum(sample["tier"] == tier for sample in task["samples"])
              for tier in (1, 2, 3)}
    print(json.dumps({"output": str(args.output), "sample_count": len(task["samples"]),
                      "tier_counts": counts, "seed": args.seed}, ensure_ascii=False))


if __name__ == "__main__":
    main()
