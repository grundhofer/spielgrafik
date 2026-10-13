#!/usr/bin/env python3
"""Requisiten-Sprites für hd-2d aus dem KI-Blatt assets/raw/props.png (Stilreferenz: das Dachs-Blatt).

    .venv/bin/python styles/hd-2d/scripts/build_props.py [--preview out.png]

Oben 7 Requisiten (Fass, Kistenstapel, Kiste, Taurolle, Netz, Grasbüschel, Strandhafer), unten 4 Flugbilder einer
Möwe und eine stehende Möwe. Alle mit demselben Maßstab wie die Vorderansicht des Dachses (SCALE Blattpixel je
Sprite-Pixel), damit Requisiten und Figur dasselbe Pixelraster haben. Verkleinert wird wie beim Dachs (häufigster
Palettenindex im Zellinneren, dunkle Linien bevorzugt), danach der Umriss geschlossen. Die Möwen-Flugbilder werden
am Schnabel ausgerichtet (Flügel verschieben den Schwerpunkt), die übrigen an der Grundlinie, waagrecht mittig.
Ausgaben: assets/props/<name>.png, demo/sprites/<name>.png, assets/props.json (Größe, Anker unten Mitte).
"""
import argparse
import json
import pathlib
import shutil
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from hd2dlib import figures, kmeans, nearest, oklab, oklab_to_rgb, outline_edge  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
NCOL = 32
SCALE = 5.2          # Blattpixel je Sprite-Pixel (wie die Vorderansicht des Dachses: 312 px / 60)
DARK_SHARE = 0.34
NAMES = ["barrel", "crates", "crate", "rope", "net", "grass", "seagrass",
         "gull_0", "gull_1", "gull_2", "gull_3", "gull_stand"]


