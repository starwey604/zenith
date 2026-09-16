"""Sampled pickup-angle and complete-unit exit screening; no return simulation."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from .benchmark import _rigid_pose, _screen_one
from .chassis import ChassisMount
from .collision import Box
from .frames import axis_turn, transform
from .length_design import scale_anchor_spans
from .model_import import load_local, model_reference_paths


def rotated_grasp(world_grasp_tool: np.ndarray, outward_axis: np.ndarray,
                  angle_rad: float, tool_to_unit: np.ndarray) -> np.ndarray:
    """Rotate the tool about the ore centre along its symmetry axis."""
    grasp = _rigid_pose(world_grasp_tool, "world_grasp_tool")
    offset = _rigid_pose(tool_to_unit, "tool_to_unit")
    axis = np.asarray(outward_axis, dtype=float)
    if (axis.shape != (3,) or not np.isfinite(axis).all()
            or not np.isclose(np.linalg.norm(axis), 1.0, atol=1e-6)
            or not np.isfinite(angle_rad)):
        raise ValueError("outward axis must be unit and placement angle finite")
    return axis_turn(axis, float(angle_rad), (grasp @ offset)[:3, 3]) @ grasp


def whole_unit_edge_margin_m(world_unit: np.ndarray, half_extents_m: np.ndarray,
                             edge_point_world_m: np.ndarray, outward_axis: np.ndarray) -> float:
    """Distance of the ore's innermost OBB corner past the exit plane."""
    unit = _rigid_pose(world_unit, "world_unit")
    half = np.asarray(half_extents_m, dtype=float)
    edge = np.asarray(edge_point_world_m, dtype=float)
    axis = np.asarray(outward_axis, dtype=float)
    if (half.shape != (3,) or edge.shape != (3,) or axis.shape != (3,)
            or not np.isfinite(np.r_[half, edge, axis]).all() or np.any(half <= 0)
            or not np.isclose(np.linalg.norm(axis), 1.0, atol=1e-6)):
        raise ValueError("ore, edge and outward axis require finite valid geometry")
    support = float(np.abs(axis @ unit[:3, :3]) @ half)
    return float(axis @ (unit[:3, 3] - edge) - support)


def required_axial_travel_m(world_unit_at_grasp: np.ndarray, half_extents_m: np.ndarray,
                            edge_point_world_m: np.ndarray, outward_axis: np.ndarray,
                            safety_distance_m: float, minimum_travel_m: float,
                            pose_guard_m: float) -> float:
    if (not np.isfinite([safety_distance_m, minimum_travel_m, pose_guard_m]).all()
            or safety_distance_m <= 0 or minimum_travel_m <= 0 or pose_guard_m < 0):
        raise ValueError("safety and minimum travel must be positive; pose guard nonnegative")
    initial_margin = whole_unit_edge_margin_m(world_unit_at_grasp, half_extents_m,
                                               edge_point_world_m, outward_axis)
    return max(float(minimum_travel_m),
               float(safety_distance_m + pose_guard_m - initial_margin))


def _validate_pickup_scene(scene: dict) -> tuple[np.ndarray, np.ndarray]:
    if (scene.get("schema_version") != 1 or scene.get("length_unit") != "m"
            or scene.get("angle_unit") != "rad"
            or scene.get("source_type") not in ("design_assumption", "measured")):
        raise ValueError("pickup exit requires schema_version=1, metres, radians and source_type")
    pickup = scene["tasks"]["pickup_2026"]
    _rigid_pose(pickup["flange_to_tool"], "pickup_2026.flange_to_tool")
    _rigid_pose(pickup["tool_to_unit"], "pickup_2026.tool_to_unit")
    angles = np.asarray(pickup["placement_angle_samples_rad"], dtype=float)
    if angles.ndim != 1 or not len(angles) or not np.isfinite(angles).all():
        raise ValueError("placement angles must be a nonempty finite list")
    wrapped = np.sort(np.mod(angles, 2 * np.pi))
    gaps = np.diff(np.r_[wrapped, wrapped[0] + 2 * np.pi])
    if np.min(gaps) < 1e-6:
        raise ValueError("placement angles must be distinct modulo one revolution")
    half = np.asarray(scene["geometry"]["held_unit_half_extents_m"], dtype=float)
    if half.shape != (3,) or not np.isfinite(half).all() or np.any(half <= 0):
        raise ValueError("held ore half extents must be a positive finite 3-vector")
    guard = float(pickup["edge_pose_guard_m"])
    if not np.isfinite(guard) or guard < 0:
        raise ValueError("edge pose guard must be finite and nonnegative")
    units = pickup["energy_units"]
    if len(units) != 6 or sorted(unit["slot_id"] for unit in units) != list(range(1, 7)):
        raise ValueError("pickup exit requires six distinct slot IDs")
    for unit in units:
        _rigid_pose(unit["world_grasp_tool"], f"slot_{unit['slot_id']}.world_grasp_tool")
        axis = np.asarray(unit["outward_symmetry_axis_world"], dtype=float)
        edge = np.asarray(unit["exit_edge_point_world_m"], dtype=float)
        lengths = np.asarray([unit[key] for key in ("approach_distance_m", "extraction_distance_m",
                                                  "edge_safety_distance_m", "max_axial_extraction_distance_m")], dtype=float)
        if (axis.shape != (3,) or edge.shape != (3,) or not np.isfinite(np.r_[axis, edge, lengths]).all()
                or not np.isclose(np.linalg.norm(axis), 1.0, atol=1e-6)
                or np.any(lengths <= 0)):
            raise ValueError(f"slot_{unit['slot_id']} exit geometry or travel invalid")
    return angles, gaps


