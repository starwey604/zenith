import itertools
import json
from pathlib import Path

import numpy as np

from scripts.arm_design_study.storage_2026 import _validated_samples, screen_storage_scene
from scripts.arm_design_study.storage_stress import BOUNDS, build_pressure_samples, build_pressure_task


ROOT = Path(__file__).resolve().parents[1]


def _pose(sample):
    return np.r_[sample["xyz_m"], sample["theta_rad"], sample["phi_rad"],
                 sample["alpha_rad"]]


def test_pressure_set_is_fixed_valid_and_pairs_second_and_third_tier():
    first = build_pressure_samples(20260916)
    assert first == build_pressure_samples(20260916)
    changed = build_pressure_samples(20260917)
    assert [sample["tier"] for sample in first].count(1) == 15
    assert [sample["tier"] for sample in first].count(2) == 25
    assert [sample["tier"] for sample in first].count(3) == 27
    assert len({sample["sample_id"] for sample in first}) == len(first)
    assert any(_pose(a).tolist() != _pose(b).tolist() for a, b in zip(first, changed)
               if a["sample_class"] == "stratified_interior")
    assert all(_pose(a).tolist() == _pose(b).tolist() for a, b in zip(first, changed)
               if a["sample_class"] not in {"stratified_interior"})

    tier1 = [sample for sample in first if sample["tier"] == 1]
    corners = [sample for sample in tier1 if sample["sample_class"] == "xyz_corner"]
    expected = {tuple(BOUNDS[i, bit] for i, bit in enumerate(bits))
                for bits in itertools.product((0, 1), repeat=3)}
    assert {tuple(sample["xyz_m"]) for sample in corners} == expected
    assert all(np.allclose(_pose(sample)[3:], [0, np.pi / 2, 0]) for sample in tier1)

    tier2 = [sample for sample in first if sample["tier"] == 2]
    tier3 = [sample for sample in first if sample["tier"] == 3]
    assert all(np.array_equal(_pose(a), _pose(b)) for a, b in zip(tier2, tier3[:25]))
    assert {sample["q_target_signed_rad"] for sample in tier3} == {
        0.0, -np.pi / 2, np.pi / 2}
    task = build_pressure_task(ROOT / "configs/storage_2026.synthetic.json")
    assert task["samples"] == first
    assert {sample["tier"] for sample in _validated_samples(task)[1]} == {1, 2, 3}


def test_checked_in_stress_config_and_report_match_generated_task():
    task_path = ROOT / "configs/storage_2026.stress.synthetic.json"
    task = json.loads(task_path.read_text(encoding="utf-8"))
    assert task == build_pressure_task(ROOT / "configs/storage_2026.synthetic.json")
    report = screen_storage_scene(ROOT / "configs/benchmark.synthetic.json", task_path,
                                  "xarm6", "nominal", "rear_center")
    assert len(report["rows"]) == 67
    summary = report["candidate_summary"][0]
    assert [summary["tiers"][str(tier)]["total"] for tier in (1, 2, 3)] == [15, 25, 27]
    assert 0 <= summary["balanced_completion_fraction"] <= 1
    assert all(row["sample_class"] is not None for row in report["rows"])
    assert all("min_joint_limit_margin_rad" in row for row in report["rows"])
