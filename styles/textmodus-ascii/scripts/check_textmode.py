#!/usr/bin/env python3
"""Prüft gerenderte Bilder (640×350) auf die Regeln des Textmodus.

    .venv/bin/python styles/textmodus-ascii/scripts/check_textmode.py <ordner mit f*.png>

  - nur die 16 Farben der Textmoduspalette
  - je Zelle (8×14) höchstens zwei Farben
  - hat eine Zelle zwei Farben, ist mindestens eine davon eine der 8 dunklen (Hintergrund kann nur 0–7 sein)
  - jedes Pixel ist Vorder- oder Hintergrund eines Zeichens aus dem Zeichensatz-ROM: das Muster der
    Vordergrundpixel muss einem der 256 Zeichen entsprechen (oder dessen Umkehrung, wenn beide Farben dunkel
    sind und Vorder-/Hintergrund nicht unterscheidbar sind), Cursorzeilen ausgenommen
"""
import pathlib, sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tmscreen import GLYPHS, PALETTE  # noqa: E402

PAL = {c: i for i, c in enumerate(PALETTE)}


def main():
    files = sorted(pathlib.Path(sys.argv[1]).glob("f*.png"))
    glyph_set = {g.tobytes() for g in GLYPHS}
    bad_color = bad_two = bad_bg = bad_glyph = 0
    for p in files:
        a = np.asarray(Image.open(p).convert("RGB"))
        idx = np.full(a.shape[:2], -1)
        for c, i in PAL.items():
            idx[(a == c).all(-1)] = i
        bad_color += int((idx < 0).sum())
        cells = idx.reshape(25, 14, 80, 8).transpose(0, 2, 1, 3)
        for y in range(25):
            for x in range(80):
                c = cells[y, x]
                u = np.unique(c)
                if len(u) > 2:
                    bad_two += 1
                    continue
                if len(u) == 2:
                    if u.min() > 7:
                        bad_bg += 1
                    # Vordergrund = die helle Farbe, bei zwei dunklen beide Lesarten zulassen
                    pats = [(c == u[1])] if u[1] > 7 else [(c == u[0]), (c == u[1])]
                    ok = any(pt.astype(bool).tobytes() in glyph_set for pt in pats)
                    if not ok and y != 23:          # Zeile 23: Unterstrich-Cursor der Eingabe
                        bad_glyph += 1
    print(f"{len(files)} Bilder: Fremdfarben-Pixel {bad_color}, Zellen mit >2 Farben {bad_two}, "
          f"Zellen mit zwei hellen Farben {bad_bg}, Zellen ohne passendes Zeichen {bad_glyph}")
    print("ok" if not (bad_color or bad_two or bad_bg or bad_glyph) else "PROBLEME")


if __name__ == "__main__":
    main()
