#!/usr/bin/env python3
"""KI-Figurenblatt (assets/raw/badger.png) -> Materialraster für die Dachs-Sprites (Vorstufe der Handarbeit).

Je Quellpixel ein Material (Kontur, Fell, Weiß, Rot, Grün, Braun, Hellbraun), dann je Zielpixel (Hires-Raster,
SCALE Quellpixel je Pixel) der Anteil je Material. Kontur wird schon ab 30 % Anteil gesetzt (dünne Linien),
sonst gewinnt das häufigste Material. Füße aller Bilder auf einer Grundlinie, waagerecht am Kopf ausgerichtet.
Ausgabe: scripts/badger_ai/frame<N>.txt (ein Zeichen je Hires-Pixel) als Ausgangspunkt für die Handkorrektur
in scripts/badger_sprites.txt, und eine Vergrößerung zur Ansicht.

Zeichen: . leer, K Kontur (schwarz), F Fell (dunkelgrau), W weiß, R rot (Schal), G grün (Mütze, Weste),
         B braun (Tasche), P hellbraun (Paket), Y gelb (Knöpfe)
"""
import pathlib, sys

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCALE = 11.6
OUT_H = 42

MAT = {".": None, "K": (0, 0, 0), "F": (60, 60, 64), "W": (255, 255, 255), "R": (104, 55, 43),
       "G": (88, 141, 67), "B": (90, 50, 20), "P": (160, 110, 50), "Y": (220, 180, 50)}


def classify(rgb):
    r, g, b = [rgb[..., i].astype(int) for i in range(3)]
    lum = (r * 3 + g * 6 + b) / 10
    mx, mn = np.maximum(np.maximum(r, g), b), np.minimum(np.minimum(r, g), b)
    sat = mx - mn
    m = np.full(r.shape, "F", dtype="<U1")
    m[(lum > 175) & (sat < 90)] = "W"
    m[(r > g + 55) & (r > b + 55) & (g < 80)] = "R"  # noqa
    m[(g > r + 10) & (g > b + 25)] = "G"
    red = (r > g + 55) & (r > b + 55) & (g < 80)
    brown = (r > g + 20) & (g > b + 8) & (lum < 175) & ~red & (lum >= 40)
    m[brown & (lum < 85)] = "B"
    m[brown & (lum >= 85)] = "P"
    m[(r > 180) & (g > 140) & (b < 90)] = "Y"
    m[(lum < 22) & (sat < 30)] = "K"
    return m


def main():
    im = np.asarray(Image.open(ROOT / "assets/raw/badger.png").convert("RGBA"))
    op = im[..., 3] > 160
    cols = op.any(0)
    runs, s = [], None
    for x in range(len(cols) + 1):
        c = x < len(cols) and cols[x]
        if c and s is None:
            s = x
        if not c and s is not None:
            if x - s > 40:
                runs.append((s, x))
            s = None
    mats = classify(im[..., :3])
    mats[~op] = "."
    outdir = ROOT / "scripts/badger_ai"
    outdir.mkdir(exist_ok=True)
    sheets = []
    for n, (x0, x1) in enumerate(runs, 1):
        sub = op[:, x0:x1]
        ys = np.flatnonzero(sub.any(1))
        y0, y1 = ys[0], ys[-1] + 1
        # Kopfmitte (oberes Viertel) als waagerechter Anker
        head = sub[y0:y0 + (y1 - y0) // 4]
        hx = x0 + np.flatnonzero(head.any(0)).mean()
        ox = hx - 12.5 * SCALE                  # Kopfmitte auf Spalte 12,5 von 24
        oy = y1 - OUT_H * SCALE                 # Füße auf der letzten Zeile
        grid = np.full((OUT_H, 24), ".", dtype="<U1")
        for ty in range(OUT_H):
            for tx in range(24):
                sx0, sy0 = int(ox + tx * SCALE), int(oy + ty * SCALE)
                blk = mats[max(0, sy0):max(0, sy0 + int(SCALE)), max(0, sx0):max(0, sx0 + int(SCALE))]
                if blk.size == 0:
                    continue
                vals, cnt = np.unique(blk, return_counts=True)
                frac = dict(zip(vals, cnt / blk.size))
                if frac.get(".", 0) > 0.6:
                    continue
                if frac.get("K", 0) >= 0.30:
                    grid[ty, tx] = "K"
                    continue
                best = max((v for v in frac if v != "."), key=lambda v: frac[v])
                grid[ty, tx] = best
        (outdir / f"frame{n}.txt").write_text("\n".join("".join(r) for r in grid) + "\n")
        sheets.append(grid)
        print(f"Bild {n}: Quelle x {x0}-{x1}, y {y0}-{y1}, Kopfmitte {hx:.0f}")
    # Ansicht
    cell = 8
    view = Image.new("RGB", (len(sheets) * 26 * cell, OUT_H * cell), (255, 0, 255))
    px = view.load()
    for n, g in enumerate(sheets):
        for y in range(OUT_H):
            for x in range(24):
                c = MAT[g[y, x]]
                if c is None:
                    continue
                for dy in range(cell):
                    for dx in range(cell):
                        px[(n * 26 + x) * cell + dx, y * cell + dy] = c
    view.save(outdir / "view.png")


if __name__ == "__main__":
    main()
