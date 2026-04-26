"""Generate 20 sample DXF 2D CAD drawings — 10 manufacturing, 10 construction."""

from __future__ import annotations

import logging
import math
from pathlib import Path

import ezdxf
from ezdxf import units
from ezdxf.document import Drawing

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _new_doc(description: str = "") -> Drawing:
    doc = ezdxf.new(dxfversion="R2010")
    doc.header["$INSUNITS"] = units.MM
    if description:
        doc.header["$PROJECTNAME"] = description[:255]

    # Create layers with explicit dark colors (ACI color index)
    # Avoid color 7 (white on white bg) and 2 (yellow, hard to see on white)
    layer_colors = {
        "BORDER": 250,     # dark gray
        "TITLEBLOCK": 250, # dark gray
        "TEXT": 250,       # dark gray
        "OUTLINE": 1,      # red
        "HOLE": 3,         # green
        "CENTER": 5,       # blue
        "DIMENSIONS": 5,   # blue
        "WALLS": 1,        # red
        "DOORS": 6,        # magenta
        "WINDOWS": 4,      # cyan
        "STRUCTURE": 1,    # red
        "BRACING": 3,      # green
        "CONCRETE": 8,     # dark gray
        "REBAR": 1,        # red
        "STIRRUP": 3,      # green
        "BRICK": 1,        # red
        "INSULATION": 4,   # cyan
        "PLASTER": 8,      # dark gray
        "RENDER": 30,      # orange
        "AIR_GAP": 3,      # green
        "TREADS": 1,       # red
        "HANDRAIL": 30,    # orange
        "STRINGER": 3,     # green
        "GRID": 8,         # dark gray
        "COLUMNS": 1,      # red
        "LABELS": 250,     # dark gray
        "FOOTING": 1,      # red
        "SLAB": 8,         # dark gray
        "SOIL": 30,        # orange
        "RAFTER": 1,       # red
        "PURLIN": 3,       # green
        "BUILDING": 1,     # red
        "BOUNDARY": 30,    # orange
        "ROAD": 8,         # dark gray
        "VEGETATION": 3,   # green
        "FRAME": 1,        # red
        "GLASS": 4,        # cyan
        "SILL": 30,        # orange
        "FLOOR": 1,        # red
        "ROOF": 3,         # green
        "ELEVATION": 8,    # dark gray
    }
    for name, color in layer_colors.items():
        doc.layers.add(name, color=color)

    return doc


def _add_title_block(msp, title: str, width: float, height: float) -> None:
    """Draw a border and title box."""
    msp.add_lwpolyline(
        [(0, 0), (width, 0), (width, height), (0, height)],
        close=True,
        dxfattribs={"layer": "BORDER"},
    )
    # title box bottom-right
    tx, ty = width - 80, 0
    msp.add_lwpolyline(
        [(tx, ty), (width, ty), (width, ty + 20), (tx, ty + 20)],
        close=True,
        dxfattribs={"layer": "TITLEBLOCK"},
    )
    msp.add_text(
        title,
        height=3.0,
        dxfattribs={"layer": "TEXT", "insert": (tx + 5, ty + 10)},
    )


def _add_center_mark(msp, cx: float, cy: float, size: float = 3.0, layer: str = "CENTER") -> None:
    msp.add_line((cx - size, cy), (cx + size, cy), dxfattribs={"layer": layer})
    msp.add_line((cx, cy - size), (cx, cy + size), dxfattribs={"layer": layer})


def _add_dimension_line(
    msp, p1: tuple, p2: tuple, offset: float = 10.0, layer: str = "DIMENSIONS"
) -> None:
    """Simplified dimension annotation between two points."""
    mx = (p1[0] + p2[0]) / 2
    my = (p1[1] + p2[1]) / 2
    dist = math.dist(p1, p2)
    msp.add_line(p1, p2, dxfattribs={"layer": layer, "linetype": "DASHED"})
    msp.add_text(
        f"{dist:.1f}",
        height=2.5,
        dxfattribs={"layer": layer, "insert": (mx, my + offset)},
    )


