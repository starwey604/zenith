"""Validate and publish finalist graph-IK reports beside greedy sweep reports."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import tarfile


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _comparison(greedy: list[dict], graph: list[dict], key: str) -> dict:
    old = {row[key]: row for row in greedy}
    new = {row[key]: row for row in graph}
    if old.keys() != new.keys():
        raise ValueError(f"graph and greedy {key} sets differ")
    return {"greedy_complete": sum(row["geometric_complete"] for row in greedy),
            "graph_complete": sum(row["geometric_complete"] for row in graph),
            "case_count": len(new),
            "cases": [{"id": case_id,
                       "greedy_complete": old[case_id]["geometric_complete"],
                       "graph_complete": new[case_id]["geometric_complete"],
                       "greedy_failure": old[case_id]["failure"],
                       "graph_failure": new[case_id]["failure"],
                       "graph_nodes": new[case_id].get("ik_graph", {}).get("node_count"),
                       "graph_edges": new[case_id].get("ik_graph", {}).get("edge_count")}
                      for case_id in old]}


def publish(run_dirs: list[Path], sweep_scene_path: Path, candidate_archive: Path,
            stress_path: Path, result_dir: Path) -> dict:
    if not run_dirs or len(set(run_dirs)) != len(run_dirs):
        raise ValueError("supply distinct graph run directories")
    base = json.loads(sweep_scene_path.read_text(encoding="utf-8"))
    manifest = {"schema_version": 1, "source_type": "design_assumption",
                "sweep_scene_sha256": _sha256(sweep_scene_path),
                "candidate_archive_sha256": _sha256(candidate_archive),
                "module_stress_sha256": _sha256(stress_path), "inputs": []}
    summaries = []
    files = []
    with tarfile.open(candidate_archive, "r:gz") as old_archive:
        for run_dir in run_dirs:
            scene_path = run_dir / "scene.json"
            benchmark_path = run_dir / "benchmark.json"
            module_path = run_dir / "module_stress.json"
            scene = json.loads(scene_path.read_text(encoding="utf-8"))
            if (scene.get("ik_solver", {}).get("mode") != "graph"
                    or len(scene["robots"]) != len(scene["length_variants"]) != len(scene["parking"]["candidates"]) != 1):
                raise ValueError(f"not a single graph candidate scene: {scene_path}")
            cid = scene["length_variants"][0]["variant_id"]
            with old_archive.extractfile(f"candidates/{cid}.json") as handle:
                old = json.load(handle)
            old_candidate = old["candidate"]
            if (scene["robots"][0] != old_candidate["robot"]
                    or scene["length_variants"][0]["anchor_span_scales"] != old_candidate["anchor_span_scales"]
                    or scene["parking"]["candidates"][0]["parking_id"] != old_candidate["parking_id"]):
                raise ValueError(f"candidate geometry/parking changed: {cid}")
            greedy_scene = copy.deepcopy(scene)
            greedy_scene["ik_solver"] = base["ik_solver"]
            greedy_bytes = (json.dumps(greedy_scene, ensure_ascii=False, indent=2,
                                       allow_nan=False) + "\n").encode()
            if hashlib.sha256(greedy_bytes).hexdigest() != old["derived_scene_sha256"]:
                raise ValueError(f"scene differs beyond IK solver: {cid}")
            benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
            module = json.loads(module_path.read_text(encoding="utf-8"))
            scene_hash = _sha256(scene_path)
            if (benchmark["scene_sha256"] != scene_hash or module["scene_sha256"] != scene_hash
                    or module["stress_sha256"] != manifest["module_stress_sha256"]
                    or len(benchmark["rows"]) != 8 or len(module["rows"]) != 9):
                raise ValueError(f"graph task report integrity failed: {cid}")
            summaries.append({"candidate_id": cid,
                              "benchmark": _comparison(old["reports"]["benchmark"]["rows"],
                                                       benchmark["rows"], "task_id"),
                              "module_stress": _comparison(old["reports"]["module_stress"]["rows"],
                                                           module["rows"], "case_id")})
            manifest["inputs"].append({"candidate_id": cid,
                                       "sweep_input_key": old["input_key"],
                                       "graph_scene_sha256": scene_hash,
                                       "graph_benchmark_sha256": _sha256(benchmark_path),
                                       "graph_module_stress_sha256": _sha256(module_path)})
            files.extend((cid, path) for path in (scene_path, benchmark_path, module_path))
    result_dir.mkdir(parents=True, exist_ok=True)
    archive = result_dir / "reports.tar.gz"
    temporary = result_dir / "reports.tar.gz.tmp"
    with tarfile.open(temporary, "w:gz", compresslevel=6) as handle:
        for cid, path in files:
            handle.add(path, arcname=f"{cid}/{path.name}", recursive=False)
    os.replace(temporary, archive)
    (result_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                               encoding="utf-8")
    (result_dir / "summary.json").write_text(json.dumps({"schema_version": 1,
                                                       "candidate_count": len(summaries),
                                                       "rows": summaries},
                                                      ensure_ascii=False, indent=2) + "\n",
                                              encoding="utf-8")
    return {"candidate_count": len(summaries), "archive": str(archive),
            "summary": str(result_dir / "summary.json")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, action="append", required=True)
    parser.add_argument("--sweep-scene", type=Path, required=True)
    parser.add_argument("--candidate-archive", type=Path, required=True)
    parser.add_argument("--module-stress", type=Path, required=True)
    parser.add_argument("--result-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.run_dir, args.sweep_scene,
                             args.candidate_archive, args.module_stress,
                             args.result_dir), ensure_ascii=False))


if __name__ == "__main__":
    main()
