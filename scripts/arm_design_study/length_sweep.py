"""Low-memory, resumable full-task sweep of six-axis length hypotheses."""
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


ROOT = Path(__file__).resolve().parent
SOURCE_FILES = tuple(sorted(ROOT.glob("*.py")))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _factor_label(value: float) -> str:
    return f"{value:.3f}".replace(".", "p")


def validate_spec(spec: dict, scene: dict) -> None:
    if spec.get("schema_version") != 1 or spec.get("source_type") != "design_assumption":
        raise ValueError("sweep spec needs schema_version=1 and declared design assumptions")
    robots = spec.get("robots")
    parking = spec.get("parking_ids")
    if (not isinstance(robots, list) or not robots or len(set(robots)) != len(robots)
            or not set(robots) <= set(scene["robots"])):
        raise ValueError("sweep robots must be unique members of the base scene")
    known_parking = {item["parking_id"] for item in scene["parking"]["candidates"]}
    if (not isinstance(parking, list) or not parking or len(set(parking)) != len(parking)
            or not set(parking) <= known_parking):
        raise ValueError("sweep parking IDs must be unique members of the base scene")
    sampling = spec.get("sampling", {"mode": "grid"})
    if sampling.get("mode") == "grid":
        factors = spec.get("span_factors")
        if (not isinstance(factors, list) or len(factors) < 2
                or any(isinstance(value, bool) or not isinstance(value, (int, float))
                       or not 0.5 <= value <= 1.5 for value in factors)
                or len({round(float(value), 6) for value in factors}) != len(factors)):
            raise ValueError("grid needs distinct finite span factors in [0.5, 1.5]")
    elif sampling.get("mode") == "sobol":
        bounds = sampling.get("factor_bounds")
        count = sampling.get("sample_count")
        seed = sampling.get("seed")
        if (not isinstance(bounds, list) or len(bounds) != 2
                or any(not isinstance(pair, list) or len(pair) != 2 or not 0.5 <= pair[0] < pair[1] <= 1.5
                       for pair in bounds)
                or isinstance(count, bool) or not isinstance(count, int)
                or count < 2 or count & (count - 1)
                or isinstance(seed, bool) or not isinstance(seed, int) or seed < 0):
            raise ValueError("Sobol sampling needs two factor bounds, power-of-two count and fixed seed")
    else:
        raise ValueError("sampling mode must be grid or sobol")
    if spec.get("span_indices") != [2, 3]:
        raise ValueError("v1 varies only zero-pose anchor spans 2 and 3")
    if (isinstance(spec.get("max_workers"), bool) or not isinstance(spec.get("max_workers"), int)
            or not 1 <= spec["max_workers"] <= 2):
        raise ValueError("v1 limits workers to one or two for the 12 GB laptop")


def length_factor_pairs(spec: dict) -> list[tuple[float, float]]:
    sampling = spec.get("sampling", {"mode": "grid"})
    if sampling["mode"] == "grid":
        return [(float(factor2), float(factor3)) for factor2 in spec["span_factors"]
                for factor3 in spec["span_factors"]]
    from scipy.stats import qmc

    bounds = sampling["factor_bounds"]
    count = sampling["sample_count"]
    unit = qmc.Sobol(d=2, scramble=True, seed=sampling["seed"]).random_base2(
        m=count.bit_length() - 1)
    pairs = [(1.0, 1.0)]
    for vector in unit:
        pairs.append(tuple(float(low + value * (high - low))
                           for (low, high), value in zip(bounds, vector)))
    return pairs


