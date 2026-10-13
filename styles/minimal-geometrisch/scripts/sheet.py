#!/usr/bin/env python3
"""Kontaktbogen aus gerenderten Einzelbildern (Sichtprüfung während des Baus).

    .venv/bin/python scripts/sheet.py <Bildordner> <ziel.jpg> [Bildnummern ...]
"""
import pathlib, sys
from PIL import Image, ImageDraw

src, dst = pathlib.Path(sys.argv[1]), sys.argv[2]
idx = [int(x) for x in sys.argv[3:]] or [0, 25, 51, 77, 102, 128, 153, 179]
tw, th = 640, 360
cols = 4
rows = (len(idx) + cols - 1) // cols
sheet = Image.new("RGB", (tw * cols, th * rows), "black")
d = ImageDraw.Draw(sheet)
for k, i in enumerate(idx):
    im = Image.open(src / f"f{i:08d}.png").convert("RGB").resize((tw, th), Image.LANCZOS)
    x, y = (k % cols) * tw, (k // cols) * th
    sheet.paste(im, (x, y))
    d.rectangle([x, y, x + 70, y + 16], fill="black")
    d.text((x + 4, y + 2), f"#{i} {i / 30:.2f}s", fill="white")
sheet.save(dst, quality=88)
