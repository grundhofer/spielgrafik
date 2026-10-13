"""Hilfsfunktionen für den Eintrag gummischlauch (nur NumPy und Pillow)."""
from collections import deque

import numpy as np
from PIL import Image


def load_rgba(path):
    return np.asarray(Image.open(path).convert("RGBA")).astype(np.float32) / 255.0


def clean_alpha(a, lo=16 / 255, hi=230 / 255):
    """Codex legt einen schwachen Schein (Alpha ≤ 0,04) um jedes Teil; die eigentliche Kante springt in 1–2 px
    von etwa 0,02 auf 0,94. Schein weg, Kante behalten, Deckendes auf 1."""
    return np.clip((a - lo) / (hi - lo), 0.0, 1.0)


def label(mask, min_px=200):
    """Zusammenhangskomponenten (8er-Nachbarschaft) per Breitensuche. Liefert Liste von
    (Pixelzahl, (x0, y0, x1, y1), Maske) nach Größe sortiert."""
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    comps = []
    ys, xs = np.nonzero(mask)
    n = 0
    for y0, x0 in zip(ys, xs):
        if lab[y0, x0]:
            continue
        n += 1
        q = deque([(y0, x0)])
        lab[y0, x0] = n
        pts = []
        while q:
            y, x = q.popleft()
            pts.append((y, x))
            for dy in (-1, 0, 1):
                yy = y + dy
                if yy < 0 or yy >= h:
                    continue
                for dx in (-1, 0, 1):
                    xx = x + dx
                    if 0 <= xx < w and mask[yy, xx] and not lab[yy, xx]:
                        lab[yy, xx] = n
                        q.append((yy, xx))
        if len(pts) < min_px:
            continue
        p = np.array(pts)
        comps.append((len(pts), (int(p[:, 1].min()), int(p[:, 0].min()), int(p[:, 1].max()) + 1,
                                 int(p[:, 0].max()) + 1), n))
    comps.sort(key=lambda c: -c[0])
    return lab, comps


def premul_resize(rgba, size):
    """Vormultipliziert mit Lanczos verkleinern (keine dunklen oder hellen Säume)."""
    rgb, a = rgba[..., :3], rgba[..., 3:4]
    pm = np.concatenate([rgb * a, a], axis=2)
    out = []
    for c in range(4):
        im = Image.fromarray(pm[..., c].astype(np.float32), mode="F")
        out.append(np.asarray(im.resize(size, Image.LANCZOS)))
    pm2 = np.clip(np.stack(out, axis=2), 0.0, 1.0)
    a2 = pm2[..., 3:4]
    rgb2 = np.where(a2 > 1e-4, pm2[..., :3] / np.maximum(a2, 1e-4), 0.0)
    return np.concatenate([np.clip(rgb2, 0, 1), a2], axis=2)


def save_rgba(arr, path):
    Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(path)


def bleed(rgba, iters=6):
    """Farbe deckender Pixel in die durchsichtigen Nachbarn ausbreiten (gegen dunkle Säume beim Filtern;
    Alpha bleibt unverändert)."""
    rgb = rgba[..., :3].copy()
    known = rgba[..., 3] > 0.02
    for _ in range(iters):
        acc = np.zeros_like(rgb)
        cnt = np.zeros(known.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            k = np.roll(known, (dy, dx), (0, 1))
            acc += np.roll(rgb, (dy, dx), (0, 1)) * k[..., None]
            cnt += k
        new = (~known) & (cnt > 0)
        rgb[new] = acc[new] / cnt[new][:, None]
        known = known | new
    out = rgba.copy()
    out[..., :3] = rgb
    return out