def generate_candidates(spec: dict, scene: dict) -> list[dict]:
    """Fixed factor grid or fixed-seed two-dimensional quasi-Monte Carlo sample."""
    validate_spec(spec, scene)
    from .length_design import anchor_spans_m
    from .model_import import load_local

    parks = {item["parking_id"]: item for item in scene["parking"]["candidates"]}
    candidates = []
    pairs = length_factor_pairs(spec)
    for robot in spec["robots"]:
        spans = anchor_spans_m(load_local(robot))
        if spans[2] <= 0 or spans[3] <= 0:
            raise ValueError(f"{robot} has a zero span 2 or 3")
        for factor2, factor3 in pairs:
            for parking_id in spec["parking_ids"]:
                candidate_id = (f"{robot}_s2_{_factor_label(factor2)}"
                                f"_s3_{_factor_label(factor3)}_{parking_id}")
                candidates.append({"candidate_id": candidate_id, "robot": robot,
                                   "factor2": factor2, "factor3": factor3,
                                   "span2_m": spans[2] * factor2,
                                   "span3_m": spans[3] * factor3,
                                   "parking_id": parking_id,
                                   "parking": copy.deepcopy(parks[parking_id])})
    if len({item["candidate_id"] for item in candidates}) != len(candidates):
        raise ValueError("candidate IDs collide")
    return candidates


def input_manifest(spec_path: Path, scene_path: Path, task_path: Path) -> dict:
    from .model_import import XARM_XML, UR5E_XML, UR5E_CLASSES

    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    candidates = generate_candidates(spec, scene)
    inputs = {"spec_sha256": _sha256(spec_path), "base_scene_sha256": _sha256(scene_path),
              "storage_task_sha256": _sha256(task_path),
              "source_sha256": _canonical_hash({str(path.relative_to(ROOT)): _sha256(path)
                                                for path in SOURCE_FILES}),
              "model_sha256": {str(path): _sha256(path)
                               for path in (XARM_XML, UR5E_XML, UR5E_CLASSES)}}
    return {"schema_version": 1, "run_id": spec["run_id"],
            "input_key": _canonical_hash(inputs), "inputs": inputs,
            "candidate_ids": [item["candidate_id"] for item in candidates],
            "candidate_count": len(candidates), "spec": spec}


def candidate_scene(base_scene: dict, base_scene_path: Path, candidate: dict) -> dict:
    """Only candidate geometry/parking differs; all targets and obstacles stay fixed."""
    scene = copy.deepcopy(base_scene)
    scene["scenario_id"] = f"{base_scene['scenario_id']}::{candidate['candidate_id']}"
    scene["robots"] = [candidate["robot"]]
    scene["length_variants"] = [{"variant_id": candidate["candidate_id"],
                                 "anchor_span_scales": {"2": candidate["factor2"],
                                                        "3": candidate["factor3"]}}]
    scene["parking"]["candidates"] = [copy.deepcopy(candidate["parking"])]
    interface_file = base_scene["tasks"]["module_2027"]["interface_file"]
    scene["tasks"]["module_2027"]["interface_file"] = str(
        (base_scene_path.parent / interface_file).resolve())
    return scene


def _worker_init() -> None:
    # Each worker evaluates tiny matrices; nested BLAS threads would oversubscribe CPU.
    for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[key] = "1"


def _summary(candidate: dict, storage: dict, pickup: dict, benchmark: dict) -> dict:
    storage_summary = storage["candidate_summary"][0]
    pickup_summary = pickup["candidate_summary"][0]
    benchmark_summary = benchmark["candidate_summary"][0]
    by_slot = {slot: sum(row["exit_geometric_complete"] for row in pickup["rows"]
                         if row["slot_id"] == slot) for slot in range(1, 7)}
    return {"candidate_id": candidate["candidate_id"], "robot": candidate["robot"],
            "factor2": candidate["factor2"], "factor3": candidate["factor3"],
            "span2_m": candidate["span2_m"], "span3_m": candidate["span3_m"],
            "parking_id": candidate["parking_id"],
            "tier1_complete": storage_summary["tiers"]["1"]["complete"],
            "tier2_complete": storage_summary["tiers"]["2"]["complete"],
            "tier3_complete": storage_summary["tiers"]["3"]["complete"],
            "tier1_total": storage_summary["tiers"]["1"]["total"],
            "tier2_total": storage_summary["tiers"]["2"]["total"],
            "tier3_total": storage_summary["tiers"]["3"]["total"],
            "storage_balanced_fraction": storage_summary["balanced_completion_fraction"],
            "pickup_complete": pickup_summary["complete_case_count"],
            "pickup_total": pickup_summary["case_count"],
            "pickup_all_angle_slots": pickup_summary["all_sampled_angles_slot_count"],
            "pickup_min_slot_complete": min(by_slot.values()),
            "pickup_by_slot": by_slot,
            "module_complete": benchmark_summary["module_complete"]}


