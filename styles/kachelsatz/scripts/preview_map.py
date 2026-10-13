#!/usr/bin/env python3
"""Setzt die Karte wie die Godot-Demo zusammen (Dual-Grid, Ebenen übereinander), ohne Godot.

    .venv/bin/python styles/kachelsatz/scripts/preview_map.py [--frame 0] [--grid] [--out datei.png]

Dient als Referenz: scripts/check_tiles.py vergleicht das Godot-Bild der Kachelebenen mit diesem Ergebnis.
"""
import argparse, json, pathlib

import numpy as np
from PIL import Image

ENTRY = pathlib.Path(__file__).resolve().parent.parent
T = 16


def load_map(path):
    rows = [l.rstrip("\n") for l in open(path, encoding="utf-8") if l.strip() and not l.startswith("#")]
    return rows


def cell(rows, x, y):
    y = min(max(y, 0), len(rows) - 1)
    x = min(max(x, 0), len(rows[0]) - 1)
    return rows[y][x]


def hash2(x, y, salt=0):
    h = (x * 374761393 + y * 668265263 + salt * 2246822519) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return (h ^ (h >> 16)) / 0xFFFFFFFF


SALT = {"water": 1, "sand": 2, "grass": 3, "stone": 4, "jetty": 5}


def pick(cands, h):
    """Variante nach Wahrscheinlichkeit, deterministisch über den Zellen-Hash (wie main.gd)."""
    cands = sorted(cands, key=lambda t: t["atlas"][1])
    total = sum(t["probability"] for t in cands)
    acc = 0.0
    for t in cands:
        acc += t["probability"]
        if h * total < acc:
            return t
    return cands[-1]


def compose(rows, desc, tiledir, frame=0, layers=None, view=(426, 240), frames=None, origin=(8, 8)):
    """frames: optional je Ebene eigenes Animationsbild; origin: Ausschnitt im Bild der Anzeigekacheln
    ((8, 8) = Welt ab 0/0; die Demo zeigt die Welt um 8 px nach unten versetzt, also (8, 0))."""
    W, H = len(rows[0]), len(rows)
    img = np.zeros(((H + 1) * T, (W + 1) * T, 4), np.float64)
    for lname in (layers or desc["order"]):
        L = desc["layers"][lname]
        atlas = np.asarray(Image.open(tiledir / L["texture"]).convert("RGBA")).astype(np.float64) / 255
        lookup = {}
        for t in L["tiles"]:
            lookup.setdefault(tuple(t["corners"]), []).append(t)
        cov = L["covers"]
        for dy in range(H + 1):
            for dx in range(W + 1):
                cs = [cell(rows, dx - 1, dy - 1), cell(rows, dx, dy - 1), cell(rows, dx - 1, dy), cell(rows, dx, dy)]
                key = tuple(int(c in cov or cov == ["*"]) for c in cs)
                if key not in lookup:
                    continue
                t = pick(lookup[key], hash2(dx, dy, SALT[lname]))
                f = (frames.get(lname, frame) if frames else frame) % t["frames"]
                ax, ay = t["atlas"]
                src = atlas[ay * T:(ay + 1) * T, (ax + f) * T:(ax + f + 1) * T]
                y0, x0 = dy * T, dx * T
                dst = img[y0:y0 + T, x0:x0 + T]
                a = src[..., 3:4]
                dst[..., :3] = src[..., :3] * a + dst[..., :3] * (1 - a)
                dst[..., 3:4] = a + dst[..., 3:4] * (1 - a)
    # Anzeige-Ebene liegt um (-8, -8) versetzt
    out = img[origin[1]:origin[1] + view[1], origin[0]:origin[0] + view[0]]
    return (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", type=int, default=0)
    ap.add_argument("--grid", action="store_true")
    ap.add_argument("--zoom", type=int, default=3)
    ap.add_argument("--out", default=str(ENTRY / "assets" / "map_preview.png"))
    a = ap.parse_args()
    tiledir = ENTRY / "assets" / "tiles"
    desc = json.loads((tiledir / "tiles.json").read_text())
    rows = load_map(ENTRY / "demo" / "map" / "harbour.txt")
    im = compose(rows, desc, tiledir, a.frame)
    pil = Image.fromarray(im).convert("RGB").resize((im.shape[1] * a.zoom, im.shape[0] * a.zoom), Image.NEAREST)
    if a.grid:
        px = pil.load()
        for y in range(pil.height):
            for x in range(pil.width):
                if (x // a.zoom) % T == 0 and x % a.zoom == 0 or (y // a.zoom) % T == 0 and y % a.zoom == 0:
                    px[x, y] = (255, 0, 255)
    pil.save(a.out)
    print(a.out)


if __name__ == "__main__":
    main()
