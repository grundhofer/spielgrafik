#!/usr/bin/env python3
"""Material-ID-Renders (blender/render_badger.py) -> Halbblock-Karten des Dachses.

    .venv/bin/python styles/textmodus-ascii/scripts/sprite_from_render.py <renderordner> [--rows 16]

Je Zielpixel (8×7 Bildschirmpixel = eine Zellhälfte) zählt das Skript die Materialien aus und nimmt das
häufigste; kleine Merkmale (Auge, Nase, Messing) zählen vierfach. Material -> Palettenfarbe nach MAT_COLOR.
Danach Zellregel: Liegen zwei helle Farben in einer Zelle übereinander, wird Dunkelgrau zu Schwarz (sonst die
untere Hälfte zu ihrer dunklen Schwester). Ausgabe: <renderordner>/badger_maps.json und der Vergleich
assets/badger_auto_vs_hand.png (links automatisch aus dem Render, rechts das von Hand gesetzte Sprite).

Ergebnis des Versuchs: Bei 16 Halbzeilen Höhe ist die Figur nur 6–7 Spalten breit; Auge, Nase und Beine gehen
im Mehrheitsentscheid unter. Die Demo nutzt deshalb die Handfassung aus build_sprites.py.
"""
import argparse, json, pathlib, sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tmscreen import COLOR_LETTERS  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
RENDER_PX, ORTHO, CAM_Z = 700, 1.4, 0.62
FIG_H = 1.011

# ID-Farbe aus render_badger.py (sRGB 0..255) -> Material
IDS = {
    (51, 51, 51): "FurDark", (255, 255, 255): "FurLight", (0, 128, 0): "Cap", (255, 255, 0): "Brass",
    (0, 255, 0): "Vest", (204, 204, 153): "Shirt", (255, 0, 0): "Scarf", (128, 64, 0): "Satchel",
    (255, 153, 51): "Parcel", (0, 0, 0): "Nose", (0, 0, 255): "Eye",
}
MAT_COLOR = {  # Material -> Buchstabe (COLOR_LETTERS)
    "FurDark": "d", "FurLight": "w", "Cap": "g", "Brass": "y", "Vest": "g", "Shirt": "l", "Scarf": "r",
    "Satchel": "n", "Parcel": "n", "Nose": "k", "Eye": "k",
}
WEIGHT = {"Eye": 5.0, "Nose": 4.0, "Brass": 2.0}


def classify(im):
    a = np.asarray(im.convert("RGBA")).astype(int)
    rgb, alpha = a[..., :3], a[..., 3]
    keys = np.array(list(IDS.keys()))
    d = ((rgb[..., None, :] - keys[None, None]) ** 2).sum(-1)
    idx = d.argmin(-1)
    names = list(IDS.values())
    out = np.full(idx.shape, -1)
    ok = (alpha > 128) & (d.min(-1) < 900)
    out[ok] = idx[ok]
    return out, names


def to_map(path, rows, cols, origin_col):
    cls, names = classify(Image.open(path))
    m_per_px = ORTHO / RENDER_PX
    ground_y = RENDER_PX / 2 + CAM_Z / m_per_px          # Bildzeile von z = 0
    bh = FIG_H / rows / m_per_px * 1.0                   # Renderpixel je Halbzeile
    bw = bh * 8 / 7                                      # Zellhälfte ist 8×7 Bildschirmpixel
    x_origin = RENDER_PX / 2
    out = []
    for r in range(rows):
        y0 = ground_y - (rows - r) * bh
        line = ""
        for c in range(cols):
            x0 = x_origin + (c - origin_col) * bw
            blk = cls[int(round(y0)):int(round(y0 + bh)), int(round(x0)):int(round(x0 + bw))]
            n = blk.size
            score = {}
            for k in np.unique(blk):
                cnt = (blk == k).sum()
                if k < 0:
                    score[None] = cnt
                else:
                    score[names[k]] = cnt * WEIGHT.get(names[k], 1.0)
            best = max(score, key=score.get) if score else None
            empty = score.get(None, 0) / max(n, 1)
            line += "." if best is None or empty > 0.62 else MAT_COLOR[best]
        out.append(line)
    return out


def fix_cells(rows, parity=0):
    rows = [list(r) for r in rows]
    for v in range(parity, len(rows) - 1, 2):
        for x in range(len(rows[v])):
            a, b = rows[v][x], rows[v + 1][x]
            if a == "." or b == "." or a == b:
                continue
            ca, cb = COLOR_LETTERS[a], COLOR_LETTERS[b]
            if ca >= 8 and cb >= 8:
                if a == "d":
                    rows[v][x] = "k"
                elif b == "d":
                    rows[v + 1][x] = "k"
                else:
                    rows[v + 1][x] = next(k for k, c in COLOR_LETTERS.items() if c == cb - 8)
    return ["".join(r) for r in rows]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("renders")
    ap.add_argument("--rows", type=int, default=16)
    ap.add_argument("--cols", type=int, default=12)
    ap.add_argument("--origin", type=float, default=5.5, help="Spalte des Figurursprungs")
    a = ap.parse_args()
    rd = pathlib.Path(a.renders)
    maps = {}
    for p in sorted(rd.glob("*.png")):
        m = fix_cells(to_map(p, a.rows, a.cols, a.origin))
        maps[p.stem] = m
        print(p.stem)
        print("\n".join(m))
        print()
    (rd / "badger_maps.json").write_text(json.dumps(maps, indent=1))
    # Vergleich vor dem Hafenbild
    import build_scene, build_sprites
    from tmscreen import Screen
    scene, _ = build_scene.build()
    s = scene.copy()
    s.sprite(30, 24, maps["side_idle"])
    s.sprite(44, 24, build_sprites.side_frame(near=4, far=2))
    s.sprite(58, 24, maps["front_idle"])
    s.sprite(70, 24, build_sprites.FRONT)
    s.render(scale=2).crop((26 * 16, 11 * 28, 80 * 16, 20 * 28)).save(ROOT / "assets" / "badger_auto_vs_hand.png")


if __name__ == "__main__":
    main()
