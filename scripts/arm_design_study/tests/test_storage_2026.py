import json
from pathlib import Path

import numpy as np
import pytest

from scripts.arm_design_study.storage_2026 import (
    arm_opt_pq_axes, arm_opt_preinsert_pose, screen_storage_scene, storage_path,
)


ROOT = Path(__file__).resolve().parents[1]


def test_tiers_have_only_their_rule_required_motion_and_reject_fourth():
    preinsert = np.eye(4)
    paths = [storage_path(tier, preinsert, 4, 0.20875, 0.22375,
                          0.52 if tier == 3 else None) for tier in (1, 2, 3)]
    assert [list(dict.fromkeys(point.phase for point in path)) for path in paths] == [
        ["insert_minus_x"],
        ["insert_minus_x", "raise_plus_z"],
        ["insert_minus_x", "raise_plus_z", "turn_p_90", "turn_q_target"],
    ]
    assert [len(path) for path in paths] == [4, 8, 16]
    assert np.allclose(paths[0][-1].world_tool[:3, 3], [-0.1, 0, 0])
    assert np.allclose(paths[1][-1].world_tool[:3, 3], [-0.1, 0, 0.1])
    with pytest.raises(ValueError, match="only RoboMaster difficulty tiers"):
        storage_path(4, preinsert, 4, 0.20875, 0.22375, 0.52)


def test_arm_opt_pose_and_axis_offsets_are_explicit_inputs():
    station = np.eye(4)
    station[:3, 3] = [0.25, 0.0, 0.0]
    first = arm_opt_preinsert_pose(station, [-0.05, 0.2, 0.6], 0, np.pi / 2, 0)
    assert np.allclose(first[:3, 3], [0.2, 0.2, 0.6])
    p_origin, p_axis, q_origin, q_axis = arm_opt_pq_axes(first, 0.20875, 0.22375)
    after_insert = first @ np.array([[1, 0, 0, -0.1], [0, 1, 0, 0],
                                     [0, 0, 1, 0], [0, 0, 0, 1]])
    assert np.allclose(p_origin, after_insert[:3, 3] + first[:3, 2] * 0.20875)
    assert np.allclose(q_origin, after_insert[:3, 3] + first[:3, 2] * 0.22375)
    assert np.allclose(p_axis, first[:3, 1])
    assert np.allclose(q_axis, first[:3, 0])
    measured = storage_path(3, first, 4, q_target_signed_rad=0.52,
                            p_axis_origin_world=p_origin, p_axis_world=p_axis,
                            q_axis_origin_world=q_origin, q_axis_world=q_axis)
    assert measured[-1].phase == "turn_q_target"
    with pytest.raises(ValueError, match="all four origin/vector"):
        storage_path(3, first, 4, q_target_signed_rad=0.52,
                     p_axis_origin_world=p_origin)


def test_fixed_storage_scene_reports_only_tiers_one_to_three():
    report = screen_storage_scene(ROOT / "configs/benchmark.synthetic.json",
                                  ROOT / "configs/storage_2026.synthetic.json",
                                  "xarm6", "nominal", "rear_center")
    assert len(report["rows"]) == 6
    assert {row["tier"] for row in report["rows"]} == {1, 2, 3}
    assert report["excluded_difficulty"] == 4
    summary = report["candidate_summary"][0]
    assert summary["tiers"]["1"]["total"] == 2
    assert summary["tiers"]["2"]["total"] == 2
    assert summary["tiers"]["3"]["total"] == 2
    assert summary["tiers"]["3"]["complete"] == 2
    assert all(row["path_point_count"] in (16, 32, 64) for row in report["rows"])


def test_storage_config_rejects_fourth_tier_before_solving(tmp_path):
    task = json.loads((ROOT / "configs/storage_2026.synthetic.json").read_text(encoding="utf-8"))
    task["samples"][0]["tier"] = 4
    path = tmp_path / "storage.json"
    path.write_text(json.dumps(task), encoding="utf-8")
    with pytest.raises(ValueError, match="never tier 4"):
        screen_storage_scene(ROOT / "configs/benchmark.synthetic.json", path,
                             "xarm6", "nominal", "rear_left")
