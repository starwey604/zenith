"""Verify all v2 candidate reports before publishing copies and plots."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

from .length_sweep_v2 import artifact_path
from .length_sweep_v2_plots import render


def publish(work_dir: Path, result_dir: Path) -> dict:
    manifest = json.loads((work_dir / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((work_dir / "summary.json").read_text(encoding="utf-8"))
    ids = manifest["candidate_ids"]
    if (summary["schema_version"] != 2 or summary["input_key"] != manifest["input_key"]
            or summary["complete_candidate_count"] != len(ids) or summary["errors"]
            or {row["candidate_id"] for row in summary["rows"]} != set(ids)):
        raise ValueError("cannot publish an incomplete or inconsistent v2 sweep")
    sources = [artifact_path(work_dir, cid) for cid in ids]
    for source in sources:
        artifact = json.loads(source.read_text(encoding="utf-8"))
        reports = artifact["reports"]
        if (artifact["schema_version"] != 2 or artifact["input_key"] != manifest["input_key"]
                or artifact["candidate"]["candidate_id"] != source.stem
                or artifact["base_scene_sha256"] != manifest["inputs"]["base_scene_sha256"]
                or artifact["storage_task_sha256"] != manifest["inputs"]["storage_task_sha256"]
                or artifact["module_stress_sha256"] != manifest["inputs"]["module_stress_sha256"]
                or [len(reports[name]["rows"]) for name in
                    ("storage", "pickup_exit", "benchmark", "module_stress")] != [67, 72, 8, 9]
                or any(reports[name]["scene_sha256"] != artifact["derived_scene_sha256"]
                       for name in reports)):
            raise ValueError(f"candidate artifact failed integrity check: {source}")
    result_dir.mkdir(parents=True, exist_ok=True)
    candidates_dir = result_dir / "candidates"
    candidates_dir.mkdir(exist_ok=True)
    for source in sources:
        shutil.copy2(source, candidates_dir / source.name)
    for name in ("manifest.json", "summary.json", "summary.csv"):
        shutil.copy2(work_dir / name, result_dir / name)
    rendered = render(result_dir / "summary.json", result_dir / "plots")
    return {"candidate_count": len(ids), "result_dir": str(result_dir), **rendered}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--result-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.work_dir, args.result_dir), ensure_ascii=False))


if __name__ == "__main__":
    main()
