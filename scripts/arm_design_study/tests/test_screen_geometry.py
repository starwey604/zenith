import numpy as np
from scripts.arm_design_study.chassis import ChassisMount
from scripts.arm_design_study.collision import Box, Capsule, box_sat_clearance, chassis_box, collision_scan, segment_box_distance, segment_segment_distance
from scripts.arm_design_study.frames import transform
from scripts.arm_design_study.parking import parking_legality

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


def test_intended_tool_contact_is_local_exception():
    tool = Capsule("tool", np.array([0, 0, 1]), np.array([0, 0, 0]), 0.01, 7)
    chassis = Box("chassis", transform(translation=[2, 0, 0]), np.array([0.1, 0.1, 0.1]))
    fixture = Box("socket", transform(translation=[0, 0, 0.5]), np.array([0.1, 0.1, 0.1]), False)
    _, hit = collision_scan([tool], chassis, [fixture], "straight_insert", set())
    assert hit is not None and hit["part_b"] == "socket"
    _, hit = collision_scan([tool], chassis, [fixture], "straight_insert",
                            {("socket", "tool", "straight_insert")})
    assert hit is None
