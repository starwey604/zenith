"""Rebuild the enclosure document and print STLs without opening FreeCAD GUI."""

from pathlib import Path
import sys

import FreeCAD as App

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from case_v1 import build_assembly, build_base, build_lid, export_print_stls


def rebuild():
    base, lid = build_base(), build_lid()
    for name, shape in (("base", base), ("lid", lid)):
        if not shape.isValid() or len(shape.Solids) != 1:
            raise RuntimeError(f"{name} is not a single valid solid")
    if base.common(lid).Volume > 1e-6:
        raise RuntimeError("base and lid overlap")

    doc = build_assembly()
    doc.saveAs(str(HERE / "lbc3_case_v1.FCStd"))
    export_print_stls(HERE)
    App.closeDocument(doc.Name)
    print("Saved", HERE / "lbc3_case_v1.FCStd")


if __name__ == "__main__":
    rebuild()
