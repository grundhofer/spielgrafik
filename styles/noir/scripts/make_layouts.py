#!/usr/bin/env python3
"""Setzt die Blender-Posen (blender/pose_layout.py) zum Layout-Bogen auf reinem Magenta zusammen: erste Referenz für
den Laufbogen (raw/walk.png). Übernommen aus styles/bilderbuch-gouache/scripts/make_layouts.py; neu ist die
Umsetzung in Grautöne: alles außer dem roten Schal wird entsättigt, damit das Bildmodell die Tonwerte des
Schwarzweiß-Stils und die einzige Akzentfarbe schon im Layout sieht.

    .venv/bin/python styles/noir/scripts/make_layouts.py

Ergebnis:
  assets/ref/walk_layout.png    1536x1024, 2 Reihen x 5 Zellen (307x512): walk_0 … walk_7, stand, turn
  assets/ref/layouts.json       Raster, Bildnamen in Lesereihenfolge, Bodenlinie und Sohlen je Zelle
"""
import json, pathlib

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
REF = ROOT / "assets/ref"
MAGENTA = (255, 0, 255, 255)
SHEETS = {
    "walk": {"dir": "poses_walk", "cols": 5, "rows": 2,
             "names": [f"walk_{i}" for i in range(8)] + ["stand", "turn"]},
}


def noir_tone(im):
    """Entsättigt alles außer roten Flächen (Schal). Rot = Farbton nahe 0° und deutlich gesättigt."""
    a = np.asarray(im.convert("RGBA")).astype(np.float32)
    rgb = a[..., :3] / 255.0
    lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    mx, mn = rgb.max(-1), rgb.min(-1)
    sat = (mx - mn) / np.maximum(mx, 1e-4)
    red = (rgb[..., 0] >= mx - 1e-6) & (rgb[..., 0] > rgb[..., 1] * 2.4) & (rgb[..., 0] > rgb[..., 2] * 2.0) & (sat > 0.55)
    out = np.repeat(lum[..., None], 3, -1)
    out[red] = rgb[red]
    a[..., :3] = np.clip(out * 255.0 + 0.5, 0, 255)
    return Image.fromarray(a.astype(np.uint8), "RGBA")


def main():
    out = {}
    for key, s in SHEETS.items():
        d = REF / s["dir"]
        info = json.loads((d / "poses.json").read_text())
        feet = {f["name"]: f["feet"] for f in info["frames"]}
        cw, ch = info["w"], info["h"]
        sheet = Image.new("RGBA", (1536, 1024), MAGENTA)
        ox = (1536 - cw * s["cols"]) // 2
        oy = (1024 - ch * s["rows"]) // 2
        cells = []
        for i, name in enumerate(s["names"]):
            im = noir_tone(Image.open(d / f"{name}.png"))
            x, y = ox + (i % s["cols"]) * cw, oy + (i // s["cols"]) * ch
            sheet.alpha_composite(im, (x, y))
            cells.append({"name": name, "x": x, "y": y, "w": cw, "h": ch, "ground_y": y + info["ground_y"],
                          "feet": feet[name]})
        sheet.convert("RGB").save(REF / f"{key}_layout.png")
        out[key] = {"file": f"assets/ref/{key}_layout.png", "cols": s["cols"], "rows": s["rows"],
                    "px_per_m": info["px_per_m"], "cells": cells}
        print("ok", REF / f"{key}_layout.png")
    (REF / "layouts.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
