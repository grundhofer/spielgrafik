#!/usr/bin/env python3
"""Prüft, ob Tiefenbild und Kameradaten zusammenpassen (gleiche Projektion wie in Godot: vertikaler
Bildwinkel, Keep Height, Pixelmitten). Für Pixel im unteren Bilddrittel wird der Sehstrahl mit der Kaiebene
y = 0 geschnitten und die erwartete Tiefe (entlang der Blickachse) mit depth.png verglichen.

    .venv/bin/python styles/vorgerendert-fixkamera/scripts/check_camera.py
"""
import json
import math
import pathlib

import numpy as np
from PIL import Image

STYLE = pathlib.Path(__file__).resolve().parent.parent

for shot in ("totale", "nah"):
    d = STYLE / "assets" / "bg" / shot
    meta = json.loads((d / "meta.json").read_text())
    cam = meta["camera"]
    B = np.array(cam["basis_columns"]).T          # Spalten = lokale Achsen
    o = np.array(cam["origin"])
    W, H = meta["size"]
    f = (H / 2) / math.tan(math.radians(cam["fov"]) / 2)
    e = np.asarray(Image.open(d / "depth.png").convert("RGB")).astype(np.int64)
    depth = (e[..., 0] * 65536 + e[..., 1] * 256 + e[..., 2]) / 16777215 * meta["depth_range"]
    errs = []
    for y in range(int(H * 0.72), H, 3):
        for x in range(0, W, 3):
            v = np.array([(x + 0.5 - W / 2) / f, -(y + 0.5 - H / 2) / f, -1.0])   # Kameraraum, z = -1
            r = B @ v
            if r[1] >= -1e-6:
                continue
            s = -o[1] / r[1]                       # Schnitt mit y = 0
            errs.append(depth[y, x] - s)            # s = Tiefe entlang der Blickachse (v hat z = -1)
    errs = np.array(errs)
    print(shot, "Pixel", len(errs), "Median Abweichung %.1f mm" % (1000 * np.median(errs)),
          "| |Abw.| p90 %.1f mm" % (1000 * np.percentile(np.abs(errs), 90)))
