#!/usr/bin/env python3
"""Kleine 1-Bit-Sprites aus Code: Möwe mit drei Flügelstellungen (oben, Mitte, unten), weiß mit
Gegenkontur wie der Dachs (an Weiß ein Tintenpixel), damit sie vor dunklem Himmel und hellem Glutband steht.

    .venv/bin/python styles/einbit-pixel/scripts/build_fx.py
"""
import pathlib, sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build_badger import contrast_rim, PAPER  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
GULL = ["""
.     .
.     .
 .   .
  ...
""", """

..   ..
  ...

""", """

  ...
 .   .
.     .
"""]


def frame(art, w=11, h=8):
    rows = art.strip("\n").split("\n") if art.strip("\n") else []
    lines = art.split("\n")[1:-1]
    op = np.zeros((h, w), bool)
    for r, line in enumerate(lines):
        for k, ch in enumerate(line):
            if ch == ".":
                op[r + 2, k + 2] = True
    px = np.full((h, w), PAPER, np.uint8)
    return contrast_rim(op, px)


def main():
    strip = np.concatenate([frame(a) for a in GULL], axis=1)
    for p in (ROOT / "demo" / "art" / "gull.png", ROOT / "assets" / "gull.png"):
        Image.fromarray(strip, "RGBA").save(p)
    print("gull", strip.shape)


if __name__ == "__main__":
    main()
