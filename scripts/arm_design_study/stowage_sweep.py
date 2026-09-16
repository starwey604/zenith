"""Three-process, resume-safe minimum-stowage sweep over completed length studies."""
from __future__ import annotations

import argparse
import csv
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import time

from .length_sweep import _available_memory_gib, _canonical_hash, _sha256, _worker_init
from .length_sweep_v2_plots import robust_fraction


ROOT = Path(__file__).resolve().parent


def validate_spec(spec: dict) -> None:
    if spec.get("schema_version") != 1 or spec.get("source_type") != "design_assumption":
        raise ValueError("stowage sweep needs schema 1 design assumptions")
    studies = spec.get("studies")
    if not isinstance(studies, list) or not studies or len({s.get("study_id") for s in studies}) != len(studies):
        raise ValueError("studies need unique IDs")
    limit = spec.get("rule_limit_m")
    if not isinstance(limit, list) or len(limit) != 3 or any(x <= 0 for x in limit):
        raise ValueError("rule limit must be a positive three-vector")
    search = spec.get("search", {})
    count = search.get("sobol_sample_count")
    if (not isinstance(count, int) or isinstance(count, bool) or count < 2 or count & (count - 1)
            or not isinstance(search.get("local_start_count"), int)
            or not 1 <= search["local_start_count"] <= 32
            or not isinstance(search.get("local_max_iterations"), int)
            or search["local_max_iterations"] < 1 or not isinstance(search.get("seed"), int)):
        raise ValueError("invalid deterministic search settings")
    if not 1 <= spec.get("max_workers", 0) <= 3:
        raise ValueError("stowage sweep is capped at three workers")


def _resolved(config_path: Path, value: str) -> Path:
    return (config_path.parent / value).resolve()


def _task_best(rows: list[dict]) -> dict:
    best = max(rows, key=lambda row: (robust_fraction(row), row["storage_balanced_fraction"],
                                      row["pickup_complete"], row["module_stress_complete"]))
    return {key: best[key] for key in ("candidate_id", "parking_id", "tier1_complete",
            "tier2_complete", "tier3_complete", "storage_balanced_fraction",
            "pickup_complete", "pickup_min_slot_complete", "module_complete",
            "module_stress_complete", "module_stress_total")}


def collect_candidates(config_path: Path, spec: dict) -> tuple[list[dict], dict[str, dict], dict]:
    """Deduplicate the four parking rows; stowing is independent of field parking."""
    candidates, scenes, inputs = [], {}, {}
    for study in spec["studies"]:
        summary_path = _resolved(config_path, study["summary_file"])
        scene_path = _resolved(config_path, study["scene_file"])
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        scene = json.loads(scene_path.read_text(encoding="utf-8"))
        if summary["complete_candidate_count"] != summary["candidate_count"] or summary["errors"]:
            raise ValueError(f"incomplete source study: {summary_path}")
        study_id = study["study_id"]
        scenes[study_id] = scene
        inputs[study_id] = {"summary": str(summary_path), "summary_sha256": _sha256(summary_path),
                            "scene": str(scene_path), "scene_sha256": _sha256(scene_path)}
        groups: dict[tuple[str, int], list[dict]] = {}
        for row in summary["rows"]:
            groups.setdefault((row["robot"], int(row["sample_index"])), []).append(row)
        for (robot, sample_index), rows in sorted(groups.items()):
            first = rows[0]
            invariant = (first["anchor_span_scales"], first["span_m"], first["active_span_indices"])
            if any((r["anchor_span_scales"], r["span_m"], r["active_span_indices"]) != invariant for r in rows):
                raise ValueError("parking rows disagree on geometry")
            candidates.append({"candidate_id": f"{robot}_q{sample_index:02d}", "study_id": study_id,
                               "robot": robot, "sample_index": sample_index,
                               "sampling_kind": first.get("sampling_kind"),
                               "active_span_indices": first["active_span_indices"],
                               "anchor_span_scales": first["anchor_span_scales"],
                               "span_m": first["span_m"], "task_best": _task_best(rows)})
    if len({c["candidate_id"] for c in candidates}) != len(candidates):
        raise ValueError("stowage candidate IDs collide")
    return candidates, scenes, inputs


