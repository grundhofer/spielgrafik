#!/usr/bin/env python3
"""Kleine Aquarell-Bibliothek (NumPy + Pillow): Rauschen, Weichzeichnen, Verwerfen und ein Pigmentmodell.

Pigmentmodell: Jede Lasur trägt eine optische Dichte D = -ln(Farbe) je Kanal (lineares Licht) bei. Lasuren addieren
ihre Dichten, das Ergebnis ist Papier * exp(-Summe D). So verhalten sich übereinanderliegende Lasuren wie echte
transparente Farbschichten (nur dunkler, nie heller), und weißes Papier bleibt, wo keine Farbe liegt.
"""
import numpy as np
from PIL import Image

PAPER = np.array([0.957, 0.937, 0.894])          # sRGB des Papiers (warmes Weiß, gleich wie in Godot)


def s2l(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def l2s(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])


def density(srgb, paper=PAPER):
    """Dichte einer Lasur, die auf dem Papier die Farbe srgb ergibt."""
    return -np.log(np.clip(s2l(srgb) / s2l(paper), 1e-4, 1.0))


def value_noise(h, w, cell, seed, octaves=4, persistence=0.5, aniso=(1.0, 1.0)):
    """fBm aus bikubisch vergrößerten Zufallsgittern, 0..1. cell = Größe der gröbsten Zelle in px.
    aniso streckt die Zellen (x, y), z. B. (3, 1) für waagerechte Schlieren."""
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w))
    amp, total, c = 1.0, 0.0, float(cell)
    for _ in range(octaves):
        gx = max(2, int(np.ceil(w / (c * aniso[0]))) + 3)
        gy = max(2, int(np.ceil(h / (c * aniso[1]))) + 3)
        g = rng.random((gy, gx)).astype(np.float32)
        im = Image.fromarray(g, mode="F").resize((int(gx * c * aniso[0]), int(gy * c * aniso[1])), Image.BICUBIC)
        a = np.asarray(im)
        ox, oy = int(rng.integers(0, max(1, a.shape[1] - w))), int(rng.integers(0, max(1, a.shape[0] - h)))
        out += amp * a[oy:oy + h, ox:ox + w]
        total += amp
        amp *= persistence
        c = max(1.0, c / 2.0)
    out /= total
    lo, hi = np.percentile(out, 1), np.percentile(out, 99)
    return np.clip((out - lo) / (hi - lo + 1e-9), 0, 1)


def _box(a, r, axis):
    if r < 1:
        return a
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    p = np.pad(a, pad, mode="edge")
    cs = np.cumsum(p, axis=axis)
    n = a.shape[axis]
    hi = np.take(cs, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(cs, np.arange(0, n), axis=axis)
    return (hi - lo) / (2 * r + 1)


def blur(a, sigma):
    """Gauß-Näherung durch drei Kastenfilter je Achse."""
    if sigma <= 0.3:
        return a
    r = max(1, int(round(sigma * 0.93)))
    out = a.astype(np.float64)
    for _ in range(3):
        out = _box(_box(out, r, 0), r, 1)
    return out


def warp(a, dx, dy, order=1):
    """Tastet a an (x+dx, y+dy) ab (bilinear oder nächster Nachbar), Ränder geklemmt."""
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    x = np.clip(xx + dx, 0, w - 1)
    y = np.clip(yy + dy, 0, h - 1)
    if order == 0:
        return a[np.rint(y).astype(int), np.rint(x).astype(int)]
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0 + 1, w - 1), np.minimum(y0 + 1, h - 1)
    fx, fy = x - x0, y - y0
    if a.ndim == 3:
        fx, fy = fx[..., None], fy[..., None]
    return (a[y0, x0] * (1 - fx) * (1 - fy) + a[y0, x1] * fx * (1 - fy)
            + a[y1, x0] * (1 - fx) * fy + a[y1, x1] * fx * fy)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def inner_edge(mask, sigma):
    """Band innen am Rand einer (weichen) Maske, 0..1: hier sammelt sich beim Trocknen das Pigment."""
    return np.clip((mask - blur(mask, sigma)) * 2.2, 0, 1) * mask


def to_srgb_image(lin_rgb, alpha=None):
    rgb = (l2s(lin_rgb) * 255 + 0.5).clip(0, 255).astype(np.uint8)
    if alpha is None:
        return Image.fromarray(rgb, "RGB")
    a = (np.clip(alpha, 0, 1) * 255 + 0.5).astype(np.uint8)
    return Image.fromarray(np.dstack([rgb, a]), "RGBA")


def downscale_rgba(im, size):
    """Verkleinern mit vormultipliziertem Alpha (keine dunklen oder hellen Säume)."""
    a = np.asarray(im).astype(np.float64) / 255.0
    pm = a.copy()
    pm[..., :3] *= pm[..., 3:4]
    chans = [np.asarray(Image.fromarray(pm[..., i].astype(np.float32), "F").resize(size, Image.LANCZOS))
             for i in range(4)]
    out = np.dstack(chans)
    al = np.clip(out[..., 3], 0, 1)
    rgb = np.where(al[..., None] > 1e-4, out[..., :3] / np.maximum(al[..., None], 1e-4), 0)
    return Image.fromarray((np.dstack([np.clip(rgb, 0, 1), al]) * 255 + 0.5).astype(np.uint8), "RGBA")
