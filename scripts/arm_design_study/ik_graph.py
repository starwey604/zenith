"""Layered IK graph over a geometric flange path.

Every retained lift is a graph node. Edges use unwrapped joint travel, a
per-waypoint step limit, and optional collision checks at interpolated states.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Protocol, Sequence

import numpy as np

from .chassis import ChassisMount
from .frames import inverse
from .ik_solutions import IKDiagnostics, IKEnumeration, enumerate_ik, periodic_joint_distance
from .sixr import SixR


class FlangeWaypoint(Protocol):
    phase: str
    world_flange: np.ndarray


StateFree = Callable[[np.ndarray, int, FlangeWaypoint], bool]
EdgeFree = Callable[[np.ndarray, int, float], bool]


@dataclass(frozen=True)
class GraphNode:
    q_rad: np.ndarray
    branch_index: int
    lift_index: int
    position_error_m: float
    angle_error_rad: float


@dataclass(frozen=True)
class GraphEdge:
    source_index: int  # -1 denotes the supplied start seed at layer 0
    target_index: int
    travel_rad: float
    max_step_rad: float
    collision_samples: int


@dataclass(frozen=True)
class GraphLayer:
    index: int
    phase: str
    nodes: tuple[GraphNode, ...]
    incoming_edges: tuple[GraphEdge, ...] = ()
    forward_diagnostics: IKDiagnostics | None = None
    backward_diagnostics: IKDiagnostics | None = None


@dataclass(frozen=True)
class GraphChoice:
    index: int
    phase: str
    node_index: int
    branch_index: int
    lift_index: int
    q_rad: np.ndarray
    position_error_m: float
    angle_error_rad: float


@dataclass(frozen=True)
class IKGraphResult:
    layers: tuple[GraphLayer, ...]
    path: tuple[GraphChoice, ...]  # best complete path, or best reachable prefix
    failure: dict | None
    total_joint_travel_rad: float | None
    greedy_complete: bool
    greedy_failure_index: int | None
    greedy_joint_travel_rad: float | None
    candidate_edges: int
    step_rejections: int
    collision_rejections: int
    collision_samples: int
    edge_collision_checked: bool
    start_step_enforced: bool

    @property
    def complete(self) -> bool:
        return self.failure is None

    def to_dict(self, include_graph: bool = False) -> dict:
        """Compact JSON report; include_graph also exports all nodes and edges."""
        result = {
            "complete": self.complete,
            "failure": self.failure,
            "path": [
                {"index": item.index, "phase": item.phase,
                 "node_index": item.node_index, "branch_index": item.branch_index,
                 "lift_index": item.lift_index, "q_rad": item.q_rad.tolist(),
                 "position_error_m": item.position_error_m,
                 "angle_error_rad": item.angle_error_rad}
                for item in self.path],
            "total_joint_travel_rad": self.total_joint_travel_rad,
            "greedy_complete": self.greedy_complete,
            "greedy_failure_index": self.greedy_failure_index,
            "greedy_joint_travel_rad": self.greedy_joint_travel_rad,
            "candidate_edges": self.candidate_edges,
            "step_rejections": self.step_rejections,
            "collision_rejections": self.collision_rejections,
            "collision_samples": self.collision_samples,
            "edge_collision_checked": self.edge_collision_checked,
            "start_step_enforced": self.start_step_enforced,
            "layers": [
                {"index": layer.index, "phase": layer.phase,
                 "nodes": len(layer.nodes), "valid_incoming_edges": len(layer.incoming_edges),
                 "forward_ik": _diagnostics_dict(layer.forward_diagnostics),
                 "backward_ik": _diagnostics_dict(layer.backward_diagnostics)}
                for layer in self.layers],
        }
        if include_graph:
            for entry, layer in zip(result["layers"], self.layers):
                entry["node_data"] = [
                    {"q_rad": node.q_rad.tolist(), "branch_index": node.branch_index,
                     "lift_index": node.lift_index,
                     "position_error_m": node.position_error_m,
                     "angle_error_rad": node.angle_error_rad}
                    for node in layer.nodes]
                entry["edges"] = [edge.__dict__ for edge in layer.incoming_edges]
        return result


def _diagnostics_dict(diagnostics: IKDiagnostics | None) -> dict | None:
    if diagnostics is None:
        return None
    return {**{key: value for key, value in diagnostics.__dict__.items() if key != "tiers"},
            "tiers": [tier.__dict__ for tier in diagnostics.tiers]}


def _seed_array(seeds: Sequence[np.ndarray] | np.ndarray) -> np.ndarray:
    value = np.asarray(seeds, dtype=float)
    if value.shape == (6,):
        value = value[None, :]
    if value.ndim != 2 or value.shape[1] != 6 or not np.isfinite(value).all() or len(value) == 0:
        raise ValueError("seeds must contain finite six-angle vectors")
    return value


def _branch_seeds(enumeration: IKEnumeration, reference: np.ndarray) -> list[np.ndarray]:
    return [min(branch.lifts, key=lambda lift: np.sum(np.abs(lift.q_rad - reference))).q_rad
            for branch in enumeration.branches]


def _merge_nodes(enumerations: Sequence[IKEnumeration], tolerance_rad: float) -> tuple[GraphNode, ...]:
    unique: list[tuple[np.ndarray, float, float]] = []
    for enumeration in enumerations:
        for branch in enumeration.branches:
            for lift in branch.lifts:
                q = lift.q_rad
                error = (lift.position_error_m, lift.angle_error_rad)
                for index, (old_q, old_position, old_angle) in enumerate(unique):
                    if np.max(np.abs(q - old_q)) <= tolerance_rad:
                        if error < (old_position, old_angle):
                            unique[index] = (q, *error)
                        break
                else:
                    unique.append((q, *error))
    unique.sort(key=lambda item: tuple(item[0]))
    representatives: list[np.ndarray] = []
    per_branch: dict[int, int] = {}
    nodes = []
    for q, position, angle in unique:
        branch_index = next((index for index, representative in enumerate(representatives)
                             if periodic_joint_distance(q, representative) <= tolerance_rad), None)
        if branch_index is None:
            branch_index = len(representatives)
            representatives.append(q)
        lift_index = per_branch.get(branch_index, 0)
        per_branch[branch_index] = lift_index + 1
        nodes.append(GraphNode(q, branch_index, lift_index, position, angle))
    return tuple(nodes)


def enumerate_path_layers(
    arm: SixR, mount: ChassisMount, path: Sequence[FlangeWaypoint],
    seeds: Sequence[np.ndarray] | np.ndarray,
    state_free: StateFree | None = None,
    sobol_tiers: tuple[int, ...] = (32, 64, 128),
    backward_continuation: bool = True,
    branch_tolerance_rad: float = 1e-3,
) -> tuple[GraphLayer, ...]:
    """Enumerate each pose forward, then propagate found branches backward."""
    initial = _seed_array(seeds)
    arm_from_world = inverse(mount.world_to_arm())
    targets = [arm_from_world @ point.world_flange for point in path]

    def enumerate_at(index: int, guesses: list[np.ndarray]) -> IKEnumeration:
        check = (None if state_free is None else
                 lambda q: bool(state_free(q, index, path[index])))
        return enumerate_ik(arm, targets[index], seeds=guesses,
                            collision_free=check, sobol_tiers=sobol_tiers,
                            branch_tolerance_rad=branch_tolerance_rad)

    forward: list[IKEnumeration] = []
    for index in range(len(path)):
        guesses = list(initial)
        if forward:
            guesses.extend(_branch_seeds(forward[-1], initial[0]))
        forward.append(enumerate_at(index, guesses))

    backward: list[IKEnumeration | None] = [None] * len(path)
    layers: list[GraphLayer | None] = [None] * len(path)
    for index in range(len(path) - 1, -1, -1):
        if backward_continuation:
            guesses = [*initial, *_branch_seeds(forward[index], initial[0])]
            if index + 1 < len(path):
                guesses.extend(_branch_seeds(forward[index + 1], initial[0]))
                next_enumeration = backward[index + 1]
                if next_enumeration is not None:
                    guesses.extend(_branch_seeds(next_enumeration, initial[0]))
            backward[index] = enumerate_at(index, guesses)
        sources = [forward[index]]
        if backward[index] is not None:
            sources.append(backward[index])
        layers[index] = GraphLayer(index, path[index].phase,
                                   _merge_nodes(sources, branch_tolerance_rad),
                                   forward_diagnostics=forward[index].diagnostics,
                                   backward_diagnostics=(backward[index].diagnostics
                                                         if backward[index] is not None else None))
    return tuple(layer for layer in layers if layer is not None)


def _trace_path(layers: Sequence[GraphLayer], parents: list[dict[int, int]],
                final_index: int, node_index: int) -> tuple[GraphChoice, ...]:
    path = []
    for index in range(final_index, -1, -1):
        node = layers[index].nodes[node_index]
        path.append(GraphChoice(index, layers[index].phase, node_index,
                                node.branch_index, node.lift_index, node.q_rad,
                                node.position_error_m, node.angle_error_rad))
        node_index = parents[index][node_index]
    return tuple(reversed(path))


def search_ik_graph(
    layers: Sequence[GraphLayer], start_q: np.ndarray,
    max_joint_step_rad: float = 0.5,
    interpolation_step_rad: float = 0.05,
    edge_free: EdgeFree | None = None,
    enforce_start_step: bool = False,
) -> IKGraphResult:
    """Shortest path in the complete layered graph of enumerated lifts.

    ``edge_free(q, index, alpha)`` checks an intermediate configuration of
    the segment ending at waypoint ``index``. The caller owns any moving
    obstacle interpolation. With no callback, edge collisions are unchecked.
    """
    start_q = np.asarray(start_q, dtype=float)
    if start_q.shape != (6,) or not np.isfinite(start_q).all():
        raise ValueError("start_q must be a finite six-angle vector")
    if (not np.isfinite([max_joint_step_rad, interpolation_step_rad]).all()
            or max_joint_step_rad <= 0 or interpolation_step_rad <= 0):
        raise ValueError("joint step and interpolation resolution must be positive")
    if any(layer.index != index for index, layer in enumerate(layers)):
        raise ValueError("layers must have consecutive indices from zero")
    if not layers:
        raise ValueError("at least one waypoint is required")
    if any(node.q_rad.shape != (6,) or not np.isfinite(node.q_rad).all()
           for layer in layers for node in layer.nodes):
        raise ValueError("graph nodes must contain finite six-angle vectors")

    completed_layers: list[GraphLayer] = []
    costs: list[dict[int, float]] = []
    parents: list[dict[int, int]] = []
    candidate_edges = step_rejections = collision_rejections = collision_samples = 0
    failure = None
    for index, layer in enumerate(layers):
        previous_nodes = (None,) if index == 0 else completed_layers[-1].nodes
        previous_costs = {-1: 0.0} if index == 0 else costs[-1]
        current_costs: dict[int, float] = {}
        current_parents: dict[int, int] = {}
        edges = []
        layer_collision_rejections = 0
        source_indices = (-1,) if index == 0 else range(len(previous_nodes))
        for source_index in source_indices:
            previous_q = start_q if index == 0 else previous_nodes[source_index].q_rad
            for target_index, node in enumerate(layer.nodes):
                candidate_edges += 1
                delta = node.q_rad - previous_q
                max_step = float(np.max(np.abs(delta)))
                if (index > 0 or enforce_start_step) and max_step > max_joint_step_rad + 1e-12:
                    step_rejections += 1
                    continue
                samples = 0
                if edge_free is not None and (index > 0 or enforce_start_step):
                    intervals = max(2, int(np.ceil(max_step / interpolation_step_rad)))
                    blocked = False
                    for step in range(1, intervals):
                        alpha = step / intervals
                        samples += 1
                        collision_samples += 1
                        if not edge_free(previous_q + alpha * delta, index, alpha):
                            collision_rejections += 1
                            layer_collision_rejections += 1
                            blocked = True
                            break
                    if blocked:
                        continue
                travel = float(np.sum(np.abs(delta)))
                edges.append(GraphEdge(source_index, target_index, travel, max_step, samples))
                if source_index in previous_costs:
                    new_cost = previous_costs[source_index] + travel
                    if new_cost < current_costs.get(target_index, float("inf")) - 1e-12:
                        current_costs[target_index] = new_cost
                        current_parents[target_index] = source_index
        completed_layers.append(replace(layer, incoming_edges=tuple(edges)))
        costs.append(current_costs)
        parents.append(current_parents)
        if not current_costs and failure is None:
            geometric = max((diagnostics.geometric_branches for diagnostics in
                             (layer.forward_diagnostics, layer.backward_diagnostics)
                             if diagnostics is not None), default=0)
            if not layer.nodes:
                reason = "no_ik" if geometric == 0 else "state_collision"
            elif edges:
                reason = "disconnected"
            elif layer_collision_rejections:
                reason = "edge_collision"
            else:
                reason = "joint_step"
            failure = {"index": index, "phase": layer.phase, "reason": reason,
                       "candidate_nodes": len(layer.nodes),
                       "reachable_previous_nodes": len(previous_costs)}

    if failure is None:
        final_index = len(layers) - 1
    else:
        final_index = failure["index"] - 1
    if final_index >= 0:
        best_node = min(costs[final_index], key=lambda node: (costs[final_index][node], node))
        path = _trace_path(completed_layers, parents, final_index, best_node)
        total = costs[final_index][best_node] if failure is None else None
    else:
        path, total = (), None

    greedy_index = -1
    greedy_cost = 0.0
    greedy_failure = None
    for index, layer in enumerate(completed_layers):
        choices = [edge for edge in layer.incoming_edges if edge.source_index == greedy_index]
        if not choices:
            greedy_failure = index
            break
        best = min(choices, key=lambda edge: (edge.travel_rad, edge.target_index))
        greedy_index = best.target_index
        greedy_cost += best.travel_rad
    greedy_complete = greedy_failure is None and len(completed_layers) == len(layers)
    return IKGraphResult(tuple(completed_layers), path, failure, total,
                         greedy_complete, greedy_failure,
                         greedy_cost if greedy_complete else None,
                         candidate_edges, step_rejections, collision_rejections,
                         collision_samples, collision_samples > 0, enforce_start_step)


def solve_ik_path(
    arm: SixR, mount: ChassisMount, path: Sequence[FlangeWaypoint],
    seed: np.ndarray, state_free: StateFree | None = None,
    edge_free: EdgeFree | None = None,
    sobol_tiers: tuple[int, ...] = (32, 64, 128),
    backward_continuation: bool = True,
    max_joint_step_rad: float = 0.5,
    interpolation_step_rad: float = 0.05,
    enforce_start_step: bool = False,
) -> IKGraphResult:
    """Enumerate numerical IK roots at each pose and search all valid edges."""
    layers = enumerate_path_layers(arm, mount, path, seed, state_free,
                                   sobol_tiers, backward_continuation)
    return search_ik_graph(layers, seed, max_joint_step_rad,
                           interpolation_step_rad, edge_free, enforce_start_step)
