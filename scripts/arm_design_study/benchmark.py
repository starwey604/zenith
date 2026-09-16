"""Fixed-scene geometric screening for six-axis arms, lengths and parking."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np

from .bayonet import Bayonet
from .bayonet_trajectory import generate_bayonet_path, follow_ik
from .chassis import ChassisMount
from .collision import Box, chassis_box, collision_scan, robot_capsules
from .frames import inverse, transform, yaw_pose
from .length_design import scale_anchor_spans
from .model_import import load_local, model_reference_paths
from .parking import parking_legality
from .task_2026 import core_assembly_path, energy_unit_pickup_path, follow_task_ik


ROOT = Path(__file__).resolve().parent
CORE_FIELDS = ("pre_insert_world_tool", "p_axis_origin_world", "p_axis_world",
               "q_axis_origin_world", "q_axis_world", "p_upward_turn_sign", "q_target_signed_rad", "flange_to_tool")
PICKUP_FIELDS = ("world_grasp_tool", "outward_symmetry_axis_world",
                 "approach_distance_m", "extraction_distance_m")


def _required(data: dict, fields: tuple[str, ...], prefix: str) -> None:
    missing = [f"{prefix}.{field}" for field in fields if data.get(field) is None]
    if missing:
        raise ValueError("missing_input: " + ", ".join(missing))


def _rigid_pose(value, label: str) -> np.ndarray:
    pose = np.asarray(value, dtype=float)
    if (pose.shape != (4, 4) or not np.isfinite(pose).all()
            or not np.allclose(pose[3], [0, 0, 0, 1])
            or not np.allclose(pose[:3, :3].T @ pose[:3, :3], np.eye(3), atol=1e-5)
            or np.linalg.det(pose[:3, :3]) < 0.999):
        raise ValueError(f"{label} must be a finite SE(3) pose")
    return pose


def _box_pose(world_frame: np.ndarray, local_centre: np.ndarray) -> np.ndarray:
    return world_frame @ transform(translation=local_centre)


def _expanded_extent_in_chassis_frame(mount: ChassisMount, chassis: Box,
                                      capsules: list, carried: Box | None) -> np.ndarray:
    """Axis-aligned extent of the coarse bodies in the parked chassis frame."""
    chassis_from_world = inverse(yaw_pose(mount.x_m, mount.y_m, mount.yaw_rad))
    lows, highs = [], []
    def body(box: Box) -> None:
        pose = chassis_from_world @ box.pose
        half = np.abs(pose[:3, :3]) @ box.half_m
        lows.append(pose[:3, 3] - half)
        highs.append(pose[:3, 3] + half)
    body(chassis)
    for capsule in capsules:
        endpoints = np.array([(chassis_from_world @ np.r_[point, 1.0])[:3]
                              for point in (capsule.start, capsule.end)])
        lows.append(endpoints.min(axis=0) - capsule.radius_m)
        highs.append(endpoints.max(axis=0) + capsule.radius_m)
    if carried is not None:
        body(carried)
    return np.max(highs, axis=0) - np.min(lows, axis=0)


def _default_seed(robot: str) -> np.ndarray:
    if robot == "ur5e":
        return np.array([-np.pi / 2, -np.pi / 2, np.pi / 2,
                         -np.pi / 2, -np.pi / 2, 0.0])
    # A bent wrist is closer to an upward-facing workbench connection.
    return np.array([0.0, 0.0, 0.0, 0.0, np.pi - 1e-5, 0.0])


def _build_tasks(scene: dict, interface: Bayonet) -> dict[str, dict]:
    count = int(scene.get("samples_per_phase", 8))
    module = scene["tasks"]["module_2027"]
    _required(module, ("world_socket", "flange_to_pin", "leave_distance_m"), "module_2027")
    socket = _rigid_pose(module["world_socket"], "module_2027.world_socket")
    flange_to_pin = _rigid_pose(module["flange_to_pin"], "module_2027.flange_to_pin")
    if float(module["leave_distance_m"]) <= 0:
        raise ValueError("module_2027.leave_distance_m must be positive for this screening round")
    body_centre = np.asarray(module["body_centre_from_socket_m"], dtype=float)
    body_half = np.asarray(module["body_half_extents_m"], dtype=float)
    if (body_centre.shape != (3,) or body_half.shape != (3,)
            or not np.isfinite(np.r_[body_centre, body_half]).all() or np.any(body_half <= 0)):
        raise ValueError("module body centre/half extents must be finite positive geometry")
    bayonet = generate_bayonet_path(interface, socket, flange_to_pin, count,
                                    float(module["leave_distance_m"]))
    core = scene["tasks"]["core_2026"]
    _required(core, CORE_FIELDS, "core_2026")
    if core["p_upward_turn_sign"] not in (-1, 1):
        raise ValueError("core P upward sign must be ±1")
    core_path = core_assembly_path(np.asarray(core["pre_insert_world_tool"]),
                                   np.asarray(core["p_axis_origin_world"]), np.asarray(core["p_axis_world"]),
                                   np.asarray(core["q_axis_origin_world"]), np.asarray(core["q_axis_world"]),
                                   core["p_upward_turn_sign"] * np.pi / 2,
                                   float(core["q_target_signed_rad"]), count)
    units = scene["tasks"]["pickup_2026"]["energy_units"]
    if len(units) != 6 or sorted(unit.get("slot_id") for unit in units) != list(range(1, 7)):
        raise ValueError("pickup task must declare all six distinct slot IDs")
    result = {"module_2027": {"kind": "module", "path": bayonet,
                               "flange_to_pin": flange_to_pin},
              "core_2026": {"kind": "core", "path": core_path,
                            "flange_to_tool": np.asarray(core["flange_to_tool"], dtype=float)}}
    pickup = scene["tasks"]["pickup_2026"]
    _required(pickup, ("flange_to_tool",), "pickup_2026")
    for unit in units:
        _required(unit, PICKUP_FIELDS, f"pickup_2026.slot_{unit['slot_id']}")
        path = energy_unit_pickup_path(np.asarray(unit["world_grasp_tool"]),
                                       np.asarray(unit["outward_symmetry_axis_world"]),
                                       float(unit["approach_distance_m"]),
                                       float(unit["extraction_distance_m"]), count)
        result[f"pickup_{unit['slot_id']}"] = {"kind": "pickup", "path": path,
                                              "flange_to_tool": np.asarray(pickup["flange_to_tool"], dtype=float)}
    return result


def _screen_one(scene: dict, arm, mount: ChassisMount, parking_id: str,
                task_id: str, task: dict, obstacles: list[Box],
                allowed_contacts: set[tuple[str, str, str]],
                allowed_polygon: np.ndarray, radii: np.ndarray) -> dict:
    chassis_half = np.asarray(scene["chassis"]["half_extents_m"], dtype=float)
    legal, parking_reason, parking_margin = parking_legality(mount, chassis_half, allowed_polygon, obstacles)
    result = {"robot": arm.name, "robot_provenance": arm.provenance,
              "parking_id": parking_id, "task_id": task_id, "task_kind": task["kind"],
              "parking": {"x_m": mount.x_m, "y_m": mount.y_m, "yaw_rad": mount.yaw_rad},
              "parking_clearance_proxy_m": parking_margin if np.isfinite(parking_margin) else None,
              "path_point_count": len(task["path"]), "ik_point_count": 0,
              "geometric_complete": False, "failure": None, "min_clearance_proxy_m": None,
              "min_joint_limit_margin_rad": None, "checked_waypoints": []}
    if not legal:
        result["failure"] = {"index": 0, "phase": "parking", "reason": "parking_illegal",
                             "detail": parking_reason}
        return result
    seed = _default_seed(arm.name.split("[")[0])
    chassis = chassis_box(mount, chassis_half)
    max_expanded = np.asarray(scene["geometry"]["max_expanded_span_m"], dtype=float)
    module = scene["tasks"]["module_2027"]
    module_local = np.asarray(module["body_centre_from_socket_m"], dtype=float)
    module_half = np.asarray(module["body_half_extents_m"], dtype=float)
    held_half = np.asarray(scene["geometry"]["held_unit_half_extents_m"], dtype=float)

    def state_geometry(q: np.ndarray, index: int):
        point = task["path"][index]
        caps = robot_capsules(arm, mount, q, radii,
                              float(scene["geometry"]["tool_radius_m"]),
                              float(scene["geometry"]["tool_length_m"]))
        carried = None
        if task["kind"] == "module" and point.phase in ("locked", "leave_table"):
            carried = Box("carried_module", _box_pose(point.world_module, module_local), module_half,
                          False)
        elif task["kind"] == "core" or (task["kind"] == "pickup" and point.phase in ("grasp", "extract_axis")):
            unit_from_tool = task.get("tool_to_unit", np.eye(4))
            carried = Box("carried_energy_unit", point.world_tool @ unit_from_tool, held_half, False)
        clearance, hit = collision_scan(caps, chassis, obstacles, point.phase,
                                        allowed_contacts, carried)
        extent = _expanded_extent_in_chassis_frame(mount, chassis, caps, carried)
        return clearance, hit, extent

    def quality(q: np.ndarray, index: int, _point) -> float:
        clearance, _, extent = state_geometry(q, index)
        return float(min(clearance, np.min(max_expanded - extent)))

    if task["kind"] == "module":
        trajectory, ik_failure = follow_ik(arm, mount, task["path"], seed,
                                           random_seed=int(scene["random_seed"]),
                                           quality_fn=quality)
    else:
        trajectory, ik_failure = follow_task_ik(arm, mount, task["path"],
                                                task["flange_to_tool"], seed,
                                                random_seed=int(scene["random_seed"]),
                                                quality_fn=quality)
    result["ik_point_count"] = len(trajectory)
    geometric_failure = None
    margins, limit_margins = [], []
    for record in trajectory:
        index = record["index"]
        point = task["path"][index]
        q = np.asarray(record["q_rad"], dtype=float)
        clearance, hit, extent = state_geometry(q, index)
        limit_margin = float(np.min(np.minimum(q - arm.limits[:, 0], arm.limits[:, 1] - q)))
        margins.append(clearance)
        limit_margins.append(limit_margin)
        checked = {"index": index, "phase": point.phase, "q_rad": record["q_rad"],
                   "world_flange": record["world_flange"],
                   "world_module": point.world_module.tolist() if task["kind"] == "module" else None,
                   "clearance_proxy_m": clearance if np.isfinite(clearance) else None,
                   "joint_limit_margin_rad": limit_margin,
                   "expanded_span_m": extent.tolist(),
                   "position_error_m": record["position_error_m"],
                   "angle_error_rad": record["angle_error_rad"]}
        result["checked_waypoints"].append(checked)
        if geometric_failure is None and hit is not None:
            geometric_failure = {"index": index, "phase": point.phase,
                                 "reason": "collision", **hit}
        if geometric_failure is None and np.any(extent > max_expanded + 1e-9):
            geometric_failure = {"index": index, "phase": point.phase,
                                 "reason": "expanded_limit", "expanded_span_m": extent.tolist()}
    if margins:
        finite = [value for value in margins if np.isfinite(value)]
        result["min_clearance_proxy_m"] = min(finite) if finite else None
        result["min_joint_limit_margin_rad"] = min(limit_margins)
    if geometric_failure is not None and (ik_failure is None or geometric_failure["index"] <= ik_failure["index"]):
        result["failure"] = geometric_failure
    elif ik_failure is not None:
        result["failure"] = ik_failure
    else:
        result["geometric_complete"] = True
    return result


def screen_scene(config_path: Path) -> dict:
    raw = config_path.read_bytes()
    scene = json.loads(raw)
    if scene.get("schema_version") != 1 or scene.get("length_unit") != "m" or scene.get("angle_unit") != "rad":
        raise ValueError("benchmark requires schema_version=1, metres and radians")
    if scene.get("source_type") not in ("design_assumption", "measured") or not scene.get("scenario_id"):
        raise ValueError("benchmark config must have scenario_id and measured/design_assumption source_type")
    if not isinstance(scene.get("random_seed"), int) or scene["random_seed"] < 0:
        raise ValueError("random_seed must be a nonnegative integer")
    for label, values, field in (("robots", scene["robots"], None),
                                 ("length variants", scene["length_variants"], "variant_id"),
                                 ("parking candidates", scene["parking"]["candidates"], "parking_id")):
        ids = values if field is None else [item[field] for item in values]
        if not ids or len(set(ids)) != len(ids):
            raise ValueError(f"{label} must be nonempty with unique IDs")
    maximum = np.asarray(scene["geometry"]["max_expanded_span_m"], dtype=float)
    if maximum.shape != (3,) or not np.isfinite(maximum).all() or np.any(maximum <= 0):
        raise ValueError("max_expanded_span_m must be a positive finite 3-vector")
    interface_path = (config_path.parent / scene["tasks"]["module_2027"]["interface_file"]).resolve()
    interface = Bayonet.load(interface_path)
    tasks = _build_tasks(scene, interface)
    obstacles = [Box.from_config(item) for item in scene["obstacles"]]
    module = scene["tasks"]["module_2027"]
    socket = np.asarray(module["world_socket"], dtype=float)
    obstacles.append(Box("module_on_table",
                         _box_pose(socket, np.asarray(module["body_centre_from_socket_m"], dtype=float)),
                         np.asarray(module["body_half_extents_m"], dtype=float), False,
                         ("approach", "cone_align", "key_align", "straight_insert", "bayonet_turn")))
    allowed_contacts = {(item["obstacle"], item["part"], phase)
                        for item in scene.get("allowed_contacts", []) for phase in item["phases"]}
    polygon = np.asarray(scene["parking"]["allowed_polygon_xy_m"], dtype=float)
    rows = []
    for robot in scene["robots"]:
        base = load_local(robot)
        for variant in scene["length_variants"]:
            scales = {int(key): float(value) for key, value in variant["anchor_span_scales"].items()}
            arm = scale_anchor_spans(base, scales) if scales else base
            radii = np.asarray(scene["geometry"]["link_capsule_radii_by_robot_m"][robot], dtype=float)
            for parking in scene["parking"]["candidates"]:
                mount = ChassisMount(float(parking["x_m"]), float(parking["y_m"]),
                                     float(parking["yaw_rad"]),
                                     transform(translation=np.asarray(scene["chassis"]["arm_mount_translation_m"], dtype=float)))
                for task_id, task in tasks.items():
                    row = _screen_one(scene, arm, mount, parking["parking_id"], task_id,
                                      task, obstacles, allowed_contacts, polygon, radii)
                    row["length_variant_id"] = variant["variant_id"]
                    row["anchor_span_scales"] = scales
                    rows.append(row)
    groups: dict[tuple[str, str, str], list[dict]] = {}
    for row in rows:
        base_name = row["robot"].split("[")[0]
        key = (base_name, row["length_variant_id"], row["parking_id"])
        groups.setdefault(key, []).append(row)
    summaries = []
    for (robot, length_id, parking_id), group in groups.items():
        by_task = {row["task_id"]: row for row in group}
        summaries.append({"robot": robot, "length_variant_id": length_id,
                          "parking_id": parking_id, "task_count": len(group),
                          "geometric_complete_count": sum(row["geometric_complete"] for row in group),
                          "pickup_complete_count": sum(by_task[f"pickup_{j}"]["geometric_complete"] for j in range(1, 7)),
                          "core_complete": by_task["core_2026"]["geometric_complete"],
                          "module_complete": by_task["module_2027"]["geometric_complete"],
                          "task_failure_reasons": {task_id: (row["failure"]["reason"] if row["failure"] else None)
                                                   for task_id, row in by_task.items()}})
    summaries.sort(key=lambda entry: (-entry["geometric_complete_count"], entry["robot"],
                                      entry["length_variant_id"], entry["parking_id"]))
    reference_paths = model_reference_paths(scene["robots"])
    references = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in reference_paths}
    return {"scenario_id": scene["scenario_id"], "source_type": scene["source_type"],
            "scene_sha256": hashlib.sha256(raw).hexdigest(),
            "interface_file": str(interface_path),
            "interface_sha256": hashlib.sha256(interface_path.read_bytes()).hexdigest(),
            "reference_model_sha256": references,
            "random_seed": scene["random_seed"],
            "notes": scene.get("notes"), "task_ids": list(tasks),
            "candidate_count": len(scene["robots"]) * len(scene["length_variants"]) * len(scene["parking"]["candidates"]),
            "candidate_summary": summaries, "rows": rows}


def write_reports(report: dict, output_prefix: Path) -> tuple[Path, Path, Path]:
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path = output_prefix.with_suffix(".json")
    csv_path = output_prefix.with_suffix(".csv")
    summary_path = output_prefix.with_name(output_prefix.name + "_candidates.csv")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    fields = ("scenario_id", "robot", "length_variant_id", "parking_id", "task_id",
              "geometric_complete", "failure_reason", "failure_phase", "ik_point_count",
              "path_point_count", "min_clearance_proxy_m", "min_joint_limit_margin_rad",
              "parking_clearance_proxy_m")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in report["rows"]:
            writer.writerow({"scenario_id": report["scenario_id"],
                             **{key: row.get(key) for key in fields if key != "scenario_id"},
                             "failure_reason": row["failure"]["reason"] if row["failure"] else None,
                             "failure_phase": row["failure"]["phase"] if row["failure"] else None})
    summary_fields = ("robot", "length_variant_id", "parking_id", "task_count",
                      "geometric_complete_count", "pickup_complete_count",
                      "core_complete", "module_complete", "task_failure_reasons")
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=summary_fields)
        writer.writeheader()
        for entry in report["candidate_summary"]:
            writer.writerow({**entry, "task_failure_reasons": json.dumps(entry["task_failure_reasons"], ensure_ascii=False)})
    return json_path, csv_path, summary_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Fixed synthetic-scene geometric benchmark")
    parser.add_argument("--scene", type=Path, default=ROOT / "configs/benchmark.synthetic.json")
    parser.add_argument("--output-prefix", type=Path, default=ROOT / "runs/benchmark_screen")
    args = parser.parse_args()
    report = screen_scene(args.scene)
    paths = write_reports(report, args.output_prefix)
    completed = sum(row["geometric_complete"] for row in report["rows"])
    print(json.dumps({"reports": [str(path) for path in paths],
                      "candidate_count": report["candidate_count"],
                      "task_count": len(report["task_ids"]),
                      "geometric_complete_rows": completed,
                      "total_rows": len(report["rows"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
