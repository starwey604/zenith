"""Export assembled CAD geometry into embedded browser data; no source edits."""
import hashlib
import json
from pathlib import Path
import FreeCAD as App

ROOT = Path(__file__).resolve().parents[1]


def open_source(path):
    return next((d for d in App.listDocuments().values() if d.FileName == str(path)), None) or App.openDocument(str(path))


def mesh_object(obj):
    verts, facets = obj.Shape.tessellate(0.65)
    return {"name": obj.Name, "label": obj.Label,
            "vertices": [round(c, 3) for v in verts for c in v],
            "triangles": [i for f in facets for i in f]}


launcher_path = ROOT / "cad/launcher_reference.FCStd"
case_path = ROOT.parent / "lbc3_case_v1/lbc3_case_v1.FCStd"
launcher = open_source(launcher_path)
case = open_source(case_path)
result = {
    "launcher": [mesh_object(o) for o in launcher.Objects if o.Name.startswith("Ref_") and (int(o.Name[4:]) >= 1197 or o.Name == "Ref_1187") and o.Name != "Ref_1265"],
    "case": [mesh_object(case.getObject(n)) for n in ("CASE_base", "CASE_lid", "REF_lbc3_board", "REF_top_plate")],
    "sources": {str(p.relative_to(ROOT.parent)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (launcher_path, case_path)},
    "case_bounds_mm": [-7, -7, -12.5, 91.5, 74, 21.5],
    "units": "mm",
}
out = ROOT / "magazine_study/assets/reference_meshes.json"
out.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
print('Exported', out, out.stat().st_size, 'bytes', sum(len(o['triangles'])//3 for o in result['launcher']), 'launcher triangles')
