#!/usr/bin/env python3
"""Linienstärke messen: Median der Lauflängen von Tuschepixeln quer zu den Linien (in Zeilen und Spalten).

    .venv/bin/python styles/ligne-claire/scripts/line_width.py BILD.png [BILD2.png ...] [--box x0,y0,x1,y1]

Tusche = Helligkeit < 75 (und deckend). Gezählt werden Läufe von 1-10 px Länge, die auf beiden Seiten an helle
Pixel (Helligkeit > 85, also auch Fell, Weste, Schal) grenzen; längere Läufe (schwarze Flächen) und Läufe entlang einer Linie fallen heraus.
Gleiche Messung für Hintergrund und Figur, damit die Werte vergleichbar sind.
"""
import argparse
import numpy as np
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("images", nargs="+")
ap.add_argument("--box")
a = ap.parse_args()


def runs(ink, light):
    out = []
    for li, lt in zip(ink, light):
        x, n = 0, len(li)
        while x < n:
            if li[x]:
                s = x
                while x < n and li[x]:
                    x += 1
                if s > 0 and x < n and lt[s - 1] and lt[x] and x - s <= 10:
                    out.append(x - s)
            else:
                x += 1
    return out


for path in a.images:
    im = Image.open(path).convert("RGBA")
    if a.box:
        im = im.crop(tuple(int(v) for v in a.box.split(",")))
    arr = np.asarray(im).astype(np.float32)
    L = (arr[..., :3] * [0.299, 0.587, 0.114]).sum(2)
    opaque = arr[..., 3] > 128
    ink = (L < 75) & opaque
    light = (L > 85) & opaque
    r = np.array(runs(ink, light) + runs(ink.T, light.T))
    print(f"{path}: Median {np.median(r):.1f} px, Quartile {np.percentile(r, 25):.0f}-{np.percentile(r, 75):.0f}, "
          f"n={len(r)}")
