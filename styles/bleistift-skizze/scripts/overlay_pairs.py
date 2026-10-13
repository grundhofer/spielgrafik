#!/usr/bin/env python3
"""Prüfbild für die Vorschubtabelle: je Bildwechsel die unteren 70 Zeilen beider Laufbilder übereinander
(Rot = Bild i, Cyan = Bild i+1, Schwarz = beide), Bild i+1 um den Vorschub aus assets/walk_advance.json
verschoben (Figuren am Hüllrechteck ausgerichtet, Sohle auf gemeinsamer Zeile). 3-fach vergrößert.

    .venv/bin/python styles/bleistift-skizze/scripts/overlay_pairs.py out.png [dx0 dx1 ...]
"""
import json, pathlib, sys
import numpy as np
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[1]
cells = json.loads((ROOT / "assets/sheet_cells.json").read_text())
A = np.asarray(Image.open(ROOT / "assets/raw/walk.png").convert("RGBA"))[..., 3] > 100
A = np.pad(A, ((0, 0), (100, 400)))
order = json.loads((ROOT / "assets/walk_advance.json").read_text())
names = order["frames"]
adv = [float(v) for v in (sys.argv[2:] or order["advance"])]
by = {c["name"]: c for c in cells}
H, W, K = 70, 300, 3


def band(c, shift):
    x0, sy = c["box"][0] + 100 - 40, c["sole_y"]
    return np.roll(A[sy - H + 1:sy + 1, x0:x0 + W], int(round(shift)), 1)


rows = []
for i in range(len(names)):
    a, b = by[names[i]], by[names[(i + 1) % len(names)]]
    ba, bb = band(a, 0), band(b, adv[i])
    img = np.full((H, W, 3), 255, np.uint8)
    img[ba & ~bb] = (230, 40, 40)
    img[bb & ~ba] = (40, 190, 230)
    img[ba & bb] = (30, 30, 30)
    im = Image.fromarray(img).resize((W * K, H * K), Image.NEAREST)
    d = ImageDraw.Draw(im)
    for x in range(0, W, 10):
        d.line([(x * K, H * K - (12 if x % 50 else 30)), (x * K, H * K)], fill=(0, 120, 0))
    d.text((4, 4), f"{names[i]} -> {names[(i + 1) % len(names)]}  dx={adv[i]:+.0f}", fill=(0, 0, 200))
    rows.append(im)
out = Image.new("RGB", (W * K * 2, (H * K + 6) * ((len(rows) + 1) // 2)), "white")
for i, im in enumerate(rows):
    out.paste(im, ((i % 2) * W * K, (i // 2) * (H * K + 6)))
out.save(sys.argv[1])
print("ok", sys.argv[1], adv)