# ---------------------------------------------------------------------------
# Manufacturing drawings (10)
# ---------------------------------------------------------------------------

def _mfg_01_shaft(out: Path) -> Path:
    """Simple stepped shaft with dimensions."""
    doc = _new_doc("Stepped Shaft")
    msp = doc.modelspace()
    _add_title_block(msp, "STEPPED SHAFT", 297, 210)
    # shaft profile
    pts = [(50, 80), (50, 110), (100, 110), (100, 120), (180, 120),
           (180, 110), (230, 110), (230, 80), (180, 80), (180, 70),
           (100, 70), (100, 80)]
    msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "OUTLINE"})
    _add_center_mark(msp, 140, 95)
    _add_dimension_line(msp, (50, 80), (230, 80), offset=-15)
    _add_dimension_line(msp, (50, 80), (50, 110), offset=-15)
    fp = out / "mfg_01_stepped_shaft.dxf"
    doc.saveas(fp)
    return fp


def _mfg_02_flange(out: Path) -> Path:
    """Bolt-circle flange."""
    doc = _new_doc("Bolt Circle Flange")
    msp = doc.modelspace()
    _add_title_block(msp, "FLANGE", 297, 210)
    cx, cy = 148, 105
    msp.add_circle((cx, cy), 60, dxfattribs={"layer": "OUTLINE"})
    msp.add_circle((cx, cy), 30, dxfattribs={"layer": "OUTLINE"})
    msp.add_circle((cx, cy), 15, dxfattribs={"layer": "HOLE"})
    for i in range(6):
        a = math.radians(60 * i)
        bx = cx + 45 * math.cos(a)
        by = cy + 45 * math.sin(a)
        msp.add_circle((bx, by), 5, dxfattribs={"layer": "HOLE"})
        _add_center_mark(msp, bx, by, size=2, layer="CENTER")
    _add_center_mark(msp, cx, cy)
    fp = out / "mfg_02_flange.dxf"
    doc.saveas(fp)
    return fp


def _mfg_03_bracket(out: Path) -> Path:
    """L-bracket with mounting holes."""
    doc = _new_doc("L-Bracket")
    msp = doc.modelspace()
    _add_title_block(msp, "L-BRACKET", 297, 210)
    pts = [(60, 60), (60, 160), (80, 160), (80, 100), (160, 100), (160, 60)]
    msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "OUTLINE"})
    for hx, hy in [(70, 140), (70, 120), (120, 80), (140, 80)]:
        msp.add_circle((hx, hy), 4, dxfattribs={"layer": "HOLE"})
    _add_dimension_line(msp, (60, 60), (60, 160))
    _add_dimension_line(msp, (60, 60), (160, 60), offset=-10)
    fp = out / "mfg_03_bracket.dxf"
    doc.saveas(fp)
    return fp


def _mfg_04_gasket(out: Path) -> Path:
    """Rectangular gasket with rounded corners and bolt holes."""
    doc = _new_doc("Gasket")
    msp = doc.modelspace()
    _add_title_block(msp, "GASKET", 297, 210)
    # Outer rounded rectangle approximation
    w, h, r = 120, 80, 10
    ox, oy = 88, 65
    msp.add_lwpolyline([
        (ox + r, oy, 0, 0, 0), (ox + w - r, oy, 0.4142, 0, 0),
        (ox + w, oy + r, 0, 0, 0), (ox + w, oy + h - r, 0.4142, 0, 0),
        (ox + w - r, oy + h, 0, 0, 0), (ox + r, oy + h, 0.4142, 0, 0),
        (ox, oy + h - r, 0, 0, 0), (ox, oy + r, 0.4142, 0, 0),
    ], close=True, dxfattribs={"layer": "OUTLINE"})
    # Center hole
    msp.add_circle((ox + w / 2, oy + h / 2), 20, dxfattribs={"layer": "HOLE"})
    # Bolt holes at corners
    for dx, dy in [(20, 20), (w - 20, 20), (20, h - 20), (w - 20, h - 20)]:
        msp.add_circle((ox + dx, oy + dy), 5, dxfattribs={"layer": "HOLE"})
    fp = out / "mfg_04_gasket.dxf"
    doc.saveas(fp)
    return fp


