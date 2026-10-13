#!/usr/bin/env python3
"""Setzt die Blender-Einzelbilder (blender/walk_layout.py) zu einem 1536×1024-Posenblatt zusammen.

Oben 8 Laufphasen, unten 4 Stehbilder; alle Figuren gleich groß, am Ursprung der Figur (Mitte zwischen den
Füßen, Laufen auf der Stelle) in der Zellmitte, Füße auf einer Grundlinie je Reihe. Das Blatt dient
genimg.py als Layout-Referenz.

    .venv/bin/python styles/hibit-pixel/scripts/compose_layout.py <renderordner> styles/hibit-pixel/assets/ref/pose_layout.png
"""
import pathlib, sys

from PIL import Image

src, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
W, H = 1536, 1024
FIG_H = 250            # Figurenhöhe im Blatt (Render: 372 px)
SCALE = FIG_H / 372.0
BASE = (400, 880)      # Fußlinie oben / unten
sheet = Image.new("RGBA", (W, H), (255, 255, 255, 255))
rows = [sorted(src.glob("walk_*.png")), sorted(src.glob("idle_*.png"))]
for r, files in enumerate(rows):
    cell = W / len(files)
    for i, f in enumerate(files):
        im = Image.open(f).convert("RGBA")
        im = im.resize((round(im.width * SCALE), round(im.height * SCALE)), Image.LANCZOS)
        # Render: Ursprung der Figur bei x = 240 (Bildmitte), Boden bei y = 460 (480er-Bild)
        ox, oy = 240 * SCALE, 460 * SCALE
        x = round(cell * (i + 0.5) - ox)
        y = round(BASE[r] - oy)
        sheet.alpha_composite(im, (x, y))
out.parent.mkdir(parents=True, exist_ok=True)
sheet.convert("RGB").save(out)
print(out, sheet.size)
