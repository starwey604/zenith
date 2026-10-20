import numpy as np
from scripts.arm_design_study.ik_solutions import canonical_angles, lifted_angles, periodic_joint_distance

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
