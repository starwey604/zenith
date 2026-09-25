"""Deterministic numerical IK branch enumeration for one six-axis flange pose.

Branches are physical joint poses modulo 2*pi.  Lifts retain every equivalent
angle vector inside the authored limits, so a later path search can measure
actual joint travel without wrapping away full revolutions.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Callable, Sequence

import numpy as np
from scipy.stats import qmc

from .sixr import SixR


TAU = 2.0 * np.pi
CollisionFree = Callable[[np.ndarray], bool]


def canonical_angles(q: np.ndarray) -> np.ndarray:
    """Represent revolute angles in [-pi, pi), including the pi boundary."""
    return (np.asarray(q, dtype=float) + np.pi) % TAU - np.pi


def periodic_joint_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Largest joint difference after identifying angles separated by 2*pi."""
    return float(np.max(np.abs(canonical_angles(np.asarray(a) - np.asarray(b)))))


def lifted_angles(canonical_q: np.ndarray, limits: np.ndarray) -> tuple[np.ndarray, ...]:
    """All joint vectors equivalent to canonical_q and inside finite limits."""
    canonical_q = np.asarray(canonical_q, dtype=float)
    limits = np.asarray(limits, dtype=float)
    if canonical_q.shape != (6,) or limits.shape != (6, 2):
        raise ValueError("expected six joint angles and six limit pairs")
    choices = []
    for angle, (lower, upper) in zip(canonical_q, limits):
        first = int(np.ceil((lower - angle - 1e-10) / TAU))
        last = int(np.floor((upper - angle + 1e-10) / TAU))
        choices.append([angle + TAU * turn for turn in range(first, last + 1)
                        if lower - 1e-9 <= angle + TAU * turn <= upper + 1e-9])
    return tuple(np.asarray(q, dtype=float) for q in product(*choices))


@dataclass(frozen=True)
class IKLift:
    q_rad: np.ndarray
    position_error_m: float
    angle_error_rad: float


@dataclass(frozen=True)
class IKBranch:
    canonical_q_rad: np.ndarray
    lifts: tuple[IKLift, ...]
    position_error_m: float
    angle_error_rad: float


@dataclass(frozen=True)
class IKTier:
    sobol_seeds: int
    new_branches: int
    total_branches: int


@dataclass(frozen=True)
class IKDiagnostics:
    seed_count: int
    converged_count: int
    fk_valid_count: int
    collision_rejected_count: int
    geometric_branches: int
    independent_branches: int
    lifted_solutions: int
    best_position_error_m: float | None
    best_angle_error_rad: float | None
    stable: bool
    collision_checked: bool
    tiers: tuple[IKTier, ...]


@dataclass(frozen=True)
class IKEnumeration:
    branches: tuple[IKBranch, ...]
    diagnostics: IKDiagnostics

    def to_dict(self) -> dict:
        """JSON-compatible result for search reports and future path graphs."""
        return {
            "branches": [
                {"canonical_q_rad": branch.canonical_q_rad.tolist(),
                 "position_error_m": branch.position_error_m,
                 "angle_error_rad": branch.angle_error_rad,
                 "lifts": [
                     {"q_rad": lift.q_rad.tolist(),
                      "position_error_m": lift.position_error_m,
                      "angle_error_rad": lift.angle_error_rad}
                     for lift in branch.lifts]}
                for branch in self.branches],
            "diagnostics": {
                "seed_count": self.diagnostics.seed_count,
                "converged_count": self.diagnostics.converged_count,
                "fk_valid_count": self.diagnostics.fk_valid_count,
                "collision_rejected_count": self.diagnostics.collision_rejected_count,
                "geometric_branches": self.diagnostics.geometric_branches,
                "independent_branches": self.diagnostics.independent_branches,
                "lifted_solutions": self.diagnostics.lifted_solutions,
                "best_position_error_m": self.diagnostics.best_position_error_m,
                "best_angle_error_rad": self.diagnostics.best_angle_error_rad,
                "stable": self.diagnostics.stable,
                "collision_checked": self.diagnostics.collision_checked,
                "tiers": [tier.__dict__ for tier in self.diagnostics.tiers],
            },
        }


def _caller_seeds(seeds: Sequence[np.ndarray] | np.ndarray | None) -> np.ndarray:
    if seeds is None:
        return np.empty((0, 6))
    value = np.asarray(seeds, dtype=float)
    if value.shape == (6,):
        value = value[None, :]
    if value.ndim != 2 or value.shape[1] != 6 or not np.isfinite(value).all():
        raise ValueError("seeds must be finite six-angle vectors")
    return value


