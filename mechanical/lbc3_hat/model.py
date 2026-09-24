"""Parametric mechanical model for the LubanCat-3 40-pin add-on ("top plate").

Coordinate system (board frame, millimetres):
  origin  = LBC3 PCB bottom-left corner, viewed from the TOP (unit is the DXF
            board frame; x grows right, y grows "up" the board away from the
            40-pin header edge)
  z = 0   = LBC3 PCB TOP surface (components live above); the PCB occupies
            z = -BOARD_T .. 0.

Ground truth for BOARD_L/W, corner radius, mount holes, the 40-pin header span
and the SoC position comes from the vendor files:
  * LubanCat3_DXF_BOT.dxf          (BG_OUTLINE + PIN_BOTTOM layers)
  * LubanCat3_PCB尺寸图_.pdf        (R1.5X4, 85 x 56)

Every value marked  # TBC  is a placeholder that still needs a measurement from
the real board / schematic before manufacturing.

Run inside FreeCAD (GUI or freecadcmd):  exec(open(__file__).read())
"""

import FreeCAD as App
import Part
from FreeCAD import Vector

# --------------------------------------------------------------------------
# Parameters (mm) -- edit here, the model is regenerated from these.
# --------------------------------------------------------------------------
BOARD_L = 85.0          # board length  (X)  [vendor: 85]
BOARD_W = 56.0          # board width   (Y)  [vendor: 56]
BOARD_T = 1.6           # PCB thickness      [TBC: verify, 1.6 typical]
CORNER_R = 1.5          # board corner fillet [vendor: R1.5X4]

# 40-pin male header on the LBC3 (from DXF PIN_BOTTOM grid)
HDR_X0 = 28.52          # x of column 0 (pin 39/40 side)
HDR_PITCH = 2.54
HDR_COLS = 20
HDR_ROWS_Y = (1.78, 4.32)
HDR_BODY_PAD = 1.27     # body plastic overhangs 1.27 beyond the end pins

# Board mount holes (DXF r=1.3 -> Dia 2.6 -> M2.5 clearance)
MOUNT_HOLES = [(23.5, 3.5), (81.5, 3.5), (23.5, 52.5), (81.5, 52.5)]
MOUNT_HOLE_D = 2.6

# Top plate
PLATE_T = 1.6
GAP = 11.0              # LBC3 top surface -> plate bottom. # TBC (= 40-pin
                        #   mated height; must also fit the fan below)
M25_CLEAR_D = 2.7       # M2.5 clearance in the plate
M25_HEAD_D = 4.7        # M2.5 socket/lens head recess  # TBC

# Fan (mounted to the underside of the plate, above the SoC)   -- all TBC
FAN_U = 40.0            # fan size (square)
FAN_THK = 10.0
FAN_SCREW_SPAN = 32.0   # hole centre spacing
FAN_SCREW_D = 3.2       # M3 screws into the fan
FAN_OPEN_D = 34.0       # opening in the plate
FAN_CX = 55.0           # centre  # TBC (SoC position)
FAN_CY = 22.0

# Camera B2B -> FPC30 adapter board that we want to pin down  -- all TBC
B2B_CX, B2B_CY = 38.0, 51.0
B2B_L, B2B_W, B2B_H = 20.0, 8.0, 3.0

# Notch in the LBC3 top edge (from DXF BG_OUTLINE), as a closed polygon
NOTCH = [(16.0, 56.0), (17.0, 55.0), (17.0, 52.5), (18.5, 51.0),
         (20.0, 52.5), (20.0, 55.0), (21.0, 56.0), (21.0, 57.5), (16.0, 57.5)]

COL_BOARD = (0.20, 0.45, 0.20)
COL_PLATE = (0.20, 0.35, 0.70)
COL_STAND = (0.85, 0.55, 0.10)
COL_HDR = (0.35, 0.35, 0.35)
COL_FAN = (0.15, 0.15, 0.15)
COL_B2B = (0.10, 0.60, 0.10)


