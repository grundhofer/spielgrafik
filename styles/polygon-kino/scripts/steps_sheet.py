#!/usr/bin/env python3
"""Doku-Bild der Rotoskopie für eine Dachs-Phase: Lichtbild aus Blender, Kennbild nach den Regeln (Palette,
überabgetastet), fertige Polygone in 320x200 mit Ecken. Schreibt assets/rotoscope_steps.png und
assets/palettes.png (beide 16-Farben-Paletten).

  .venv/bin/python styles/polygon-kino/scripts/steps_sheet.py <passes-ordner> [--frame B_wave_06]
"""
import argparse
import json
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import polyvec as pv  # noqa: E402
import vectorize as V  # noqa: E402

ENTRY = pathlib.Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("passes")
    ap.add_argument("--frame", default="B_wave_06")
    a = ap.parse_args()
    pdir = pathlib.Path(a.passes)
    shot, clip, idx = a.frame.split("_")
    ids = json.load(open(pdir / "ids.json"))
    ss = json.load(open(pdir / "frames.json"))["ss"]
    data = json.load(open(ENTRY / "demo/data/scenes.json"))
    pal = data["palettes"][shot]
    lab = V.label_map(shot, ids, str(pdir / a.frame), ss)
    ys, xs = np.nonzero(lab >= 0)
    pad = 4 * ss
    y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad, lab.shape[0])
    x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad, lab.shape[1])
    H = 600
    sc = H / (y1 - y0)
    W = int((x1 - x0) * sc)
    bg = (60, 58, 92)
    lit = np.asarray(Image.open(pdir / f"{a.frame}_lit.png"))[y0:y1, x0:x1]
    p1 = np.where(lit[..., 3:4] > 0, np.repeat(lit[..., :1], 3, axis=2), np.array(bg, np.uint8))
    p1 = Image.fromarray(p1.astype(np.uint8)).resize((W, H), Image.NEAREST)
    p2 = Image.fromarray(V.to_rgb(lab, pal, "#3c3a5c")[y0:y1, x0:x1]).resize((W, H), Image.NEAREST)
    polys = data["shots"][shot]["clips"][clip]["frames"][int(idx)]
    img = np.full((lab.shape[0] // ss, lab.shape[1] // ss), -1, np.int32)
    for c, t, p in polys:
        pv.raster(img, list(zip(p[0::2], p[1::2])), c)
    p3 = Image.fromarray(V.to_rgb(img, pal, "#3c3a5c")[y0 // ss:y1 // ss, x0 // ss:x1 // ss])
    k = H / p3.height
    p3 = p3.resize((int(p3.width * k), H), Image.NEAREST)
    d = ImageDraw.Draw(p3)
    for c, t, p in polys:
        pts = [((x - x0 / ss) * k, (y - y0 / ss) * k) for x, y in zip(p[0::2], p[1::2])]
        d.line(pts + [pts[0]], fill=(255, 255, 255), width=1)
        for q in pts:
            d.rectangle([q[0] - 1.5, q[1] - 1.5, q[0] + 1.5, q[1] + 1.5], fill=(255, 255, 255))
    p4 = Image.fromarray(V.to_rgb(img, pal, "#3c3a5c")[y0 // ss:y1 // ss, x0 // ss:x1 // ss]).resize(
        (p3.width, H), Image.NEAREST)
    gap = 12
    sheet = Image.new("RGB", (p1.width + p2.width + p3.width + p4.width + 3 * gap, H), (11, 10, 20))
    x = 0
    for p in (p1, p2, p3, p4):
        sheet.paste(p, (x, 0))
        x += p.width + gap
    sheet.save(ENTRY / "assets/rotoscope_steps.png", optimize=True)
    # Paletten
    sw = 40
    pim = Image.new("RGB", (16 * sw, 2 * sw + 6), (11, 10, 20))
    dd = ImageDraw.Draw(pim)
    for r, key in enumerate(("A", "B")):
        for i, hx in enumerate(data["palettes"][key]):
            dd.rectangle([i * sw, r * (sw + 6), i * sw + sw - 1, r * (sw + 6) + sw - 1], fill=hx)
    pim.save(ENTRY / "assets/palettes.png")
    print("Polygone:", len(polys), "Ecken:", sum(len(p[2]) // 2 for p in polys), "->", ENTRY / "assets")


if __name__ == "__main__":
    main()
