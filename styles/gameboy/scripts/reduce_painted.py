"""Gemalten Laufzyklus (shared/badger/walk_painted.png, 6 Bilder) materialtreu auf das Handheld-Raster bringen.

Jeder Quellpixel wird einem Material zugeordnet (Farbregeln), je Zielpixel entscheidet die Mehrheit (kleine Teile wie
Nase und Auge gewichtet), dann Material -> Ton. Ergebnis ist die Vorlage, die badger.py von Hand bereinigt.
Aufruf: .venv/bin/python styles/gameboy/scripts/reduce_painted.py --width 16 [--preview out.png]
"""
import argparse
import colorsys

import numpy as np
from PIL import Image

MAT = ["fur", "white", "scarf", "green", "tan", "brown", "black"]
TONE = {"fur": 3, "white": 0, "scarf": 2, "green": 2, "tan": 0, "brown": 3, "black": 3}
WEIGHT = {"black": 2.5, "white": 1.0, "scarf": 1.1}


def classify(rgb):
    r, g, b = [int(c) for c in rgb]
    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    if l < 0.14:
        return "black"
    if r > 100 and r > 1.8 * g:
        return "scarf"
    if l > 0.75:
        return "white"
    if l > 0.5 or (0.08 <= h <= 0.13 and l > 0.38 and s > 0.3):
        return "tan"
    if h < 0.06 and s > 0.22:
        return "brown"
    if g - b >= 14 and h >= 0.095:
        return "green"
    return "fur"


def frames(path):
    im = Image.open(path).convert("RGBA")
    a = np.asarray(im)
    occ = a[..., 3] > 60
    colsum = occ.any(0)
    runs, start = [], None
    for x, v in enumerate(colsum):
        if v and start is None:
            start = x
        if not v and start is not None:
            if x - start > 40:
                runs.append((start, x))
            start = None
    if start is not None:
        runs.append((start, len(colsum)))
    # zusammenhängende Nachbarbilder (Schal berührt) an der dünnsten Spalte teilen
    med = sorted(x1 - x0 for x0, x1 in runs)[len(runs) // 2]
    out = []
    for x0, x1 in runs:
        if x1 - x0 > 1.5 * med:
            prof = occ[:, x0:x1].sum(0)
            lo, hi = int((x1 - x0) * 0.3), int((x1 - x0) * 0.7)
            cut = x0 + lo + int(np.argmin(prof[lo:hi]))
            out += [(x0, cut), (cut, x1)]
        else:
            out.append((x0, x1))
    runs = out
    ys = np.where(occ.any(1))[0]
    return im, runs, ys[0], ys[-1] + 1


def reduce(width=16, path="shared/badger/walk_painted.png"):
    im, runs, y0, y1 = frames(path)
    a = np.asarray(im)
    # gemeinsamer Maßstab: breitestes Bild -> width Pixel
    span = max(x1 - x0 for x0, x1 in runs)
    cell = span / width
    H = int(np.ceil((y1 - y0) / cell))
    lut = {}
    out = []
    for x0, x1 in runs:
        # Bild am Kopf ausrichten: Schwerpunkt der Mützenpartie (obere 20 %)
        top = a[y0:y0 + int((y1 - y0) * 0.2), x0:x1, 3] > 60
        cx = x0 + np.where(top.any(0))[0].mean()
        ox = cx - width * cell * 0.45
        grid = np.full((H, width), -1, np.int8)
        for gy in range(H):
            for gx in range(width):
                ya, yb = int(y0 + gy * cell), int(y0 + (gy + 1) * cell)
                xa, xb = int(ox + gx * cell), int(ox + (gx + 1) * cell)
                xa, xb = max(xa, 0), min(xb, a.shape[1])
                if xb <= xa:
                    continue
                blk = a[ya:yb, xa:xb].reshape(-1, 4)
                blk = blk[blk[:, 3] > 128]
                if len(blk) < 0.45 * cell * cell:
                    continue
                cnt = {}
                for p in blk[:, :3]:
                    k = tuple(int(v) >> 2 for v in p)
                    m = lut.get(k)
                    if m is None:
                        m = lut[k] = classify(p)
                    cnt[m] = cnt.get(m, 0) + WEIGHT.get(m, 1.0)
                grid[gy, gx] = MAT.index(max(cnt, key=cnt.get))
        out.append(grid)
    return out


def tones(grid):
    t = np.full(grid.shape, -1, np.int8)
    for i, m in enumerate(MAT):
        t[grid == i] = TONE[m]
    return t


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=16)
    ap.add_argument("--preview")
    a = ap.parse_args()
    gs = reduce(a.width)
    keys = "Kwsgtbn"
    for g in gs:
        print("\n".join("".join("." if v < 0 else keys[v] for v in row) for row in g))
        print()
    if a.preview:
        import sys, os
        sys.path.insert(0, os.path.dirname(__file__))
        import pix
        row = []
        for g in gs:
            t = tones(g)
            bg = np.full((t.shape[0] + 2, a.width + 4), 1, np.int8)
            pix.put(bg, t, 2, 1)
            row.append(bg)
        pix.save_preview(np.concatenate(row, 1), a.preview, 10)
