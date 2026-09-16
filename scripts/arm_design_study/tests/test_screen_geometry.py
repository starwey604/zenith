import numpy as np

from scripts.arm_design_study.bayonet import Bayonet
from scripts.arm_design_study.bayonet_trajectory import generate_bayonet_path
from scripts.arm_design_study.chassis import ChassisMount
from scripts.arm_design_study.collision import (Box, Capsule, box_sat_clearance, chassis_box,
                                                collision_scan, robot_capsules,
                                                segment_box_distance, segment_segment_distance)
from scripts.arm_design_study.frames import inverse, transform, yaw_pose
from scripts.arm_design_study.length_design import scale_anchor_spans
from scripts.arm_design_study.model_import import load_local
from scripts.arm_design_study.parking import parking_legality
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_segment_distances_handle_crossing_parallel_and_box_surface():
    assert np.isclose(segment_segment_distance(np.array([-1, 0, 0]), np.array([1, 0, 0]),
                                               np.array([0, -1, 0]), np.array([0, 1, 0])), 0)
    assert np.isclose(segment_segment_distance(np.array([0, 0, 0]), np.array([1, 0, 0]),
                                               np.array([0, 1, 0]), np.array([1, 1, 0])), 1)
    box = Box("test", transform(), np.array([0.5, 0.5, 0.5]))
    assert np.isclose(segment_box_distance(np.array([-2, 0, 0]), np.array([2, 0, 0]), box), 0)
    assert np.isclose(segment_box_distance(np.array([-2, 1.5, 0]), np.array([2, 1.5, 0]), box), 1)


def test_rotated_box_sat_and_parking_footprint():
    polygon = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]])
    obstacle = Box("fixture", transform(translation=[0, 0, 0.1]), np.array([0.2, 0.2, 0.1]))
    illegal = ChassisMount(0.0, 0.0, 0.0, np.eye(4))
    legal = ChassisMount(0.7, 0.0, np.pi / 4, np.eye(4))
    assert parking_legality(illegal, np.array([0.1, 0.1, 0.1]), polygon, [obstacle])[0] is False
    assert parking_legality(legal, np.array([0.1, 0.1, 0.1]), polygon, [obstacle])[0] is True
    assert box_sat_clearance(chassis_box(legal, np.array([0.1, 0.1, 0.1])), obstacle) > 0


def test_stretched_arm_updates_capsule_span():
    arm = load_local("ur5e")
    long_arm = scale_anchor_spans(arm, {2: 1.15})
    mount = ChassisMount(0.0, 0.0, 0.0, np.eye(4))
    radii = np.full(7, 0.02)
    nominal = {part.name: part for part in robot_capsules(arm, mount, np.zeros(6), radii, 0.01, 0.04)}
    stretched = {part.name: part for part in robot_capsules(long_arm, mount, np.zeros(6), radii, 0.01, 0.04)}
    old = np.linalg.norm(nominal["link_2"].end - nominal["link_2"].start)
    new = np.linalg.norm(stretched["link_2"].end - stretched["link_2"].start)
    assert np.isclose(new, old * 1.15)
    assert np.isclose(stretched["link_2"].radius_m, nominal["link_2"].radius_m)


def test_tool_capsule_can_follow_a_fixed_flange_adapter_direction():
    arm = load_local("ur5e")
    mount = ChassisMount(0.0, 0.0, 0.0, np.eye(4))
    radii = np.full(7, 0.02)
    default = robot_capsules(arm, mount, np.zeros(6), radii, 0.01, 0.04)[-1]
    flipped = robot_capsules(arm, mount, np.zeros(6), radii, 0.01, 0.04,
                             np.array([0.0, 0.0, 1.0]))[-1]
    assert np.allclose(default.end - default.start, -(flipped.end - flipped.start))
    assert np.isclose(np.linalg.norm(flipped.end - flipped.start), 0.04)


def test_intended_tool_contact_is_local_exception():
    tool = Capsule("tool", np.array([0, 0, 1]), np.array([0, 0, 0]), 0.01, 7)
    chassis = Box("chassis", transform(translation=[2, 0, 0]), np.array([0.1, 0.1, 0.1]))
    fixture = Box("socket", transform(translation=[0, 0, 0.5]), np.array([0.1, 0.1, 0.1]), False)
    _, hit = collision_scan([tool], chassis, [fixture], "straight_insert", set())
    assert hit is not None and hit["part_b"] == "socket"
    _, hit = collision_scan([tool], chassis, [fixture], "straight_insert",
                            {("socket", "tool", "straight_insert")})
    assert hit is None


def test_bayonet_departure_keeps_locked_relative_pose_and_moves_module():
    interface = Bayonet.load(ROOT / "configs/bayonet_interface.synthetic_example.json")
    socket = yaw_pose(0.2, 0.3, 0.25) @ transform(translation=[0, 0, 0.6])
    flange_to_pin = transform(translation=[0, 0, -0.05])
    path = generate_bayonet_path(interface, socket, flange_to_pin,
                                 samples_per_phase=6, leave_distance_m=0.1)
    locked = next(point for point in path if point.phase == "locked")
    leave = [point for point in path if point.phase == "leave_table"]
    assert len(leave) == 5
    assert np.allclose(locked.world_module, socket)
    assert np.allclose(inverse(locked.world_module) @ locked.world_flange,
                       inverse(leave[-1].world_module) @ leave[-1].world_flange)
    assert np.isclose(np.linalg.norm(leave[-1].world_module[:3, 3] - socket[:3, 3]), 0.1)
