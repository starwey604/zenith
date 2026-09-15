from pathlib import Path
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from scripts.arm_design_study.bayonet import Bayonet
from scripts.arm_design_study.bayonet_trajectory import generate_bayonet_path
from scripts.arm_design_study.chassis import ChassisMount
from scripts.arm_design_study.frames import transform, inverse
from scripts.arm_design_study.model_import import load_local, compare_mjcf_fk
from scripts.arm_design_study.length_design import anchor_spans_m, scale_anchor_spans
from scripts.arm_design_study.task_2026 import core_assembly_path, energy_unit_pickup_path, follow_task_ik, TaskWaypoint

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name", ["xarm6", "ur5e"])
def test_poe_matches_reference_mjcf(name):
    arm = load_local(name)
    rng = np.random.default_rng(14)
    for _ in range(3):
        q = rng.uniform(arm.limits[:, 0] * 0.3, arm.limits[:, 1] * 0.3)
        position, rotation = compare_mjcf_fk(name, q)
        assert position < 1e-8
        assert rotation < 1e-7


@pytest.mark.parametrize("name", ["xarm6", "ur5e"])
def test_geometric_jacobian_matches_fk_difference(name):
    arm = load_local(name)
    q = np.clip(np.array([0.1, -0.2, 0.1, -0.1, 0.2, 0.1]),
                arm.limits[:, 0] + 0.1, arm.limits[:, 1] - 0.1)
    jac = arm.jacobian(q)
    step = 1e-6
    initial = arm.fk(q)
    for j in range(6):
        moved = q.copy()
        moved[j] += step
        next_pose = arm.fk(moved)
        linear = (next_pose[:3, 3] - initial[:3, 3]) / step
        angular = Rotation.from_matrix(next_pose[:3, :3] @ initial[:3, :3].T).as_rotvec() / step
        assert np.linalg.norm(np.r_[linear, angular] - jac[:, j]) < 2e-5


def test_chassis_and_mount_composition():
    arm = load_local("ur5e")
    mount = ChassisMount(1.0, -0.5, np.pi / 2,
                         transform(translation=np.array([0.2, 0.0, 0.4])))
    q = np.zeros(6)
    world = mount.world_flange(arm, q)
    assert np.allclose(inverse(mount.world_to_arm()) @ world, arm.fk(q))
    assert np.allclose(mount.world_to_arm()[:3, 3], [1.0, -0.3, 0.4])


def test_ur5e_limits_use_authored_radians():
    arm = load_local("ur5e")
    assert np.allclose(arm.limits[0], [-6.28319, 6.28319])
    assert np.allclose(arm.limits[2], [-3.1415, 3.1415])


def test_stretch_one_span_preserves_axis_layout_and_scales_anchor_distance():
    arm = load_local("ur5e")
    original = anchor_spans_m(arm)
    stretched = scale_anchor_spans(arm, {2: 1.15})
    assert np.allclose(stretched.axes, arm.axes)
    assert np.isclose(anchor_spans_m(stretched)[2], original[2] * 1.15)
    assert np.allclose(stretched.points[:2], arm.points[:2])
    assert not np.allclose(stretched.home_flange[:3, 3], arm.home_flange[:3, 3])
    assert np.allclose(stretched.fk(np.zeros(6)), stretched.home_flange)


def test_bayonet_straight_then_turn_and_unlock():
    interface = Bayonet.load(ROOT / "configs/bayonet_interface.synthetic_example.json")
    points = generate_bayonet_path(interface, np.eye(4), samples_per_phase=8)
    assert points[-1].phase == "locked"
    assert not interface.straight_pull_allowed(points[-1].relative_pose)
    # A turn attempted before reaching the stop is rejected.
    premature = transform(Rotation.from_euler("z", 0.1).as_matrix(), [0.0, 0.0, -0.005])
    good, reason, _ = interface.check_pose(premature, "bayonet_turn")
    assert not good and reason == "premature_turn"
    # Reversing the turn opens the straight-slot extraction route.
    unlocked = transform(translation=[0.0, 0.0, -interface.stop_m])
    good, _, _ = interface.check_pose(unlocked, "straight_insert")
    assert good
    assert interface.straight_pull_allowed(unlocked)


def test_unknown_interface_dimensions_fail_explicitly():
    with pytest.raises(ValueError, match="missing_input: guide.lead_cone_half_angle_rad"):
        Bayonet.load(ROOT / "configs/bayonet_interface.template.json")


def test_2026_core_path_has_rule_translations_and_explicit_p_q_rotations():
    start = np.eye(4)
    path = core_assembly_path(start, np.zeros(3), np.array([0, 1, 0]),
                              np.zeros(3), np.array([1, 0, 0]),
                              -np.pi / 2, np.pi / 4, samples_per_phase=3)
    assert len(path) == 12
    insert_end = path[2].world_tool
    rise_end = path[5].world_tool
    assert np.allclose(insert_end[:3, 3], [-0.1, 0, 0])
    assert np.allclose(rise_end[:3, 3], [-0.1, 0, 0.1])
    assert np.isclose(np.linalg.norm(path[8].world_tool[:3, 3]), np.linalg.norm(rise_end[:3, 3]))
    assert not np.allclose(path[-1].world_tool[:3, :3], path[8].world_tool[:3, :3])


def test_2026_pickup_stays_on_specified_symmetry_axis():
    grasp = transform(translation=[0.5, 0.2, 0.6])
    axis = np.array([0.0, 1.0, 0.0])
    path = energy_unit_pickup_path(grasp, axis, 0.08, 0.12, samples_per_phase=4)
    assert len(path) == 9
    assert np.allclose(path[0].world_tool[:3, 3], [0.5, 0.28, 0.6])
    assert np.allclose(path[-1].world_tool[:3, 3], [0.5, 0.32, 0.6])
    assert all(np.allclose(point.world_tool[:3, :3], grasp[:3, :3]) for point in path)


def test_task_tool_offset_maps_back_to_same_flange_for_ik():
    arm = load_local("ur5e")
    mount = ChassisMount(0.0, 0.0, 0.0, transform(translation=[0, 0, 0.4]))
    q = np.array([-np.pi / 2, -np.pi / 2, np.pi / 2, -np.pi / 2, -np.pi / 2, 0.0])
    offset = transform(translation=[0.0, 0.0, 0.1])
    tool = mount.world_flange(arm, q) @ offset
    records, failure = follow_task_ik(arm, mount, [TaskWaypoint("known_pose", tool, 1.0)], offset, q)
    assert failure is None
    assert len(records) == 1
    assert np.allclose(records[0]["q_rad"], q, atol=1e-5)
