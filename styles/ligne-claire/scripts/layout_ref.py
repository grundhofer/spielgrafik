#!/usr/bin/env python3
"""Layout-Referenz für agy: getuschte Blender-Bilder einer Reihe als Raster auf Magenta (1536x1024).

    .venv/bin/python styles/ligne-claire/scripts/layout_ref.py SHEET.png FRAMES COLS ROWS OUT.png [--pick 0,1,2]

SHEET ist ein Blatt aus ink_badger.py (Bilder nebeneinander, gleiche Breite). Alle Bilder werden mit demselben
Faktor skaliert und mit gemeinsamer Fußlinie je Zeile in gleich große Zellen gesetzt.
"""
import argparse
import numpy as np
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("sheet"); ap.add_argument("frames", type=int); ap.add_argument("cols", type=int)
ap.add_argument("rows", type=int); ap.add_argument("out")
ap.add_argument("--pick", default="")
a = ap.parse_args()
sh = Image.open(a.sheet).convert("RGBA")
fw = sh.width // a.frames
pick = [int(x) for x in a.pick.split(",")] if a.pick else list(range(a.frames))
fr = [sh.crop((i * fw, 0, (i + 1) * fw, sh.height)) for i in pick]
al = np.zeros((sh.height, fw), bool)
for f in fr:
    al |= np.asarray(f)[..., 3] > 0
ys, xs = np.nonzero(al)
box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
W, H = 1536, 1024
cw, ch = W // a.cols, H // a.rows
k = min((cw - 24) / (box[2] - box[0]), (ch - 40) / (box[3] - box[1]))
canvas = Image.new("RGBA", (W, H), (255, 0, 255, 255))
for n, f in enumerate(fr):
    c = f.crop(box)
    c = c.resize((round(c.width * k), round(c.height * k)), Image.LANCZOS)
    col, row = n % a.cols, n // a.cols
    x = col * cw + (cw - c.width) // 2
    y = row * ch + ch - 20 - c.height
    canvas.alpha_composite(c, (x, y))
canvas.convert("RGB").save(a.out)
print("Faktor", round(k, 3), "Zelle", cw, ch)
