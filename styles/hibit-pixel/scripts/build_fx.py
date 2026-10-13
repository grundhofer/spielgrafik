#!/usr/bin/env python3
"""Effekt-Texturen für hibit-pixel, alle im Code gesetzt (keine KI): Rauch-Bildfolge für Partikel, Lichthöfe,
Nebelband, Möwe, Lichttexturen.

    .venv/bin/python styles/hibit-pixel/scripts/build_fx.py

Alles liegt auf dem 640×360-Raster: Partikel tauschen Einzelbilder statt zu skalieren (CanvasItemMaterial
particles_animation), Lichthöfe sind Stufen mit geordnetem Dithering an den Stufengrenzen.
"""
import pathlib

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "demo" / "art"
OUT.mkdir(parents=True, exist_ok=True)
BAYER4 = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) + 0.5) / 16


def bayer(h, w):
    return np.tile(BAYER4, (h // 4 + 1, w // 4 + 1))[:h, :w]


def stepped(v, steps, band=0.35):
    """Wert 0..1 in `steps` Stufen; nur in einem schmalen Übergang an jeder Stufengrenze geditht."""
    h, w = v.shape
    s = v * steps
    base = np.floor(s)
    frac = s - base
    # Nachkommateil um 0,5 herum auf einen Übergang der Breite `band` zusammendrücken
    t = np.clip((frac - 0.5) / band + 0.5, 0, 1)
    up = t > bayer(h, w)
    return np.clip((base + up) / steps, 0, 1)


def save(arr, name):
    Image.fromarray(np.asarray(arr, dtype=np.uint8), "RGBA").save(OUT / name)
    Image.fromarray(np.asarray(arr, dtype=np.uint8), "RGBA").save(ROOT / "assets" / name)   # Kopie in assets/
    print(name, arr.shape[1], "x", arr.shape[0])


def halo(size, radius, steps, power=1.6, name="halo.png"):
    y, x = np.mgrid[0:size, 0:size]
    c = (size - 1) / 2
    d = np.sqrt((x - c) ** 2 + (y - c) ** 2) / radius
    v = np.clip(1 - d, 0, 1) ** power
    a = stepped(v, steps)
    rgba = np.zeros((size, size, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = np.round(a * 255).astype(np.uint8)
    save(rgba, name)


def flare(size, radius, steps, name):
    """Aufblitzen des Leuchtfeuers: kleiner runder Hof plus waagrechte und senkrechte Strahlen (1–3 px dick)."""
    y, x = np.mgrid[0:size, 0:size]
    c = (size - 1) / 2
    dx, dy = np.abs(x - c), np.abs(y - c)
    d = np.sqrt(dx ** 2 + dy ** 2)
    core = np.clip(1 - d / (radius * 0.45), 0, 1) ** 1.5
    spike_h = np.clip(1 - dx / radius, 0, 1) ** 2.2 * (dy <= np.where(dx < radius * 0.3, 1, 0))
    spike_v = np.clip(1 - dy / (radius * 0.6), 0, 1) ** 2.2 * (dx <= 0)
    v = np.maximum(core, np.maximum(spike_h, spike_v))
    a = stepped(np.clip(v, 0, 1), steps)
    rgba = np.zeros((size, size, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = np.round(a * 255).astype(np.uint8)
    save(rgba, name)


def rect_halo(w, h, inner, outer, steps, name):
    """Lichthof um ein Fenster: Abstand zu einem Rechteck, Stufen nach außen."""
    y, x = np.mgrid[0:h, 0:w]
    cx0, cx1 = outer, w - 1 - outer
    cy0, cy1 = outer, h - 1 - outer
    dx = np.maximum(np.maximum(cx0 - x, x - cx1), 0)
    dy = np.maximum(np.maximum(cy0 - y, y - cy1), 0)
    d = np.sqrt(dx ** 2 + dy ** 2) / outer
    v = np.clip(1 - d, 0, 1) ** 1.8
    a = stepped(v, steps)
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = np.round(a * 255).astype(np.uint8)
    save(rgba, name)


def smoke_frames():
    """8 Bilder 14×14: Wölkchen wächst (Radius 1,5 -> 6), oben links Lichtkante, unten rechts Schatten,
    die letzten drei zerfallen (geordnetes Ausdünnen)."""
    n, S = 8, 14
    out = np.zeros((S, S * n, 4), np.uint8)
    light, body, shade = (196, 178, 196), (150, 138, 168), (108, 100, 136)
    for i in range(n):
        r = 1.6 + i * 0.62
        y, x = np.mgrid[0:S, 0:S]
        c = (S - 1) / 2
        dx, dy = x - c, y - c
        # zwei überlappende Kreise für eine unregelmäßige Form
        inside = (dx ** 2 + dy ** 2 <= r * r) | ((dx + r * 0.45) ** 2 + (dy + r * 0.35) ** 2 <= (r * 0.7) ** 2)
        col = np.zeros((S, S, 3))
        col[:] = body
        lit = (dx + dy) < -r * 0.55
        sh = (dx + dy) > r * 0.6
        col[lit] = light
        col[sh] = shade
        keep = inside.copy()
        if i >= 5:   # zerfallen: geordnet ausdünnen
            thr = (i - 4) / 4.0
            keep &= bayer(S, S) > thr
        tile = np.zeros((S, S, 4), np.uint8)
        tile[..., :3] = col.astype(np.uint8)
        tile[..., 3] = np.where(keep, 255, 0)
        out[:, i * S:(i + 1) * S] = tile
    save(out, "smoke.png")


def mote():
    """Lichtstaub: 2 Bilder je 1 px (hell, gedämpft); Farbe kommt aus dem Licht (LIGHT_ONLY)."""
    out = np.zeros((1, 2, 4), np.uint8)
    out[0, 0] = (255, 236, 200, 255)
    out[0, 1] = (255, 236, 200, 150)
    save(out, "mote.png")


def mist():
    """Nebelschwaden 640×28, in x kachelbar: 9 flache Ellipsen (60–150 px breit) mit weichem Rand,
    Alpha in 3 Stufen mit Dithering nur an den Stufengrenzen, dazwischen Lücken."""
    W, H = 640, 28
    y, x = np.mgrid[0:H, 0:W]
    rng = np.random.default_rng(7)
    v = np.zeros((H, W))
    for _ in range(9):
        cx = rng.uniform(0, W); cy = rng.uniform(14, 20)
        rx = rng.uniform(30, 75); ry = rng.uniform(4, 7)
        for off in (-W, 0, W):
            d = ((x - cx - off) / rx) ** 2 + ((y - cy) / ry) ** 2
            v = np.maximum(v, np.clip(1 - d, 0, 1) ** 0.8)
    a = stepped(np.clip(v, 0, 1), 3, band=0.5) * 0.34
    rgba = np.zeros((H, W, 4), np.uint8)
    rgba[..., 0], rgba[..., 1], rgba[..., 2] = 222, 176, 210
    rgba[..., 3] = np.round(a * 255).astype(np.uint8)
    save(rgba, "mist.png")


def gull():
    """Möwe, 4 Flügelstellungen, 11×6 je Bild (W = weiß, G = grau Flügelspitze, D = dunkel)."""
    pats = [
        ["D.........D", ".GW.....WG.", "..WW...WW..", "....WWW....", "...........", "..........."],
        ["...........", "DGW.....WGD", "..WWW.WWW..", "....WWW....", "...........", "..........."],
        ["...........", "...........", "DGWWW.WWWGD", "....WWW....", "...........", "..........."],
        ["...........", "...........", "....WWW....", "..WWWWWWW..", ".GW.....WG.", "D.........D"],
    ]
    cols = {"W": (236, 228, 240, 255), "G": (150, 150, 176, 255), "D": (60, 52, 82, 255)}
    out = np.zeros((6, 11 * 4, 4), np.uint8)
    for i, p in enumerate(pats):
        for yy, row in enumerate(p):
            for xx, ch in enumerate(row):
                if ch in cols:
                    out[yy, i * 11 + xx] = cols[ch]
    save(out, "gull.png")


def blob_shadow(w, h, name):
    """Kontaktschatten unter der Figur: Pixel-Ellipse, innen dichter, Rand geordnet ausgedünnt."""
    y, x = np.mgrid[0:h, 0:w]
    d = ((x - (w - 1) / 2) / (w / 2)) ** 2 + ((y - (h - 1) / 2) / (h / 2)) ** 2
    a = np.where(d < 0.45, 0.55, np.where(d < 1.0, 0.55 * (bayer(h, w) > 0.5), 0.0))
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., :3] = (12, 8, 24)
    rgba[..., 3] = np.round(a * 255).astype(np.uint8)
    save(rgba, name)


def light_tex(size, name, power):
    """Lichttextur (weich): Stärke im RGB, die Stufen setzt der light()-Shader."""
    y, x = np.mgrid[0:size, 0:size]
    c = (size - 1) / 2
    d = np.sqrt((x - c) ** 2 + (y - c) ** 2) / c
    v = np.clip(1 - d, 0, 1) ** power
    rgba = np.zeros((size, size, 4), np.uint8)
    rgba[..., 0] = rgba[..., 1] = rgba[..., 2] = np.round(v * 255)
    rgba[..., 3] = 255
    save(rgba, name)


if __name__ == "__main__":
    halo(48, 23, 5, 1.7, "halo_lantern.png")
    halo(24, 11, 4, 1.5, "halo_lamp.png")
    flare(97, 48, 5, "flare_lamp.png")
    rect_halo(48, 60, 0, 12, 4, "halo_window.png")
    smoke_frames()
    mote()
    mist()
    gull()
    light_tex(256, "light_soft.png", 1.6)
    blob_shadow(28, 5, "shadow.png")
