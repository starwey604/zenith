from pathlib import Path

from scripts.arm_design_study.benchmark import screen_scene


ROOT = Path(__file__).resolve().parents[1]


def test_fixed_scene_reports_all_tasks_and_collision_aware_ik_branches():
    report = screen_scene(ROOT / "configs/benchmark.synthetic.json")
    assert report["candidate_count"] == 12
    assert len(report["rows"]) == 12 * 8
    assert len(report["candidate_summary"]) == 12
    by_key = {(row["robot"], row["length_variant_id"], row["parking_id"], row["task_id"]): row
              for row in report["rows"]}
    module = by_key[("xarm6", "nominal", "rear_left", "module_2027")]
    assert module["geometric_complete"]
    assert module["checked_waypoints"][-1]["phase"] == "leave_table"
    assert by_key[("ur5e", "nominal", "rear_left", "pickup_1")]["geometric_complete"]
    illegal = by_key[("xarm6", "nominal", "fixture_overlap_check", "module_2027")]
    assert illegal["failure"]["reason"] == "parking_illegal"
