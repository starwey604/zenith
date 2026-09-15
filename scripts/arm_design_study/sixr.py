"""Six revolute joints represented by base-frame axes, points and home flange."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

from .frames import axis_turn


@dataclass(frozen=True)
class SixR:
    name: str
    axes: np.ndarray       # (6, 3), at q=0 in arm base frame
    points: np.ndarray     # (6, 3), one point on each axis
    home_flange: np.ndarray
    limits: np.ndarray     # (6, 2), radians
    provenance: str

    def __post_init__(self) -> None:
        for key, shape in (("axes", (6, 3)), ("points", (6, 3)), ("home_flange", (4, 4)), ("limits", (6, 2))):
            value = np.asarray(getattr(self, key), dtype=float)
            if value.shape != shape or not np.isfinite(value).all():
                raise ValueError(f"{key} must be finite with shape {shape}")
            object.__setattr__(self, key, value)
        norms = np.linalg.norm(self.axes, axis=1)
        if np.max(np.abs(norms - 1.0)) > 1e-7:
            raise ValueError("joint axes must be unit vectors")
        if np.any(self.limits[:, 0] >= self.limits[:, 1]):
            raise ValueError("invalid joint limits")
        if np.linalg.det(self.home_flange[:3, :3]) < 0.999999:
            raise ValueError("home flange rotation invalid")

    def fk(self, q: np.ndarray) -> np.ndarray:
        q = np.asarray(q, dtype=float)
        if q.shape != (6,):
            raise ValueError("q must have six angles")
        pose = np.eye(4)
        for axis, point, angle in zip(self.axes, self.points, q):
            pose = pose @ axis_turn(axis, float(angle), point)
        return pose @ self.home_flange

    def joint_anchors(self, q: np.ndarray) -> np.ndarray:
        """Zero-pose axis points carried through upstream joints, in A."""
        q = np.asarray(q, dtype=float)
        if q.shape != (6,):
            raise ValueError("q must have six angles")
        chain = np.eye(4)
        anchors = []
        for axis, point, angle in zip(self.axes, self.points, q):
            anchors.append((chain @ np.r_[point, 1.0])[:3])
            chain = chain @ axis_turn(axis, float(angle), point)
        return np.asarray(anchors)

    def jacobian(self, q: np.ndarray) -> np.ndarray:
        """Geometric Jacobian: [Cartesian velocity; angular velocity]."""
        q = np.asarray(q, dtype=float)
        tip = self.fk(q)[:3, 3]
        chain = np.eye(4)
        columns = []
        for axis, point, angle in zip(self.axes, self.points, q):
            world_axis = chain[:3, :3] @ axis
            world_point = (chain @ np.r_[point, 1.0])[:3]
            columns.append(np.r_[np.cross(world_axis, tip - world_point), world_axis])
            chain = chain @ axis_turn(axis, float(angle), point)
        return np.column_stack(columns)

    def pose_error(self, q: np.ndarray, target: np.ndarray) -> np.ndarray:
        actual = self.fk(q)
        angle = Rotation.from_matrix(target[:3, :3] @ actual[:3, :3].T).as_rotvec()
        return np.r_[actual[:3, 3] - target[:3, 3], angle]

    def ik(self, target: np.ndarray, seed: np.ndarray, position_tolerance_m: float = 1e-4,
           angle_tolerance_rad: float = 1e-3) -> tuple[np.ndarray, bool, np.ndarray]:
        seed = np.clip(np.asarray(seed, dtype=float), self.limits[:, 0] + 1e-9, self.limits[:, 1] - 1e-9)
        # Rotational error is weighted to one metre per radian during search.
        solution = least_squares(lambda q: self.pose_error(q, target), seed,
                                 bounds=(self.limits[:, 0], self.limits[:, 1]),
                                 max_nfev=300, xtol=1e-10, ftol=1e-10, gtol=1e-10)
        error = self.pose_error(solution.x, target)
        accepted = (np.linalg.norm(error[:3]) <= position_tolerance_m
                    and np.linalg.norm(error[3:]) <= angle_tolerance_rad)
        return solution.x, bool(accepted), error

    def axis_relation(self) -> dict[str, float]:
        """Absolute cosine is 1 for parallel/antiparallel axes."""
        return {f"axis_{i + 1}_{j + 1}_parallel_cos": float(np.clip(abs(self.axes[i] @ self.axes[j]), 0.0, 1.0))
                for i, j in ((1, 2), (2, 3), (3, 4), (4, 5))}
