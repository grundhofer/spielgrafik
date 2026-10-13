"""Lage der Figuren im Posenblatt assets/ref/pose_layout.png (für build_badger.py).

Liefert je Figur Mützenmitte (wie build_badger.cap_x), Oberkante, Höhe und den Ursprung der Zelle aus
assets/ref/pose_layout.json (Bodenpunkt der Figur im Blatt).
"""
import json
import pathlib

import numpy as np
from PIL import Image

from hd2dlib import figures, runs

ROOT = pathlib.Path(__file__).resolve().parents[1]


def layout_figures():
    lay = np.asarray(Image.open(ROOT / "assets" / "ref" / "pose_layout.png").convert("RGB")).astype(np.int64)
    m = np.abs(lay - 255).sum(2) > 30
    meta = json.loads((ROOT / "assets" / "ref" / "pose_layout.json").read_text())
    out = []
    for f, c in zip(figures(m), meta["cells"]):
        h = f["bot"] - f["top"] + 1
        xs = []
        for y in range(f["top"], f["top"] + max(3, int(0.08 * h))):
            row = m[y, f["x0"]:f["x1"]]
            if row.any():
                best = max(runs(row, 1), key=lambda r: r[1] - r[0])
                xs.append(f["x0"] + (best[0] + best[1] - 1) / 2)
        out.append({"cap": float(np.mean(xs)), "top": f["top"], "h": h, "origin": c["origin"]})
    return out
