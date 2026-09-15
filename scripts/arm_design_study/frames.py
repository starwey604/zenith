"""Rigid transforms; metres and radians throughout."""
from __future__ import annotations

import numpy as np
from scipy.spatial.transform import Rotation


def transform(rotation: np.ndarray | None = None, translation: np.ndarray | None = None) -> np.ndarray:
    result = np.eye(4)
    if rotation is not None:
        result[:3, :3] = np.asarray(rotation, dtype=float)
    if translation is not None:
        result[:3, 3] = np.asarray(translation, dtype=float)
    return result


def inverse(pose: np.ndarray) -> np.ndarray:
    result = np.eye(4)
    result[:3, :3] = pose[:3, :3].T
    result[:3, 3] = -result[:3, :3] @ pose[:3, 3]
    return result


def axis_turn(axis: np.ndarray, angle: float, point: np.ndarray) -> np.ndarray:
    """SE(3) rotation about a directed line through point."""
    rotation = Rotation.from_rotvec(np.asarray(axis) * angle).as_matrix()
    return transform(rotation, np.asarray(point) - rotation @ np.asarray(point))


def yaw_pose(x: float, y: float, yaw: float) -> np.ndarray:
    return transform(Rotation.from_euler("z", yaw).as_matrix(), np.array([x, y, 0.0]))
