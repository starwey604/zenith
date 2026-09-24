"""Parametric mechanical model for the LubanCat-3 40-pin add-on ("top plate").

Two coordinate frames are used:

* **board frame** (what you edit below), millimetres:
    origin = LBC3 PCB bottom-left corner viewed from the TOP
    x = along the long edge (0 .. 85), y = away from the 40-pin edge (0 .. 56)
    z = height above the PCB top surface (PCB occupies z = -1.6 .. 0)

* **STEP frame** (the vendor `Lubancat3_3D_Model.STEP`), millimetres:
    the board plane is X-Z, the board normal is Y
    PCB top surface is y = 0, bottom y = -1.6
    mapping:  step = (board_x, board_z, -board_y)

Ground truth from the vendor files (`LubanCat3(EBF410513V2R0_20260521)/`):
  DXF结构图  -> outline 85x56, R1.5x4, 40-pin span x 28.52..76.78, rows y 1.78/4.32,
                mount holes Dia2.6 at (23.5,3.5)(23.5,52.5)(81.5,3.5)(81.5,52.5)
  3D模型     -> RK3576 centre board (58.5, 32.2); 40-pin pin tips at +8.54 above PCB
                Ethernet HR911130A occupies board x -3.0 .. 18.4

Values marked  # TBC  still need a decision.

Run inside FreeCAD:  exec(open(__file__).read()); build()
"""

import FreeCAD as App
import Part
from FreeCAD import Vector

# --------------------------------------------------------------------------
# Parameters (mm), board frame
# --------------------------------------------------------------------------
BOARD_L, BOARD_W, BOARD_T, CORNER_R = 85.0, 56.0, 1.6, 1.5

HDR_X0, HDR_PITCH, HDR_COLS = 28.52, 2.54, 20
HDR_ROWS_Y = (1.78, 4.32)
HDR_BODY_PAD = 1.27

MOUNT_HOLES = [(23.5, 3.5), (81.5, 3.5), (23.5, 52.5), (81.5, 52.5)]
MOUNT_HOLE_D = 2.6

PLATE_T = 1.6
GAP = 8.5                 # PCB top -> plate bottom (= 40-pin mated height)
M25_CLEAR_D = 2.7

# Plate footprint: cut away the left edge so the Ethernet stays reachable.
PLATE_X_MIN = 18.4        # right edge of the HR911130A jack
# Power-input (24V -> 5V) keep-out on the right.   # TBC: real module footprint
POWER_OPEN = (68.0, 8.0, 84.0, 20.0)

# Fan: 18 x 18 x 4 mm, mounted under the plate above the SoC.
FAN_U, FAN_THK = 18.0, 4.0
FAN_SCREW_SPAN, FAN_SCREW_D = 15.0, 1.8
FAN_OPEN_D = 16.0
FAN_CX, FAN_CY = 58.5, 32.2      # RK3576 centre, measured from the STEP

# CAM1 board-to-board socket  "0.4mm BTB母座2x15P 双槽 立贴式"
# board x 35.20..43.70, y 50.03..52.53, height 0.77  (from the STEP)
CAM1_RECT = (35.20, 50.03, 43.70, 52.53)
CAM1_H = 0.77
# Adapter board: just covers CAM1 + two M2.5 screws.   # TBC: refine with user
ADAPTER_L, ADAPTER_W, ADAPTER_T = 10.0, 10.0, 1.6
ADAPTER_CX, ADAPTER_CY = 39.45, 51.0
ADAPTER_Z0 = CAM1_H              # sits on top of the socket
ADAPTER_HOLE_SPAN = 3.5          # the two M2.5 holes, along board y
ADAPTER_HOLE_D = 2.7

NOTCH = [(16.0, 56.0), (17.0, 55.0), (17.0, 52.5), (18.5, 51.0),
         (20.0, 52.5), (20.0, 55.0), (21.0, 56.0), (21.0, 57.5), (16.0, 57.5)]

COL_BOARD, COL_PLATE = (0.20, 0.45, 0.20), (0.20, 0.35, 0.70)
COL_STAND, COL_HDR = (0.85, 0.55, 0.10), (0.35, 0.35, 0.35)
COL_FAN, COL_ADAPTER = (0.15, 0.15, 0.15), (0.10, 0.60, 0.10)


# --------------------------------------------------------------------------
# helpers (board frame)
# --------------------------------------------------------------------------
def rounded_box(length, width, height, z0):
    s = Part.makeBox(length, width, height, Vector(0, 0, z0))
    vert = [e for e in s.Edges
            if abs(e.Vertexes[0].Point.x - e.Vertexes[1].Point.x) < 1e-6
            and abs(e.Vertexes[0].Point.y - e.Vertexes[1].Point.y) < 1e-6]
    return s.makeFillet(CORNER_R, vert)


def box_between(x0, y0, z0, x1, y1, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, Vector(x0, y0, z0))


def poly_prism(points, z0, height):
    wire = Part.makePolygon([Vector(x, y, z0) for x, y in points])
    return Part.Face(wire).extrude(Vector(0, 0, height))


def cyl(x, y, z0, d, h):
    return Part.makeCylinder(d / 2, h, Vector(x, y, z0))


