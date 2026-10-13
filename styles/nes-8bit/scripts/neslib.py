"""Gemeinsame Daten und Helfer für den Eintrag nes-8bit: Systempalette, Oklab, Musterformat."""
import numpy as np

# Systempalette der 8-Bit-Konsole (64 Einträge, $0D-$0F, $1D-$1F, $2E/$2F, $3E/$3F schwarz).
# Gleiche Werte wie die Palette "nes" in tools/sprites.py, hier mit festen Nummern.
SYSPAL_HEX = [
    "7c7c7c", "0000fc", "0000bc", "4428bc", "940084", "a80020", "a81000", "881400",
    "503000", "007800", "006800", "005800", "004058", "000000", "000000", "000000",
    "bcbcbc", "0078f8", "0058f8", "6844fc", "d800cc", "e40058", "f83800", "e45c10",
    "ac7c00", "00b800", "00a800", "00a844", "008888", "000000", "000000", "000000",
    "f8f8f8", "3cbcfc", "6888fc", "9878f8", "f878f8", "f85898", "f87858", "fca044",
    "f8b800", "b8f818", "58d854", "58f898", "00e8d8", "787878", "000000", "000000",
    "fcfcfc", "a4e4fc", "b8b8f8", "d8b8f8", "f8b8f8", "f8a4c0", "f0d0b0", "fce0a8",
    "f8d878", "d8f878", "b8f8b8", "b8f8d8", "00fcfc", "f8d8f8", "000000", "000000",
]
SYSPAL = np.array([[int(h[i:i + 2], 16) for i in (0, 2, 4)] for h in SYSPAL_HEX], dtype=np.float32)
BLACK = 0x0F
# Nutzbare Nummern: ein Schwarz ($0F) statt der Doppelten; $0D ("schwärzer als schwarz") meiden.
USABLE = [i for i in range(64) if SYSPAL_HEX[i] != "000000"] + [BLACK]


def oklab(rgb):
    c = np.clip(np.asarray(rgb, dtype=np.float64), 0, 255) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]])
    m2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]])
    return np.cbrt(c @ m1.T) @ m2.T


SYS_LAB = oklab(SYSPAL)


def nearest_sys(rgb, allowed=None):
    """RGB-Feld (...,3) -> Systemfarbnummern (Oklab-Abstand), optional nur aus 'allowed'."""
    allowed = np.array(USABLE if allowed is None else allowed)
    lab = oklab(rgb)
    d = ((lab[..., None, :] - SYS_LAB[allowed]) ** 2).sum(-1)
    return allowed[d.argmin(-1)]


def lab_dist2(a, b):
    """Quadratischer Oklab-Abstand zwischen Systemfarbnummern (Matrix 64x64)."""
    return ((SYS_LAB[a][..., None, :] - SYS_LAB[b][..., None, :, :]) ** 2).sum(-1) if False else None


D2 = ((SYS_LAB[:, None, :] - SYS_LAB[None, :, :]) ** 2).sum(-1)   # 64x64


def tile_bytes(px):
    """8x8-Feld mit Farbnummern 0..3 -> 16 Byte im 2-Bit-Planarformat (8 Byte Ebene 0, dann 8 Byte Ebene 1)."""
    px = np.asarray(px, dtype=np.uint8)
    lo = [int(sum(((px[y, x] & 1) << (7 - x)) for x in range(8))) for y in range(8)]
    hi = [int(sum((((px[y, x] >> 1) & 1) << (7 - x)) for x in range(8))) for y in range(8)]
    return bytes(lo + hi)


def bytes_tile(b):
    out = np.zeros((8, 8), np.uint8)
    for y in range(8):
        for x in range(8):
            out[y, x] = ((b[y] >> (7 - x)) & 1) | (((b[8 + y] >> (7 - x)) & 1) << 1)
    return out
