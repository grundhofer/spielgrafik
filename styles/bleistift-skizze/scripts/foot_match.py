#!/usr/bin/env python3
"""Hilfsmessung für die Vorschubtabelle: vergleicht je Bildwechsel die untersten Zeilen (Bodenkontakt) zweier
Laufbilder bei verschiedenen Verschiebungen und gibt die Kurve aus. Koordinaten je Bild: x relativ zur linken
Kante des Hüllrechtecks im KI-Bogen, Sohle auf gemeinsamer Zeile.

    .venv/bin/python styles/bleistift-skizze/scripts/foot_match.py [rows]
"""
import json, pathlib, sys
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
cells = json.loads((ROOT / "assets/sheet_cells.json").read_text())
A = np.asarray(Image.open(ROOT / "assets/raw/walk.png").convert("RGBA"))[..., 3] > 100
A = np.pad(A, ((0, 0), (0, 300)))
ROWS = int(sys.argv[1]) if len(sys.argv) > 1 else 8
W = 260


def band(c, rows):
    x0 = c["box"][0]
    sy = c["sole_y"]
    return A[sy - rows + 1:sy + 1, x0:x0 + W]


def head_x(c):
    x0, y0, x1, y1 = c["box"]
    ys, xs = np.nonzero(A[y0:y0 + 75, x0:x1])
    return xs.mean()


walk = cells[:8]
for i in range(8):
    a, b = walk[i], walk[(i + 1) % 8]
    ba, bb = band(a, ROWS), band(b, ROWS)
    scores = {}
    for dx in range(-60, 61):
        # Bild b um dx verschoben gegen Bild a: Bodenpunkt x in a entspricht x - dx in b
        sh = np.roll(bb, dx, 1)
        if dx > 0:
            sh[:, :dx] = False
        elif dx < 0:
            sh[:, dx:] = False
        inter, union = (ba & sh).sum(), (ba | sh).sum()
        scores[dx] = round(float(inter) / max(1, union), 3)
    best = sorted(scores.items(), key=lambda kv: -kv[1])[:4]
    # dx = Fußlage in a minus Fußlage in b (lokal); Vorschub der Figur = dx
    hb = head_x(b) + best[0][0]
    print(f"{a['name']}->{b['name']}: best dx {best}  head a={head_x(a):.1f} head b(at a)={hb:.1f} -> body moves {hb - head_x(a):+.1f}")
