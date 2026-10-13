#!/usr/bin/env python3
"""Schichtblatt zur Erklärung: alle Querschnitte eines Modells nebeneinander und daneben der Stapel aus drei
Richtungen (wie in der Demo: jede Schicht um 1 px nach oben versetzt und gedreht, Nearest).

    .venv/bin/python styles/sprite-stacking/scripts/preview_slices.py boat_a [--cols 8] [--scale 3]

Farbe = Farbleiter des Materials in Stufe 4 plus Musterversatz (ohne Licht). Ausgabe: assets/preview/slices_<name>.png
"""
import argparse, json, math, pathlib

import numpy as np
from PIL import Image, ImageDraw

ENTRY = pathlib.Path(__file__).resolve().parent.parent
ST = ENTRY / "demo" / "stacks"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--cols", type=int, default=8)
    ap.add_argument("--scale", type=int, default=3)
    a = ap.parse_args()
    cfg = json.loads((ST / "stacks.json").read_text())
    info = cfg["stacks"][a.name]
    atlas = np.asarray(Image.open(ST / f"{a.name}.png").convert("RGBA"))
    ramps = np.asarray(Image.open(ST / "ramps.png").convert("RGB"))
    nx, ny = info["size"]
    L = info["layers"]
    # Schichten in Modellkoordinaten zurücklegen
    vol = np.zeros((L, ny, nx, 3), np.uint8)
    occ = np.zeros((L, ny, nx), bool)
    pv = (-min(c[4] for c in info["cells"] if c), -min(c[5] for c in info["cells"] if c))
    for z, c in enumerate(info["cells"][:L]):
        if not c:
            continue
        ax, ay, w, h, ox, oy = c
        cell = atlas[ay:ay + h, ax:ax + w]
        x0, y0 = int(round(ox + pv[0])), int(round(oy + pv[1]))
        m = cell[..., 3] > 127
        mat = cell[..., 0].astype(int)
        var = (cell[..., 2].astype(int) & 15) - 8
        col = ramps[mat, np.clip(4 + var, 0, 7)]
        sub = vol[z, y0:y0 + h, x0:x0 + w]
        sub[m] = col[m]
        occ[z, y0:y0 + h, x0:x0 + w] |= m
    W, H = vol.shape[2], vol.shape[1]
    s = a.scale
    cols = a.cols
    rows = (L + cols - 1) // cols
    cw, ch = W * s + 6, H * s + 16
    grid = Image.new("RGB", (cols * cw, rows * ch), (24, 26, 44))
    d = ImageDraw.Draw(grid)
    for z in range(L):
        im = np.full((H, W, 3), (40, 44, 70), np.uint8)
        im[occ[z]] = vol[z][occ[z]]
        x, y = (z % cols) * cw, (z // cols) * ch
        grid.paste(Image.fromarray(im).resize((W * s, H * s), Image.NEAREST), (x + 3, y + 13))
        d.text((x + 3, y + 1), f"Schicht {z}", fill=(220, 210, 190))
    # Stapel aus drei Richtungen
    R = int(math.hypot(W, H)) + 4
    views = []
    for ang in (0, 45, 110):
        cv = np.full((R + L + 4, R, 3), (24, 26, 44), np.uint8)
        c, sn = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        yy, xx = np.mgrid[0:cv.shape[0], 0:R]
        for z in range(L):
            gx = xx + 0.5 - R / 2
            gy = yy + 0.5 - (cv.shape[0] - R / 2 - 2) + z
            lx = c * gx + sn * gy + pv[0]
            ly = -sn * gx + c * gy + pv[1]
            ix, iy = np.floor(lx).astype(int), np.floor(ly).astype(int)
            ok = (ix >= 0) & (ix < W) & (iy >= 0) & (iy < H)
            hit = np.zeros(ok.shape, bool)
            hit[ok] = occ[z, iy[ok], ix[ok]]
            cv[hit] = vol[z, iy[hit], ix[hit]]
        views.append(Image.fromarray(cv).resize((R * s, cv.shape[0] * s), Image.NEAREST))
    vw = sum(v.width for v in views) + 12 * len(views)
    out = Image.new("RGB", (max(grid.width, vw), grid.height + views[0].height + 22), (24, 26, 44))
    out.paste(grid, (0, 0))
    x = 0
    d2 = ImageDraw.Draw(out)
    for v, ang in zip(views, (0, 45, 110)):
        out.paste(v, (x, grid.height + 18))
        d2.text((x + 3, grid.height + 4), f"Stapel, {ang} Grad gedreht", fill=(220, 210, 190))
        x += v.width + 12
    p = ENTRY / "assets" / "preview" / f"slices_{a.name}.png"
    out.save(p)
    print(p, out.size)


if __name__ == "__main__":
    main()
