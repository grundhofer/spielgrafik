"""Gemeinsame Bausteine für apple2-hires: Hi-Res-Speicher (40 Bytes × 192 Zeilen, Bit 7 = Farbgruppe),
Farbmodell (wie demo/shaders/hires.gdshader) und Füllmuster.

Speicher: mem[y, b] ist das Byte für die Bildpunkte x = 7b … 7b+6 der Zeile y; Bit 0 ist der linke Bildpunkt,
Bit 7 die Farbgruppe (0 = Violett/Grün, 1 = Blau/Orange; verschiebt die 7 Bildpunkte um einen halben Punkt).

Farbmodell (Farbfernseher, „Farbsäume“): Jeder Bildpunkt sind zwei Halbpunkte des 560er-Signals; bei Bit 7 = 1
kommen sie einen Halbpunkt später, die Lücke füllt der letzte Halbpunkt des Byte davor. Die Farbe eines
Bildpunkts ergibt sich aus dem Fenster von 4 Halbpunkten um ihn herum (eine Periode des Farbträgers): welche
der vier Phasen gesetzt sind, ergibt eine der 16 Farben. Gleichmäßige Streifen (1010…) werden so zur vollen
Fläche, benachbarte gesetzte Punkte weiß, an Kanten entstehen Säume in Zwischenfarben.
"""
import numpy as np

W, H = 280, 192
GFX_H = 160

# 16 Farben des NTSC-Modells (Index = gesetzte Phasen 0..3 als Bits), sRGB-Werte wie in Emulatoren üblich
PAL16 = np.array([
    (0, 0, 0),        # 0 schwarz
    (144, 23, 64),    # 1 dunkelrot (nur Saum)
    (64, 44, 165),    # 2 dunkelblau (nur Saum)
    (208, 67, 229),   # 3 VIOLETT   (Gruppe 0, gerade Spalte)
    (0, 105, 64),     # 4 dunkelgrün (nur Saum)
    (128, 128, 128),  # 5 grau (nur Saum)
    (47, 149, 229),   # 6 BLAU      (Gruppe 1, gerade Spalte)
    (191, 171, 255),  # 7 hellblau (nur Saum)
    (64, 84, 0),      # 8 braun (nur Saum)
    (208, 106, 26),   # 9 ORANGE    (Gruppe 1, ungerade Spalte)
    (128, 128, 128),  # 10 grau (nur Saum)
    (255, 150, 191),  # 11 rosa (nur Saum)
    (47, 188, 26),    # 12 GRÜN     (Gruppe 0, ungerade Spalte)
    (191, 211, 90),   # 13 gelb (nur Saum)
    (111, 232, 191),  # 14 türkis (nur Saum)
    (255, 255, 255),  # 15 WEISS
], dtype=np.uint8)

# die sechs Hi-Res-Farben (Index in PAL16)
BLACK, VIOLET, BLUE, ORANGE, GREEN, WHITE = 0, 3, 6, 9, 12, 15


def bits_of(mem):
    """(192, 40) Bytes -> (192, 280) Bits und (192, 280) Gruppe je Bildpunkt."""
    b = np.zeros((mem.shape[0], W), np.uint8)
    for k in range(7):
        b[:, k::7] = (mem >> k) & 1
    hi = np.repeat((mem >> 7) & 1, 7, axis=1)
    return b, hi


def dots_of(mem):
    """560 Halbpunkte je Zeile, mit Verzögerung bei Bit 7 = 1."""
    bits, hi = bits_of(mem)
    rows = mem.shape[0]
    d = np.zeros((rows, 2 * W + 2), np.uint8)
    for bidx in range(40):
        h = (mem[:, bidx] >> 7) & 1
        x0 = 7 * bidx
        seg = np.repeat(bits[:, x0:x0 + 7], 2, axis=1)          # 14 Halbpunkte
        s = 14 * bidx
        # h = 0: an Stelle s..s+13; h = 1: s+1..s+14, Stelle s hält den letzten Halbpunkt des Byte davor
        m0 = h == 0
        d[m0, s:s + 14] = seg[m0]
        m1 = ~m0
        if m1.any():
            prev = bits[m1, x0 - 1] if x0 > 0 else np.zeros(m1.sum(), np.uint8)
            d[m1, s] = prev
            d[m1, s + 1:s + 15] = seg[m1]
    # Ein späteres Byte mit h = 0 überschreibt den übergelaufenen Halbpunkt: oben schon durch die Reihenfolge,
    # weil Byte b+1 mit h = 0 Stelle 14(b+1) danach neu schreibt.
    return d[:, :2 * W]


def render(mem, model="fringe"):
    """RGB-Bild (rows, 280, 3) nach dem Farbmodell.

    model: "fringe" (4-Halbpunkte-Fenster für jeden Bildpunkt), "crisp" (Fenster nur für gesetzte Bildpunkte und
    Lücken zwischen zwei gesetzten; übrige ungesetzte Punkte schwarz: helle Säume bleiben, dunkle fallen weg)
    oder "ideal" (sechs Farben, ohne Säume)."""
    bits, hi = bits_of(mem)
    rows = mem.shape[0]
    if model == "ideal":
        on = bits.astype(bool)
        left = np.zeros_like(on); left[:, 1:] = on[:, :-1]
        right = np.zeros_like(on); right[:, :-1] = on[:, 1:]
        x = np.arange(W)[None, :]
        col = np.where(hi == 1, np.where(x % 2 == 0, BLUE, ORANGE), np.where(x % 2 == 0, VIOLET, GREEN))
        idx = np.where(on, np.where(left | right, WHITE, col), BLACK)
        # Lücke zwischen zwei gleichfarbigen Punkten wird Fläche
        lcol = np.zeros_like(col); lcol[:, 1:] = col[:, :-1]
        gap = (~on) & left & right
        idx = np.where(gap, lcol, idx)
        return PAL16[idx]
    d = dots_of(mem)
    dp = np.zeros((rows, 2 * W + 4), np.uint8)
    dp[:, 1:2 * W + 1] = d                                   # dp[i+1] = d[i]; d[-1] = 0
    x = np.arange(W)[None, :]
    s = 2 * x + hi - 1                                       # erstes Halbpunkt-Fenster
    nib = np.zeros((rows, W), np.int32)
    r = np.arange(rows)[:, None]
    for k in range(4):
        dd = s + k
        v = dp[r, np.clip(dd + 1, 0, 2 * W + 3)]
        nib |= (v.astype(np.int32) << (dd % 4))
    if model == "crisp":
        on = bits.astype(bool)
        left = np.zeros_like(on); left[:, 1:] = on[:, :-1]
        right = np.zeros_like(on); right[:, :-1] = on[:, 1:]
        nib = np.where(on | (left & right), nib, 0)
    return PAL16[nib]


def to_rgb_screen(mem, model="fringe", scale=3):
    img = render(mem, model)
    if scale > 1:
        img = np.repeat(np.repeat(img, scale, axis=0), scale, axis=1)
    return img


# Speicheradresse einer Zeile im echten Hi-Res-Bild ($2000-$3FFF, verschachtelt)
def line_addr(y):
    return (y % 8) * 1024 + ((y // 8) % 8) * 128 + (y // 64) * 40


def to_bin(mem):
    """8192 Bytes im Format einer Hi-Res-Seite (verschachtelte Zeilen, Lücken 0)."""
    out = bytearray(8192)
    for y in range(mem.shape[0]):
        a = line_addr(y)
        out[a:a + 40] = bytes(mem[y].tolist())
    return bytes(out)
