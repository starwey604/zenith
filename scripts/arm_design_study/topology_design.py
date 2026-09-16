"""Manufacturable synthetic 6R topology hypotheses for task-driven screening.

These arms are deliberately simple product-of-exponentials models.  They are
not vendor models or certified mechanical designs.  All templates share a
folded zero pose, common main-link dimensions and common joint limits so an
initial comparison changes axis topology instead of product scale.
"""
from __future__ import annotations

import numpy as np

from .frames import transform
from .sixr import SixR


GENERATED_ARM_NAMES = (
    "rm2p_offset_wrist",
    "rm2p_spherical_wrist",
    "rm3p_spherical_wrist",
    "rm_spherical_shoulder",
    "rm_offset_shoulder",
)

_COMMON_LIMITS = np.array([
    [-np.pi, np.pi],
    [-2.35, 2.35],
    [-2.70, 2.70],
    [-np.pi, np.pi],
    [-1.90, 1.90],
    [-np.pi, np.pi],
])


def _unit_rows(values: list[list[float]]) -> np.ndarray:
    axes = np.asarray(values, dtype=float)
    return axes / np.linalg.norm(axes, axis=1, keepdims=True)


def _arm(name: str, axes: list[list[float]], points: list[np.ndarray],
         flange_xyz: np.ndarray, description: str) -> SixR:
    return SixR(
        name=name,
        axes=_unit_rows(axes),
        points=np.asarray(points, dtype=float),
        home_flange=transform(translation=np.asarray(flange_xyz, dtype=float)),
        limits=_COMMON_LIMITS.copy(),
        provenance=(
            "synthetic constrained-topology design assumption; "
            "main spans 0.290/0.390 m, shoulder height 0.150 m; " + description
        ),
    )


def load_generated_arm(name: str) -> SixR:
    """Create one common-scale topology hypothesis by stable identifier."""
    if name not in GENERATED_ARM_NAMES:
        raise ValueError(f"unknown generated arm: {name}")

    # The zero pose folds the 390 mm forearm back over the 290 mm upper arm.
    # Axis signs are immaterial to topology and are kept positive for readable
    # relation codes.  Points are physical axis anchors, not link-frame origins.
    base = np.array([0.0, 0.0, 0.100])
    shoulder = np.array([0.0, 0.0, 0.150])
    elbow = np.array([-0.290, 0.0, 0.150])
    wrist = np.array([0.100, 0.0, 0.150])

    if name == "rm2p_offset_wrist":
        wrist_6 = wrist + np.array([0.0, 0.0, 0.060])
        return _arm(
            name,
            [[0, 0, 1], [0, 1, 0], [0, 1, 0], [1, 0, 0], [0, 1, 0], [1, 0, 0]],
            [base, shoulder, elbow, wrist, wrist, wrist_6],
            wrist_6 + np.array([0.080, 0.0, 0.0]),
            "J2||J3; roll-pitch-roll wrist with 60 mm J6 offset",
        )
    if name == "rm2p_spherical_wrist":
        return _arm(
            name,
            [[0, 0, 1], [0, 1, 0], [0, 1, 0], [1, 0, 0], [0, 1, 0], [1, 0, 0]],
            [base, shoulder, elbow, wrist, wrist, wrist],
            wrist + np.array([0.080, 0.0, 0.0]),
            "J2||J3; intersecting roll-pitch-roll spherical wrist",
        )
    if name == "rm3p_spherical_wrist":
        return _arm(
            name,
            [[0, 0, 1], [0, 1, 0], [0, 1, 0], [0, 1, 0], [0, 0, 1], [1, 0, 0]],
            [base, shoulder, elbow, wrist, wrist, wrist],
            wrist + np.array([0.080, 0.0, 0.0]),
            "J2||J3||J4 folded planar chain; J4/J5/J6 intersect",
        )
    if name == "rm_spherical_shoulder":
        return _arm(
            name,
            [[0, 0, 1], [0, 1, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 0, 0]],
            [shoulder, shoulder, shoulder, elbow, wrist, wrist],
            wrist + np.array([0.080, 0.0, 0.0]),
            "J1/J2/J3 intersecting spherical shoulder; elbow plus two-axis wrist",
        )
    shoulder_roll = shoulder + np.array([0.0, 0.0, 0.060])
    return _arm(
        name,
        [[0, 0, 1], [0, 1, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 0, 0]],
        [base, shoulder, shoulder_roll, elbow, wrist, wrist],
        wrist + np.array([0.080, 0.0, 0.0]),
        "60 mm offset shoulder-roll axis; elbow plus two-axis wrist",
    )


def relation_signature(arm: SixR, tolerance: float = 1e-8) -> tuple[str, ...]:
    """Classify adjacent zero-pose axes as parallel, intersecting or skew."""
    signature = []
    for index in range(5):
        one, two = arm.axes[index], arm.axes[index + 1]
        delta = arm.points[index + 1] - arm.points[index]
        cross = np.cross(one, two)
        norm = float(np.linalg.norm(cross))
        if norm <= tolerance:
            distance = float(np.linalg.norm(np.cross(delta, one)))
            signature.append("coaxial" if distance <= tolerance else "parallel")
        else:
            distance = abs(float(delta @ cross)) / norm
            signature.append("intersect" if distance <= tolerance else "skew")
    return tuple(signature)
