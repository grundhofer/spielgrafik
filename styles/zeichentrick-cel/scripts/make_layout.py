#!/usr/bin/env python3
"""Setzt die Blender-Posen (blender/pose_layout.py) zu einem Layout-Bogen auf Weiß zusammen: erste Referenz für
den Cel-Bogen (assets/raw/sheet.png). Nach styles/bilderbuch-gouache/scripts/make_layouts.py.

    .venv/bin/python styles/zeichentrick-cel/scripts/make_layout.py

Ergebnis:
  assets/ref/sheet_layout.png  1536x1024, 2 Reihen x 5 Zellen (307x512): walk_0 … walk_7, stand, front
  assets/ref/layout.json       Raster, Bildnamen in Lesereihenfolge, Bodenlinie und Sohlen je Zelle
"""
import json, pathlib
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
REF = ROOT / "assets/ref"
NAMES = [f"walk_{i}" for i in range(8)] + ["stand", "front"]
COLS, ROWS = 5, 2


def main():
    d = REF / "poses"
    info = json.loads((d / "poses.json").read_text())
    feet = {f["name"]: f["feet"] for f in info["frames"]}
    cw, ch = info["w"], info["h"]
    sheet = Image.new("RGBA", (1536, 1024), (255, 255, 255, 255))
    ox = (1536 - cw * COLS) // 2
    oy = (1024 - ch * ROWS) // 2
    cells = []
    for i, name in enumerate(NAMES):
        im = Image.open(d / f"{name}.png").convert("RGBA")
        x, y = ox + (i % COLS) * cw, oy + (i // COLS) * ch
        sheet.alpha_composite(im, (x, y))
        cells.append({"name": name, "x": x, "y": y, "w": cw, "h": ch, "ground_y": y + info["ground_y"],
                      "feet": feet[name]})
    sheet.convert("RGB").save(REF / "sheet_layout.png")
    (REF / "layout.json").write_text(json.dumps({"file": "assets/ref/sheet_layout.png", "cols": COLS, "rows": ROWS,
                                                 "px_per_m": info["px_per_m"], "cells": cells}, indent=1))
    print("ok", REF / "sheet_layout.png")


if __name__ == "__main__":
    main()
