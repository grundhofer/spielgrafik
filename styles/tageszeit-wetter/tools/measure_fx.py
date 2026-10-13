#!/usr/bin/env python3
"""Misst, ob die Effekte in jedem Zustand sichtbar sind und ob etwas flimmert.

    .venv/bin/python styles/tageszeit-wetter/tools/measure_fx.py FRAMES_DIR

FRAMES_DIR: Bilder f00000000.png … aus tools/render.py (180 Bilder, 30 fps). Bereiche aus assets/data_a.png
(Himmel, Wasser) und festen Rechtecken (Schornstein, Laterne samt Kai). Je stehendem Zustand:
  bewegt  Anteil der Pixel, die sich über 0,5 s um mehr als 12 Stufen ändern
  sprung  Anteil der Pixel, die von Bild zu Bild um mehr als 40 Stufen springen (Flimmern/Salzrauschen)
Oberfläche (Textfeld, Zustandsleiste) und der Dachs sind ausgenommen.
"""
import json, pathlib, sys

import numpy as np
from PIL import Image

ENTRY = pathlib.Path(__file__).resolve().parent.parent
HOLDS = {"Tag": (0, 13), "Dämmerung": (24, 37), "Nacht": (48, 61), "Regen": (72, 88),
         "Nebel": (119, 135), "Schnee": (146, 179)}


def main():
    d = pathlib.Path(sys.argv[1])
    fr = sorted(d.glob("f*.png"))
    da = np.asarray(Image.open(ENTRY / "assets" / "data_a.png").convert("RGB"), np.float32) / 255
    sky, water = da[..., 0] > 0.5, da[..., 1] > 0.5
    excl = np.zeros(sky.shape, bool)
    excl[540:712, 644:1272] = True        # Textfeld
    excl[6:58, 780:1272] = True           # Zustandsleiste
    excl[520:712, 360:500] = True         # Dachs
    regions = {
        "Himmel": sky & ~excl, "Wasser": water & ~excl,
        "Schornstein": np.zeros_like(sky), "Laterne+Kai": np.zeros_like(sky), "Kai": np.zeros_like(sky),
    }
    regions["Schornstein"][0:60, 90:330] = True
    regions["Laterne+Kai"][250:340, 340:420] = True
    regions["Laterne+Kai"][590:720, 200:360] = True
    regions["Kai"][600:720, 0:640] = True
    for k in ("Schornstein", "Laterne+Kai", "Kai"):
        regions[k] &= ~excl
    load = lambda i: np.asarray(Image.open(fr[i]).convert("RGB"), np.int16)
    out = {}
    for name, (a, b) in HOLDS.items():
        res = {}
        pairs = [(i, i + 15) for i in range(a, b - 14, 5)] or [(a, b)]
        steps = list(range(a, b))
        for rn, m in regions.items():
            mv = np.mean([(np.abs(load(j) - load(i)).max(-1) > 12)[m].mean() for i, j in pairs])
            jp = np.mean([(np.abs(load(i + 1) - load(i)).max(-1) > 40)[m].mean() for i in steps[::3]])
            res[rn] = {"bewegt": round(float(mv), 4), "sprung": round(float(jp), 4)}
        out[name] = res
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
