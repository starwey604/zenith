import json
from pathlib import Path

from scripts.arm_design_study.length_sweep_v2_plots import render


def test_large_topology_catalog_renders_without_unreadable_legend(tmp_path):
    robots = [f"orth6r_{index:012x}" for index in range(13)]
    rows = []
    for index, robot in enumerate(robots):
        rows.append({"candidate_id": f"{robot}_q00_rear_left", "robot": robot,
                     "parking_id": "rear_left", "span_m": {str(j): 0.2 for j in range(2, 6)},
                     "tier1_complete": 0, "tier2_complete": 0, "tier3_complete": 0,
                     "storage_balanced_fraction": index / 13,
                     "pickup_complete": index, "module_complete": True,
                     "module_stress_complete": index % 9,
                     "module_stress_total": 9,
                     "module_stress_min_clearance_m": 0.01,
                     "module_stress_min_joint_margin_rad": 0.1})
    summary = tmp_path / "summary.json"
    summary.write_text(json.dumps({"rows": rows, "spec": {"robots": robots},
                                   "candidate_count": len(rows),
                                   "complete_candidate_count": len(rows),
                                   "errors": {}}), encoding="utf-8")
    result = render(summary, tmp_path / "plots")
    assert all(path.endswith(".png") for path in result["plots"])
    assert all(Path(path).stat().st_size > 0 for path in result["plots"])
