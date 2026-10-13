#!/usr/bin/env python3
"""Hilfsfunktionen für die Verarbeitung der KI-Bilder (nur NumPy + Pillow): Zusammenhangskomponenten, Freistellen,
Farbsaum entfernen, Ausfüllen (Übermalen) von Bildbereichen, Bildvergleich bei Verschiebung."""
from collections import deque

import numpy as np
from PIL import Image, ImageDraw

import wc


def label(mask):
    """4-Nachbarschaft; gibt (Etiketten, Anzahl) zurück, 0 = Hintergrund. Für Masken bis etwa 1 Mio. Pixel."""
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    n = 0
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys.tolist(), xs.tolist()):
        if lab[y0, x0]:
            continue
        n += 1
        lab[y0, x0] = n
        q = deque([(y0, x0)])
        while q:
            y, x = q.popleft()
            for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = n
                    q.append((yy, xx))
    return lab, n


def components(mask):
    """Liste von Komponenten mit Fläche, Rahmen und Schwerpunkt."""
    lab, n = label(mask)
    out = []
    for i in range(1, n + 1):
        ys, xs = np.nonzero(lab == i)
        out.append({"id": i, "area": int(len(ys)), "x0": int(xs.min()), "x1": int(xs.max()), "y0": int(ys.min()),
                    "y1": int(ys.max()), "cx": float(xs.mean()), "cy": float(ys.mean())})
    return lab, out


def dilate(mask, r):
    return wc.blur(mask.astype(np.float64), r) > 0.02 if r > 0 else mask


def erode(mask, r):
    return ~dilate(~mask, r) if r > 0 else mask


def key_magenta(rgb, tol=70.0, soft=50.0):
    """rgb 0..255 float. Alpha aus dem Abstand zur Schlüsselfarbe, Farbe halbtransparenter Pixel entmischt."""
    key = np.array([255.0, 0.0, 255.0])
    dist = np.sqrt(((rgb - key) ** 2).sum(-1))
    a = np.clip((dist - tol) / soft, 0, 1)
    out = rgb.copy()
    semi = (a > 0) & (a < 1)
    a3 = a[semi][:, None]
    out[semi] = np.clip((rgb[semi] - key * (1 - a3)) / np.maximum(a3, 0.05), 0, 255)
    return out, a


def despill(rgb, alpha, band_px=3):
    """Magenta-Stich am Rand entfernen: R und B nicht heller als G plus ihr Abstand im Inneren der Figur.
    Wirkt nur in einem Streifen von band_px Pixeln neben transparenten Stellen."""
    near = alpha < 0.98
    near = dilate(near, band_px) & (alpha > 0)
    rgb = rgb.copy()
    m = np.minimum(rgb[..., 0], rgb[..., 2])
    excess = np.where(near, np.clip(m - rgb[..., 1] - 18.0, 0, None), 0)
    rgb[..., 0] -= excess
    rgb[..., 2] -= excess
    return np.clip(rgb, 0, 255)


def polygon_mask(w, h, polys):
    im = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(im)
    for p in polys:
        d.polygon([tuple(map(float, q)) for q in p], fill=255)
    return np.asarray(im) > 0


def fill_region(rgb, hole, seed=5):
    """Übermalt die Maske hole mit einer weichen Lasur aus der Umgebung (normierte Faltung, grob nach fein) und
    leichter Körnung. Für Himmel, Wasser und ruhige Flächen (z. B. mitgemalten Rauch entfernen)."""
    known = (~hole).astype(np.float64)
    out = rgb.copy()
    ys, xs = np.nonzero(hole)
    if len(ys) == 0:
        return out
    size = max(ys.max() - ys.min(), xs.max() - xs.min()) + 1
    fill = None
    for sigma in (size / 2.0, size / 4.0, size / 8.0, 4.0):
        if sigma < 2:
            continue
        num = wc.blur(rgb * known[..., None], sigma)
        den = wc.blur(known, sigma)[..., None]
        est = num / np.maximum(den, 1e-6)
        fill = est if fill is None else np.where(den > 0.25, est, fill)
    n = wc.value_noise(rgb.shape[0], rgb.shape[1], 24, seed, 3)
    fill = fill * (0.97 + 0.06 * n)[..., None]
    soft = wc.blur(hole.astype(np.float64), 2.0)
    soft = np.maximum(soft, hole.astype(np.float64))
    return out * (1 - soft[..., None]) + fill * soft[..., None]


def best_shift(a, b, xs, ys=(0,)):
    """Verschiebung (dx, dy) aus xs × ys, bei der b (verschoben) am besten auf a passt (größte Überdeckung der
    Masken, IoU). a, b: bool-Masken gleicher Größe. Bei Gleichstand die Mitte des Plateaus."""
    scores = []
    for dy in ys:
        for dx in xs:
            bb = np.roll(np.roll(b, dy, 0), dx, 1)
            inter = (a & bb).sum()
            uni = (a | bb).sum()
            scores.append((inter / max(uni, 1), dx, dy))
    top = max(s[0] for s in scores)
    plateau = [s for s in scores if s[0] >= top - 1e-9]
    mid = plateau[len(plateau) // 2]
    return mid[1], mid[2], top
