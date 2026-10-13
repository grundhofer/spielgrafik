#!/usr/bin/env python3
"""Bitmapschrift aus DotGothic16 (OFL) für die Demo: jedes Zeichen mit FreeType (Pillow, fontmode "1",
also ohne Kantenglättung und mit Hinting) in 16 px gerastert und in ein Atlasbild gelegt.

Warum nicht Godots Schriftrasterung: Godot 4.7 zeichnete DotGothic16 bei 16 px ohne Kantenglättung mit
2 px breiten senkrechten Strichen und ohne den i-Punkt (siehe style.json → pitfalls). Pillow trifft das Punktraster der Schrift genau.

Ausgabe: demo/fonts/dotgothic16_atlas.png (weiß, 1-Bit-Alpha) und demo/fonts/dotgothic16_atlas.json
(je Zeichen: x, y, w, h im Atlas und Vorschub in px; Zeilenhöhe, Oberlänge).
"""
import json, pathlib

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SD = pathlib.Path(__file__).resolve().parent.parent
FONT = SD / "demo/fonts/DotGothic16-Regular.ttf"
OUT = SD / "demo/fonts/dotgothic16_atlas"
SIZE = 16
CHARS = "".join(chr(c) for c in range(32, 127)) + "ÄÖÜäöüß" + "【】「」　▼…–"


def main():
    f = ImageFont.truetype(str(FONT), SIZE)
    asc, desc = f.getmetrics()
    cell_h = asc + desc
    glyphs = {}
    cols = 32
    cw = SIZE + 2
    rows = (len(CHARS) + cols - 1) // cols
    atlas = Image.new("L", (cols * cw, rows * cell_h), 0)
    for i, ch in enumerate(CHARS):
        adv = int(round(f.getlength(ch)))
        g = Image.new("L", (cw, cell_h), 0)
        d = ImageDraw.Draw(g)
        d.fontmode = "1"
        d.text((0, 0), ch, font=f, fill=255, anchor="la")
        a = np.asarray(g) > 127
        w = max(adv, int(np.flatnonzero(a.any(0)).max()) + 1 if a.any() else adv)
        x, y = (i % cols) * cw, (i // cols) * cell_h
        atlas.paste(g.crop((0, 0, w, cell_h)), (x, y))
        glyphs[ch] = [x, y, w, cell_h, adv]
    alpha = np.asarray(atlas)
    rgba = np.dstack([np.full(alpha.shape, 255, np.uint8)] * 3 + [np.where(alpha > 127, 255, 0).astype(np.uint8)])
    Image.fromarray(rgba, "RGBA").save(str(OUT) + ".png")
    meta = {"source": FONT.name, "size": SIZE, "ascent": asc, "descent": desc, "line_h": cell_h, "glyphs": glyphs}
    pathlib.Path(str(OUT) + ".json").write_text(json.dumps(meta, ensure_ascii=False))
    print(f"{len(glyphs)} Zeichen, Zeilenhöhe {cell_h} (Oberlänge {asc}, Unterlänge {desc})")


if __name__ == "__main__":
    main()
