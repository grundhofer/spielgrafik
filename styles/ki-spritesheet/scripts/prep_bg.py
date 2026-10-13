#!/usr/bin/env python3
"""Hintergrund aufbereiten: agy-Bild (1264×848) auf 1280 Breite skalieren, auf 16:9 beschneiden, Wassermaske.

    .venv/bin/python styles/ki-spritesheet/scripts/prep_bg.py [--grid out.png]

Schreibt assets/bg.png, assets/bg_mask.png (R = Wasser, G = freier Himmel ohne Objekte) und kopiert beide nach demo/art/.
Wasser wird über die Farbe gewählt (türkis/blau unter dem Horizont, über der Kaikante); Boote, Steg, Felsen und
die Laterne bleiben draußen, weil sie andere Farbtöne haben.
"""
import argparse, pathlib, shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

E = pathlib.Path(__file__).resolve().parents[1]
TOP = 84            # erste Zeile des Ausschnitts nach dem Skalieren
HORIZON = 427 - TOP  # Horizont im skalierten Bild (Zeile 422 im Rohbild ×1,0127)
QUAY = 628 - TOP     # Kaikante (Wasser endet), skaliert


CONTOUR_MAX = 70     # Konturen der Objekte: hellster Kanal unter 70 (Wolkenränder und Himmel liegen bei ≥ 84)


def sky_mask(rgb):
    """Freier Himmel (für die Möwen): Flutfüllung von der oberen Bildkante über dem Horizont, die nur an den
    dunklen Objektkonturen stoppt. Dach, Schornstein, Leuchtturm, Felsen, Laterne und Pfahl sind rundum dunkel
    umrandet und bleiben draußen; Wolken (heller, dünner Rand) gehören zum Himmel. Danach 1 px erodiert, damit
    auch der weiche Rand der Konturen als Objekt zählt."""
    passable = (rgb.max(-1) >= CONTOUR_MAX)
    passable[HORIZON - 1:] = False
    # Laternenhaus des Leuchtturms: Dachkappe und Glas haben dünne, helle Ränder, die Flut liefe sonst hinein
    passable[28:87, 1086:1141] = False
    sky = np.zeros_like(passable)
    sky[0] = passable[0]
    while True:
        grown = sky.copy()
        grown[1:] |= sky[:-1]
        grown[:-1] |= sky[1:]
        grown[:, 1:] |= sky[:, :-1]
        grown[:, :-1] |= sky[:, 1:]
        grown &= passable
        if (grown == sky).all():
            break
        sky = grown
    er = sky.copy()
    er[1:] &= sky[:-1]
    er[:-1] &= sky[1:]
    er[:, 1:] &= sky[:, :-1]
    er[:, :-1] &= sky[:, 1:]
    return er


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid")
    a = ap.parse_args()
    raw = Image.open(E / "assets/raw/bg.png").convert("RGB")
    s = 1280 / raw.width
    big = raw.resize((1280, round(raw.height * s)), Image.LANCZOS)
    bg = big.crop((0, TOP, 1280, TOP + 720))
    bg.save(E / "assets/bg.png")
    arr = np.asarray(bg).astype(np.float32) / 255
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    yy = np.arange(720)[:, None] * np.ones((1, 1280))
    # Wasser: Blau/Grün deutlich über Rot, unterhalb des Horizonts, oberhalb der Kaikante
    water = (b > r + 0.12) & (g > r + 0.05) & (yy > HORIZON + 1) & (yy < QUAY + 4)
    m = Image.fromarray((water * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3))
    sky = Image.fromarray(sky_mask(np.asarray(bg)).astype(np.uint8) * 255)
    mask = Image.merge("RGB", (m, sky, Image.new("L", (1280, 720), 0)))
    mask.save(E / "assets/bg_mask.png")
    for f in ("bg.png", "bg_mask.png"):
        shutil.copy2(E / "assets" / f, E / "demo/art" / f)
    print("Wasseranteil", round(float(np.asarray(m).mean() / 255), 3))
    if a.grid:
        g2 = bg.copy()
        d = ImageDraw.Draw(g2)
        for x in range(0, 1280, 50):
            d.line([(x, 0), (x, 720)], fill=(255, 255, 0) if x % 100 == 0 else (90, 90, 0))
            if x % 100 == 0:
                d.text((x + 2, 2), str(x), fill=(255, 255, 0))
        for y in range(0, 720, 50):
            d.line([(0, y), (1280, y)], fill=(255, 255, 0) if y % 100 == 0 else (90, 90, 0))
            if y % 100 == 0:
                d.text((2, y + 2), str(y), fill=(255, 255, 0))
        g2.save(a.grid)


if __name__ == "__main__":
    main()
