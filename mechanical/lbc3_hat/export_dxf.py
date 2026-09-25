"""Export 2D DXF drawings for the LubanCat-3 add-on.

Outputs (into ./dxf/):
  * lbc3_top_plate.dxf : the 40-pin add-on board (top plate) outline + holes,
                         with the 40P footprint called out.
  * lbc3_board.dxf     : the LubanCat-3 board outline + mount holes, with the
                         CAM1 (B2B) footprint called out.
  * lbc3_cam1_adapter.dxf : the CAM1 adapter PCB outline and mechanical
                            connector envelopes (not copper land patterns).

Everything is drawn in the **board frame** with Z as the drawing normal:
x to the right, y away from the 40-pin edge, millimetres.

Run inside FreeCAD:  exec(open(__file__).read())
"""

import os
import FreeCAD as App
import Part
import importDXF
from FreeCAD import Vector

FONT = "/usr/share/fonts/TTF/DejaVuSans.ttf"

HERE = "/home/ww/codings/zenith/mechanical/lbc3_hat"
_ns = {}
exec(open(os.path.join(HERE, "model.py")).read(), _ns)

BOARD_L, BOARD_W, CORNER_R = _ns["BOARD_L"], _ns["BOARD_W"], _ns["CORNER_R"]
HDR_X0, HDR_PITCH, HDR_COLS = _ns["HDR_X0"], _ns["HDR_PITCH"], _ns["HDR_COLS"]
HDR_ROWS_Y, HDR_BODY_PAD = _ns["HDR_ROWS_Y"], _ns["HDR_BODY_PAD"]
CAM1_RECT = _ns["CAM1_RECT"]
ADAPTER_CX, ADAPTER_CY = _ns["ADAPTER_CX"], _ns["ADAPTER_CY"]
AXE_L, AXE_W = _ns["AXE630124D_L"], _ns["AXE630124D_W"]
FPC_CX, FPC_CY = _ns["FPC30_CX"], _ns["FPC30_CY"]
FPC_L, FPC_W = _ns["FPC30_L"], _ns["FPC30_W"]
MOUNT_HOLES, MOUNT_HOLE_D = _ns["MOUNT_HOLES"], _ns["MOUNT_HOLE_D"]
NOTCH = _ns["NOTCH"]


def feat(doc, name, shape):
    o = doc.addObject("Part::Feature", name)
    o.Shape = shape
    return o


def rect(x0, y0, x1, y1):
    return Part.Face(Part.makePolygon([Vector(x0, y0, 0), Vector(x1, y0, 0),
                                       Vector(x1, y1, 0), Vector(x0, y1, 0),
                                       Vector(x0, y0, 0)]))


def circle(x, y, d):
    return Part.Wire([Part.makeCircle(d / 2, Vector(x, y, 0), Vector(0, 0, 1))])


def text(doc, name, s, x, y, size=2.5):
    """Real text geometry (Draft ShapeString) so it survives DXF export."""
    try:
        import Draft
        ss = Draft.makeShapeString(s, FONT, size, 0)
        ss.Label = name
        ss.Placement.Base = Vector(x, y, 0)
        return ss
    except Exception:
        return None


def horizontal_face(shape, zdir=-1):
    for f in shape.Faces:
        n = f.normalAt(0, 0)
        if abs(abs(n.z) - 1) < 1e-6:
            if (n.z * zdir) > 0:
                return f
    return None