def manifest(config_path: Path) -> tuple[dict, list[dict], dict[str, dict]]:
    from .model_import import model_reference_paths

    spec = json.loads(config_path.read_text(encoding="utf-8"))
    validate_spec(spec)
    candidates, scenes, source_inputs = collect_candidates(config_path, spec)
    source_files = tuple(sorted(ROOT.glob("*.py")))
    rule_reference = _resolved(config_path, spec["rule_reference_file"])
    models = model_reference_paths(sorted({candidate["robot"] for candidate in candidates}))
    inputs = {"config_sha256": _sha256(config_path), "source_studies": source_inputs,
              "rule_reference": str(rule_reference), "rule_reference_sha256": _sha256(rule_reference),
              "source_sha256": {p.name: _sha256(p) for p in source_files},
              "model_sha256": {str(path): _sha256(path) for path in models}}
    value = {"schema_version": 1, "run_id": spec["run_id"], "input_key": _canonical_hash(inputs),
             "inputs": inputs, "spec": spec, "candidate_count": len(candidates),
             "candidate_ids": [c["candidate_id"] for c in candidates]}
    return value, candidates, scenes


def _artifact_path(output_dir: Path, candidate_id: str) -> Path:
    return output_dir / "candidates" / f"{candidate_id}.json"


def _run(candidate: dict, scene: dict, manifest_value: dict, output_dir: Path) -> dict:
    from .stowage import search_minimum_stowage
    start = time.monotonic()
    row = search_minimum_stowage(candidate, scene, manifest_value["spec"]["rule_limit_m"],
                                 float(manifest_value["spec"]["minimum_clearance_m"]),
                                 manifest_value["spec"]["search"])
    row["elapsed_s"] = time.monotonic() - start
    artifact = {"schema_version": 1, "input_key": manifest_value["input_key"],
                "candidate": candidate, "result": row}
    path = _artifact_path(output_dir, candidate["candidate_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    temp.write_text(json.dumps(artifact, ensure_ascii=False, separators=(",", ":"),
                               allow_nan=False), encoding="utf-8")
    os.replace(temp, path)
    return row


def _read_completed(output_dir: Path, manifest_value: dict,
                    candidates: list[dict]) -> dict[str, dict]:
    complete = {}
    for candidate in candidates:
        path = _artifact_path(output_dir, candidate["candidate_id"])
        if not path.exists():
            continue
        artifact = json.loads(path.read_text(encoding="utf-8"))
        if (artifact.get("schema_version") != 1 or artifact.get("input_key") != manifest_value["input_key"]
                or artifact.get("candidate") != candidate):
            raise ValueError(f"stale stowage checkpoint: {path}")
        complete[candidate["candidate_id"]] = artifact["result"]
    return complete


