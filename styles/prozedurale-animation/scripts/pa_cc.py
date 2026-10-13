"""Zusammenhangskomponenten eines Alphakanals ohne SciPy (Breitensuche auf einem verkleinerten Raster).

Dünne Teile (Takelage, Riemenringe) hängen über die Dilatation am Hauptteil.
"""
from collections import deque

import numpy as np


def components(alpha, thresh=8, cell=4, dilate=2, min_cells=20):
    """Liefert eine Liste (label_full, bbox) je Komponente, sortiert von links nach rechts.

    label_full: bool-Maske in voller Auflösung (alpha > 0 und Zelle gehört zur Komponente).
    bbox: (x0, y0, x1, y1) in voller Auflösung, x1/y1 exklusiv.
    """
    h, w = alpha.shape
    hs, ws = (h + cell - 1) // cell, (w + cell - 1) // cell
    pad = np.zeros((hs * cell, ws * cell), bool)
    pad[:h, :w] = alpha > thresh
    small = pad.reshape(hs, cell, ws, cell).any(axis=(1, 3))
    grown = small.copy()
    for _ in range(dilate):
        g = grown.copy()
        g[1:] |= grown[:-1]; g[:-1] |= grown[1:]
        g[:, 1:] |= grown[:, :-1]; g[:, :-1] |= grown[:, 1:]
        grown = g
    lab = np.zeros((hs, ws), np.int32)
    n = 0
    for y0 in range(hs):
        for x0 in range(ws):
            if not grown[y0, x0] or lab[y0, x0]:
                continue
            n += 1
            lab[y0, x0] = n
            q = deque([(y0, x0)])
            while q:
                y, x = q.popleft()
                for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                    if 0 <= yy < hs and 0 <= xx < ws and grown[yy, xx] and not lab[yy, xx]:
                        lab[yy, xx] = n
                        q.append((yy, xx))
    full = np.repeat(np.repeat(lab, cell, 0), cell, 1)[:h, :w]
    out = []
    for k in range(1, n + 1):
        if (lab == k).sum() < min_cells:
            continue
        m = (full == k) & (alpha > 0)
        ys, xs = np.nonzero(m)
        if len(xs) == 0:
            continue
        out.append((m, (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)))
    out.sort(key=lambda c: (c[1][0], c[1][1]))
    return out
