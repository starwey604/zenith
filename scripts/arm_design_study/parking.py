"""Check a stationary chassis footprint against a declared parking region."""
from __future__ import annotations

import numpy as np

from .chassis import ChassisMount
from .collision import Box, box_sat_clearance, chassis_box


def point_in_polygon_xy(point: np.ndarray, polygon: np.ndarray) -> bool:
    """Ray casting with boundary included."""
    x, y = point
    inside = False
    for a, b in zip(polygon, np.roll(polygon, -1, axis=0)):
        edge = b - a
        cross = edge[0] * (y - a[1]) - edge[1] * (x - a[0])
        projection = float((point - a) @ edge)
        if abs(cross) <= 1e-10 and -1e-10 <= projection <= float(edge @ edge) + 1e-10:
            return True
        if (a[1] > y) != (b[1] > y):
            crossing = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if x < crossing:
                inside = not inside
    return inside


def parking_legality(mount: ChassisMount, chassis_half_m: np.ndarray,
                     allowed_polygon_xy: np.ndarray, obstacles: list[Box]) -> tuple[bool, str, float]:
    polygon = np.asarray(allowed_polygon_xy, dtype=float)
    if polygon.ndim != 2 or polygon.shape[1] != 2 or len(polygon) < 3 or not np.isfinite(polygon).all():
        raise ValueError("parking polygon must have at least three finite XY vertices")
    cross_signs = []
    for a, b, c in zip(polygon, np.roll(polygon, -1, axis=0), np.roll(polygon, -2, axis=0)):
        one, two = b - a, c - b
        turn = one[0] * two[1] - one[1] * two[0]
        if abs(turn) > 1e-10:
            cross_signs.append(np.sign(turn))
    if not cross_signs or len(set(cross_signs)) != 1:
        raise ValueError("parking allowed polygon must be convex; corner check assumes convexity")
    body = chassis_box(mount, chassis_half_m)
    local_corners = np.array([[sx * body.half_m[0], sy * body.half_m[1], 0.0, 1.0]
                              for sx in (-1, 1) for sy in (-1, 1)])
    world_corners = (body.pose @ local_corners.T).T[:, :2]
    if not all(point_in_polygon_xy(point, polygon) for point in world_corners):
        return False, "outside_allowed_polygon", float("-inf")
    clearance = float("inf")
    for obstacle in obstacles:
        if not obstacle.blocks_chassis:
            continue
        gap = box_sat_clearance(body, obstacle)
        clearance = min(clearance, gap)
        if gap <= 0:
            return False, f"chassis_vs_{obstacle.name}", gap
    return True, "ok", clearance
