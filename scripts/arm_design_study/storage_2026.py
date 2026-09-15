"""One-core RoboMaster 2026 energy-unit storage geometry, tiers 1–3 only."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from .benchmark import _rigid_pose, _screen_one
from .chassis import ChassisMount
from .collision import Box
from .frames import transform
from .length_design import scale_anchor_spans
from .model_import import load_local, XARM_XML, UR5E_XML, UR5E_CLASSES
from .task_2026 import TaskWaypoint, core_assembly_path


ZENITH = Path(__file__).resolve().parents[2]
ARM_OPT_TRAJECTORY = ZENITH.parent / "arm_opt" / "traj_disp.py"
RULE_2026 = ZENITH / "references" / "RoboMaster 2026 机甲大师超级对抗赛比赛规则手册V2.2.0（20260807）.pdf"


def arm_opt_preinsert_pose(station_world_pose: np.ndarray, xyz_m: np.ndarray,
                           theta_rad: float, phi_rad: float, alpha_rad: float) -> np.ndarray:
    """T1 = T_W_A * [Rz(theta) Ry(phi) Rz(alpha), xyz], as in arm_opt."""
    station = _rigid_pose(station_world_pose, "station_world_pose")
    xyz = np.asarray(xyz_m, dtype=float)
    angles = np.asarray([theta_rad, phi_rad, alpha_rad], dtype=float)
    if xyz.shape != (3,) or not np.isfinite(np.r_[xyz, angles]).all():
        raise ValueError("storage xyz and pose angles must be finite")
    rotation = (Rotation.from_euler("z", theta_rad).as_matrix()
                @ Rotation.from_euler("y", phi_rad).as_matrix()
                @ Rotation.from_euler("z", alpha_rad).as_matrix())
    return station @ transform(rotation=rotation, translation=xyz)


def arm_opt_pq_axes(preinsert_world_tool: np.ndarray, p_offset_m: float,
                    q_offset_m: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Axis points/lines from arm_opt T2, with explicit design offsets."""
    first = _rigid_pose(preinsert_world_tool, "preinsert_world_tool")
    if (not np.isfinite([p_offset_m, q_offset_m]).all()
            or p_offset_m <= 0 or q_offset_m <= 0):
        raise ValueError("P/Q origin offsets must be finite positive metres")
    after_insert = first @ transform(translation=[-0.1, 0.0, 0.0])
    p_origin = after_insert[:3, 3] + after_insert[:3, 2] * p_offset_m
    q_origin = after_insert[:3, 3] + after_insert[:3, 2] * q_offset_m
    return p_origin, after_insert[:3, 1], q_origin, after_insert[:3, 0]


def storage_path(tier: int, preinsert_world_tool: np.ndarray,
                 samples_per_phase: int, p_offset_m: float | None = None,
                 q_offset_m: float | None = None,
                 q_target_signed_rad: float | None = None,
                 p_axis_origin_world=None, p_axis_world=None,
                 q_axis_origin_world=None, q_axis_world=None) -> list[TaskWaypoint]:
    """Tier 1: insert; tier 2: insert/rise; tier 3: insert/rise/P/Q."""
    if tier not in (1, 2, 3):
        raise ValueError("storage supports only RoboMaster difficulty tiers 1, 2 and 3")
    if samples_per_phase < 2:
        raise ValueError("storage needs at least two samples per phase")
    first = _rigid_pose(preinsert_world_tool, "preinsert_world_tool")
    if tier == 3:
        if q_target_signed_rad is None:
            raise ValueError("tier 3 needs a Q target")
        explicit = (p_axis_origin_world, p_axis_world, q_axis_origin_world, q_axis_world)
        if all(value is not None for value in explicit):
            p_origin, p_axis, q_origin, q_axis = (np.asarray(value, dtype=float) for value in explicit)
        elif any(value is not None for value in explicit):
            raise ValueError("tier 3 explicit P/Q axes require all four origin/vector fields")
        else:
            if p_offset_m is None or q_offset_m is None:
                raise ValueError("tier 3 needs explicit P/Q axes or arm_opt offsets")
            p_origin, p_axis, q_origin, q_axis = arm_opt_pq_axes(first, p_offset_m, q_offset_m)
        return core_assembly_path(first, p_origin, p_axis, q_origin, q_axis,
                                  -np.pi / 2, float(q_target_signed_rad), samples_per_phase)
    path = []
    for progress in np.linspace(0.0, 1.0, samples_per_phase):
        path.append(TaskWaypoint("insert_minus_x",
                                 first @ transform(translation=[-0.1 * float(progress), 0, 0]),
                                 float(progress)))
    if tier == 2:
        after_insert = path[-1].world_tool
        for progress in np.linspace(0.0, 1.0, samples_per_phase):
            path.append(TaskWaypoint("raise_plus_z",
                                     after_insert @ transform(translation=[0, 0, 0.1 * float(progress)]),
                                     float(progress)))
    return path


