"""Validate binary STL outputs for finite, non-degenerate and closed meshes."""

from __future__ import annotations

import json
import struct
from collections import Counter
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
PRINTABLE = [
    "front-tub.stl",
    "rear-tray.stl",
    "rear-lid.stl",
    "fit-coupon.stl",
    "wall-dock.stl",
]


def read_stl(path: Path) -> np.ndarray:
    data = path.read_bytes()
    if len(data) < 84:
        raise ValueError("file is shorter than a binary STL header")
    count = struct.unpack_from("<I", data, 80)[0]
    if len(data) != 84 + 50 * count:
        raise ValueError(f"bad byte count for {count} triangles")
    tris = np.empty((count, 3, 3), dtype=np.float64)
    for i in range(count):
        values = struct.unpack_from("<12fH", data, 84 + 50 * i)
        tris[i] = np.asarray(values[3:12]).reshape(3, 3)
    return tris


def vertex_key(v):
    # Final printable STLs are emitted by Manifold3D, which reuses exact float32
    # positions for shared vertices. Avoid quantisation merging nearby thin details.
    return tuple(float(x) for x in v)


def validate(path: Path):
    tris = read_stl(path)
    if not np.isfinite(tris).all():
        raise ValueError("non-finite vertex")
    area2 = np.linalg.norm(np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]), axis=1)
    degenerate = int(np.count_nonzero(area2 < 1e-8))
    edges = Counter()
    for tri in tris:
        keys = [vertex_key(v) for v in tri]
        for a, b in ((keys[0], keys[1]), (keys[1], keys[2]), (keys[2], keys[0])):
            edges[tuple(sorted((a, b)))] += 1
    open_edges = sum(1 for count in edges.values() if count == 1)
    nonmanifold_edges = sum(1 for count in edges.values() if count > 2)
    result = {
        "triangles": int(len(tris)),
        "degenerateTriangles": degenerate,
        "openEdges": open_edges,
        "nonManifoldEdges": nonmanifold_edges,
    }
    if degenerate or open_edges or nonmanifold_edges:
        raise ValueError(json.dumps(result))
    return result


def main():
    report = {}
    failures = []
    for name in PRINTABLE:
        try:
            report[name] = validate(OUT / name)
        except Exception as exc:  # keep all part failures in one report
            report[name] = {"error": str(exc)}
            failures.append(name)
    (OUT / "mesh-validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if failures:
        raise SystemExit(f"Mesh validation failed: {', '.join(failures)}")


if __name__ == "__main__":
    main()
