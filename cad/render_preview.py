"""Preview renderer for the v0.8 assembly (Pillow + numpy only)."""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
ASM = ROOT / "output" / "assembly"
OUT = ROOT / "output"

COLORS = {
    "tub": (226, 222, 210), "lid": (205, 210, 214), "display": (170, 172, 178), "display-glass": (18, 22, 26),
    "battery": (214, 186, 92), "bms-pcb": (40, 150, 90), "bms-parts": (30, 30, 30), "header": (28, 28, 30),
    "tray": (150, 185, 215), "magnets": (120, 120, 128),
}
WIRE_COLORS = {"W1": (210, 40, 40), "W2": (25, 25, 25), "W3": (25, 25, 25), "W4": (210, 40, 40)}


def load(path: Path) -> np.ndarray:
    data = path.read_bytes()
    n = struct.unpack_from("<I", data, 80)[0]
    rec = np.frombuffer(data, dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")], count=n, offset=84)
    return rec["v"].astype(np.float64)


def meshes(names, offsets=None, prefix=""):
    offsets = offsets or {}
    items = []
    for name in names:
        path = ASM / f"{prefix}{name}.stl"
        if not path.exists():
            continue
        tris = load(path) + np.asarray(offsets.get(name, (0, 0, 0)))
        base = COLORS.get(name) or WIRE_COLORS.get(name.replace("wire-", ""), (200, 60, 60))
        items.append((tris, base))
    return items


def view_basis(eye, up=(0.0, 1.0, 0.0)):
    depth = np.asarray(eye, float)
    depth /= np.linalg.norm(depth)
    up = np.asarray(up, float)
    right = np.cross(up, depth)
    right /= np.linalg.norm(right)
    up = np.cross(depth, right)
    return np.vstack([right, up, depth])


def render(draw, items, box, eye, title, font, up=(0.0, 1.0, 0.0), note=None, depth_cue=None):
    x0, y0, x1, y1 = box
    rot = view_basis(eye, up)
    allv = np.concatenate([t.reshape(-1, 3) for t, _ in items])
    center = (allv.min(0) + allv.max(0)) / 2
    tr = [((t - center) @ rot.T, c) for t, c in items]
    xy = np.concatenate([t[:, :, :2].reshape(-1, 2) for t, _ in tr])
    mn, mx = xy.min(0), xy.max(0)
    scale = min((x1 - x0 - 60) / (mx[0] - mn[0]), (y1 - y0 - 110) / (mx[1] - mn[1]))
    origin = np.array([(x0 + x1) / 2, (y0 + y1) / 2 + 20])
    tris = np.concatenate([t for t, _ in tr])
    cols = np.concatenate([np.tile(np.asarray(c, float), (len(t), 1)) for t, c in tr])
    nrm = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    ln = np.linalg.norm(nrm, axis=1)
    ok = (ln > 1e-9) & (nrm[:, 2] > 0)
    tris, cols, nrm = tris[ok], cols[ok], nrm[ok] / ln[ok, None]
    light = np.array([-0.35, 0.45, 0.82])
    light /= np.linalg.norm(light)
    inten = 0.55 + 0.45 * np.abs(nrm @ light)
    if depth_cue is None:
        depth_cue = max(abs(e) for e in eye) / np.linalg.norm(eye) > 0.99
    if depth_cue:
        dz = tris[:, :, 2].mean(1)
        inten *= 0.72 + 0.28 * (dz - dz.min()) / max(float(np.ptp(dz)), 1e-6)
    order = np.argsort(tris[:, :, 2].max(1) + tris[:, :, 2].mean(1) * 0.01)
    for i in order:
        poly = tris[i, :, :2].copy()
        poly[:, 1] *= -1
        poly = poly * scale + origin
        c = tuple(np.clip(cols[i] * inten[i], 0, 255).astype(int))
        draw.polygon([tuple(p) for p in poly], fill=c)
    draw.text((x0 + 24, y0 + 16), title, fill=(40, 42, 44), font=font)
    if note:
        draw.text((x0 + 24, y0 + 50), note, fill=(95, 98, 100), font=font_small())


def font_small():
    try:
        return ImageFont.truetype("arial.ttf", 22)
    except OSError:
        return ImageFont.load_default()


def main():
    try:
        font = ImageFont.truetype("arialbd.ttf", 30)
    except OSError:
        font = ImageFont.load_default()
    wires = [f"wire-W{i}" for i in range(1, 5)]
    inside = ["tub", "display", "header", "tray", "battery", "bms-pcb", "bms-parts"] + wires

    img = Image.new("RGB", (3000, 1500), (247, 247, 244))
    dr = ImageDraw.Draw(img)
    render(dr, meshes(["tub", "display-glass"]), (0, 0, 900, 1500), (0, 0, -1), "FRONT", font,
           note="silver housing hidden by 2.5 mm rim")
    render(dr, meshes(inside), (900, 0, 2000, 1500), (0, 0, 1), "REAR, LID OFF", font,
           note="seen from the back: USB-C of the display on the left")
    render(dr, meshes(inside + ["lid", "magnets"], {"lid": (0, 0, 45), "magnets": (0, 0, 45)}),
           (2000, 0, 3000, 1500), (0.55, -0.75, 1.0), "EXPLODED", font, note="lid lifted 45 mm")
    img.resize((1500, 750), Image.Resampling.LANCZOS).save(OUT / "enclosure-preview.png")

    img = Image.new("RGB", (2400, 2400), (247, 247, 244))
    dr = ImageDraw.Draw(img)
    render(dr, meshes(inside), (0, 0, 2400, 2400), (0, 0, 1), "REAR, LID OFF - ASSEMBLY VIEW", font,
           note="tray (blue) on the stock display cover; seen from the back")
    img.resize((1400, 1400), Image.Resampling.LANCZOS).save(OUT / "interior-rear.png")

    sec = inside + ["lid", "magnets"]
    img = Image.new("RGB", (3000, 1500), (247, 247, 244))
    dr = ImageDraw.Draw(img)
    render(dr, meshes(sec, prefix="secA-"), (0, 0, 1500, 1500), (0, 1, 0), "SECTION A - 2x4 header, BAT window",
           font, up=(0, 0, 1), note="front glass at the bottom, lid on top")
    render(dr, meshes(sec, prefix="secB-"), (1500, 0, 3000, 1500), (0, 1, 0), "SECTION B - battery and BMS", font,
           up=(0, 0, 1), note="battery on the stock cover | BMS on VHB, parts toward the lid")
    img.resize((1500, 750), Image.Resampling.LANCZOS).save(OUT / "sections.png")
    print(OUT / "enclosure-preview.png")


if __name__ == "__main__":
    main()
