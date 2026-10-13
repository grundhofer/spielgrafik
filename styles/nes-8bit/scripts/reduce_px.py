#!/usr/bin/env python3
"""KI-Pixelbild auf ein echtes Raster bringen: jede Quellzelle auf Systemfarben abbilden und je Zielpixel
die häufigste Systemfarbe im Zellinneren wählen (keine Mischfarben).
   reduce_px.py in.png out.png --width 256 [--inner 0.6] [--preview x3.png]"""
import argparse, pathlib, sys
import numpy as np
from PIL import Image
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import neslib


def reduce(img, width, height=None, inner=0.6, allowed=None):
    rgb = np.asarray(img.convert("RGB")).astype(np.float32)
    H, W, _ = rgb.shape
    height = height or round(H * width / W)
    idx = neslib.nearest_sys(rgb, allowed)
    out = np.zeros((height, width), np.int32)
    sx, sy = W / width, H / height
    m = (1 - inner) / 2
    for j in range(height):
        y0, y1 = int(round((j + m) * sy)), max(int(round((j + 1 - m) * sy)), int(round((j + m) * sy)) + 1)
        for i in range(width):
            x0, x1 = int(round((i + m) * sx)), max(int(round((i + 1 - m) * sx)), int(round((i + m) * sx)) + 1)
            cell = idx[y0:y1, x0:x1].ravel()
            out[j, i] = np.bincount(cell, minlength=64).argmax()
    return out


def to_rgb(idx):
    return Image.fromarray(neslib.SYSPAL[idx].astype(np.uint8))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("inp"); ap.add_argument("out")
    ap.add_argument("--width", type=int, default=256); ap.add_argument("--height", type=int, default=0)
    ap.add_argument("--inner", type=float, default=0.6)
    ap.add_argument("--preview")
    a = ap.parse_args()
    idx = reduce(Image.open(a.inp), a.width, a.height or None, a.inner)
    np.save(pathlib.Path(a.out).with_suffix(".npy"), idx)
    im = to_rgb(idx); im.save(a.out)
    if a.preview:
        im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(a.preview)
    u, c = np.unique(idx, return_counts=True)
    print(f"{a.out}: {idx.shape[1]}x{idx.shape[0]}, {len(u)} Systemfarben:",
          " ".join(f"{v:02X}:{n}" for v, n in sorted(zip(u, c), key=lambda t: -t[1])))
