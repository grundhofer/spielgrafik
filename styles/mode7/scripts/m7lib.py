"""Gemeinsame Mode-7-Rechnung für die Python-Werkzeuge des Eintrags mode7.

Dieselben Formeln stehen in demo/scripts/main.gd (Kamera, HDMA-Tabelle, Projektion der Sprites) und in
demo/shaders/mode7.gdshader (Pixelrechnung der PPU). probe.py vergleicht die Godot-Aufnahme mit
render_plane() hier.

Koordinaten:
  Welt in Metern: x nach Osten, y nach Norden. Karte 1024×1024 Texel, 1 Texel = 0,1 m.
  Texel u = (x - X_MIN) * 10 (nach rechts), v = (Y_MAX - y) * 10 (nach unten).
  Kurs theta: 0 = Norden (−v), positiv = nach rechts gedreht.
Bild 256×224, Horizont in Zeile Y_H; darüber Mode 1 (Himmel, Textfenster), Mode 7 von Zeile Y_H+1 bis PLANE_END-1.
"""
import json
import math
import pathlib

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
STYLE = HERE.parent

W, H = 256, 224
Y_H = 92            # Horizontzeile: Zeilen 0..Y_H gehören zum Himmel (Mode 1), ab Y_H+1 Mode 7
PLANE_END = 224     # Mode 7 bis zur letzten Zeile; das Textfenster liegt oben über dem Himmel
F = 236.0           # Brennweite in Pixeln (waagrechter Bildwinkel 2*atan(128/F) = 57 Grad)
TPM = 10            # Texel je Meter
X_MIN = -51.2
Y_MAX = 72.4
MAP = 1024


def to_texel(x, y):
    return (x - X_MIN) * TPM, (Y_MAX - y) * TPM


def rnd(x):
    """Runden wie in GDScript floor(x + 0.5) (nicht numpy-Bankrunden)."""
    return math.floor(x + 0.5)


# ---------------------------------------------------------------------------------------------
# Ablauf (dieselben Zahlen in main.gd)
# ---------------------------------------------------------------------------------------------
CAM_P0 = (0.9, -15.0)
CAM_P1 = (0.3, 0.0)
CAM_T = 3.7
CAM_TH0 = -14.0
CAM_TH1 = -3.0
CAM_H0 = 5.0
CAM_H1 = 2.8


def ease_out(s, k=2.2):
    s = min(max(s, 0.0), 1.0)
    return 1.0 - (1.0 - s) ** k


def smooth(s):
    s = min(max(s, 0.0), 1.0)
    return s * s * (3.0 - 2.0 * s)


def camera(t):
    """Kameraposition (m), Kurs (Grad) und Augenhöhe (m) zur Zeit t."""
    s = ease_out(t / CAM_T)
    x = CAM_P0[0] + (CAM_P1[0] - CAM_P0[0]) * s
    y = CAM_P0[1] + (CAM_P1[1] - CAM_P0[1]) * s
    th = CAM_TH0 + (CAM_TH1 - CAM_TH0) * smooth(t / CAM_T)
    h = CAM_H0 + (CAM_H1 - CAM_H0) * ease_out(t / CAM_T, 1.6)
    return x, y, th, h


def basis(theta_deg):
    th = math.radians(theta_deg)
    fwd = (math.sin(th), -math.cos(th))      # in Texelachsen (u, v)
    right = (math.cos(th), math.sin(th))
    return fwd, right


def clip13(n):
    return (n | ~1023) if (n & 0x2000) else (n & 1023)


def s16(n):
    return max(-32768, min(32767, n))


def hdma_table(cx, cy, theta_deg, cam_h):
    """HDMA-Tabelle der Matrix A..D (8.8 Festkomma) je Bildzeile und die Register X0, Y0, HOFS, VOFS.

    Wie ein Spiel sie auf der CPU vorberechnet: je Zeile die Entfernung lambda = F*cam_h/(y - Y_H);
    A, C = Schrittweite je Pixel quer, B, D so, dass (B*y) die Mitte der Zeile trifft (VOFS = Y0).
    """
    cu, cv = to_texel(cx, cy)
    fwd, right = basis(theta_deg)
    x0, y0 = rnd(cu), rnd(cv)
    hofs, vofs = x0 - 128, y0
    tab = np.zeros((H, 4), dtype=np.int64)
    for y in range(Y_H + 1, PLANE_END):
        lam = F * cam_h * TPM / (y - Y_H)          # Texel
        step = lam / F                              # Texel je Pixel
        a = s16(rnd(step * right[0] * 256))
        c = s16(rnd(step * right[1] * 256))
        b = s16(rnd((cu - x0 + lam * fwd[0]) * 256 / y))
        d = s16(rnd((cv - y0 + lam * fwd[1]) * 256 / y))
        tab[y] = (a, b, c, d)
    return tab, (x0, y0, hofs, vofs)


def render_plane(tab, regs, tilemap, tiles):
    """Mode-7-Pixelrechnung (wie bsnes, PPU Mode 7, M7SEL = Kachel 0 außerhalb) -> CGRAM-Index je Pixel.

    tilemap: (128,128) uint8, tiles: (256,8,8) uint8. Zeilen außerhalb des Mode-7-Bereichs bleiben 0.
    """
    x0, y0, hofs, vofs = regs
    out = np.zeros((H, W), dtype=np.uint8)
    xs = np.arange(W, dtype=np.int64)
    ch = clip13(hofs - x0)
    cvv = clip13(vofs - y0)
    for y in range(Y_H + 1, PLANE_END):
        a, b, c, d = (int(v) for v in tab[y])
        ox = ((a * ch) & ~63) + ((b * cvv) & ~63) + ((b * y) & ~63) + (x0 << 8)
        oy = ((c * ch) & ~63) + ((d * cvv) & ~63) + ((d * y) & ~63) + (y0 << 8)
        px = (ox + a * xs) >> 8
        py = (oy + c * xs) >> 8
        oob = ((px | py) & ~1023) != 0
        tx = (px >> 3) & 127
        ty = (py >> 3) & 127
        tile = np.where(oob, 0, tilemap[ty, tx])
        out[y] = tiles[tile, py & 7, px & 7]
    return out


def project(cx, cy, theta_deg, cam_h, wx, wy, alt=0.0):
    """Weltpunkt (m) -> (Bild-x, Bild-y, Entfernung m). Bild-y ist die Zeile, deren Boden die Entfernung zeigt."""
    fwd, right = basis(theta_deg)
    du, dv = (wx - cx) * TPM, (cy - wy) * TPM
    z = (du * fwd[0] + dv * fwd[1]) / TPM
    xr = (du * right[0] + dv * right[1]) / TPM
    if z <= 0.05:
        return None
    sx = 128 + F * xr / z
    sy = Y_H + F * (cam_h - alt) / z
    return sx, sy, z


def load_json(p):
    return json.loads(pathlib.Path(p).read_text())