def export_top_plate():
    doc = App.newDocument("dxf_top_plate")
    plate = _ns["build_plate"]()
    plate.translate(Vector(0, 0, -_ns["GAP"]))
    feat(doc, "PLATE_OUTLINE", horizontal_face(plate, +1))
    # 40P footprint call-out: body outline + all 40 pad centres + pin1 marker.
    # Board silkscreen: pin 1 is at the RIGHT end (x max), pin 40 at the LEFT.
    x0 = HDR_X0 - HDR_BODY_PAD
    x1 = HDR_X0 + (HDR_COLS - 1) * HDR_PITCH + HDR_BODY_PAD
    y0, y1 = HDR_ROWS_Y[0] - 1.27, HDR_ROWS_Y[1] + 1.27
    feat(doc, "ANNO_40P_BODY", rect(x0, y0, x1, y1))
    for i in range(HDR_COLS):
        px = HDR_X0 + i * HDR_PITCH
        for j, py in enumerate(HDR_ROWS_Y):
            feat(doc, "ANNO_40P_PAD_%02d_%d" % (i, j), circle(px, py, 1.7))
    px1 = HDR_X0 + (HDR_COLS - 1) * HDR_PITCH
    feat(doc, "ANNO_40P_PIN1_BOX", rect(px1 - 1.6, y0, px1 + 1.6, y1))
    text(doc, "ANNO_40P_TEXT",
         "40P 2x20 2.54  pin1=RIGHT  pin40=LEFT", x0 - 1.0, y1 + 2.0, 2.5)
    doc.recompute()
    out = os.path.join(HERE, "dxf", "lbc3_top_plate.dxf")
    importDXF.export(doc.Objects, out)
    print("wrote", out)
    App.closeDocument(doc.Name)


def export_board():
    doc = App.newDocument("dxf_board")
    b = _ns["rounded_box"](BOARD_L, BOARD_W, 1.0, 0.0)
    b = b.cut(_ns["poly_prism"](NOTCH, -1, 3))
    for x, y in MOUNT_HOLES:
        b = b.cut(Part.makeCylinder(MOUNT_HOLE_D / 2, 4, Vector(x, y, -2)))
    feat(doc, "BOARD_OUTLINE", horizontal_face(b, +1))
    # CAM1 B2B call-out
    x0, y0, x1, y1 = CAM1_RECT
    feat(doc, "ANNO_CAM1_BODY", rect(x0, y0, x1, y1))
    text(doc, "ANNO_CAM1_TEXT", "CAM1 B2B 0.4mm 2x15P", x0 - 1.0, y1 + 1.5, 2.0)
    doc.recompute()
    out = os.path.join(HERE, "dxf", "lbc3_board.dxf")
    importDXF.export(doc.Objects, out)
    print("wrote", out)
    App.closeDocument(doc.Name)


def export_adapter():
    doc = App.newDocument("dxf_cam1_adapter")
    adapter = _ns["build_adapter"]()
    adapter.translate(Vector(0, 0, -_ns["ADAPTER_Z0"]))
    feat(doc, "ADAPTER_PCB_OUTLINE", horizontal_face(adapter, +1))

    # Both connectors are shown in the LBC3 top-view board frame.  The B2B
    # header is mounted on the adapter's bottom, so its PCB pad order must be
    # mirrored in the actual ECAD footprint.
    feat(doc, "ANNO_AXE630124D_BOTTOM_BODY",
         rect(ADAPTER_CX - AXE_L / 2, ADAPTER_CY - AXE_W / 2,
              ADAPTER_CX + AXE_L / 2, ADAPTER_CY + AXE_W / 2))
    feat(doc, "ANNO_KH_FG0_5_H2_0_30PIN_TOP_BODY",
         rect(FPC_CX - FPC_L / 2, FPC_CY - FPC_W / 2,
              FPC_CX + FPC_L / 2, FPC_CY + FPC_W / 2))
    feat(doc, "ANNO_FPC_RIBBON_EXIT_PLUS_Y",
         Part.makePolygon([Vector(FPC_CX, FPC_CY + FPC_W / 2, 0),
                           Vector(FPC_CX, FPC_CY + FPC_W / 2 + 1.0, 0)]))
    text(doc, "ANNO_AXE_TEXT", "BOTTOM AXE630124D", 53.0, 50.5, 1.8)
    text(doc, "ANNO_FPC_TEXT", "TOP KH-FG0.5-H2.0-30PIN", 53.0, 60.0, 1.8)
    text(doc, "ANNO_DXF_NOTE", "MECHANICAL ONLY - CHECK ECAD LAND PATTERNS", 53.0, 56.0, 1.5)
    doc.recompute()
    out = os.path.join(HERE, "dxf", "lbc3_cam1_adapter.dxf")
    importDXF.export(doc.Objects, out)
    print("wrote", out)
    App.closeDocument(doc.Name)


if __name__ == "__main__":
    os.makedirs(os.path.join(HERE, "dxf"), exist_ok=True)
    export_top_plate()
    export_board()
    export_adapter()
    print("done")