def rounded_box(length, width, height, z0):
    s = Part.makeBox(length, width, height, Vector(0, 0, z0))
    vert = [e for e in s.Edges
            if abs(e.Vertexes[0].Point.x - e.Vertexes[1].Point.x) < 1e-6
            and abs(e.Vertexes[0].Point.y - e.Vertexes[1].Point.y) < 1e-6]
    return s.makeFillet(CORNER_R, vert)


def poly_prism(points, z0, height):
    wire = Part.makePolygon([Vector(x, y, z0) for x, y in points])
    return Part.Face(wire).extrude(Vector(0, 0, height))


def show(shape, name, color):
    obj = Part.show(shape, name)
    obj.ViewObject.ShapeColor = color
    obj.ViewObject.Transparency = 70 if name.startswith("REF") else 0
    return obj


def build():
    doc = App.newDocument("lbc3_hat")

    # ---- reference: LBC3 board -------------------------------------------
    board = rounded_box(BOARD_L, BOARD_W, BOARD_T, -BOARD_T)
    board = board.cut(poly_prism(NOTCH, -BOARD_T - 1, BOARD_T + 2))
    for x, y in MOUNT_HOLES:
        board = board.cut(Part.makeCylinder(MOUNT_HOLE_D / 2, BOARD_T + 4,
                                            Vector(x, y, -BOARD_T - 2)))
    show(board, "REF_LBC3_board", COL_BOARD)

    # ---- reference: 40-pin male header on the LBC3 -----------------------
    body = Part.makeBox(HDR_COLS * HDR_PITCH + 2 * HDR_BODY_PAD, 5.08, 2.5,
                        Vector(HDR_X0 - HDR_PITCH / 2 - HDR_BODY_PAD,
                               HDR_ROWS_Y[0] - 1.27, 0.0))
    show(body, "REF_header40_male", COL_HDR)

    # ---- reference: SoC + fan envelope -----------------------------------
    soc = Part.makeBox(16, 16, 1.0, Vector(FAN_CX - 8, FAN_CY - 8, 0.0))
    show(soc, "REF_soc", COL_HDR)
    fan = Part.makeBox(FAN_U, FAN_U, FAN_THK,
                       Vector(FAN_CX - FAN_U / 2, FAN_CY - FAN_U / 2,
                              GAP - FAN_THK))
    show(fan, "REF_fan", COL_FAN)

    # ---- reference: camera B2B -> FPC30 adapter --------------------------
    b2b = Part.makeBox(B2B_L, B2B_W, B2B_H,
                       Vector(B2B_CX - B2B_L / 2, B2B_CY - B2B_W / 2, 0.0))
    show(b2b, "REF_b2b_adapter", COL_B2B)

    # ---- top plate -------------------------------------------------------
    plate = rounded_box(BOARD_L, BOARD_W, PLATE_T, GAP)
    plate = plate.cut(poly_prism(NOTCH, GAP - 1, PLATE_T + 2))
    for x, y in MOUNT_HOLES:                      # M2.5 fixing holes
        plate = plate.cut(Part.makeCylinder(M25_CLEAR_D / 2, PLATE_T + 4,
                                            Vector(x, y, GAP - 2)))
    # fan opening + fan screws
    plate = plate.cut(Part.makeCylinder(FAN_OPEN_D / 2, PLATE_T + 4,
                                        Vector(FAN_CX, FAN_CY, GAP - 2)))
    for sx in (-1, 1):
        for sy in (-1, 1):
            plate = plate.cut(Part.makeCylinder(
                FAN_SCREW_D / 2, PLATE_T + 4,
                Vector(FAN_CX + sx * FAN_SCREW_SPAN / 2,
                       FAN_CY + sy * FAN_SCREW_SPAN / 2, GAP - 2)))
    show(plate, "TOP_plate", COL_PLATE)

    # ---- copper/nylon standoffs at the 4 board mount holes ---------------
    for i, (x, y) in enumerate(MOUNT_HOLES):
        st = Part.makeCylinder(M25_CLEAR_D / 2 + 0.9, GAP, Vector(x, y, 0.0))
        show(st, "STANDOFF_%d" % (i + 1), COL_STAND)

    doc.recompute()
    return doc


if __name__ == "__main__":
    _doc = build()
    print("objects:", [o.Name for o in _doc.Objects])