def _screen_case(scene: dict, arm, mount: ChassisMount, parking_id: str,
                 unit: dict, angle: float, obstacles: list[Box],
                 polygon: np.ndarray, radii: np.ndarray) -> dict:
    pickup = scene["tasks"]["pickup_2026"]
    half = np.asarray(scene["geometry"]["held_unit_half_extents_m"], dtype=float)
    axis = np.asarray(unit["outward_symmetry_axis_world"], dtype=float)
    edge = np.asarray(unit["exit_edge_point_world_m"], dtype=float)
    offset = np.asarray(pickup["tool_to_unit"], dtype=float)
    grasp = rotated_grasp(np.asarray(unit["world_grasp_tool"]), axis, angle, offset)
    travel = required_axial_travel_m(grasp @ offset, half, edge, axis,
                                     float(unit["edge_safety_distance_m"]),
                                     float(unit["extraction_distance_m"]),
                                     float(pickup["edge_pose_guard_m"]))
    row = {"robot": arm.name.split("[")[0], "parking_id": parking_id,
           "slot_id": unit["slot_id"], "placement_angle_rad": angle,
           "exit_geometric_complete": False, "failure": None,
           "required_extraction_distance_m": travel,
           "edge_margin_at_exit_target_m": None, "edge_margin_at_exit_actual_m": None,
           "ik_point_count": 0, "path_point_count": 0,
           "min_clearance_proxy_m": None, "checked_waypoints": []}
    if travel > float(unit["max_axial_extraction_distance_m"]) + 1e-9:
        row["failure"] = {"phase": "extract_axis", "reason": "insufficient_axial_stroke"}
        return row
    from .task_2026 import energy_unit_pickup_path
    path = energy_unit_pickup_path(grasp, axis, float(unit["approach_distance_m"]),
                                   travel, int(scene["samples_per_phase"]))
    task = {"kind": "pickup", "path": path, "tool_to_unit": offset,
            "flange_to_tool": np.asarray(pickup["flange_to_tool"], dtype=float)}
    base = _screen_one(scene, arm, mount, parking_id, f"pickup_{unit['slot_id']}",
                       task, obstacles, set(), polygon, radii)
    row["ik_point_count"] = base["ik_point_count"]
    row["path_point_count"] = base["path_point_count"]
    row["min_clearance_proxy_m"] = base["min_clearance_proxy_m"]
    row["checked_waypoints"] = base["checked_waypoints"]
    if not base["geometric_complete"]:
        row["failure"] = base["failure"]
        return row
    target_unit = path[-1].world_tool @ offset
    actual_flange = mount.world_flange(arm, np.asarray(base["checked_waypoints"][-1]["q_rad"], dtype=float))
    actual_unit = actual_flange @ np.asarray(pickup["flange_to_tool"], dtype=float) @ offset
    row["edge_margin_at_exit_target_m"] = whole_unit_edge_margin_m(target_unit, half, edge, axis)
    row["edge_margin_at_exit_actual_m"] = whole_unit_edge_margin_m(actual_unit, half, edge, axis)
    if row["edge_margin_at_exit_actual_m"] < float(unit["edge_safety_distance_m"]) - 1e-8:
        row["failure"] = {"phase": "extract_axis", "reason": "edge_safety_failed"}
        return row
    row["exit_geometric_complete"] = True
    return row


