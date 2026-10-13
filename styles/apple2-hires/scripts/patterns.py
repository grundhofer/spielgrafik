"""Füllmuster für die Hi-Res-Seite: Zeilen aus (Bitfolge, Farbgruppe), wiederholt über x (absolute Spalte) und y.

Volle Farben gibt es nur sechs (Schwarz, Weiß, Violett, Grün, Blau, Orange); alle Mischtöne entstehen aus
Zeilen- oder Spaltenmustern. Eine Bitfolge wird über die absolute Spalte x indiziert (x % len), damit benachbarte
Flächen mit demselben Muster nahtlos ineinander übergehen und die Farbe (gerade/ungerade Spalte) stimmt.
"""
import numpy as np

# Name: Liste von Zeilen (Bits, Gruppe). Gruppe 0 = Violett/Grün, 1 = Blau/Orange.
PATTERNS = {
    "schwarz":      [("0", 1)],
    "schwarz0":     [("0", 0)],
    "weiss":        [("1", 1)],
    "weiss0":       [("1", 0)],
    "violett":      [("10", 0)],
    "gruen":        [("01", 0)],
    "blau":         [("10", 1)],
    "orange":       [("01", 1)],
    "dunkelblau":   [("10", 1), ("00", 1)],
    "nachtblau":    [("10", 1), ("00", 1), ("00", 1)],
    "dunkelviolett": [("10", 0), ("00", 0)],
    "dunkelgruen":  [("01", 0), ("00", 0)],
    "braun":        [("01", 1), ("00", 1)],
    "indigo":       [("10", 1), ("10", 0)],
    "rot":          [("01", 1), ("10", 0)],
    "gelb":         [("01", 1), ("1", 1)],
    "hellblau":     [("10", 1), ("1", 1)],
    "rosa":         [("10", 0), ("1", 0)],
    "hellgruen":    [("01", 0), ("1", 0)],
    "grau_vg":      [("10", 0), ("01", 0)],
    "grau_bo":      [("10", 1), ("01", 1)],
    "grau_ws":      [("1", 1), ("0", 1)],
    "hellgrau":     [("1", 1), ("1", 1), ("0", 1)],
    "stein":        [("1", 1), ("10", 1), ("1", 1), ("01", 1)],
    "pflaster":     [("11111111111110", 1), ("01", 1), ("01", 1)],
    "dunkelgrau":   [("10", 1), ("00", 1), ("01", 1), ("00", 1)],
    "graubraun":    [("01", 1), ("10", 1), ("00", 1)],
    "olivgrau":     [("01", 0), ("10", 0), ("00", 0)],
    "fels":         [("10", 0), ("00", 0), ("01", 0), ("00", 0)],
    "holz":         [("01", 1), ("01", 1), ("00", 1)],
    "holzhell":     [("01", 1), ("1", 1), ("01", 1), ("00", 1)],
    "meer":         [("10", 1), ("10", 1), ("10", 1), ("00", 1)],
    "blau_k":       [("1000", 1), ("0010", 1)],
    "violett_k":    [("1000", 0), ("0010", 0)],
    "gruen_k":      [("0100", 0), ("0001", 0)],
    "orange_k":     [("0100", 1), ("0001", 1)],
    "blau_k2":      [("1000", 1), ("0000", 1), ("0010", 1), ("0000", 1)],
    "grau_k":       [("1000", 0), ("0001", 0)],
    "grau_k1":      [("1000", 1), ("0001", 1)],
    "weiss_k":      [("1100", 1), ("0011", 1)],
    "weiss_k2":     [("1100", 1), ("0000", 1), ("0011", 1), ("0000", 1)],
    "meer2":        [("10", 1), ("10", 1), ("00", 1), ("10", 1), ("10", 1), ("10", 1), ("11", 1), ("10", 1)],
}


def pattern_bit(name, x, y):
    rows = PATTERNS[name]
    bits, h = rows[y % len(rows)]
    return int(bits[x % len(bits)]), h


def pattern_tile(name, w=28, h=24, x0=0, y0=0):
    """Bits und Gruppe je Bildpunkt für eine Fläche (für Muster-Übersichten)."""
    b = np.zeros((h, w), np.uint8)
    g = np.zeros((h, w), np.uint8)
    for yy in range(h):
        for xx in range(w):
            b[yy, xx], g[yy, xx] = pattern_bit(name, x0 + xx, y0 + yy)
    return b, g
