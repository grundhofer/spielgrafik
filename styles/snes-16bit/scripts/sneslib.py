"""Gemeinsame Hilfen für den Eintrag snes-16bit: Oklab, k-means, 5-Bit-Farben (BGR555), Kachelzerlegung.

Die SNES-PPU speichert Farben als 15 Bit (5 Bit je Kanal, BGR555). Jede Farbe, die in CGRAM landet, geht durch
c5(); zurück nach 8 Bit wie üblich v5 << 3 | v5 >> 2 (0..31 -> 0..255).
"""
import numpy as np


def srgb_to_lin(c):
    c = np.clip(c, 0, 255) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055) * 255.0


_M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
                [0.0883024619, 0.2817188376, 0.6299787005]])
_M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
                [0.0259040371, 0.7827717662, -0.8086757660]])


def oklab(rgb):
    return np.cbrt(srgb_to_lin(np.asarray(rgb, dtype=np.float64)) @ _M1.T) @ _M2.T


def oklab_to_rgb(lab):
    lms = (np.asarray(lab) @ np.linalg.inv(_M2).T) ** 3
    return lin_to_srgb(lms @ np.linalg.inv(_M1).T)


def c5(rgb):
    """8-Bit-RGB auf das 5-Bit-Raster der SNES-Palette runden (Ergebnis wieder 8 Bit)."""
    v = np.clip(np.round(np.asarray(rgb, dtype=np.float64) * 31.0 / 255.0), 0, 31).astype(np.int64)
    return (v << 3) | (v >> 2)


def on_grid5(rgb):
    rgb = np.asarray(rgb, dtype=np.int64)
    return np.all(c5(rgb) == rgb, axis=-1)


def bgr555(rgb):
    v = np.clip(np.round(np.asarray(rgb, dtype=np.float64) * 31.0 / 255.0), 0, 31).astype(np.int64)
    return v[..., 0] | (v[..., 1] << 5) | (v[..., 2] << 10)


def kmeans(x, k, iters=20, seed=0, w=None, init=None):
    """Gewichtetes k-means (x: N×D). Gibt Zentren (k×D) zurück; leere Cluster werden neu gestreut."""
    x = np.asarray(x, dtype=np.float64)
    n = len(x)
    w = np.ones(n) if w is None else np.asarray(w, dtype=np.float64)
    rng = np.random.default_rng(seed)
    if init is not None:
        c = np.array(init, dtype=np.float64)
    else:
        # k-means++
        c = [x[rng.choice(n, p=w / w.sum())]]
        d = ((x - c[0]) ** 2).sum(1)
        for _ in range(1, k):
            p = d * w
            if p.sum() <= 0:
                c.append(x[rng.integers(n)])
            else:
                c.append(x[rng.choice(n, p=p / p.sum())])
            d = np.minimum(d, ((x - c[-1]) ** 2).sum(1))
        c = np.array(c)
    for _ in range(iters):
        lab = nearest(x, c)
        for j in range(len(c)):
            m = lab == j
            if m.any():
                c[j] = (x[m] * w[m, None]).sum(0) / w[m].sum()
            else:
                c[j] = x[rng.integers(n)]
    return c


def nearest(x, c, chunk=200000):
    out = np.empty(len(x), dtype=np.int64)
    for s in range(0, len(x), chunk):
        d = ((x[s:s + chunk, None, :] - c[None]) ** 2).sum(-1)
        out[s:s + chunk] = d.argmin(1)
    return out


def tiles(shape, size=8):
    """Kachelindex je Pixel (Zeile-major) für ein Bild der Form (H, W)."""
    H, W = shape
    ty, tx = np.mgrid[0:H, 0:W]
    return (ty // size) * ((W + size - 1) // size) + (tx // size)