def _mfg_05_gear_profile(out: Path) -> Path:
    """Simplified spur gear profile."""
    doc = _new_doc("Spur Gear")
    msp = doc.modelspace()
    _add_title_block(msp, "SPUR GEAR PROFILE", 297, 210)
    cx, cy = 148, 105
    teeth = 12
    outer_r, root_r, bore_r = 55, 45, 12
    msp.add_circle((cx, cy), bore_r, dxfattribs={"layer": "HOLE"})
    msp.add_circle((cx, cy), root_r, dxfattribs={"layer": "OUTLINE", "linetype": "DASHED"})
    pts = []
    for i in range(teeth):
        a1 = math.radians(360 / teeth * i)
        a2 = math.radians(360 / teeth * (i + 0.3))
        a3 = math.radians(360 / teeth * (i + 0.5))
        a4 = math.radians(360 / teeth * (i + 0.7))
        pts.append((cx + root_r * math.cos(a1), cy + root_r * math.sin(a1)))
        pts.append((cx + outer_r * math.cos(a2), cy + outer_r * math.sin(a2)))
        pts.append((cx + outer_r * math.cos(a3), cy + outer_r * math.sin(a3)))
        pts.append((cx + root_r * math.cos(a4), cy + root_r * math.sin(a4)))
    msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "OUTLINE"})
    _add_center_mark(msp, cx, cy, size=5)
    fp = out / "mfg_05_gear_profile.dxf"
    doc.saveas(fp)
    return fp


def _mfg_06_bushing(out: Path) -> Path:
    """Bushing cross-section."""
    doc = _new_doc("Bushing")
    msp = doc.modelspace()
    _add_title_block(msp, "BUSHING CROSS-SECTION", 297, 210)
    cx, cy = 148, 105
    msp.add_circle((cx, cy), 40, dxfattribs={"layer": "OUTLINE"})
    msp.add_circle((cx, cy), 25, dxfattribs={"layer": "OUTLINE"})
    msp.add_circle((cx, cy), 20, dxfattribs={"layer": "HOLE"})
    # Hatch lines (cross section)
    for i in range(-38, 39, 4):
        y = cy + i
        dx = math.sqrt(max(0, 40**2 - i**2))
        di = math.sqrt(max(0, 25**2 - i**2)) if abs(i) < 25 else 0
        if dx > di:
            msp.add_line((cx - dx, y), (cx - di, y), dxfattribs={"layer": "HATCH"})
            msp.add_line((cx + di, y), (cx + dx, y), dxfattribs={"layer": "HATCH"})
    _add_center_mark(msp, cx, cy, size=5)
    fp = out / "mfg_06_bushing.dxf"
    doc.saveas(fp)
    return fp


def _mfg_07_keyway(out: Path) -> Path:
    """Shaft end with keyway slot."""
    doc = _new_doc("Keyway Shaft End")
    msp = doc.modelspace()
    _add_title_block(msp, "KEYWAY SHAFT END", 297, 210)
    cx, cy = 148, 105
    msp.add_circle((cx, cy), 35, dxfattribs={"layer": "OUTLINE"})
    # Keyway slot
    kw, kd = 10, 5
    msp.add_lwpolyline([
        (cx - kw / 2, cy + 35 - kd), (cx - kw / 2, cy + 35),
        (cx + kw / 2, cy + 35), (cx + kw / 2, cy + 35 - kd),
    ], close=True, dxfattribs={"layer": "OUTLINE"})
    msp.add_circle((cx, cy), 15, dxfattribs={"layer": "HOLE"})
    _add_center_mark(msp, cx, cy)
    _add_dimension_line(msp, (cx - kw / 2, cy + 35), (cx + kw / 2, cy + 35), offset=5)
    fp = out / "mfg_07_keyway.dxf"
    doc.saveas(fp)
    return fp


