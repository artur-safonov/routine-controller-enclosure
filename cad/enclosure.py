"""Routine controller enclosure v0.8 - every module lives behind the display.

Frame: REAR view with the origin at the display centre. x points right and y up
as seen from the back, z is depth from the front face (0) toward the lid. The
frame is right-handed, so STL files are exported unchanged. Seen from the front,
left and right swap: the display USB-C port is on the left side in this frame.

Layout inputs use rear-view millimetres from the lower-left display corner,
as measured on a real board, and are converted with rc()/rr().
"""

from __future__ import annotations

import json
import math
import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
ASM = OUT / "assembly"
import manifold3d as m  # noqa: E402

m.set_circular_segments(48)

P = {
    # --- measured on a real board, mm ---
    "displayX": 85.0, "displayY": 85.0, "displayZ": 10.0,     # silver housing + stock rear cover
    "headerX0": 62.0, "headerX1": 68.0, "headerY0": 20.0, "headerY1": 35.0, "headerH": 5.0,
    "usbY": 35.0, "usbZ": 7.5,          # display USB-C: 50 mm from the top edge, 7.5 mm from the glass
    "batteryX": 52.0, "batteryY": 70.0, "batteryZ": 5.0,      # pouch without tabs, turned upright
    "bmsX": 17.0, "bmsY": 30.0, "bmsZ": 4.0,

    # --- read from the board photos (rear view); verify with the tray print ---
    "batOpenX0": 75.0, "batOpenY0": 21.5, "batOpenY1": 32.5,  # stock-cover window over the BAT (MX1.25) socket
    "plugPlusY": 26.0, "plugMinusY": 29.0,                    # silkscreen: B+ is the lower pin in rear view
    "coverScrewBR": (78.0, 16.0), "coverScrewHole": 5.2,
    "batteryTabL": 7.0, "batteryTabW": 5.0, "batteryTabInset": 9.0,
    "bmsPcbT": 1.0,

    # --- placement behind the display (rear view, from the lower-left corner) ---
    "batteryX0": 4.5, "batteryY0": 4.5, "bmsX0": 62.5, "bmsY0": 44.0,

    # --- wires: battery leads stay 18 AWG, the MX1.25 pigtail is 28 AWG ---
    "wireOD18": 2.2, "wireOD28": 1.0,

    # --- enclosure ---
    "fit": 0.3, "wall": 2.0, "frontSkin": 1.4, "lidT": 2.8, "outerR": 4.0, "innerR": 1.8,
    "windowX": 80.0, "windowY": 80.0, "windowR": 2.5, "windowChamfer": 0.6,
    "usbOpenW": 12.6, "usbOpenH": 7.0,
    "trayT": 0.8, "trayGap": 0.15, "ribW": 1.2, "ribH": 2.6, "batteryFit": 0.4, "bmsFit": 0.3, "headerFit": 0.4,
    "tape": 0.3, "vhb": 0.8, "foam": 0.6,
    "columnD": 5.0, "columnFoam": 0.6, "lipW": 1.2, "lipH": 1.2,
    "screwPilotD": 1.8, "screwClearD": 2.4, "screwHeadD": 4.4,
    "magnetX": 30.0, "magnetY": 10.0, "magnetT": 2.0, "magnetClearance": 0.18, "magnetSkin": 0.45,
    "dockRailY": 16.0, "dockZ": 3.2, "washerD": 9.4, "washerT": 1.2, "dockFrontSkin": 0.45,
    "guideWall": 1.2, "guideLip": 0.25, "guideLipH": 0.6,
    "stripAllowance": 4.0, "layAllowance": 5.0, "plugRise": 8.0,
}

H = P["displayX"] / 2


def rc(x, y):
    return (x - H, y - H)


def rr(x0, x1, y0, y1):
    return (x0 - H, x1 - H, y0 - H, y1 - H)


