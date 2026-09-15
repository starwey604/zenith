"""Verify a completed raw sweep, then copy reports and plots for Git LFS."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

from .length_sweep import _artifact_path
from .length_sweep_plots import render


def publish(work_dir: Path, result_dir: Path) -> dict:
    manifest = json.loads((work_dir / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((work_dir / "summary.json").read_text(encoding="utf-8"))
    if (summary["input_key"] != manifest["input_key"]
            or summary["complete_candidate_count"] != manifest["candidate_count"]
            or summary["errors"]):
        raise ValueError("cannot publish an incomplete or failed sweep")
    ids = set(manifest["candidate_ids"])
    if {row["candidate_id"] for row in summary["rows"]} != ids:
        raise ValueError("summary candidate IDs disagree with manifest")
    source_files = [_artifact_path(work_dir, candidate_id)
                    for candidate_id in manifest["candidate_ids"]]
    for source in source_files:
        with source.open("r", encoding="utf-8") as handle:
            artifact = json.load(handle)
        candidate_id = artifact["candidate"]["candidate_id"]
        if (artifact["input_key"] != manifest["input_key"]
                or artifact["base_scene_sha256"] != manifest["inputs"]["base_scene_sha256"]
                or artifact["storage_task_sha256"] != manifest["inputs"]["storage_task_sha256"]
                or source.stem != candidate_id
                or [len(artifact["reports"][name]["rows"])
                    for name in ("storage", "pickup_exit", "benchmark")] != [67, 72, 8]):
            raise ValueError(f"candidate artifact failed integrity check: {source}")
    result_dir.mkdir(parents=True, exist_ok=True)
    target_candidates = result_dir / "candidates"
    target_candidates.mkdir(exist_ok=True)
    for source in source_files:
        shutil.copy2(source, target_candidates / source.name)
    for name in ("manifest.json", "summary.json", "summary.csv"):
        shutil.copy2(work_dir / name, result_dir / name)
    plots = render(result_dir / "summary.json", result_dir / "plots")
    return {"candidate_count": manifest["candidate_count"],
            "raw_candidate_reports": len(source_files),
            "plots": [str(path) for path in plots], "result_dir": str(result_dir)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--result-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.work_dir, args.result_dir), ensure_ascii=False))


if __name__ == "__main__":
    main()
