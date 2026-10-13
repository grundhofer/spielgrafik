#!/usr/bin/env python3
"""Versuch: KI-Bild automatisch in eine Videotext-Seite umsetzen (ohne Handzeichnung).

    .venv/bin/python styles/videotext/scripts/ai_convert.py assets/raw/bg_a.png

Je Mosaikpunkt (80 × 57, Sechstel-Zeilen 2:3:2 wie im Zeichengenerator) die häufigste der 8 Farben (nächste
Farbe in Oklab je Bildpunkt), dann dieselbe Zeilen-DP wie für die Seite (ttxenc). Ausgabe:
assets/ki_automatisch.png = links das Mosaikraster nach Farbwahl, rechts die regelkonforme Seite.
"""
import pathlib
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_page as BP  # noqa: E402
import ttxenc as E  # noqa: E402
import ttxlib as T  # noqa: E402


def main():
    src = T.HERE / sys.argv[1]
    a = np.asarray(Image.open(src).convert("RGB"), dtype=np.float64)
    lab = E._oklab(a.reshape(-1, 3)).reshape(a.shape)
    d = ((lab[:, :, None, :] - E._LAB[None, None]) ** 2).sum(-1)
    idx = d.argmin(-1)
    H, W = idx.shape
    grid = np.zeros((57, 80), dtype=int)
    for r in range(19):
        y0, h = r * H / 19, H / 19
        for k, (f0, f1) in enumerate(((0, 2 / 7), (2 / 7, 5 / 7), (5 / 7, 1))):
            ya, yb = int(y0 + f0 * h + 0.5), int(y0 + f1 * h + 0.5)
            for x in range(80):
                xa, xb = int(x * W / 80 + 0.5), int((x + 1) * W / 80 + 0.5)
                grid[3 * r + k, x] = np.bincount(idx[ya:yb, xa:xb].ravel(), minlength=8).argmax()
    page = T.blank_page()
    w = np.ones(grid.shape)
    sep = np.zeros((19, 40), dtype=int)
    rows, stats = BP.encode_picture(grid, grid, w, sep, rows=range(1, 20), log=False)
    for r, b in rows.items():
        page[r] = b
    miss = sum(s[3] for s in stats)
    img = T.render(T.decode_page(page))[T.CH:20 * T.CH]
    left = np.repeat(np.repeat(T.PALETTE[grid], 10, 1), [8, 12, 8] * 19, 0)
    out = np.concatenate([left, np.zeros((left.shape[0], 20, 3), np.uint8), img], 1)
    Image.fromarray(out).save(T.HERE / "assets" / "ki_automatisch.png")
    print(f"{src.name}: {miss} von {19 * 240} Sechsteln weichen nach der Regel-DP vom Raster ab, "
          f"{sum(s[4] for s in stats)} Steuerzellen")


if __name__ == "__main__":
    main()