def _validated_samples(task: dict) -> tuple[np.ndarray, list[dict]]:
    if (task.get("schema_version") != 1 or task.get("length_unit") != "m"
            or task.get("angle_unit") != "rad"
            or task.get("source_type") not in ("design_assumption", "measured")):
        raise ValueError("storage task requires schema_version=1, metres, radians and source_type")
    station = _rigid_pose(task["station_world_pose"], "station_world_pose")
    _rigid_pose(task["flange_to_tool"], "flange_to_tool")
    _rigid_pose(task["tool_to_unit"], "tool_to_unit")
    samples = task["samples"]
    ids = [item["sample_id"] for item in samples]
    if not ids or len(set(ids)) != len(ids) or any(not name for name in ids):
        raise ValueError("storage sample IDs must be nonempty and unique")
    if set(item["tier"] for item in samples) != {1, 2, 3}:
        raise ValueError("storage fixed dataset must cover tiers 1, 2 and 3, never tier 4")
    for item in samples:
        tier = item["tier"]
        xyz = np.asarray(item["xyz_m"], dtype=float)
        angles = np.asarray([item["theta_rad"], item["phi_rad"], item["alpha_rad"]], dtype=float)
        if (xyz.shape != (3,) or not np.isfinite(np.r_[xyz, angles]).all()
                or not (-0.1 - 1e-9 <= xyz[0] <= 1e-9)
                or not (0.1 - 1e-9 <= xyz[1] <= 0.3 + 1e-9)
                or not (0.5 - 1e-9 <= xyz[2] <= 0.7 + 1e-9)
                or abs(angles[0]) > np.pi / 2 + 1e-9
                or not (-1e-9 <= angles[1] <= np.pi / 2 + 1e-9)
                or abs(angles[2]) > np.pi / 4 + 1e-9):
            raise ValueError(f"sample {item['sample_id']} leaves 2026 one-core pose ranges")
        if tier == 1 and not np.allclose(angles, [0, np.pi / 2, 0], atol=1e-7):
            raise ValueError("tier 1 requires theta=0, phi=90°, alpha=0")
        if tier == 3:
            q_target = float(item["q_target_signed_rad"])
            if not np.isfinite(q_target) or abs(q_target) > np.pi / 2 + 1e-9:
                raise ValueError("tier 3 Q target must be within ±90°")
            axis_fields = ("p_axis_origin_world", "p_axis_world",
                           "q_axis_origin_world", "q_axis_world")
            present = [item.get(key) is not None for key in axis_fields]
            if any(present) and not all(present):
                raise ValueError("explicit tier 3 P/Q axes require all four fields")
        elif item.get("q_target_signed_rad") is not None:
            raise ValueError("tiers 1 and 2 must not request Q rotation")
    needs_offsets = any(item["tier"] == 3 and not all(item.get(key) is not None for key in
                         ("p_axis_origin_world", "p_axis_world", "q_axis_origin_world", "q_axis_world"))
                        for item in samples)
    offsets = (task.get("p_axis_offset_m"), task.get("q_axis_offset_m"))
    if needs_offsets or all(value is not None for value in offsets):
        values = np.asarray(offsets, dtype=float)
        if values.shape != (2,) or not np.isfinite(values).all() or np.any(values <= 0):
            raise ValueError("P/Q offsets must be positive finite design inputs")
    if int(task["samples_per_phase"]) < 2:
        raise ValueError("samples_per_phase must be at least two")
    return station, samples


