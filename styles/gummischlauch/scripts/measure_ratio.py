"""Misst das Größenverhältnis Dachs : Häuschen : Tür (Prüfung „Größenverhältnisse“).

Häuschen und Tür aus der Textur assets/props/cottage.png (wird in Ruhe 1:1 gezeichnet):
  - Türblatt = größte Komponente graugrüner Pixel (G > R + 0,02, Helligkeit < 0,45) in der linken Hälfte
  - Türrahmen samt Sturz = über der Blattmitte nach oben, solange braune Rahmenpixel (R − B > 0,12, R > G) folgen
  - Häuschen = Höhe des deckenden Inhalts samt Schornstein (content_h)
Dachs aus assets/measure_badger.json (vorher scripts/measure_badger.py laufen lassen): Sohlenzeile und oberste
Zeile je Tick, Vorderansicht ab Tick 63 (nach dem Federsprung), Gang Tick 12–53.
Ergebnis: assets/measure_ratio.json

    .venv/bin/python styles/gummischlauch/scripts/measure_ratio.py
"""
import json
import pathlib

import numpy as np
from PIL import Image

import gs_util as g

HERE = pathlib.Path(__file__).resolve().parent.parent


def main():
    scene = json.loads((HERE / "assets" / "scene.json").read_text())
    cm = scene["props"]["cottage"]
    a = np.asarray(Image.open(HERE / "assets" / cm["file"]).convert("RGBA")).astype(np.float32) / 255.0
    rgb, al = a[..., :3], a[..., 3]
    h, w = al.shape
    lum = rgb.mean(axis=2)
    leaf = (al > 0.9) & (rgb[..., 1] > rgb[..., 0] + 0.02) & (lum < 0.45)
    leaf[:, w // 2:] = False
    lab, comps = g.label(leaf, min_px=200)
    x0, y0, x1, y1 = comps[0][1]
    cx = (x0 + x1) // 2
    brown = (al > 0.9) & (rgb[..., 0] - rgb[..., 2] > 0.12) & (rgb[..., 0] > rgb[..., 1])
    top = y0
    # über dem Blatt: schmale dunkle Fuge, dann der braune Sturz; nach oben gehen, bis kein Braun mehr folgt
    y = y0 - 1
    gap = 0
    while y > 0 and gap < 4:
        if brown[y, cx - 3:cx + 4].mean() > 0.5:
            top, gap = y, 0
        else:
            gap += 1
        y -= 1
    leaf_px = y1 - y0
    frame_px = y1 - top
    cottage_px = cm["content_h"]
    mb = json.loads((HERE / "assets" / "measure_badger.json").read_text())
    tops = mb["head_top_per_tick"]
    sole = mb["sole_bottom_front_view"][0]
    front_h = sole - min(tops[63:]) + 1
    walk_h = [sole - max(tops[12:54]) + 1, sole - min(tops[12:54]) + 1]
    res = {
        "door_leaf_px": int(leaf_px), "door_frame_px": int(frame_px), "cottage_px": int(cottage_px),
        "cottage_foot_y": cm["at"][1], "badger_sole_y": sole,
        "badger_front_px": int(front_h), "badger_walk_px": [int(v) for v in walk_h],
        "door_frame_to_badger": round(frame_px / front_h, 3), "door_leaf_to_badger": round(leaf_px / front_h, 3),
        "cottage_to_badger": round(cottage_px / front_h, 3),
    }
    (HERE / "assets" / "measure_ratio.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
