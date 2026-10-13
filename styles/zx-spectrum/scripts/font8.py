#!/usr/bin/env python3
"""Zeichensatz im Spectrum-Format aus der Schrift Pixel Operator 8 (CC0): 8 Bytes je Zeichen, 8×8-Zelle.

Die Schrift ist proportional; jede Glyphe wird in ihre 8-px-Zelle gesetzt (Tinte waagerecht mittig, Großbuchstaben
ab Zeile 0, Unterlängen in Zeile 7), damit Text im 32×24-Raster der Attributzellen steht.
Codes 32..127 wie ASCII; Umlaute als UDG (benutzerdefinierte Zeichen) ab Code 144: Ä Ö Ü ä ö ü ß.
Ausgabe: demo/rom/charset.bin (768 + 56 Bytes), assets/font_preview.png.
"""
import pathlib

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ENTRY = pathlib.Path(__file__).resolve().parent.parent
FONT = ENTRY / "demo/fonts/PixelOperator8.ttf"
UDG = "ÄÖÜäöüß"


def glyph(font, ch):
    im = Image.new("L", (16, 12), 0)
    d = ImageDraw.Draw(im)
    d.fontmode = "1"
    d.text((4, 0), ch, font=font, fill=255)
    a = np.asarray(im) > 0
    cell = np.zeros((8, 8), bool)
    cols = np.flatnonzero(a.any(0))
    if cols.size:
        w = cols[-1] - cols[0] + 1
        if w > 8:
            raise SystemExit(f"{ch!r} zu breit: {w}")
        left = (8 - w) // 2
        if a[8:].any():
            raise SystemExit(f"{ch!r} reicht unter Zeile 7")
        cell[:, left:left + w] = a[:8, cols[0]:cols[-1] + 1]
    return cell


def main():
    font = ImageFont.truetype(str(FONT), 8)
    chars = [chr(c) for c in range(32, 128)] + list(UDG)
    cells = [glyph(font, ch) for ch in chars]
    data = bytearray()
    for c in cells:
        for row in c:
            data.append(int(np.packbits(row.astype(np.uint8))[0]))
    (ENTRY / "demo/rom").mkdir(parents=True, exist_ok=True)
    (ENTRY / "demo/rom/charset.bin").write_bytes(bytes(data))
    sheet = np.zeros((8 * 7, 8 * 16), np.uint8)
    for i, c in enumerate(cells):
        y, x = (i // 16) * 8, (i % 16) * 8
        sheet[y:y + 8, x:x + 8] = c * 255
    Image.fromarray(sheet).resize((sheet.shape[1] * 6, sheet.shape[0] * 6), Image.NEAREST).save(
        ENTRY / "assets/font_preview.png")
    print(f"{len(cells)} Zeichen, {len(data)} Bytes")


if __name__ == "__main__":
    main()
