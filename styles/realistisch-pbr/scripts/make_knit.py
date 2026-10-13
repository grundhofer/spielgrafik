#!/usr/bin/env python3
"""Strickmuster (glatt rechts) für den Schal, aus Code: Höhenkarte aus V-förmigen Maschen,
daraus Normalenkarte, Graustufen-Detail und ORM. Kachelt nahtlos (8 Maschen × 10 Reihen).

    .venv/bin/python styles/realistisch-pbr/scripts/make_knit.py

Schreibt demo/textures/knit_a.png, knit_n.png, knit_orm.png samt .import-Dateien. Im Shader mit
tile_m ≈ 0,1 m: eine Masche ist dann gut 1 cm breit (grobes Strickgarn).
"""
import pathlib
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build_textures import write_import  # noqa: E402

TEX = pathlib.Path(__file__).resolve().parent.parent / "demo" / "textures"
N = 512
COLS, ROWS = 8, 10


def main():
    rng = np.random.default_rng(20261013)
    y, x = np.mgrid[0:N, 0:N].astype(np.float32) + 0.5
    sw, sh = N / COLS, N / ROWS
    h = np.zeros((N, N), np.float32)
    # jede Masche: zwei schräge Schenkel (Ellipsen), die sich unten zur Spitze des V treffen
    u = (x % sw) / sw          # 0..1 innerhalb der Masche
    v = (y % sh) / sh
    for side, ang in ((0.27, 0.55), (0.73, -0.55)):
        # Schenkel reicht über die Reihengrenze in die nächste Reihe (verschränkte Maschen)
        for off in (-1.0, 0.0, 1.0):
            px = (u - side)
            py = (v - 0.5 - off)
            c, s = np.cos(ang), np.sin(ang)
            rx = px * c - py * s * (sh / sw)
            ry = px * s * (sw / sh) + py * c
            d = (rx / 0.22) ** 2 + (ry / 0.62) ** 2
            h = np.maximum(h, np.sqrt(np.clip(1.0 - d, 0.0, 1.0)))
    # Garnstruktur: feine schräge Fasern, Rauschen
    fib = 0.5 + 0.5 * np.sin((x * 0.9 + y * 0.35) * 2 * np.pi / 6.0 + rng.random((N, N)) * 0.8)
    h = h * (0.88 + 0.12 * fib) + 0.03 * rng.random((N, N))
    # Normalen aus der Höhe (periodische Ableitung, damit die Kachel nahtlos bleibt)
    k = 3.0
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5 * k
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5 * k
    n = np.stack([-gx, gy, np.ones_like(h)], -1)   # OpenGL: +Y zeigt im Bild nach oben
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    Image.fromarray(((n * 0.5 + 0.5) * 255 + 0.5).astype(np.uint8)).save(TEX / "knit_n.png")
    # Detail (linear Mittel 0,5): Rillen dunkler
    lin = 0.18 + 0.82 * np.clip(h, 0, 1) ** 0.7
    lin = lin * (0.5 / lin.mean())
    srgb = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.clip(lin, 0, 1) ** (1 / 2.4) - 0.055)
    Image.fromarray((np.clip(srgb, 0, 1) * 255 + 0.5).astype(np.uint8), "L").convert("RGB").save(TEX / "knit_a.png")
    ao = 0.45 + 0.55 * np.clip(h, 0, 1)
    rough = 0.82 + 0.12 * rng.random((N, N))
    orm = np.stack([ao, rough, np.zeros_like(h)], -1)
    Image.fromarray((orm * 255 + 0.5).astype(np.uint8)).save(TEX / "knit_orm.png")
    for name, normal in (("knit_a.png", False), ("knit_n.png", True), ("knit_orm.png", False)):
        write_import(TEX / name, normal=normal)
    print("ok", TEX / "knit_a.png")


if __name__ == "__main__":
    main()