def _write(output_dir: Path, manifest_value: dict, complete: dict[str, dict], errors: dict) -> None:
    ordered = [complete[cid] for cid in manifest_value["candidate_ids"] if cid in complete]
    report = {key: manifest_value[key] for key in ("schema_version", "run_id", "input_key", "inputs",
                                                    "spec", "candidate_count")}
    report.update({"complete_candidate_count": len(ordered), "errors": errors, "rows": ordered})
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                                        allow_nan=False) + "\n", encoding="utf-8")
    fields = ("candidate_id", "robot", "sample_index", "span2_mm", "span3_mm", "span4_mm",
              "span5_mm", "size_x_mm", "size_y_mm", "size_z_mm", "worst_axis_ratio",
              "arm_size_x_mm", "arm_size_y_mm", "arm_size_z_mm", "volume_l", "clearance_mm",
              "collision_free", "rule_pass", "evaluations", "elapsed_s")
    with (output_dir / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        for row in ordered:
            flat = {"candidate_id": row["candidate_id"], "robot": row["robot"],
                    "sample_index": row["sample_index"], "worst_axis_ratio": row["worst_axis_ratio"],
                    "volume_l": row["envelope_volume_m3"] * 1000,
                    "clearance_mm": None if row["clearance_m"] is None else row["clearance_m"] * 1000,
                    "collision_free": row["collision_free"], "rule_pass": row["rule_pass"],
                    "evaluations": row["evaluations"], "elapsed_s": row["elapsed_s"]}
            flat.update({f"span{i}_mm": row["span_m"][str(i)] * 1000 for i in range(2, 6)})
            flat.update({f"size_{axis}_mm": row["dimensions_m"][i] * 1000
                         for i, axis in enumerate("xyz")})
            flat.update({f"arm_size_{axis}_mm": row["arm_only_dimensions_m"][i] * 1000
                         for i, axis in enumerate("xyz")})
            writer.writerow(flat)


def sweep(config_path: Path, output_dir: Path, workers: int | None = None,
          limit: int | None = None) -> dict:
    manifest_value, candidates, scenes = manifest(config_path)
    manifest_path = output_dir / "manifest.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    if manifest_path.exists() and json.loads(manifest_path.read_text(encoding="utf-8")) != manifest_value:
        raise ValueError("output directory belongs to different inputs")
    manifest_path.write_text(json.dumps(manifest_value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    complete = _read_completed(output_dir, manifest_value, candidates)
    pending = [c for c in candidates if c["candidate_id"] not in complete]
    if limit is not None:
        pending = pending[:limit]
    worker_count = manifest_value["spec"]["max_workers"] if workers is None else workers
    if not 1 <= worker_count <= manifest_value["spec"]["max_workers"]:
        raise ValueError("workers exceeds memory-safe cap")
    reserve = float(manifest_value["spec"].get("reserve_available_memory_gib", 2.0))
    errors = {}
    print(json.dumps({"candidate_count": len(candidates), "completed_before_run": len(complete),
                      "pending_this_run": len(pending), "workers": worker_count}, ensure_ascii=False), flush=True)
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=worker_count, mp_context=context,
                             initializer=_worker_init, max_tasks_per_child=16) as executor:
        active, cursor = {}, 0
        while cursor < len(pending) or active:
            while cursor < len(pending) and len(active) < worker_count and _available_memory_gib() >= reserve:
                candidate = pending[cursor]
                cursor += 1
                future = executor.submit(_run, candidate, scenes[candidate["study_id"]],
                                         manifest_value, output_dir)
                active[future] = candidate["candidate_id"]
            if not active:
                time.sleep(5)
                continue
            done, _ = wait(active, return_when=FIRST_COMPLETED, timeout=30)
            for future in done:
                cid = active.pop(future)
                try:
                    row = future.result()
                except Exception as error:
                    errors[cid] = f"{type(error).__name__}: {error}"
                    print(json.dumps({"candidate_id": cid, "error": errors[cid]}), flush=True)
                else:
                    complete[cid] = row
                    print(json.dumps({"candidate_id": cid, "completed": len(complete),
                                      "total": len(candidates), "size_mm": [round(x * 1000, 1)
                                      for x in row["dimensions_m"]], "rule_pass": row["rule_pass"],
                                      "elapsed_s": round(row["elapsed_s"], 1)}, ensure_ascii=False), flush=True)
                _write(output_dir, manifest_value, complete, errors)
    _write(output_dir, manifest_value, complete, errors)
    return {"manifest": manifest_value, "complete": complete, "errors": errors}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/stowage_sweep.v1.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "runs/stowage_sweep_v1")
    parser.add_argument("--workers", type=int)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    result = sweep(args.config, args.output_dir, args.workers, args.limit)
    print(json.dumps({"candidate_count": result["manifest"]["candidate_count"],
                      "complete_candidate_count": len(result["complete"]),
                      "error_count": len(result["errors"]), "output_dir": str(args.output_dir)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
