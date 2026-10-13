#!/usr/bin/env python3
"""Lage der Teile auf dem KI-Blatt relativ zur zusammengesetzten Vorlage (links auf dem Blatt).

    .venv/bin/python -I styles/prozedurale-animation/scripts/pa_align.py

Körper: Kopfbereich (Blattzeilen 75–290) gegen die Vorlage verschoben, kleinste mittlere Farbabweichung
plus Strafterm für ungleiche Deckung. Bein: unterste 110 Zeilen (Pfote) gegen das nahe Bein der Vorlage.
Ergebnis (Stand 13.10.2026): Körper (-585, -15), Bein (-932, 14); in prep_assets.py fest eingetragen.
"""
import pathlib, sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pa_cc import components  # noqa: E402

a = np.asarray(Image.open(HERE.parent / "assets" / "raw" / "badger.png").convert("RGBA")).astype(np.float32)
cs = components(a[..., 3].astype(np.uint8))
(mA, bA), (mB, bB), (mL, bL) = cs[0], cs[1], cs[2]


def best(tm, tpl, y0, y1, x0, x1, dxs, dys, wpen, min_px):
    res = None
    for dy in dys:
        for dx in dxs:
            reg = a[y0 + dy:y1 + dy, x0 + dx:x1 + dx]
            rm = mA[y0 + dy:y1 + dy, x0 + dx:x1 + dx]
            m = tm & rm
            if m.sum() < min_px:
                continue
            d = np.abs(reg[..., :3] - tpl[..., :3]).sum(-1)[m].mean() + wpen * (tm ^ rm).mean()
            if res is None or d < res[0]:
                res = (float(d), dx, dy)
    return res


x0, _, x1, _ = bB
body = best(mB[75:290, x0:x1], a[75:290, x0:x1], 75, 290, x0, x1, range(-640, -520), range(-60, 61), 200, 1000)
lx0, _, lx1, ly1 = bL
ty0 = ly1 - 110
leg = best(mL[ty0:ly1, lx0:lx1], a[ty0:ly1, lx0:lx1], ty0, ly1, lx0, lx1, range(-1100, -700, 2), range(-60, 40, 2), 300, 2000)
print({"body_to_assembled": body[1:], "body_err": round(body[0], 1), "leg_to_assembled": leg[1:], "leg_err": round(leg[0], 1)})