def enumerate_ik(
    arm: SixR,
    target: np.ndarray,
    seeds: Sequence[np.ndarray] | np.ndarray | None = None,
    collision_free: CollisionFree | None = None,
    sobol_tiers: tuple[int, ...] = (32, 64, 128),
    position_tolerance_m: float = 1e-4,
    angle_tolerance_rad: float = 1e-3,
    branch_tolerance_rad: float = 1e-3,
) -> IKEnumeration:
    """Find distinct numerical roots; two empty Sobol tiers mark stability.

    ``sobol_tiers`` are cumulative counts.  Collision checks are applied to
    every lift, since scene/cable checks may depend on the angle winding.
    Stability describes this deterministic search only; it is not a proof
    that every root was found or that an empty result is unreachable.
    """
    target = np.asarray(target, dtype=float)
    if target.shape != (4, 4) or not np.isfinite(target).all():
        raise ValueError("target must be a finite 4x4 pose")
    if not np.allclose(target[3], [0, 0, 0, 1], atol=1e-8):
        raise ValueError("target must be a homogeneous pose")
    if not np.allclose(target[:3, :3].T @ target[:3, :3], np.eye(3), atol=1e-6) or np.linalg.det(target[:3, :3]) < 0.999999:
        raise ValueError("target rotation must be proper and orthonormal")
    if not sobol_tiers or any(tier <= 0 or tier & (tier - 1) for tier in sobol_tiers) or tuple(sorted(set(sobol_tiers))) != sobol_tiers:
        raise ValueError("sobol_tiers must be increasing powers of two")
    if min(position_tolerance_m, angle_tolerance_rad, branch_tolerance_rad) <= 0:
        raise ValueError("tolerances must be positive")

    lower, upper = arm.limits[:, 0], arm.limits[:, 1]
    padding = np.minimum(1e-9, (upper - lower) / 4)
    interior_lower, interior_upper = lower + padding, upper - padding
    initial = [*_caller_seeds(seeds), np.zeros(6), (lower + upper) / 2]
    # Sobol's unscrambled sequence is reproducible and nested at 32/64/128.
    sobol = qmc.Sobol(d=6, scramble=False).random_base2(int(np.log2(sobol_tiers[-1])))
    sobol_q = qmc.scale(sobol, lower, upper)

    attempted: list[np.ndarray] = []
    roots: list[tuple[np.ndarray, float, float]] = []
    seed_count = converged_count = fk_valid_count = 0

    def try_seed(seed: np.ndarray) -> None:
        nonlocal seed_count, converged_count, fk_valid_count
        seed = np.clip(seed, interior_lower, interior_upper)
        if any(np.max(np.abs(seed - previous)) < 1e-10 for previous in attempted):
            return
        attempted.append(seed)
        seed_count += 1
        q, converged, _ = arm.ik(target, seed, position_tolerance_m, angle_tolerance_rad)
        if not converged:
            return
        converged_count += 1
        q = np.asarray(q, dtype=float)
        if q.shape != (6,) or not np.isfinite(q).all() or np.any(q < lower - 1e-9) or np.any(q > upper + 1e-9):
            return
        # Recheck FK independently of the solver's accepted flag.
        error = arm.pose_error(q, target)
        position, angle = float(np.linalg.norm(error[:3])), float(np.linalg.norm(error[3:]))
        if position > position_tolerance_m or angle > angle_tolerance_rad:
            return
        fk_valid_count += 1
        canonical = canonical_angles(q)
        for index, (existing, old_position, old_angle) in enumerate(roots):
            if periodic_joint_distance(canonical, existing) <= branch_tolerance_rad:
                if (position, angle) < (old_position, old_angle):
                    roots[index] = (canonical, position, angle)
                return
        roots.append((canonical, position, angle))

    for seed in initial:
        try_seed(seed)
    tiers = []
    empty_tiers = 0
    previous_count = 0
    for tier in sobol_tiers:
        before = len(roots)
        for seed in sobol_q[previous_count:tier]:
            try_seed(seed)
        new = len(roots) - before
        tiers.append(IKTier(tier, new, len(roots)))
        empty_tiers = empty_tiers + 1 if new == 0 else 0
        previous_count = tier
        if empty_tiers >= 2:
            break

    branches = []
    rejected = 0
    for canonical, position, angle in sorted(roots, key=lambda item: tuple(item[0])):
        lifts = []
        for q in lifted_angles(canonical, arm.limits):
            error = arm.pose_error(q, target)
            lift_position, lift_angle = float(np.linalg.norm(error[:3])), float(np.linalg.norm(error[3:]))
            if lift_position > position_tolerance_m or lift_angle > angle_tolerance_rad:
                continue
            if collision_free is not None and not collision_free(q.copy()):
                rejected += 1
                continue
            lifts.append(IKLift(q, lift_position, lift_angle))
        if lifts:
            branches.append(IKBranch(canonical, tuple(lifts), position, angle))
    accepted_errors = [(lift.position_error_m, lift.angle_error_rad)
                       for branch in branches for lift in branch.lifts]
    best_position, best_angle = min(accepted_errors) if accepted_errors else (None, None)
    diagnostics = IKDiagnostics(
        seed_count=seed_count, converged_count=converged_count,
        fk_valid_count=fk_valid_count, collision_rejected_count=rejected,
        geometric_branches=len(roots),
        independent_branches=len(branches),
        lifted_solutions=sum(len(branch.lifts) for branch in branches),
        best_position_error_m=best_position, best_angle_error_rad=best_angle,
        stable=empty_tiers >= 2, collision_checked=collision_free is not None,
        tiers=tuple(tiers),
    )
    return IKEnumeration(tuple(branches), diagnostics)