# ----------------------------------------------------------------- helpers
def U(items):
    items = [i for i in items if i is not None]
    return items[0] if len(items) == 1 else m.Manifold.batch_boolean(items, m.OpType.Add)


def CU(items):
    items = [i for i in items if i is not None]
    return items[0] if len(items) == 1 else m.CrossSection.batch_boolean(items, m.OpType.Add)


def rect(x0, x1, y0, y1):
    return m.CrossSection.square((x1 - x0, y1 - y0)).translate((x0, y0))


def rrect(cx, cy, sx, sy, r):
    r = min(r, sx / 2 - 1e-3, sy / 2 - 1e-3)
    return m.CrossSection.square((sx - 2 * r, sy - 2 * r), center=True).offset(
        r, m.JoinType.Round, 2.0, 64).translate((cx, cy))


def circle(cx, cy, r):
    return m.CrossSection.circle(r, 48).translate((cx, cy))


def prism(cs, z0, z1):
    return cs.extrude(z1 - z0).translate((0, 0, z0))


def box(x0, x1, y0, y1, z0, z1):
    return m.Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def rbox(r, z0, z1):
    return box(r[0], r[1], r[2], r[3], z0, z1)


def cbox(cx, cy, sx, sy, z0, z1):
    return box(cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, z0, z1)


def cyl(cx, cy, d, z0, z1, d_top=None):
    return m.Manifold.cylinder(z1 - z0, d / 2, (d_top if d_top else d) / 2, 48).translate((cx, cy, z0))


def grow(r, d):
    return (r[0] - d, r[1] + d, r[2] - d, r[3] + d)


def ivol(a, b):
    return (a ^ b).volume()


# ----------------------------------------------------------- depth stack
fs = P["frontSkin"]
Z = {"disp0": fs, "cover": fs + P["displayZ"]}
Z["tray1"] = Z["cover"] + P["trayT"]
Z["bat0"] = Z["cover"] + P["tape"]
Z["bat1"] = Z["bat0"] + P["batteryZ"]
Z["tab"] = Z["bat0"] + P["batteryZ"] / 2
Z["lid0"] = Z["bat1"] + P["foam"]
Z["case"] = Z["lid0"] + P["lidT"]
Z["bmsPcb0"] = Z["cover"] + P["vhb"]
Z["bmsPcb1"] = Z["bmsPcb0"] + P["bmsPcbT"]
Z["bmsTop"] = Z["bmsPcb0"] + P["bmsZ"]
Z["headerTop"] = Z["cover"] + P["headerH"]
Z["column0"] = Z["cover"] + P["columnFoam"]


# ------------------------------------------------------------------ layout
def layout():
    IN = H + P["fit"]
    L = {"inner": IN, "outer": IN + P["wall"], "caseXY": 2 * (IN + P["wall"]), "z": Z}
    bx0, by0 = P["batteryX0"], P["batteryY0"]
    L["battery"] = rr(bx0, bx0 + P["batteryX"], by0, by0 + P["batteryY"])
    ty0 = by0 + P["batteryY"]
    L["tabs"] = {
        "neg": dict(x=bx0 + P["batteryTabInset"] - H, y0=ty0 - H, y1=ty0 + P["batteryTabL"] - H),
        "pos": dict(x=bx0 + P["batteryX"] - P["batteryTabInset"] - H, y0=ty0 - H, y1=ty0 + P["batteryTabL"] - H),
    }
    L["bms"] = rr(P["bmsX0"], P["bmsX0"] + P["bmsX"], P["bmsY0"], P["bmsY0"] + P["bmsY"])
    L["header"] = rr(P["headerX0"], P["headerX1"], P["headerY0"], P["headerY1"])
    L["batOpen"] = rr(P["batOpenX0"], 2 * H + 1.0, P["batOpenY0"], P["batOpenY1"])
    L["coverScrew"] = rc(*P["coverScrewBR"])
    c = IN - 2.8
    L["columns"] = [(-c, -c), (c, -c), (-c, c), (c, c)]
    L["magnets"] = [(-19.0, -24.0), (19.0, -24.0), (-19.0, 24.0), (19.0, 24.0)]
    # lid posts press the tray: two on the floor, two on the battery rib (via 1 mm foam)
    rib_c = P["batteryX0"] - P["batteryFit"] - P["ribW"] / 2
    z_floor, z_rib = Z["tray1"] + P["foam"], Z["cover"] + P["ribH"] + P["foam"]
    L["posts"] = [(*rc(70.0, 8.0), z_floor, 2.4, 2.4), (*rc(65.5, 79.0), z_floor, 2.4, 2.4),
                  (*rc(30.0, rib_c), z_rib, 5.0, 1.0), (*rc(rib_c, 42.0), z_rib, 1.0, 5.0)]
    L["bmsBoss"] = rc(71.0, 51.5)
    L["usb"] = dict(y=P["usbY"] - H, z=fs + P["usbZ"])
    return L


