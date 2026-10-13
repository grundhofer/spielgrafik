#!/usr/bin/env python3
"""Gedrucktes Licht für Leuchtfeuer und Laterne: flache Scheiben und Strahlen als fertige Überlagerungsbilder.

    .venv/bin/python styles/ukiyo-e/scripts/build_lights.py      (nach build_bg.py)

Licht wird im Holzschnitt mit einem eigenen Farbstock gedruckt, nicht addiert: deckende, hartkantige Flächen in
Blassgelb mit einem Bokashi-Verlauf zu einer Seite und feiner Indigo-Kontur. Die Bilder werden gegen das fertige
Druckbild (assets/bg.png) gerechnet: Im Gehäuse von Laternenraum bzw. Laterne bleiben die dunklen Teile des
Schlüsselstocks (RGB-Summe < 200, Übergang bis 260, nicht blau) frei, die Scheibe liegt also hinter Dach, Sprossen und Geländer.
In der Demo werden die Bilder nur ein- und ausgeschaltet (10 Bilder/s), nie überblendet oder skaliert.

Ausgang (assets/ und demo/art/), Lage in lights.json (linke obere Ecke in Druckkoordinaten):
  lamp_a.png    Leuchtfeuer, Stufe 1: Scheibe r = 19 um den Laternenraum
  lamp_b.png    Leuchtfeuer, Stufe 2 (Blitz): Scheibe r = 24 und zehn Strahlen (abwechselnd lang und kurz), die
                Richtungen in den Turm hinein sind weggelassen
  lantern_1.png, lantern_2.png  Laterne: Scheibe r = 17 bzw. 21 hinter dem Laternengehäuse (Flackern = Wechsel
                zwischen keiner, kleiner und großer Scheibe)
"""
import json, math, pathlib
import numpy as np
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUTS = [ROOT / "assets", ROOT / "demo/art"]
PALE = np.array([255, 236, 168], float)
DEEP = np.array([236, 172, 78], float)
INDIGO = np.array([38, 44, 92], float)
SS = 4


def shape_mask(size, cx, cy, disc_r, rays):
    """Maske (Überabtastung SS) aus Scheibe und Strahlenkeilen; rays = [(winkel, r0, r1, halbe Breite)]."""
    im = Image.new("L", (size[0] * SS, size[1] * SS), 0)
    dr = ImageDraw.Draw(im)
    c = (cx * SS, cy * SS)
    r = disc_r * SS
    dr.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=255)
    for ang, r0, r1, half in rays:
        pts = [(c[0] + math.cos(ang - half) * r0 * SS, c[1] + math.sin(ang - half) * r0 * SS),
               (c[0] + math.cos(ang) * r1 * SS, c[1] + math.sin(ang) * r1 * SS),
               (c[0] + math.cos(ang + half) * r0 * SS, c[1] + math.sin(ang + half) * r0 * SS)]
        dr.polygon(pts, fill=255)
    return np.asarray(im, np.float32) / 255.0


def erode_ss(m, px):
    """Maske um px (Überabtastungs-Pixel) schrumpfen (Minimum über ein Quadrat)."""
    out = m.copy()
    for dy in range(-px, px + 1):
        for dx in range(-px, px + 1):
            out = np.minimum(out, np.roll(np.roll(m, dy, 0), dx, 1))
    return out


