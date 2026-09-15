"""Command-line geometry checks and explicitly synthetic docking trial."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import numpy as np

from .bayonet import Bayonet
from .bayonet_trajectory import generate_bayonet_path, follow_ik
from .chassis import ChassisMount
from .frames import transform
from .length_design import anchor_spans_m, scale_anchor_spans
from .model_import import load_local, compare_mjcf_fk
from .task_2026 import core_assembly_path, energy_unit_pickup_path, follow_task_ik


ROOT = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Geometry-only six-axis model checks")
    parser.add_argument("command", choices=("models", "bayonet-demo", "core-2026", "pickup-2026"))
    parser.add_argument("--robot", choices=("xarm6", "ur5e"), default="xarm6")
    parser.add_argument("--interface", type=Path,
                        default=ROOT / "configs/bayonet_interface.synthetic_example.json")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--scale-span", action="append", default=[], metavar="INDEX:FACTOR",
                        help="stretch zero-pose joint-anchor span 1..5; synthetic geometry")
    parser.add_argument("--socket", type=Path, help="fixed world socket scenario JSON (T_W_D)")
    parser.add_argument("--parking-x", type=float, default=0.0)
    parser.add_argument("--parking-y", type=float, default=0.0)
    parser.add_argument("--parking-yaw", type=float, default=0.0)
    parser.add_argument("--mount-z", type=float, default=0.4)
    parser.add_argument("--task-config", type=Path)
    parser.add_argument("--slot", type=int, default=1, help="pickup slot 1..6")
    parser.add_argument("--solve-ik", action="store_true", help="track 2026 task with the chosen 6R arm and parked chassis")
    args = parser.parse_args()
    if args.command == "models":
        payload = {}
        for name in ("xarm6", "ur5e"):
            arm = load_local(name)
            sample = arm.limits[:, 0] + 0.63 * (arm.limits[:, 1] - arm.limits[:, 0])
            mismatch_m, mismatch_rotation = compare_mjcf_fk(name, sample)
            payload[name] = {"provenance": arm.provenance, "axis_relation": arm.axis_relation(),
                             "zero_pose_anchor_spans_m": anchor_spans_m(arm),
                             "reference_sample_q_rad": sample.tolist(),
                             "limits_rad": arm.limits.tolist(), "home_flange": arm.home_flange.tolist(),
                             "reference_fk_error_m": mismatch_m,
                             "reference_rotation_matrix_error": mismatch_rotation}
    elif args.command in ("core-2026", "pickup-2026"):
        if args.task_config is None:
            raise ValueError("missing_input: --task-config")
        config = json.loads(args.task_config.read_text(encoding="utf-8"))
        if config.get("source_type") not in ("measured", "design_assumption") or not config.get("scenario_id"):
            raise ValueError("task config needs source_type and scenario_id")
        if args.command == "core-2026":
            fields = ("pre_insert_world_tool", "p_axis_origin_world", "p_axis_world",
                      "q_axis_origin_world", "q_axis_world", "p_upward_turn_sign", "q_target_signed_rad")
            missing = [field for field in fields if config.get(field) is None]
            if missing:
                raise ValueError("missing_input: " + ", ".join(missing))
            sign = config["p_upward_turn_sign"]
            if sign not in (-1, 1):
                raise ValueError("p_upward_turn_sign must be +1 or -1")
            path = core_assembly_path(np.asarray(config["pre_insert_world_tool"]),
                                      np.asarray(config["p_axis_origin_world"]), np.asarray(config["p_axis_world"]),
                                      np.asarray(config["q_axis_origin_world"]), np.asarray(config["q_axis_world"]),
                                      sign * np.pi / 2, config["q_target_signed_rad"])
        else:
            units = config.get("energy_units")
            if not isinstance(units, list) or len(units) != 6 or args.slot not in range(1, 7):
                raise ValueError("pickup config must contain six slots and --slot 1..6")
            unit = next((item for item in units if item.get("slot_id") == args.slot), None)
            if unit is None:
                raise ValueError("pickup slot id missing")
            fields = ("world_grasp_tool", "outward_symmetry_axis_world",
                      "approach_distance_m", "extraction_distance_m")
            missing = [field for field in fields if unit.get(field) is None]
            if missing:
                raise ValueError("missing_input: " + ", ".join(f"slot_{args.slot}.{field}" for field in missing))
            path = energy_unit_pickup_path(np.asarray(unit["world_grasp_tool"]),
                                           np.asarray(unit["outward_symmetry_axis_world"]),
                                           unit["approach_distance_m"], unit["extraction_distance_m"])
        payload = {"scenario_id": config["scenario_id"], "source_type": config["source_type"],
                   "rule_reference": config.get("rule_reference"), "slot_id": args.slot if args.command == "pickup-2026" else None,
                   "waypoint_count": len(path),
                   "waypoints": [{"phase": point.phase, "progress": point.progress,
                                  "world_tool": point.world_tool.tolist()} for point in path]}
        if args.solve_ik:
            if config.get("flange_to_tool") is None:
                raise ValueError("missing_input: flange_to_tool")
            arm = load_local(args.robot)
            scales = {}
            for entry in args.scale_span:
                try:
                    index_str, factor_str = entry.split(":", 1)
                    scales[int(index_str)] = float(factor_str)
                except ValueError as error:
                    raise ValueError(f"invalid --scale-span {entry!r}; expected INDEX:FACTOR") from error
            if scales:
                arm = scale_anchor_spans(arm, scales)
            mount = ChassisMount(args.parking_x, args.parking_y, args.parking_yaw,
                                 transform(translation=np.array([0.0, 0.0, args.mount_z])))
            default_seed = (np.array([-np.pi / 2, -np.pi / 2, np.pi / 2,
                                      -np.pi / 2, -np.pi / 2, 0.0])
                            if args.robot == "ur5e" else np.zeros(6))
            seed = np.asarray(config.get("initial_joint_seed_rad", default_seed), dtype=float)
            if seed.shape != (6,) or not np.isfinite(seed).all():
                raise ValueError("initial_joint_seed_rad must contain six finite angles")
            records, failure = follow_task_ik(arm, mount, path,
                                              np.asarray(config["flange_to_tool"], dtype=float), seed)
            payload.update({"robot": args.robot, "robot_provenance": arm.provenance,
                            "anchor_span_scales": scales, "initial_joint_seed_rad": seed.tolist(),
                            "parking": {"x_m": args.parking_x, "y_m": args.parking_y, "yaw_rad": args.parking_yaw},
                            "chassis_to_arm": mount.chassis_to_arm.tolist(),
                            "ik_point_count": len(records), "failure": failure, "trajectory": records})
    else:
        interface = Bayonet.load(args.interface)
        arm = load_local(args.robot)
        scales = {}
        for entry in args.scale_span:
            try:
                index_str, factor_str = entry.split(":", 1)
                scales[int(index_str)] = float(factor_str)
            except ValueError as error:
                raise ValueError(f"invalid --scale-span {entry!r}; expected INDEX:FACTOR") from error
        if scales:
            arm = scale_anchor_spans(arm, scales)
        mount = ChassisMount(args.parking_x, args.parking_y, args.parking_yaw,
                             transform(translation=np.array([0.0, 0.0, args.mount_z])))
        # UR5e zero pose is a singular, fully straight-arm configuration.
        # Use the reference model's bent home joint pattern for this demo.
        home_seed = (np.array([-np.pi / 2, -np.pi / 2, np.pi / 2,
                               -np.pi / 2, -np.pi / 2, 0.0])
                     if args.robot == "ur5e" else np.zeros(6))
        seed = np.clip(home_seed, arm.limits[:, 0] + 1e-6, arm.limits[:, 1] - 1e-6)
        # Synthetic socket is placed relative to this arm's starting flange.
        # It is an algorithm check, not a RoboMaster workbench feasibility claim.
        initial = -0.8 * interface.data["guide"]["lead_cone_depth_m"]
        if args.socket:
            scenario = json.loads(args.socket.read_text(encoding="utf-8"))
            if scenario.get("world_socket") is None:
                raise ValueError("missing_input: world_socket")
            world_socket = np.asarray(scenario["world_socket"], dtype=float)
            if (world_socket.shape != (4, 4) or not np.isfinite(world_socket).all()
                    or not np.allclose(world_socket[3], [0, 0, 0, 1])
                    or not np.allclose(world_socket[:3, :3].T @ world_socket[:3, :3], np.eye(3), atol=1e-5)
                    or np.linalg.det(world_socket[:3, :3]) < 0.999):
                raise ValueError("world_socket must be a finite SE(3) 4x4 matrix")
            source_type = scenario.get("source_type")
            scenario_id = scenario.get("scenario_id")
            if source_type not in ("measured", "design_assumption") or not scenario_id:
                raise ValueError("socket scenario needs source_type and scenario_id")
        else:
            world_socket = mount.world_flange(arm, seed) @ transform(translation=np.array([0.0, 0.0, initial]))
            source_type = "design_assumption"
            scenario_id = "synthetic_bayonet_kinematic_demo"
        path = generate_bayonet_path(interface, world_socket)
        records, failure = follow_ik(arm, mount, path, seed)
        payload = {"scenario_id": scenario_id, "source_type": source_type,
                   "robot": args.robot, "interface": str(args.interface), "stationary_socket": world_socket.tolist(),
                   "robot_provenance": arm.provenance, "anchor_span_scales": scales,
                   "initial_joint_seed_rad": seed.tolist(),
                   "parking": {"x_m": args.parking_x, "y_m": args.parking_y, "yaw_rad": args.parking_yaw},
                   "chassis_to_arm": mount.chassis_to_arm.tolist(),
                   "path_point_count": len(path), "ik_point_count": len(records), "failure": failure,
                   "trajectory": records}
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(args.output)
    else:
        print(rendered)


if __name__ == "__main__":
    main()
