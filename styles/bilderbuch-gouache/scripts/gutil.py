"""Hilfsfunktionen für den Eintrag bilderbuch-gouache (NumPy + Pillow, ohne SciPy)."""
from collections import deque

import numpy as np
from PIL import Image


def label(mask):
    """Zusammenhangskomponenten (8er-Nachbarschaft). Gibt (labels, Anzahl) zurück, Label 0 = Hintergrund."""
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    n = 0
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys, xs):
        if lab[y0, x0]:
            continue
        n += 1
        lab[y0, x0] = n
        q = deque([(y0, x0)])
        while q:
            y, x = q.popleft()
            for dy in (-1, 0, 1):
                yy = y + dy
                if yy < 0 or yy >= h:
                    continue
                for dx in (-1, 0, 1):
                    xx = x + dx
                    if 0 <= xx < w and mask[yy, xx] and not lab[yy, xx]:
                        lab[yy, xx] = n
                        q.append((yy, xx))
    return lab, n


def bbox(a, thr=0):
    ys, xs = np.nonzero(a > thr)
    if len(ys) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def premul_resize(im, size, resample=Image.LANCZOS):
    """RGBA vormultipliziert skalieren (keine Farbsäume an weichen Kanten)."""
    a = np.asarray(im.convert("RGBA"), np.float32) / 255.0
    pm = a.copy()
    pm[..., :3] *= pm[..., 3:4]
    big = Image.fromarray((pm * 255 + 0.5).clip(0, 255).astype(np.uint8), "RGBA")
    sm = np.asarray(big.resize(size, resample), np.float32) / 255.0
    al = sm[..., 3:4]
    rgb = np.where(al > 1e-3, sm[..., :3] / np.maximum(al, 1e-3), 0)
    out = np.dstack([np.clip(rgb, 0, 1), np.clip(al, 0, 1)])
    return Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGBA")


def bleed_rgb(im, iters=8):
    """Farbe deckender Randpixel in die transparente Umgebung ausbreiten (gegen dunkle/magenta Säume beim
    linearen Filtern); Alpha bleibt unverändert."""
    a = np.asarray(im.convert("RGBA"), np.float32)
    rgb, al = a[..., :3].copy(), a[..., 3]
    known = al > 0
    for _ in range(iters):
        acc = np.zeros_like(rgb)
        cnt = np.zeros(al.shape, np.float32)
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
            k = np.roll(np.roll(known, dy, 0), dx, 1)
            c = np.roll(np.roll(rgb, dy, 0), dx, 1)
            acc += c * k[..., None]
            cnt += k
        new = (~known) & (cnt > 0)
        rgb[new] = acc[new] / cnt[new][:, None]
        known = known | new
    return Image.fromarray(np.dstack([rgb, al]).clip(0, 255).astype(np.uint8), "RGBA")
