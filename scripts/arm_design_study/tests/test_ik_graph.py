import numpy as np
from scripts.arm_design_study.ik_graph import GraphLayer, GraphNode, search_ik_graph

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
