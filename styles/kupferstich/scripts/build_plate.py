#!/usr/bin/env python3
"""Macht aus dem KI-Stich (assets/raw/bg2.png) die Druckplatte der Demo: Linien auf blankem Papier.

    .venv/bin/python styles/kupferstich/scripts/build_plate.py

Schritte (in Quellauflösung, erst am Ende auf Plattengröße verkleinert):
 1. Ausschnitt laut layout.json, Helligkeit -> Tuschedichte D (Papier = 99. Perzentil, Tusche = 0,5. Perzentil).
 2. Flächenton zu 60 % entfernen: Das Bildmodell legt einen braunen Grund zwischen die Linien. Lokaler Grund
    = Minimum über 7x7, geglättet; D_lin = (D - 0,6 Grund) / (1 - 0,6 Grund). Ganz entfernt (100 %) verliert die
    Nachtszene ihre Dunkelheit, 60 % lässt die Linien auf hellerem Papier stehen und hält die Stimmung.
 3. Kontrast: (D_lin - 0,08) / 0,84, Gamma 0,9 (feinste Grauschleier fallen weg).
 4. Einfassung (Linie am Bildrand), auf Plattengröße verkleinern (Lanczos).
Verworfen (siehe style.json): Tonwert über Schwellen je Pixel nachstellen (Linien in dunklen Stellen verdicken)
verklumpt Linien, die nach dem Verkleinern unter 2 px Abstand liegen, zu Flecken.
Ausgabe: assets/plate_ink.png (RGB: R = Tusche, G = Kammfeld für Lichteffekte im Shader, B = helle Spiegelungen im
Wasser für das Glitzern, aus assets/plate_mask.png von build_scene.py) + Kopie in demo/art.
Der Shader dünnt im Licht die Linien über das Kammfeld aus (feine Linien verschwinden zuerst).
"""
import json, shutil

import numpy as np
from PIL import Image

import inklib as K

WASH = 0.6


def ink_lines(D, wash=WASH):
    """Tuschedichte ohne (größten Teil des) Flächentons, mit leichtem Kontrast."""
    m = K.blur(K.erode(D, 3), 2)
    Dl = np.clip((D - wash * m) / np.maximum(1 - wash * m, 0.15), 0, 1)
    return np.clip((Dl - 0.08) / 0.84, 0, 1) ** 0.9


def main():
    lay = K.LAYOUT
    x0, y0, x1, y1 = lay["src_crop"]
    px, py, pw, ph = lay["plate"]
    im = Image.open(K.SD / lay["src"]).convert("RGB").crop((x0, y0, x1, y1))
    D, paper, ink = K.density(K.lum(im), lo_pct=0.5, hi_pct=99.0)
    E = ink_lines(D)
    # Einfassung: 2,5 Quellpixel breite Linie am Bildrand
    h, w = E.shape
    b = 3
    E[:b, :] = 1
    E[-b:, :] = 1
    E[:, :b] = 1
    E[:, -b:] = 1
    ink_d = K.resize_f(E, (pw, ph)).clip(0, 1)
    ridge = K.blur(ink_d, 0.9)
    ridge = np.clip(ridge / max(1e-3, float(np.percentile(ridge, 99.5))), 0, 1)
    water = np.asarray(Image.open(K.SD / "assets/plate_mask.png").convert("RGB"), np.float32)[..., 1] / 255
    refl = water * np.clip((0.62 - K.blur(ink_d, 4.0)) / 0.35, 0, 1)
    rgb = np.stack([ink_d, ridge, refl], -1)
    out = K.SD / "assets/plate_ink.png"
    Image.fromarray(np.clip(rgb * 255 + 0.5, 0, 255).astype(np.uint8)).save(out)
    shutil.copy(out, K.SD / "demo/art/plate_ink.png")
    info = {"src_paper_lum": round(paper, 3), "src_ink_lum": round(ink, 3), "scale": pw / (x1 - x0),
            "mean_ink": round(float(ink_d.mean()), 3)}
    print(json.dumps(info))


if __name__ == "__main__":
    main()
