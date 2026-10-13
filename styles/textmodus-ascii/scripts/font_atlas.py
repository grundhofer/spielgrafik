#!/usr/bin/env python3
"""Baut aus einer Terminus-BDF (OFL-1.1) den Zeichensatz-ROM des Textmodus: 256 Zeichen in CP437-Reihenfolge.

    .venv/bin/python styles/textmodus-ascii/scripts/font_atlas.py <ter-u14b.bdf> [--height 14]

Ausgabe:
  demo/fonts/cp437_8x14.png   Atlas 16×16 Zellen à 8×14, weiß auf transparent (1-Bit-Alpha)
  demo/fonts/cp437.json       Zuordnung Unicode-Zeichen -> Code 0..255 (für Skripte und GDScript)
  assets/charset.png          Vorschau ×3 mit Codes

Der Atlas ist eine abgeleitete Fassung (Modified Version im Sinn der OFL): Er trägt nicht den reservierten
Namen „Terminus Font“. Zeichen, die in Terminus fehlen, werden hier gezeichnet und im Bericht genannt.
"""
import argparse, json, pathlib, sys

from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent.parent

# CP437: 0x00–0x1F und 0x7F sind im ROM Grafikzeichen, Pythons Codec liefert dort Steuerzeichen.
LOW = " ☺☻♥♦♣♠•◘○◙♂♀♪♫☼►◄↕‼¶§▬↨↑↓→←∟↔▲▼"
HIGH = bytes(range(0x80, 0x100)).decode("cp437")
CP437 = LOW + "".join(chr(c) for c in range(0x20, 0x7F)) + "⌂" + HIGH
assert len(CP437) == 256


def parse_bdf(path):
    glyphs, cur, bitmap = {}, None, None
    fbb = None
    for line in pathlib.Path(path).read_text(encoding="latin-1").splitlines():
        p = line.split()
        if not p:
            continue
        if p[0] == "FONTBOUNDINGBOX":
            fbb = tuple(map(int, p[1:5]))
        elif p[0] == "STARTCHAR":
            cur = {}
        elif p[0] == "ENCODING":
            cur["enc"] = int(p[1])
        elif p[0] == "BBX":
            cur["bbx"] = tuple(map(int, p[1:5]))
        elif p[0] == "BITMAP":
            bitmap = []
        elif p[0] == "ENDCHAR":
            cur["rows"] = bitmap
            glyphs[cur["enc"]] = cur
            bitmap = None
        elif bitmap is not None:
            bitmap.append(int(p[0], 16))
    return fbb, glyphs


def glyph_image(g, fbb, w, h):
    """Glyph auf die volle Zelle (w×h) setzen, Grundlinie aus der Fontbox."""
    fw, fh, fx, fy = fbb
    bw, bh, bx, by = g["bbx"]
    im = Image.new("1", (w, h), 0)
    # Oberkante der Glyphe in Zellkoordinaten: Zelle reicht von fy (unten) bis fy+fh (oben)
    top = (fy + fh) - (by + bh)
    nbytes = (bw + 7) // 8
    for r, val in enumerate(g["rows"]):
        for c in range(bw):
            if val >> (nbytes * 8 - 1 - c) & 1:
                x, y = bx - fx + c, top + r
                if 0 <= x < w and 0 <= y < h:
                    im.putpixel((x, y), 1)
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bdf")
    ap.add_argument("--height", type=int, default=14)
    a = ap.parse_args()
    fbb, glyphs = parse_bdf(a.bdf)
    w, h = fbb[0], fbb[1]
    if h != a.height:
        sys.exit(f"Fontbox {w}×{h}, erwartet Höhe {a.height}")
    atlas = Image.new("RGBA", (16 * w, 16 * h), (0, 0, 0, 0))
    missing = []
    for code, ch in enumerate(CP437):
        g = glyphs.get(ord(ch))
        if g is None:
            missing.append(f"{code:02X} {ch} U+{ord(ch):04X}")
            continue
        im = glyph_image(g, fbb, w, h)
        cell = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        cell.paste((255, 255, 255, 255), (0, 0), im.convert("L"))
        atlas.paste(cell, ((code % 16) * w, (code // 16) * h))
    fonts = HERE / "demo" / "fonts"
    fonts.mkdir(parents=True, exist_ok=True)
    atlas.save(fonts / f"cp437_8x{h}.png")
    (fonts / "cp437.json").write_text(json.dumps({"cell": [w, h], "chars": CP437}, ensure_ascii=False))
    # Vorschau
    k = 3
    prev = Image.new("RGB", (16 * (w + 2) * k + 40, 16 * (h + 2) * k + 20), (0, 0, 170))
    d = ImageDraw.Draw(prev)
    big = atlas.resize((atlas.width * k, atlas.height * k), Image.NEAREST)
    for code in range(256):
        cx, cy = code % 16, code // 16
        src = big.crop((cx * w * k, cy * h * k, (cx + 1) * w * k, (cy + 1) * h * k))
        prev.paste((255, 255, 85), (40 + cx * (w + 2) * k, 20 + cy * (h + 2) * k), src)
    for i in range(16):
        d.text((4, 20 + i * (h + 2) * k + 10), f"{i:X}0", fill=(170, 170, 170))
        d.text((40 + i * (w + 2) * k + 6, 4), f"{i:X}", fill=(170, 170, 170))
    (HERE / "assets").mkdir(exist_ok=True)
    prev.save(HERE / "assets" / "charset.png")
    print(f"Atlas {atlas.size}, Zelle {w}×{h}, fehlend: {len(missing)}")
    for m in missing:
        print("  fehlt:", m)


if __name__ == "__main__":
    main()
