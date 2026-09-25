import json

import numpy as np
import pytest

from scripts.arm_design_study.ik_solutions import (
    canonical_angles, enumerate_ik, lifted_angles, periodic_joint_distance,
)
from scripts.arm_design_study.model_import import load_local


def test_periodic_clustering_metric_and_distinct_lifts():
    physical = canonical_angles(np.array([0.2, np.pi, 0.1, -0.2, 0.3, 0.4]))
    same_pose = physical + np.array([2 * np.pi, 2 * np.pi, 0, 0, 0, 0])
    assert np.isclose(physical[1], -np.pi)
    assert periodic_joint_distance(physical, same_pose) < 1e-12
    assert periodic_joint_distance(physical, physical + np.array([0.1, 0, 0, 0, 0, 0])) > 0.09

    limits = np.array([[-7, 7], [-4, 4], [-1, 1], [-1, 1], [-1, 1], [-1, 1]], dtype=float)
    lifts = lifted_angles(physical, limits)
    assert len(lifts) == 6  # three J1 turns and two J2 turns
    assert all(np.all(q >= limits[:, 0]) and np.all(q <= limits[:, 1]) for q in lifts)
    assert all(periodic_joint_distance(q, physical) < 1e-12 for q in lifts)
    assert np.isclose(max(q[0] for q in lifts) - min(q[0] for q in lifts), 4 * np.pi)


def test_known_pose_recovers_branch_and_repeats_exactly():
    arm = load_local("ur5e")
    known = np.array([0.4, -1.0, 1.1, -0.8, 0.9, 0.2])
    target = arm.fk(known)
    first = enumerate_ik(arm, target, seeds=known)
    second = enumerate_ik(arm, target, seeds=known)

    assert json.dumps(first.to_dict(), sort_keys=True) == json.dumps(second.to_dict(), sort_keys=True)
    assert first.diagnostics.collision_checked is False
    assert first.diagnostics.stable
    assert first.diagnostics.converged_count >= first.diagnostics.independent_branches >= 1
    assert first.diagnostics.lifted_solutions > first.diagnostics.independent_branches
    assert min(periodic_joint_distance(known, branch.canonical_q_rad)
               for branch in first.branches) < 1e-5
    for branch in first.branches:
        for lift in branch.lifts:
            assert np.all(lift.q_rad >= arm.limits[:, 0] - 1e-9)
            assert np.all(lift.q_rad <= arm.limits[:, 1] + 1e-9)
            assert lift.position_error_m <= 1e-4
            assert lift.angle_error_rad <= 1e-3


@pytest.mark.parametrize("name", ["xarm6", "willow0907", "rm3p_spherical_wrist"])
def test_caller_seed_recovers_known_pose_across_axis_layouts(name):
    arm = load_local(name)
    midpoint = arm.limits.mean(axis=1)
    offset = np.array([0.23, -0.31, 0.19, -0.27, 0.35, -0.17])
    known = midpoint + np.minimum(arm.limits[:, 1] - midpoint, 1.0) * offset
    result = enumerate_ik(arm, arm.fk(known), seeds=known, sobol_tiers=(2, 4))
    assert any(periodic_joint_distance(known, branch.canonical_q_rad) < 1e-5
               for branch in result.branches)


def test_collision_callback_filters_each_lift_independently():
    arm = load_local("ur5e")
    known = np.array([-0.4, -1.0, 1.1, -0.8, 0.9, 0.2])
    allowed_j1 = known[0] + 2 * np.pi
    result = enumerate_ik(
        arm, arm.fk(known), seeds=known,
        collision_free=lambda q: abs(q[0] - allowed_j1) < 1e-3,
        sobol_tiers=(2, 4),
    )
    assert result.diagnostics.collision_checked
    assert result.diagnostics.collision_rejected_count > 0
    assert result.diagnostics.independent_branches >= 1
    assert all(abs(lift.q_rad[0] - allowed_j1) < 1e-3
               for branch in result.branches for lift in branch.lifts)
    assert any(periodic_joint_distance(known, branch.canonical_q_rad) < 1e-5
               for branch in result.branches)


def test_sobol_tier_counts_new_physical_branches_after_caller_seed():
    arm = load_local("ur5e")
    known = np.array([0.4, -1.0, 1.1, -0.8, 0.9, 0.2])
    result = enumerate_ik(arm, arm.fk(known), seeds=known, sobol_tiers=(2, 4))
    assert result.diagnostics.tiers[0].sobol_seeds == 2
    assert result.diagnostics.tiers[-1].sobol_seeds == 4
    assert sum(tier.new_branches for tier in result.diagnostics.tiers) <= result.diagnostics.independent_branches
    assert result.diagnostics.seed_count >= 4