def down(a):
    h, w = a.shape[:2]
    return a.reshape(h // SS, SS, w // SS, SS, *a.shape[2:]).mean((1, 3))


def make(bg, name, center, box, disc_r, rays, housing, bokashi_side="top"):
    """bg: Druckbild HxWx3; center: Mitte in Druckkoordinaten; box: (x0, y0, w, h) des Sprites; housing: Rechteck,
    in dem die dunklen Teile des Druckbilds über der Scheibe stehen bleiben."""
    x0, y0, w, h = box
    cx, cy = center[0] - x0, center[1] - y0
    m = shape_mask((w, h), cx, cy, disc_r, rays)
    inner = erode_ss(m, SS)                            # Konturbreite 1 px
    yy, xx = np.mgrid[0:h * SS, 0:w * SS].astype(np.float32) / SS
    # Bokashi: von der oberen (bzw. unteren) Kante der Scheibe nach innen über 45 % des Radius tiefer Gelb
    dx = np.clip(np.abs(xx - cx), 0, disc_r - 1e-3)
    edge = cy - np.sqrt(disc_r ** 2 - dx ** 2) if bokashi_side == "top" else cy + np.sqrt(disc_r ** 2 - dx ** 2)
    dist = (yy - edge) if bokashi_side == "top" else (edge - yy)
    t = np.clip(1 - dist / (0.45 * disc_r), 0, 1)
    in_disc = ((xx - cx) ** 2 + (yy - cy) ** 2) <= disc_r ** 2
    t = np.where(in_disc, t, 0)
    fill = PALE[None, None] * (1 - t[..., None]) + DEEP[None, None] * t[..., None]
    col = fill * inner[..., None] + INDIGO[None, None] * (m - inner)[..., None]
    rgb = down(col)
    alpha = down(m)
    rgb = rgb / np.maximum(alpha[..., None], 1e-4)
    # Gehäuse: dunkle Teile des Druckbilds bleiben sichtbar (Scheibe dahinter)
    cb = bg[y0:y0 + h, x0:x0 + w].astype(float)
    crop = cb.sum(-1)
    hx0, hy0, hx1, hy1 = housing
    hm = np.zeros((h, w), bool)
    hm[max(0, hy0 - y0):hy1 - y0, max(0, hx0 - x0):hx1 - x0] = True
    hm &= (cb[..., 2] - cb[..., 0]) < 50               # blaues Wasser/Himmel gehört nicht zum Gehäuse
    hole = np.where(hm, np.clip((260 - crop) / 60, 0, 1), 0)
    alpha = alpha * (1 - hole)
    out = np.concatenate([np.clip(rgb, 0, 255), alpha[..., None] * 255], -1)
    img = Image.fromarray((out + 0.5).astype(np.uint8), "RGBA")
    for d in OUTS:
        img.save(d / f"{name}.png")
    print("ok", name, img.size, "deckend", int((alpha > 0.5).sum()), "px")
    return {"pos": [x0, y0], "size": [w, h]}


def main():
    bg = np.asarray(Image.open(ROOT / "assets/bg.png").convert("RGB"))
    sc = json.loads((ROOT / "assets/scene.json").read_text())
    lx, ly = sc["lamp"][0], sc["lamp"][1]
    info = {}
    lamp_housing = (928, 34, 983, 92)                 # Spitze, Dach, Laternenraum, Galerie (6-fach abgelesen)
    box = (lx - 64, ly - 64, 128, 128)
    info["lamp_a"] = make(bg, "lamp_a", (lx, ly), box, 19, [], lamp_housing)
    rays = []
    for i in range(12):
        ang = math.radians(15 + 30 * i)
        if abs(math.degrees(ang) - 90) < 40:          # nicht in den Turm hinein
            continue
        rays.append((ang, 20, 58 if i % 2 == 0 else 42, 0.16))
    info["lamp_b"] = make(bg, "lamp_b", (lx, ly), box, 24, rays, lamp_housing)
    nx, ny = sc["lantern"][0], sc["lantern"][1]
    lantern_housing = (994, 318, 1031, 366)           # Bügel, Dach, Sprossen, Boden der Laterne
    box = (nx - 32, ny - 32, 64, 64)
    info["lantern_1"] = make(bg, "lantern_1", (nx, ny), box, 17, [], lantern_housing, "bottom")
    info["lantern_2"] = make(bg, "lantern_2", (nx, ny), box, 21, [], lantern_housing, "bottom")
    for d in OUTS:
        (d / "lights.json").write_text(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
