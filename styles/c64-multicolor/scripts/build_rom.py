#!/usr/bin/env python3
"""Fügt Hintergrund, Zeichensatz und Sprites zu demo/rom/c64.json zusammen (Speicherabbild für die Demo).

Inhalt (Bytes base64-kodiert, im Format des Videochips):
  bitmap  8000 Bytes Multicolor-Bitmap (Zellen 40x25 à 8 Bytes; Zeilen 18-24 leer, dort Textmodus)
  screen  1000 Bytes Bildschirmspeicher (Bitmap-Zeilen: Farben 01/10; Textzeilen: Zeichencodes, von main.gd gesetzt)
  color   1000 Bytes Farbspeicher (Bitpaar 11 bzw. Zeichenfarbe)
  charset 2048 Bytes eigener Zeichensatz (scripts/font8.py), Codes 128-255 invertiert
  sprites n*64 Bytes Sprite-Formen (63 Bytes + Füllbyte), dazu je Form das Multicolor-Flag
  raster  240 Einträge [Hintergrund, Rahmen, Modus] je Bildzeile (20 Rahmenzeilen oben, 200 Bildzeilen, 20 unten)
  anim    Farbzyklus-Plätze [Zelle, Platz, Gruppe, Aus-Farbe] (Glitzern, Sterne, Leuchtfeuer, Laterne)
"""
import base64, json, sys

import numpy as np

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from c64lib import *  # noqa
import font8

BORDER = LBLUE
TEXT_BG = BLUE
TEXT_ROW = 18


def b64(b):
    return base64.b64encode(bytes(b)).decode()


def main():
    bg = np.load(ROOT / "assets/bg_build.npz")
    pairs = np.zeros((200, 160), np.uint8)
    pairs[:144] = bg["pairs"][:144]
    screen = bytearray(bg["screen"].tobytes())
    color = bytearray(bg["color"].tobytes())
    for i in range(TEXT_ROW * 40, 1000):
        screen[i] = font8.code(" ")
        color[i] = WHITE
    raster = []
    line_bg = list(bg["raster"]) + [TEXT_BG] * (200 - 144)
    # Ortszeile: Rasterbalken hinter der ersten Textzeile (dunkelgraue Kante, dann schwarz)
    line_bg[TEXT_ROW * 8] = DGREY
    for y in range(TEXT_ROW * 8 + 1, TEXT_ROW * 8 + 8):
        line_bg[y] = BLACK
    for y in range(240):
        sy = y - 20
        if 0 <= sy < 200:
            raster.append([int(line_bg[sy]), BORDER, 0 if sy < TEXT_ROW * 8 else 1])
        else:
            raster.append([TEXT_BG, BORDER, 1])
    group = bg["group"]
    anim = []
    for ci, slot, g in bg["anim"].tolist():
        cy, cx = divmod(ci, 40)
        if g == 5:   # Stern: Aus-Farbe = Hintergrund seiner Zeile
            ys, xs = np.nonzero(group[cy * 8:cy * 8 + 8, cx * 4:cx * 4 + 4] == 5)
            off = int(bg["raster"][cy * 8 + ys[0]])
        elif g in (1, 2):
            off = BLUE
        else:
            off = DGREY
        anim.append([ci, slot, g, off])
    spr = json.loads((ROOT / "assets/sprites.json").read_text())
    data = bytearray()
    for s in spr["shapes"]:
        data += sprite_bytes(s["rows"], s["mc"])
    motif = json.loads((PROJECT / "data/motif.json").read_text())
    rom = {
        "palette": [f"{r:02x}{g:02x}{b:02x}" for r, g, b in PAL],
        "bitmap": b64(bitmap_bytes(pairs)),
        "screen": b64(screen),
        "color": b64(color),
        "charset": b64(font8.charset()),
        "sprites": b64(data),
        "sprite_mc": [s["mc"] for s in spr["shapes"]],
        "mc0": spr["mc0"], "mc1": spr["mc1"],
        "raster": raster,
        "anim": anim,
        "badger": spr["badger"], "gull": spr["gull"], "smoke": spr["smoke"], "beam": spr["beam"],
        "text_row": TEXT_ROW,
        "ui": motif["ui_text"],
        "codes": {ch: font8.code(ch) for ch in sorted(set("".join(
            [motif["ui_text"]["location"], motif["ui_text"]["line"], motif["ui_text"]["parser_prompt"],
             *motif["ui_text"]["choices"], "0123456789 >"])))},
    }
    out = ROOT / "demo/rom/c64.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rom, ensure_ascii=False))
    print(f"{out.relative_to(ROOT)}: {out.stat().st_size // 1024} KB, {len(spr['shapes'])} Sprite-Formen, "
          f"{len(anim)} Farbzyklus-Plätze")


if __name__ == "__main__":
    main()