# --------------------------------------------------------------------------
# solids (board frame)
# --------------------------------------------------------------------------
def build_plate():
    s = rounded_box(BOARD_L, BOARD_W, PLATE_T, GAP)
    s = s.cut(box_between(-4, -4, GAP - 2, PLATE_X_MIN, 60, GAP + PLATE_T + 2))
    s = s.cut(poly_prism(NOTCH, GAP - 1, PLATE_T + 2))
    for x, y in MOUNT_HOLES:
        s = s.cut(cyl(x, y, GAP - 2, M25_CLEAR_D, PLATE_T + 4))
    s = s.cut(cyl(FAN_CX, FAN_CY, GAP - 2, FAN_OPEN_D, PLATE_T + 4))
    for sx in (-1, 1):
        for sy in (-1, 1):
            s = s.cut(cyl(FAN_CX + sx * FAN_SCREW_SPAN / 2,
                          FAN_CY + sy * FAN_SCREW_SPAN / 2,
                          GAP - 2, FAN_SCREW_D, PLATE_T + 4))
    x0, y0, x1, y1 = POWER_OPEN
    s = s.cut(box_between(x0, y0, GAP - 2, x1, y1, GAP + PLATE_T + 2))
    # two M2.5 holes for the CAM1 adapter board
    for sy in (-1, 1):
        s = s.cut(cyl(ADAPTER_CX, ADAPTER_CY + sy * ADAPTER_HOLE_SPAN,
                      GAP - 2, ADAPTER_HOLE_D, PLATE_T + 4))
    return s


def build_adapter():
    s = Part.makeBox(ADAPTER_L, ADAPTER_W, ADAPTER_T,
                     Vector(ADAPTER_CX - ADAPTER_L / 2, ADAPTER_CY - ADAPTER_W / 2,
                            ADAPTER_Z0))
    for sy in (-1, 1):
        s = s.cut(cyl(ADAPTER_CX, ADAPTER_CY + sy * ADAPTER_HOLE_SPAN,
                      ADAPTER_Z0 - 1, ADAPTER_HOLE_D, ADAPTER_T + 2))
    return s


def build_adapter_spacers():
    """M2.5 nylon spacers between the plate underside and the adapter board."""
    z0 = ADAPTER_Z0 + ADAPTER_T
    return [cyl(ADAPTER_CX, ADAPTER_CY + sy * ADAPTER_HOLE_SPAN, z0,
                M25_CLEAR_D + 1.8, GAP - z0) for sy in (-1, 1)]


def build_standoffs():
    return [cyl(x, y, 0, M25_CLEAR_D + 1.8, GAP) for x, y in MOUNT_HOLES]


# --------------------------------------------------------------------------
# frame conversion
# --------------------------------------------------------------------------
def to_step(shape):
    """(board_x, board_y, board_z) -> (board_x, board_z, -board_y)."""
    m = App.Matrix()
    m.A11, m.A12, m.A13 = 1, 0, 0
    m.A21, m.A22, m.A23 = 0, 0, 1
    m.A31, m.A32, m.A33 = 0, -1, 0
    return shape.transformGeometry(m)


def show(shape, name, color, doc=None, transparency=0):
    doc = doc or App.ActiveDocument
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    obj.ViewObject.ShapeColor = color
    obj.ViewObject.Transparency = transparency
    return obj


def build(doc_name="lbc3_hat"):
    """Standalone board-frame document (reference + plate + adapter)."""
    doc = App.newDocument(doc_name)
    board = rounded_box(BOARD_L, BOARD_W, BOARD_T, -BOARD_T)
    board = board.cut(poly_prism(NOTCH, -BOARD_T - 1, BOARD_T + 2))
    for x, y in MOUNT_HOLES:
        board = board.cut(cyl(x, y, -BOARD_T - 2, MOUNT_HOLE_D, BOARD_T + 4))
    show(board, "REF_lbc3_board", COL_BOARD, doc, 75)

    hdr = Part.makeBox(HDR_COLS * HDR_PITCH + 2 * HDR_BODY_PAD, 5.08, 2.5,
                       Vector(HDR_X0 - HDR_PITCH / 2 - HDR_BODY_PAD, HDR_ROWS_Y[0] - 1.27, 0))
    show(hdr, "REF_header40_male", COL_HDR, doc)
    fan = Part.makeBox(FAN_U, FAN_U, FAN_THK,
                       Vector(FAN_CX - FAN_U / 2, FAN_CY - FAN_U / 2, GAP - FAN_THK))
    show(fan, "REF_fan15", COL_FAN, doc)

    show(build_plate(), "TOP_plate", COL_PLATE, doc, 40)
    show(build_adapter(), "B2B_adapter", COL_ADAPTER, doc)
    for i, st in enumerate(build_standoffs()):
        show(st, "STANDOFF_%d" % (i + 1), COL_STAND, doc)
    for i, sp in enumerate(build_adapter_spacers()):
        show(sp, "ADAPTER_SPACER_%d" % (i + 1), COL_ADAPTER, doc)
    doc.recompute()
    return doc


def fit_into_step(doc):
    """Add the plate / adapter / standoffs to an open STEP document."""
    show(to_step(build_plate()), "TOP_plate", COL_PLATE, doc, 40)
    show(to_step(build_adapter()), "B2B_adapter", COL_ADAPTER, doc)
    for i, st in enumerate(build_standoffs()):
        show(to_step(st), "STANDOFF_%d" % (i + 1), COL_STAND, doc)
    for i, sp in enumerate(build_adapter_spacers()):
        show(to_step(sp), "ADAPTER_SPACER_%d" % (i + 1), COL_ADAPTER, doc)
    doc.recompute()
    return doc


if __name__ == "__main__":
    _doc = build()
    print("objects:", [o.Name for o in _doc.Objects])
