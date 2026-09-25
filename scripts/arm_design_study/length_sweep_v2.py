"""Resume-safe full-task Sobol sweep over each six-axis model's nonzero spans 2..5."""
from __future__ import annotations

import argparse
import copy
import csv
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import time

from .length_sweep import _available_memory_gib, _canonical_hash, _sha256, _worker_init


ROOT = Path(__file__).resolve().parent
SPAN_KEYS = (2, 3, 4, 5)


def validate_spec(spec: dict, scene: dict) -> None:
    if (spec.get("schema_version") != 2 or spec.get("source_type") != "design_assumption"
            or spec.get("span_indices") != list(SPAN_KEYS)):
        raise ValueError("v2 needs synthetic schema 2 and spans 2..5")
    robots, parks = spec.get("robots"), spec.get("parking_ids")
    available_parks = {p["parking_id"] for p in scene["parking"]["candidates"]}
    if (not isinstance(robots, list) or not robots or len(set(robots)) != len(robots)
            or not set(robots) <= set(scene["robots"])):
        raise ValueError("v2 robots must be unique reference models in scene")
    if (not isinstance(parks, list) or not parks or len(set(parks)) != len(parks)
            or not set(parks) <= available_parks):
        raise ValueError("v2 parking IDs must be unique candidates in scene")
    sampling = spec.get("sampling", {})
    factor_bounds = sampling.get("factor_bounds")
    span_bounds = sampling.get("span_bounds_m")
    count = sampling.get("sample_count")
    factor_bounds_valid = (isinstance(factor_bounds, list) and len(factor_bounds) == 2
                           and all(isinstance(value, (int, float)) and not isinstance(value, bool)
                                   for value in factor_bounds)
                           and 0.25 <= factor_bounds[0] < factor_bounds[1] <= 4.0)
    span_bounds_valid = (isinstance(span_bounds, dict)
                         and set(span_bounds) == {str(index) for index in SPAN_KEYS}
                         and all(isinstance(pair, list) and len(pair) == 2
                                 and all(isinstance(value, (int, float)) and not isinstance(value, bool)
                                         and 0 < value <= 2.0 for value in pair)
                                 and pair[0] < pair[1] for pair in span_bounds.values()))
    explicit = sampling.get("explicit_spans_m", [])
    explicit_valid = (isinstance(explicit, list)
                      and all(isinstance(item, dict)
                              and set(item) == {str(index) for index in SPAN_KEYS}
                              and all(isinstance(value, (int, float)) and not isinstance(value, bool)
                                      and 0 < value <= 2.0 for value in item.values())
                              for item in explicit))
    if (sampling.get("mode") != "sobol" or factor_bounds_valid == span_bounds_valid
            or isinstance(count, bool) or not isinstance(count, int) or count < 0
            or (count != 0 and (count < 2 or count & (count - 1)))
            or not isinstance(sampling.get("seed"), int)
            or sampling["seed"] < 0 or sampling.get("include_baseline") is not True
            or not explicit_valid):
        raise ValueError("v2 needs zero or a fixed-seed Sobol power-of-two count, one bounds mode, baseline and valid explicit spans")
    if (isinstance(spec.get("max_workers"), bool) or not isinstance(spec.get("max_workers"), int)
            or not 1 <= spec["max_workers"] <= 3):
        raise ValueError("v2 limits workers to one, two or three for the 12 GB laptop")


