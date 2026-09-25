"""First-pass printable two-piece enclosure for LubanCat-3 and its add-ons.

Board-frame coordinates, millimetres: x along the 85 mm board edge, +y away
from the 40-pin header, z above the LubanCat-3 PCB top face.  Connector
windows are generous access openings, not connector-specific snap fits.

Run in FreeCAD or FreeCADCmd from the repository root.  The reference shapes
in the assembly are lightweight envelopes; collision checks use the vendor
V2R0 STEP separately.
"""

from pathlib import Path
import sys

import FreeCAD as App
import Part
from FreeCAD import Vector

HAT_DIR = Path(__file__).resolve().parents[1] / "lbc3_hat"
if str(HAT_DIR) not in sys.path:
    sys.path.insert(0, str(HAT_DIR))
import model as hat

# Exterior and print parameters.
X0, X1 = -7.0, 91.5
Y0, Y1 = -7.0, 74.0
WALL = 2.4
CORNER_R = 2.5
FLOOR_Z, FLOOR_TOP = -12.5, -9.5
SEAM_Z = 6.0
ROOF_INNER_Z, ROOF_Z = 19.0, 21.5

# Four case screws are outside both PCBs.  M3 clearance in the lid and a
# pilot hole in the base leave the insert/screw method open for the next pass.
CASE_SCREWS = [(-3.0, -3.0), (87.5, -3.0),
               (-3.0, 70.0), (87.5, 70.0)]
CASE_POST_D = 6.0
LID_CLEAR_D, BASE_PILOT_D, HEAD_RECESS_D = 3.3, 2.5, 5.8
BOARD_BOSS_D, BOARD_CLEAR_D = 6.5, 2.8

# Board-frame apertures: x extent on the rear wall, y extent on the sides.
# XT30 is PCB-soldered; the two GH1.25 connectors are horizontal 2-pin.
# They are intended for the existing 40-pin top PCB (top face z=10.1).
# Aperture positions remain provisional until its connector footprints are laid
# out; the second GH location likely needs a small rear-right PCB extension.
REAR_FPC = (25.0, 54.0, 1.0, 9.5)       # x0, x1, z0, z1
REAR_XT30 = (57.0, 84.0, 8.5, 17.0)
RIGHT_GH_PAIR = (44.5, 65.0, 9.0, 17.0) # y0, y1, z0, z1
RIGHT_PORTS = [
    (6.0, 17.0, -2.0, 8.0),       # first USB-C
    (19.0, 33.0, -2.0, 8.0),      # mini HDMI
    (35.0, 46.0, -2.0, 8.0),      # second USB-C
]
LEFT_IO = (0.5, 55.7, -4.5, 18.0)       # RJ45 + stacked USB ports

# A small ledge supports the cantilevered CAM1 adapter head with 0.2 mm
# nominal vertical clearance to its underside (z=0.8).
ADAPTER_LEDGE = (29.0, 61.0, 50.0, 64.0, 0.6)


def box(x0, y0, z0, x1, y1, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, Vector(x0, y0, z0))


def rounded_prism(x0, y0, z0, x1, y1, z1, radius):
    solid = box(x0, y0, z0, x1, y1, z1)
    vertical = [e for e in solid.Edges
                if abs(e.Vertexes[0].Point.x - e.Vertexes[1].Point.x) < 1e-7
                and abs(e.Vertexes[0].Point.y - e.Vertexes[1].Point.y) < 1e-7]
    return solid.makeFillet(radius, vertical)


def bore(x, y, z0, diameter, height):
    return Part.makeCylinder(diameter / 2.0, height, Vector(x, y, z0))


def shell(z0, z1, cavity_z0, cavity_z1):
    outer = rounded_prism(X0, Y0, z0, X1, Y1, z1, CORNER_R)
    inner = rounded_prism(X0 + WALL, Y0 + WALL, cavity_z0,
                          X1 - WALL, Y1 - WALL, cavity_z1,
                          max(0.5, CORNER_R - WALL))
    return outer.cut(inner)


def cut_access_windows(shape):
    """Cut existing board ports plus the proposed external wiring windows."""
    ly0, ly1, lz0, lz1 = LEFT_IO
    shape = shape.cut(box(X0 - 1, ly0, lz0, X0 + WALL + 1, ly1, lz1))
    for ry0, ry1, rz0, rz1 in RIGHT_PORTS + [RIGHT_GH_PAIR]:
        shape = shape.cut(box(X1 - WALL - 1, ry0, rz0,
                              X1 + 1, ry1, rz1))
    for rx0, rx1, rz0, rz1 in (REAR_FPC, REAR_XT30):
        shape = shape.cut(box(rx0, Y1 - WALL - 1, rz0,
                              rx1, Y1 + 1, rz1))
    return shape


def build_base():
    base = shell(FLOOR_Z, SEAM_Z, FLOOR_TOP, SEAM_Z + 1)
    for x, y in CASE_SCREWS:
        base = base.fuse(bore(x, y, FLOOR_TOP, CASE_POST_D,
                              SEAM_Z - FLOOR_TOP))
    for x, y in hat.MOUNT_HOLES:
        base = base.fuse(bore(x, y, FLOOR_TOP, BOARD_BOSS_D,
                              -hat.BOARD_T - FLOOR_TOP))
        base = base.cut(bore(x, y, FLOOR_Z - 0.1, BOARD_CLEAR_D,
                             -hat.BOARD_T - FLOOR_Z + 0.2))
    lx0, ly0, lx1, ly1, lz1 = ADAPTER_LEDGE
    base = base.fuse(box(lx0, ly0, FLOOR_TOP, lx1, ly1, lz1))
    for x, y in CASE_SCREWS:
        base = base.cut(bore(x, y, -1.0, BASE_PILOT_D, SEAM_Z + 1.1))
    return cut_access_windows(base).removeSplitter()


