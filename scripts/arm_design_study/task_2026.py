"""Rule-shaped task waypoints; field poses and gripper offsets remain inputs."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .frames import axis_turn, transform
from .frames import inverse
from .bayonet_trajectory import follow_ik
from .chassis import ChassisMount
from .sixr import SixR


@dataclass(frozen=True)
class TaskWaypoint:
    phase: str
    world_tool: np.ndarray
    progress: float


@dataclass(frozen=True)
class ToolIKTarget:
    phase: str
    world_flange: np.ndarray
    depth_m: None = None
    phase_rad: None = None


def follow_task_ik(arm: SixR, mount: ChassisMount, path: list[TaskWaypoint],
                   flange_to_tool: np.ndarray, seed: np.ndarray,
                   random_seed: int = 17, quality_fn=None) -> tuple[list[dict], dict | None]:
    """Track the same world tool path for each arm and parked chassis."""
    offset = _pose(flange_to_tool, "flange_to_tool")
    targets = [ToolIKTarget(point.phase, point.world_tool @ inverse(offset)) for point in path]
    return follow_ik(arm, mount, targets, seed, random_seed=random_seed,
                     quality_fn=quality_fn)


def solve_task_ik_graph(arm: SixR, mount: ChassisMount, path: list[TaskWaypoint],
                        flange_to_tool: np.ndarray, seed: np.ndarray,
                        state_free=None, edge_free=None, **graph_options):
    """Search all enumerated IK branches for an existing tool-space task path.

    ``state_free`` receives the original TaskWaypoint; ``edge_free`` receives
    (interpolated_q, destination_index, fraction) for scene-aware checks.
    """
    from .ik_graph import solve_ik_path

    offset = _pose(flange_to_tool, "flange_to_tool")
    targets = [ToolIKTarget(point.phase, point.world_tool @ inverse(offset)) for point in path]
    state_check = (None if state_free is None else
                   lambda q, index, _target: state_free(q, index, path[index]))
    return solve_ik_path(arm, mount, targets, seed, state_free=state_check,
                         edge_free=edge_free, **graph_options)


def _unit_axis(axis: np.ndarray, label: str) -> np.ndarray:
    value = np.asarray(axis, dtype=float)
    if value.shape != (3,) or not np.isfinite(value).all() or not np.isclose(np.linalg.norm(value), 1.0, atol=1e-6):
        raise ValueError(f"{label} must be a directed unit vector in W")
    return value


def _pose(pose: np.ndarray, label: str) -> np.ndarray:
    value = np.asarray(pose, dtype=float)
    if (value.shape != (4, 4) or not np.isfinite(value).all()
            or not np.allclose(value[3], [0, 0, 0, 1])
            or not np.allclose(value[:3, :3].T @ value[:3, :3], np.eye(3), atol=1e-5)
            or np.linalg.det(value[:3, :3]) < 0.999):
        raise ValueError(f"{label} must be a finite 4x4 pose")
    return value


def core_assembly_path(pre_insert_world_tool: np.ndarray,
                       p_axis_origin_world: np.ndarray, p_axis_world: np.ndarray,
                       q_axis_origin_world: np.ndarray, q_axis_world: np.ndarray,
                       p_turn_signed_rad: float, q_target_signed_rad: float,
                       samples_per_phase: int = 16) -> list[TaskWaypoint]:
    """2026 sequence: -X 100mm, +Z 100mm, P upward 90°, Q target.

    P/Q line locations, sign of 'upward', and grasped-tool pose must be
    supplied from a measured station frame or labeled design assumption.
    The -X/+Z directions refer to the initial unit/tool local axes, as in
    arm_opt; verify those axes against the actual assembly-column frame.
    """
    start = _pose(pre_insert_world_tool, "pre_insert_world_tool")
    p_axis = _unit_axis(p_axis_world, "p_axis_world")
    q_axis = _unit_axis(q_axis_world, "q_axis_world")
    p_origin = np.asarray(p_axis_origin_world, dtype=float)
    q_origin = np.asarray(q_axis_origin_world, dtype=float)
    if p_origin.shape != (3,) or q_origin.shape != (3,) or not np.isfinite(np.r_[p_origin, q_origin]).all():
        raise ValueError("P/Q origins must be finite points in W")
    if samples_per_phase < 2:
        raise ValueError("at least two samples per phase")
    if not np.isclose(abs(p_turn_signed_rad), np.pi / 2, atol=1e-6):
        raise ValueError("P turn must be 90 degrees with explicitly chosen sign")
    if abs(q_target_signed_rad) > np.pi / 2 + 1e-7:
        raise ValueError("Q target exceeds the 2026 ±90-degree range")
    after_insert = start @ transform(translation=np.array([-0.1, 0.0, 0.0]))
    after_rise = after_insert @ transform(translation=np.array([0.0, 0.0, 0.1]))
    result: list[TaskWaypoint] = []
    for progress in np.linspace(0.0, 1.0, samples_per_phase):
        pose = start @ transform(translation=np.array([-0.1 * progress, 0.0, 0.0]))
        result.append(TaskWaypoint("insert_minus_x", pose, float(progress)))
    for progress in np.linspace(0.0, 1.0, samples_per_phase):
        pose = after_insert @ transform(translation=np.array([0.0, 0.0, 0.1 * progress]))
        result.append(TaskWaypoint("raise_plus_z", pose, float(progress)))
    for progress in np.linspace(0.0, 1.0, samples_per_phase):
        pose = axis_turn(p_axis, p_turn_signed_rad * progress, p_origin) @ after_rise
        result.append(TaskWaypoint("turn_p_90", pose, float(progress)))
    after_p = axis_turn(p_axis, p_turn_signed_rad, p_origin) @ after_rise
    for progress in np.linspace(0.0, 1.0, samples_per_phase):
        pose = axis_turn(q_axis, q_target_signed_rad * progress, q_origin) @ after_p
        result.append(TaskWaypoint("turn_q_target", pose, float(progress)))
    return result


def energy_unit_pickup_path(world_grasp_tool: np.ndarray, outward_symmetry_axis_world: np.ndarray,
                            approach_distance_m: float, extraction_distance_m: float,
                            samples_per_phase: int = 16) -> list[TaskWaypoint]:
    """Approach, grasp and extract one of six magnet-held units axially.

    Slot pose, free extraction sign and travel distances are measured inputs;
    10 N extra magnetic force is recorded for later dynamics, not solved here.
    """
    grasp = _pose(world_grasp_tool, "world_grasp_tool")
    outward = _unit_axis(outward_symmetry_axis_world, "outward_symmetry_axis_world")
    if approach_distance_m <= 0 or extraction_distance_m <= 0 or samples_per_phase < 2:
        raise ValueError("pickup distances must be positive and sampling at least two")
    result: list[TaskWaypoint] = []
    for progress in np.linspace(0.0, 1.0, samples_per_phase):
        pose = grasp.copy()
        pose[:3, 3] = grasp[:3, 3] + outward * approach_distance_m * (1.0 - progress)
        result.append(TaskWaypoint("approach_axis", pose, float(progress)))
    result.append(TaskWaypoint("grasp", grasp.copy(), 1.0))
    for progress in np.linspace(0.0, 1.0, samples_per_phase):
        pose = grasp.copy()
        pose[:3, 3] = grasp[:3, 3] + outward * extraction_distance_m * progress
        result.append(TaskWaypoint("extract_axis", pose, float(progress)))
    return result
