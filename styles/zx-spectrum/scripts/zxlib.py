"""Gemeinsame Teile für den Eintrag zx-spectrum: Palette, Bildschirmformat (.scr), Darstellung.

Bildschirm wie auf der Hardware: 6144 Bytes Bitmap (256×192, 1 Bit je Pixel, Zeilen verschränkt adressiert)
und 768 Bytes Attribute (32×24 Zellen à 8×8: Bit 7 FLASH, Bit 6 BRIGHT, Bits 5–3 PAPER, Bits 2–0 INK).
"""
import numpy as np

# Farbnummern 0–7 (Schwarz, Blau, Rot, Magenta, Grün, Cyan, Gelb, Weiß), normal und hell.
# Werte wie tools/sprites.py --palette zx (0xD7 normal, 0xFF hell; Schwarz hat keine helle Variante).
NORMAL = np.array([[0, 0, 0], [0, 0, 0xD7], [0xD7, 0, 0], [0xD7, 0, 0xD7],
                   [0, 0xD7, 0], [0, 0xD7, 0xD7], [0xD7, 0xD7, 0], [0xD7, 0xD7, 0xD7]], dtype=np.uint8)
BRIGHT = np.array([[0, 0, 0], [0, 0, 0xFF], [0xFF, 0, 0], [0xFF, 0, 0xFF],
                   [0, 0xFF, 0], [0, 0xFF, 0xFF], [0xFF, 0xFF, 0], [0xFF, 0xFF, 0xFF]], dtype=np.uint8)
PAL16 = np.concatenate([NORMAL, BRIGHT])          # Index = bright*8 + Farbe
NAMES = "kbrmgcyw"                                  # Buchstaben für Patches: klein = normal, GROSS = hell
W, H = 256, 192


def attr_byte(ink, paper, bright=0, flash=0):
    return (flash << 7) | (bright << 6) | ((paper & 7) << 3) | (ink & 7)


def unpack_attr(a):
    return a & 7, (a >> 3) & 7, (a >> 6) & 1, (a >> 7) & 1


def addr(col, y):
    """Bitmap-Adresse (0..6143) der Bytespalte col (0..31) in Pixelzeile y (0..191)."""
    return ((y & 0xC0) << 5) | ((y & 0x07) << 8) | ((y & 0x38) << 2) | col


def pack(bits, attrs):
    """bits: 192×256 (0/1), attrs: 24×32 Bytes -> 6912 Bytes .scr."""
    scr = bytearray(6912)
    for y in range(H):
        row = np.packbits(bits[y].astype(np.uint8))
        for c in range(32):
            scr[addr(c, y)] = int(row[c])
    scr[6144:] = bytes(np.asarray(attrs, dtype=np.uint8).reshape(-1))
    return bytes(scr)


def unpack(scr):
    scr = np.frombuffer(bytes(scr), dtype=np.uint8)
    bits = np.zeros((H, W), np.uint8)
    for y in range(H):
        row = np.array([scr[addr(c, y)] for c in range(32)], np.uint8)
        bits[y] = np.unpackbits(row)
    return bits, scr[6144:6912].reshape(24, 32).copy()


def render(bits, attrs, flash_phase=0):
    """RGB-Bild 256×192 wie die Hardware es zeigt."""
    a = np.asarray(attrs).astype(np.int32)
    ink, paper, br, fl = a & 7, (a >> 3) & 7, (a >> 6) & 1, (a >> 7) & 1
    if flash_phase:
        ink, paper = np.where(fl == 1, paper, ink), np.where(fl == 1, ink, paper)
    ink_f = np.repeat(np.repeat(ink + 8 * br, 8, 0), 8, 1)
    pap_f = np.repeat(np.repeat(paper + 8 * br, 8, 0), 8, 1)
    idx = np.where(np.asarray(bits) > 0, ink_f, pap_f)
    return PAL16[idx]


def oklab(rgb):
    c = np.clip(np.asarray(rgb, dtype=np.float64), 0, 255) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]])
    m2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]])
    return np.cbrt(c @ m1.T) @ m2.T


def cell_colours(img_rgb):
    """Prüfung: je 8×8-Zelle die Menge der vorkommenden Farben (für Bilder 256×192)."""
    out = {}
    for cy in range(img_rgb.shape[0] // 8):
        for cx in range(img_rgb.shape[1] // 8):
            blk = img_rgb[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8].reshape(-1, 3)
            out[(cx, cy)] = {tuple(int(v) for v in c) for c in np.unique(blk, axis=0)}
    return out


def cell_ok(colours):
    """Zellregel: höchstens zwei Farben, beide aus derselben Helligkeitsgruppe (Schwarz passt zu beiden)."""
    if len(colours) > 2:
        return False
    nonblack = [c for c in colours if c != (0, 0, 0)]
    if len(nonblack) < 2:
        return True
    hi = [max(c) == 0xFF for c in nonblack]
    return hi[0] == hi[1]
