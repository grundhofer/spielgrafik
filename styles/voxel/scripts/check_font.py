#!/usr/bin/env python3
"""Prüft im gerenderten Bild, ob die Pixelschrift auf ihrem Raster sitzt: Läufe gleichfarbiger Textpixel
(waagerecht und senkrecht) müssen Vielfache der Schriftpixelgröße sein (Ortsschild 44 px -> 4 px,
Dialog 22 px -> 2 px). Gezählt werden die Lauflängen der Textfarbe in den Bereichen von Ortsschild, Dialogtext
und Auswahl.

    .venv/bin/python styles/voxel/scripts/check_font.py media/poster.png
"""
import sys
from collections import Counter
import numpy as np
from PIL import Image

TEXT = (0xf4, 0xea, 0xd2)
REGIONS = {                       # Name: (x0, y0, x1, y1, Schriftpixel in px, Farbe)
    "Ortsschild": (28, 24, 600, 80, 4, TEXT),
    "Dialogtext": (512, 548, 920, 640, 2, TEXT),
    "Auswahl (gewählt)": (912, 556, 1232, 592, 2, (0x2a, 0x1a, 0x08)),
    "Auswahl (übrige)": (912, 604, 1232, 688, 2, TEXT),
}


def runs(mask):
    out = Counter()
    for row in mask:
        n = 0
        for v in row:
            if v:
                n += 1
            elif n:
                out[n] += 1; n = 0
        if n:
            out[n] += 1
    return out


def main():
    im = np.array(Image.open(sys.argv[1]).convert("RGB")).astype(int)
    ok_all = True
    for name, (x0, y0, x1, y1, fp, col) in REGIONS.items():
        a = im[y0:y1, x0:x1]
        m = np.abs(a - np.array(col)).max(2) <= 2
        h, v = runs(m), runs(m.T)
        tot = h + v
        bad = sum(c for k, c in tot.items() if k % fp)
        ok_all &= bad == 0
        print(f"{name}: {m.sum()} Textpixel, Läufe waagerecht {dict(sorted(h.items()))}, senkrecht "
              f"{dict(sorted(v.items()))}; nicht auf dem {fp}-px-Raster: {bad}")
    print("ok" if ok_all else "ABWEICHUNG")


if __name__ == "__main__":
    main()
