#!/usr/bin/env python3
"""Saubere Vorlagen der vorhandenen Figurenbögen für das Übermalen in einer anderen Technik.

    .venv/bin/python styles/tusche-sumie/tools/make_clean_refs.py

raw/walk.png kam mit halbtransparentem Schleier (Alpha 0,1–0,3); für die Vorlage zählt nur die deckende Figur
(Alpha > 0,5), auf Weiß gesetzt. Ergebnis: assets/ref/walk_clean.png, assets/ref/front_clean.png.
"""
import numpy as np
from PIL import Image

from inkutil import ROOT

for key in ("walk", "front"):
    a = np.asarray(Image.open(ROOT / f"assets/raw/{key}.png").convert("RGBA"), np.float32) / 255.0
    al = np.where(a[..., 3] > 0.5, a[..., 3], 0.0)[..., None]
    rgb = a[..., :3] * al + (1 - al)
    Image.fromarray((rgb * 255 + 0.5).astype(np.uint8), "RGB").save(ROOT / f"assets/ref/{key}_clean.png")
    print("ok", key)