def generate_candidates(spec: dict, scene: dict) -> list[dict]:
    """Only nonzero zero-pose anchor spans receive factors; zero spans stay fixed."""
    validate_spec(spec, scene)
    from scipy.stats import qmc
    from .length_design import anchor_spans_m
    from .model_import import load_local

    parking = {p["parking_id"]: p for p in scene["parking"]["candidates"]}
    sampling = spec["sampling"]
    factor_bounds = sampling.get("factor_bounds")
    span_bounds = sampling.get("span_bounds_m")
    count = spec["sampling"]["sample_count"]
    candidates = []
    for robot in spec["robots"]:
        reference = anchor_spans_m(load_local(robot))
        active = [i for i in SPAN_KEYS if reference[i] > 1e-8]
        if not active:
            raise ValueError(f"{robot} has no nonzero design span")
        if span_bounds is not None and set(map(int, span_bounds)) != set(active):
            raise ValueError(f"{robot} absolute span bounds must match its nonzero design spans")
        points = (qmc.Sobol(d=len(active), scramble=True, seed=spec["sampling"]["seed"]).random_base2(
            m=count.bit_length() - 1) if count else [])
        samples: list[tuple[str, tuple[float, ...]]] = [("baseline", tuple(1.0 for _ in active))]
        for explicit_index, values in enumerate(sampling.get("explicit_spans_m", []), start=1):
            factors = tuple(float(values[str(index)] / reference[index]) for index in active)
            samples.append((f"explicit_{explicit_index}", factors))
        if span_bounds is None:
            lower, upper = factor_bounds
            sobol_factors = [tuple(float(lower + value * (upper - lower)) for value in point)
                             for point in points]
        else:
            sobol_factors = [tuple(float((span_bounds[str(index)][0]
                                          + value * (span_bounds[str(index)][1]
                                                     - span_bounds[str(index)][0]))
                                         / reference[index])
                                   for index, value in zip(active, point)) for point in points]
        samples.extend(("sobol", factors) for factors in sobol_factors)
        for sample_index, (sampling_kind, factors) in enumerate(samples):
            scales = {str(i): factor for i, factor in zip(active, factors)}
            spans = {str(i): reference[i] * scales.get(str(i), 1.0) for i in SPAN_KEYS}
            for park_id in spec["parking_ids"]:
                cid = f"{robot}_q{sample_index:02d}_{park_id}"
                candidates.append({"candidate_id": cid, "robot": robot,
                                   "sample_index": sample_index,
                                   "sampling_kind": sampling_kind,
                                   "active_span_indices": active,
                                   "anchor_span_scales": scales,
                                   "span_m": spans,
                                   "parking_id": park_id,
                                   "parking": copy.deepcopy(parking[park_id])})
    if len({c["candidate_id"] for c in candidates}) != len(candidates):
        raise ValueError("candidate IDs collide")
    return candidates


def input_manifest(spec_path: Path, scene_path: Path, storage_path: Path,
                   module_path: Path) -> dict:
    from .model_import import model_reference_paths

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    candidates = generate_candidates(spec, scene)
    source_files = tuple(sorted(ROOT.glob("*.py")))
    paths = model_reference_paths(spec["robots"])
    inputs = {"spec_sha256": _sha256(spec_path), "base_scene_sha256": _sha256(scene_path),
              "storage_task_sha256": _sha256(storage_path),
              "module_stress_sha256": _sha256(module_path),
              "source_sha256": _canonical_hash({p.name: _sha256(p) for p in source_files}),
              "model_sha256": {str(p): _sha256(p) for p in paths}}
    return {"schema_version": 2, "run_id": spec["run_id"],
            "input_key": _canonical_hash(inputs), "inputs": inputs,
            "candidate_ids": [c["candidate_id"] for c in candidates],
            "candidate_count": len(candidates), "spec": spec}


def candidate_scene(base: dict, base_path: Path, candidate: dict) -> dict:
    scene = copy.deepcopy(base)
    scene["scenario_id"] = f"{base['scenario_id']}::{candidate['candidate_id']}"
    scene["robots"] = [candidate["robot"]]
    scene["length_variants"] = [{"variant_id": candidate["candidate_id"],
                                 "anchor_span_scales": candidate["anchor_span_scales"]}]
    scene["parking"]["candidates"] = [copy.deepcopy(candidate["parking"])]
    interface_file = base["tasks"]["module_2027"]["interface_file"]
    scene["tasks"]["module_2027"]["interface_file"] = str((base_path.parent / interface_file).resolve())
    return scene


def summarize(candidate: dict, storage: dict, pickup: dict, benchmark: dict,
              module_stress: dict) -> dict:
    st = storage["candidate_summary"][0]
    pk = pickup["candidate_summary"][0]
    bm = benchmark["candidate_summary"][0]
    by_slot = {slot: sum(row["exit_geometric_complete"] for row in pickup["rows"]
                         if row["slot_id"] == slot) for slot in range(1, 7)}
    return {"candidate_id": candidate["candidate_id"], "robot": candidate["robot"],
            "sample_index": candidate["sample_index"],
            "sampling_kind": candidate["sampling_kind"],
            "parking_id": candidate["parking_id"],
            "active_span_indices": candidate["active_span_indices"],
            "anchor_span_scales": candidate["anchor_span_scales"],
            "span_m": candidate["span_m"],
            "tier1_complete": st["tiers"]["1"]["complete"],
            "tier2_complete": st["tiers"]["2"]["complete"],
            "tier3_complete": st["tiers"]["3"]["complete"],
            "storage_balanced_fraction": st["balanced_completion_fraction"],
            "pickup_complete": pk["complete_case_count"],
            "pickup_by_slot": by_slot,
            "pickup_all_angle_slots": pk["all_sampled_angles_slot_count"],
            "pickup_min_slot_complete": min(by_slot.values()),
            "module_complete": bm["module_complete"],
            "module_stress_complete": module_stress["complete_count"],
            "module_stress_total": module_stress["case_count"],
            "module_stress_min_clearance_m": min(
                (row["min_clearance_proxy_m"] for row in module_stress["rows"]
                 if row["min_clearance_proxy_m"] is not None), default=None),
            "module_stress_min_joint_margin_rad": min(
                (row["min_joint_limit_margin_rad"] for row in module_stress["rows"]
                 if row["min_joint_limit_margin_rad"] is not None), default=None)}


