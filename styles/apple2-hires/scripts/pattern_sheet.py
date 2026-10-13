"""Übersicht aller Füllmuster nach dem Farbmodell (assets/patterns_preview.png) und ihre Mittelfarben.

    .venv/bin/python styles/apple2-hires/scripts/pattern_sheet.py
"""
import json, pathlib
import numpy as np
from PIL import Image, ImageDraw
from a2lib import render, PAL16
from patterns import PATTERNS, pattern_tile

ENTRY = pathlib.Path(__file__).resolve().parent.parent


def pack(bits, grp):
    """Bits (rows, 280) und Gruppe je Bildpunkt -> Bytes (rows, 40)."""
    rows = bits.shape[0]
    mem = np.zeros((rows, 40), np.uint8)
    for k in range(7):
        mem |= (bits[:, k::7] << k).astype(np.uint8)
    mem |= (grp[:, ::7] << 7).astype(np.uint8)
    return mem


def mean_colour(name):
    b = np.zeros((32, 280), np.uint8)
    g = np.zeros((32, 280), np.uint8)
    tb, tg = pattern_tile(name, 280, 32)
    rgb = render(pack(tb, tg)).astype(np.float64) / 255.0
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    m = lin[4:28, 14:266].reshape(-1, 3).mean(0)
    s = np.where(m <= 0.0031308, m * 12.92, 1.055 * m ** (1 / 2.4) - 0.055)
    return [int(round(v * 255)) for v in s]


def main():
    names = list(PATTERNS)
    cols = 6
    cw, chh = 42, 28        # 6 Bytes breit inkl. Abstand
    rows = (len(names) + cols - 1) // cols
    bits = np.zeros((rows * (chh + 4), 280), np.uint8)
    grp = np.zeros_like(bits)
    for i, n in enumerate(names):
        cx, cy = (i % cols) * cw + 7, (i // cols) * (chh + 4) + 2
        tb, tg = pattern_tile(n, 28, 20, cx, cy)
        bits[cy:cy + 20, cx:cx + 28] = tb
        grp[cy:cy + 20, cx:cx + 28] = tg
    img = render(pack(bits, grp))
    S = 3
    big = Image.fromarray(np.repeat(np.repeat(img, S, 0), S, 1))
    canvas = Image.new("RGB", (big.width, big.height + rows * 14), (30, 30, 30))
    out = Image.new("RGB", (big.width, rows * (chh + 4) * S + rows * 0), (0, 0, 0))
    d = ImageDraw.Draw(big)
    means = {}
    for i, n in enumerate(names):
        cx, cy = (i % cols) * cw + 7, (i // cols) * (chh + 4) + 2
        means[n] = mean_colour(n)
        d.text((cx * S, (cy + 20) * S + 1), n, fill=(255, 255, 255))
    big.save(ENTRY / "assets" / "patterns_preview.png")
    (ENTRY / "assets" / "pattern_means.json").write_text(json.dumps(means, indent=0))
    for n in names:
        print(n, "#%02x%02x%02x" % tuple(means[n]))


if __name__ == "__main__":
    main()