def screen_storage_scene(scene_path: Path, task_path: Path,
                         robot_filter: str | None = None,
                         variant_filter: str | None = None,
                         parking_filter: str | None = None) -> dict:
    scene_raw, task_raw = scene_path.read_bytes(), task_path.read_bytes()
    scene, task = json.loads(scene_raw), json.loads(task_raw)
    station, samples = _validated_samples(task)
    if (scene.get("schema_version") != 1 or scene.get("length_unit") != "m"
            or scene.get("angle_unit") != "rad"
            or scene.get("source_type") not in ("design_assumption", "measured")):
        raise ValueError("storage needs a fixed scene in metres/radians with a declared source")
    robots = [name for name in scene["robots"] if robot_filter is None or name == robot_filter]
    variants = [item for item in scene["length_variants"]
                if variant_filter is None or item["variant_id"] == variant_filter]
    parking = [item for item in scene["parking"]["candidates"]
               if parking_filter is None or item["parking_id"] == parking_filter]
    if not robots or not variants or not parking:
        raise ValueError("candidate filter selects no robot, arm length or parking")
    obstacles = [Box.from_config(item) for item in scene["obstacles"]]
    obstacles.extend(Box.from_config(item) for item in task.get("core_obstacles", []))
    allowed_contacts = {(item["obstacle"], item["part"], phase)
                        for item in task.get("allowed_contacts", []) for phase in item["phases"]}
    polygon = np.asarray(scene["parking"]["allowed_polygon_xy_m"], dtype=float)
    paths = {}
    for sample in samples:
        first = arm_opt_preinsert_pose(station, sample["xyz_m"],
                                       sample["theta_rad"], sample["phi_rad"], sample["alpha_rad"])
        paths[sample["sample_id"]] = storage_path(sample["tier"], first,
                                                  int(task["samples_per_phase"]),
                                                  task.get("p_axis_offset_m"),
                                                  task.get("q_axis_offset_m"),
                                                  sample.get("q_target_signed_rad"),
                                                  sample.get("p_axis_origin_world"),
                                                  sample.get("p_axis_world"),
                                                  sample.get("q_axis_origin_world"),
                                                  sample.get("q_axis_world"))
    rows = []
    for robot in robots:
        base = load_local(robot)
        for variant in variants:
            scales = {int(key): float(value) for key, value in variant["anchor_span_scales"].items()}
            arm = scale_anchor_spans(base, scales) if scales else base
            radii = np.asarray(scene["geometry"]["link_capsule_radii_by_robot_m"][robot], dtype=float)
            for park in parking:
                mount = ChassisMount(float(park["x_m"]), float(park["y_m"]), float(park["yaw_rad"]),
                                     transform(translation=np.asarray(scene["chassis"]["arm_mount_translation_m"])))
                for sample in samples:
                    path = paths[sample["sample_id"]]
                    target = {"kind": "core", "path": path,
                              "flange_to_tool": np.asarray(task["flange_to_tool"], dtype=float),
                              "tool_to_unit": np.asarray(task["tool_to_unit"], dtype=float)}
                    base_row = _screen_one(scene, arm, mount, park["parking_id"], sample["sample_id"],
                                           target, obstacles, allowed_contacts, polygon, radii)
                    rows.append({"robot": robot, "length_variant_id": variant["variant_id"],
                                 "parking_id": park["parking_id"], "sample_id": sample["sample_id"],
                                 "sample_class": sample.get("sample_class"),
                                 "tier": sample["tier"], "xyz_m": sample["xyz_m"],
                                 "theta_rad": sample["theta_rad"], "phi_rad": sample["phi_rad"],
                                 "alpha_rad": sample["alpha_rad"],
                                 "q_target_signed_rad": sample.get("q_target_signed_rad"),
                                 "pq_axis_source": ("explicit_sample_axes" if sample["tier"] == 3 and
                                                    sample.get("p_axis_origin_world") is not None else
                                                    "arm_opt_offsets" if sample["tier"] == 3 else None),
                                 "path_phases": list(dict.fromkeys(point.phase for point in path)),
                                 "ready_for_confirmation_geometry": base_row["geometric_complete"],
                                 "failure": base_row["failure"],
                                 "path_point_count": base_row["path_point_count"],
                                 "ik_point_count": base_row["ik_point_count"],
                                 "min_clearance_proxy_m": base_row["min_clearance_proxy_m"],
                                 "min_joint_limit_margin_rad": base_row["min_joint_limit_margin_rad"],
                                 "checked_waypoints": base_row["checked_waypoints"]})
    summaries = []
    for robot in robots:
        for variant in variants:
            for park in parking:
                group = [row for row in rows if row["robot"] == robot
                         and row["length_variant_id"] == variant["variant_id"]
                         and row["parking_id"] == park["parking_id"]]
                tier_counts = {}
                for tier in (1, 2, 3):
                    tier_rows = [row for row in group if row["tier"] == tier]
                    passed = [row for row in tier_rows if row["ready_for_confirmation_geometry"]]
                    failures = [row["failure"] for row in tier_rows if row["failure"]]
                    tier_counts[str(tier)] = {
                        "complete": len(passed), "total": len(tier_rows),
                        "completion_fraction": len(passed) / len(tier_rows),
                        "failure_phases": dict(Counter(item["phase"] for item in failures)),
                        "failure_reasons": dict(Counter(item["reason"] for item in failures)),
                        "min_pass_clearance_proxy_m": min(
                            (row["min_clearance_proxy_m"] for row in passed
                             if row["min_clearance_proxy_m"] is not None), default=None),
                        "min_pass_joint_limit_margin_rad": min(
                            (row["min_joint_limit_margin_rad"] for row in passed
                             if row["min_joint_limit_margin_rad"] is not None), default=None)}
                summaries.append({"robot": robot, "length_variant_id": variant["variant_id"],
                                  "parking_id": park["parking_id"], "complete_count": sum(
                                      row["ready_for_confirmation_geometry"] for row in group),
                                  "sample_count": len(group),
                                  "balanced_completion_fraction": sum(
                                      tier_counts[str(tier)]["completion_fraction"] for tier in (1, 2, 3)) / 3,
                                  "tiers": tier_counts})
    summaries.sort(key=lambda entry: (-entry["balanced_completion_fraction"],
                                      -entry["complete_count"], entry["robot"],
                                      entry["length_variant_id"], entry["parking_id"]))
    references = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in (XARM_XML, UR5E_XML, UR5E_CLASSES, ARM_OPT_TRAJECTORY, RULE_2026)}
    return {"scenario_id": scene["scenario_id"], "scene_source_type": scene["source_type"],
            "task_scenario_id": task["scenario_id"], "task_source_type": task["source_type"],
            "scene_sha256": hashlib.sha256(scene_raw).hexdigest(),
            "task_sha256": hashlib.sha256(task_raw).hexdigest(),
            "reference_sha256": references,
            "excluded_difficulty": 4,
            "pass_condition": "sampled geometry through the tier's final required motion",
            "confirmation_and_release": "not simulated or scored",
            "notes": task.get("notes"), "candidate_summary": summaries, "rows": rows}


