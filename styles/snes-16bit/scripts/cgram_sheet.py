#!/usr/bin/env python3
"""CGRAM-Übersicht (256 Einträge, 16 Paletten à 16) als Bild: assets/cgram.png.

    .venv/bin/python styles/snes-16bit/scripts/cgram_sheet.py

Zeile 0: BG3-Paletten 0..3 (Textfenster, je 4 Einträge) = zugleich 4bpp-Palette 0;
Zeilen 1..7: BG1/BG2-Paletten; Zeilen 8..10: OBJ-Paletten 0..2 (Dachs/Paket, Rauch, Möwe); Rest leer.
Index 0 jeder Palette ist durchsichtig (diagonal gestrichen), animierte Einträge haben einen weißen Rahmen.
"""
import json, pathlib, sys
import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import re  # noqa: E402

STYLE = HERE.parent
DEMO = STYLE / 'demo'


def cgram():
    cg = [None] * 256
    s = (DEMO / 'scripts/main.gd').read_text()
    fills = re.search(r'const BG3_FILL := \[(.*)\]\n', s).group(1)
    fills = [tuple(int(x) for x in g.split(',')) for g in re.findall(r'\[([\d, ]+)\]', fills)]
    light = tuple(int(x) for x in re.search(r'const BG3_LIGHT := \[([\d, ]+)\]', s).group(1).split(','))
    dark = tuple(int(x) for x in re.search(r'const BG3_DARK := \[([\d, ]+)\]', s).group(1).split(','))
    c8 = lambda v: tuple((x << 3) | (x >> 2) for x in v)  # noqa: E731
    for p, f in enumerate(fills):
        cg[4 * p + 1], cg[4 * p + 2], cg[4 * p + 3] = c8(f), c8(light), c8(dark)
    bg = json.loads((DEMO / 'art/bg.json').read_text())
    for i, h in enumerate(bg['cgram']):
        if h != '000000':
            cg[bg['cgram_first'] + i] = tuple(int(h[k:k + 2], 16) for k in (0, 2, 4))
    spr = json.loads((DEMO / 'art/sprites.json').read_text())
    for p, arr in spr['obj_palettes'].items():
        for j, h in enumerate(arr):
            cg[128 + 16 * int(p) + 1 + j] = tuple(int(h[k:k + 2], 16) for k in (0, 2, 4))
    anim = {int(i) for v in bg['lights'].values() for i in v}
    return cg, anim


if __name__ == '__main__':
    cg, anim = cgram()
    S = 14
    im = Image.new('RGB', (16 * S, 16 * S), (40, 40, 40))
    d = ImageDraw.Draw(im)
    for i, c in enumerate(cg):
        x, y = (i % 16) * S, (i // 16) * S
        if c is None:
            if i % 16 == 0 or (i < 32 and i % 4 == 0):
                d.line([(x + 2, y + 2), (x + S - 3, y + S - 3)], fill=(90, 90, 90))
            continue
        d.rectangle([x + 1, y + 1, x + S - 2, y + S - 2], fill=c)
        if i in anim:
            d.rectangle([x, y, x + S - 1, y + S - 1], outline=(255, 255, 255))
    im.resize((im.width * 2, im.height * 2), Image.NEAREST).save(STYLE / 'assets/cgram.png')
    used = sum(c is not None for c in cg)
    print(f'CGRAM: {used} von 256 Einträgen belegt, {len(anim)} animiert')
