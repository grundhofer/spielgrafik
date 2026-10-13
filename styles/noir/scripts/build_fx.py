#!/usr/bin/env python3
"""Code-Assets der Noir-Demo (ohne Bildmodell, fester Seed).

    .venv/bin/python styles/noir/scripts/build_fx.py

  assets/noise.png   256×256, kachelbar: R = Nebel (tiefe Frequenzen), G = Nebel fein, B = Wertrauschen fein
  assets/aux_mask.png 1280×720, RGB: R = Ferne (Himmel, Meer, Landzungen, Boote; 0 = Häuschen, Laterne mit Pfahl,
                     Fässer und Kisten, Kai), Nebel und Leuchtturmstrahl liegen nur auf der Ferne;
                     G = Pflaster (aus floor_mask.png von build_bg.py); B = 0
"""
import json, pathlib

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "assets"
RNG = np.random.default_rng(20261012)


def tile_noise(n, size=256):
    """Kachelbares Wertrauschen: n×n Zufallsgitter, 3×3 gekachelt, bikubisch vergrößert, Mitte ausgeschnitten."""
    g = RNG.random((n, n)).astype(np.float32)
    big = np.tile(g, (3, 3))
    im = Image.fromarray((big * 255).astype(np.uint8)).resize((size * 3, size * 3), Image.BICUBIC)
    return np.asarray(im).astype(np.float32)[size:2 * size, size:2 * size] / 255.0


def fbm(octaves, size=256):
    acc, amp, tot = np.zeros((size, size), np.float32), 1.0, 0.0
    for n in octaves:
        acc += amp * tile_noise(n, size)
        tot += amp
        amp *= 0.55
    acc /= tot
    acc = (acc - acc.min()) / (acc.max() - acc.min())
    return acc


def main():
    r = fbm([4, 8, 16, 32])
    g = fbm([8, 16, 32, 64])
    b = tile_noise(128)
    noise = np.stack([r, g, b], -1)
    Image.fromarray((noise * 255 + 0.5).astype(np.uint8), "RGB").save(OUT / "noise.png")

    sc = json.loads((OUT / "scene.json").read_text())
    S, y0 = sc["scale"], sc["crop_y0"]
    P = lambda x, y: (x * S, (y - y0) * S)
    m = Image.new("L", (1280, 720), 255)
    d = ImageDraw.Draw(m)
    # Kai (alles unter der Kaikante) und Häuschen (Dach und Wand bis zur rechten Kante bei Quell-x 330)
    d.rectangle([0, sc["quay_edge_y"] - 2, 1280, 720], fill=0)
    d.polygon([P(0, 140), P(70, 175), P(330, 362), P(312, 372), P(312, 700), P(0, 760)], fill=0)
    d.polygon([P(125, 75), P(240, 75), P(240, 300), P(125, 300)], fill=0)           # Schornstein
    # Laterne mit Pfahl und Arm
    d.polygon([P(900, 285), P(975, 282), P(975, 670), P(948, 670), P(948, 400), P(900, 400)], fill=0)
    # Fässer und Kisten rechts
    d.polygon([P(1258, 560), P(1536, 560), P(1536, 800), P(1258, 800)], fill=0)
    m = m.filter(ImageFilter.GaussianBlur(1.2))
    floor = Image.open(OUT / "floor_mask.png").convert("L")
    Image.merge("RGB", (m, floor, Image.new("L", m.size, 0))).save(OUT / "aux_mask.png")
    print("ok noise.png aux_mask.png")


if __name__ == "__main__":
    main()
