#!/usr/bin/env python3
"""Vorschau einzelner Grafiken aus art.py: vergrößert auf drei Untergründen (Kai, Meer, Himmel).

    ../../.venv/bin/python scripts/preview_art.py <out.png> NAME [NAME …]   (NAME z. B. BADGER:stand, BARREL)
"""
import sys, pathlib
from PIL import Image
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import art
from p8pal import PAL

def get(name):
    if name.startswith("BADGER:"):
        return art.badger_frame(name.split(":")[1])
    if ":" in name:
        n, i = name.split(":")
        return getattr(art, n)[int(i)]
    return getattr(art, name)

def main():
    out, names = sys.argv[1], sys.argv[2:]
    items = [get(n) for n in names]
    bgs = [6, 1, 14]
    k = 10
    W = sum(max(len(r) for r in it) + 3 for it in items) + 2
    H = max(len(it) for it in items) + 4
    canvas = Image.new("RGB", (W * k, H * k * len(bgs)), (0, 0, 0))
    for bi, bg in enumerate(bgs):
        tile = Image.new("RGB", (W, H), PAL[bg])
        px = tile.load()
        x = 2
        for it in items:
            for y, row in enumerate(it):
                for xx, ch in enumerate(row):
                    if ch != ".":
                        px[x + xx, 2 + y] = PAL[int(ch, 16)]
            x += max(len(r) for r in it) + 3
        canvas.paste(tile.resize((W * k, H * k), Image.NEAREST), (0, bi * H * k))
    canvas.save(out)

main()
