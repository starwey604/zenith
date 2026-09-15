"""Geometry hypotheses: stretch selected zero-pose joint-anchor spans."""
from __future__ import annotations

from collections.abc import Mapping
import numpy as np

from .sixr import SixR


def anchor_spans_m(arm: SixR) -> dict[int, float]:
    """Span i joins joint anchor i to i+1; not a certified link length."""
    return {i + 1: float(np.linalg.norm(arm.points[i + 1] - arm.points[i])) for i in range(5)}


def scale_anchor_spans(arm: SixR, scales: Mapping[int, float]) -> SixR:
    """Move each downstream joint anchor and flange; preserve axis directions.

    A zero-length span cannot define a stretch direction. The resulting robot
    is a kinematic design hypothesis, not a modification of the vendor MJCF.
    """
    points = arm.points.copy()
    flange = arm.home_flange.copy()
    original = arm.points.copy()
    for index, factor in sorted(scales.items()):
        if index not in range(1, 6) or not np.isfinite(factor) or factor <= 0:
            raise ValueError("span index must be 1..5 with positive finite scale")
        vector = original[index] - original[index - 1]
        if np.linalg.norm(vector) < 1e-8:
            raise ValueError(f"joint-anchor span {index} is zero; stretch direction undefined")
        delta = (factor - 1.0) * vector
        points[index:] += delta
        flange[:3, 3] += delta
    text = ", ".join(f"{index}:{factor:.5g}" for index, factor in sorted(scales.items()))
    return SixR(f"{arm.name}[span {text}]", arm.axes.copy(), points, flange,
                arm.limits.copy(), arm.provenance + f"; synthetic anchor span scales: {text}")
