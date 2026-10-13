#!/usr/bin/env python3
"""Wie viele Pixel eines gerenderten Bildes liegen genau auf einer der acht Palettenfarben?

    .venv/bin/python styles/minimal-geometrisch/scripts/palette_check.py media/poster.png [weitere.png ...]

Die Palette wird aus demo/main.gd gelesen. "genau" heißt: größte Kanalabweichung <= 2 (Rundung im Renderer).
Der Rest sind Kantenpixel der 4x-MSAA-Glättung und der Schrift (Mischungen zweier Palettenfarben).
Getrennt gezählt: Szene (y < 598) und Oberfläche (y >= 598).
"""
import pathlib, re, sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent.parent
src = (HERE / "demo" / "main.gd").read_text()
pal = re.findall(r'^const (\w+) := Color\("#([0-9a-f]{6})"\)', src, re.M)
P = np.array([[int(h[i:i + 2], 16) for i in (0, 2, 4)] for _, h in pal], np.int16)
UI_TOP = 598

for path in sys.argv[1:]:
    A = np.asarray(Image.open(path).convert("RGB"), np.int16)
    dist = np.abs(A[:, :, None, :] - P[None, None, :, :]).max(3)      # H x W x 8
    nearest = dist.min(2)
    exact = nearest <= 2
    for name, sl in (("Szene", slice(0, UI_TOP)), ("Oberfläche", slice(UI_TOP, None))):
        e = exact[sl]
        share = e.mean()
        idx = dist[sl].argmin(2)[e]
        used = {pal[k][0]: round(float((idx == k).mean()) * 100, 1) for k in range(len(pal)) if (idx == k).any()}
        uniq = len(np.unique(A[sl].reshape(-1, 3), axis=0))
        print(f"{path} {name}: {share * 100:.2f} % der Pixel genau auf der Palette, {uniq} verschiedene Farbwerte "
              f"insgesamt (Rest = Kantenglättung); Anteile: {used}")
