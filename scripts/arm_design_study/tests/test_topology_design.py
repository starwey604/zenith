import numpy as np
import json
from pathlib import Path

from scripts.arm_design_study.length_sweep_v2 import generate_candidates
from scripts.arm_design_study.model_import import load_local, model_reference_paths
from scripts.arm_design_study.topology_design import GENERATED_ARM_NAMES, relation_signature


def test_generated_topologies_are_distinct_full_rank_sixr_hypotheses():
    geometries = set()
    probe = np.array([0.31, -0.52, 0.47, -0.38, 0.61, -0.29])
    for name in GENERATED_ARM_NAMES:
        arm = load_local(name)
        assert arm.axes.shape == (6, 3)
        assert arm.points.shape == (6, 3)
        assert np.linalg.matrix_rank(arm.jacobian(probe), tol=1e-7) == 6
        assert len(relation_signature(arm)) == 5
        geometries.add((tuple(np.round(arm.axes.ravel(), 8)),
                        tuple(np.round(arm.points.ravel(), 8))))
        assert "synthetic constrained-topology" in arm.provenance
    assert len(geometries) == len(GENERATED_ARM_NAMES)


def test_generated_topologies_have_no_external_model_dependency():
    assert model_reference_paths(list(GENERATED_ARM_NAMES)) == ()


def test_topology_pilot_runs_common_scene_and_full_candidate_matrix():
    root = Path(__file__).resolve().parents[1]
    scene = json.loads((root / "configs/benchmark.topology_v1.chassis250.synthetic.json").read_text())
    spec = json.loads((root / "configs/length_sweep.topology_v1.json").read_text())
    candidates = generate_candidates(spec, scene)
    assert len(candidates) == 5 * 3 * 4
    assert set(scene["robots"]) == set(GENERATED_ARM_NAMES)
    assert {tuple(scene["geometry"]["link_capsule_radii_by_robot_m"][name])
            for name in GENERATED_ARM_NAMES} == {
                (0.055, 0.055, 0.048, 0.042, 0.035, 0.030, 0.025)
            }
    assert all(candidate["sampling_kind"] in {"baseline", "sobol"}
               for candidate in candidates)
