#!/usr/bin/env python3
"""Simuliert, wie stark die Gesichtsschärfe der Figur von der Subpixel-Lage abhängt, je nach Abtastverfahren im Shader.

    .venv/bin/python styles/fotoreal-standbild/tools/sim_sampling.py

Atmen und Gewichtsverlagerung verschieben die Figur um Bruchteile eines Pixels; lineare Filterung macht sie dabei je
nach Lage weicher oder schärfer (die Schärfe "pumpt"). Hier wird die Figur (demo/art/actor.png, 2x) in NumPy so
abgetastet wie im Shader, für 8x8 Subpixel-Verschiebungen, und je Verfahren die Standardabweichung des Laplace-Filters
im Gesicht ausgegeben (min, max, max/min; 1,00 = kein Pumpen). Grundlage für die Wahl in actor.gdshader (tap9).
"""
import pathlib

import numpy as np
from PIL import Image

ART = pathlib.Path(__file__).resolve().parent.parent / "demo" / "art"


def bilin(img, x, y):
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = x - x0, y - y0
    h, w = img.shape
    xa, xb = np.clip(x0, 0, w - 1), np.clip(x0 + 1, 0, w - 1)
    ya, yb = np.clip(y0, 0, h - 1), np.clip(y0 + 1, 0, h - 1)
    return (img[ya, xa] * (1 - fx) * (1 - fy) + img[ya, xb] * fx * (1 - fy)
            + img[yb, xa] * (1 - fx) * fy + img[yb, xb] * fx * fy)


def lap(L):
    return (-4 * L[1:-1, 1:-1] + L[:-2, 1:-1] + L[2:, 1:-1] + L[1:-1, :-2] + L[1:-1, 2:]).std()


def main():
    hi = np.asarray(Image.open(ART / "actor.png").convert("RGBA"), np.float32) / 255
    L2 = (hi[..., :3] * hi[..., 3:]).mean(-1)                      # vormultiplizierte Helligkeit, 2x
    h2, w2 = L2.shape[0] // 2 * 2, L2.shape[1] // 2 * 2
    mip1 = L2[:h2, :w2].reshape(h2 // 2, 2, w2 // 2, 2).mean((1, 3))  # Mipmap-Stufe 1 (2x2-Kasten)
    lo = Image.open(ART / "actor.png").convert("RGBA").resize((L2.shape[1] // 2, L2.shape[0] // 2), Image.LANCZOS)
    lo = np.asarray(lo, np.float32) / 255
    L1 = (lo[..., :3] * lo[..., 3:]).mean(-1)                        # 1x wie vor der Umstellung
    yy, xx = np.mgrid[15:60, 60:115].astype(np.float32)             # Gesicht in Bildschirmpixeln der Figur

    def scheme(img, scale, offs):
        def f(dx, dy):
            acc = 0
            for ox in offs:
                for oy in offs:
                    acc = acc + bilin(img, (xx + 0.5 + dx + ox) * scale - 0.5, (yy + 0.5 + dy + oy) * scale - 0.5)
            return acc / len(offs) ** 2
        return f

    schemes = {
        "1x bilinear (vorher)": scheme(L1, 1, [0.0]),
        "2x, Mipmap-Stufe 1": scheme(mip1, 1, [0.0]),
        "2x bilinear, 1 Punkt": scheme(L2, 2, [0.0]),
        "2x, 2x2 Punkte +-1/4 px": scheme(L2, 2, [-0.25, 0.25]),
        "2x, 3x3 Punkte 0,+-1/3 px": scheme(L2, 2, [-1 / 3, 0, 1 / 3]),
        "2x, 4x4 Punkte": scheme(L2, 2, [-0.375, -0.125, 0.125, 0.375]),
    }
    ph = np.linspace(0, 1, 9)[:-1]
    for name, f in schemes.items():
        v = np.array([[lap(f(dx, dy)) for dx in ph] for dy in ph]) * 255
        print(f"{name:28s} min {v.min():6.2f}  max {v.max():6.2f}  max/min {v.max() / v.min():.2f}")


if __name__ == "__main__":
    main()