L = layout()
IN, OUTER = L["inner"], L["outer"]


def tray_outline():
    s = 2 * (IN - P["trayGap"])
    return rrect(0, 0, s, s, P["innerR"] - P["trayGap"])


def column_cs(grow_by=0.0):
    r = P["columnD"] / 2
    out = []
    for cx, cy in L["columns"]:
        sx, sy = math.copysign(1, cx), math.copysign(1, cy)
        wx, wy = sx * (IN + 0.01), sy * (IN + 0.01)
        out += [circle(cx, cy, r),
                rect(min(cx, wx), max(cx, wx), cy - r, cy + r),
                rect(cx - r, cx + r, min(cy, wy), max(cy, wy))]
    cs = CU(out)
    return cs.offset(grow_by, m.JoinType.Round, 2.0, 48) if grow_by else cs


# ------------------------------------------------------------ wiring model
def pads():
    b, tb = L["bms"], L["tabs"]
    zp = Z["bmsPcb1"] + 0.7
    zplug = Z["cover"] + 0.5
    solder_y = tb["pos"]["y1"] - 1.5
    return {
        # BMS component side up, P-end toward the header: P-, B+, P+ left to right; B- at the far end
        "BMS P-": (b[0] + 1.7, b[2] + 1.5, zp), "BMS B+": (b[0] + 6.1, b[2] + 1.5, zp),
        "BMS P+": (b[0] + 11.7, b[2] + 1.5, zp), "BMS B-": (b[0] + 8.5, b[3] - 1.5, zp),
        "BAT +": (tb["pos"]["x"], solder_y, Z["tab"]), "BAT -": (tb["neg"]["x"], solder_y, Z["tab"]),
        "PLUG B+": (*rc(83.9, P["plugPlusY"]), zplug), "PLUG B-": (*rc(82.3, P["plugMinusY"]), zplug),
    }


