"""Verify, publish and plot a completed minimum-stowage run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

from .stowage_plots import render


def publish(work_dir: Path, result_dir: Path) -> dict:
    manifest = json.loads((work_dir / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((work_dir / "summary.json").read_text(encoding="utf-8"))
    ids = manifest["candidate_ids"]
    if (summary["input_key"] != manifest["input_key"] or summary["errors"]
            or summary["complete_candidate_count"] != len(ids)
            or {row["candidate_id"] for row in summary["rows"]} != set(ids)):
        raise ValueError("cannot publish an incomplete or inconsistent stowage sweep")
    result_dir.mkdir(parents=True, exist_ok=True)
    target_candidates = result_dir / "candidates"
    target_candidates.mkdir(exist_ok=True)
    for candidate_id in ids:
        source = work_dir / "candidates" / f"{candidate_id}.json"
        artifact = json.loads(source.read_text(encoding="utf-8"))
        if (artifact.get("schema_version") != 1 or artifact.get("input_key") != manifest["input_key"]
                or artifact.get("candidate", {}).get("candidate_id") != candidate_id
                or artifact.get("result", {}).get("candidate_id") != candidate_id):
            raise ValueError(f"invalid candidate artifact: {source}")
        shutil.copy2(source, target_candidates / source.name)
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