def artifact_path(output_dir: Path, candidate_id: str) -> Path:
    return output_dir / "candidates" / f"{candidate_id}.json"


def run_candidate(candidate: dict, base_path: Path, storage_path: Path,
                  module_path: Path, manifest: dict, output_dir: Path,
                  scratch_dir: Path) -> dict:
    from .benchmark import screen_scene
    from .module_stress import screen_module_stress
    from .pickup_exit import screen_pickup_exit
    from .storage_2026 import screen_storage_scene

    base = json.loads(base_path.read_text(encoding="utf-8"))
    scene = candidate_scene(base, base_path, candidate)
    scratch_dir.mkdir(parents=True, exist_ok=True)
    scene_path = scratch_dir / f"{candidate['candidate_id']}.scene.json"
    scene_path.write_text(json.dumps(scene, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                          encoding="utf-8")
    start = time.monotonic()
    storage = screen_storage_scene(scene_path, storage_path)
    pickup = screen_pickup_exit(scene_path)
    benchmark = screen_scene(scene_path)
    module_stress = screen_module_stress(scene_path, module_path)
    if (len(storage["rows"]) != 67 or len(pickup["rows"]) != 72
            or len(benchmark["rows"]) != 8 or len(module_stress["rows"]) != 9
            or storage["excluded_difficulty"] != 4):
        raise ValueError("worker did not run the identical full task set")
    scene_hash = _sha256(scene_path)
    if (any(report["scene_sha256"] != scene_hash
            for report in (storage, pickup, benchmark, module_stress))
            or storage["task_sha256"] != manifest["inputs"]["storage_task_sha256"]
            or module_stress["stress_sha256"] != manifest["inputs"]["module_stress_sha256"]):
        raise ValueError("worker input hashes disagree")
    summary = summarize(candidate, storage, pickup, benchmark, module_stress)
    summary["elapsed_s"] = time.monotonic() - start
    artifact = {"schema_version": 2, "input_key": manifest["input_key"],
                "candidate": candidate, "summary": summary,
                "base_scene_sha256": manifest["inputs"]["base_scene_sha256"],
                "derived_scene_sha256": scene_hash,
                "storage_task_sha256": manifest["inputs"]["storage_task_sha256"],
                "module_stress_sha256": manifest["inputs"]["module_stress_sha256"],
                "reports": {"storage": storage, "pickup_exit": pickup,
                            "benchmark": benchmark, "module_stress": module_stress}}
    path = artifact_path(output_dir, candidate["candidate_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    temp.write_text(json.dumps(artifact, ensure_ascii=False, allow_nan=False,
                               separators=(",", ":")), encoding="utf-8")
    os.replace(temp, path)
    return summary


def read_completed(output_dir: Path, manifest: dict, candidates: list[dict]) -> dict[str, dict]:
    complete = {}
    for candidate in candidates:
        path = artifact_path(output_dir, candidate["candidate_id"])
        if not path.exists():
            continue
        artifact = json.loads(path.read_text(encoding="utf-8"))
        if (artifact.get("schema_version") != 2 or artifact.get("input_key") != manifest["input_key"]
                or artifact.get("candidate") != candidate):
            raise ValueError(f"stale or mismatched checkpoint: {path}")
        complete[candidate["candidate_id"]] = artifact["summary"]
    return complete


def write_summaries(output_dir: Path, manifest: dict, complete: dict[str, dict],
                    errors: dict[str, str]) -> None:
    ordered = [complete[cid] for cid in manifest["candidate_ids"] if cid in complete]
    report = {"schema_version": 2, "run_id": manifest["run_id"],
              "input_key": manifest["input_key"], "inputs": manifest["inputs"],
              "spec": manifest["spec"], "candidate_count": manifest["candidate_count"],
              "complete_candidate_count": len(ordered), "errors": errors, "rows": ordered}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                                  allow_nan=False) + "\n", encoding="utf-8")
    fields = ("candidate_id", "robot", "sample_index", "sampling_kind", "parking_id",
              "span2_mm", "span3_mm", "span4_mm", "span5_mm",
              "factor2", "factor3", "factor4", "factor5",
              "tier1_complete", "tier2_complete", "tier3_complete",
              "storage_balanced_fraction", "pickup_complete", "pickup_min_slot_complete",
              "module_complete", "module_stress_complete", "module_stress_total",
              "module_stress_min_clearance_m", "module_stress_min_joint_margin_rad", "elapsed_s")
    with (output_dir / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in ordered:
            flat = dict(row)
            for i in SPAN_KEYS:
                flat[f"span{i}_mm"] = row["span_m"][str(i)] * 1000
                flat[f"factor{i}"] = row["anchor_span_scales"].get(str(i))
            writer.writerow({key: flat.get(key) for key in fields})


def sweep(spec_path: Path, base_path: Path, storage_path: Path, module_path: Path,
          output_dir: Path, scratch_dir: Path, workers: int | None = None,
          limit: int | None = None) -> dict:
    manifest = input_manifest(spec_path, base_path, storage_path, module_path)
    candidates = generate_candidates(manifest["spec"], json.loads(base_path.read_text(encoding="utf-8")))
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists():
        if json.loads(manifest_path.read_text(encoding="utf-8")) != manifest:
            raise ValueError("run directory belongs to different inputs")
    else:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
    complete = read_completed(output_dir, manifest, candidates)
    pending = [c for c in candidates if c["candidate_id"] not in complete]
    if limit is not None:
        if limit < 0:
            raise ValueError("limit must be nonnegative")
        pending = pending[:limit]
    worker_count = manifest["spec"]["max_workers"] if workers is None else workers
    if not 1 <= worker_count <= manifest["spec"]["max_workers"]:
        raise ValueError("workers exceeds memory-safe cap")
    reserve = float(manifest["spec"].get("reserve_available_memory_gib", 2.0))
    errors: dict[str, str] = {}
    print(json.dumps({"run_id": manifest["run_id"], "candidate_count": len(candidates),
                      "completed_before_run": len(complete), "pending_this_run": len(pending),
                      "workers": worker_count, "memory_reserve_gib": reserve},
                     ensure_ascii=False), flush=True)
    if pending:
        context = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(max_workers=worker_count, mp_context=context,
                                 initializer=_worker_init, max_tasks_per_child=8) as executor:
            active = {}
            cursor = 0
            while cursor < len(pending) or active:
                while cursor < len(pending) and len(active) < worker_count:
                    if _available_memory_gib() < reserve:
                        break
                    candidate = pending[cursor]
                    cursor += 1
                    future = executor.submit(run_candidate, candidate, base_path, storage_path,
                                             module_path, manifest, output_dir, scratch_dir)
                    active[future] = candidate["candidate_id"]
                if not active:
                    print(f"Memory reserve active: available={_available_memory_gib():.2f} GiB",
                          flush=True)
                    time.sleep(10)
                    continue
                done, _ = wait(active, return_when=FIRST_COMPLETED, timeout=30)
                for future in done:
                    cid = active.pop(future)
                    try:
                        summary = future.result()
                    except Exception as error:
                        errors[cid] = f"{type(error).__name__}: {error}"
                        print(json.dumps({"candidate_id": cid, "error": errors[cid]},
                                         ensure_ascii=False), flush=True)
                    else:
                        complete[cid] = summary
                        print(json.dumps({"candidate_id": cid, "completed": len(complete),
                                          "total": manifest["candidate_count"],
                                          "tier3": f"{summary['tier3_complete']}/27",
                                          "pickup": f"{summary['pickup_complete']}/72",
                                          "module": f"{summary['module_stress_complete']}/9",
                                          "elapsed_s": round(summary["elapsed_s"], 1)},
                                         ensure_ascii=False), flush=True)
                    write_summaries(output_dir, manifest, complete, errors)
    write_summaries(output_dir, manifest, complete, errors)
    return {"manifest": manifest, "complete": complete, "errors": errors}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=ROOT / "configs/length_sweep.v2.json")
    parser.add_argument("--scene", type=Path, default=ROOT / "configs/benchmark.six_axis_v2.synthetic.json")
    parser.add_argument("--storage-task", type=Path,
                        default=ROOT / "configs/storage_2026.stress.synthetic.json")
    parser.add_argument("--module-stress", type=Path,
                        default=ROOT / "configs/module_2027.stress.synthetic.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "runs/length_sweep_v2")
    parser.add_argument("--scratch-dir", type=Path, default=ROOT / "runs/length_sweep_v2_scratch")
    parser.add_argument("--workers", type=int)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    result = sweep(args.spec, args.scene, args.storage_task, args.module_stress,
                   args.output_dir, args.scratch_dir, args.workers, args.limit)
    print(json.dumps({"candidate_count": result["manifest"]["candidate_count"],
                      "complete_candidate_count": len(result["complete"]),
                      "error_count": len(result["errors"]), "output_dir": str(args.output_dir)},
                     ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
