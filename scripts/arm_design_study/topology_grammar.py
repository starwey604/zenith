"""Finite, reproducible grammar of orthogonal six-revolute-axis hypotheses.

This is a kinematic candidate generator, not a mechanical CAD validator.
Every accepted layout is built from straight coordinate-aligned primitives;
one short orthogonal dogleg is allowed for the offset-shoulder family.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, replace
import hashlib
from itertools import product
import json
from pathlib import Path

import numpy as np

from .frames import transform
from .sixr import SixR
from .topology_design import COMMON_LIMITS, GENERATED_ARM_NAMES, load_generated_arm, relation_signature


AXES = {"x": np.array([1.0, 0.0, 0.0]),
        "y": np.array([0.0, 1.0, 0.0]),
        "z": np.array([0.0, 0.0, 1.0])}
PROBE_CONFIGURATIONS = (
    np.array([0.31, -0.52, 0.47, -0.38, 0.61, -0.29]),
    np.array([-0.43, 0.27, -0.59, 0.41, -0.34, 0.53]),
    np.array([0.19, 0.36, -0.28, -0.44, 0.52, 0.33]),
)


@dataclass(frozen=True)
class GrammarSpec:
    shoulder_height_m: float = 0.150
    base_axis_height_m: float = 0.100
    upper_arm_m: float = 0.290
    forearm_m: float = 0.390
    small_offset_m: float = 0.060
    flange_overhang_m: float = 0.080
    max_doglegs: int = 1
    allowed_adjacent_coaxial: tuple[tuple[int, int], ...] = ()

    def __post_init__(self) -> None:
        dimensions = (self.shoulder_height_m, self.base_axis_height_m,
                      self.upper_arm_m, self.forearm_m, self.small_offset_m,
                      self.flange_overhang_m)
        if not np.isfinite(dimensions).all() or min(dimensions) <= 0:
            raise ValueError("grammar dimensions must be finite and positive")
        if self.max_doglegs < 0:
            raise ValueError("max_doglegs must be nonnegative")
        if any(pair not in ((1, 2), (2, 3), (3, 4), (4, 5), (5, 6))
               for pair in self.allowed_adjacent_coaxial):
            raise ValueError("coaxial whitelist must contain adjacent joint pairs")


@dataclass(frozen=True)
class PrimitiveRoute:
    from_joint: int
    to_joint: int
    kind: str  # coincident, straight, or short_dogleg
    vertices_m: tuple[tuple[float, float, float], ...]


@dataclass(frozen=True)
class TopologyCandidate:
    topology_id: str
    geometry_id: str
    layout: str
    axis_word: tuple[str, ...]
    arm: SixR
    relations: tuple[str, ...]
    routes: tuple[PrimitiveRoute, ...]
    full_rank_probes: int
    equivalent_syntaxes: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "topology_id": self.topology_id,
            "geometry_id": self.geometry_id,
            "layout": self.layout,
            "axis_word": "".join(self.axis_word),
            "axes": self.arm.axes.tolist(),
            "axis_points_m": self.arm.points.tolist(),
            "home_flange": self.arm.home_flange.tolist(),
            "joint_limits_rad": self.arm.limits.tolist(),
            "relations": list(self.relations),
            "routes": [route.__dict__ for route in self.routes],
            "full_rank_probes": self.full_rank_probes,
            "equivalent_syntaxes": list(self.equivalent_syntaxes),
            "provenance": self.arm.provenance,
        }


@dataclass(frozen=True)
class GrammarCatalog:
    spec: GrammarSpec
    candidates: tuple[TopologyCandidate, ...]
    attempted: int
    rejected: dict[str, int]
    template_matches: dict[str, str]

    def to_dict(self) -> dict:
        return {
            "schema_version": 1,
            "source_type": "synthetic_design_assumption",
            "grammar": "orthogonal_6r_top_mount_tool_x_v1",
            "spec": self.spec.__dict__,
            "attempted": self.attempted,
            "rejected": self.rejected,
            "accepted": len(self.candidates),
            "template_matches": self.template_matches,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


def canonical_geometry_key(arm: SixR, resolution: float = 1e-6) -> tuple[int, ...]:
    """Sign-free screw lines and flange pose; anchor shifts along axes vanish."""
    if not np.isfinite(resolution) or resolution <= 0:
        raise ValueError("resolution must be positive and finite")
    values = []
    for axis, point in zip(arm.axes, arm.points):
        direction = axis.copy()
        first = next(index for index in range(3) if abs(direction[index]) > 1e-12)
        if direction[first] < 0:
            direction = -direction
        nearest_origin = point - direction * float(direction @ point)
        values.extend(np.r_[direction, nearest_origin])
    values.extend(arm.home_flange.ravel())
    return tuple(int(value) for value in np.rint(np.asarray(values) / resolution))


def _layout_points(spec: GrammarSpec) -> tuple[tuple[str, np.ndarray, np.ndarray], ...]:
    base = np.array([0.0, 0.0, spec.base_axis_height_m])
    shoulder = np.array([0.0, 0.0, spec.shoulder_height_m])
    elbow = shoulder + np.array([-spec.upper_arm_m, 0.0, 0.0])
    wrist = elbow + np.array([spec.forearm_m, 0.0, 0.0])
    up = np.array([0.0, 0.0, spec.small_offset_m])
    overhang = np.array([spec.flange_overhang_m, 0.0, 0.0])
    standard = np.asarray([base, shoulder, elbow, wrist, wrist, wrist])
    spherical_shoulder = np.asarray([shoulder, shoulder, shoulder, elbow, wrist, wrist])
    layouts = [
        ("serial_spherical_wrist", standard, wrist + overhang),
        ("spherical_shoulder", spherical_shoulder, wrist + overhang),
    ]
    for sign, direction in ((1, "up"), (-1, "down")):
        wrist_offset = standard.copy()
        wrist_offset[5] = wrist + sign * up
        layouts.append((f"serial_wrist_offset_{direction}",
                        wrist_offset, wrist_offset[5] + overhang))
        shoulder_offset = np.asarray([base, shoulder, shoulder + sign * up,
                                      elbow, wrist, wrist])
        layouts.append((f"offset_shoulder_{direction}",
                        shoulder_offset, wrist + overhang))
    return tuple(layouts)


def axis_words() -> tuple[tuple[str, ...], ...]:
    """J1 vertical; J2 horizontal; J6 roll axis along zero-pose tool X."""
    return tuple(("z", second, third, fourth, fifth, "x")
                 for second, third, fourth, fifth in product(("x", "y"), "xyz", "xyz", "xyz"))


def _routes(points: np.ndarray, spec: GrammarSpec) -> tuple[tuple[PrimitiveRoute, ...], str | None]:
    routes = []
    doglegs = 0
    for index, (start, end) in enumerate(zip(points[:-1], points[1:]), start=1):
        delta = end - start
        active = np.flatnonzero(np.abs(delta) > 1e-9)
        if len(active) == 0:
            kind, vertices = "coincident", (tuple(start),)
        elif len(active) == 1:
            kind, vertices = "straight", (tuple(start), tuple(end))
        elif len(active) == 2 and min(abs(delta[active])) <= spec.small_offset_m + 1e-9:
            doglegs += 1
            corner = start.copy()
            short_axis = active[np.argmin(np.abs(delta[active]))]
            corner[short_axis] = end[short_axis]
            kind, vertices = "short_dogleg", (tuple(start), tuple(corner), tuple(end))
        else:
            return (), "non_orthogonal_link_route"
        routes.append(PrimitiveRoute(index, index + 1, kind, vertices))
    if doglegs > spec.max_doglegs:
        return (), "too_many_doglegs"
    return tuple(routes), None


def _rank_probe_count(arm: SixR) -> int:
    return int(sum(np.linalg.matrix_rank(arm.jacobian(q), tol=1e-7) == 6
                   for q in PROBE_CONFIGURATIONS))


def generate_topology_catalog(spec: GrammarSpec | None = None) -> GrammarCatalog:
    """Enumerate the finite grammar, normalize geometry, and reject bad 6R arms."""
    spec = GrammarSpec() if spec is None else spec
    accepted: dict[tuple[int, ...], TopologyCandidate] = {}
    aliases: dict[tuple[int, ...], list[str]] = {}
    rejected: Counter[str] = Counter()
    attempted = 0
    for layout, points, flange_xyz in _layout_points(spec):
        routes, route_error = _routes(points, spec)
        for word in axis_words():
            attempted += 1
            if route_error is not None:
                rejected[route_error] += 1
                continue
            axes = np.asarray([AXES[letter] for letter in word])
            arm = SixR("candidate", axes, points.copy(),
                       transform(translation=flange_xyz), COMMON_LIMITS.copy(),
                       "synthetic orthogonal-axis grammar v1; straight primitive route hypothesis")
            relations = relation_signature(arm)
            if any(relation == "coaxial" and (index + 1, index + 2)
                   not in spec.allowed_adjacent_coaxial
                   for index, relation in enumerate(relations)):
                rejected["adjacent_coaxial"] += 1
                continue
            full_rank = _rank_probe_count(arm)
            if full_rank < 2:
                rejected["jacobian_rank"] += 1
                continue
            key = canonical_geometry_key(arm)
            if key in accepted:
                rejected["duplicate_screw_geometry"] += 1
                aliases[key].append(f"{layout}:{''.join(word)}")
                continue
            syntax = f"{layout}:{''.join(word)}"
            syntax_digest = hashlib.sha256(syntax.encode()).hexdigest()[:12]
            geometry_digest = hashlib.sha256(json.dumps(key, separators=(",", ":")).encode()).hexdigest()[:12]
            topology_id = f"orth6r_{syntax_digest}"
            geometry_id = f"geom_{geometry_digest}"
            arm = SixR(topology_id, arm.axes, arm.points, arm.home_flange,
                       arm.limits, arm.provenance + f"; layout={layout}; axis_word={''.join(word)}")
            accepted[key] = TopologyCandidate(topology_id, geometry_id, layout, word, arm,
                                              relations, routes, full_rank)
            aliases[key] = []
    candidates = tuple(sorted((replace(candidate, equivalent_syntaxes=tuple(aliases[key]))
                               for key, candidate in accepted.items()),
                              key=lambda item: item.topology_id))
    if len({item.topology_id for item in candidates}) != len(candidates):
        raise RuntimeError("stable topology ID hash collision")
    by_key = {canonical_geometry_key(item.arm): item.topology_id for item in candidates}
    template_matches = {}
    if spec == GrammarSpec():
        for name in GENERATED_ARM_NAMES:
            match = by_key.get(canonical_geometry_key(load_generated_arm(name)))
            if match is None:
                raise RuntimeError(f"grammar failed to reproduce existing template: {name}")
            template_matches[name] = match
    return GrammarCatalog(spec, candidates, attempted, dict(sorted(rejected.items())),
                          template_matches)


def load_grammar_arm(topology_id: str, catalog: GrammarCatalog | None = None) -> SixR:
    """Load a generated candidate by its stable syntax ID."""
    catalog = generate_topology_catalog() if catalog is None else catalog
    for candidate in catalog.candidates:
        if candidate.topology_id == topology_id:
            return candidate.arm
    raise ValueError(f"unknown grammar topology ID: {topology_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="write deterministic JSON catalog")
    args = parser.parse_args()
    catalog = generate_topology_catalog()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(catalog.to_dict(), ensure_ascii=False, indent=2) + "\n")
    print(f"{catalog.attempted} raw combinations, {len(catalog.candidates)} accepted; {args.output}")


if __name__ == "__main__":
    main()
