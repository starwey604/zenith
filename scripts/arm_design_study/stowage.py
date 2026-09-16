"""Minimum stowed-envelope search for one six-axis arm design hypothesis."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import numpy as np
from scipy.optimize import minimize
from scipy.stats import qmc

from .chassis import ChassisMount
from .collision import Box, Capsule, chassis_box, collision_scan, robot_capsules
from .frames import transform
from .length_design import scale_anchor_spans
from .model_import import load_local


@dataclass(frozen=True)
class StowageGeometry:
    dimensions_m: np.ndarray
    lower_m: np.ndarray
    upper_m: np.ndarray
    arm_dimensions_m: np.ndarray
    arm_lower_m: np.ndarray
    arm_upper_m: np.ndarray
    bound_sources: dict[str, list[str]]
    clearance_m: float
    collision: dict | None


def geometry_aabb(chassis: Box, capsules: list[Capsule]) -> tuple[np.ndarray, np.ndarray]:
    """Axis-aligned chassis-frame bounds of the coarse complete robot geometry."""
    if not capsules:
        raise ValueError("at least one arm capsule is required")
    rotation = chassis.pose[:3, :3]
    chassis_half = np.abs(rotation) @ chassis.half_m
    lows = [chassis.pose[:3, 3] - chassis_half]
    highs = [chassis.pose[:3, 3] + chassis_half]
    for capsule in capsules:
        endpoints = np.vstack((capsule.start, capsule.end))
        lows.append(endpoints.min(axis=0) - capsule.radius_m)
        highs.append(endpoints.max(axis=0) + capsule.radius_m)
    return np.min(lows, axis=0), np.max(highs, axis=0)


def evaluate_stowage(arm, q: np.ndarray, scene: dict) -> StowageGeometry:
    """Evaluate one fixed-base stow pose in robot body coordinates."""
    mount = ChassisMount(0.0, 0.0, 0.0,
                         transform(translation=np.asarray(
                             scene["chassis"]["arm_mount_translation_m"], dtype=float)))
    half = np.asarray(scene["chassis"]["half_extents_m"], dtype=float)
    chassis = chassis_box(mount, half)
    base_name = arm.name.split("[")[0]
    geometry = scene["geometry"]
    capsules = robot_capsules(
        arm, mount, np.asarray(q, dtype=float),
        np.asarray(geometry["link_capsule_radii_by_robot_m"][base_name], dtype=float),
        float(geometry["tool_radius_m"]), float(geometry["tool_length_m"]),
        np.asarray(geometry.get("tool_axis_in_flange", [0.0, 0.0, -1.0]), dtype=float))
    lower, upper = geometry_aabb(chassis, capsules)
    capsule_lows = np.vstack([np.minimum(c.start, c.end) - c.radius_m for c in capsules])
    capsule_highs = np.vstack([np.maximum(c.start, c.end) + c.radius_m for c in capsules])
    arm_lower, arm_upper = capsule_lows.min(axis=0), capsule_highs.max(axis=0)
    chassis_lower = chassis.pose[:3, 3] - np.abs(chassis.pose[:3, :3]) @ chassis.half_m
    chassis_upper = chassis.pose[:3, 3] + np.abs(chassis.pose[:3, :3]) @ chassis.half_m
    names = [capsule.name for capsule in capsules] + ["chassis"]
    all_lows = np.vstack((capsule_lows, chassis_lower))
    all_highs = np.vstack((capsule_highs, chassis_upper))
    tolerance = 1e-8
    sources = {}
    for index, axis in enumerate("xyz"):
        sources[f"{axis}_lower"] = [name for name, value in zip(names, all_lows[:, index])
                                     if abs(value - lower[index]) <= tolerance]
        sources[f"{axis}_upper"] = [name for name, value in zip(names, all_highs[:, index])
                                     if abs(value - upper[index]) <= tolerance]
    clearance, collision = collision_scan(capsules, chassis, [], "stowage", set())
    return StowageGeometry(upper - lower, lower, upper, arm_upper - arm_lower,
                           arm_lower, arm_upper, sources, float(clearance), collision)


def periodic_search_limits(limits: np.ndarray) -> np.ndarray:
    """Use one full geometric revolution where authored limits span multiple turns."""
    limits = np.asarray(limits, dtype=float).copy()
    if limits.shape != (6, 2):
        raise ValueError("six joint-limit pairs required")
    for index, (lower, upper) in enumerate(limits):
        if upper - lower > 2 * np.pi:
            centre = float(np.clip(0.0, lower + np.pi, upper - np.pi))
            limits[index] = [centre - np.pi, centre + np.pi]
    return limits


def _stable_seed(base_seed: int, candidate_id: str) -> int:
    digest = hashlib.sha256(candidate_id.encode()).digest()
    return (base_seed + int.from_bytes(digest[:4], "little")) % (2**32)


def search_minimum_stowage(candidate: dict, scene: dict, rule_limit_m: np.ndarray,
                           minimum_clearance_m: float, search: dict) -> dict:
    """Deterministic Sobol search followed by bounded Powell refinements."""
    rule = np.asarray(rule_limit_m, dtype=float)
    if rule.shape != (3,) or np.any(rule <= 0):
        raise ValueError("rule limit must be a positive three-vector")
    base = load_local(candidate["robot"])
    scales = {int(key): float(value) for key, value in candidate["anchor_span_scales"].items()}
    arm = scale_anchor_spans(base, scales) if scales else base
    bounds = periodic_search_limits(arm.limits)
    count = int(search["sobol_sample_count"])
    if count < 2 or count & (count - 1):
        raise ValueError("Sobol sample count must be a power of two")
    seed = _stable_seed(int(search["seed"]), candidate["candidate_id"])
    unit = qmc.Sobol(d=6, scramble=True, seed=seed).random_base2(m=count.bit_length() - 1)
    samples = qmc.scale(unit, bounds[:, 0], bounds[:, 1])
    samples = np.vstack((samples, np.clip(np.zeros(6), bounds[:, 0], bounds[:, 1]),
                         bounds.mean(axis=1)))
    evaluations = 0
    cache: dict[tuple[float, ...], tuple[float, StowageGeometry]] = {}

    def assess(q: np.ndarray) -> tuple[float, StowageGeometry]:
        nonlocal evaluations
        clipped = np.clip(np.asarray(q, dtype=float), bounds[:, 0], bounds[:, 1])
        key = tuple(np.round(clipped, 11))
        if key in cache:
            return cache[key]
        result = evaluate_stowage(arm, clipped, scene)
        normalized = result.dimensions_m / rule
        compact = float(np.max(normalized) + 0.01 * np.mean(normalized))
        deficit = max(0.0, minimum_clearance_m - result.clearance_m)
        # The fixed jump prevents a colliding but tiny pose from outranking any valid pose.
        score = compact + (10.0 + 1000.0 * deficit if deficit > 0 else 0.0)
        cache[key] = (score, result)
        evaluations += 1
        return cache[key]

    initial = [(assess(q)[0], q.copy(), assess(q)[1]) for q in samples]
    valid = [item for item in initial if item[2].clearance_m >= minimum_clearance_m]
    ranked = sorted(valid if valid else initial, key=lambda item: item[0])
    starts = ranked[:int(search["local_start_count"])]
    trials = list(initial)
    scipy_bounds = [tuple(pair) for pair in bounds]
    for _, start, _ in starts:
        solution = minimize(lambda q: assess(q)[0], start, method="Powell", bounds=scipy_bounds,
                            options={"maxiter": int(search["local_max_iterations"]),
                                     "xtol": 2e-5, "ftol": 2e-6})
        score, geometry = assess(solution.x)
        trials.append((score, np.clip(solution.x, bounds[:, 0], bounds[:, 1]), geometry))
    valid_trials = [item for item in trials if item[2].clearance_m >= minimum_clearance_m]
    pool = valid_trials if valid_trials else trials
    best_score, best_q, best = min(pool, key=lambda item: item[0])
    normalized = best.dimensions_m / rule
    margin = rule - best.dimensions_m
    return {
        "candidate_id": candidate["candidate_id"], "robot": candidate["robot"],
        "sample_index": candidate["sample_index"],
        "sampling_kind": candidate.get("sampling_kind"),
        "active_span_indices": candidate["active_span_indices"],
        "anchor_span_scales": candidate["anchor_span_scales"], "span_m": candidate["span_m"],
        "q_rad": best_q.tolist(), "search_joint_limits_rad": bounds.tolist(),
        "dimensions_m": best.dimensions_m.tolist(), "lower_m": best.lower_m.tolist(),
        "upper_m": best.upper_m.tolist(), "rule_limit_m": rule.tolist(),
        "arm_only_dimensions_m": best.arm_dimensions_m.tolist(),
        "arm_only_lower_m": best.arm_lower_m.tolist(), "arm_only_upper_m": best.arm_upper_m.tolist(),
        "bound_sources": best.bound_sources,
        "rule_margin_m": margin.tolist(), "worst_axis_ratio": float(np.max(normalized)),
        "envelope_volume_m3": float(np.prod(best.dimensions_m)),
        "minimum_clearance_m": minimum_clearance_m,
        "clearance_m": best.clearance_m if math.isfinite(best.clearance_m) else None,
        "collision": best.collision, "collision_free": best.clearance_m >= minimum_clearance_m,
        "rule_pass": bool(best.clearance_m >= minimum_clearance_m and np.all(margin >= 0)),
        "objective": float(best_score), "evaluations": evaluations,
        "initial_valid_count": len(valid), "task_best": candidate["task_best"],
    }
