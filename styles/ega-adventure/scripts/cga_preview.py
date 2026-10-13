#!/usr/bin/env python3
"""CGA-Fassung des Bildes als Standbild (gleiche Paartabelle wie demo/shaders/ega.gdshader).

    .venv/bin/python styles/ega-adventure/scripts/cga_preview.py [bild.pic.json ausgabe.png]
Ohne Angabe: demo/art/harbor.pic.json -> assets/harbor_cga.png.
"""
import json, pathlib, sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from agipic import replay  # noqa: E402

SD = HERE.parent
CGA = np.array([[0, 0, 0], [85, 255, 255], [255, 85, 255], [255, 255, 255]], np.uint8)
PAIR = [0, 1, 5, 5, 10, 2, 6, 7, 3, 5, 5, 5, 11, 10, 15, 15]   # links*4 + rechts

src = pathlib.Path(sys.argv[1]) if len(sys.argv) > 2 else SD / "demo/art/harbor.pic.json"
dst = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else SD / "assets/harbor_cga.png"
vis, _ = replay(json.loads(src.read_text())["commands"])
h, w = vis.shape
out = np.zeros((h, w * 2, 3), np.uint8)
pairs = np.array(PAIR)[vis]
out[:, 0::2] = CGA[pairs // 4]
out[:, 1::2] = CGA[pairs % 4]
Image.fromarray(out).save(dst)
print("ok", dst)
