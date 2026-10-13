#!/usr/bin/env python3
"""Gemeinsame 1-Bit-Bausteine: Tonstufen, Musterfamilien und Umsetzung eines Tonbilds in zwei Farben.

Ein Tonbild (Stufe 0 = schwarz … 16 = weiß) plus eine Familienkarte ergeben über feste Schwellenmatrizen das
1-Bit-Bild. Dieselben Matrizen stehen in demo/shaders/onebit.gdshaderinc; Python dient zur Vorschau und zum
Backen der Sprites.

Familien:
  0 BAYER   geordnetes 4×4-Dithering (12,5 % Diagonalpunkte, 25 % Punktraster, 50 % Schachbrett …)
  1 LINES   Zeilenraster: füllt ganze Zeilen in der Reihenfolge 0,4,2,6,1,5,3,7 (Himmel)
  2 DASH    Strichraster 16×8: Striche, die mit der Stufe länger werden, zuerst jede vierte Zeile (Wasser,
            im Spiel zeilenweise verschoben)
"""
import numpy as np

BAYER, LINES, DASH = 0, 1, 2
BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]])
RANK8 = np.array([0, 4, 2, 6, 1, 5, 3, 7])          # Bitumkehr: Reihenfolge, in der Zeilen gefüllt werden
ROWRANK = np.argsort(RANK8)                          # Zeile y wird als ROWRANK[y]-te gefüllt
LINES8 = ROWRANK[:, None] * 8 + ROWRANK[None, :]     # 0..63
# Wasser (16×8): Striche, die von ihrer Mitte aus wachsen. Zuerst jede vierte Zeile (Zeilen 0 und 4, bis Stufe 4
# volle Linien), dann die Zeilen 2 und 6 (bis Stufe 8), dann die ungeraden Zeilen. Stufe 1 = 4-px-Striche alle
# 16 px in jeder vierten Zeile, Stufe 2 = 8-px-Striche; jede Zeile hat ihren eigenen Versatz.
def _dash_matrix():
    order_rows = [[0, 4], [2, 6], [1, 5], [3, 7]]
    centre = [2, 9, 13, 6, 10, 1, 5, 14]
    grow = [0]
    for k in range(1, 9):
        grow += [k, -k]
    grow = grow[:16]
    T = np.zeros((8, 16), int)
    base = 0
    for pair in order_rows:
        for i, dx in enumerate(grow):
            for j, y in enumerate(pair):
                T[y, (centre[y] + dx) % 16] = base + i * 2 + j
        base += 32
    return T


DASH8 = _dash_matrix()       # 8 Zeilen × 16 Spalten, Werte 0..127


def white(level, family, x, y):
    """level 0..16 (Array), family (Array), x/y ganzzahlige Bildkoordinaten (Arrays gleicher Form) -> bool."""
    level = np.asarray(level)
    family = np.broadcast_to(np.asarray(family), level.shape)
    b = BAYER4[y % 4, x % 4] < level
    ln = LINES8[y % 8, x % 8] < level * 4
    ds = DASH8[y % 8, x % 16] < level * 8
    return np.where(family == LINES, ln, np.where(family == DASH, ds, b))


def render(levels, families, x0=0, y0=0):
    h, w = levels.shape
    y, x = np.mgrid[y0:y0 + h, x0:x0 + w]
    return white(levels, families, x, y)


def to_rgb(mask, ink=(0x1A, 0x18, 0x14), paper=(0xEE, 0xE8, 0xD8)):
    out = np.empty(mask.shape + (3,), np.uint8)
    out[...] = ink
    out[mask] = paper
    return out


def box_mean(a, k):
    """Mittelwert über ein k×k-Fenster (k ungerade), Ränder gespiegelt."""
    r = k // 2
    p = np.pad(a.astype(np.float64), r, mode="reflect")
    c = p.cumsum(0).cumsum(1)
    c = np.pad(c, ((1, 0), (1, 0)))
    s = c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]
    return s / (k * k)


def erode(mask, k):
    return box_mean(mask.astype(np.float64), k) > 0.999


def dilate(mask, k):
    return box_mean(mask.astype(np.float64), k) > 0.001


def opening(mask, k):
    return dilate(erode(mask, k), k)


def cell_mean(a, w, h):
    """Flächenmittel auf ein w×h-Raster (Quellbild wird ganzzahlig überabgetastet)."""
    H, W = a.shape
    ys = (np.arange(h + 1) * H / h).round().astype(int)
    xs = (np.arange(w + 1) * W / w).round().astype(int)
    c = np.pad(a.astype(np.float64).cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    s = c[ys[1:], :][:, xs[1:]] - c[ys[:-1], :][:, xs[1:]] - c[ys[1:], :][:, xs[:-1]] + c[ys[:-1], :][:, xs[:-1]]
    area = (ys[1:] - ys[:-1])[:, None] * (xs[1:] - xs[:-1])[None, :]
    return s / area


def pattern_texture():
    """Schwellenmatrizen als 16×24-Bild für den Shader: Zeilen 0–7 Bayer (4×4 zweimal nebeneinander, Werte ×4),
    8–15 LINES (8×8, zweimal), 16–23 DASH (16×8). Wert = Schwelle in 1/128 (Weiß, wenn Wert < Stufe·8)."""
    t = np.zeros((24, 16), np.uint8)
    t[0:8] = np.tile(BAYER4 * 8, (2, 4))
    t[8:16] = np.tile(LINES8 * 2, (1, 2))
    t[16:24] = DASH8
    return t
