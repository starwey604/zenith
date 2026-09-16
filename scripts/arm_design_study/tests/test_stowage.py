import json
from pathlib import Path

import numpy as np

from scripts.arm_design_study.chassis import ChassisMount
from scripts.arm_design_study.collision import Capsule, chassis_box
from scripts.arm_design_study.frames import transform
from scripts.arm_design_study.stowage import geometry_aabb, periodic_search_limits
from scripts.arm_design_study.stowage_sweep import manifest


ROOT = Path(__file__).resolve().parents[1]


def test_geometry_aabb_combines_chassis_and_capsule_radius():
    mount = ChassisMount(0.0, 0.0, 0.0, transform())
    chassis = chassis_box(mount, np.array([0.2, 0.1, 0.15]))
    capsule = Capsule("arm", np.array([0.0, 0.0, 0.3]),
                      np.array([0.5, 0.0, 0.3]), 0.05, 3)
    lower, upper = geometry_aabb(chassis, [capsule])
    assert np.allclose(lower, [-0.2, -0.1, 0.0])
    assert np.allclose(upper, [0.55, 0.1, 0.35])


def test_periodic_search_limits_preserve_narrow_authored_ranges():
    original = np.array([[-7.0, 7.0], [-2.0, 1.0], [-3.0, 4.0],
                         [-1.0, 1.0], [-6.0, 2.0], [-np.pi, np.pi]])
    actual = periodic_search_limits(original)
    assert np.allclose(actual[1], original[1])
    assert np.allclose(actual[3], original[3])
    assert np.all(actual[:, 0] >= original[:, 0])
    assert np.all(actual[:, 1] <= original[:, 1])
    assert np.all(actual[:, 1] - actual[:, 0] <= 2 * np.pi + 1e-12)


def test_manifest_deduplicates_field_parking_from_stowage_geometry():
    value, candidates, scenes = manifest(ROOT / "configs/stowage_sweep.v1.json")
    assert value["candidate_count"] == 153
    assert len(candidates) == 153
    assert len(scenes) == 2
    assert len({candidate["candidate_id"] for candidate in candidates}) == 153
    assert {candidate["robot"] for candidate in candidates} == {
        "xarm6", "ur5e", "lite6", "unitree_z1", "ur10e", "widowx250", "piper", "willow0907"}
    config = json.loads((ROOT / "configs/stowage_sweep.v1.json").read_text(encoding="utf-8"))
    assert config["max_workers"] == 3


def test_chassis250_stowage_reuses_geometry_samples_without_stale_task_scores():
    config_path = ROOT / "configs/stowage_sweep.chassis250.v1.json"
    value, candidates, scenes = manifest(config_path)
    assert value["candidate_count"] == 153
    assert all(candidate["task_best"] is None for candidate in candidates)
    for scene in scenes.values():
        assert scene["chassis"]["half_extents_m"] == [0.18, 0.18, 0.125]
        assert scene["chassis"]["arm_mount_translation_m"] == [0.0, 0.0, 0.25]
