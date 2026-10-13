#!/usr/bin/env python3
"""Vergleicht die Schrift im Godot-Bild Pixel für Pixel mit einer zweiten Rasterung derselben TTF (Pillow,
fontmode "1", Grundlinie wie in ui.gd). Aufruf mit einem Einzelbild in 400×240 (z. B. aus probe.py --keep):

    .venv/bin/python styles/einbit-pixel/scripts/check_font.py <bild.png>
"""
import pathlib, sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[1]
F = ImageFont.truetype(str(ROOT / "demo" / "fonts" / "PixelOperator.ttf"), 16)
B = ImageFont.truetype(str(ROOT / "demo" / "fonts" / "PixelOperator-Bold.ttf"), 16)
TEXTS = [(F, 10, 207, "Die Laterne flackert im Wind."), (F, 10, 219, "Am Kai wartet ein Paket auf dich."),
         (F, 10, 231, "> nimm paket"), (F, 241, 207, "Zum Leuchtturm gehen"), (F, 241, 219, "Das Paket ansehen")]

img = np.asarray(Image.open(sys.argv[1]).convert("L")) < 128
total_bad = 0
for font, x, base, s in TEXTS:
    ref = Image.new("1", (400, 240), 0)
    d = ImageDraw.Draw(ref)
    d.fontmode = "1"
    d.text((x, base), s, font=font, fill=1, anchor="ls")
    r = np.asarray(ref, bool)
    ys, xs = np.where(r)
    box = (slice(ys.min(), ys.max() + 1), slice(xs.min(), xs.max() + 1))
    bad = int((r[box] != img[box]).sum())
    best = min(((int((np.roll(np.roll(r, dy, 0), dx, 1)[box] != img[box]).sum()), dx, dy)
                for dy in (-1, 0, 1) for dx in (-1, 0, 1)))
    total_bad += bad
    print(f"{s!r}: {bad} abweichende Pixel; bester Versatz {best[1]:+d}/{best[2]:+d} mit {best[0]}")
print("gesamt", total_bad)