def write_storage_reports(report: dict, output_prefix: Path) -> tuple[Path, Path]:
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path, csv_path = output_prefix.with_suffix(".json"), output_prefix.with_suffix(".csv")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    fields = ("scenario_id", "task_scenario_id", "robot", "length_variant_id", "parking_id",
              "sample_id", "sample_class", "tier", "ready_for_confirmation_geometry",
              "failure_phase", "failure_reason", "path_point_count", "ik_point_count",
              "min_clearance_proxy_m", "min_joint_limit_margin_rad")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in report["rows"]:
            writer.writerow({"scenario_id": report["scenario_id"],
                             "task_scenario_id": report["task_scenario_id"],
                             **{key: row.get(key) for key in fields if key not in ("scenario_id", "task_scenario_id")},
                             "failure_phase": row["failure"]["phase"] if row["failure"] else None,
                             "failure_reason": row["failure"]["reason"] if row["failure"] else None})
    return json_path, csv_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    parser.add_argument("--robot", choices=("xarm6", "ur5e"))
    parser.add_argument("--variant")
    parser.add_argument("--parking")
    args = parser.parse_args()
    report = screen_storage_scene(args.scene, args.task, args.robot, args.variant, args.parking)
    outputs = write_storage_reports(report, args.output_prefix)
    print(json.dumps({"reports": [str(path) for path in outputs],
                      "candidate_count": len(report["candidate_summary"]),
                      "sample_count": len(report["rows"]),
                      "geometry_complete_count": sum(row["ready_for_confirmation_geometry"] for row in report["rows"])},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