def _mfg_08_spring_washer(out: Path) -> Path:
    """Spring washer top view."""
    doc = _new_doc("Spring Washer")
    msp = doc.modelspace()
    _add_title_block(msp, "SPRING WASHER", 297, 210)
    cx, cy = 148, 105
    msp.add_circle((cx, cy), 30, dxfattribs={"layer": "OUTLINE"})
    msp.add_circle((cx, cy), 15, dxfattribs={"layer": "HOLE"})
    # Split line
    msp.add_line((cx, cy + 15), (cx + 5, cy + 30), dxfattribs={"layer": "OUTLINE"})
    msp.add_line((cx, cy - 15), (cx - 5, cy - 30), dxfattribs={"layer": "OUTLINE"})
    _add_center_mark(msp, cx, cy)
    fp = out / "mfg_08_spring_washer.dxf"
    doc.saveas(fp)
    return fp


def _mfg_09_cam_profile(out: Path) -> Path:
    """Eccentric cam profile."""
    doc = _new_doc("Cam Profile")
    msp = doc.modelspace()
    _add_title_block(msp, "CAM PROFILE", 297, 210)
    cx, cy = 148, 105
    pts = []
    for i in range(72):
        a = math.radians(5 * i)
        r = 30 + 15 * (0.5 + 0.5 * math.sin(a))
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "OUTLINE"})
    msp.add_circle((cx, cy), 8, dxfattribs={"layer": "HOLE"})
    _add_center_mark(msp, cx, cy)
    fp = out / "mfg_09_cam_profile.dxf"
    doc.saveas(fp)
    return fp


def _mfg_10_mounting_plate(out: Path) -> Path:
    """Mounting plate with slot and holes."""
    doc = _new_doc("Mounting Plate")
    msp = doc.modelspace()
    _add_title_block(msp, "MOUNTING PLATE", 297, 210)
    ox, oy, w, h = 68, 55, 160, 100
    msp.add_lwpolyline(
        [(ox, oy), (ox + w, oy), (ox + w, oy + h), (ox, oy + h)],
        close=True, dxfattribs={"layer": "OUTLINE"},
    )
    # 4 corner holes
    for dx, dy in [(20, 20), (w - 20, 20), (20, h - 20), (w - 20, h - 20)]:
        msp.add_circle((ox + dx, oy + dy), 6, dxfattribs={"layer": "HOLE"})
    # Center slot
    sw, sh = 40, 12
    sx = ox + (w - sw) / 2
    sy = oy + (h - sh) / 2
    r = sh / 2
    msp.add_lwpolyline([
        (sx + r, sy), (sx + sw - r, sy, 1), (sx + sw - r, sy + sh, 0),
        (sx + r, sy + sh, 1),
    ], close=True, dxfattribs={"layer": "HOLE"})
    _add_dimension_line(msp, (ox, oy), (ox + w, oy), offset=-12)
    _add_dimension_line(msp, (ox, oy), (ox, oy + h), offset=-12)
    fp = out / "mfg_10_mounting_plate.dxf"
    doc.saveas(fp)
    return fp


# ---------------------------------------------------------------------------
# Construction drawings (10)
# ---------------------------------------------------------------------------

