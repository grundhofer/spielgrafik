#!/usr/bin/env python3
"""Wandelt ein Bild automatisch in Textmodus-Zellen um (Versuch, nicht Teil der Demo).

    .venv/bin/python styles/textmodus-ascii/scripts/convert_image.py <bild> <ausgabe.png> [--rows 19]

Das Bild wird auf 640 × rows·14 Pixel zugeschnitten und skaliert. Je Zelle (8×14) wählt das Skript aus
Leerzeichen, █ ▀ ▄ ▌ ▐ ░ ▒ ▓ und allen Paaren aus 16 Vorder- und 8 Hintergrundfarben das Paar mit dem
kleinsten Fehler, verglichen auf 2×2 Teilflächen (je 4×7 Pixel), damit Schattierzeichen als Mischfarbe zählen.
Ausgabe: Vorschau ×2 (nur Bildzeilen 1..rows).
"""
import argparse, pathlib, sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tmscreen import CODE, GLYPHS, PALETTE, Screen  # noqa: E402

CHARS = [" ", "█", "▀", "▄", "▌", "▐", "░", "▒", "▓"]
SUB = (7, 4)          # Teilfläche (Zeilen, Spalten)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("out")
    ap.add_argument("--rows", type=int, default=19)
    a = ap.parse_args()
    rows = a.rows
    im = Image.open(a.image).convert("RGB")
    ar = 640 / (rows * 14)
    w, h = im.size
    if w / h > ar:
        nw = int(h * ar)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = int(w / ar)
        im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    im = im.resize((640, rows * 14), Image.LANCZOS)
    px = np.asarray(im, dtype=float)
    pal = np.array(PALETTE, float)
    ny, nx = 14 // SUB[0], 8 // SUB[1]
    cells = px.reshape(rows, 14, 80, 8, 3).transpose(0, 2, 1, 3, 4)
    tgt = cells.reshape(rows, 80, ny, SUB[0], nx, SUB[1], 3).mean(axis=(3, 5))
    masks = np.array([GLYPHS[CODE[c]] for c in CHARS], float)
    frac = masks.reshape(len(CHARS), ny, SUB[0], nx, SUB[1]).mean(axis=(2, 4))[..., None]
    s = Screen()
    best = np.full((rows, 80), np.inf)
    for ci, c in enumerate(CHARS):
        for f in range(16):
            for b in range(8):
                col = frac[ci] * pal[f] + (1 - frac[ci]) * pal[b]
                e = ((tgt - col) ** 2).sum(axis=(-3, -2, -1))
                upd = e < best
                best[upd] = e[upd]
                s.ch[1:1 + rows][upd] = CODE[c]
                s.fg[1:1 + rows][upd] = f
                s.bg[1:1 + rows][upd] = b
    s.render(scale=2).crop((0, 28, 1280, 28 * (rows + 1))).save(a.out)
    print("mittlerer Fehler je Teilfläche (RGB-Abstand):", round(float(np.sqrt(best / (ny * nx)).mean()), 1))


if __name__ == "__main__":
    main()
