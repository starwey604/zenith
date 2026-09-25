"""Prepare and run the same complete task suite for generated 6R topologies."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from .length_sweep_v2 import ROOT, sweep
from .topology_grammar import generate_topology_catalog


DEFAULT_SCENE = ROOT / "configs/benchmark.topology_v1.chassis250.synthetic.json"
DEFAULT_STORAGE = ROOT / "configs/storage_2026.stress.synthetic.json"
DEFAULT_MODULE = ROOT / "configs/module_2027.stress.synthetic.json"
DEFAULT_PARKING = ("rear_left", "rear_center", "rear_right", "mid_left")


def prepare_inputs(output_root: Path, base_path: Path = DEFAULT_SCENE,
                   sobol_sample_count: int = 0,
                   solver_mode: str = "greedy",
                   ik_sobol_tiers: tuple[int, ...] = (8, 16, 32),
                   max_workers: int = 3,
                   reserve_available_memory_gib: float = 2.0) -> tuple[Path, Path]:
    """Freeze generated IDs, geometry and equal task settings into input files."""
    if sobol_sample_count < 0 or (sobol_sample_count and
                                  (sobol_sample_count < 2 or sobol_sample_count & (sobol_sample_count - 1))):
        raise ValueError("Sobol length sample count must be zero or a power of two >= 2")
    if solver_mode not in ("greedy", "graph"):
        raise ValueError("solver_mode must be greedy or graph")
    if isinstance(max_workers, bool) or not isinstance(max_workers, int) or not 1 <= max_workers <= 24:
        raise ValueError("max_workers must be 1..24")
    if reserve_available_memory_gib <= 0:
        raise ValueError("memory reserve must be positive")
    catalog = generate_topology_catalog()
    scene = copy.deepcopy(json.loads(base_path.read_text(encoding="utf-8")))
    scene["scenario_id"] = "rm_orthogonal_grammar_full_tasks_v1_chassis250_synthetic"
    scene["robots"] = [candidate.topology_id for candidate in catalog.candidates]
    radii = next(iter(scene["geometry"]["link_capsule_radii_by_robot_m"].values()))
    scene["geometry"]["link_capsule_radii_by_robot_m"] = {
        name: list(radii) for name in scene["robots"]}
    scene["length_variants"] = [{"variant_id": "nominal", "anchor_span_scales": {}}]
    scene["ik_solver"] = {"mode": solver_mode, "sobol_tiers": list(ik_sobol_tiers),
                          "backward_continuation": True,
                          "max_joint_step_rad": 0.5,
                          "interpolation_step_rad": 0.1,
                          "enforce_start_step": False}
    interface = scene["tasks"]["module_2027"]["interface_file"]
    scene["tasks"]["module_2027"]["interface_file"] = str((base_path.parent / interface).resolve())
    scene["notes"] = ("受约束正交六轴语法的统一合成全任务扫描；每个构型共用底盘250 mm、"
                      "关节限位、粗胶囊半径、四泊位及同一组装配/取矿/存矿任务；"
                      f"IK模式={solver_mode}；材料载荷未评分。")
    spec = {"schema_version": 2,
            "run_id": f"rm_orthogonal_grammar_{solver_mode}_length{sobol_sample_count}_v1_20260925",
            "source_type": "design_assumption",
            "robots": scene["robots"],
            "span_indices": [2, 3, 4, 5],
            "sampling": {"mode": "sobol", "factor_bounds": [0.85, 1.15],
                         "sample_count": sobol_sample_count, "seed": 20260925,
                         "include_baseline": True},
            "parking_ids": list(DEFAULT_PARKING),
            "max_workers": max_workers,
            "reserve_available_memory_gib": reserve_available_memory_gib,
            "notes": "同一完整任务分母；每构型基线加指定数量的固定Sobol长度样本，并遍历四个泊位。"}
    output_root.mkdir(parents=True, exist_ok=True)
    scene_path, spec_path = output_root / "scene.json", output_root / "spec.json"
    for path, data in ((scene_path, scene), (spec_path, spec)):
        serialized = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if path.exists() and path.read_text(encoding="utf-8") != serialized:
            raise ValueError(f"prepared input changed; use a new run directory: {path}")
        path.write_text(serialized, encoding="utf-8")
    return scene_path, spec_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, default=ROOT / "runs/grammar_baseline_v1")
    parser.add_argument("--length-samples", type=int, default=0)
    parser.add_argument("--solver", choices=("greedy", "graph"), default="greedy")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--memory-reserve-gib", type=float, default=2.0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    scene_path, spec_path = prepare_inputs(args.work_dir / "inputs",
                                          sobol_sample_count=args.length_samples,
                                          solver_mode=args.solver,
                                          max_workers=args.workers,
                                          reserve_available_memory_gib=args.memory_reserve_gib)
    if args.prepare_only:
        print(json.dumps({"scene": str(scene_path), "spec": str(spec_path)}))
        return
    result = sweep(spec_path, scene_path, DEFAULT_STORAGE, DEFAULT_MODULE,
                   args.work_dir, args.work_dir / "scratch", args.workers, args.limit)
    print(json.dumps({"candidate_count": result["manifest"]["candidate_count"],
                      "completed": len(result["complete"]),
                      "errors": result["errors"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