def _con_01_floor_plan(out: Path) -> Path:
    """Simple single-room floor plan."""
    doc = _new_doc("Single Room Floor Plan")
    msp = doc.modelspace()
    _add_title_block(msp, "FLOOR PLAN - ROOM", 420, 297)
    # Outer walls
    wall = 10
    ox, oy, rw, rh = 40, 40, 200, 150
    msp.add_lwpolyline(
        [(ox, oy), (ox + rw, oy), (ox + rw, oy + rh), (ox, oy + rh)],
        close=True, dxfattribs={"layer": "WALLS"},
    )
    msp.add_lwpolyline(
        [(ox + wall, oy + wall), (ox + rw - wall, oy + wall),
         (ox + rw - wall, oy + rh - wall), (ox + wall, oy + rh - wall)],
        close=True, dxfattribs={"layer": "WALLS"},
    )
    # Door opening
    msp.add_line(
        (ox + 80, oy), (ox + 110, oy), dxfattribs={"layer": "WALLS", "color": 0}
    )
    msp.add_arc(
        (ox + 80, oy + wall), 30, 270, 0, dxfattribs={"layer": "DOORS"}
    )
    # Window
    msp.add_line(
        (ox + rw, oy + 50), (ox + rw, oy + 100),
        dxfattribs={"layer": "WINDOWS", "linetype": "DASHED"},
    )
    _add_dimension_line(msp, (ox, oy - 5), (ox + rw, oy - 5), offset=-8)
    fp = out / "con_01_floor_plan.dxf"
    doc.saveas(fp)
    return fp


def _con_02_wall_section(out: Path) -> Path:
    """Wall cross-section detail."""
    doc = _new_doc("Wall Section")
    msp = doc.modelspace()
    _add_title_block(msp, "WALL SECTION DETAIL", 297, 210)
    ox, oy = 100, 30
    layers = [
        ("PLASTER", 5), ("BRICK", 25), ("INSULATION", 8),
        ("AIR_GAP", 3), ("BRICK", 12), ("RENDER", 3),
    ]
    y = oy
    for name, thickness in layers:
        msp.add_lwpolyline(
            [(ox, y), (ox + 80, y), (ox + 80, y + thickness), (ox, y + thickness)],
            close=True, dxfattribs={"layer": name},
        )
        msp.add_text(name, height=2, dxfattribs={"layer": "TEXT", "insert": (ox + 85, y + thickness / 2)})
        y += thickness
    _add_dimension_line(msp, (ox - 10, oy), (ox - 10, y), offset=-15)
    fp = out / "con_02_wall_section.dxf"
    doc.saveas(fp)
    return fp


def _con_03_foundation(out: Path) -> Path:
    """Strip foundation cross-section."""
    doc = _new_doc("Strip Foundation")
    msp = doc.modelspace()
    _add_title_block(msp, "STRIP FOUNDATION", 297, 210)
    # Ground line
    msp.add_line((30, 120), (270, 120), dxfattribs={"layer": "GROUND"})
    # Foundation
    pts = [(100, 120), (100, 60), (90, 60), (90, 40), (210, 40),
           (210, 60), (200, 60), (200, 120)]
    msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "CONCRETE"})
    # Rebar dots
    for rx in range(100, 210, 15):
        msp.add_circle((rx, 50), 2, dxfattribs={"layer": "REBAR"})
    # Wall above
    msp.add_lwpolyline(
        [(110, 120), (110, 180), (190, 180), (190, 120)],
        close=True, dxfattribs={"layer": "WALLS"},
    )
    _add_dimension_line(msp, (90, 40), (210, 40), offset=-10)
    fp = out / "con_03_foundation.dxf"
    doc.saveas(fp)
    return fp


