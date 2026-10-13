"""Kleine Gouache-Pinselbibliothek (NumPy + Pillow) für den Eintrag bilderbuch-gouache.

Alles deterministisch über feste Seeds. Grundidee: Eine Form wird als Abstandsfeld beschrieben, der Rand mit
niederfrequentem Rauschen verbogen (wackelige, runde Bilderbuchkante) und mit in Strichrichtung gestrecktem
Rauschen aufgerissen (Trockenpinsel). Die Farbe ist deckend; Strichspuren und Papierkorn ändern nur die
Helligkeit um wenige Prozent, nicht die Deckkraft (Gouache deckt, Aquarell lasiert).
"""
import numpy as np
from PIL import Image


def noise(h, w, cell_y, cell_x, seed, octaves=1):
    """Glattes Wertrauschen 0..1 (bikubisch hochgezogenes Zufallsgitter), optional mehrere Oktaven."""
    rng = np.random.RandomState(seed)
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    cy, cx = float(cell_y), float(cell_x)
    for _ in range(octaves):
        gh, gw = max(2, int(np.ceil(h / cy)) + 3), max(2, int(np.ceil(w / cx)) + 3)
        g = rng.rand(gh, gw).astype(np.float32)
        im = Image.fromarray((g * 65535).astype(np.uint16).astype(np.int32), mode="I")
        big = im.resize((int(gw * cx), int(gh * cy)), Image.BICUBIC)
        a = np.asarray(big, np.float32)[:h, :w] / 65535.0
        out += amp * a
        tot += amp
        amp *= 0.5
        cy, cx = max(1.0, cy / 2), max(1.0, cx / 2)
    return np.clip(out / tot, 0, 1)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def ellipse_sdf(h, w, cx, cy, rx, ry):
    """Näherung: positiver Abstand innen (in px, bezogen auf den kleineren Radius)."""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    q = np.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2)
    return (1 - q) * min(rx, ry)


def roundrect_sdf(h, w, x0, y0, x1, y1, r):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    hx, hy = (x1 - x0) / 2 - r, (y1 - y0) / 2 - r
    qx, qy = np.abs(x - cx) - hx, np.abs(y - cy) - hy
    outside = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2) + np.minimum(np.maximum(qx, qy), 0)
    return -(outside - r)


def dab_alpha(sdf, seed, wobble=4.0, wobble_cell=40, streak=6.0, streak_cells=(3, 60), soft=1.2,
              holes=0.0):
    """Deckkraft einer Gouache-Fläche aus einem Abstandsfeld.

    wobble: Randverbiegung in px (runde, handgemalte Kante)
    streak: Tiefe der Trockenpinsel-Fransen in px, Rauschen mit Zellen (y, x) – x lang = waagerechte Striche
    holes:  Anteil Papierlöcher nahe am Rand (Trockenpinsel)
    """
    h, w = sdf.shape
    wob = (noise(h, w, wobble_cell, wobble_cell, seed, 2) - 0.5) * 2 * wobble
    st = noise(h, w, streak_cells[0], streak_cells[1], seed + 1, 2)
    d = sdf + wob - (1 - st) * streak
    a = smoothstep(-soft, soft, d)
    if holes > 0:
        g = noise(h, w, 2, 9, seed + 2, 1)
        near = 1 - smoothstep(0, streak * 2.5 + 1, d)
        a *= 1 - near * (g < holes).astype(np.float32) * 0.85
    return np.clip(a, 0, 1)


def paint_rgb(h, w, rgb, seed, streak_amp=0.035, grain_amp=0.03, cells=(3, 50), tint=None, tint_amp=0.0):
    """Deckende Farbfläche: Grundfarbe + Pinselspuren (gestrecktes Rauschen) + Papierkorn.
    tint: zweite Farbe, die fleckig untergemischt wird (gemischte Gouache ist nie ganz gleichmäßig)."""
    base = np.ones((h, w, 3), np.float32) * (np.array(rgb, np.float32) / 255.0)
    if tint is not None and tint_amp > 0:
        m = noise(h, w, 30, 30, seed + 7, 2)[..., None] * tint_amp
        base = base * (1 - m) + (np.array(tint, np.float32) / 255.0) * m
    s = (noise(h, w, cells[0], cells[1], seed + 3, 2) - 0.5) * 2 * streak_amp
    g = (np.random.RandomState(seed + 4).rand(h, w).astype(np.float32) - 0.5) * 2 * grain_amp
    g = np.asarray(Image.fromarray(((g + 0.5) * 255).clip(0, 255).astype(np.uint8)).resize((w, h)),
                   np.float32) / 255.0 - 0.5 if False else g
    return np.clip(base * (1 + s[..., None] + g[..., None]), 0, 1)


def to_image(rgb, a):
    arr = np.dstack([rgb, a[..., None]]) * 255
    return Image.fromarray(np.clip(arr + 0.5, 0, 255).astype(np.uint8), "RGBA")


def premul_resize(im, size):
    """RGBA vormultipliziert verkleinern (keine Farbsäume an weichen Kanten)."""
    a = np.asarray(im, np.float32) / 255.0
    pm = a.copy()
    pm[..., :3] *= pm[..., 3:4]
    big = Image.fromarray((pm * 255 + 0.5).clip(0, 255).astype(np.uint8), "RGBA")
    sm = np.asarray(big.resize(size, Image.LANCZOS), np.float32) / 255.0
    al = sm[..., 3:4]
    rgb = np.where(al > 1e-3, sm[..., :3] / np.maximum(al, 1e-3), 0)
    out = np.dstack([np.clip(rgb, 0, 1), np.clip(al, 0, 1)])
    return Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGBA")