def wires():
    p = pads()
    fl = Z["tray1"]
    z_hump = fl + P["wireOD28"] + P["wireOD18"] / 2
    W = [
        dict(id="W1", awg=18, net="CELL+", color="red", a="BAT +", b="BMS B+", level=1, factoryLead=True,
             path=[rc(59.2, 77.15), rc(59.2, 38.3), rc(65.0, 38.3), (*rc(68.6, 38.3), z_hump),
                   (*rc(68.6, 43.0), z_hump)],
             raise_=[(rr(64.4, 69.8, 37.1, 44.1), P["wireOD28"])]),
        dict(id="W2", awg=18, net="CELL-", color="black", a="BAT -", b="BMS B-", level=0, factoryLead=True,
             path=[rc(13.5, 83.2), rc(71.0, 83.2)]),
        dict(id="W3", awg=28, net="PACK-", color="black", a="PLUG B-", b="BMS P-", level=0, factoryLead=True,
             plug=True, path=[rc(82.3, 41.4), rc(64.2, 41.4)]),
        dict(id="W4", awg=28, net="PACK+", color="red", a="PLUG B+", b="BMS P+", level=0, factoryLead=True,
             plug=True, path=[rc(83.9, 42.9), rc(74.2, 42.9)]),
    ]
    # the tab-side leads first run along their tab before entering the channel
    W[0]["path"].insert(0, rc(47.5, 77.15))
    for wr in W:
        a, b = p[wr["a"]], p[wr["b"]]
        wr["path"] = [a[:2]] + wr["path"] + [b[:2]] if len(wr["path"][0]) == 2 else [a[:2]] + wr["path"] + [b[:2]]
        wr["od"] = P[f"wireOD{wr['awg']}"]
        w = wr["od"] + 0.1
        xy = [q[:2] for q in wr["path"]]
        wr["rects"] = [(min(x0, x1) - w / 2, max(x0, x1) + w / 2, min(y0, y1) - w / 2, max(y0, y1) + w / 2)
                       for (x0, y0), (x1, y1) in zip(xy, xy[1:])]

    def under(wr, x, y):
        if wr["level"] == 0:
            return 0.0
        for other in W:
            if other is wr or other["level"] != 0:
                continue
            if any(a - 1e-6 <= x <= b + 1e-6 and c - 1e-6 <= y <= d + 1e-6 for a, b, c, d in other["rects"]):
                return other["od"]
        return 0.0

    for wr in W:
        od = wr["od"]
        pts3 = [p[wr["a"]]]
        for q in wr["path"][1:-1]:
            pts3.append(q if len(q) == 3 else (q[0], q[1], fl + od / 2 + under(wr, *q)))
        pts3.append(p[wr["b"]])
        wr["points3d"] = [tuple(round(v, 3) for v in q) for q in pts3]
        route = sum(math.dist(pts3[i], pts3[i + 1]) for i in range(len(pts3) - 1))
        if wr.get("plug"):
            route += P["plugRise"]
        wr["routeMm"] = round(route, 1)
        ends = 1 if wr.get("factoryLead") else 2
        wr["cutMm"] = int(math.ceil((route + ends * P["stripAllowance"] + P["layAllowance"]) / 5.0) * 5)
    return W


WIRES = wires()


def wire_regions():
    return {wr["id"]: CU([rect(*r) for r in wr["rects"]]) for wr in WIRES}


# ------------------------------------------------------------ tray (spacer)
def cutouts():
    bf = P["batteryFit"]
    tb = L["tabs"]
    tw = P["batteryTabW"] / 2 + 0.3
    return {
        "battery": grow(L["battery"], bf),
        "bms": grow(L["bms"], P["bmsFit"]),
        "header": grow(L["header"], P["headerFit"]),
        "batOpen": L["batOpen"],
        "tabs": [(t["x"] - tw, t["x"] + tw, t["y0"] - bf, t["y1"] + 0.3) for t in tb.values()],
    }


def keepout2d():
    c = cutouts()
    return CU([rect(*c["battery"]), rect(*c["bms"]), rect(*c["header"]), rect(*c["batOpen"])]
              + [rect(*t) for t in c["tabs"]] + [column_cs(0.3)])


