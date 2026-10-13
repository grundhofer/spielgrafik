#!/usr/bin/env python3
"""Vergleichsbogen assets/sheet.png: Hafen-Anker des Stils und die drei verarbeiteten Orte (Serienpalette),
darunter dieselben Orte mit der festen Hafen-Palette und die Gegenproben. Alle Bilder in Originalgröße 416x256
(1 Bildpunkt = 1 Pixel des 640x400-Schirms), Beschriftung mit dem Schriftatlas der Demo.

    .venv/bin/python styles/ortsserie/pc98-adventure/scripts/make_sheet.py
"""
import json, pathlib

import numpy as np
from PIL import Image

SD = pathlib.Path(__file__).resolve().parent.parent
ROOT = SD.parents[2]
A = SD / "assets"
FONT = ROOT / "styles/ortsserie/demo/pc98-adventure/fonts/dotgothic16_atlas"
TW, TH, GAP, LAB = 416, 256, 12, 22

ROWS = [
    ("Serie: verarbeitet mit der gemeinsamen Serienpalette (so in den Godot-Szenen)", [
        (ROOT / "styles/pc98-adventure/assets/bg_preview.png", "Anker: Hafen (pc98-adventure, eigene Palette)"),
        (A / "leuchtturm_bg_lit.png", "Leuchtturm (Holz wird rosabraun statt ocker)"),
        (A / "stube_bg_lit.png", "Hafenmeisterstube"),
        (A / "klippe_bg_lit.png", "Klippenpfad (oben rechts aus dem Anker kopiert)")]),
    ("Feste Hafen-Palette (16 Register des Ankers) – wo sie Farben verliert", [
        (A / "hafen_bg_serie.png", "Hafen mit der Serienpalette (zum Vergleich)"),
        (A / "leuchtturm_bg_fixed.png", "Leuchtturm: Kalkwand wird Creme"),
        (A / "stube_bg_fixed.png", "Stube: Kerzenschein wird Pfirsich"),
        (A / "klippe_bg_fixed.png", "Klippe: hält (Himmel kopiert)")]),
    ("Gegenproben (Serienpalette, nur statisch verarbeitet)", [
        (A / "leuchtturm_a_bg_serie.png", "Leuchtturm A: mit Anker (Rahmen weg)"),
        (A / "leuchtturm_b_bg_serie.png", "Leuchtturm B: ohne Referenz (Rahmen weg)"),
        (A / "klippe_b_bg_serie.png", "Klippe B: ohne Referenz"),
        (None, "palettes")]),
]


def text(img, x, y, s, col):
    atlas = np.asarray(Image.open(str(FONT) + ".png").convert("RGBA"))
    g = json.loads(pathlib.Path(str(FONT) + ".json").read_text())["glyphs"]
    for ch in s:
        gx, gy, w, h, adv = g.get(ch, g["?"])
        a = atlas[gy:gy + h, gx:gx + w, 3] > 0
        ys, xs = np.nonzero(a)
        for yy, xx in zip(ys, xs):
            if 0 <= y + yy - 4 < img.shape[0] and 0 <= x + xx < img.shape[1]:
                img[y + yy - 4, x + xx] = col
        x += adv


def palettes(img, x0, y0):
    stats = json.loads((A / "build_stats.json").read_text())
    rows = [("Hafen-Palette (Anker)", stats["leuchtturm"]["fixed"]["palette"]),
            ("Serienpalette (Hafen + 3 Orte)", stats["leuchtturm"]["serie"]["palette"])]
    for r, (name, pal) in enumerate(rows):
        y = y0 + r * 110
        text(img, x0, y + 4, name, (238, 221, 187))
        for i, h in enumerate(pal):
            c = [int(h[k:k + 2], 16) for k in (0, 2, 4)]
            xx, yy = x0 + (i % 8) * 50, y + 28 + (i // 8) * 36
            img[yy:yy + 30, xx:xx + 46] = c
    text(img, x0, y0 + 230, "Register 14/15: Licht, je Ort animiert", (136, 136, 170))


def main():
    W = GAP + 4 * (TW + GAP)
    H = GAP + len(ROWS) * (LAB * 2 + TH + GAP)
    img = np.zeros((H, W, 3), np.uint8)
    img[:] = (17, 17, 34)
    y = GAP
    for title, tiles in ROWS:
        text(img, GAP, y + 4, title, (238, 153, 119))
        y += LAB
        for c, (path, label) in enumerate(tiles):
            x = GAP + c * (TW + GAP)
            if path is None:
                palettes(img, x, y)
                continue
            t = np.asarray(Image.open(path).convert("RGB"))
            img[y + LAB:y + LAB + TH, x:x + TW] = t[:TH, :TW]
            text(img, x, y + 4, label, (238, 221, 187))
        y += LAB + TH + GAP
    Image.fromarray(img).save(A / "sheet.png", optimize=True)
    print(A / "sheet.png", img.shape)


if __name__ == "__main__":
    main()
