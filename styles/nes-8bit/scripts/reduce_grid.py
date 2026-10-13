#!/usr/bin/env python3
"""KI-Pixelbild auf sein eigenes (ungleichmäßiges) Kunstpixel-Raster zurückführen.

Das Bildmodell zeichnet "Pixel" mit schwankender Breite (hier 6,2-6,8 Bildpixel, Phase driftet). Statt eines
festen Rasters sucht eine dynamische Programmierung je Achse die Zellgrenzen: Grenzen liegen auf starken
Kanten (Summe der Farbsprünge über die ganze Spalte bzw. Zeile), Abstände 5-8 Bildpixel, Abweichung vom
mittleren Abstand kostet. Je Zelle gewinnt die häufigste Farbe im Zellinneren (Vorquantisierung Median-Cut).

   reduce_grid.py in.png out.npy [--period 6.5] [--colors 96] [--preview p.png]
Ausgabe: .npy mit RGB je Kunstpixel (float32), Vorschau optional."""
import argparse
import numpy as np
from PIL import Image


def fit_bounds(edge, n_px, period, lam=6.0, dmin=5, dmax=8):
    """edge[i] = Kantenstärke zwischen Pixel i und i+1 (Länge n_px-1). Rückgabe: Grenzen 0..n_px."""
    e = np.zeros(n_px + 1)
    e[1:n_px] = edge / (edge.mean() + 1e-9)
    best = np.full(n_px + 1, -1e18)
    prev = np.zeros(n_px + 1, int)
    # Anfang: erste Grenze darf eine angeschnittene Zelle sein (0 < b0 <= dmax)
    best[0] = 0.0
    for pos in range(1, n_px + 1):
        for d in range(dmin, dmax + 1):
            q = pos - d
            if q < 0:
                if pos <= dmax and best[pos] < e[pos] - 2.0:      # angeschnittene erste Zelle
                    best[pos] = e[pos] - 2.0
                    prev[pos] = 0
                continue
            s = best[q] + e[pos] - lam * abs(d - period) / period
            if s > best[pos]:
                best[pos] = s
                prev[pos] = q
    # Ende: letzte Zelle darf angeschnitten sein
    end = max(range(max(0, n_px - dmax), n_px + 1), key=lambda p: best[p] - (0 if p == n_px else 2.0))
    b = [n_px] if end != n_px else []
    p = end
    while p > 0:
        b.append(p)
        p = prev[p]
    b.append(0)
    return sorted(set(b))


def reduce(img, period, colors=96, inner=0.5):
    rgb = img.convert("RGB")
    a = np.asarray(rgb).astype(np.float32)
    H, W, _ = a.shape
    ex = np.abs(np.diff(a, axis=1)).sum(2).sum(0)
    ey = np.abs(np.diff(a, axis=0)).sum(2).sum(1)
    bx = fit_bounds(ex, W, period[0])
    by = fit_bounds(ey, H, period[1])
    q = rgb.quantize(colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    qi = np.asarray(q)
    pal = np.array(q.getpalette()[:colors * 3]).reshape(-1, 3)
    out = np.zeros((len(by) - 1, len(bx) - 1, 3), np.float32)
    m = (1 - inner) / 2
    for j in range(len(by) - 1):
        y0, y1 = by[j], by[j + 1]
        ya, yb = int(round(y0 + m * (y1 - y0))), max(int(round(y1 - m * (y1 - y0))), int(round(y0 + m * (y1 - y0))) + 1)
        for i in range(len(bx) - 1):
            x0, x1 = bx[i], bx[i + 1]
            xa, xb = int(round(x0 + m * (x1 - x0))), max(int(round(x1 - m * (x1 - x0))), int(round(x0 + m * (x1 - x0))) + 1)
            cell = qi[ya:yb, xa:xb].ravel()
            out[j, i] = pal[np.bincount(cell, minlength=colors).argmax()]
    return out, bx, by


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("inp"); ap.add_argument("out")
    ap.add_argument("--period", type=float, nargs=2, default=[6.5, 6.44])
    ap.add_argument("--colors", type=int, default=96)
    ap.add_argument("--preview")
    a = ap.parse_args()
    out, bx, by = reduce(Image.open(a.inp), a.period, a.colors)
    np.save(a.out, out)
    dx, dy = np.diff(bx), np.diff(by)
    print(f"{a.out}: {out.shape[1]}x{out.shape[0]} Kunstpixel; Zellbreiten {dx.min()}-{dx.max()} (Mittel {dx.mean():.2f}), "
          f"Zellhöhen {dy.min()}-{dy.max()} (Mittel {dy.mean():.2f})")
    if a.preview:
        Image.fromarray(out.astype(np.uint8)).resize((out.shape[1] * 3, out.shape[0] * 3), Image.NEAREST).save(a.preview)
