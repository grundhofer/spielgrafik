#!/usr/bin/env python3
"""Zerlegt den KI-Laufbogen (assets/raw/walk.png, echter Alphakanal von Codex) in die zehn Figuren und misst sie.

    .venv/bin/python styles/bleistift-skizze/scripts/split_sheet.py [--debug out_dir]

Erkennung über Zusammenhangsflächen der (gedehnten) Alphamaske, Reihenfolge wie im Layout (Reihe, dann x).
Je Figur: Hüllrechteck im Bogen, Sohlenzeile (unterste Zeile mit mindestens 6 deckenden Pixeln) und die
Bodenkontakt-Läufe (zusammenhängende Spalten mit Deckung in den untersten 4 Zeilen über der Sohle).
Ergebnis: assets/sheet_cells.json
"""
import argparse, json, pathlib
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
NAMES = [f"walk_{i}" for i in range(8)] + ["stand", "turn"]


def label(mask):
    """4-Nachbarschafts-Zusammenhang ohne SciPy (Union-Find über Zeilenläufe)."""
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    parent = [0]

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    nxt = 1
    for y in range(h):
        row = mask[y]
        x = 0
        while x < w:
            if not row[x]:
                x += 1
                continue
            x0 = x
            while x < w and row[x]:
                x += 1
            ids = set(lab[y - 1, x0:x][lab[y - 1, x0:x] > 0].tolist()) if y else set()
            if ids:
                roots = sorted({find(i) for i in ids})
                r = roots[0]
                for o in roots[1:]:
                    parent[o] = r
            else:
                parent.append(nxt)
                r = nxt
                nxt += 1
            lab[y, x0:x] = r
    for y in range(h):
        nz = lab[y] > 0
        if nz.any():
            lab[y, nz] = [find(v) for v in lab[y, nz]]
    return lab


def dilate(m, r):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= np.roll(np.roll(m, dy, 0), dx, 1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--debug")
    a = ap.parse_args()
    im = Image.open(ROOT / "assets/raw/walk.png").convert("RGBA")
    A = np.asarray(im)[..., 3]
    mask = A > 24
    lab = label(dilate(mask, 6))
    ids, counts = np.unique(lab[lab > 0], return_counts=True)
    big = [i for i, c in zip(ids, counts) if c > 5000]
    boxes = []
    for i in big:
        ys, xs = np.nonzero((lab == i) & mask)
        boxes.append((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    if len(boxes) != 10:
        raise SystemExit(f"{len(boxes)} Figuren gefunden statt 10: {boxes}")
    boxes.sort(key=lambda b: (b[1] > 512, b[0]))
    cells = []
    for name, (x0, y0, x1, y1) in zip(NAMES, boxes):
        sub = mask[y0:y1, x0:x1]
        rows = np.nonzero(sub.sum(1) >= 6)[0]
        sole = int(rows.max())
        band = sub[max(0, sole - 3):sole + 1].any(0)
        runs, x = [], 0
        while x < band.size:
            if band[x]:
                s = x
                while x < band.size and band[x]:
                    x += 1
                runs.append([x0 + s, x0 + x - 1])
            else:
                x += 1
        cells.append({"name": name, "box": [x0, y0, x1, y1], "w": x1 - x0, "h": y1 - y0,
                      "sole_y": y0 + sole, "height": sole + 1, "contact_runs": runs})
        print(f"{name:7s} box={x0:4d},{y0:4d}-{x1:4d},{y1:4d}  w={x1 - x0:3d} h={sole + 1:3d}  sole_y={y0 + sole}  "
              f"contact={runs}")
    (ROOT / "assets/sheet_cells.json").write_text(json.dumps(cells, indent=1))
    if a.debug:
        out = pathlib.Path(a.debug)
        out.mkdir(parents=True, exist_ok=True)
        for c in cells:
            x0, y0, x1, y1 = c["box"]
            fr = Image.new("RGBA", (x1 - x0, y1 - y0), (255, 255, 255, 255))
            fr.alpha_composite(im.crop((x0, y0, x1, y1)))
            fr.convert("RGB").save(out / f"{c['name']}.png")


if __name__ == "__main__":
    main()