def _con_04_roof_truss(out: Path) -> Path:
    """Simple triangular roof truss."""
    doc = _new_doc("Roof Truss")
    msp = doc.modelspace()
    _add_title_block(msp, "ROOF TRUSS", 420, 297)
    # Bottom chord
    msp.add_line((50, 100), (370, 100), dxfattribs={"layer": "STRUCTURE"})
    # Top chords
    msp.add_line((50, 100), (210, 220), dxfattribs={"layer": "STRUCTURE"})
    msp.add_line((370, 100), (210, 220), dxfattribs={"layer": "STRUCTURE"})
    # Web members
    web_x = [110, 170, 250, 310]
    for wx in web_x:
        ty = 100 + (120 * (1 - abs(wx - 210) / 160))
        msp.add_line((wx, 100), (wx, ty), dxfattribs={"layer": "STRUCTURE"})
    # Diagonal bracing
    msp.add_line((110, 100), (170, 100 + 120 * (1 - 40 / 160)), dxfattribs={"layer": "BRACING"})
    msp.add_line((310, 100), (250, 100 + 120 * (1 - 40 / 160)), dxfattribs={"layer": "BRACING"})
    _add_dimension_line(msp, (50, 100), (370, 100), offset=-15)
    fp = out / "con_04_roof_truss.dxf"
    doc.saveas(fp)
    return fp


def _con_05_staircase(out: Path) -> Path:
    """Staircase section view."""
    doc = _new_doc("Staircase Section")
    msp = doc.modelspace()
    _add_title_block(msp, "STAIRCASE SECTION", 297, 210)
    steps = 10
    riser, tread = 18, 25
    ox, oy = 50, 40
    for i in range(steps):
        x = ox + i * tread
        y = oy + i * riser
        msp.add_lwpolyline(
            [(x, y), (x + tread, y), (x + tread, y + riser)],
            dxfattribs={"layer": "STRUCTURE"},
        )
    # Stringer line
    msp.add_line((ox, oy), (ox + steps * tread, oy + steps * riser), dxfattribs={"layer": "STRUCTURE"})
    # Handrail
    msp.add_line(
        (ox, oy + 90), (ox + steps * tread, oy + steps * riser + 90),
        dxfattribs={"layer": "HANDRAIL"},
    )
    fp = out / "con_05_staircase.dxf"
    doc.saveas(fp)
    return fp


def _con_06_column_grid(out: Path) -> Path:
    """Structural column grid plan."""
    doc = _new_doc("Column Grid")
    msp = doc.modelspace()
    _add_title_block(msp, "COLUMN GRID PLAN", 420, 297)
    cols, rows = 5, 3
    sx, sy, dx, dy = 60, 60, 70, 70
    for c in range(cols):
        for r in range(rows):
            cx_pos = sx + c * dx
            cy_pos = sy + r * dy
            msp.add_lwpolyline(
                [(cx_pos - 5, cy_pos - 5), (cx_pos + 5, cy_pos - 5),
                 (cx_pos + 5, cy_pos + 5), (cx_pos - 5, cy_pos + 5)],
                close=True, dxfattribs={"layer": "COLUMNS"},
            )
            _add_center_mark(msp, cx_pos, cy_pos, size=2)
    # Grid lines
    for c in range(cols):
        x = sx + c * dx
        msp.add_line((x, sy - 20), (x, sy + (rows - 1) * dy + 20), dxfattribs={"layer": "GRID", "linetype": "DASHDOT"})
        msp.add_text(chr(65 + c), height=5, dxfattribs={"layer": "TEXT", "insert": (x - 2, sy - 30)})
    for r in range(rows):
        y = sy + r * dy
        msp.add_line((sx - 20, y), (sx + (cols - 1) * dx + 20, y), dxfattribs={"layer": "GRID", "linetype": "DASHDOT"})
        msp.add_text(str(r + 1), height=5, dxfattribs={"layer": "TEXT", "insert": (sx - 30, y - 2)})
    fp = out / "con_06_column_grid.dxf"
    doc.saveas(fp)
    return fp


