#!/usr/bin/env python3
"""Statusleiste (320 x 32) und Schriftverläufe für die Oberfläche, nur aus Palettenfarben.

Grund ist die KI-Textur "iron" (genietetes Eisenblech), gekachelt; die Kästen sind mit der Farbtabelle
abgedunkelt (dieselbe Tabelle, mit der die 3D-Ansicht nach Entfernung dunkler wird) und haben eine
eingelassene Kante (oben/links dunkel, unten/rechts hell). Schrift zeichnet Godot (hud.gd).

    python3 scripts/build_ui.py      # schreibt demo/ui/*.png
"""
import pathlib
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import rc_palette as P  # noqa: E402

ENTRY = pathlib.Path(__file__).resolve().parent.parent
UI = ENTRY / "demo" / "ui"

# Kästen (x0, y0, x1, y1) in Statusleistenkoordinaten, einschließlich
BOXES = {"paket": (3, 3, 44, 28), "wahl": (48, 3, 206, 28), "ort": (210, 3, 316, 28)}
SLOT = (296, 15, 313, 26)


def main():
    UI.mkdir(parents=True, exist_ok=True)
    cm = np.asarray(Image.open(ENTRY / "assets" / "colormap.png"))
    iron = np.asarray(Image.open(ENTRY / "assets" / "textures" / "iron.png"))
    bar = np.tile(iron, (1, 5))[16:48, :320].copy()
    bar = cm[4][bar]                                   # etwas dunkler als volle Helligkeit
    light = P.nearest_index(np.array([[150, 140, 128]]), P.ramp_mask(["granit", "grau"]))[0]
    dark = P.nearest_index(np.array([[22, 20, 22]]), P.ramp_mask(["grau", "nacht"]))[0]
    # obere Kante der Leiste
    bar[0] = light
    bar[1] = cm[10][bar[1]]
    for name, (x0, y0, x1, y1) in list(BOXES.items()) + [("slot", SLOT)]:
        inner = bar[y0:y1 + 1, x0:x1 + 1]
        bar[y0:y1 + 1, x0:x1 + 1] = cm[22 if name != "slot" else 26][inner]
        bar[y0, x0:x1 + 1] = dark
        bar[y0:y1 + 1, x0] = dark
        bar[y1, x0:x1 + 1] = light
        bar[y0:y1 + 1, x1] = light
    Image.fromarray(P.PALETTE[bar], "RGB").save(UI / "statusbar.png")

    # Verläufe für Schrift (je Bildzeile eine Palettenfarbe), oben hell, unten dunkler
    def grad(colors, name):
        idx = [P.nearest_index(np.array([c]))[0] for c in colors]
        Image.fromarray(P.PALETTE[np.array(idx)][:, None, :].astype(np.uint8), "RGB").save(UI / f"grad_{name}.png")

    grad([(255, 170, 150), (250, 120, 100), (236, 80, 64), (216, 64, 52), (190, 44, 36), (160, 30, 26),
          (140, 24, 20), (120, 20, 18), (110, 16, 16), (100, 14, 14), (90, 12, 12), (80, 10, 10),
          (70, 8, 8), (60, 6, 6), (50, 5, 5), (40, 4, 4), (36, 4, 4), (30, 3, 3), (26, 3, 3), (22, 2, 2)], "red")
    grad([(255, 250, 200), (255, 236, 150), (255, 220, 110), (250, 200, 80), (236, 176, 60), (214, 150, 46),
          (190, 126, 36), (170, 110, 30), (150, 96, 26), (130, 84, 22)], "gold")
    grad([(236, 232, 224), (214, 208, 198), (196, 190, 180), (178, 172, 162), (160, 154, 146), (144, 138, 130),
          (130, 124, 118), (118, 112, 106), (106, 100, 96), (96, 92, 88)], "gray")
    shadow = P.nearest_index(np.array([[16, 12, 12]]))[0]
    Image.fromarray(P.PALETTE[np.array([[shadow]])].astype(np.uint8), "RGB").save(UI / "shadow.png")

    # Paket-Symbol für das Inventarfeld (RGBA, Palettenfarben)
    pk = np.asarray(Image.open(ENTRY / "assets" / "sprites" / "parcel.png"))
    rgba = np.dstack([P.PALETTE[pk], np.where(pk == P.TRANSPARENT, 0, 255).astype(np.uint8)])
    Image.fromarray(rgba.astype(np.uint8), "RGBA").save(UI / "parcel_icon.png")
    print("Statusleiste und Verläufe geschrieben:", sorted(p.name for p in UI.glob("*.png")))


if __name__ == "__main__":
    main()
