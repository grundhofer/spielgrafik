"""Gemeinsame Hilfsfunktionen für die Farbzyklus-Skripte (Oklab, k-means, Masken-Werkzeuge).

oklab() und kmeans() sind aus styles/vga-adventure/scripts/pixgrid.py übernommen (nur gelesen, hier kopiert),
kmeans_vec() rechnet k-means auf beliebigen Merkmalsvektoren (hier: Abend- und Nachtfarbe zusammen, 6 Werte).
"""
import numpy as np

M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
               [0.0883024619, 0.2817188376, 0.6299787005]])
M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
               [0.0259040371, 0.7827717662, -0.8086757660]])
BAYER4 = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) + 0.5) / 16


def oklab(rgb):
    c = np.clip(np.asarray(rgb, np.float64), 0, 255) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return np.cbrt(c @ M1.T) @ M2.T


def oklab_to_rgb(lab):
    lms = np.asarray(lab, np.float64) @ np.linalg.inv(M2).T
    lin = (lms ** 3) @ np.linalg.inv(M1).T
    lin = np.clip(lin, 0, 1)
    c = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055)
    return np.clip(c * 255, 0, 255)


def kmeans_vec(x, k, iters=16, seed=1, weights=None):
    """k-means++ auf Merkmalsvektoren x (n, d). Gibt (Zentren, Labels) zurück."""
    rng = np.random.default_rng(seed)
    n = len(x)
    if n <= k:
        return x.copy(), np.arange(n)
    w = np.ones(n) if weights is None else weights
    cent = [x[rng.choice(n, p=w / w.sum())]]
    d = ((x - cent[0]) ** 2).sum(1)
    for _ in range(1, k):
        p = d * w
        c = x[rng.choice(n, p=p / p.sum())] if p.sum() > 0 else x[rng.integers(n)]
        cent.append(c)
        d = np.minimum(d, ((x - c) ** 2).sum(1))
    cent = np.array(cent)
    for _ in range(iters):
        lbl = assign(x, cent)
        for j in range(k):
            m = lbl == j
            if m.any():
                cent[j] = (x[m] * w[m, None]).sum(0) / w[m].sum()
    return cent, assign(x, cent)


def assign(x, cent, chunk=20000):
    out = np.empty(len(x), np.int32)
    for s in range(0, len(x), chunk):
        d = ((x[s:s + chunk, None, :] - cent[None]) ** 2).sum(-1)
        out[s:s + chunk] = d.argmin(1)
    return out


def hsv(rgb):
    r, g, b = [rgb[..., i] / 255.0 for i in range(3)]
    mx, mn = np.maximum(np.maximum(r, g), b), np.minimum(np.minimum(r, g), b)
    d = mx - mn + 1e-9
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    s = np.where(mx > 0, (mx - mn) / (mx + 1e-9), 0)
    return h, s, mx


def dilate(m, r=1):
    out = m.copy()
    H, W = m.shape
    p = np.pad(m, r)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= p[r + dy:r + dy + H, r + dx:r + dx + W]
    return out


def distance_to(src, maxd=8):
    """Schachbrett-Abstand (8er-Nachbarschaft) jedes Pixels zur Maske src, gekappt bei maxd."""
    d = np.full(src.shape, maxd + 1, np.int32)
    d[src] = 0
    cur = src.copy()
    for k in range(1, maxd + 1):
        nxt = dilate(cur, 1)
        d[nxt & ~cur] = k
        cur = nxt
    return d


def hexs(c):
    c = np.clip(np.round(c), 0, 255).astype(int)
    return '%02x%02x%02x' % tuple(c)
