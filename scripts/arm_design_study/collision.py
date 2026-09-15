"""Coarse geometry for design screening; no contact-force integration."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .chassis import ChassisMount
from .frames import transform, yaw_pose
from .sixr import SixR


@dataclass(frozen=True)
class Capsule:
    name: str
    start: np.ndarray
    end: np.ndarray
    radius_m: float
    chain_index: int


@dataclass(frozen=True)
class Box:
    name: str
    pose: np.ndarray
    half_m: np.ndarray
    blocks_chassis: bool = True
    active_phases: tuple[str, ...] = ()

    @classmethod
    def from_config(cls, data: dict) -> "Box":
        center = np.asarray(data["center_m"], dtype=float)
        half = np.asarray(data["half_extents_m"], dtype=float)
        if center.shape != (3,) or half.shape != (3,) or not np.isfinite(np.r_[center, half]).all() or np.any(half <= 0):
            raise ValueError("obstacle center/half extents must be finite 3-vectors; extents positive")
        yaw = float(data.get("yaw_rad", 0.0))
        if not np.isfinite(yaw):
            raise ValueError("obstacle yaw must be finite")
        pose = yaw_pose(float(center[0]), float(center[1]), yaw)
        pose[2, 3] = center[2]
        return cls(str(data["name"]), pose, half, bool(data.get("blocks_chassis", True)),
                   tuple(data.get("active_phases", ())))


def segment_segment_distance(a: np.ndarray, b: np.ndarray, c: np.ndarray, d: np.ndarray) -> float:
    """Exact closest distance between two finite 3-D line segments."""
    u, v, w = b - a, d - c, a - c
    aa, bb, cc = float(u @ u), float(u @ v), float(v @ v)
    dd, ee = float(u @ w), float(v @ w)
    candidates: list[tuple[float, float]] = []
    if aa < 1e-16 and cc < 1e-16:
        return float(np.linalg.norm(a - c))
    if aa < 1e-16:
        candidates.append((0.0, float(np.clip(ee / cc, 0, 1))))
    elif cc < 1e-16:
        candidates.append((float(np.clip(-dd / aa, 0, 1)), 0.0))
    else:
        denom = aa * cc - bb * bb
        if denom > 1e-16:
            s, t = (bb * ee - cc * dd) / denom, (aa * ee - bb * dd) / denom
            if 0 <= s <= 1 and 0 <= t <= 1:
                candidates.append((s, t))
        candidates.extend(((0.0, float(np.clip(ee / cc, 0, 1))),
                           (1.0, float(np.clip((ee + bb) / cc, 0, 1))),
                           (float(np.clip(-dd / aa, 0, 1)), 0.0),
                           (float(np.clip((bb - dd) / aa, 0, 1)), 1.0)))
    return min(float(np.linalg.norm((a + s * u) - (c + t * v))) for s, t in candidates)


def segment_box_distance(start: np.ndarray, end: np.ndarray, box: Box) -> float:
    """Exact centre-line distance to an oriented box via piecewise quadratics."""
    rotation = box.pose[:3, :3]
    a = rotation.T @ (start - box.pose[:3, 3])
    b = rotation.T @ (end - box.pose[:3, 3])
    delta = b - a
    cuts = [0.0, 1.0]
    for j in range(3):
        if abs(delta[j]) > 1e-14:
            for bound in (-box.half_m[j], box.half_m[j]):
                value = (bound - a[j]) / delta[j]
                if 0 < value < 1:
                    cuts.append(float(value))
    cuts = sorted(set(cuts))
    trial = cuts.copy()
    for left, right in zip(cuts[:-1], cuts[1:]):
        mid = a + delta * ((left + right) / 2)
        active = np.abs(mid) > box.half_m
        if not active.any():
            trial.append((left + right) / 2)
            continue
        bound = np.sign(mid[active]) * box.half_m[active]
        offset = a[active] - bound
        speed = delta[active]
        denominator = float(speed @ speed)
        if denominator > 1e-16:
            trial.append(float(np.clip(-(offset @ speed) / denominator, left, right)))
    return min(float(np.linalg.norm(np.maximum(np.abs(a + delta * t) - box.half_m, 0.0))) for t in trial)


def box_sat_clearance(a: Box, b: Box) -> float:
    """SAT signed separation proxy: positive separated, nonpositive overlap."""
    ra, rb = a.pose[:3, :3], b.pose[:3, :3]
    axes = [ra[:, j] for j in range(3)] + [rb[:, j] for j in range(3)]
    for i in range(3):
        for j in range(3):
            cross = np.cross(ra[:, i], rb[:, j])
            norm = np.linalg.norm(cross)
            if norm > 1e-9:
                axes.append(cross / norm)
    centres = b.pose[:3, 3] - a.pose[:3, 3]
    gaps = []
    for axis in axes:
        extent_a = float(np.abs(axis @ ra) @ a.half_m)
        extent_b = float(np.abs(axis @ rb) @ b.half_m)
        gaps.append(float(abs(axis @ centres) - extent_a - extent_b))
    return max(gaps)


def robot_capsules(arm: SixR, mount: ChassisMount, q: np.ndarray,
                   radii_m: np.ndarray, tool_radius_m: float,
                   tool_length_m: float) -> list[Capsule]:
    """Each stretched anchor-to-anchor span becomes a stretched capsule."""
    radii = np.asarray(radii_m, dtype=float)
    if radii.shape != (7,) or not np.isfinite(radii).all() or np.any(radii <= 0):
        raise ValueError("seven positive capsule radii required")
    if tool_radius_m <= 0 or tool_length_m <= 0:
        raise ValueError("tool radius/length must be positive")
    arm_pose = mount.world_to_arm()
    anchors = arm.joint_anchors(q)
    flange = arm.fk(q)
    local = [np.zeros(3)] + list(anchors) + [flange[:3, 3]]
    world = [(arm_pose @ np.r_[point, 1.0])[:3] for point in local]
    result = [Capsule(f"link_{j}", world[j], world[j + 1], float(radii[j]), j)
              for j in range(7) if np.linalg.norm(world[j + 1] - world[j]) > 1e-8]
    world_flange = arm_pose @ flange
    start = world_flange[:3, 3]
    end = start - world_flange[:3, 2] * tool_length_m
    result.append(Capsule("tool", start, end, tool_radius_m, 7))
    return result


def chassis_box(mount: ChassisMount, half_m: np.ndarray) -> Box:
    half = np.asarray(half_m, dtype=float)
    if half.shape != (3,) or np.any(half <= 0):
        raise ValueError("chassis half extents must be positive 3-vector")
    pose = yaw_pose(mount.x_m, mount.y_m, mount.yaw_rad)
    pose[2, 3] = half[2]
    return Box("chassis", pose, half)


def collision_scan(capsules: list[Capsule], chassis: Box, obstacles: list[Box],
                   phase: str, allowed_contacts: set[tuple[str, str, str]],
                   carried_box: Box | None = None) -> tuple[float, dict | None]:
    """Return lowest signed shape margin and the first colliding pair."""
    minimum = float("inf")
    hit = None
    def record(clearance: float, one: str, two: str) -> None:
        nonlocal minimum, hit
        if clearance < minimum:
            minimum = clearance
        if clearance <= 0 and hit is None:
            hit = {"part_a": one, "part_b": two, "clearance_proxy_m": clearance}
    for i, one in enumerate(capsules):
        for j, two in enumerate(capsules[i + 1:], start=i + 1):
            if j - i <= 2:
                continue  # adjacent nonzero bodies share joint/wrist volume
            record(segment_segment_distance(one.start, one.end, two.start, two.end)
                   - one.radius_m - two.radius_m, one.name, two.name)
    for capsule in capsules:
        if capsule.chain_index >= 2 and ("chassis", capsule.name, phase) not in allowed_contacts:
            record(segment_box_distance(capsule.start, capsule.end, chassis)
                   - capsule.radius_m, capsule.name, "chassis")
    for obstacle in obstacles:
        if obstacle.active_phases and phase not in obstacle.active_phases:
            continue
        for capsule in capsules:
            if (obstacle.name, capsule.name, phase) in allowed_contacts:
                continue
            record(segment_box_distance(capsule.start, capsule.end, obstacle)
                   - capsule.radius_m, capsule.name, obstacle.name)
        if obstacle.blocks_chassis and (obstacle.name, "chassis", phase) not in allowed_contacts:
            record(box_sat_clearance(chassis, obstacle), "chassis", obstacle.name)
        if carried_box is not None and (obstacle.name, carried_box.name, phase) not in allowed_contacts:
            record(box_sat_clearance(carried_box, obstacle), carried_box.name, obstacle.name)
    if carried_box is not None:
        for index, capsule in enumerate(capsules):
            if index >= len(capsules) - 3:
                continue  # attachment and nearest wrist bodies overlap by design
            record(segment_box_distance(capsule.start, capsule.end, carried_box)
                   - capsule.radius_m, capsule.name, carried_box.name)
    return minimum, hit
