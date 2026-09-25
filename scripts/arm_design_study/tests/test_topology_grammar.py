import json
from dataclasses import replace

import numpy as np
import pytest

from scripts.arm_design_study.topology_design import GENERATED_ARM_NAMES, load_generated_arm
from scripts.arm_design_study.topology_grammar import (
    GrammarSpec, axis_words, canonical_geometry_key, generate_topology_catalog,
    load_grammar_arm,
)


def test_catalog_is_deterministic_and_covers_existing_templates():
    first = generate_topology_catalog()
    second = generate_topology_catalog()
    assert json.dumps(first.to_dict(), sort_keys=True) == json.dumps(second.to_dict(), sort_keys=True)
    assert first.attempted == 324
    assert len(first.candidates) == 134
    assert first.attempted == len(first.candidates) + sum(first.rejected.values())
    assert set(first.template_matches) == set(GENERATED_ARM_NAMES)
    assert len({candidate.topology_id for candidate in first.candidates}) == len(first.candidates)
    assert len({candidate.geometry_id for candidate in first.candidates}) == len(first.candidates)
    assert sum(len(candidate.equivalent_syntaxes) for candidate in first.candidates) == first.rejected["duplicate_screw_geometry"]

    by_id = {candidate.topology_id: candidate for candidate in first.candidates}
    for name, topology_id in first.template_matches.items():
        original = load_generated_arm(name)
        generated = by_id[topology_id].arm
        assert load_grammar_arm(topology_id, first).name == topology_id
        assert canonical_geometry_key(generated) == canonical_geometry_key(original)
        for q in (np.zeros(6), np.array([0.31, -0.52, 0.47, -0.38, 0.61, -0.29])):
            assert np.allclose(generated.fk(q), original.fk(q), atol=1e-10)
    with pytest.raises(ValueError, match="unknown grammar topology ID"):
        load_grammar_arm("orth6r_missing", first)


def test_screw_line_key_ignores_axis_sign_and_anchor_shift_along_axis():
    arm = load_generated_arm("rm2p_spherical_wrist")
    axes = arm.axes.copy()
    axes[[0, 3]] *= -1
    points = arm.points + arm.axes * np.array([0.07, -0.03, 0.04, 0.09, -0.02, 0.01])[:, None]
    same_lines = replace(arm, axes=axes, points=points)
    assert canonical_geometry_key(same_lines) == canonical_geometry_key(arm)
    moved_off_axis = points.copy()
    moved_off_axis[2, 0] += 0.01
    assert canonical_geometry_key(replace(arm, points=moved_off_axis)) != canonical_geometry_key(arm)


def test_every_accepted_route_is_built_from_straight_orthogonal_primitives():
    catalog = generate_topology_catalog()
    assert len(axis_words()) == 54
    assert all(candidate.axis_word[0] == "z" and candidate.axis_word[-1] == "x"
               for candidate in catalog.candidates)
    for candidate in catalog.candidates:
        assert candidate.full_rank_probes >= 2
        assert "coaxial" not in candidate.relations
        assert sum(route.kind == "short_dogleg" for route in candidate.routes) <= 1
        for route in candidate.routes:
            for start, end in zip(route.vertices_m[:-1], route.vertices_m[1:]):
                assert np.count_nonzero(np.abs(np.asarray(end) - start) > 1e-9) == 1


def test_topology_id_stays_fixed_when_lengths_change_but_geometry_id_changes():
    baseline = generate_topology_catalog()
    resized = generate_topology_catalog(GrammarSpec(upper_arm_m=0.320, forearm_m=0.410))
    assert resized.template_matches == {}
    key = ("serial_spherical_wrist", tuple("zyyxyx"))
    original = next(item for item in baseline.candidates if (item.layout, item.axis_word) == key)
    changed = next(item for item in resized.candidates if (item.layout, item.axis_word) == key)
    assert original.topology_id == changed.topology_id
    assert original.geometry_id != changed.geometry_id
    assert not np.allclose(original.arm.points, changed.arm.points)


def test_whitelisting_coaxial_pair_cannot_bypass_six_dof_rank_filter():
    spec = GrammarSpec(allowed_adjacent_coaxial=((4, 5), (5, 6)))
    catalog = generate_topology_catalog(spec)
    assert catalog.rejected["jacobian_rank"] >= 18
    assert all("coaxial" not in candidate.relations for candidate in catalog.candidates)


@pytest.mark.parametrize("changes", [{"upper_arm_m": 0.0}, {"small_offset_m": float("nan")},
                                     {"allowed_adjacent_coaxial": ((1, 6),)}])
def test_invalid_grammar_specs_fail(changes):
    with pytest.raises(ValueError):
        GrammarSpec(**changes)
