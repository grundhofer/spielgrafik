#!/usr/bin/env python3
"""Entwurf für die Dachs-Views: verkleinert das vorhandene Laufblatt (shared/badger/walk_painted.png, 6 Bilder)
materialtreu auf das AGI-Raster (Doppelpixel, ca. 9×30) und gibt es als Buchstaben-Raster aus.

Das Ergebnis ist nur eine Vorlage für die von Hand gesetzten Views in build_views.py (bei 8 Pixeln Breite
entscheidet jedes Pixel, das Verkleinern allein ergibt keine lesbare Figur).

    .venv/bin/python styles/ega-adventure/scripts/draft_badger.py [--height 30]
Materialien: K schwarz, D dunkles Fell, W helles Fell/Hemd, G grün (Mütze/Weste), R Schal,
             B Leder (Tasche/Riemen), P Paket, Y Messing, . leer
"""
import argparse, pathlib, sys

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from sprites import oklab  # noqa: E402


def classify(rgb):
    lab = oklab(rgb.astype(np.float32))
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    C = np.hypot(a, b)
    h = (np.degrees(np.arctan2(b, a)) + 360) % 360
    m = np.full(L.shape, "D", dtype="<U1")
    m[(L > 0.72) & (C < 0.07)] = "W"
    m[(C >= 0.07) & ((h < 45) | (h > 340)) & (a > 0.08)] = "R"
    m[(C >= 0.04) & (h >= 100) & (h < 160) & (L < 0.62)] = "G"
    brownish = (C >= 0.045) & (h >= 45) & (h < 100)
    m[brownish & (L < 0.55)] = "B"
    m[brownish & (L >= 0.55)] = "P"
    m[(C >= 0.09) & (h >= 75) & (h < 105) & (L >= 0.62)] = "Y"
    m[L < 0.28] = "K"
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--height", type=int, default=30)
    ap.add_argument("--src", default=str(ROOT / "shared/badger/walk_painted.png"))
    a = ap.parse_args()
    im = np.asarray(Image.open(a.src).convert("RGBA"))
    op = im[..., 3] > 128
    cols = op.any(0)
    runs, start = [], None
    for x, v in enumerate(cols):
        if v and start is None:
            start = x
        if not v and start is not None:
            if x - start > 40:
                runs.append((start, x))
            start = None
    frames = []
    for x0, x1 in runs:
        sub = op[:, x0:x1]
        ys = np.flatnonzero(sub.any(1))
        frames.append((x0, x1, ys[0], ys[-1] + 1))
    H = max(f[3] - f[2] for f in frames)
    cell_h = H / a.height
    cell_w = cell_h * 2  # Doppelpixel: doppelt so breit wie hoch
    print(f"{len(frames)} Bilder, Figurhöhe {H} px, Zelle {cell_w:.1f}×{cell_h:.1f}")
    for fi, (x0, x1, y0, y1) in enumerate(frames):
        rgb = im[y0:y1, x0:x1, :3]
        alpha = op[y0:y1, x0:x1]
        mat = classify(rgb)
        # Anker: Kopfmitte im oberen Viertel
        top = alpha[: (y1 - y0) // 4]
        cx = np.flatnonzero(top.any(0)).mean()
        gw = 12
        ox = cx - gw / 2 * cell_w
        oy = (y1 - y0) - a.height * cell_h  # Füße unten
        out = []
        for gy in range(a.height):
            row = ""
            for gx in range(gw):
                ys0, ys1 = int(round(oy + gy * cell_h)), int(round(oy + (gy + 1) * cell_h))
                xs0, xs1 = int(round(ox + gx * cell_w)), int(round(ox + (gx + 1) * cell_w))
                ys0, xs0 = max(ys0, 0), max(xs0, 0)
                ys1, xs1 = min(ys1, alpha.shape[0]), min(xs1, alpha.shape[1])
                if ys1 <= ys0 or xs1 <= xs0:
                    row += "."
                    continue
                al = alpha[ys0:ys1, xs0:xs1]
                if al.mean() < 0.45:
                    row += "."
                    continue
                vals, cnt = np.unique(mat[ys0:ys1, xs0:xs1][al], return_counts=True)
                row += vals[cnt.argmax()]
            out.append(row)
        print(f"--- Bild {fi}")
        print("\n".join(out))


if __name__ == "__main__":
    main()
