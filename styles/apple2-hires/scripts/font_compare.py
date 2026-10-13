#!/usr/bin/env python3
"""Abgleich des Zeichensatzes font57 mit einer Pixelschrift im TrueType-Format, die ein 7×8-Punktraster nachbildet.

Die Vergleichsschrift gehört nicht zum Eintrag und wird nicht mitgeliefert. Geprüft wurde Fassung 2 gegen
„Print Char 21“ von Kreative Korp (Nachbildung der 40-Zeichen-Schrift des Apple II; Kreative Software Relay Fonts
Free Use License, keine Bearbeitungen – hier nur zum Messen gerendert):

    .venv/bin/python styles/apple2-hires/scripts/font_compare.py /pfad/zu/PrintChar21.ttf

Die Schrift wird mit FreeType bei 112 px gerendert (1 Punkt = 14 px) und Zelle für Zelle auf das 7×8-Raster
abgetastet; teilweise gefüllte Zellen werden gemeldet. Je Zeichen: abweichende Punkte als kleinster Wert über
alle Verschiebungen um ±1 Zeile/Spalte (auf einer um 1 Punkt gepolsterten Fläche; fängt verschobene Kopien).
Ä Ö Ü entfallen (kein Umlaut im Zeichengenerator).
"""
import pathlib, sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from font57 import G, glyph_bytes  # noqa: E402

DOT, SIZE = 14, 112


def ref_cell(font, ch):
    img = Image.new("L", (7 * DOT + 20, 8 * DOT + 20), 0)
    ImageDraw.Draw(img).text((0, 0), ch, fill=255, font=font)
    a = np.array(img)
    cell = np.zeros((8, 7), np.uint8)
    for y in range(8):
        for x in range(7):
            m = a[y * DOT:(y + 1) * DOT, x * DOT:(x + 1) * DOT].mean()
            if 20 < m < 235:
                print(f"  Hinweis: {ch!r} Zelle {y},{x} nur teilweise gefüllt ({m:.0f})")
            cell[y, x] = 1 if m >= 128 else 0
    return cell


def dist(m, r):
    H, W = m.shape[0] + 2, m.shape[1] + 2
    R = np.zeros((H, W), np.uint8)
    R[1:-1, 1:-1] = r
    best = None
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            M = np.zeros((H, W), np.uint8)
            M[1 + dy:1 + dy + m.shape[0], 1 + dx:1 + dx + m.shape[1]] = m
            d = int((M != R).sum())
            best = d if best is None else min(best, d)
    return best


def main():
    font = ImageFont.truetype(sys.argv[1], SIZE)
    res = {}
    for ch in G:
        if ch == " " or not ch.isascii():
            continue
        m = np.array([[(v >> k) & 1 for k in range(7)] for v in glyph_bytes(ch)], np.uint8)
        res[ch] = dist(m, ref_cell(font, ch))
    alnum = sorted(b for c, b in res.items() if c.isalnum())
    print(f"verglichen: {len(res)} Zeichen, davon {len(alnum)} Buchstaben und Ziffern")
    print("pixelgleich (auch nach Verschiebung):", "".join(c for c, b in res.items() if b == 0) or "-")
    print("1–2 Punkte Abstand:", "".join(c for c, b in res.items() if 0 < b <= 2) or "-")
    print(f"Buchstaben/Ziffern: Median {alnum[len(alnum) // 2]}, kleinster {alnum[0]}")
    print("je Zeichen:", " ".join(f"{c}:{b}" for c, b in res.items()))


if __name__ == "__main__":
    main()
