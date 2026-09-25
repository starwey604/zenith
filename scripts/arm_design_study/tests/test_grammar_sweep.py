import json

from scripts.arm_design_study.grammar_sweep import prepare_inputs
from scripts.arm_design_study.length_sweep_v2 import generate_candidates
from scripts.arm_design_study.model_import import load_local, model_reference_paths


def test_generated_topologies_run_the_same_baseline_matrix(tmp_path):
    scene_path, spec_path = prepare_inputs(tmp_path)
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    candidates = generate_candidates(spec, scene)

    assert len(scene["robots"]) == 134
    assert len(candidates) == 134 * 4
    assert {entry["sampling_kind"] for entry in candidates} == {"baseline"}
    assert {entry["parking_id"] for entry in candidates} == set(spec["parking_ids"])
    assert all(entry["anchor_span_scales"] == {
        str(index): 1.0 for index in entry["active_span_indices"]} for entry in candidates)
    assert len(model_reference_paths(scene["robots"])) == 1
    assert load_local(scene["robots"][0]).points.shape == (6, 3)
    assert prepare_inputs(tmp_path) == (scene_path, spec_path)


def test_generated_length_samples_include_shorter_and_longer_designs(tmp_path):
    scene_path, spec_path = prepare_inputs(tmp_path, sobol_sample_count=2)
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    candidates = generate_candidates(spec, scene)
    assert len(candidates) == 134 * 3 * 4
    assert any(any(value < 1 for value in entry["anchor_span_scales"].values())
               for entry in candidates)
    assert any(any(value > 1 for value in entry["anchor_span_scales"].values())
               for entry in candidates)


def test_workstation_worker_cap_is_frozen_in_run_spec(tmp_path):
    scene_path, spec_path = prepare_inputs(tmp_path, max_workers=20,
                                           reserve_available_memory_gib=4.0)
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    assert spec["max_workers"] == 20
    assert spec["reserve_available_memory_gib"] == 4.0
    assert len(generate_candidates(spec, scene)) == 536


def test_followup_length_sweep_can_select_generated_topologies(tmp_path):
    from scripts.arm_design_study.topology_grammar import generate_topology_catalog

    selected = tuple(candidate.topology_id
                     for candidate in generate_topology_catalog().candidates[:2])
    scene_path, spec_path = prepare_inputs(tmp_path, sobol_sample_count=8,
                                           robot_ids=selected,
                                           length_factor_bounds=(0.75, 1.25))
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    assert scene["robots"] == list(selected)
    assert len(generate_candidates(spec, scene)) == 2 * 9 * 4
    assert spec["sampling"]["factor_bounds"] == [0.75, 1.25]