def guides(ko):
    t, lip_h, fl = P["guideWall"], P["guideLipH"], Z["tray1"]
    regs = wire_regions()
    ids = list(regs)
    od = {wr["id"]: wr["od"] for wr in WIRES}
    s2 = CU(list(regs.values()))
    zones = []
    for wr in WIRES:
        i = wr["id"]
        own = regs[i] - CU([regs[j] for j in ids if j != i])
        for rr_, extra in wr.get("raise_", []):
            rcs = rect(*rr_)
            zones.append((own ^ rcs, od[i] + extra))
            own = own - rcs
        zones.append((own, od[i]))
        for j in ids:
            if j > i:
                ov = regs[i] ^ regs[j]
                if ov.area() > 1e-3:
                    zones.append((ov, od[i] + od[j]))
    inner = tray_outline()
    away = column_cs(0.8)
    walls2d = (s2.offset(t, m.JoinType.Miter, 2.0) - s2 - ko - away) ^ inner
    lips2d = (s2 - s2.offset(-P["guideLip"], m.JoinType.Miter, 2.0) - ko - away) ^ inner
    solids, clears, taken = [], [], None
    for h in sorted({round(hh, 3) for _, hh in zones}, reverse=True):
        zone = CU([c for c, hh in zones if abs(hh - h) < 1e-3 and c.area() > 1e-3])
        zo = zone.offset(t + 0.05, m.JoinType.Miter, 2.0)
        if taken is not None:
            zo = zo - taken
        top = fl + h + 0.2 + lip_h
        solids += [prism(walls2d ^ zo, fl, top), prism(lips2d ^ zo, top - lip_h, top)]
        clears.append(prism((s2 ^ zo) - ko, fl, top - lip_h - 0.001))
        taken = zo if taken is None else taken + zo
    return U(solids), U(clears)


def rear_tray():
    zc, zt = Z["cover"], Z["tray1"]
    c = cutouts()
    outline = tray_outline()
    holes = CU([rect(*c["battery"]), rect(*c["bms"]), rect(*c["header"]), rect(*c["batOpen"]),
                circle(*L["coverScrew"], P["coverScrewHole"] / 2), column_cs(0.3)])
    floor = prism(outline - holes, zc, zt)

    rw, rtop = P["ribW"], zc + P["ribH"]
    bat = rect(*c["battery"])
    away = column_cs(0.8)
    ring = (bat.offset(rw, m.JoinType.Miter, 2.0) - bat - CU([rect(*t) for t in c["tabs"]]) - away) ^ outline
    b = c["bms"]
    nest = CU([rect(b[0] - rw, b[0], b[2], b[3] + rw), rect(b[1], b[1] + rw, b[2], b[3] + rw),
               rect(b[0] - rw, b[1] + rw, b[3], b[3] + rw)]) ^ outline - away
    walls, clears = guides(keepout2d())
    tray = U([floor, prism(ring, zt, rtop), prism(nest, zt, rtop), walls])
    tray -= clears
    tray -= prism(column_cs(0.3), zc - 1, Z["lid0"])
    return tray


# ------------------------------------------------------------------- tub
def front_tub():
    top = Z["lid0"]
    shell = prism(rrect(0, 0, 2 * OUTER, 2 * OUTER, P["outerR"]), 0, top) - prism(
        rrect(0, 0, 2 * IN, 2 * IN, P["innerR"]), fs, top + 1)
    wx, wy, wr_, ch = P["windowX"], P["windowY"], P["windowR"], P["windowChamfer"]
    window = U([prism(rrect(0, 0, wx, wy, wr_), -1, fs + 1),
                m.Manifold.batch_hull([prism(rrect(0, 0, wx + 2 * ch, wy + 2 * ch, wr_ + ch), -0.5, 0.0),
                                       prism(rrect(0, 0, wx, wy, wr_), ch - 0.001, ch)])])
    tub = shell - window
    tub = U([tub, prism(column_cs() ^ rrect(0, 0, 2 * IN + 0.02, 2 * IN + 0.02, P["innerR"]),
                        Z["column0"], top)])
    u = L["usb"]
    tub -= prism(rrect(0, 0, P["usbOpenW"], P["usbOpenH"], P["usbOpenH"] / 2 - 0.01), 0, 10).rotate(
        (0, -90, 0)).translate((-IN + 0.5, u["y"], u["z"]))
    for cx, cy in L["columns"]:
        tub -= cyl(cx, cy, P["screwPilotD"], Z["column0"] + 0.8, top + 1)
    return tub


