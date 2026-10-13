#!/usr/bin/env python3
"""Versuch: KI-Figurenblatt (assets/raw/badger_ai.png) automatisch auf das Dachsraster (11 × 15 Mosaikpunkte)
bringen und mit den handgesetzten Bildern vergleichen.

    .venv/bin/python styles/videotext/scripts/badger_ai_versuch.py

Je Figur: Begrenzungsrahmen der nicht schwarzen und nicht weißen Bodenpunkte, Raster 11 × 15, je Mosaikpunkt
die häufigste der 8 Farben (Oklab), dann dieselbe Zeilen-DP auf schwarzem Grund. Ausgabe:
assets/badger_ki_vs_hand.png – oben KI-Seitenansicht und -Vorderansicht, unten die Handfassung (walk0, front0).
"""
import pathlib
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sprites_ttx as S  # noqa: E402
import ttxenc as E  # noqa: E402
import ttxlib as T  # noqa: E402


def to_grid(img, box, w=11, h=15):
    a = np.asarray(img.crop(box).convert("RGB"), dtype=np.float64)
    lab = E._oklab(a.reshape(-1, 3)).reshape(a.shape)
    idx = ((lab[:, :, None, :] - E._LAB[None, None]) ** 2).sum(-1).argmin(-1)
    H, W = idx.shape
    g = np.zeros((h, w), dtype=int)
    for y in range(h):
        for x in range(w):
            blk = idx[int(y * H / h):int((y + 1) * H / h), int(x * W / w):int((x + 1) * W / w)]
            g[y, x] = np.bincount(blk.ravel(), minlength=8).argmax()
    return g


def render_sprite(g):
    """Figur auf schwarzem Grund in Zeilen 1–5 einer leeren Seite kodieren und als Bild liefern."""
    t = np.zeros((15, 80), dtype=int)
    t[:, 4:4 + g.shape[1]] = np.where(g < 0, 0, g)
    page = T.blank_page()
    for r in range(5):
        b, _, _ = E.encode_row(t[3 * r:3 * r + 3], w=np.where(t[3 * r:3 * r + 3] > 0, 4.0, 1.0))
        page[1 + r] = b
    img = T.render(T.decode_page(page))
    return img[T.CH:6 * T.CH, 0:10 * T.CW]


def main():
    src = Image.open(T.HERE / "assets" / "raw" / "badger_ai.png")
    # Figuren ohne den weißen Boden: Rahmen von Hand aus dem Bild abgelesen (1264 × 848)
    side = to_grid(src, (80, 15, 560, 780))
    front = to_grid(src, (740, 30, 1250, 780))
    spr = S.load()
    tiles = [render_sprite(side), render_sprite(front), render_sprite(spr["walk0"]), render_sprite(spr["front0"])]
    pad = lambda t: np.pad(t, ((6, 6), (6, 6), (0, 0)), constant_values=70)
    top = np.concatenate([pad(tiles[0]), pad(tiles[1])], 1)
    bot = np.concatenate([pad(tiles[2]), pad(tiles[3])], 1)
    Image.fromarray(np.concatenate([top, bot], 0)).save(T.HERE / "assets" / "badger_ki_vs_hand.png")
    for name, g in (("Seite", side), ("Vorne", front)):
        print(name)
        for row in g:
            print("  " + "".join(T.NAMES[v] if v else "." for v in row))


if __name__ == "__main__":
    main()
