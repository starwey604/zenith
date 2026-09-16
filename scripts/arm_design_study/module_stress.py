"""Fixed multi-pose bayonet docking cases, screened with the benchmark geometry."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import numpy as np

from .bayonet import Bayonet
from .benchmark import _box_pose, _build_tasks, _screen_one
from .chassis import ChassisMount
from .collision import Box
from .frames import transform
from .length_design import scale_anchor_spans
from .model_import import load_local, model_reference_paths


def screen_module_stress(scene_path: Path, stress_path: Path) -> dict:
    scene_raw, stress_raw = scene_path.read_bytes(), stress_path.read_bytes()
    scene, stress = json.loads(scene_raw), json.loads(stress_raw)
    cases = stress.get("cases")
    if (stress.get("schema_version") != 1 or stress.get("source_type") != "design_assumption"
            or not isinstance(cases, list) or not cases
            or len({item["case_id"] for item in cases}) != len(cases)):
        raise ValueError("module stress needs unique declared synthetic cases")
    if len(scene["robots"]) != len(scene["length_variants"]) != len(scene["parking"]["candidates"]) != 1:
        raise ValueError("module stress screens exactly one candidate scene")
    robot = scene["robots"][0]
    variant = scene["length_variants"][0]
    parking = scene["parking"]["candidates"][0]
    scales = {int(k): float(v) for k, v in variant["anchor_span_scales"].items()}
    base = load_local(robot)
    arm = scale_anchor_spans(base, scales) if scales else base
    mount = ChassisMount(float(parking["x_m"]), float(parking["y_m"]),
                         float(parking["yaw_rad"]),
                         transform(translation=np.asarray(scene["chassis"]["arm_mount_translation_m"], dtype=float)))
    polygon = np.asarray(scene["parking"]["allowed_polygon_xy_m"], dtype=float)
    radii = np.asarray(scene["geometry"]["link_capsule_radii_by_robot_m"][robot], dtype=float)
    interface = Bayonet.load(Path(scene["tasks"]["module_2027"]["interface_file"]))
    original_socket = np.asarray(scene["tasks"]["module_2027"]["world_socket"], dtype=float)
    rows = []
    for case in cases:
        delta = np.asarray(case["delta_xyz_m"], dtype=float)
        yaw = float(case["yaw_delta_rad"])
        if delta.shape != (3,) or not np.isfinite(delta).all() or not np.isfinite(yaw):
            raise ValueError("module stress case needs finite metre translation and radian yaw")
        local = copy.deepcopy(scene)
        socket = original_socket.copy()
        c, s = np.cos(yaw), np.sin(yaw)
        socket[:3, :3] = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]]) @ socket[:3, :3]
        socket[:3, 3] += delta
        module = local["tasks"]["module_2027"]
        module["world_socket"] = socket.tolist()
        task = _build_tasks(local, interface)["module_2027"]
        obstacles = [Box.from_config(item) for item in local["obstacles"]]
        obstacles.append(Box("module_on_table",
                             _box_pose(socket, np.asarray(module["body_centre_from_socket_m"], dtype=float)),
                             np.asarray(module["body_half_extents_m"], dtype=float), False,
                             ("approach", "cone_align", "key_align", "straight_insert", "bayonet_turn")))
        contacts = {(item["obstacle"], item["part"], phase)
                    for item in local.get("allowed_contacts", []) for phase in item["phases"]}
        row = _screen_one(local, arm, mount, parking["parking_id"], case["case_id"],
                          task, obstacles, contacts, polygon, radii)
        row["case_id"] = case["case_id"]
        row["delta_xyz_m"] = case["delta_xyz_m"]
        row["yaw_delta_rad"] = yaw
        rows.append(row)
    paths = model_reference_paths([robot])
    return {"scenario_id": stress["scenario_id"],
            "scene_sha256": hashlib.sha256(scene_raw).hexdigest(),
            "stress_sha256": hashlib.sha256(stress_raw).hexdigest(),
            "reference_model_sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                                       for path in paths},
            "case_count": len(rows), "complete_count": sum(row["geometric_complete"] for row in rows),
            "rows": rows}
