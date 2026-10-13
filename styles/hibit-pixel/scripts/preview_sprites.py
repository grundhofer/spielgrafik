#!/usr/bin/env python3
"""Vorschau: Sprite-Streifen vergrößert auf grauem Grund (mit Zellgrenzen), zum Ansehen der Einzelbilder.

    .venv/bin/python styles/hibit-pixel/scripts/preview_sprites.py in.png out.png [--cell 48] [--zoom 6]
"""
import argparse
from PIL import Image, ImageDraw

ap = argparse.ArgumentParser()
ap.add_argument("inp"); ap.add_argument("out")
ap.add_argument("--cell", type=int, default=48); ap.add_argument("--zoom", type=int, default=6)
ap.add_argument("--bg", default="5a6e7a")
a = ap.parse_args()
im = Image.open(a.inp).convert("RGBA")
bg = Image.new("RGBA", im.size, "#" + a.bg)
bg.alpha_composite(im)
big = bg.resize((im.width * a.zoom, im.height * a.zoom), Image.NEAREST)
d = ImageDraw.Draw(big)
for x in range(0, im.width, a.cell):
    d.line([(x * a.zoom, 0), (x * a.zoom, big.height)], fill=(255, 255, 0, 255))
big.convert("RGB").save(a.out)
print(a.out, big.size)