def _con_07_beam_detail(out: Path) -> Path:
    """Reinforced concrete beam cross-section."""
    doc = _new_doc("RC Beam Detail")
    msp = doc.modelspace()
    _add_title_block(msp, "RC BEAM SECTION", 297, 210)
    ox, oy, bw, bh = 110, 50, 80, 120
    msp.add_lwpolyline(
        [(ox, oy), (ox + bw, oy), (ox + bw, oy + bh), (ox, oy + bh)],
        close=True, dxfattribs={"layer": "CONCRETE"},
    )
    # Bottom rebar
    cover = 8
    for i in range(3):
        rx = ox + cover + 10 + i * 25
        msp.add_circle((rx, oy + cover + 5), 4, dxfattribs={"layer": "REBAR"})
    # Top rebar
    for i in range(2):
        rx = ox + cover + 20 + i * 30
        msp.add_circle((rx, oy + bh - cover - 5), 3, dxfattribs={"layer": "REBAR"})
    # Stirrups
    msp.add_lwpolyline(
        [(ox + cover, oy + cover), (ox + bw - cover, oy + cover),
         (ox + bw - cover, oy + bh - cover), (ox + cover, oy + bh - cover)],
        close=True, dxfattribs={"layer": "STIRRUP"},
    )
    _add_dimension_line(msp, (ox, oy), (ox + bw, oy), offset=-10)
    _add_dimension_line(msp, (ox - 5, oy), (ox - 5, oy + bh), offset=-15)
    fp = out / "con_07_beam_detail.dxf"
    doc.saveas(fp)
    return fp


def _con_08_site_plan(out: Path) -> Path:
    """Simple site plan with building footprint."""
    doc = _new_doc("Site Plan")
    msp = doc.modelspace()
    _add_title_block(msp, "SITE PLAN", 420, 297)
    # Property boundary
    msp.add_lwpolyline(
        [(40, 40), (380, 40), (380, 250), (40, 250)],
        close=True, dxfattribs={"layer": "BOUNDARY", "linetype": "DASHDOT"},
    )
    # Building footprint
    msp.add_lwpolyline(
        [(120, 100), (300, 100), (300, 200), (120, 200)],
        close=True, dxfattribs={"layer": "BUILDING"},
    )
    # Driveway
    msp.add_lwpolyline(
        [(180, 40), (240, 40), (240, 100), (180, 100)],
        close=True, dxfattribs={"layer": "PAVING"},
    )
    # Setback lines
    msp.add_lwpolyline(
        [(70, 70), (350, 70), (350, 220), (70, 220)],
        close=True, dxfattribs={"layer": "SETBACK", "linetype": "DASHED"},
    )
    # North arrow
    msp.add_line((370, 260), (370, 280), dxfattribs={"layer": "ANNOTATION"})
    msp.add_text("N", height=5, dxfattribs={"layer": "ANNOTATION", "insert": (367, 282)})
    fp = out / "con_08_site_plan.dxf"
    doc.saveas(fp)
    return fp


def _con_09_window_detail(out: Path) -> Path:
    """Window frame cross-section detail."""
    doc = _new_doc("Window Detail")
    msp = doc.modelspace()
    _add_title_block(msp, "WINDOW FRAME DETAIL", 297, 210)
    ox, oy = 90, 40
    # Wall section
    msp.add_lwpolyline(
        [(ox, oy), (ox + 30, oy), (ox + 30, oy + 140), (ox, oy + 140)],
        close=True, dxfattribs={"layer": "WALLS"},
    )
    # Window opening
    msp.add_lwpolyline(
        [(ox + 30, oy + 30), (ox + 100, oy + 30), (ox + 100, oy + 120), (ox + 30, oy + 120)],
        close=True, dxfattribs={"layer": "WINDOWS"},
    )
    # Frame
    msp.add_lwpolyline(
        [(ox + 30, oy + 30), (ox + 36, oy + 30), (ox + 36, oy + 120), (ox + 30, oy + 120)],
        close=True, dxfattribs={"layer": "FRAME"},
    )
    msp.add_lwpolyline(
        [(ox + 94, oy + 30), (ox + 100, oy + 30), (ox + 100, oy + 120), (ox + 94, oy + 120)],
        close=True, dxfattribs={"layer": "FRAME"},
    )
    # Sill
    msp.add_lwpolyline(
        [(ox + 25, oy + 25), (ox + 105, oy + 25), (ox + 105, oy + 30), (ox + 25, oy + 30)],
        close=True, dxfattribs={"layer": "SILL"},
    )
    # Lintel
    msp.add_lwpolyline(
        [(ox + 25, oy + 120), (ox + 105, oy + 120), (ox + 105, oy + 128), (ox + 25, oy + 128)],
        close=True, dxfattribs={"layer": "LINTEL"},
    )
    # Glass
    msp.add_line((ox + 65, oy + 32), (ox + 65, oy + 118), dxfattribs={"layer": "GLASS", "linetype": "DASHED"})
    fp = out / "con_09_window_detail.dxf"
    doc.saveas(fp)
    return fp


