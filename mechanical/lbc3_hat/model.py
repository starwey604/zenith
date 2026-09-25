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
M25_CLEAR_D = 2.7         # 4x board mount screws (board holes are Dia2.6)
M2_CLEAR_D = 2.2          # CAM1 adapter screws
M2_SPACER_OD = 4.0

# Plate footprint: cut away the left edge so the Ethernet stays reachable.
PLATE_X_MIN = 18.4        # right edge of the HR911130A jack
# Power-input (24V -> 5V) keep-out on the right.   # TBC: real module footprint
POWER_OPEN = (68.0, 8.0, 84.0, 20.0)

# Fan: 18 x 18 x 4 mm, mounted under the plate above the SoC.
FAN_U, FAN_THK = 18.0, 4.0
FAN_SCREW_SPAN, FAN_SCREW_D = 15.0, 1.8
FAN_OPEN_D = 16.0
FAN_CX, FAN_CY = 58.5, 32.2      # RK3576 centre, measured from the STEP

# CAM1 J16 is AXE530127D (V2R0 schematic sheet 27), also measured in STEP.
# Its mating header AXE630124D goes on the UNDERSIDE of the adapter.
CAM1_RECT = (35.20, 50.03, 43.70, 52.53)
CAM1_H = 0.77
CAM1_MATED_H = 0.8
AXE630124D_L, AXE630124D_W, AXE630124D_H = 7.8, 2.0, 0.65

# CAM1 -> 30P FPC adapter.  The 10 mm neck fits between the infrared receiver
# and the neighbouring FPC connector.  The 24 mm head is beyond the rear edge
# of the LBC3 board, with 1 mm diagonal transitions at the shoulders.
ADAPTER_NECK_X = (34.45, 44.45)
ADAPTER_NECK_Y0 = 47.0
ADAPTER_SHOULDER_Y = 55.3
ADAPTER_HEAD_X = (27.45, 51.45)
ADAPTER_HEAD_Y = (56.3, 65.3)
ADAPTER_T = 1.6
ADAPTER_CX, ADAPTER_CY = 39.45, 51.28
ADAPTER_Z0 = CAM1_MATED_H

# Kinghelm KH-FG0.5-H2.0-30PIN: 19.4 mm body length, 6.0 mm depth,
# 2.0 mm height.  The FPC enters from the rear (+y) edge.  These are
# mechanical envelopes, not production land patterns.
FPC30_CX, FPC30_CY = ADAPTER_CX, 60.3
FPC30_L, FPC30_W, FPC30_H = 19.4, 6.0, 2.0
# CAM1 adapter retention.
# The top plate is a PCB and cannot carry moulded bosses, so the downward
# pressure comes from a SEPARATE part: a 3D-printed press bar screwed to the
# plate's underside.  It is shaped to clear the IR receiver (y>=51.12) and the
# 24P FPC (y<=46.24), and leaves the +y edge free for the 30P ribbon.
PRESS_BAR = (33.0, 47.2, 46.0, 50.4)      # x0, y0, x1, y1
PRESS_BAR_Z0 = 3.4                        # bar bottom (foam sits below it)
FOAM_T = 1.0                              # silicone/EPDM pad -> compliance
PRESS_BAR_HOLES = [(34.6, 48.8), (44.4, 48.8)]   # 2x M2 into heat-set inserts
M2_INSERT_D = 3.6                         # cosmetic: modelled as a hole

NOTCH = [(16.0, 56.0), (17.0, 55.0), (17.0, 52.5), (18.5, 51.0),
         (20.0, 52.5), (20.0, 55.0), (21.0, 56.0), (21.0, 57.5), (16.0, 57.5)]

COL_BOARD, COL_PLATE = (0.20, 0.45, 0.20), (0.20, 0.35, 0.70)
COL_STAND, COL_HDR = (0.85, 0.55, 0.10), (0.35, 0.35, 0.35)
COL_FAN, COL_ADAPTER = (0.15, 0.15, 0.15), (0.10, 0.60, 0.10)
COL_PRESS, COL_FOAM_PAD = (0.85, 0.30, 0.30), (0.95, 0.85, 0.20)


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
    # two M2 holes for the printed press bar that holds the CAM1 adapter
    for hx, hy in PRESS_BAR_HOLES:
        s = s.cut(cyl(hx, hy, GAP - 2, M2_CLEAR_D, PLATE_T + 4))
    return s


