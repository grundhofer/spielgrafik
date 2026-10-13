#!/usr/bin/env python3
"""Pseudo-Pixelraster eines KI-Pixelbildes schätzen: Kantenstärke je Spalte/Zeile, beste Periode und Phase.
   gridscan.py bild.png [--x0 0 --x1 W --y0 0 --y1 H]"""
import argparse
import numpy as np
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("img")
ap.add_argument("--x0", type=int, default=0); ap.add_argument("--x1", type=int, default=0)
ap.add_argument("--y0", type=int, default=0); ap.add_argument("--y1", type=int, default=0)
ap.add_argument("--pmin", type=float, default=3.0); ap.add_argument("--pmax", type=float, default=14.0)
a = ap.parse_args()
im = np.asarray(Image.open(a.img).convert("RGB")).astype(np.float32)
H, W, _ = im.shape
im = im[a.y0:a.y1 or H, a.x0:a.x1 or W]
ex = np.abs(np.diff(im, axis=1)).sum(2).sum(0)      # Kante zwischen Spalte i und i+1
ey = np.abs(np.diff(im, axis=0)).sum(2).sum(1)
for name, e in (("x", ex), ("y", ey)):
    e = e / e.mean()
    best = []
    for p in np.arange(a.pmin, a.pmax, 0.01):
        pos = np.arange(len(e)) + 0.5
        ph = (pos / p) % 1.0
        # Kantenenergie nahe einer Phase bündeln: Kreisstatistik
        z = (e * np.exp(2j * np.pi * ph)).sum() / e.sum()
        best.append((abs(z), p, (np.angle(z) / (2 * np.pi)) % 1.0))
    best.sort(reverse=True)
    print(name, " ".join(f"p={p:.2f} r={r:.3f} ph={ph:.2f}" for r, p, ph in best[:6]))
