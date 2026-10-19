"""Generate engineering-drawing.svg (front, rear wiring plan, depth stack, wire table) from build-report.json."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
R = json.loads((ROOT / "output" / "build-report.json").read_text(encoding="utf-8"))
P, L, W, Z = R["parameters"], R["layout"], R["wires"], R["layout"]["z"]
CX, CY, CZ = R["case"]["x"], R["case"]["y"], R["case"]["z"]
S = 4.2

out = []


def add(s):
    out.append(s)


def text(x, y, s, size=15, weight="normal", fill="#222", anchor="start"):
    add(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
        f'text-anchor="{anchor}" font-family="Arial">{s}</text>')


def rect(x, y, w, h, fill="none", stroke="#333", sw=1.5, rx=0, extra=""):
    add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx:.1f}" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="{sw}" {extra}/>')


def dim_h(x0, x1, y, label):
    add(f'<line x1="{x0:.1f}" y1="{y:.1f}" x2="{x1:.1f}" y2="{y:.1f}" stroke="#2a6fb0" stroke-width="1.3" '
        f'marker-start="url(#a)" marker-end="url(#a)"/>')
    text((x0 + x1) / 2, y - 6, label, 14, fill="#2a6fb0", anchor="middle")


def dim_v(x, y0, y1, label):
    add(f'<line x1="{x:.1f}" y1="{y0:.1f}" x2="{x:.1f}" y2="{y1:.1f}" stroke="#2a6fb0" stroke-width="1.3" '
        f'marker-start="url(#a)" marker-end="url(#a)"/>')
    add(f'<text x="{x - 8:.1f}" y="{(y0 + y1) / 2:.1f}" font-size="14" fill="#2a6fb0" text-anchor="middle" '
        f'font-family="Arial" transform="rotate(-90 {x - 8:.1f} {(y0 + y1) / 2:.1f})">{label}</text>')


class View:
    """Design frame is the rear view; the front view mirrors x."""

    def __init__(self, ox, oy, front, s=S):
        self.ox, self.oy, self.front, self.s = ox, oy, front, s

    def p(self, x, y):
        xx = -x if self.front else x
        return self.ox + (xx + CX / 2) * self.s, self.oy + (CY / 2 - y) * self.s

    def box(self, r, **kw):
        (ax, ay), (bx, by) = self.p(r[0], r[3]), self.p(r[1], r[2])
        rect(min(ax, bx), ay, abs(bx - ax), by - ay, **kw)
        return (ax + bx) / 2, (ay + by) / 2


W_PX, H_PX = 2150, 1000
add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W_PX}" height="{H_PX}" viewBox="0 0 {W_PX} {H_PX}">')
add('<defs><marker id="a" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
    '<path d="M0 2 L5 5 L0 8 z" fill="#2a6fb0"/></marker></defs>')
rect(0, 0, W_PX, H_PX, fill="#fafaf7", stroke="none")
text(40, 52, f"ROUTINE CONTROLLER - ENCLOSURE v{R['version']}", 30, "bold")
text(40, 80, f"{CX:g} x {CY:g} x {CZ:g} mm  |  everything behind the display  |  power: LiPo -> BMS -> display BAT (IP5306), "
     f"charging through the display USB-C", 16, fill="#555")

half = P["displayX"] / 2
disp = (-half, half, -half, half)

# ---------------- FRONT
fv = View(60, 170, True)
text(60, 150, "FRONT", 20, "bold")
(ax, ay), (bx, by) = fv.p(CX / 2, CY / 2), fv.p(-CX / 2, -CY / 2)
rect(ax, ay, bx - ax, by - ay, fill="#ece8dc", stroke="#333", sw=2, rx=P["outerR"] * S)
fv.box((-P["windowX"] / 2, P["windowX"] / 2, -P["windowY"] / 2, P["windowY"] / 2), fill="#161b1f", stroke="#111",
       rx=P["windowR"] * S)
fv.box(disp, stroke="#999", sw=1, extra='stroke-dasharray="6 4"')
u = L["usb"]
x0, y0 = fv.p(-CX / 2, u["y"] + P["usbOpenW"] / 2)
rect(x0 - 3, y0, 6, P["usbOpenW"] * S, fill="#333", stroke="none", rx=2)
text(x0 - 10, y0 + P["usbOpenW"] * S / 2 + 5, "USB-C charge", 13, anchor="end", fill="#ddd")
dim_h(ax, bx, by + 40, f"{CX:g}")
dim_v(ax - 22, ay, by, f"{CY:g}")
text((ax + bx) / 2, by + 75, f"window {P['windowX']:g} x {P['windowY']:g}, rim over glass "
     f"{(P['displayX'] - P['windowX']) / 2:g} mm/side; dashed = hidden silver housing", 13, fill="#2a6fb0",
     anchor="middle")

# ---------------- REAR plan with wiring
RS = 8.0
rv = View(520, 130, False, RS)
text(520, 118, "REAR, LID OFF - as seen from the back", 20, "bold")
(ax, ay), (bx, by) = rv.p(-CX / 2, CY / 2), rv.p(CX / 2, -CY / 2)
rect(ax, ay, bx - ax, by - ay, fill="#f1eee6", stroke="#333", sw=2, rx=P["outerR"] * RS)
rv.box(disp, fill="#cfd0d4", stroke="#888")
rv.box(L["batOpen"], fill="#b9895a", stroke="#7a5a3a", sw=1)
bt = L["battery"]
c = rv.box(bt, fill="#e7cf7c", stroke="#9c7d1f")
text(c[0], c[1] - 10, "LiPo 505573", 18, "bold", anchor="middle")
text(c[0], c[1] + 12, "52 x 70 x 5 upright, on 0.3 tape", 13, anchor="middle")
text(c[0], c[1] + 30, "+ tab next to the BMS", 13, "bold", fill="#b00", anchor="middle")
for k, t in L["tabs"].items():
    tw = P["batteryTabW"] / 2
    cc = rv.box((t["x"] - tw, t["x"] + tw, t["y0"], t["y1"]), fill="#c8c8c8", stroke="#777", sw=1)
    text(cc[0], cc[1] + 32, "-" if k == "neg" else "+", 20, "bold", fill="#b00", anchor="middle")
b = L["bms"]
c = rv.box(b, fill="#3aa169", stroke="#1d5a35")
text(c[0], c[1] - 6, "BMS", 16, "bold", "#fff", "middle")
text(c[0], c[1] + 12, "parts up", 11, fill="#fff", anchor="middle")
c = rv.box(L["header"], fill="#222", stroke="#000")
text(c[0], c[1] + 4, "2x4", 11, "bold", "#fff", "middle")
bo = L["batOpen"]
bx_, by_ = rv.p(bo[0], bo[2])
text(bx_ + 4, by_ + 16, "BAT window: MX1.25 plug", 11, anchor="start")
for cx, cy in L["columns"]:
    x, y = rv.p(cx, cy)
    add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{P["columnD"] / 2 * RS:.1f}" fill="#ddd" stroke="#555"/>')
cols = {"red": "#d22", "black": "#111"}
for wr in W:
    pts = wr["path2d"]
    col = cols[wr["color"]]
    poly = " ".join(f"{rv.p(x, y)[0]:.1f},{rv.p(x, y)[1]:.1f}" for x, y in pts)
    add(f'<polyline points="{poly}" fill="none" stroke="{col}" stroke-width="{max(wr["od"] * RS * 0.7, 4):.1f}" '
        f'stroke-linejoin="round" opacity="0.92"/>')
    mid = pts[len(pts) // 2 - 1] if len(pts) > 3 else pts[1]
    mx, my = rv.p(*mid)
    add(f'<rect x="{mx - 15:.1f}" y="{my - 10:.1f}" width="30" height="18" rx="4" fill="#fff" stroke="{col}"/>')
    text(mx, my + 4, wr["id"], 12, "bold", anchor="middle")
for name, (x, y, z) in R["pads"].items():
    X, Y = rv.p(x, y)
    add(f'<circle cx="{X:.1f}" cy="{Y:.1f}" r="3.2" fill="#ffd400" stroke="#333"/>')
    if name.startswith("BMS"):
        lab = name.split(" ", 1)[1]
        text(X, Y + (18 if lab != "B-" else -8), lab, 11, "bold", anchor="middle")
dim_h(ax, bx, by + 30, f"{CX:g}")
text((ax + bx) / 2, by + 60, "USB-C of the display is on the LEFT in this view", 13, fill="#555", anchor="middle")

# ---------------- stack + wire table
x0 = 1290
yy = 130
text(x0, yy - 12, "DEPTH STACK (mm from the front face)", 20, "bold")
rows = [
    ("front skin / window rim", 0, P["frontSkin"]),
    ("display in silver housing + stock cover", Z["disp0"], Z["cover"]),
    ("printed tray on the stock cover", Z["cover"], Z["tray1"]),
    ("battery on 0.3 tape", Z["bat0"], Z["bat1"]),
    ("BMS: VHB 0.8 + PCB + parts", Z["cover"], Z["bmsTop"]),
    ("2x4 header (sticks out of the cover)", Z["cover"], Z["headerTop"]),
    ("foam 1.0 -> 0.6", Z["bat1"], Z["lid0"]),
    ("lid with magnets (0.45 skin)", Z["lid0"], CZ),
]
for i, (name, a, bb) in enumerate(rows):
    y = yy + 22 * i + 20
    text(x0, y, name, 14)
    text(x0 + 420, y, f"{a:.1f} - {bb:.1f}", 14, "bold", anchor="end")

ty = yy + 230
text(x0, ty, "WIRE CUT LIST", 20, "bold")
xs = [x0, x0 + 50, x0 + 330, x0 + 420]
for i, h in enumerate(("ID", "AWG  from -> to", "route", "cut")):
    text(xs[i], ty + 30, h, 14, "bold", anchor="end" if i >= 2 else "start")
for j, wr in enumerate(W):
    y = ty + 54 + j * 24
    add(f'<rect x="{xs[0] - 14:.1f}" y="{y - 11:.1f}" width="8" height="12" fill="{cols[wr["color"]]}"/>')
    text(xs[0], y, wr["id"], 14, "bold")
    text(xs[1], y, f'{wr["awg"]}   {wr["a"]} -> {wr["b"]}', 13)
    text(xs[2], y, f'{wr["routeMm"]:.0f}', 14, anchor="end")
    text(xs[3], y, f'{wr["cutMm"]}', 14, "bold", anchor="end")
ny = ty + 54 + len(W) * 24 + 6
text(xs[0], ny, "cut = length of the existing lead measured from the tab / plug:", 12, fill="#555")
text(xs[0], ny + 17, "route + 4 mm strip at the BMS + 5 mm laying allowance (+8 mm plug rise)", 12, fill="#555")

notes = [
    "Every part is held rigidly:",
    "- display: window rim in front, 4 corner columns + foam at the back",
    "- tray: header hole + columns locate it, 4 lid posts clamp it",
    "- battery: tray rib on 4 sides, tape below, foam from the lid",
    "- BMS: VHB on the stock cover, nest walls, foam boss on the lid",
    "- wires: snap channels with 0.25 mm lips sized per stack",
    "- lid: 4 x M2 x 8 countersunk self-tapping screws into columns",
    "",
    "UPS board and the panel USB-C socket are no longer used.",
]
for i, n in enumerate(notes):
    text(x0, ny + 60 + i * 21, n, 14, "bold" if i == 0 else "normal")
add("</svg>")
(ROOT / "engineering-drawing.svg").write_text("\n".join(out), encoding="utf-8")
print(ROOT / "engineering-drawing.svg")
