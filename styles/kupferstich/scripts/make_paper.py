#!/usr/bin/env python3
"""Altes Buchpapier mit Plattenrand (1280x720) für die Demo, ganz aus Code (fester Seed).

    .venv/bin/python styles/kupferstich/scripts/make_paper.py

Papier: warmer Grundton, wolkige Fleckung, zum Rand hin nachgedunkelt, Fasern, Korn, einige Stockflecken.
Plattenrand: Die Kupferplatte presst sich beim Drucken ins feuchte Papier. Innerhalb der Plattenkante liegt ein
leichter Plattenton (Farbfilm, den das Auswischen auf der Platte lässt), an der Kante eine Prägung mit Schatten
oben/links innen und Licht unten/rechts innen (Licht von links oben), dazu ein feiner Farbrest in der Facette.
Ergebnis: assets/paper.png (und Kopie demo/art/paper.png).
"""
import shutil

import numpy as np
from PIL import Image, ImageDraw

import inklib as K

W, H = 1280, 720
PAPER = np.array([234, 223, 199], np.float32) / 255.0
TONED = np.array([214, 196, 160], np.float32) / 255.0   # nachgedunkelter Rand
FOX = np.array([176, 128, 82], np.float32) / 255.0      # Stockflecken


def main():
    lay = K.LAYOUT
    rng = np.random.default_rng(1871)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)

    # Wolkige Fleckung und Rand
    mott = K.fbm(H, W, [180, 90, 40, 16], rng, [1.0, 0.7, 0.45, 0.25])
    ex = np.minimum(xx, W - 1 - xx) / 60.0
    ey = np.minimum(yy, H - 1 - yy) / 60.0
    edge = np.clip(1.0 - np.minimum(ex, ey), 0, 1) ** 2
    vig = ((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2
    tone = np.clip(0.10 * vig + 0.55 * edge + 0.9 * mott, 0, 1)
    rgb = PAPER[None, None] * (1 - tone[..., None]) + TONED[None, None] * tone[..., None]

    # Fasern: kurze, leicht gebogene Striche, mal heller, mal dunkler
    fib = Image.new("L", (W, H), 128)
    d = ImageDraw.Draw(fib)
    for _ in range(2600):
        x, y = rng.random() * W, rng.random() * H
        ang = rng.random() * np.pi
        ln = 4 + rng.random() * 14
        bend = (rng.random() - 0.5) * 0.6
        pts = []
        for k in range(5):
            s = (k / 4 - 0.5) * ln
            a = ang + bend * (k / 4 - 0.5)
            pts.append((x + np.cos(a) * s, y + np.sin(a) * s))
        v = 128 + int(rng.choice([-1, 1]) * (6 + rng.random() * 10))
        d.line(pts, fill=v, width=1)
    fibers = (np.asarray(fib, np.float32) - 128) / 255.0
    fibers = K.blur(fibers, 0.6)
    grain = (rng.random((H, W)).astype(np.float32) - 0.5) * 0.022
    lumv = fibers * 0.9 + grain
    rgb = rgb * (1 + lumv[..., None])

    # Stockflecken (häufiger am Rand, nicht in der Bildplatte)
    px, py, pw, ph = lay["plate_mark"]
    fox = np.zeros((H, W), np.float32)
    n = 0
    while n < 26:
        x, y = rng.random() * W, rng.random() * H
        if px - 4 < x < px + pw + 4 and py - 4 < y < py + ph + 4:
            continue
        near = min(x, W - x, y, H - y)
        if rng.random() > np.exp(-near / 140.0) + 0.15:
            continue
        r = 0.8 + rng.random() ** 2 * 4.5
        dist = np.sqrt((xx - x) ** 2 + (yy - y) ** 2)
        fox = np.maximum(fox, np.clip(1 - dist / r, 0, 1) * (0.35 + 0.4 * rng.random()))
        halo = np.clip(1 - dist / (r * 4), 0, 1) ** 2 * 0.12
        fox = np.maximum(fox, halo)
        n += 1
    rgb = rgb * (1 - fox[..., None]) + FOX[None, None] * fox[..., None]

    # Plattenrand
    inside = (xx >= px) & (xx < px + pw) & (yy >= py) & (yy < py + ph)
    rgb[inside] *= np.array([0.975, 0.971, 0.965], np.float32)
    bev = 2
    top = inside & (yy < py + bev)
    left = inside & (xx < px + bev)
    bottom = inside & (yy >= py + ph - bev)
    right = inside & (xx >= px + pw - bev)
    rgb[top | left] *= 0.94
    rgb[(bottom | right) & ~(top | left)] = np.minimum(rgb[(bottom | right) & ~(top | left)] * 1.035, 1.0)
    edge_line = (((np.abs(xx - px) < 1) | (np.abs(xx - (px + pw - 1)) < 1)) & (yy >= py) & (yy < py + ph)) | \
                (((np.abs(yy - py) < 1) | (np.abs(yy - (py + ph - 1)) < 1)) & (xx >= px) & (xx < px + pw))
    rgb[edge_line] *= 0.90
    # Farbrest knapp außerhalb der Facette, unregelmäßig
    wipe = K.value_noise(H, W, 7, rng)
    outer = (~inside) & (xx >= px - 2) & (xx < px + pw + 2) & (yy >= py - 2) & (yy < py + ph + 2)
    rgb[outer] *= (0.93 + 0.06 * wipe[outer])[:, None]

    out = K.SD / "assets/paper.png"
    Image.fromarray(np.clip(rgb * 255 + 0.5, 0, 255).astype(np.uint8)).save(out)
    (K.SD / "demo/art").mkdir(parents=True, exist_ok=True)
    shutil.copy(out, K.SD / "demo/art/paper.png")
    print("ok", out)


if __name__ == "__main__":
    main()
