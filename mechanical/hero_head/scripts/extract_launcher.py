"""Extract a review subset in a reproducible launcher coordinate frame.

Run in the FreeCAD GUI Python console using exec(compile(...), {'__file__': path}).
This preserves STEP solids. It does not reconstruct sketches or mating constraints.
"""
import json
from pathlib import Path

import FreeCAD as App
import Part

ROOT = Path(__file__).resolve().parents[1]
source = next((d for d in App.listDocuments().values()
               if d.getObject("Part__Feature1507") and d.getObject("HERO")), None)
if source is None:
    source = App.openDocument(str(ROOT / "cad/reference_full.FCStd"))


def world_shape(obj):
    shape = obj.Shape.copy()
    shape.Placement = obj.getGlobalPlacement()
    return shape


wheels = [world_shape(source.getObject("Part__Feature" + str(i))) for i in (1205, 1207)]
cylinder = next(f.Surface for f in wheels[0].Faces
                if isinstance(f.Surface, Part.Cylinder) and abs(f.Surface.Radius - 30) < 1e-6)
up = App.Vector(cylinder.Axis)
if up.y < 0:
    up = -up
left = wheels[1].CenterOfMass - wheels[0].CenterOfMass
spacing = left.Length
left.normalize()
forward = left.cross(up)
forward.normalize()
origin = (wheels[0].CenterOfMass + wheels[1].CenterOfMass) * 0.5
rotation = App.Rotation(forward, left, up, "XYZ").inverted()
transform = App.Placement(rotation.multVec(-origin), rotation)

study = App.newDocument("HeroLauncherReference")
group = study.addObject("App::Part", "LauncherReference")
group.Label = "交龙原版发射核心参考（非参数化重绘）"
rows = []
# Includes wheels, motors, gate pieces and old referee speed module.
# Excludes the original pitch brackets and their two riser plates.
indices = [i for i in range(1179, 1245) if i not in (1182, 1183, 1198, 1199)] + [1265]
for i in indices:
    original = source.getObject("Part__Feature" + str(i))
    shape = world_shape(original)
    shape.Placement = transform.multiply(shape.Placement)
    obj = study.addObject("Part::Feature", "Ref_" + str(i))
    obj.Label = original.Label
    obj.Shape = shape
    obj.addProperty("App::PropertyString", "SourceObject", "Provenance")
    obj.SourceObject = original.Name
    group.addObject(obj)
    b = shape.BoundBox
    rows.append({"source_object": original.Name, "label": original.Label,
                 "bbox_mm": [b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax],
                 "valid": shape.isValid(), "solids": len(shape.Solids)})
    if App.GuiUp:
        obj.ViewObject.ShapeColor = ((0.18, 0.21, 0.25) if i in (1205, 1207)
                                     else (0.25, 0.55, 0.85) if i <= 1196 or i == 1265
                                     else (0.78, 0.80, 0.84))
        obj.ViewObject.LineColor = (0.12, 0.14, 0.17)
        obj.ViewObject.DisplayMode = "Flat Lines"
        obj.ViewObject.Visibility = True

study.recompute()
b = group.Shape.BoundBox
report = {
    "status": "reference subset only; fasteners, original linkage and supports not exhaustively included",
    "coordinate_frame": "X forward toward muzzle; Y along left-to-right STEP wheel-centre vector; Z wheel axis toward original +Y; origin midpoint of wheel solid centroids",
    "source_to_reference_matrix": list(transform.toMatrix().A),
    "wheel_diameter_mm": cylinder.Radius * 2,
    "wheel_axis_spacing_mm": spacing,
    "nominal_unloaded_gap_mm": spacing - cylinder.Radius * 2,
    "bbox_size_mm": [b.XLength, b.YLength, b.ZLength],
    "all_selected_shapes_valid": all(r["valid"] for r in rows),
    "parts": rows,
}
(ROOT / "reports/launcher_reference.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
if App.GuiUp:
    import FreeCADGui as Gui
    group.ViewObject.Visibility = True
    Gui.activeDocument().activeView().viewAxonometric()
    Gui.activeDocument().activeView().fitAll()
    Gui.updateGui()
study.saveAs(str(ROOT / "cad/launcher_reference.FCStd"))
print(json.dumps({k: v for k, v in report.items() if k != "parts"}, ensure_ascii=False))