def build_lid():
    lid = shell(SEAM_Z, ROOF_Z, SEAM_Z - 1, ROOF_INNER_Z)
    for x, y in CASE_SCREWS:
        lid = lid.fuse(bore(x, y, SEAM_Z, CASE_POST_D,
                            ROOF_INNER_Z - SEAM_Z))
        lid = lid.cut(bore(x, y, SEAM_Z - 0.1, LID_CLEAR_D,
                           ROOF_Z - SEAM_Z + 0.2))
        lid = lid.cut(bore(x, y, ROOF_Z - 2.4, HEAD_RECESS_D, 2.5))
    # Fan intake; the fan is 18 x 18 x 4 above the top PCB, centred on SoC.
    lid = lid.cut(bore(hat.FAN_CX, hat.FAN_CY,
                       ROOF_INNER_Z - 0.1, 18.0,
                       ROOF_Z - ROOF_INNER_Z + 0.2))
    # Three high-side slots provide an air exit opposite the fan intake.
    for x0 in (43.0, 53.0, 63.0):
        lid = lid.cut(box(x0, Y0 - 1, 9.0,
                          x0 + 7.0, Y0 + WALL + 1, 12.0))
    return cut_access_windows(lid).removeSplitter()


def reference_board():
    board = hat.rounded_box(hat.BOARD_L, hat.BOARD_W,
                            hat.BOARD_T, -hat.BOARD_T)
    board = board.cut(hat.poly_prism(hat.NOTCH, -hat.BOARD_T - 1,
                                     hat.BOARD_T + 2))
    for x, y in hat.MOUNT_HOLES:
        board = board.cut(bore(x, y, -hat.BOARD_T - 1,
                               hat.MOUNT_HOLE_D, hat.BOARD_T + 2))
    return board


def show(doc, shape, name, color, transparency=0):
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    if obj.ViewObject is not None:
        obj.ViewObject.ShapeColor = color
        obj.ViewObject.Transparency = transparency
    return obj


def build_assembly(name="lbc3_case_v1"):
    doc = App.newDocument(name)
    show(doc, build_base(), "CASE_base", (0.82, 0.77, 0.66), 15)
    show(doc, build_lid(), "CASE_lid", (0.35, 0.55, 0.72), 70)
    show(doc, reference_board(), "REF_lbc3_board", (0.15, 0.52, 0.19), 35)
    show(doc, hat.build_plate(), "REF_top_plate", (0.16, 0.25, 0.65), 35)
    show(doc, hat.build_adapter(), "REF_cam1_adapter", (0.10, 0.62, 0.18))
    show(doc, hat.build_adapter_header(), "REF_AXE630124D", (0.35, 0.35, 0.35))
    show(doc, hat.build_fpc30(), "REF_FPC30", (0.15, 0.15, 0.15))
    show(doc, box(hat.FAN_CX - hat.FAN_U / 2,
                  hat.FAN_CY - hat.FAN_U / 2,
                  hat.GAP + hat.PLATE_T,
                  hat.FAN_CX + hat.FAN_U / 2,
                  hat.FAN_CY + hat.FAN_U / 2,
                  hat.GAP + hat.PLATE_T + hat.FAN_THK),
         "REF_fan18", (0.1, 0.1, 0.1))
    # Vendor STEP envelopes, for visible I/O orientation without embedding
    # the 56 MB, 577-object reference assembly in this editable document.
    ports = [
        ("REF_RJ45_envelope", (-3.02, 1.86, -3.0, 18.38, 17.74, 13.5)),
        ("REF_USB3_envelope", (-2.97, 21.24, -3.2, 14.49, 37.07, 16.34)),
        ("REF_USB2_envelope", (-2.96, 39.11, -3.2, 14.63, 54.93, 16.49)),
        ("REF_USB_C_1_envelope", (78.39, 6.96, -1.1, 85.97, 15.9, 3.28)),
        ("REF_mini_HDMI_envelope", (77.59, 20.33, -1.05, 85.59, 31.53, 3.2)),
        ("REF_USB_C_2_envelope", (77.85, 35.93, -0.6, 85.95, 44.87, 3.16)),
    ]
    for port_name, coords in ports:
        show(doc, box(*coords), port_name, (0.42, 0.42, 0.42), 75)
    doc.recompute()
    return doc


def print_oriented_shapes():
    """Return copies with their print-bed face at z=0."""
    base = build_base()
    base.translate(Vector(0, 0, -FLOOR_Z))
    lid = build_lid()
    lid.rotate(Vector((X0 + X1) / 2, (Y0 + Y1) / 2, 0),
               Vector(1, 0, 0), 180)
    lid.translate(Vector(0, 0, ROOF_Z))
    return base, lid


def export_print_stls(directory=None):
    """Export separate, bed-oriented STL files for the two case pieces."""
    import MeshPart

    output = Path(directory) if directory else Path(__file__).resolve().parent
    output.mkdir(parents=True, exist_ok=True)
    for filename, shape in zip(("case_base_print.stl", "case_lid_print.stl"),
                               print_oriented_shapes()):
        mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.15,
                                      AngularDeflection=0.35, Relative=False)
        mesh.write(str(output / filename))
        print("wrote", output / filename, "facets", mesh.CountFacets)


if __name__ == "__main__":
    _doc = build_assembly()
    print("objects:", [o.Name for o in _doc.Objects])
