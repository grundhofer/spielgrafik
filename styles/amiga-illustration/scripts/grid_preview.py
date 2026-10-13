"""Hilfsbild zum Ablesen von Koordinaten für assets/ai_layout.json: KI-Bild auf 320 Breite, Ausschnitt ab
crop_y, 4-fach vergrößert mit 10-px-Raster und Beschriftung; optional Masken farbig darüber.

    .venv/bin/python styles/amiga-illustration/scripts/grid_preview.py OUT.png [--crop-y 30] [--full] [--masks]
"""
import argparse
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
STYLE = HERE.parent

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--image", default=str(STYLE / "assets/raw/bg.png"))
ap.add_argument("--crop-y", type=int, default=0)
ap.add_argument("--full", action="store_true", help="ganzes Bild auf 320 Breite statt Ausschnitt")
ap.add_argument("--masks", action="store_true")
ap.add_argument("--zoom", type=int, default=4)
a = ap.parse_args()
im = Image.open(a.image).convert("RGB")
h = round(320 * im.height / im.width)
small = im.resize((320, h), Image.BOX)
if a.masks:
    from load_ai import load_ai
    rgb, m = load_ai(a.image)
    base = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))
    arr = np.asarray(base).astype(float)
    for key, col in (("water", (0, 120, 255)), ("lamp", (255, 255, 0)), ("lantern", (255, 128, 0)),
                     ("window", (255, 0, 255)), ("sky", (0, 255, 0))):
        mk = m[key]
        a_ = 0.15 if key == "sky" else 0.5
        arr[mk] = arr[mk] * (1 - a_) + np.array(col) * a_
    small = Image.fromarray(arr.astype(np.uint8))
elif not a.full:
    small = small.crop((0, a.crop_y, 320, a.crop_y + 144))
z = a.zoom
big = small.resize((small.width * z, small.height * z), Image.NEAREST)
d = ImageDraw.Draw(big)
for x in range(0, small.width, 10):
    d.line([(x * z, 0), (x * z, big.height)], fill=(255, 255, 255) if x % 50 == 0 else (90, 90, 90))
    if x % 50 == 0:
        d.text((x * z + 2, 2), str(x), fill=(255, 255, 0))
for y in range(0, small.height, 10):
    d.line([(0, y * z), (big.width, y * z)], fill=(255, 255, 255) if y % 50 == 0 else (90, 90, 90))
    d.text((2, y * z + 2), str(y), fill=(255, 255, 0))
big.save(a.out)
print(small.size)
