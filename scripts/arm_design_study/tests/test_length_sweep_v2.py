import json
from pathlib import Path

from scripts.arm_design_study.length_sweep_v2 import candidate_scene, generate_candidates
from scripts.arm_design_study.model_import import compare_mjcf_fk, compare_urdf_fk, load_local


ROOT = Path(__file__).resolve().parents[1]
CONFIGS = ROOT / "configs"
SCENE = CONFIGS / "benchmark.six_axis_v2.synthetic.json"
SPEC = CONFIGS / "length_sweep.v2.json"
WILLOW_SCENE = CONFIGS / "benchmark.willow0907.synthetic.json"
WILLOW_SPEC = CONFIGS / "length_sweep.willow0907.v1.json"


def test_each_reference_has_six_joint_fk_and_zero_spans_are_fixed():
    scene = json.loads(SCENE.read_text(encoding="utf-8"))
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    candidates = generate_candidates(spec, scene)
    assert len(candidates) == 7 * 17 * 4
    assert candidates == generate_candidates(spec, scene)
    for robot in spec["robots"]:
        arm = load_local(robot)
        assert arm.points.shape == (6, 3)
        assert max(compare_mjcf_fk(robot, arm.limits.mean(axis=1))) < 1e-9
        group = [candidate for candidate in candidates if candidate["robot"] == robot]
        assert len(group) == 68
        for candidate in group:
            for index in (2, 3, 4, 5):
                if candidate["span_m"][str(index)] == 0:
                    assert str(index) not in candidate["anchor_span_scales"]
        assert all(candidate["sample_index"] == 0
                   for candidate in group[:4])


def test_candidate_changes_only_arm_geometry_and_parking():
    scene = json.loads(SCENE.read_text(encoding="utf-8"))
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    candidate = generate_candidates(spec, scene)[-1]
    derived = candidate_scene(scene, SCENE, candidate)
    assert derived["robots"] == [candidate["robot"]]
    assert derived["tasks"]["core_2026"] == scene["tasks"]["core_2026"]
    assert derived["tasks"]["pickup_2026"] == scene["tasks"]["pickup_2026"]
    assert derived["obstacles"] == scene["obstacles"]
    assert derived["length_variants"][0]["anchor_span_scales"] == candidate["anchor_span_scales"]
    assert derived["parking"]["candidates"] == [candidate["parking"]]


def test_willow_urdf_absolute_span_sweep_includes_baseline_and_xarm_main_spans():
    scene = json.loads(WILLOW_SCENE.read_text(encoding="utf-8"))
    spec = json.loads(WILLOW_SPEC.read_text(encoding="utf-8"))
    candidates = generate_candidates(spec, scene)
    assert len(candidates) == (1 + 1 + 32) * 4
    assert {candidate["robot"] for candidate in candidates} == {"willow0907"}
    assert {candidate["sampling_kind"] for candidate in candidates} == {
        "baseline", "explicit_1", "sobol"
    }
    arm = load_local("willow0907")
    assert max(compare_urdf_fk("willow0907", arm.limits.mean(axis=1))) < 1e-9
    explicit = [candidate for candidate in candidates
                if candidate["sampling_kind"] == "explicit_1"]
    assert len(explicit) == 4
    assert abs(explicit[0]["span_m"]["2"] - 0.2880214074850155) < 1e-12
    assert abs(explicit[0]["span_m"]["3"] - 0.41083439937206646) < 1e-12
    for candidate in candidates:
        if candidate["sampling_kind"] != "sobol":
            continue
        for index, bounds in spec["sampling"]["span_bounds_m"].items():
            assert bounds[0] <= candidate["span_m"][index] <= bounds[1]


def test_module_stress_declares_nine_distinct_target_poses():
    spec = json.loads((CONFIGS / "module_2027.stress.synthetic.json").read_text(encoding="utf-8"))
    cases = spec["cases"]
    assert len(cases) == 9
    assert len({case["case_id"] for case in cases}) == 9
    assert len({(tuple(case["delta_xyz_m"]), case["yaw_delta_rad"]) for case in cases}) == 9
