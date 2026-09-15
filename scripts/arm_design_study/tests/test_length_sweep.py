import json
from pathlib import Path

import pytest

from scripts.arm_design_study.length_sweep import (
    _artifact_path, candidate_scene, generate_candidates, input_manifest, read_completed,
    validate_spec,
)
from scripts.arm_design_study.length_sweep_plots import pareto_2d


ROOT = Path(__file__).resolve().parents[1]
SCENE_PATH = ROOT / "configs/benchmark.synthetic.json"
SPEC_PATH = ROOT / "configs/length_sweep.v1.json"
TASK_PATH = ROOT / "configs/storage_2026.stress.synthetic.json"


def test_full_grid_generates_unique_candidates_and_only_changes_design_fields():
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    scene = json.loads(SCENE_PATH.read_text(encoding="utf-8"))
    candidates = generate_candidates(spec, scene)
    assert len(candidates) == 100
    assert len({item["candidate_id"] for item in candidates}) == 100
    assert {item["parking_id"] for item in candidates} == {"rear_left", "rear_center"}
    assert {item["robot"] for item in candidates} == {"xarm6", "ur5e"}
    for item in (candidates[0], candidates[24], candidates[50], candidates[-1]):
        derived = candidate_scene(scene, SCENE_PATH, item)
        assert derived["tasks"]["core_2026"] == scene["tasks"]["core_2026"]
        assert derived["tasks"]["pickup_2026"] == scene["tasks"]["pickup_2026"]
        assert derived["obstacles"] == scene["obstacles"]
        assert derived["geometry"] == scene["geometry"]
        assert derived["random_seed"] == scene["random_seed"]
        assert Path(derived["tasks"]["module_2027"]["interface_file"]).read_bytes() == (
            SCENE_PATH.parent / scene["tasks"]["module_2027"]["interface_file"]).read_bytes()
        assert derived["length_variants"][0]["anchor_span_scales"] == {
            "2": item["factor2"], "3": item["factor3"]}
    spec["max_workers"] = 3
    with pytest.raises(ValueError, match="one or two"):
        validate_spec(spec, scene)


def test_checkpoint_requires_exact_inputs_and_candidate(tmp_path):
    manifest = input_manifest(SPEC_PATH, SCENE_PATH, TASK_PATH)
    scene = json.loads(SCENE_PATH.read_text(encoding="utf-8"))
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    candidate = generate_candidates(spec, scene)[0]
    path = _artifact_path(tmp_path, candidate["candidate_id"])
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"schema_version": 1, "input_key": manifest["input_key"],
                                "candidate": candidate, "summary": {"candidate_id": candidate["candidate_id"]}}),
                    encoding="utf-8")
    assert read_completed(tmp_path, manifest, [candidate])[candidate["candidate_id"]]["candidate_id"] == candidate["candidate_id"]
    altered = dict(manifest)
    altered["input_key"] = "changed"
    with pytest.raises(ValueError, match="stale or mismatched checkpoint"):
        read_completed(tmp_path, altered, [candidate])


def test_fixed_seed_sobol_candidate_set_contains_baseline():
    scene = json.loads(SCENE_PATH.read_text(encoding="utf-8"))
    spec = json.loads((ROOT / "configs/length_sweep.sobol.template.json").read_text(encoding="utf-8"))
    candidates = generate_candidates(spec, scene)
    assert candidates == generate_candidates(spec, scene)
    assert len(candidates) == 68
    assert len({item["candidate_id"] for item in candidates}) == 68
    assert sum(item["factor2"] == item["factor3"] == 1.0 for item in candidates) == 4
    assert all(0.75 <= item["factor2"] <= 1.25 and 0.75 <= item["factor3"] <= 1.25
               for item in candidates)


def test_pareto_keeps_tradeoffs_and_requires_module_geometry():
    rows = [{"candidate_id": "a", "storage_balanced_fraction": 0.8,
             "pickup_complete": 60, "pickup_total": 72, "module_complete": True},
            {"candidate_id": "b", "storage_balanced_fraction": 0.9,
             "pickup_complete": 55, "pickup_total": 72, "module_complete": True},
            {"candidate_id": "c", "storage_balanced_fraction": 0.7,
             "pickup_complete": 58, "pickup_total": 72, "module_complete": True},
            {"candidate_id": "d", "storage_balanced_fraction": 1.0,
             "pickup_complete": 72, "pickup_total": 72, "module_complete": False}]
    assert pareto_2d(rows) == {"a", "b"}
