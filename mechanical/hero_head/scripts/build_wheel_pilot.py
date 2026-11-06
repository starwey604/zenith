"""Native Sketcher + PartDesign redraw of one measured STEP wheel annulus.

Pilot only: validates the CAD workflow, not rubber material or firing performance.
Run in FreeCAD GUI after extract_launcher.py.
"""
import json
import math
from pathlib import Path

import FreeCAD as App
import Part
import Sketcher

ROOT = Path(__file__).resolve().parents[1]
source = next((d for d in App.listDocuments().values() if d.getObject("Ref_1205")), None)
if source is None:
    source = App.openDocument(str(ROOT / "cad/launcher_reference.FCStd"))
reference = source.getObject("Ref_1205").Shape.copy()
reference.translate(-reference.CenterOfMass)

doc = App.newDocument("WheelRingParametric")
sheet = doc.addObject("Spreadsheet::Sheet", "Parameters")
sheet.set("A1", "Parameter")
sheet.set("B1", "Value")
sheet.set("C1", "Source")
for row, (alias, value) in enumerate([
    ("WheelDiameter", "60 mm"), ("WheelBore", "46.002 mm"), ("WheelThickness", "18 mm")
], 2):
    sheet.set("A" + str(row), alias)
    sheet.set("B" + str(row), value)
    sheet.setAlias("B" + str(row), alias)
    sheet.set("C" + str(row), "STEP Ref_1205; geometry only, tolerance unknown")
body = doc.addObject("PartDesign::Body", "WheelRing")
sketch = doc.addObject("Sketcher::SketchObject", "RingSketch")
body.addObject(sketch)
for i, radius in enumerate((30, 23.001)):
    sketch.addGeometry(Part.Circle(App.Vector(0, 0, 0), App.Vector(0, 0, 1), radius), False)
    sketch.addConstraint(Sketcher.Constraint("Coincident", i, 3, -1, 1))
    constraint = sketch.addConstraint(Sketcher.Constraint("Radius", i, radius))
    name = "OuterRadius" if i == 0 else "InnerRadius"
    sketch.renameConstraint(constraint, name)
    sketch.setExpression("Constraints." + name, "Parameters." + ("WheelDiameter" if i == 0 else "WheelBore") + " / 2")
sketch.setExpression("Placement.Base.z", "-Parameters.WheelThickness / 2")
pad = body.newObject("PartDesign::Pad", "RingPad")
pad.Profile = sketch
pad.setExpression("Length", "Parameters.WheelThickness")
doc.recompute()

baseline_volume = pad.Shape.Volume
difference = pad.Shape.cut(reference).Volume + reference.cut(pad.Shape).Volume
sheet.set("B2", "62 mm")
doc.recompute()
changed_volume = pad.Shape.Volume
expected_changed_volume = math.pi * (31**2 - 23.001**2) * 18
sheet.set("B2", "60 mm")
doc.recompute()
result = {
    "source": "launcher_reference.FCStd / Ref_1205 (STEP Part__Feature1205)",
    "diameter_mm": 60, "bore_mm": 46.002, "thickness_mm": 18,
    "sketch_fully_constrained": sketch.FullyConstrained,
    "shape_valid": pad.Shape.isValid(),
    "solid_count": len(pad.Shape.Solids),
    "reference_volume_mm3": reference.Volume,
    "redraw_volume_mm3": baseline_volume,
    "symmetric_difference_volume_mm3": difference,
    "diameter_62_recompute_volume_mm3": changed_volume,
    "diameter_62_expected_volume_mm3": expected_changed_volume,
    "restored_volume_mm3": pad.Shape.Volume,
    "limitations": "Single simple annulus; complex gate/support parts and assembly joints not tested. Dimensions reproduce the supplied STEP, not manufacturing tolerances.",
}
assert result["sketch_fully_constrained"] and result["shape_valid"]
assert result["solid_count"] == 1 and difference < 1e-5
assert abs(changed_volume - expected_changed_volume) < 1e-5
assert abs(pad.Shape.Volume - baseline_volume) < 1e-5
(ROOT / "reports/parametric_pilot.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
if App.GuiUp:
    import FreeCADGui as Gui
    sketch.ViewObject.Visibility = False
    pad.ViewObject.ShapeColor = (0.25, 0.55, 0.85)
    Gui.activeDocument().activeView().viewAxonometric()
    Gui.activeDocument().activeView().fitAll()
doc.recompute()
doc.saveAs(str(ROOT / "cad/wheel_ring_parametric.FCStd"))
print(json.dumps(result, ensure_ascii=False))
