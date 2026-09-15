import json
from pathlib import Path

import numpy as np

from scripts.arm_design_study.pickup_exit import (
    required_axial_travel_m, rotated_grasp, screen_pickup_exit,
    whole_unit_edge_margin_m,
)


ROOT = Path(__file__).resolve().parents[1]


def test_whole_ore_edge_uses_innermost_corner_and_pose_guard():
    tool = np.eye(4)
    tool[1, 3] = 0.14
    offset = np.eye(4)
    outward = np.array([0.0, -1.0, 0.0])
    edge = np.array([0.0, 0.06, 0.0])
    half = np.array([0.04, 0.025, 0.02])
    rotated = rotated_grasp(tool, outward, np.pi / 2, offset)
    assert np.isclose(whole_unit_edge_margin_m(rotated @ offset, half, edge, outward), -0.105)
    travel = required_axial_travel_m(rotated @ offset, half, edge, outward, 0.04, 0.12, 0.001)
    assert np.isclose(travel, 0.146)
    exit_unit = rotated @ offset
    exit_unit[:3, 3] += outward * travel
    assert whole_unit_edge_margin_m(exit_unit, half, edge, outward) >= 0.041 - 1e-10


def test_angle_rotates_about_ore_centre_when_gripper_is_offset():
    tool = np.eye(4)
    tool[1, 3] = 0.14
    offset = np.eye(4)
    offset[0, 3] = 0.10
    outward = np.array([0.0, -1.0, 0.0])
    rotated = rotated_grasp(tool, outward, np.pi / 2, offset)
    assert not np.allclose(rotated[:3, 3], tool[:3, 3])
    assert np.allclose((rotated @ offset)[:3, 3], (tool @ offset)[:3, 3])


def test_pickup_pass_ends_at_safe_exit_without_loaded_return(tmp_path):
    scene = json.loads((ROOT / "configs/benchmark.synthetic.json").read_text(encoding="utf-8"))
    scene["tasks"]["pickup_2026"]["placement_angle_samples_rad"] = [0.0]
    path = tmp_path / "scene.json"
    path.write_text(json.dumps(scene), encoding="utf-8")
    report = screen_pickup_exit(path, "ur5e", "nominal", "rear_left")
    assert len(report["rows"]) == 6
    slot_one = next(row for row in report["rows"] if row["slot_id"] == 1)
    assert slot_one["exit_geometric_complete"]
    assert slot_one["edge_margin_at_exit_actual_m"] >= 0.04
    assert slot_one["checked_waypoints"][-1]["phase"] == "extract_axis"
    assert "joint_return_q_rad" not in slot_one
    assert report["post_exit_retreat"] == "assumed feasible later; not screened or scored"


def test_too_short_axial_stroke_fails_before_ik(tmp_path):
    scene = json.loads((ROOT / "configs/benchmark.synthetic.json").read_text(encoding="utf-8"))
    scene["tasks"]["pickup_2026"]["placement_angle_samples_rad"] = [0.0]
    scene["tasks"]["pickup_2026"]["energy_units"][0]["max_axial_extraction_distance_m"] = 0.12
    path = tmp_path / "scene.json"
    path.write_text(json.dumps(scene), encoding="utf-8")
    report = screen_pickup_exit(path, "xarm6", "nominal", "rear_left")
    slot_one = next(row for row in report["rows"] if row["slot_id"] == 1)
    assert not slot_one["exit_geometric_complete"]
    assert slot_one["failure"]["reason"] == "insufficient_axial_stroke"
    assert slot_one["ik_point_count"] == 0