def reduce(lbl, m, ox, oy, w, h, dark):
    idx = np.full((h, w), -1, np.int64)
    inset = 0.15
    for v in range(h):
        fy0, fy1 = oy + v * SCALE, oy + (v + 1) * SCALE
        for u in range(w):
            fx0, fx1 = ox + u * SCALE, ox + (u + 1) * SCALE
            a0, a1 = max(0, int(round(fy0))), min(m.shape[0], int(round(fy1)))
            b0, b1 = max(0, int(round(fx0))), min(m.shape[1], int(round(fx1)))
            if a1 <= a0 or b1 <= b0 or m[a0:a1, b0:b1].mean() < 0.5:
                continue
            y0 = int(np.floor(fy0 + inset * SCALE)); y1 = max(y0 + 1, int(np.ceil(fy1 - inset * SCALE)))
            x0 = int(np.floor(fx0 + inset * SCALE)); x1 = max(x0 + 1, int(np.ceil(fx1 - inset * SCALE)))
            mm = m[y0:y1, x0:x1]
            if not mm.any():
                mm, y0, y1, x0, x1 = m[a0:a1, b0:b1], a0, a1, b0, b1
            ll = lbl[y0:y1, x0:x1][mm]
            bc = np.bincount(ll, minlength=NCOL)
            dk = bc * dark
            idx[v, u] = int(np.argmax(dk)) if dk.sum() >= DARK_SHARE * len(ll) else int(np.argmax(bc))
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", default="")
    a = ap.parse_args()
    sheet = np.asarray(Image.open(ROOT / "assets" / "raw" / "props.png").convert("RGBA"))
    m = sheet[..., 3] >= 200
    figs = figures(m, row_gap=20, col_gap=6)
    assert len(figs) == 12, len(figs)
    rgb = sheet[..., :3].astype(np.int64)
    lab_all = oklab(rgb[m])
    rng = np.random.default_rng(7)
    cent = kmeans(lab_all[rng.choice(len(lab_all), 80000, replace=False)], NCOL, iters=25, seed=7)
    lbl = np.zeros(m.shape, np.int64)
    lbl[m] = nearest(lab_all, cent)
    pal = np.clip(np.round(oklab_to_rgb(cent)), 0, 255).astype(np.uint8)
    L = cent[:, 0]
    dark = L < 0.25
    outline_c = int(np.argmin(L))
    beak = m & (rgb[..., 0] > 200) & (rgb[..., 1] > 110) & (rgb[..., 1] < 200) & (rgb[..., 2] < 90)

    out_a = ROOT / "assets" / "props"
    out_d = ROOT / "demo" / "sprites"
    out_a.mkdir(parents=True, exist_ok=True)
    out_d.mkdir(parents=True, exist_ok=True)
    meta = {"scale_src": SCALE, "palette": NCOL, "sprites": {}}
    gull_frames = []
    for name, f in zip(NAMES, figs):
        w = int(np.ceil((f["x1"] - f["x0"]) / SCALE)) + 4
        h = int(np.ceil((f["bot"] - f["top"] + 1) / SCALE)) + 3
        if name.startswith("gull_") and name != "gull_stand":
            # Flugbilder: gemeinsamer Rahmen, Schnabel an fester Stelle
            bm = beak[f["top"]:f["bot"] + 1, f["x0"]:f["x1"]]
            ys, xs = np.nonzero(bm)
            bx, by = f["x0"] + xs.mean(), f["top"] + ys.mean()
            gull_frames.append((name, f, bx, by))
            continue
        ox = (f["x0"] + f["x1"]) / 2 - w / 2 * SCALE
        oy = (f["bot"] + 1) - (h - 1) * SCALE           # Grundlinie: unterste deckende Zeile = h − 2
        mf = np.zeros_like(m)
        mf[f["top"]:f["bot"] + 1, f["x0"]:f["x1"]] = m[f["top"]:f["bot"] + 1, f["x0"]:f["x1"]]
        idx = reduce(lbl, mf, ox, oy, w, h, dark)
        idx = close(idx, outline_c, L)
        save(idx, pal, name, out_a, out_d)
        meta["sprites"][name] = {"size": [w, h], "anchor": [w / 2, h - 1]}
    # Möwe im Flug: Rahmen groß genug für alle vier Bilder, Schnabel bei (BX, BY)
    W = int(max(np.ceil(max(bx - f["x0"], 0) / SCALE) for _, f, bx, by in gull_frames)
            + max(np.ceil((f["x1"] - bx) / SCALE) for _, f, bx, by in gull_frames)) + 4
    BXc = int(max(np.ceil((bx - f["x0"]) / SCALE) for _, f, bx, by in gull_frames)) + 2
    up = int(max(np.ceil((by - f["top"]) / SCALE) for _, f, bx, by in gull_frames)) + 2
    dn = int(max(np.ceil((f["bot"] - by) / SCALE) for _, f, bx, by in gull_frames)) + 2
    H = up + dn
    frames = []
    for name, f, bx, by in gull_frames:
        ox = bx - (BXc + 0.5) * SCALE
        oy = by - (up + 0.5) * SCALE
        mf = np.zeros_like(m)                 # nur die eigene Figur (der Rahmen ragt in die Nachbarbilder)
        mf[f["top"]:f["bot"] + 1, f["x0"]:f["x1"]] = m[f["top"]:f["bot"] + 1, f["x0"]:f["x1"]]
        idx = reduce(lbl, mf, ox, oy, W, H, dark)
        frames.append(close(idx, outline_c, L))
    stripv = np.concatenate(frames, axis=1)
    save(stripv, pal, "gull_fly", out_a, out_d)
    meta["sprites"]["gull_fly"] = {"size": [W, H], "frames": 4, "beak": [BXc, up]}
    (ROOT / "assets" / "props.json").write_text(json.dumps(meta, indent=1))
    shutil.copy(ROOT / "assets" / "props.json", out_d / "props.json")
    if a.preview:
        ims = [Image.open(out_a / f"{n}.png") for n in ["barrel", "crates", "crate", "rope", "net", "grass",
                                                         "seagrass", "gull_fly", "gull_stand"]]
        Wp = sum(i.width for i in ims) + 4 * len(ims)
        Hp = max(i.height for i in ims)
        pv = Image.new("RGBA", (Wp, Hp), (60, 70, 90, 255))
        x = 0
        for i in ims:
            pv.alpha_composite(i, (x, Hp - i.height))
            x += i.width + 4
        pv.resize((Wp * 4, Hp * 4), Image.NEAREST).save(a.preview)
    print(json.dumps(meta["sprites"]))


def close(idx, outline_c, L):
    out = idx.copy()
    edge = outline_edge(idx >= 0)
    out[edge & (L[np.clip(idx, 0, None)] >= 0.25)] = outline_c
    return out


def save(idx, pal, name, out_a, out_d):
    a = idx >= 0
    c = pal[np.clip(idx, 0, None)].copy()
    c[~a] = 0
    Image.fromarray(np.dstack([c, a.astype(np.uint8) * 255]), "RGBA").save(out_a / f"{name}.png")
    shutil.copy(out_a / f"{name}.png", out_d / f"{name}.png")


if __name__ == "__main__":
    main()
