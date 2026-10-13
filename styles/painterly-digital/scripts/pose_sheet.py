#!/usr/bin/env python3
"""Setzt die Blender-Posen (assets/raw/poses/*.png) zu einem Layout-Blatt 1536x1024 auf Magenta zusammen:
Reihe 1: Laufphasen 0-3 + Stehen (Seite), Reihe 2: Laufphasen 4-7 + Stehen (Dreiviertel). Zellen 307x512.
Dient nur als Posen-/Layout-Referenz für agy."""
import pathlib
from PIL import Image

S = pathlib.Path(__file__).resolve().parent.parent
P = S / "assets" / "raw" / "poses"
order = [["walk_0", "walk_1", "walk_2", "walk_3", "stand_side"],
         ["walk_4", "walk_5", "walk_6", "walk_7", "stand_threequarter"]]
sheet = Image.new("RGBA", (1536, 1024), (255, 0, 255, 255))
for r, row in enumerate(order):
    for c, name in enumerate(row):
        im = Image.open(P / f"{name}.png").convert("RGBA")
        sheet.alpha_composite(im, (c * 307 + (307 - im.width) // 2, r * 512))
sheet.convert("RGB").save(S / "assets" / "raw" / "pose_layout.png")
print("ok", S / "assets" / "raw" / "pose_layout.png")