def _artifact_path(output_dir: Path, candidate_id: str) -> Path:
    return output_dir / "candidates" / f"{candidate_id}.json"


def run_candidate(candidate: dict, base_scene_path: Path, task_path: Path,
                  manifest: dict, output_dir: Path, scratch_dir: Path) -> dict:
    """Worker writes raw trajectory JSON in ignored runs/; coordinator gets only a summary."""
    from .benchmark import screen_scene
    from .pickup_exit import screen_pickup_exit
    from .storage_2026 import screen_storage_scene

    base_scene = json.loads(base_scene_path.read_text(encoding="utf-8"))
    scene = candidate_scene(base_scene, base_scene_path, candidate)
    scratch_dir.mkdir(parents=True, exist_ok=True)
    scene_path = scratch_dir / f"{candidate['candidate_id']}.scene.json"
    scene_path.write_text(json.dumps(scene, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                          encoding="utf-8")
    start = time.monotonic()
    storage = screen_storage_scene(scene_path, task_path)
    pickup = screen_pickup_exit(scene_path)
    benchmark = screen_scene(scene_path)
    if (len(storage["rows"]) != 67 or len(pickup["rows"]) != 72
            or len(benchmark["rows"]) != 8 or not storage["excluded_difficulty"] == 4):
        raise ValueError("worker did not run the fixed full task set")
    scene_hash = _sha256(scene_path)
    if (storage["scene_sha256"] != scene_hash or pickup["scene_sha256"] != scene_hash
            or benchmark["scene_sha256"] != scene_hash
            or storage["task_sha256"] != manifest["inputs"]["storage_task_sha256"]):
        raise ValueError("worker report input hashes disagree")
    summary = _summary(candidate, storage, pickup, benchmark)
    summary["elapsed_s"] = time.monotonic() - start
    artifact = {"schema_version": 1, "input_key": manifest["input_key"],
                "candidate": candidate, "summary": summary,
                "base_scene_sha256": manifest["inputs"]["base_scene_sha256"],
                "derived_scene_sha256": scene_hash,
                "storage_task_sha256": manifest["inputs"]["storage_task_sha256"],
                "reports": {"storage": storage, "pickup_exit": pickup, "benchmark": benchmark}}
    path = _artifact_path(output_dir, candidate["candidate_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(artifact, handle, ensure_ascii=False, allow_nan=False,
                  separators=(",", ":"))
    os.replace(temp, path)
    return summary


def read_completed(output_dir: Path, manifest: dict, candidates: list[dict]) -> dict[str, dict]:
    complete = {}
    for candidate in candidates:
        path = _artifact_path(output_dir, candidate["candidate_id"])
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            artifact = json.load(handle)
        if (artifact.get("input_key") != manifest["input_key"]
                or artifact.get("candidate") != candidate
                or artifact.get("schema_version") != 1):
            raise ValueError(f"stale or mismatched checkpoint: {path}")
        complete[candidate["candidate_id"]] = artifact["summary"]
    return complete


def _available_memory_gib() -> float:
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return float("inf")
    for line in meminfo.read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / 1024**2
    return float("inf")


def write_summaries(output_dir: Path, manifest: dict, complete: dict[str, dict],
                    errors: dict[str, str]) -> None:
    ordered = [complete[item] for item in manifest["candidate_ids"] if item in complete]
    report = {"schema_version": 1, "run_id": manifest["run_id"],
              "input_key": manifest["input_key"], "inputs": manifest["inputs"],
              "candidate_count": manifest["candidate_count"],
              "complete_candidate_count": len(ordered), "errors": errors, "rows": ordered}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    fields = ("candidate_id", "robot", "factor2", "factor3", "span2_m", "span3_m",
              "parking_id", "tier1_complete", "tier2_complete", "tier3_complete",
              "tier1_total", "tier2_total", "tier3_total", "storage_balanced_fraction",
              "pickup_complete", "pickup_total", "pickup_all_angle_slots",
              "pickup_min_slot_complete", "module_complete", "elapsed_s")
    with (output_dir / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in ordered:
            writer.writerow({key: row[key] for key in fields})


def sweep(spec_path: Path, base_scene_path: Path, task_path: Path, output_dir: Path,
          scratch_dir: Path, workers: int | None = None, limit: int | None = None) -> dict:
    manifest = input_manifest(spec_path, base_scene_path, task_path)
    spec = manifest["spec"]
    scene = json.loads(base_scene_path.read_text(encoding="utf-8"))
    candidates = generate_candidates(spec, scene)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing != manifest:
            raise ValueError("run directory belongs to different inputs; choose a new output directory")
    else:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
    complete = read_completed(output_dir, manifest, candidates)
    pending = [item for item in candidates if item["candidate_id"] not in complete]
    if limit is not None:
        if limit < 0:
            raise ValueError("limit must be nonnegative")
        pending = pending[:limit]
    worker_count = spec["max_workers"] if workers is None else workers
    if not 1 <= worker_count <= spec["max_workers"]:
        raise ValueError("workers exceeds the memory-safe v1 cap")
    reserve = float(spec.get("reserve_available_memory_gib", 2.0))
    errors: dict[str, str] = {}
    print(json.dumps({"run_id": manifest["run_id"], "candidate_count": len(candidates),
                      "completed_before_run": len(complete), "pending_this_run": len(pending),
                      "workers": worker_count, "reserve_available_memory_gib": reserve},
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
                    future = executor.submit(run_candidate, candidate, base_scene_path, task_path,
                                             manifest, output_dir, scratch_dir)
                    active[future] = candidate["candidate_id"]
                if not active:
                    print(f"Memory reserve active: available={_available_memory_gib():.2f} GiB",
                          flush=True)
                    time.sleep(10)
                    continue
                done, _ = wait(active, return_when=FIRST_COMPLETED, timeout=30)
                for future in done:
                    candidate_id = active.pop(future)
                    try:
                        summary = future.result()
                    except Exception as error:  # keep successful checkpoints and report failures
                        errors[candidate_id] = f"{type(error).__name__}: {error}"
                        print(json.dumps({"candidate_id": candidate_id,
                                          "error": errors[candidate_id]}, ensure_ascii=False), flush=True)
                    else:
                        complete[candidate_id] = summary
                        print(json.dumps({"candidate_id": candidate_id,
                                          "completed": len(complete),
                                          "total": manifest["candidate_count"],
                                          "tier3": f"{summary['tier3_complete']}/27",
                                          "pickup": f"{summary['pickup_complete']}/72",
                                          "elapsed_s": round(summary["elapsed_s"], 1)},
                                         ensure_ascii=False), flush=True)
                    write_summaries(output_dir, manifest, complete, errors)
    write_summaries(output_dir, manifest, complete, errors)
    return {"manifest": manifest, "complete": complete, "errors": errors}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=ROOT / "configs/length_sweep.v1.json")
    parser.add_argument("--scene", type=Path, default=ROOT / "configs/benchmark.synthetic.json")
    parser.add_argument("--storage-task", type=Path,
                        default=ROOT / "configs/storage_2026.stress.synthetic.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "runs/length_sweep_v1")
    parser.add_argument("--scratch-dir", type=Path, default=ROOT / "runs/length_sweep_scratch")
    parser.add_argument("--workers", type=int)
    parser.add_argument("--limit", type=int, help="run at most N new candidates; resume later")
    args = parser.parse_args()
    result = sweep(args.spec, args.scene, args.storage_task, args.output_dir,
                   args.scratch_dir, args.workers, args.limit)
    print(json.dumps({"candidate_count": result["manifest"]["candidate_count"],
                      "complete_candidate_count": len(result["complete"]),
                      "error_count": len(result["errors"]),
                      "output_dir": str(args.output_dir)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
