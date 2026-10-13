#!/usr/bin/env python3
"""Bereitet die Randfigur (Drolerie: Hase mit Goldtrompete, assets/raw/drollery.png, gpt-image mit Alphakanal)
für den unteren Rand auf.

    .venv/bin/python styles/buchmalerei/scripts/build_drollery.py [--height 120]

Ausgabe: assets/drollery.png (RGBA, vormultipliziert mit Lanczos verkleinert), assets/drollery_gold.png
(RGB-Maske, R = Gold der Trompete: Farbton 36-56°, Sättigung > 0,58, Helligkeit > 0,62; G = 0; B = Relief aus der
Helligkeit), assets/drollery.json (Größe, Fußpunkt).
"""
import argparse, json, pathlib, sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build_badger import premul_resize  # noqa: E402
from build_miniature import hsv  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--height", type=int, default=120)
    a = ap.parse_args()
    src = np.array(Image.open(ROOT / "assets/raw/drollery.png").convert("RGBA"))
    al = src[..., 3] > 128
    ys, xs = np.nonzero(al)
    rows = al.sum(1)
    sole = max(y for y in range(src.shape[0]) if rows[y] > 20)
    x0, y0, x1, y1 = xs.min() - 6, ys.min() - 6, xs.max() + 7, sole + 3
    s = a.height / float(y1 - y0)
    size = (round((x1 - x0) * s), a.height)
    crop = src[y0:y1, x0:x1]
    out = premul_resize(crop, size)
    Image.fromarray(out).save(ROOT / "assets/drollery.png")
    h, sat, v = hsv(crop[..., :3])
    gold = (h >= 36) & (h <= 56) & (sat > 0.58) & (v > 0.62) & (crop[..., 3] > 128)
    rel = np.clip((v - 0.5) * 2.2, 0, 1)
    mask = np.dstack([gold * 255, np.zeros_like(v), rel * 255]).astype(np.uint8)
    Image.fromarray(mask).resize(size, Image.BOX).save(ROOT / "assets/drollery_gold.png")
    feet = np.nonzero(al[sole - 4])[0]
    info = {"source": "assets/raw/drollery.png", "scale": s, "size": list(size),
            "foot": [round(((feet.min() + feet.max()) / 2 - x0) * s, 2), round((sole - y0) * s, 2)],
            "gold_px": int((np.array(Image.open(ROOT / "assets/drollery_gold.png"))[..., 0] > 127).sum())}
    (ROOT / "assets/drollery.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info))


if __name__ == "__main__":
    main()
