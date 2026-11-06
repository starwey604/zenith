"""Run with FreeCADCmd; import reference geometry, preserving assembly structure.

Requires inspect_source.py first. This is reference geometry, not a parametric redraw.
"""
import json
import time
from pathlib import Path

import FreeCAD as App
import Import

ROOT = Path(__file__).resolve().parents[1]
started = time.monotonic()
doc = App.newDocument("HeroReference")
Import.insert("/tmp/zenith-hero-utf8.step", doc.Name)
doc.recompute()
rows = []
for obj in doc.Objects:
    row = {"name": obj.Name, "label": obj.Label, "type": obj.TypeId,
           "parents": [p.Name for p in obj.InList],
           "children": [p.Name for p in getattr(obj, "Group", [])]}
    if hasattr(obj, "Shape") and not obj.Shape.isNull():
        shape = obj.Shape.copy()
        shape.Placement = obj.getGlobalPlacement()
        b = shape.BoundBox
        row.update(bbox_mm=[b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax],
                   volume_mm3=shape.Volume, solids=len(shape.Solids), faces=len(shape.Faces))
    rows.append(row)
(ROOT / "cad").mkdir(exist_ok=True)
doc.saveAs(str(ROOT / "cad/reference_full.FCStd"))
result = {"freecad_version": App.Version(), "elapsed_s": time.monotonic() - started,
          "note": "Assembly parent shapes aggregate descendants; do not sum parent and child volumes.",
          "objects": rows}
(ROOT / "reports/reference_inventory.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print("HERO_IMPORT_COMPLETE", len(rows), "objects", result["elapsed_s"], "seconds", flush=True)
