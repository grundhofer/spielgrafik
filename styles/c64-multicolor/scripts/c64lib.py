"""Gemeinsame Helfer für den Eintrag c64-multicolor: Palette, Oklab, Speicherformate des Videochips.

Palette = tools/sprites.py --palette c64 (16 feste Farben, Reihenfolge = Farbnummern 0-15 der Hardware).
"""
import pathlib

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]          # styles/c64-multicolor
PROJECT = ROOT.parents[1]

PAL_HEX = "000000 ffffff 68372b 70a4b2 6f3d86 588d43 352879 b8c76f 6f4f25 433900 9a6759 444444 6c6c6c 9ad284 6c5eb5 959595"
PAL = np.array([[int(h[i:i + 2], 16) for i in (0, 2, 4)] for h in PAL_HEX.split()], dtype=np.uint8)
NAMES = ["schwarz", "weiß", "rot", "cyan", "lila", "grün", "blau", "gelb", "orange", "braun", "hellrot",
         "dunkelgrau", "grau", "hellgrün", "hellblau", "hellgrau"]
BLACK, WHITE, RED, CYAN, PURPLE, GREEN, BLUE, YELLOW, ORANGE, BROWN, LRED, DGREY, GREY, LGREEN, LBLUE, LGREY = range(16)


def oklab(rgb):
    c = np.clip(np.asarray(rgb, dtype=np.float64), 0, 255) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]])
    m2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]])
    return np.cbrt(c @ m1.T) @ m2.T


PAL_LAB = oklab(PAL)


def nearest(rgb, allowed=None):
    """Nächste Palettenfarbe (Oklab) je Pixel; allowed = Liste erlaubter Farbnummern."""
    lab = oklab(rgb)
    idx = np.arange(16) if allowed is None else np.array(allowed)
    d = ((lab[..., None, :] - PAL_LAB[idx]) ** 2).sum(-1)
    return idx[d.argmin(-1)]


def to_rgb(idx):
    return PAL[np.asarray(idx)]


def bitmap_bytes(pairs):
    """160x200 Bitpaare (0-3) -> 8000 Bytes im Format des Videochips (Zelle für Zelle, 8 Bytes je Zelle)."""
    out = bytearray(8000)
    for cy in range(25):
        for cx in range(40):
            for r in range(8):
                p = pairs[cy * 8 + r, cx * 4:cx * 4 + 4]
                out[(cy * 40 + cx) * 8 + r] = (int(p[0]) << 6) | (int(p[1]) << 4) | (int(p[2]) << 2) | int(p[3])
    return bytes(out)


def sprite_bytes(rows, mc):
    """24x21 Werte (hires: 0/1 je Pixel, mc: 0-3 je Doppelpixel, in beiden Spalten gleich) -> 63 Bytes (+1 Füllbyte)."""
    out = bytearray(64)
    for y in range(21):
        bits = 0
        for x in range(24):
            if mc:
                if x % 2:
                    continue
                bits = (bits << 2) | int(rows[y][x])
            else:
                bits = (bits << 1) | (1 if rows[y][x] else 0)
        out[y * 3:y * 3 + 3] = bits.to_bytes(3, "big")
    return bytes(out)
