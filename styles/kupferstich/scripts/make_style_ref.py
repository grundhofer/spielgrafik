#!/usr/bin/env python3
"""Stilreferenz für die Figuren- und Ornamentaufträge: raw/bg2.png als reine schwarze Linien auf Weiß.

    .venv/bin/python styles/kupferstich/scripts/make_style_ref.py

Das Rohbild hat Flächenton zwischen den Linien und Farbreste (rotes Band, oranger Horizont). Als Referenz soll
das Bildmodell nur die Strichtechnik sehen: Helligkeit -> Tuschedichte, lokaler Grund (Minimum 7x7, geglättet)
zu 60 % abgezogen, schwarz auf weiß. Ergebnis: assets/ref/style_engraving.png (1536x1024).
"""
import numpy as np
from PIL import Image

import inklib as K


def main():
    L = K.lum(Image.open(K.SD / "assets/raw/bg2.png").convert("RGB"))
    D, _, _ = K.density(L, lo_pct=0.5, hi_pct=99.0)
    m = K.blur(K.erode(D, 3), 2)
    Dp = np.clip((D - 0.6 * m) / np.maximum(1 - 0.6 * m, 0.15), 0, 1)
    K.to_img(1 - Dp).convert("RGB").save(K.SD / "assets/ref/style_engraving.png")
    print("ok")


if __name__ == "__main__":
    main()
