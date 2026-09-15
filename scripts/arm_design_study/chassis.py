"""Stationary parking pose composed with a fixed arm mount."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .frames import yaw_pose
from .sixr import SixR


@dataclass(frozen=True)
class ChassisMount:
    x_m: float
    y_m: float
    yaw_rad: float
    chassis_to_arm: np.ndarray

    def world_to_arm(self) -> np.ndarray:
        return yaw_pose(self.x_m, self.y_m, self.yaw_rad) @ self.chassis_to_arm

    def world_flange(self, arm: SixR, q: np.ndarray) -> np.ndarray:
        return self.world_to_arm() @ arm.fk(q)
