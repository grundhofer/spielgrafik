#!/usr/bin/env python3
"""Übersichten aus demo/rom/rom.json für den Katalog: Musterspeicher (alle 1-KB-Bänke, in Graustufen),
Sprite-Kacheln in ihren Paletten, Paletten-RAM. Ausgabe nach assets/."""
import json, pathlib, sys
import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent
sys.path.insert(0, str(HERE))
import neslib  # noqa: E402

rom = json.loads((ENTRY / "demo" / "rom" / "rom.json").read_text())
nb = len(rom["chr"])
tiles = []
for b in range(nb):
    raw = bytes.fromhex(rom["chr"][b])
    for i in range(64):
        tiles.append(neslib.bytes_tile(raw[i * 16:(i + 1) * 16]))
# Musterspeicher: je Bank 16x4 Kacheln, Bänke untereinander in zwei Spalten
grey = np.array([[0, 0, 0], [85, 85, 85], [170, 170, 170], [255, 255, 255]], np.uint8)
cols = 2
rows = (nb + 1) // cols
img = np.zeros((rows * 34, cols * 130, 3), np.uint8) + 40
for b in range(nb):
    ox, oy = (b % cols) * 130 + 1, (b // cols) * 34 + 1
    for i in range(64):
        t = tiles[b * 64 + i]
        y, x = oy + (i // 16) * 8, ox + (i % 16) * 8
        img[y:y + 8, x:x + 8] = grey[t]
Image.fromarray(img).resize((img.shape[1] * 2, img.shape[0] * 2), Image.NEAREST).save(ENTRY / "assets" / "chr_banks.png")
# Sprite-Kacheln (Bänke ab rom.banks.sprites) in Sprite-Palette 0-3 je nach Metasprite-Nutzung
pal = rom["palette"]
spr0 = rom["banks"]["sprites"] * 64
used = {}
def walk(o):
    if isinstance(o, list) and len(o) == 4 and all(isinstance(v, int) for v in o):
        used.setdefault(o[2] & 0xFE, o[3] & 3)
    elif isinstance(o, list):
        for v in o:
            walk(v)
    elif isinstance(o, dict):
        for v in o.values():
            walk(v)
walk(rom["sprites"])
n = rom["sprites"]["sprite_tiles_used"] // 2
sheet = np.zeros((20, n * 10, 3), np.uint8) + 60
for k in range(n):
    p = used.get(2 * k, 3)
    cols4 = [np.array([60, 60, 60])] + [neslib.SYSPAL[pal[16 + p * 4 + c]] for c in (1, 2, 3)]
    for half in (0, 1):
        t = tiles[spr0 + 2 * k + half]
        for y in range(8):
            for x in range(8):
                sheet[2 + half * 8 + y, k * 10 + 1 + x] = cols4[t[y, x]]
Image.fromarray(sheet).resize((sheet.shape[1] * 4, sheet.shape[0] * 4), Image.NEAREST).save(ENTRY / "assets" / "sprites.png")
# Paletten-RAM
im = Image.new("RGB", (8 * 4 * 24 + 7 * 8, 40), (40, 40, 40))
d = ImageDraw.Draw(im)
for p in range(8):
    for c in range(4):
        v = pal[p * 4 + c]
        x = p * (4 * 24 + 8) + c * 24
        d.rectangle([x, 0, x + 23, 23], fill=tuple(int(u) for u in neslib.SYSPAL[v]))
        d.text((x + 3, 26), f"{v:02X}", fill=(230, 230, 230))
im.save(ENTRY / "assets" / "palette_ram.png")
print("assets/chr_banks.png, assets/sprites.png, assets/palette_ram.png")
