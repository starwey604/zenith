import json

import numpy as np

from scripts.arm_design_study.chassis import ChassisMount
from scripts.arm_design_study.ik_graph import (
    GraphLayer, GraphNode, search_ik_graph, solve_ik_path,
)
from scripts.arm_design_study.model_import import load_local
from scripts.arm_design_study.task_2026 import TaskWaypoint, ToolIKTarget, solve_task_ik_graph


def _node(first_joint: float, branch: int = 0, lift: int = 0) -> GraphNode:
    q = np.zeros(6)
    q[0] = first_joint
    return GraphNode(q, branch, lift, 0.0, 0.0)


def test_global_path_recovers_when_greedy_choice_has_no_next_edge():
    layers = (
        GraphLayer(0, "choose", (_node(0.0, 0), _node(0.4, 1))),
        GraphLayer(1, "continue", (_node(0.8),)),
    )
    result = search_ik_graph(layers, np.zeros(6), max_joint_step_rad=0.5)
    assert result.complete
    assert [round(choice.q_rad[0], 3) for choice in result.path] == [0.4, 0.8]
    assert not result.greedy_complete
    assert result.greedy_failure_index == 1
    assert len(result.layers[1].incoming_edges) == 1
    assert result.layers[1].incoming_edges[0].source_index == 1


def test_graph_minimizes_total_travel_when_greedy_also_completes():
    layers = (
        GraphLayer(0, "first", (_node(0.0, 0), _node(0.4, 1))),
        GraphLayer(1, "second", (_node(-0.4, 0), _node(0.8, 1))),
        GraphLayer(2, "last", (_node(0.9),)),
    )
    result = search_ik_graph(layers, np.zeros(6), max_joint_step_rad=1.5)
    assert result.complete and result.greedy_complete
    assert np.isclose(result.total_joint_travel_rad, 0.9)
    assert np.isclose(result.greedy_joint_travel_rad, 1.7)


def test_interpolated_collision_blocks_edge_between_free_nodes():
    layers = (GraphLayer(0, "start", (_node(0.0),)),
              GraphLayer(1, "blocked", (_node(0.4),)),
              GraphLayer(2, "later", (_node(0.45),)))
    checked = []

    def edge_free(q, index, alpha):
        checked.append((index, alpha, q[0]))
        return not (index == 1 and 0.15 <= q[0] <= 0.25)

    result = search_ik_graph(layers, np.zeros(6), max_joint_step_rad=0.5,
                             interpolation_step_rad=0.1, edge_free=edge_free)
    assert not result.complete
    assert result.failure["reason"] == "edge_collision"
    assert len(result.path) == 1
    assert result.collision_rejections == 1
    assert any(index == 1 and 0.15 <= q <= 0.25 for index, _, q in checked)
    assert result.to_dict(include_graph=True)["layers"][1]["edges"] == []
    assert len(result.layers) == 3  # The graph still includes layers after the first disconnection.
    assert len(result.layers[2].incoming_edges) == 1


def test_lifted_turn_uses_real_joint_step_not_wrapped_distance():
    layers = (GraphLayer(0, "start", (_node(0.0),)),
              GraphLayer(1, "full_turn", (_node(2 * np.pi),)))
    result = search_ik_graph(layers, np.zeros(6), max_joint_step_rad=0.5)
    assert result.failure["reason"] == "joint_step"
    assert result.step_rejections == 1


def test_real_two_pose_path_uses_both_continuation_passes_and_is_repeatable():
    arm = load_local("rm2p_spherical_wrist")
    mount = ChassisMount(0.0, 0.0, 0.0, np.eye(4))
    q0 = np.array([0.3, -0.7, 0.5, 0.2, 0.6, -0.4])
    q1 = q0 + np.array([0.02, -0.03, 0.03, 0.02, -0.02, 0.01])
    path = [ToolIKTarget("a", arm.fk(q0)), ToolIKTarget("b", arm.fk(q1))]
    options = dict(sobol_tiers=(2, 4), max_joint_step_rad=0.2,
                   enforce_start_step=True)
    result = solve_ik_path(arm, mount, path, q0, **options)
    repeated = solve_ik_path(arm, mount, path, q0, **options)
    assert result.complete
    assert json.dumps(result.to_dict(), sort_keys=True) == json.dumps(repeated.to_dict(), sort_keys=True)
    assert all(layer.forward_diagnostics is not None and layer.backward_diagnostics is not None
               for layer in result.layers)
    assert len(result.path) == 2
    assert all(np.linalg.norm(arm.pose_error(choice.q_rad, point.world_flange)) < 1e-3
               for choice, point in zip(result.path, path))
    assert np.max(np.abs(result.path[1].q_rad - result.path[0].q_rad)) <= 0.2


def test_tool_task_wrapper_maps_world_tool_to_flange():
    arm = load_local("rm2p_spherical_wrist")
    mount = ChassisMount(0.0, 0.0, 0.0, np.eye(4))
    q = np.array([0.3, -0.7, 0.5, 0.2, 0.6, -0.4])
    offset = np.eye(4)
    offset[2, 3] = 0.12
    path = [TaskWaypoint("known", arm.fk(q) @ offset, 1.0)]
    checked = []
    result = solve_task_ik_graph(
        arm, mount, path, offset, q,
        state_free=lambda candidate, index, waypoint: checked.append(waypoint.phase) or True,
        sobol_tiers=(2, 4), enforce_start_step=True,
    )
    assert result.complete
    assert checked and set(checked) == {"known"}
    assert np.linalg.norm(arm.pose_error(result.path[0].q_rad, arm.fk(q))) < 1e-3


def test_all_colliding_ik_nodes_report_state_collision():
    arm = load_local("rm2p_spherical_wrist")
    mount = ChassisMount(0.0, 0.0, 0.0, np.eye(4))
    q = np.array([0.3, -0.7, 0.5, 0.2, 0.6, -0.4])
    result = solve_ik_path(
        arm, mount, [ToolIKTarget("blocked", arm.fk(q))], q,
        state_free=lambda _q, _index, _point: False,
        sobol_tiers=(2, 4),
    )
    assert result.failure["reason"] == "state_collision"
    assert result.layers[0].forward_diagnostics.geometric_branches > 0
    assert not result.path
