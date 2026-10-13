#!/usr/bin/env python3
"""Übernommen aus styles/bilderbuch-gouache/scripts/make_layouts.py, hier nur der Laufbogen.
Setzt die Blender-Posen (blender/pose_layout.py) zu Layout-Bögen auf reinem Magenta zusammen: erste Referenz für
die Figurenaufträge in assets/image_jobs.json (agy hält sich eng an das Layout der ersten Referenz).

    .venv/bin/python styles/kupferstich/scripts/make_layouts.py

Ergebnis:
  assets/ref/walk_layout.png    1536x1024, 2 Reihen x 5 Zellen (307x512): walk_0 … walk_7, stand, turn
  assets/ref/walk_small_layout.png  dasselbe mit --ortho 2.5 (Figur etwa 200 px hoch)
  assets/ref/layouts.json       Raster, Bildnamen in Lesereihenfolge, Bodenlinie und Sohlen je Zelle
"""
import json, pathlib
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
REF = ROOT / "assets/ref"
MAGENTA = (255, 0, 255, 255)
SHEETS = {
    "walk": {"dir": "poses_walk", "cols": 5, "rows": 2,
             "names": [f"walk_{i}" for i in range(8)] + ["stand", "turn"]},
    # Zweite Fassung in Spielgröße (Dachs etwa 200 px hoch, --ortho 2.5): Das Bildmodell hält den absoluten
    # Linienabstand; kleine Figuren im Bogen ergeben in Spielgröße dieselbe Strichweite wie der Hintergrund.
    "walk_small": {"dir": "poses_walk_small", "cols": 5, "rows": 2,
                   "names": [f"walk_{i}" for i in range(8)] + ["stand", "turn"]},
}


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
            im = Image.open(d / f"{name}.png").convert("RGBA")
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