def build_adapter():
    """One-piece CAM1 adapter with a narrow neck and rear FPC head."""
    nx0, nx1 = ADAPTER_NECK_X
    hx0, hx1 = ADAPTER_HEAD_X
    hy0, hy1 = ADAPTER_HEAD_Y
    points = [(nx0, ADAPTER_NECK_Y0), (nx1, ADAPTER_NECK_Y0),
              (nx1, ADAPTER_SHOULDER_Y), (nx1 + 1.0, hy0),
              (hx1, hy0), (hx1, hy1), (hx0, hy1), (hx0, hy0),
              (nx0 - 1.0, hy0), (nx0, ADAPTER_SHOULDER_Y),
              (nx0, ADAPTER_NECK_Y0)]
    return poly_prism(points, ADAPTER_Z0, ADAPTER_T)


def build_adapter_header():
    """AXE630124D body envelope, with the 0.8 mm mated stack height."""
    return box_between(ADAPTER_CX - AXE630124D_L / 2,
                       ADAPTER_CY - AXE630124D_W / 2,
                       ADAPTER_Z0 - AXE630124D_H,
                       ADAPTER_CX + AXE630124D_L / 2,
                       ADAPTER_CY + AXE630124D_W / 2, ADAPTER_Z0)


def build_fpc30():
    """KH-FG0.5-H2.0-30PIN body envelope on the adapter top face."""
    return box_between(FPC30_CX - FPC30_L / 2, FPC30_CY - FPC30_W / 2,
                       ADAPTER_Z0 + ADAPTER_T,
                       FPC30_CX + FPC30_L / 2, FPC30_CY + FPC30_W / 2,
                       ADAPTER_Z0 + ADAPTER_T + FPC30_H)


def build_press_bar():
    x0, y0, x1, y1 = PRESS_BAR
    s = box_between(x0, y0, PRESS_BAR_Z0, x1, y1, GAP)
    for hx, hy in PRESS_BAR_HOLES:                 # heat-set insert holes
        s = s.cut(cyl(hx, hy, PRESS_BAR_Z0 + 2.0, M2_INSERT_D, GAP - PRESS_BAR_Z0))
    return s


def build_press_foam():
    x0, y0, x1, y1 = PRESS_BAR
    return box_between(x0, y0, PRESS_BAR_Z0 - FOAM_T, x1, y1, PRESS_BAR_Z0)


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
    if obj.ViewObject is not None:  # FreeCADCmd has no GUI view provider
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
    # 18x18x4 fan sits on the TOP (component) side of the plate
    fan = Part.makeBox(FAN_U, FAN_U, FAN_THK,
                       Vector(FAN_CX - FAN_U / 2, FAN_CY - FAN_U / 2, GAP + PLATE_T))
    show(fan, "REF_fan18", COL_FAN, doc)

    show(build_plate(), "TOP_plate", COL_PLATE, doc, 40)
    show(build_adapter(), "B2B_adapter", COL_ADAPTER, doc)
    show(build_adapter_header(), "AXE630124D_bottom", COL_HDR, doc)
    show(build_fpc30(), "KH_FG0_5_H2_0_30PIN_top", COL_HDR, doc)
    for i, st in enumerate(build_standoffs()):
        show(st, "STANDOFF_%d" % (i + 1), COL_STAND, doc)
    show(build_press_bar(), "PRESS_BAR", COL_PRESS, doc)
    show(build_press_foam(), "PRESS_FOAM", COL_FOAM_PAD, doc)
    doc.recompute()
    return doc


def fit_into_step(doc):
    """Add the plate / adapter / standoffs to an open STEP document."""
    show(to_step(build_plate()), "TOP_plate", COL_PLATE, doc, 40)
    show(to_step(build_adapter()), "B2B_adapter", COL_ADAPTER, doc)
    show(to_step(build_adapter_header()), "AXE630124D_bottom", COL_HDR, doc)
    show(to_step(build_fpc30()), "KH_FG0_5_H2_0_30PIN_top", COL_HDR, doc)
    for i, st in enumerate(build_standoffs()):
        show(to_step(st), "STANDOFF_%d" % (i + 1), COL_STAND, doc)
    show(to_step(build_press_bar()), "PRESS_BAR", COL_PRESS, doc)
    show(to_step(build_press_foam()), "PRESS_FOAM", COL_FOAM_PAD, doc)
    doc.recompute()
    return doc


if __name__ == "__main__":
    _doc = build()
    print("objects:", [o.Name for o in _doc.Objects])
