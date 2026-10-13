#!/usr/bin/env python3
"""Gestochener Schlagschatten der Figur aus Code: waagerechte Linien in einer Ellipse, Linienstärke nimmt zum Rand
hin ab (Tonwert über Linienstärke wie im Stich). 4-fach überabgetastet, dann verkleinert.

    .venv/bin/python styles/kupferstich/scripts/make_fx.py

Ausgabe: assets/shadow.png (RGBA, Weiß mit Tusche als Alpha) + Kopie in demo/art.
"""
import shutil

import numpy as np
from PIL import Image

import inklib as K

W, H, SS = 132, 18, 4
PERIOD = 3.0


def main():
    yy, xx = np.mgrid[0:H * SS, 0:W * SS].astype(np.float32) / SS
    cx, cy = W * 0.5, H * 0.5
    r = np.sqrt(((xx - cx) / (W * 0.5 - 1)) ** 2 + ((yy - cy) / (H * 0.5 - 1)) ** 2)
    # Schatten fällt nach rechts (Laterne links oben): rechts dichter
    tone = np.clip(1 - r, 0, 1) ** 0.7 * np.clip(0.55 + 0.45 * (xx - cx) / (W * 0.5), 0, 1)
    phase = (yy + 0.5) / PERIOD
    dist = np.abs(phase - np.round(phase)) * PERIOD          # Abstand zur Linienmitte in px
    half = 0.15 + 0.85 * tone                                  # halbe Linienstärke in px
    a = np.clip((half - dist) * SS * 0.5 + 0.5, 0, 1) * (tone > 0.02)
    a = K.resize_f(a, (W, H), Image.BOX)
    rgba = np.dstack([np.ones_like(a)] * 3 + [a])
    out = K.SD / "assets/shadow.png"
    Image.fromarray(np.clip(rgba * 255 + 0.5, 0, 255).astype(np.uint8), "RGBA").save(out)
    shutil.copy(out, K.SD / "demo/art/shadow.png")
    print("ok", out)


if __name__ == "__main__":
    main()
