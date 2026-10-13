#!/usr/bin/env python3
"""Übersicht der drei Paletten (Abend, Nacht, Regen) mit den Zyklus-Bereichen: assets/palette_sheet.png.

    .venv/bin/python styles/farbzyklus/scripts/palette_sheet.py
"""
import json, pathlib
from PIL import Image, ImageDraw

STYLE = pathlib.Path(__file__).resolve().parent.parent
meta = json.loads((STYLE / 'demo/art/palette.json').read_text())
CELL, ROWH, LAB = 4, 18, 64
names = [('evening', 'Abend'), ('night', 'Nacht'), ('rain', 'Regen')]
W = LAB + 256 * CELL
H = 4 + len(names) * (ROWH + 4) + 46
im = Image.new('RGB', (W, H), (24, 22, 30))
d = ImageDraw.Draw(im)
for r, (key, label) in enumerate(names):
    y = 4 + r * (ROWH + 4)
    d.text((4, y + 4), label, fill=(230, 230, 230))
    for i, h in enumerate(meta['palettes'][key]):
        c = tuple(int(h[k:k + 2], 16) for k in (0, 2, 4))
        d.rectangle([LAB + i * CELL, y, LAB + i * CELL + CELL - 1, y + ROWH - 1], fill=c)
y = 4 + len(names) * (ROWH + 4) + 2
cols = [(240, 200, 90), (120, 200, 255)]
for k, (name, (s, e)) in enumerate(meta['ranges_alloc'].items()):
    col = cols[k % 2]
    d.rectangle([LAB + s * CELL, y, LAB + e * CELL - 2, y + 3], fill=col)
    d.text((LAB + s * CELL, y + 6 + (k % 3) * 12), name, fill=col)
im.save(STYLE / 'assets/palette_sheet.png')
print('assets/palette_sheet.png', im.size)
