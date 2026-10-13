#!/usr/bin/env python3
"""Prüft Decoder und Zeichengenerator der Demo gegen die Python-Fassung und die Videotext-Regeln.

    .venv/bin/python styles/videotext/scripts/check_render.py <ordner mit f*.png> <dump.txt> [--every 1]

Der Godot-Lauf schreibt mit --dump=<datei> die 25 × 40 Seitenbytes jedes Bildes. Dieses Skript
  1. dekodiert jede Seite mit ttxlib (Python) und rendert sie (Flash-Phase wie in main.gd),
  2. vergleicht das mit dem Godot-Bild (Seite liegt bei x 240, y 10): Anteil abweichender Pixel, größte Abweichung,
  3. prüft am Godot-Bild die Farbregel: nur die 8 Videotext-Farben und je Zelle höchstens zwei Farben, getrennt
     gezählt für Mosaik-/Leer-/Steuerzellen und Textzellen (die Schrift ist binär, siehe build_atlas.py); dazu die
     Zahl verschiedener Farben im ganzen Bild,
  4. zählt Steuerzellen und Bytes außerhalb des erlaubten Bereichs (7 Bit).
"""
import argparse
import pathlib
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ttxlib as T  # noqa: E402

PAL = T.PALETTE.astype(int)


def flash_on(f):
    field = int(np.floor(f * 50 / 30))
    return field % 64 >= 16


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames")
    ap.add_argument("dump")
    ap.add_argument("--every", type=int, default=1)
    a = ap.parse_args()
    pngs = sorted(pathlib.Path(a.frames).glob("f*.png"))
    dump = [l.split() for l in open(a.dump)]
    worst, total_diff, n, bad_cells, foreign = 0, 0.0, 0, 0, 0
    bad_text, foreign_text, colours = 0, 0, set()
    ctrl_counts = []
    for i, parts in enumerate(dump):
        if i % a.every or i >= len(pngs):
            continue
        f = int(parts[0])
        page = [[int(h[k:k + 2], 16) for k in range(0, 80, 2)] for h in parts[1:]]
        assert all(0 <= b < 0x80 for row in page for b in row)
        ctrl_counts.append(sum(1 for row in page[3:20] for b in row if b < 0x20))
        cells = T.decode_page(page)
        ref = T.render(cells, flash_on(f)).astype(int)
        got = np.asarray(Image.open(pngs[i]).convert("RGB"), dtype=int)[10:710, 240:1040]
        d = np.abs(got - ref).max(-1)
        worst = max(worst, int(d.max()))
        total_diff += float((d > 2).mean())
        n += 1
        # Farbregel je Zelle (Mosaik/leer/Steuerzelle und Text getrennt gezählt)
        colours |= {tuple(x) for x in np.unique(got.reshape(-1, 3), axis=0)}
        for r in range(25):
            for c in range(40):
                k = cells[r][c][0]
                blk = got[r * 28:(r + 1) * 28, c * 20:(c + 1) * 20].reshape(-1, 3)
                cols = {tuple(x) for x in np.unique(blk, axis=0)}
                many, alien = len(cols) > 2, not cols <= {tuple(p) for p in PAL}
                if k == T.CHAR:
                    bad_text += many
                    foreign_text += alien
                else:
                    bad_cells += many
                    foreign += alien
    print(f"Bilder geprüft: {n}")
    print(f"Godot gegen Python-Decoder: mittlerer Anteil abweichender Pixel {total_diff / max(n, 1):.5f}, "
          f"größte Abweichung {worst} (0–255)")
    print(f"Mosaik-/Leerzellen mit mehr als 2 Farben: {bad_cells}; Zellen mit Fremdfarben: {foreign}")
    print(f"Textzellen mit mehr als 2 Farben: {bad_text}; mit Fremdfarben: {foreign_text}")
    print(f"verschiedene Farben im Seitenbereich aller geprüften Bilder: {len(colours)} "
          f"(davon außerhalb der 8 Videotextfarben: {len(colours - {tuple(p) for p in PAL})})")
    print(f"Steuerzellen in den Bildzeilen 3–19: {min(ctrl_counts)}–{max(ctrl_counts)} je Bild")


if __name__ == "__main__":
    main()
