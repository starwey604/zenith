import json
from pathlib import Path
import tarfile

from scripts.arm_design_study.publish_length_sweep_v2 import publish


def test_complete_run_can_publish_verified_candidate_archive(tmp_path):
    work = tmp_path / "work"
    (work / "candidates").mkdir(parents=True)
    ids = ["robot_q00_rear_left"]
    manifest = {"schema_version": 2, "input_key": "same-input", "candidate_ids": ids,
                "inputs": {"base_scene_sha256": "scene", "storage_task_sha256": "storage",
                           "module_stress_sha256": "module"}}
    row = {"candidate_id": ids[0], "robot": "robot", "parking_id": "rear_left",
           "span_m": {str(index): 0.2 for index in range(2, 6)},
           "tier1_complete": 1, "tier2_complete": 1, "tier3_complete": 1,
           "storage_balanced_fraction": 0.1, "pickup_complete": 4,
           "module_complete": True, "module_stress_complete": 2,
           "module_stress_total": 9, "module_stress_min_clearance_m": 0.01,
           "module_stress_min_joint_margin_rad": 0.1}
    summary = {"schema_version": 2, "input_key": "same-input", "rows": [row],
               "spec": {"robots": ["robot"]}, "candidate_count": 1,
               "complete_candidate_count": 1, "errors": {}}
    reports = {name: {"scene_sha256": "derived", "rows": [{}] * count}
               for name, count in (("storage", 67), ("pickup_exit", 72),
                                   ("benchmark", 8), ("module_stress", 9))}
    artifact = {"schema_version": 2, "input_key": "same-input",
                "candidate": {"candidate_id": ids[0]},
                "base_scene_sha256": "scene", "storage_task_sha256": "storage",
                "module_stress_sha256": "module", "derived_scene_sha256": "derived",
                "reports": reports}
    for path, data in ((work / "manifest.json", manifest),
                       (work / "summary.json", summary),
                       (work / "candidates" / f"{ids[0]}.json", artifact)):
        path.write_text(json.dumps(data), encoding="utf-8")
    (work / "summary.csv").write_text("candidate_id\n", encoding="utf-8")

    result = publish(work, tmp_path / "published", archive_candidates=True)
    archive = Path(result["candidate_archive"])
    with tarfile.open(archive, "r:gz") as handle:
        assert handle.getnames() == [f"candidates/{ids[0]}.json"]
        assert json.load(handle.extractfile(handle.getmembers()[0])) == artifact
    assert not (tmp_path / "published" / "candidates").exists()
    assert all(Path(path).is_file() for path in result["plots"])