def screen_pickup_exit(config_path: Path, robot_filter: str | None = None,
                       variant_filter: str | None = None,
                       parking_filter: str | None = None) -> dict:
    raw = config_path.read_bytes()
    scene = json.loads(raw)
    angles, gaps = _validate_pickup_scene(scene)
    robots = [name for name in scene["robots"] if robot_filter is None or name == robot_filter]
    variants = [item for item in scene["length_variants"]
                if variant_filter is None or item["variant_id"] == variant_filter]
    parking = [item for item in scene["parking"]["candidates"]
               if parking_filter is None or item["parking_id"] == parking_filter]
    if not robots or not variants or not parking:
        raise ValueError("candidate filter selects no robot, arm length or parking")
    obstacles = [Box.from_config(item) for item in scene["obstacles"]]
    polygon = np.asarray(scene["parking"]["allowed_polygon_xy_m"], dtype=float)
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
                for unit in scene["tasks"]["pickup_2026"]["energy_units"]:
                    for angle in angles:
                        row = _screen_case(scene, arm, mount, park["parking_id"], unit,
                                           float(angle), obstacles, polygon, radii)
                        row["length_variant_id"] = variant["variant_id"]
                        rows.append(row)
    summaries = []
    for robot in robots:
        for variant in variants:
            for park in parking:
                group = [row for row in rows if row["robot"] == robot
                         and row["length_variant_id"] == variant["variant_id"]
                         and row["parking_id"] == park["parking_id"]]
                summaries.append({"robot": robot, "length_variant_id": variant["variant_id"],
                                  "parking_id": park["parking_id"], "slot_count": 6,
                                  "angle_count_per_slot": len(angles), "case_count": len(group),
                                  "complete_case_count": sum(row["exit_geometric_complete"] for row in group),
                                  "all_sampled_angles_slot_count": sum(all(row["exit_geometric_complete"] for row in group
                                                                       if row["slot_id"] == slot)
                                                                        for slot in range(1, 7))})
    references = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in model_reference_paths(robots)}
    return {"scenario_id": scene["scenario_id"], "source_type": scene["source_type"],
            "scene_sha256": hashlib.sha256(raw).hexdigest(),
            "reference_model_sha256": references,
            "placement_angle_samples_rad": angles.tolist(),
            "max_sample_angle_gap_rad": float(np.max(gaps)),
            "pass_condition": "sampled axial pickup plus complete ore past exit edge with configured safety margin",
            "post_exit_retreat": "assumed feasible later; not screened or scored",
            "notes": scene.get("notes"), "candidate_summary": summaries, "rows": rows}


def write_pickup_exit_reports(report: dict, output_prefix: Path) -> tuple[Path, Path]:
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path, csv_path = output_prefix.with_suffix(".json"), output_prefix.with_suffix(".csv")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    fields = ("scenario_id", "robot", "length_variant_id", "parking_id", "slot_id", "placement_angle_rad",
              "exit_geometric_complete", "failure_phase", "failure_reason", "required_extraction_distance_m",
              "edge_margin_at_exit_target_m", "edge_margin_at_exit_actual_m", "ik_point_count",
              "path_point_count", "min_clearance_proxy_m")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in report["rows"]:
            writer.writerow({"scenario_id": report["scenario_id"],
                             **{key: row.get(key) for key in fields if key != "scenario_id"},
                             "failure_phase": row["failure"]["phase"] if row["failure"] else None,
                             "failure_reason": row["failure"]["reason"] if row["failure"] else None})
    return json_path, csv_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    parser.add_argument("--robot", choices=("xarm6", "ur5e"))
    parser.add_argument("--variant")
    parser.add_argument("--parking")
    args = parser.parse_args()
    report = screen_pickup_exit(args.scene, args.robot, args.variant, args.parking)
    outputs = write_pickup_exit_reports(report, args.output_prefix)
    print(json.dumps({"reports": [str(path) for path in outputs],
                      "candidate_count": len(report["candidate_summary"]),
                      "case_count": len(report["rows"]),
                      "complete_case_count": sum(row["exit_geometric_complete"] for row in report["rows"])},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