# ------------------------------------------------------------------- lid
def rear_lid():
    zl0, cz = Z["lid0"], Z["case"]
    lid = prism(rrect(0, 0, 2 * OUTER, 2 * OUTER, P["outerR"]), zl0, cz)
    lip_o = rrect(0, 0, 2 * (IN - 0.2), 2 * (IN - 0.2), P["innerR"] - 0.2)
    lip = (lip_o - lip_o.offset(-P["lipW"], m.JoinType.Round, 2.0, 48)) - column_cs(0.3)
    add = [prism(lip, zl0 - P["lipH"], zl0 + 0.01)]
    add.append(cbox(*L["bmsBoss"], 10, 9, Z["bmsTop"] + P["foam"], zl0 + 0.01))
    for px, py, pz, sx, sy in L["posts"]:
        add.append(cbox(px, py, sx, sy, pz, zl0 + 0.01))
    lid = U([lid] + add)
    mc = P["magnetClearance"]
    for mx, my in L["magnets"]:
        lid -= cbox(mx, my, P["magnetX"] + 2 * mc, P["magnetY"] + 2 * mc, zl0 - 0.01, cz - P["magnetSkin"])
    for sx, sy in L["columns"]:
        lid -= cyl(sx, sy, P["screwClearD"], zl0 - 2, cz + 1)
        lid -= cyl(sx, sy, P["screwClearD"], cz - 1.0, cz + 0.01, P["screwHeadD"])
    return lid


# --------------------------------------------------------- other printables
def fit_coupon():
    """Front skin, window and a 3 mm pocket: checks that the silver housing is hidden."""
    f, dx = P["fit"], P["displayX"]
    ox = dx + 2 * f + 2.4
    c = prism(rrect(0, 0, ox, ox, 3.0), 0, fs + 3.0) - prism(rrect(0, 0, dx + 2 * f, dx + 2 * f, P["innerR"]), fs, 99)
    c -= prism(rrect(0, 0, P["windowX"], P["windowY"], P["windowR"]), -1, 99)
    u = L["usb"]
    c -= box(-ox, -dx / 2, u["y"] - P["usbOpenW"] / 2, u["y"] + P["usbOpenW"] / 2, fs, 99)
    return c


def wall_dock():
    ys = sorted({round(my, 3) for _, my in L["magnets"]})
    dock = U([prism(rrect(0, y, L["caseXY"], P["dockRailY"], 4.0), 0, P["dockZ"]) for y in ys])
    ph = P["washerT"] + 0.25
    for mx, my in L["magnets"]:
        dock -= cyl(mx, my, P["washerD"], P["dockFrontSkin"], P["dockFrontSkin"] + ph)
    for y in ys:
        dock -= prism(rrect(0, y, 72, 12, 2.5), P["dockZ"] - 0.65, P["dockZ"] + 1)
    return dock


# ----------------------------------------------------- reference components
def component_models():
    comp = {}
    comp["display"] = prism(rrect(0, 0, P["displayX"], P["displayY"], 1.5), Z["disp0"], Z["cover"])
    comp["display-glass"] = prism(rrect(0, 0, P["displayX"] - 2, P["displayY"] - 2, 1.0), Z["disp0"] - 0.02,
                                  Z["disp0"] + 0.3)
    comp["header"] = rbox(L["header"], Z["cover"], Z["headerTop"])
    bt = L["battery"]
    tw = P["batteryTabW"] / 2
    comp["battery"] = U([prism(rrect((bt[0] + bt[1]) / 2, (bt[2] + bt[3]) / 2, P["batteryX"], P["batteryY"], 1.5),
                               Z["bat0"], Z["bat1"])]
                        + [box(t["x"] - tw, t["x"] + tw, t["y0"] - 0.5, t["y1"], Z["tab"] - 0.1, Z["tab"] + 0.1)
                           for t in L["tabs"].values()])
    b = L["bms"]
    comp["bms-pcb"] = rbox(b, Z["bmsPcb0"], Z["bmsPcb1"])
    comp["bms-parts"] = box(b[0] + 2.5, b[1] - 2.5, b[2] + 4.0, b[3] - 4.0, Z["bmsPcb1"], Z["bmsTop"])
    zm1 = Z["case"] - P["magnetSkin"]
    comp["magnets"] = U([cbox(mx, my, P["magnetX"], P["magnetY"], zm1 - P["magnetT"], zm1) for mx, my in L["magnets"]])
    return comp


