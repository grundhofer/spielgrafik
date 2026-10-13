#!/usr/bin/env python3
"""Palette als 16x16-Raster (assets/palette_sheet.png), Bereiche farbig markiert. Nach build_sprites.py ausführen."""
import json, pathlib
from PIL import Image, ImageDraw

STYLE = pathlib.Path(__file__).resolve().parent.parent
meta = json.loads((STYLE / 'demo/art/palette.json').read_text())
pal = [tuple(int(h[k:k + 2], 16) for k in (0, 2, 4)) for h in meta['palette']]
S = 20
im = Image.new('RGB', (16 * S, 16 * S), (0, 0, 0))
d = ImageDraw.Draw(im)
for i, c in enumerate(pal):
    x, y = (i % 16) * S, (i // 16) * S
    d.rectangle([x, y, x + S - 1, y + S - 1], fill=c)
im.save(STYLE / 'assets/palette_sheet.png')
print({k: v for k, v in meta['ranges'].items()})
