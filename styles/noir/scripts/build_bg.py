#!/usr/bin/env python3
"""Bereitet den KI-Hintergrund (assets/raw/bg.png) für die Noir-Demo auf und rechnet die Effektmasken.

    .venv/bin/python styles/noir/scripts/build_bg.py

Schritte:
  1. Ausschnitt 16:9 (Zeilen CROP_Y0 … CROP_Y0 + 864 der 1536×1024-Quelle), Lanczos auf 1280×720.
  2. Streng schwarzweiß: Helligkeit (Rec. 601), leichte S-Kurve, Schwarz leicht abgesenkt.
  3. Masken (assets/fx_mask.png, RGB, alles in Bildschirmkoordinaten 1280×720; ohne Alphakanal, weil Godot beim
     Import die Farbe voll transparenter Pixel überschreibt):
       R  Laterne: Glas, Schein und Spiegelung auf dem Pflaster (flackert im Spiel)
       G  Lichtfeld für den Regen: weichgezeichnete helle Flächen (Laterne, Horizont, Leuchtfeuer, Fenster)
       B  offenes Wasser (Regenringe, Glitzern), ohne Boote, Steg und Pfähle
     assets/floor_mask.png (L): begehbares Pflaster (Regenspritzer, Fensterlicht), ohne Häuschen, Fässer, Kisten
  4. assets/scene.json: Lage von Laterne, Leuchtfeuer, Fenster, Horizont, Kaikante (Bildschirmkoordinaten).
"""
import json, pathlib

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "assets/raw/bg.png"
OUT = ROOT / "assets"
W, H = 1280, 720
CROP_Y0 = 100                      # Quellzeile, ab der der 16:9-Ausschnitt beginnt
S = W / 1536.0                      # Maßstab Quelle -> Bildschirm (0,8333)


def src2scr(x, y):
    return (x * S, (y - CROP_Y0) * S)


# Von Hand in der Quelle (1536×1024) abgelesen, siehe Rasterbild im Arbeitsordner
SRC = {
    "lantern": (926, 330),          # Mitte des Laternenglases
    "lantern_post_base": (962, 665),
    "lighthouse_lamp": (1362, 232),
    "window": (95, 337, 156, 566),  # x0, y0, x1, y1 (Jalousienfenster)
    "horizon_y": 515,
    "quay_edge_y": 662,             # Hinterkante des Kais am Wasser
}


def blur(a, r):
    im = Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(r))).astype(np.float32) / 255.0


def poly_mask(points, size=(W, H)):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).polygon(points, fill=255)
    return np.asarray(m).astype(np.float32) / 255.0


def main():
    src = Image.open(RAW).convert("RGB")
    assert src.size == (1536, 1024), src.size
    crop = src.crop((0, CROP_Y0, 1536, CROP_Y0 + 864)).resize((W, H), Image.LANCZOS)
    rgb = np.asarray(crop).astype(np.float32) / 255.0
    lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)

    # S-Kurve um 0,45, Schwarzpunkt 0,015
    v = np.clip((lum - 0.015) / 0.985, 0, 1)
    s = v * v * (3 - 2 * v)
    v = np.clip(0.65 * v + 0.35 * s, 0, 1)
    out = (v * 255 + 0.5).astype(np.uint8)
    Image.fromarray(np.stack([out] * 3, -1)).save(OUT / "bg.png")

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    lx, ly = src2scr(*SRC["lantern"])
    hor = (SRC["horizon_y"] - CROP_Y0) * S
    quay = (SRC["quay_edge_y"] - CROP_Y0) * S
    px, _ = src2scr(*SRC["lantern_post_base"])

    # R: Laterne. Glas + Schein (Kreis) und Spiegelung (Streifen unter dem Pfahl), nur helle Pixel.
    glow_zone = np.clip(1 - np.hypot(xx - lx, yy - ly) / 70.0, 0, 1)
    refl_zone = (np.clip(1 - np.abs(xx - (lx + 6)) / 34.0, 0, 1) *
                 np.clip((yy - quay) / 12.0, 0, 1) * np.clip((H + 40 - yy) / 120.0, 0, 1))
    bright = np.clip((v - 0.22) / 0.5, 0, 1)
    lamp = np.clip(glow_zone * (0.35 + 0.65 * bright) + refl_zone * bright * 1.2, 0, 1)
    lamp = np.maximum(lamp, blur(lamp, 2) * 0.9)

    # G: Lichtfeld für den Regen (wo Regen im Gegenlicht aufleuchtet)
    hi = np.clip((v - 0.35) / 0.45, 0, 1)
    field = blur(hi, 28) * 1.8 + blur(hi, 70) * 1.2
    field += 0.9 * np.exp(-((xx - lx) ** 2 + (yy - ly) ** 2) / (2 * 75.0 ** 2))  # Lichtkegel der Laterne
    field = np.clip(field, 0, 1)

    # B: offenes Wasser zwischen Horizont und Kaikante, ohne dunkle Silhouetten (Boote, Pfähle)
    water_zone = ((yy > hor + 3) & (yy < quay - 3) & (xx > 262)).astype(np.float32)
    sil = (blur((v < 0.12).astype(np.float32), 1.5) > 0.3).astype(np.float32)
    water = np.clip(water_zone - sil, 0, 1)
    water = blur(water, 1.0)

    # A: Pflaster vor der Kaikante; Häuschen (Wandfuß links) und Fässer/Kisten rechts ausgenommen
    floor = (yy > quay + 4).astype(np.float32)
    wall_base = lambda x: 745 * S - CROP_Y0 * S + (680 - 745) * S * (x / (310 * S))  # Wandfuß des Häuschens
    floor[(xx < 310 * S) & (yy < wall_base(xx) + 4)] = 0
    barrels = poly_mask([src2scr(1258, 610), src2scr(1536, 560), src2scr(1536, 790), src2scr(1380, 790),
                         src2scr(1258, 770)])
    floor = np.clip(floor - barrels, 0, 1)

    mask = np.stack([lamp, field, water], -1)
    Image.fromarray((mask * 255 + 0.5).astype(np.uint8), "RGB").save(OUT / "fx_mask.png")
    Image.fromarray((floor * 255 + 0.5).astype(np.uint8), "L").save(OUT / "floor_mask.png")

    wx0, wy0 = src2scr(*SRC["window"][:2])
    wx1, wy1 = src2scr(*SRC["window"][2:])
    lhx, lhy = src2scr(*SRC["lighthouse_lamp"])
    scene = {
        "size": [W, H], "crop_y0": CROP_Y0, "scale": S,
        "lantern": [round(lx, 1), round(ly, 1)], "lantern_post_x": round(px, 1),
        "lighthouse_lamp": [round(lhx, 1), round(lhy, 1)],
        "window": [round(wx0, 1), round(wy0, 1), round(wx1, 1), round(wy1, 1)],
        "horizon_y": round(hor, 1), "quay_edge_y": round(quay, 1),
    }
    (OUT / "scene.json").write_text(json.dumps(scene, indent=1))
    print(json.dumps(scene))


if __name__ == "__main__":
    main()
