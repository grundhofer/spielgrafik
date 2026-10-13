#!/usr/bin/env python3
"""Stilreferenz für den Laufbogen: raw/bg2.png als flacher Dreifarbdruck (ohne Papier- und Druckstruktur).

    .venv/bin/python styles/holzschnitt/scripts/make_style_ref.py

Gleicher Farbauszug wie build_plates.py, aber ohne Maske (Holzbraun -> Zinnober, Hellbraun -> Papier): zeigt dem
Bildmodell genau die drei Druckfarben und die Schnittbreite des Hintergrunds. Ausgang: assets/ref/style_print.png
"""
import pathlib
import numpy as np
from PIL import Image

import inklib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SEP = [("black", (7, 8, 7), (1, 0, 0)), ("black2", (18, 19, 17), (1, 0, 0)), ("paper", (238, 199, 150), (0, 0, 0)),
       ("paper2", (245, 213, 165), (0, 0, 0)), ("teal", (44, 107, 114), (0, 1, 0)), ("teal_dark", (25, 68, 73), (0, 1, 0)),
       ("orange", (240, 102, 30), (0, 0, 1)), ("tan", (192, 155, 111), (0, 0, 0)), ("brown", (86, 58, 37), (0, 0, 1)),
       ("lbrown", (133, 99, 66), (0, 0, 0))]


def main():
    im = np.asarray(Image.open(ROOT / "assets/raw/bg2.png").convert("RGB"))
    idx = inklib.majority3(inklib.classify(im, SEP), len(SEP))
    pl = inklib.plates_from_index(idx, SEP)
    P, T, O, K = (np.array(c) for c in ((240, 214, 172), (44, 107, 114), (235, 100, 35), (14, 14, 13)))
    out = np.ones(pl.shape[:2] + (3,)) * P
    out = np.where(pl[..., 1:2] > 0, T, out)
    out = np.where(pl[..., 2:3] > 0, O, out)
    out = np.where(pl[..., 0:1] > 0, K, out)
    Image.fromarray(out.astype(np.uint8)).save(ROOT / "assets/ref/style_print.png")
    print("ok assets/ref/style_print.png")


if __name__ == "__main__":
    main()