def wire_models(shrink=0.0, floor_only=False):
    out = {}
    for wr in WIRES:
        od = wr["od"] - shrink
        pts = wr["points3d"][1:-1] if floor_only else wr["points3d"]
        segs = [m.Manifold.batch_hull([m.Manifold.cube((od, od, od), center=True).translate(a),
                                       m.Manifold.cube((od, od, od), center=True).translate(c)])
                for a, c in zip(pts, pts[1:])]
        out[wr["id"]] = U(segs)
    return out


# ------------------------------------------------------------------ export
def write_stl(path: Path, solid):
    if solid.status() != m.Error.NoError:
        raise ValueError(f"{path.name}: Manifold status {solid.status()}")
    mesh = solid.to_mesh()
    v = np.asarray(mesh.vert_properties[:, :3], dtype=np.float32)
    f = np.asarray(mesh.tri_verts, dtype=np.uint32)
    tri = v[f]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    n = np.divide(n, ln, out=np.zeros_like(n), where=ln > 0)
    rec = np.zeros(len(f), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    rec["n"], rec["v"] = n, tri
    with path.open("wb") as fh:
        fh.write(b"Routine controller v0.8".ljust(80, b"\0"))
        fh.write(struct.pack("<I", len(f)))
        fh.write(rec.tobytes())
    return {"triangles": int(len(f)), "volumeMm3": round(float(solid.volume()), 1)}


def export_sections(solids):
    """A: through the 2x4 header and the BAT window; B: through the battery and the BMS."""
    cuts = {"secA": rc(0, 27.0)[1], "secB": rc(0, 60.0)[1]}
    for tag, y0 in cuts.items():
        for name, s in solids.items():
            c = s.trim_by_plane((0, -1, 0), -y0)
            path = ASM / f"{tag}-{name}.stl"
            if not c.is_empty():
                write_stl(path, c)


def main():
    OUT.mkdir(exist_ok=True)
    ASM.mkdir(exist_ok=True)
    for old in ASM.glob("*.stl"):
        old.unlink()
    for stale in ["charge-port-coupon.stl", "front-tub.stl", "rear-lid.stl", "rear-tray.stl"]:
        (OUT / stale).unlink(missing_ok=True)

    tub, tray, lid = front_tub(), rear_tray(), rear_lid()
    comp = component_models()
    wm = wire_models()

    checks = {}
    solids = {k: v for k, v in comp.items() if k not in ("display-glass", "magnets")}
    parts = {"tub": tub, "tray": tray, "lid": lid}
    for pn, ps in parts.items():
        for cn, cs in solids.items():
            checks[f"{pn} x {cn}"] = round(ivol(ps, cs), 3)
    checks["tub x tray"] = round(ivol(tub, tray), 3)
    checks["tub x lid"] = round(ivol(tub, lid), 3)
    checks["tray x lid"] = round(ivol(tray, lid), 3)
    checks["lid x magnets"] = round(ivol(lid, comp["magnets"]), 3)
    names = list(solids)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if {names[i], names[j]} <= {"bms-pcb", "bms-parts"}:
                continue
            checks[f"{names[i]} x {names[j]}"] = round(ivol(solids[names[i]], solids[names[j]]), 3)
    thin_floor = wire_models(shrink=0.1, floor_only=True)
    thin_full = wire_models(shrink=0.1)
    for wid in thin_floor:
        checks[f"wire {wid} (in channel) x tray"] = round(ivol(thin_floor[wid], tray), 3)
        checks[f"wire {wid} x lid"] = round(ivol(thin_full[wid], lid), 3)
        checks[f"wire {wid} x tub"] = round(ivol(thin_full[wid], tub), 3)
    failures = {k: v for k, v in checks.items()
                if v > (0.15 if k.startswith("wire ") and "(in channel)" in k else 0.05)}

    bt = L["battery"]
    col_gap = min(math.dist((cx, cy), (min(max(cx, bt[0]), bt[1]), min(max(cy, bt[2]), bt[3])))
                  for cx, cy in L["columns"]) - P["columnD"] / 2
    clear = {
        "batteryTopToLid": round(Z["lid0"] - Z["bat1"], 2),
        "bmsTopToLid": round(Z["lid0"] - Z["bmsTop"], 2),
        "headerTopToLid": round(Z["lid0"] - Z["headerTop"], 2),
        "batteryToHeader": round(L["header"][0] - bt[1], 2),
        "batteryToColumn": round(col_gap, 2),
        "batteryToBms": round(L["bms"][0] - bt[1], 2),
        "windowOverlapOnHousingPerSide": round((P["displayX"] - P["windowX"]) / 2, 2),
        "tallestWireToLid": round(Z["lid0"] - max(max(q[2] for q in wr["points3d"]) + wr["od"] / 2 for wr in WIRES), 2),
    }
    minimums = {"batteryTopToLid": 0.5, "bmsTopToLid": 0.8, "headerTopToLid": 0.5, "batteryToColumn": 0.2,
                "windowOverlapOnHousingPerSide": 1.5, "tallestWireToLid": 1.0}
    for k, v in minimums.items():
        if clear[k] < v:
            failures[k] = clear[k]

    printables = {
        "front-tub.stl": tub,
        "rear-tray.stl": tray,
        "rear-lid.stl": lid.rotate((180, 0, 0)),
        "fit-coupon.stl": fit_coupon(),
        "wall-dock.stl": wall_dock(),
    }
    info = {}
    for name, solid in printables.items():
        solid = solid.simplify(0.002)
        bb = solid.bounding_box()
        solid = solid.translate((-bb[0], -bb[1], -bb[2]))
        info[name] = write_stl(OUT / name, solid)
        info[name]["size"] = [round(float(bb[3] - bb[0]), 2), round(float(bb[4] - bb[1]), 2),
                              round(float(bb[5] - bb[2]), 2)]
        info[name]["massPETG_g_solid"] = round(info[name]["volumeMm3"] * 1.27e-3, 1)

    asm = {"tub": tub, "tray": tray, "lid": lid} | comp | {f"wire-{k}": v for k, v in wm.items()}
    for name, solid in asm.items():
        write_stl(ASM / f"{name}.stl", solid)
    export_sections({k: v for k, v in asm.items() if k != "display-glass"})
    write_stl(OUT / "assembly-preview.stl", m.Manifold.compose(list(asm.values())))

    report = {
        "version": "0.8",
        "parameters": {k: (list(v) if isinstance(v, tuple) else v) for k, v in P.items()},
        "case": {"x": L["caseXY"], "y": L["caseXY"], "z": round(Z["case"], 2)},
        "layout": L,
        "pads": {k: [round(c, 2) for c in v] for k, v in pads().items()},
        "wires": [{k: v for k, v in wr.items() if k not in ("path", "rects", "raise_")}
                  | {"path2d": [q[:2] for q in wr["path"]]} for wr in WIRES],
        "clearancesMm": clear,
        "collisionMm3": checks,
        "failures": failures,
        "printables": info,
    }
    (OUT / "build-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"case": report["case"], "clearancesMm": clear, "failures": failures,
                      "wires": [(w["id"], w["awg"], w["a"], w["b"], w["routeMm"], w["cutMm"]) for w in WIRES],
                      "printables": {k: v["size"] for k, v in info.items()}}, indent=1, ensure_ascii=False))
    if failures:
        raise SystemExit("CAD checks failed")


if __name__ == "__main__":
    main()
