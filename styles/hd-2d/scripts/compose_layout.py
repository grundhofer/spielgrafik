#!/usr/bin/env python3
"""Setzt die Blender-Einzelbilder (blender/pose_layout.py) zu einem 1536×1024-Posenblatt zusammen.

Oben 8 Laufphasen (Seitenansicht nach rechts), unten 4 Vorderansichten: Stehen, Stehen (wird im Prompt zum
Blinzeln), Winken Hand außen, Winken Hand innen. Alle Figuren gleich groß, Ursprung der Figur (Mitte zwischen
den Füßen) in der Zellmitte, Füße auf einer Grundlinie je Reihe. Muster: styles/hibit-pixel/scripts/compose_layout.py.

    .venv/bin/python styles/hd-2d/scripts/compose_layout.py <renderordner> styles/hd-2d/assets/ref/pose_layout.png
"""
import json
import math
import pathlib
import sys

from PIL import Image

src, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
W, H = 1536, 1024
PX_PER_M = 480 / 1.30            # Render: ortho_scale 1,30 m auf 480 px
FIG_H = 250                      # Figurenhöhe (1,011 m) im Blatt
SCALE = FIG_H / (1.011 * PX_PER_M)
ELEV = math.radians(15.0)
ORIGIN = (240, 240 + 0.55 * math.cos(ELEV) * PX_PER_M)   # Bodenpunkt der Figur im Render
BASE = (420, 900)                # Fußlinie oben / unten im Blatt
rows = [[f"walk_{k:02d}.png" for k in range(8)],
        ["front_idle_a.png", "front_idle_a.png", "front_wave_2.png", "front_wave_3.png"]]
sheet = Image.new("RGBA", (W, H), (255, 255, 255, 255))
cells = []
for r, files in enumerate(rows):
    cell = W / len(files)
    for i, f in enumerate(files):
        im = Image.open(src / f).convert("RGBA")
        im = im.resize((round(im.width * SCALE), round(im.height * SCALE)), Image.LANCZOS)
        x = round(cell * (i + 0.5) - ORIGIN[0] * SCALE)
        y = round(BASE[r] - ORIGIN[1] * SCALE)
        sheet.alpha_composite(im, (x, y))
        cells.append({"row": r, "col": i, "src": f, "origin": [round(cell * (i + 0.5), 1), BASE[r]]})
out.parent.mkdir(parents=True, exist_ok=True)
sheet.convert("RGB").save(out)
(out.with_suffix(".json")).write_text(json.dumps({"scale_px_per_m": round(SCALE * PX_PER_M, 2),
                                                  "cells": cells}, indent=1))
print(out, sheet.size, "px/m", round(SCALE * PX_PER_M, 1))
