#!/usr/bin/env python3
"""Geschnittener Schlagschatten des Dachses (Code, fester Seed).

    .venv/bin/python styles/holzschnitt/scripts/make_fx.py

shadow.png  136x24 RGBA: Schwarzstock (R = 1) als waagerechte, an den Enden spitz auslaufende Schnittstreifen in
            einer flachen Ellipse; Alpha = Deckung. Wird im Platten-Viewport unter den Dachs gelegt.
"""
import pathlib
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    W, H = 136, 24
    S = 4                                    # Überabtastung
    rng = np.random.default_rng(7)
    yy, xx = np.mgrid[0:H * S, 0:W * S].astype(np.float64) / S
    cx, cy, rx, ry = W / 2, H / 2, W / 2 - 2, H / 2 - 3
    e = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2
    cov = np.zeros_like(xx)
    # 5 Streifen, 2,2 px hoch, Abstand 3,6 px; je Streifen eigene Länge und Versatz (von Hand geschnitten)
    for i, y0 in enumerate(np.arange(cy - 7.2, cy + 7.3, 3.6)):
        half = rx * np.sqrt(max(0.0, 1 - ((y0 - cy) / (ry + 1.5)) ** 2)) * rng.uniform(0.82, 1.0)
        sx = cx + rng.uniform(-6, 6)
        u = np.clip(1 - np.abs(xx - sx) / max(half, 1), 0, 1)           # 1 in der Mitte, 0 am Ende
        th = 1.1 + 0.9 * np.sqrt(u)                                       # halbe Höhe: spitz auslaufend
        cov = np.maximum(cov, (np.abs(yy - y0) <= th * (u > 0)).astype(float))
    cov *= (e <= 1.15)
    a = np.asarray(Image.fromarray((cov * 255).astype(np.uint8)).resize((W, H), Image.BOX)).astype(np.float32) / 255
    img = np.zeros((H, W, 4), np.uint8)
    img[..., 0] = 255
    img[..., 3] = (a * 255 + 0.5).astype(np.uint8)
    for d in (ROOT / "assets", ROOT / "demo/art"):
        Image.fromarray(img, "RGBA").save(d / "shadow.png")
    print("ok shadow.png", W, H)


if __name__ == "__main__":
    main()
