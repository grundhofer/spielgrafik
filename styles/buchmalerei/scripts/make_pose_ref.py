#!/usr/bin/env python3
"""Setzt die Blender-Pose (blender/pose_layout.py, Wave Bild 12, um -60° zur Kamera gedreht) als Layout-Referenz
für das Bildmodell auf Magenta: Figur auf 88 % der Bildhöhe, waagerecht mittig, Oberkante bei 6 %.

    blender -b --factory-startup -P styles/buchmalerei/blender/pose_layout.py -- \
        --glb shared/3d/badger.glb --out <tmp>/poses --pose wave:12:-60
    .venv/bin/python styles/buchmalerei/scripts/make_pose_ref.py <tmp>/poses/wave_12_-60.png

Ergebnis: assets/ref/pose_layout.png (1024x1536, RGB)
"""
import pathlib, sys

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]

im = Image.open(sys.argv[1]).convert("RGBA")
a = np.array(im)[:, :, 3]
ys, xs = np.nonzero(a > 8)
crop = im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
H = int(1536 * 0.88)
s = H / crop.height
crop = crop.resize((round(crop.width * s), H), Image.LANCZOS)
can = Image.new("RGBA", (1024, 1536), (255, 0, 255, 255))
can.alpha_composite(crop, ((1024 - crop.width) // 2, int(1536 * 0.06)))
can.convert("RGB").save(ROOT / "assets/ref/pose_layout.png")
print("ok", ROOT / "assets/ref/pose_layout.png")
