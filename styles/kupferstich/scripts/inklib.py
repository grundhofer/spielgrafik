"""Gemeinsame Hilfen für den Eintrag kupferstich (NumPy, Pillow): Tuschedichte aus Stichen, Papier, Rauschen.

Tuschedichte D: 0 = blankes Papier, 1 = volle Druckfarbe. Alle Druckelemente (Platte, Figur, Ornamente) werden als
D gespeichert und in Godot mit derselben Druckfarbe auf dasselbe Papier gedruckt.
"""
import json, pathlib

import numpy as np
from PIL import Image, ImageFilter

SD = pathlib.Path(__file__).resolve().parents[1]
ROOT = SD.parents[1]
LAYOUT = json.loads((SD / "scripts/layout.json").read_text())


def lum(rgb):
    a = np.asarray(rgb, dtype=np.float32) / 255.0
    return a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114


def density(L, paper=None, ink=None, lo_pct=0.5, hi_pct=97.0):
    """Helligkeit -> Tuschedichte. Papier- und Tuschewert aus Perzentilen (oder vorgegeben)."""
    if paper is None:
        paper = float(np.percentile(L, hi_pct))
    if ink is None:
        ink = float(np.percentile(L, lo_pct))
    return np.clip((paper - L) / max(1e-3, paper - ink), 0, 1), paper, ink


def to_img(a):
    return Image.fromarray(np.clip(np.round(a * 255), 0, 255).astype(np.uint8))


def resize_f(a, size, resample=Image.LANCZOS):
    """Float-Feld mit Pillow (Modus F) skalieren."""
    return np.asarray(Image.fromarray(a.astype(np.float32), "F").resize(size, resample), dtype=np.float32)


def _shift_sum(a, w, axis):
    r = len(w) // 2
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r, r)
    p = np.pad(a, pad, mode="reflect")
    out = np.zeros_like(a, dtype=np.float32)
    n = a.shape[axis]
    for i, wt in enumerate(w):
        sl = [slice(None)] * a.ndim
        sl[axis] = slice(i, i + n)
        out += wt * p[tuple(sl)]
    return out


def blur(a, sigma):
    """Gauß-Weichzeichner (getrennt, Rand gespiegelt), ohne SciPy."""
    if sigma <= 0:
        return a.astype(np.float32)
    r = max(1, int(np.ceil(sigma * 3)))
    x = np.arange(-r, r + 1, dtype=np.float32)
    w = np.exp(-0.5 * (x / sigma) ** 2)
    w /= w.sum()
    a = a.astype(np.float32)
    return _shift_sum(_shift_sum(a, w, 0), w, 1)


def _shift_red(a, r, axis, fn):
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r, r)
    p = np.pad(a, pad, mode="edge")
    out = None
    n = a.shape[axis]
    for i in range(2 * r + 1):
        sl = [slice(None)] * a.ndim
        sl[axis] = slice(i, i + n)
        out = p[tuple(sl)].copy() if out is None else fn(out, p[tuple(sl)])
    return out


def erode(a, r):
    """Minimum über ein Quadrat (2r+1)."""
    return _shift_red(_shift_red(a, r, 0, np.minimum), r, 1, np.minimum)


def dilate(a, r):
    return _shift_red(_shift_red(a, r, 0, np.maximum), r, 1, np.maximum)


def value_noise(h, w, cell, rng):
    """Glattes Wertrauschen (bikubisch interpoliertes Zufallsgitter), Werte etwa 0..1."""
    gh, gw = h // cell + 3, w // cell + 3
    g = rng.random((gh, gw)).astype(np.float32)
    big = resize_f(g, (gw * cell, gh * cell), Image.BICUBIC)
    return big[cell:cell + h, cell:cell + w]


def fbm(h, w, cells, rng, weights=None):
    weights = weights or [1.0 / (i + 1) for i in range(len(cells))]
    acc = np.zeros((h, w), np.float32)
    for c, wt in zip(cells, weights):
        acc += wt * (value_noise(h, w, c, rng) - 0.5)
    return acc / sum(weights)
