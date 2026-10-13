#!/usr/bin/env python3
"""Lichttexturen in Pixel-Optik (Stufen statt Verlauf, Bayer-Raster an den Stufenkanten) und Möwen-Flügelschlag.

    .venv/bin/python styles/kachelsatz/scripts/build_lights.py
"""
import pathlib

import numpy as np
from PIL import Image

ENTRY = pathlib.Path(__file__).resolve().parent.parent
ART = ENTRY / "demo" / "art"
BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0


def stepped(v, steps=4):
    """Wert 0..1 in Stufen; zwischen den Stufen entscheidet das Bayer-Raster (geordnetes Dithering)."""
    h, w = v.shape
    th = BAYER[np.arange(h)[:, None] % 4, np.arange(w)[None, :] % 4]
    q = np.floor(v * steps + th) / steps
    return np.clip(q, 0, 1)


def save_l(v, name):
    a = (stepped(v) * 255).astype(np.uint8)
    Image.fromarray(np.stack([a, a, a], -1)).save(ART / name)


def main():
    # rundes Licht 96x96 (wird in Godot gestreckt; Raster bleibt, weil die Szene in 426x240 gerendert wird)
    n = 96
    y, x = np.mgrid[0:n, 0:n] + 0.5
    r = np.hypot(x - n / 2, y - n / 2) / (n / 2)
    save_l(np.clip(1 - r, 0, 1) ** 1.4, "light_round.png")
    # Leuchtturmstrahl: Kegel nach rechts, Spitze in der Bildmitte (256x256)
    n = 256
    y, x = np.mgrid[0:n, 0:n] + 0.5
    dx, dy = x - n / 2, y - n / 2
    ang = np.abs(np.arctan2(dy, dx))
    dist = np.hypot(dx, dy) / (n / 2)
    cone = np.clip(1 - ang / np.radians(11), 0, 1) ** 0.7 * (dx > 0)
    fall = np.clip(1 - dist, 0, 1) ** 0.6
    save_l(cone * fall, "light_beam.png")
    # Möwe: zweites Bild mit angelegten Flügeln (Breite auf 70 %, Mitte bleibt), nächster Nachbar
    g = Image.open(ART / "gull.png").convert("RGBA")
    w, h = g.size
    nw = int(round(w * 0.7))
    sq = g.resize((nw, h), Image.NEAREST)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas.paste(sq, ((w - nw) // 2, 0))
    canvas.save(ART / "gull_flap.png")
    print("ok")


if __name__ == "__main__":
    main()
