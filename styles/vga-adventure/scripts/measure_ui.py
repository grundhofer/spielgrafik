#!/usr/bin/env python3
"""Verbleiste nachmessen: Tintenausdehnung je Verb, Abstände zwischen den Spalten, zum Pfeil und zum Inventar.

    .venv/bin/python styles/vga-adventure/scripts/measure_ui.py BILD.png   (Basisauflösung 320x200 oder Leiste 320x48)

Liest die Farben aus demo/art/palette.json (ui_colors) und die Spalten (COL_X, ARROW_X, SLOT_X) aus
demo/scripts/ui.gd; Tinte zwischen zwei Spaltenanfängen gehört zur linken Spalte. Hinweis: Die Schrift setzt
ein Wortleerzeichen 6 px breit; Spaltenabstände darunter lesen sich als Wortabstand.
"""
import json, pathlib, re, sys
import numpy as np
from PIL import Image

STYLE = pathlib.Path(__file__).resolve().parent.parent
meta = json.loads((STYLE / 'demo/art/palette.json').read_text())
pal = meta['palette']
ui = meta['ui_colors']
col = lambda n: np.array([int(pal[ui[n]][k:k + 2], 16) for k in (0, 2, 4)])
im = np.asarray(Image.open(sys.argv[1]).convert('RGB')).astype(int)
if im.shape[0] == 200:
    im = im[152:]
verb = ((im == col('verb')).all(-1) | (im == col('verb_hell')).all(-1))
frame = (im == col('rahmen')).all(-1)
gd = (STYLE / 'demo/scripts/ui.gd').read_text()
cols = [int(v) for v in re.search(r'const COL_X := \[([^\]]*)\]', gd).group(1).split(',')]
arrow_x = int(re.search(r'const ARROW_X := (\d+)', gd).group(1))
slot_x = int(re.search(r'const SLOT_X := (\d+)', gd).group(1))
bounds = cols + [arrow_x - 2]
ext = [[999, -1] for _ in cols]
for y0, y1 in ((9, 21), (21, 33), (33, 45)):
    for c in range(len(cols)):
        xs = np.flatnonzero(verb[y0:y1, bounds[c]:bounds[c + 1]].any(0)) + bounds[c]
        if len(xs):
            ext[c] = [min(ext[c][0], xs.min()), max(ext[c][1], xs.max())]
arrow = np.flatnonzero(frame[:, arrow_x - 6:arrow_x + 7].any(0)) + arrow_x - 6
inv = np.flatnonzero(frame[9:, slot_x - 2:].any(0)) + slot_x - 2
print('Verbspalten (Tinte):', ', '.join(f'{a}-{b}' for a, b in ext))
gaps = [ext[i + 1][0] - ext[i][1] - 1 for i in range(len(ext) - 1)]
print('Abstand zwischen Verbspalten:', gaps)
print(f'Pfeil {arrow.min()}-{arrow.max()}, Abstand letzte Spalte -> Pfeil {arrow.min() - ext[-1][1] - 1}, '
      f'Pfeil -> Inventar {inv.min() - arrow.max() - 1}')
print(f'Inventar {inv.min()}-{inv.max()}, Rand links {ext[0][0]}, rechts {im.shape[1] - 1 - inv.max()}')
