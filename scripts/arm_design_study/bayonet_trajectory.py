"""Workspace path for a stationary workbench socket and moving wrist pin."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Callable
import numpy as np
from scipy.spatial.transform import Rotation

from .bayonet import Bayonet
from .frames import transform, inverse
from .chassis import ChassisMount
from .sixr import SixR


@dataclass(frozen=True)
class PathPoint:
    phase: str
    relative_pose: np.ndarray  # T_D_M
    world_flange: np.ndarray   # target T_W_F
    depth_m: float
    phase_rad: float
    world_module: np.ndarray | None = None  # D frame, stationary until leave_table


class IKPoseTarget(Protocol):
    phase: str
    world_flange: np.ndarray
    depth_m: float | None
    phase_rad: float | None


def generate_bayonet_path(interface: Bayonet, world_socket: np.ndarray,
                          flange_to_pin: np.ndarray | None = None,
                          samples_per_phase: int = 16,
                          leave_distance_m: float = 0.0) -> list[PathPoint]:
    """No invented contact time law; samples are geometric waypoints."""
    if samples_per_phase < 2:
        raise ValueError("at least two samples per phase")
    if leave_distance_m < 0:
        raise ValueError("leave_distance_m cannot be negative")
    flange_to_pin = np.eye(4) if flange_to_pin is None else flange_to_pin
    p, g = interface.data["pins_and_slots"], interface.data["guide"]
    initial_s = -0.8 * g["lead_cone_depth_m"]
    start = g["key_start_angle_rad"]
    phases = [
        ("approach", np.linspace(initial_s, -0.25 * g["lead_cone_depth_m"], samples_per_phase), np.full(samples_per_phase, start)),
        ("cone_align", np.linspace(-0.25 * g["lead_cone_depth_m"], 0.0, samples_per_phase), np.full(samples_per_phase, start)),
        ("key_align", np.zeros(samples_per_phase), np.full(samples_per_phase, start)),
        ("straight_insert", np.linspace(0.0, interface.stop_m, samples_per_phase), np.full(samples_per_phase, start)),
        ("bayonet_turn", np.full(samples_per_phase, interface.stop_m), np.linspace(start, start + interface.lock_angle_rad, samples_per_phase)),
        ("locked", np.array([interface.stop_m]), np.array([start + interface.lock_angle_rad])),
    ]
    result = []
    for phase, depths, angles in phases:
        for s, theta in zip(depths, angles):
            relative = transform(Rotation.from_euler("z", theta).as_matrix(), np.array([0.0, 0.0, -s]))
            valid, reason, _ = interface.check_pose(relative, phase)
            if not valid:
                raise ValueError(f"generated path invalid at {phase}: {reason}")
            target_flange = world_socket @ relative @ inverse(flange_to_pin)
            result.append(PathPoint(phase, relative, target_flange, float(s), float(theta), world_socket.copy()))
    if leave_distance_m > 0:
        locked_relative = result[-1].relative_pose
        for distance in np.linspace(0.0, leave_distance_m, samples_per_phase)[1:]:
            # After the workbench releases the module, D and M move together.
            # Their locked relative pose remains constant during withdrawal.
            world_module = world_socket @ transform(translation=[0.0, 0.0, float(distance)])
            world_flange = world_module @ locked_relative @ inverse(flange_to_pin)
            result.append(PathPoint("leave_table", locked_relative.copy(), world_flange,
                                    interface.stop_m, start + interface.lock_angle_rad,
                                    world_module))
    return result


def follow_ik(arm: SixR, mount: ChassisMount, path: list[IKPoseTarget], seed: np.ndarray,
              max_joint_step_rad: float = 0.5, random_seed: int = 17,
              quality_fn: Callable[[np.ndarray, int, IKPoseTarget], float] | None = None) -> tuple[list[dict], dict | None]:
    """Try collision-free branches when a state-quality callback is supplied."""
    arm_from_world = inverse(mount.world_to_arm())
    q = np.asarray(seed, dtype=float)
    rng = np.random.default_rng(random_seed)
    records = []
    for index, point in enumerate(path):
        target_arm = arm_from_world @ point.world_flange
        attempts = [arm.ik(target_arm, q)]
        first_q, first_good, _ = attempts[0]
        first_quality = quality_fn(first_q, index, point) if first_good and quality_fn is not None else float("inf")
        if (not first_good or first_quality <= 0
                or (index > 0 and np.max(np.abs(first_q - q)) > max_joint_step_rad)):
            if index == 0:
                seeds = [np.clip(q + rng.normal(0.0, 0.9, 6),
                                 arm.limits[:, 0] + 1e-6, arm.limits[:, 1] - 1e-6)
                         for _ in range(6)]
                seeds.extend(rng.uniform(arm.limits[:, 0] + 1e-6,
                                         arm.limits[:, 1] - 1e-6) for _ in range(12))
            else:
                seeds = [np.clip(q + rng.normal(0.0, 0.12, 6),
                                 arm.limits[:, 0] + 1e-6, arm.limits[:, 1] - 1e-6)
                         for _ in range(6)]
            for candidate in seeds:
                trial = arm.ik(target_arm, candidate)
                attempts.append(trial)
                candidate_q, good, _ = trial
                if good and quality_fn is not None:
                    margin = quality_fn(candidate_q, index, point)
                    if margin > 0 and (index == 0 or np.max(np.abs(candidate_q - q)) <= max_joint_step_rad):
                        break
        accepted = [(candidate_q, error) for candidate_q, good, error in attempts if good]
        if not accepted:
            residual = min((error for _, _, error in attempts), key=np.linalg.norm)
            return records, {"index": index, "phase": point.phase, "reason": "ik_failed",
                             "seed_attempts": len(attempts),
                             "position_error_m": float(np.linalg.norm(residual[:3])),
                             "angle_error_rad": float(np.linalg.norm(residual[3:]))}
        if quality_fn is not None:
            scores = [(quality_fn(candidate_q, index, point), candidate_q, error)
                      for candidate_q, error in accepted]
            safe = [entry for entry in scores if entry[0] > 0]
            if safe:
                selected = min(safe, key=lambda entry: np.linalg.norm(entry[1] - q))
            else:
                selected = max(scores, key=lambda entry: entry[0])
            quality, q_new, residual = selected
        else:
            q_new, residual = min(accepted, key=lambda entry: np.linalg.norm(entry[0] - q))
            quality = None
        jump = float(np.max(np.abs(q_new - q)))
        if index > 0 and jump > max_joint_step_rad:
            return records, {"index": index, "phase": point.phase, "reason": "joint_jump",
                             "seed_attempts": len(attempts), "max_step_rad": jump}
        records.append({"index": index, "phase": point.phase, "q_rad": q_new.tolist(),
                        "ik_seed_attempts": len(attempts),
                        "selected_quality_proxy_m": float(quality) if quality is not None and np.isfinite(quality) else None,
                        "depth_m": point.depth_m, "phase_rad": point.phase_rad,
                        "world_flange": point.world_flange.tolist(),
                        "position_error_m": float(np.linalg.norm(residual[:3])),
                        "angle_error_rad": float(np.linalg.norm(residual[3:]))})
        if quality_fn is not None and quality is not None and quality <= 0:
            # Preserve this sampled state so the caller can report the exact
            # collision/expanded-limit pair, then stop unproductive searches.
            return records, {"index": index, "phase": point.phase,
                             "reason": "state_quality_failed",
                             "best_quality_proxy_m": float(quality),
                             "seed_attempts": len(attempts)}
        q = q_new
    return records, None
