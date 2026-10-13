"""Hand-Mauszeiger als Pixelgrafik (eigene Zeichnung, nur Farben aus der festen UI-Rampe der Palette).

    .venv/bin/python styles/vorgerendert-diashow/scripts/cursors.py [--preview OUT.png]

Schreibt assets/cursors.png (Blatt mit drei Zeigern nebeneinander, je CELL×CELL) und demo/ui/cursors.png;
Hotspots in demo/ui/cursors.json. Zeiger: zeigende Hand nach oben (vorwärts gehen), nach rechts (drehen),
offene Hand (benutzen, ansprechen).
"""
import json
import pathlib
import sys

import numpy as np
from PIL import Image

STYLE = pathlib.Path(__file__).resolve().parent.parent
CELL = 24
COL = {"K": (0, 0, 0, 255), "W": (255, 255, 255, 255), "G": (184, 184, 184, 255), "D": (110, 110, 110, 255),
       ".": (0, 0, 0, 0)}

POINT_UP = [
    "......KK..........",
    ".....KWWK.........",
    ".....KWWK.........",
    ".....KWWK.........",
    ".....KWWK.........",
    ".....KWWKKK.......",
    ".....KWWKWWKKK....",
    ".....KWWKWWKWWKK..",
    ".KK..KWWKWWKWWKWK.",
    "KWWK.KWWKWWKWWKWWK",
    "KWWWKKWWWWWWWWWWWK",
    ".KWWWKWWWWWWWWWWWK",
    "..KWWWWWWWWWWWWWWK",
    "..KWWWWWWWWWWWWWGK",
    "...KWWWWWWWWWWWGK.",
    "...KWWWWWWWWWWWGK.",
    "....KWWWWWWWWWGK..",
    "....KGWWWWWWWGGK..",
    ".....KGGGGGGGGK...",
    ".....KDDDDDDDDK...",
    ".....KKKKKKKKKK...",
]

OPEN = [
    "........KK........",
    ".....KKKWWKKK.....",
    "....KWWKWWKWWK....",
    "....KWWKWWKWWKKK..",
    "....KWWKWWKWWKWWK.",
    "....KWWKWWKWWKWWK.",
    "KK..KWWKWWKWWKWWK.",
    "KWK.KWWKWWKWWKWWK.",
    "KWWKKWWWWWWWWWWWK.",
    ".KWWWWWWWWWWWWWWK.",
    ".KWWWWWWWWWWWWWWK.",
    "..KWWWWWWWWWWWWGK.",
    "..KWWWWWWWWWWWWGK.",
    "...KWWWWWWWWWWGK..",
    "...KWWWWWWWWWWGK..",
    "....KWWWWWWWWGK...",
    "....KGWWWWWWGGK...",
    ".....KGGGGGGGK....",
    ".....KDDDDDDDK....",
    ".....KKKKKKKKK....",
]


def to_img(rows):
    h, w = len(rows), max(len(r) for r in rows)
    a = np.zeros((h, w, 4), np.uint8)
    for y, r in enumerate(rows):
        for x, c in enumerate(r):
            a[y, x] = COL[c]
    return a


def main():
    up = to_img(POINT_UP)
    right = np.rot90(up, k=-1).copy()          # Finger zeigt nach rechts
    opn = to_img(OPEN)
    cursors = [("point_up", up, (6, 0)), ("point_right", right, (up.shape[0] - 1, 6)), ("open", opn, (9, 1))]
    sheet = np.zeros((CELL, CELL * len(cursors), 4), np.uint8)
    meta = {"cell": CELL, "cursors": {}}
    for i, (name, im, hot) in enumerate(cursors):
        h, w = im.shape[:2]
        assert h <= CELL and w <= CELL, (name, w, h)
        sheet[:h, i * CELL:i * CELL + w] = im
        meta["cursors"][name] = {"index": i, "hotspot": list(hot), "size": [w, h]}
    out_assets = STYLE / "assets" / "cursors.png"
    Image.fromarray(sheet, "RGBA").save(out_assets)
    ui = STYLE / "demo" / "ui"
    ui.mkdir(parents=True, exist_ok=True)
    Image.fromarray(sheet, "RGBA").save(ui / "cursors.png")
    (ui / "cursors.json").write_text(json.dumps(meta, indent=1))
    if "--preview" in sys.argv:
        p = sys.argv[sys.argv.index("--preview") + 1]
        bg = Image.new("RGBA", sheet.shape[1::-1], (60, 90, 140, 255))
        bg.alpha_composite(Image.fromarray(sheet, "RGBA"))
        bg.resize((bg.width * 8, bg.height * 8), Image.NEAREST).save(p)
    print("ok", {k: v["size"] for k, v in meta["cursors"].items()})


if __name__ == "__main__":
    main()
