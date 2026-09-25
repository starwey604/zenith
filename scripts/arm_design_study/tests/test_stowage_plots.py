import json
from pathlib import Path

from scripts.arm_design_study.stowage_plots import render


def test_large_stowage_catalog_uses_readable_distributions(tmp_path):
    rows = []
    for index in range(13):
        robot = f"orth6r_{index:012x}"
        rows.append({"candidate_id": f"{robot}_q00", "robot": robot,
                     "sample_index": 0, "span_m": {str(j): 0.2 for j in range(2, 6)},
                     "dimensions_m": [0.4, 0.45, 0.5],
                     "arm_only_dimensions_m": [0.3, 0.35, 0.4],
                     "worst_axis_ratio": 0.5 / 0.6,
                     "envelope_volume_m3": 0.09, "clearance_m": 0.01,
                     "collision_free": True, "rule_pass": True,
                     "task_best": None})
    summary = tmp_path / "summary.json"
    summary.write_text(json.dumps({"rows": rows, "candidate_count": len(rows),
                                   "complete_candidate_count": len(rows),
                                   "errors": {}}), encoding="utf-8")
    report = render(summary, tmp_path / "plots")
    assert report["rule_pass_count"] == 13
    assert len(report["plots"]) == 2
    assert all(Path(path).stat().st_size > 0 for path in report["plots"])
