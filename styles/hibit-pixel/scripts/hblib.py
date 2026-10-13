"""Gemeinsame Helfer für die Bauskripte von hibit-pixel (Oklab, k-means, Raster-Reduktion, Normal Maps).

Bewusst eigenständig (nur NumPy/Pillow), damit die Skripte in anderen Projekten wiederverwendbar sind.
Die Zellen-Mehrheitsregel folgt styles/snes-16bit/scripts/reduce_px.py.
"""
import numpy as np
from PIL import Image

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
    # k-means++-Start
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


def reduce_mode(lbl, out_w, out_h, k, inset=0.22, weights=None):
    """lbl: Indexbild (H×W) in Quellauflösung. Je Zielzelle gewinnt der häufigste Index im Zellinneren."""
    H, W = lbl.shape
    sx, sy = W / out_w, H / out_h
    out = np.zeros((out_h, out_w), dtype=np.int64)
    for y in range(out_h):
        y0 = int(np.floor((y + inset) * sy)); y1 = max(y0 + 1, int(np.ceil((y + 1 - inset) * sy)))
        for x in range(out_w):
            x0 = int(np.floor((x + inset) * sx)); x1 = max(x0 + 1, int(np.ceil((x + 1 - inset) * sx)))
            out[y, x] = np.bincount(lbl[y0:y1, x0:x1].ravel(), minlength=k).argmax()
    return out


def box_blur(a, r):
    if r <= 0:
        return a.copy()
    p = np.pad(a, r, mode="edge")
    c = p.cumsum(0).cumsum(1)
    c = np.pad(c, ((1, 0), (1, 0)))
    n = 2 * r + 1
    s = c[n:, n:] - c[:-n, n:] - c[n:, :-n] + c[:-n, :-n]
    return s / (n * n)


def dist_inside(mask, maxd=8):
    """Abstand (in Pixeln, Schachbrett-Metrik, gekappt) jedes Pixels der Maske zum nächsten Pixel außerhalb."""
    d = np.zeros(mask.shape, dtype=np.float64)
    cur = mask.copy()
    for i in range(1, maxd + 1):
        d[cur] = i
        er = cur.copy()
        er[1:] &= cur[:-1]; er[:-1] &= cur[1:]; er[:, 1:] &= cur[:, :-1]; er[:, :-1] &= cur[:, 1:]
        cur = er
        if not cur.any():
            break
    return d


def normals_from_height(h, strength=1.0):
    """Normal Map (Godot 2D erwartet OpenGL-Konvention: Grün = nach oben im Bild)."""
    gx = np.zeros_like(h); gy = np.zeros_like(h)
    gx[:, 1:-1] = (h[:, 2:] - h[:, :-2]) * 0.5
    gy[1:-1, :] = (h[2:, :] - h[:-2, :]) * 0.5
    nx, ny, nz = -gx * strength, gy * strength, np.ones_like(h)   # Bild-y nach unten -> ny = +dh/dy
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    n = np.dstack([nx / ln, ny / ln, nz / ln])
    return n


def encode_normals(n):
    return np.clip(np.round((n * 0.5 + 0.5) * 255), 0, 255).astype(np.uint8)


def save_rgb(arr, path):
    Image.fromarray(np.asarray(arr, dtype=np.uint8), "RGB").save(path)


def save_rgba(arr, path):
    Image.fromarray(np.asarray(arr, dtype=np.uint8), "RGBA").save(path)
