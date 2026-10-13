#!/usr/bin/env python3
"""Glyphenatlas des Videotext-Zeichengenerators aus Bedstead (CC0, Nachbau des SAA5050).

    .venv/bin/python styles/videotext/scripts/build_atlas.py

Bedstead hat eine Zelle von 600 × 1000 Einheiten (6 × 10 Punkte, Grundlinie bei 800); die Zeichen liegen in
Punktspalte 1–5 und Punktzeile 1–9 (Spalte 0 und Zeile 0 sind der Abstand). Jede Glyphe wird mit 20-facher
Auflösung gezeichnet und auf ein festes Punktraster gebracht: jeder Punkt 3 × 3 Bildpunkte (doppelte Höhe 3 × 6),
Abstandsspalte 5, Abstandszeile 1 Bildpunkt (DOT_X, DOT_Y). Je Bildpunkt entscheidet die Deckung ≥ 50 %, also
binär wie der SAA5050 (nur Vorder- oder Hintergrundfarbe). Die halben Punkte der Zeichenglättung werden dabei
1 oder 2 Bildpunkte groß. Ein gleichmäßiges Flächenmittel auf 20 × 28 (6,67 Einheiten je Bildpunkt) ergäbe beim
Binarisieren Striche von 3 oder 4 Bildpunkten Breite; mit dem festen Raster sind alle Striche 3 Bildpunkte.
Die Punkte sind damit quadratisch (auf einem 4:3-Fernseher etwa 1,19-mal so breit wie hoch) und die Zeichen
etwas schmaler, der Zeichenabstand etwas größer als im Original.
Zeilen des Atlas: 0–5 normale Höhe, 6–11 obere Hälfte, 12–17 untere Hälfte doppelter Höhe; je Zeile 16 Zeichen
(G0-Codes 0x20–0x7F, deutscher Nationalsatz). Ausgabe: demo/fonts/g0_atlas.png (L, Deckung) und eine Vorschau.
"""
import pathlib

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import ttxlib as T

HERE = T.HERE
SS = 20                         # Überabtastung
EM = T.CH * SS                  # Zellenhöhe = 1 em
FONT = ImageFont.truetype(str(HERE / "demo" / "fonts" / "bedstead.otf"), EM)
DOT_X = [0, 5, 8, 11, 14, 17, 20]                       # Bildpunktgrenzen der Punktspalten 0–5
DOT_Y = [0, 1, 4, 7, 10, 13, 16, 19, 22, 25, 28]        # Bildpunktgrenzen der Punktzeilen 0–9 (normale Höhe)


def coverage(ch, height_cells):
    w = int(round(0.6 * EM))
    im = Image.new("L", (w, EM), 0)
    ImageDraw.Draw(im).text((0, int(0.8 * EM)), ch, font=FONT, fill=255, anchor="ls")
    a = np.asarray(im, dtype=np.float32) / 255.0
    # Bildpunktgrenzen über das Punktraster auf die gezeichnete Glyphe abbilden (stückweise linear)
    out_h, out_w = T.CH * height_cells, T.CW
    xs = np.interp(np.arange(out_w + 1), DOT_X, np.arange(7) * a.shape[1] / 6)
    ys = np.interp(np.arange(out_h + 1), [v * height_cells for v in DOT_Y], np.arange(11) * a.shape[0] / 10)
    # exakte Box-Mittelung über Integralbild
    ii = np.zeros((a.shape[0] + 1, a.shape[1] + 1))
    ii[1:, 1:] = a.cumsum(0).cumsum(1)

    def integ(y, x):  # bilinear im Integralbild (Bruchteile)
        y0, x0 = int(np.floor(y)), int(np.floor(x))
        y0, x0 = min(y0, a.shape[0] - 1), min(x0, a.shape[1] - 1)
        fy, fx = y - y0, x - x0
        v00, v01, v10, v11 = ii[y0, x0], ii[y0, x0 + 1], ii[y0 + 1, x0], ii[y0 + 1, x0 + 1]
        return v00 * (1 - fy) * (1 - fx) + v01 * (1 - fy) * fx + v10 * fy * (1 - fx) + v11 * fy * fx

    res = np.zeros((out_h, out_w))
    for j in range(out_h):
        for i in range(out_w):
            y0, y1, x0, x1 = ys[j], ys[j + 1], xs[i], xs[i + 1]
            s = integ(y1, x1) - integ(y0, x1) - integ(y1, x0) + integ(y0, x0)
            res[j, i] = s / ((y1 - y0) * (x1 - x0))
    return (res >= 0.5).astype(np.float32)            # binär: Deckung ab 50 %


def main():
    at = np.zeros((18 * T.CH, 16 * T.CW), dtype=np.float32)
    for code in range(0x20, 0x80):
        ch = T.G0[code]
        i = code - 0x20
        gx, gy = (i % 16) * T.CW, (i // 16) * T.CH
        n = coverage(ch, 1)
        d = coverage(ch, 2)
        at[gy:gy + T.CH, gx:gx + T.CW] = n
        at[gy + 6 * T.CH:gy + 7 * T.CH, gx:gx + T.CW] = d[:T.CH]
        at[gy + 12 * T.CH:gy + 13 * T.CH, gx:gx + T.CW] = d[T.CH:]
    img = Image.fromarray(np.clip(at * 255 + 0.5, 0, 255).astype(np.uint8), "L")
    img.save(HERE / "demo" / "fonts" / "g0_atlas.png")
    # Vorschau: Atlas ×2 auf Blau
    prev = Image.new("RGB", img.size, (0, 0, 255))
    prev.paste((255, 255, 0), mask=img)
    prev.resize((img.width * 2, img.height * 2), Image.NEAREST).save(HERE / "assets" / "charset.png")
    print("ok", img.size)


if __name__ == "__main__":
    main()