def _con_10_elevation(out: Path) -> Path:
    """Simple building front elevation."""
    doc = _new_doc("Front Elevation")
    msp = doc.modelspace()
    _add_title_block(msp, "FRONT ELEVATION", 420, 297)
    ox, oy, bw, bh = 60, 40, 300, 160
    # Main outline
    msp.add_lwpolyline(
        [(ox, oy), (ox + bw, oy), (ox + bw, oy + bh), (ox, oy + bh)],
        close=True, dxfattribs={"layer": "OUTLINE"},
    )
    # Roof
    msp.add_lwpolyline(
        [(ox - 10, oy + bh), (ox + bw / 2, oy + bh + 60), (ox + bw + 10, oy + bh)],
        close=True, dxfattribs={"layer": "ROOF"},
    )
    # Door
    msp.add_lwpolyline(
        [(ox + 120, oy), (ox + 120, oy + 70), (ox + 170, oy + 70), (ox + 170, oy)],
        close=True, dxfattribs={"layer": "DOORS"},
    )
    # Windows
    for wx in [ox + 30, ox + 210]:
        msp.add_lwpolyline(
            [(wx, oy + 50), (wx, oy + 110), (wx + 60, oy + 110), (wx + 60, oy + 50)],
            close=True, dxfattribs={"layer": "WINDOWS"},
        )
        # Window mullion
        msp.add_line((wx + 30, oy + 50), (wx + 30, oy + 110), dxfattribs={"layer": "WINDOWS"})
    # Ground line
    msp.add_line((40, oy), (380, oy), dxfattribs={"layer": "GROUND"})
    _add_dimension_line(msp, (ox, oy), (ox + bw, oy), offset=-15)
    fp = out / "con_10_elevation.dxf"
    doc.saveas(fp)
    return fp


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

MANUFACTURING_GENERATORS = [
    _mfg_01_shaft, _mfg_02_flange, _mfg_03_bracket, _mfg_04_gasket,
    _mfg_05_gear_profile, _mfg_06_bushing, _mfg_07_keyway,
    _mfg_08_spring_washer, _mfg_09_cam_profile, _mfg_10_mounting_plate,
]

CONSTRUCTION_GENERATORS = [
    _con_01_floor_plan, _con_02_wall_section, _con_03_foundation,
    _con_04_roof_truss, _con_05_staircase, _con_06_column_grid,
    _con_07_beam_detail, _con_08_site_plan, _con_09_window_detail,
    _con_10_elevation,
]


def generate_dataset(data_dir: Path) -> list[Path]:
    """Generate all 20 DXF sample drawings. Returns list of created file paths."""
    mfg_dir = data_dir / "dxf" / "manufacturing"
    con_dir = data_dir / "dxf" / "construction"
    mfg_dir.mkdir(parents=True, exist_ok=True)
    con_dir.mkdir(parents=True, exist_ok=True)

    created: list[Path] = []
    for gen in MANUFACTURING_GENERATORS:
        fp = gen(mfg_dir)
        logger.info("Created: %s", fp)
        created.append(fp)
    for gen in CONSTRUCTION_GENERATORS:
        fp = gen(con_dir)
        logger.info("Created: %s", fp)
        created.append(fp)

    logger.info("Generated %d DXF files total.", len(created))
    return created
