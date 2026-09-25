"""Verify, publish and plot a completed minimum-stowage run."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import tarfile

from .length_sweep import _sha256
from .stowage_plots import render


def publish(work_dir: Path, result_dir: Path, archive_candidates: bool = False) -> dict:
    manifest = json.loads((work_dir / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((work_dir / "summary.json").read_text(encoding="utf-8"))
    ids = manifest["candidate_ids"]
    if (summary["input_key"] != manifest["input_key"] or summary["errors"]
            or summary["complete_candidate_count"] != len(ids)
            or {row["candidate_id"] for row in summary["rows"]} != set(ids)):
        raise ValueError("cannot publish an incomplete or inconsistent stowage sweep")
    result_dir.mkdir(parents=True, exist_ok=True)
    sources = []
    for candidate_id in ids:
        source = work_dir / "candidates" / f"{candidate_id}.json"
        artifact = json.loads(source.read_text(encoding="utf-8"))
        if (artifact.get("schema_version") != 1 or artifact.get("input_key") != manifest["input_key"]
                or artifact.get("candidate", {}).get("candidate_id") != candidate_id
                or artifact.get("result", {}).get("candidate_id") != candidate_id):
            raise ValueError(f"invalid candidate artifact: {source}")
        sources.append(source)
    archive = None
    if archive_candidates:
        archive = result_dir / "candidates.tar.gz"
        temporary = result_dir / "candidates.tar.gz.tmp"
        with tarfile.open(temporary, "w:gz", compresslevel=6) as handle:
            for source in sources:
                handle.add(source, arcname=f"candidates/{source.name}", recursive=False)
        os.replace(temporary, archive)
    else:
        target_candidates = result_dir / "candidates"
        target_candidates.mkdir(exist_ok=True)
        for source in sources:
            shutil.copy2(source, target_candidates / source.name)
    for name in ("manifest.json", "summary.json", "summary.csv"):
        shutil.copy2(work_dir / name, result_dir / name)
    config = work_dir / "inputs" / "config.json"
    if config.exists():
        if _sha256(config) != manifest["inputs"]["config_sha256"]:
            raise ValueError(f"prepared input changed: {config}")
        shutil.copy2(config, result_dir / "config.json")
    rendered = render(result_dir / "summary.json", result_dir / "plots")
    return {"candidate_count": len(ids), "result_dir": str(result_dir),
            "candidate_archive": str(archive) if archive is not None else None,
            **rendered}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--archive-candidates", action="store_true")
    args = parser.parse_args()
    print(json.dumps(publish(args.work_dir, args.result_dir,
                             args.archive_candidates), ensure_ascii=False))


if __name__ == "__main__":
    main()
