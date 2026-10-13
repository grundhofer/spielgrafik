"""Gemeinsame Helfer für die Bauskripte von hd-2d (Oklab, k-means, Kontur).

Oklab/k-means übernommen aus styles/hibit-pixel/scripts/hblib.py (nur gelesen, hier eigenständig kopiert),
damit der Eintrag ohne fremde Ordner läuft. Nur NumPy/Pillow.
"""
import numpy as np

M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
               [0.0883024619, 0.2817188376, 0.6299787005]])
M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
               [0.0259040371, 0.7827717662, -0.8086757660]])


def oklab(rgb):
    c = np.clip(np.asarray(rgb, dtype=np.float64), 0, 255) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return np.cbrt(c @ M1.T) @ M2.T


def oklab_to_rgb(lab):
    lms = np.asarray(lab, dtype=np.float64) @ np.linalg.inv(M2).T
    lin = (lms ** 3) @ np.linalg.inv(M1).T
    lin = np.clip(lin, 0, 1)
    srgb = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)
    return srgb * 255.0


def nearest(x, cent, chunk=200000):
    out = np.empty(len(x), dtype=np.int64)
    for i in range(0, len(x), chunk):
        d = ((x[i:i + chunk, None, :] - cent[None]) ** 2).sum(-1)
        out[i:i + chunk] = d.argmin(1)
    return out


def kmeans(x, k, iters=25, seed=1):
    rng = np.random.default_rng(seed)
    cent = [x[rng.integers(len(x))]]
    d2 = ((x - cent[0]) ** 2).sum(1)
    for _ in range(1, k):
        p = d2 / d2.sum()
        cent.append(x[rng.choice(len(x), p=p)])
        d2 = np.minimum(d2, ((x - cent[-1]) ** 2).sum(1))
    cent = np.array(cent)
    for _ in range(iters):
        lbl = nearest(x, cent)
        for j in range(k):
            m = lbl == j
            if m.any():
                cent[j] = x[m].mean(0)
    return cent


def runs(v, gap):
    """Zusammenhängende True-Bereiche eines 1D-Arrays; Lücken bis gap werden überbrückt."""
    idx = np.flatnonzero(v)
    out, s, p = [], idx[0], idx[0]
    for i in idx[1:]:
        if i - p > gap:
            out.append((s, p + 1))
            s = i
        p = i
    out.append((s, p + 1))
    return out


def figures(m, row_gap=20, col_gap=3, min_w=20):
    """Figuren eines Blatts (Maske): Reihen, darin Spalten. Liefert Rahmen und Reihe."""
    figs = []
    for r, (y0, y1) in enumerate(runs(m.any(1), row_gap)):
        for x0, x1 in runs(m[y0:y1].any(0), col_gap):
            if x1 - x0 < min_w:
                continue
            sub = m[y0:y1, x0:x1]
            ys = np.flatnonzero(sub.any(1))
            figs.append({"row": r, "x0": int(x0), "x1": int(x1), "top": int(y0 + ys[0]), "bot": int(y0 + ys[-1])})
    return figs


def outline_edge(op):
    """Deckende Pixel mit transparentem 4er-Nachbarn (Bildrand zählt als transparent)."""
    nb = np.zeros_like(op)
    nb[1:] |= ~op[:-1]; nb[:-1] |= ~op[1:]; nb[:, 1:] |= ~op[:, :-1]; nb[:, :-1] |= ~op[:, 1:]
    nb[0] = True; nb[-1] = True; nb[:, 0] = True; nb[:, -1] = True
    return op & nb
