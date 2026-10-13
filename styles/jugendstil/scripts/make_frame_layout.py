#!/usr/bin/env python3
"""Layout-Skizze für den Ornamentrahmen (Referenz 1 an gpt-image), 1536x1024.

    .venv/bin/python styles/jugendstil/scripts/make_frame_layout.py

Bildschirm 1280x720 = Rahmenbild-Zeilen 80..944 mal 1/1,2 (16:9 in der Mitte des 3:2-Bildes); die Zeilen
darüber und darunter (schwarz) schneidet das Spiel ab, damit die Ornamente nicht verzerrt werden.
  Fenster (Magenta):   x 134..1402, oben Korbbogen (Eckradius 192, Scheitel y 94, Kämpfer y 326), unten y 800
                       -> Bildschirm x 112..1168, y 12..600; die Szene (3:2) liegt darin mit Faktor 0,6875
  Textfeld (hellgrau): x 134..1402, y 814..930 -> Bildschirm y 612..708
  Rahmen (grau):       Seitenleisten, Zwickel über dem Bogen, Leiste zwischen Fenster und Textfeld
  außen (schwarz):     Zeilen 0..80 und 944..1024
Ausgang: assets/ref/frame_layout.png, assets/ref/frame_layout.json
"""
import json, math, pathlib
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[1]
W, H = 1536, 1024
TOP, BOTTOM = 80, 944       # sichtbarer 16:9-Bereich
X0, X1 = 134, 1402          # Fenster links/rechts
APEX, SPRING = 94, 326      # Scheitel und Kämpferlinie des Bogens
WIN_BOT = 800
PANEL = (134, 814, 1402, 930)
R_CORNER = 192              # Radius der Eckbögen (Korbbogen aus zwei Eckkreisen und einem flachen Mittelbogen)


def arch_y(x):
    """Oberkante des Fensters bei x: Eckkreise (Radius R_CORNER, Mittelpunkt auf der Kämpferlinie) und ein großer
    Kreisbogen mit Scheitel APEX, der die Eckkreise innen berührt."""
    cx = (X0 + X1) / 2
    r = R_CORNER
    dx = (X1 - X0) / 2 - r
    # dx^2 + (Rb + a)^2 = (Rb - r)^2 mit a = APEX - SPRING  ->  Rb = (dx^2 + a^2 - r^2) / (-2 (r + a))
    a = APEX - SPRING
    Rb = (dx * dx + a * a - r * r) / (-2 * (r + a))
    ccx, ccy = X0 + r, SPRING
    bx, by = cx, APEX + Rb
    k = Rb / (Rb - r)
    tx = bx + (ccx - bx) * k                     # Berührpunkt (linke Seite)
    dxx = abs(x - cx)
    if dxx <= abs(tx - cx):
        return by - math.sqrt(max(0.0, Rb * Rb - dxx * dxx))
    ex = cx - dxx
    if ex < X0:
        return SPRING
    return ccy - math.sqrt(max(0.0, r * r - (ex - ccx) ** 2))


def window_polygon(step=2):
    pts = [(X0, WIN_BOT), (X0, SPRING)]
    for x in range(X0, X1 + 1, step):
        pts.append((x, arch_y(x)))
    pts += [(X1, SPRING), (X1, WIN_BOT)]
    return pts


def main():
    im = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, TOP, W - 1, BOTTOM - 1), fill=(110, 110, 110))
    d.polygon(window_polygon(), fill=(255, 0, 255))
    d.rectangle(PANEL, fill=(214, 214, 214))
    out = ROOT / "assets/ref"
    out.mkdir(parents=True, exist_ok=True)
    im.save(out / "frame_layout.png")
    (out / "frame_layout.json").write_text(json.dumps({
        "size": [W, H], "visible_rows": [TOP, BOTTOM], "screen_scale": 1 / 1.2,
        "window": {"x0": X0, "x1": X1, "apex": APEX, "spring": SPRING, "bottom": WIN_BOT, "r_corner": R_CORNER},
        "panel": PANEL}, indent=1))
    print("ok", out / "frame_layout.png", [round(arch_y(x)) for x in (X0, X0 + 96, X0 + 192, 500, 768)])


if __name__ == "__main__":
    main()
