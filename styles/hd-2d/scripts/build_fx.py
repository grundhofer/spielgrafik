#!/usr/bin/env python3
"""Kleine Effekt-Sprites für hd-2d, im selben Pixelraster wie Figur und Requisiten (Code, keine KI).

    .venv/bin/python styles/hd-2d/scripts/build_fx.py

smoke.png: 4 Stufen eines Rauchwölkchens (je 32×32 px nebeneinander): wächst, wird zum Schluss geordnet
ausgedünnt (Bayer 4×4), damit es ohne Halbtransparenz verschwindet (Sprites nutzen Alpha-Schnitt).
Drei Töne, Licht von links oben (wie die KI-Sprites), keine Kontur.
"""
import pathlib
import shutil

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
FW = 32
TONES = [(196, 186, 204), (150, 140, 166), (104, 98, 124)]   # hell, mittel, dunkel (Lila-Grau der Dämmerung)
BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0


def puff(radius, keep):
    yy, xx = np.mgrid[0:FW, 0:FW] + 0.5
    c = FW / 2
    blobs = [(c, c + 0.5, radius), (c - radius * 0.55, c + radius * 0.25, radius * 0.7),
             (c + radius * 0.5, c + radius * 0.35, radius * 0.65)]
    inside = np.zeros((FW, FW), bool)
    shade = np.full((FW, FW), 9.0)
    for bx, by, r in blobs:
        d = np.hypot(xx - bx, yy - by)
        m = d <= r
        inside |= m
        # Licht von links oben: Abstand zu einem Punkt oben links im Blob
        s = np.hypot(xx - (bx - r * 0.45), yy - (by - r * 0.45)) / (r * 1.4)
        shade = np.where(m, np.minimum(shade, s), shade)
    img = np.zeros((FW, FW, 4), np.uint8)
    tone = np.where(shade < 0.45, 0, np.where(shade < 0.85, 1, 2))
    for k, col in enumerate(TONES):
        sel = inside & (tone == k)
        img[sel, :3] = col
        img[sel, 3] = 255
    if keep < 1.0:
        thin = np.tile(BAYER, (FW // 4, FW // 4)) >= keep
        img[thin, 3] = 0
    return img


def main():
    frames = [puff(4.0, 1.0), puff(6.8, 1.0), puff(9.5, 0.75), puff(11.5, 0.4)]
    sheet = np.concatenate(frames, axis=1)
    out_a = ROOT / "assets" / "fx"
    out_a.mkdir(parents=True, exist_ok=True)
    Image.fromarray(sheet, "RGBA").save(out_a / "smoke.png")
    shutil.copy(out_a / "smoke.png", ROOT / "demo" / "sprites" / "smoke.png")
    print("smoke.png", sheet.shape)


if __name__ == "__main__":
    main()
