"""KI-Spriteblatt des Dachses (2 Reihen: 6 Laufbilder, 4 Stehbilder) zerlegen und materialtreu verkleinern.

Nur zum Vergleich mit dem Blender-Weg (blender/render_badger.py). Materialien werden hier aus der Farbe geraten
(Oklab-Regeln wie im Eintrag vga-adventure), weil es keinen ID-Pass gibt.

    .venv/bin/python styles/amiga-illustration/scripts/ai_badger.py --height 48 --preview out.png
"""
import argparse
import pathlib
import sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from amiga import oklab  # noqa: E402

STYLE = HERE.parent
MATS = ["FurDark", "FurLight", "Cap", "Brass", "Vest", "Shirt", "Scarf", "Satchel", "Parcel", "Nose", "Eye"]


def runs(mask, min_gap):
    idx = np.flatnonzero(mask)
    out, s, p = [], idx[0], idx[0]
    for i in idx[1:]:
        if i - p > min_gap:
            out.append((s, p + 1))
            s = i
        p = i
    out.append((s, p + 1))
    return out


def extract(path):
    im = Image.open(path).convert("RGBA")
    a = np.asarray(im)
    op = a[..., 3] >= 128
    rows = [r for r in runs(op.any(1), 12) if r[1] - r[0] > 60]
    out = []
    for y0, y1 in rows:
        cols = [c for c in runs(op[y0:y1].any(0), 6) if c[1] - c[0] > 30]
        frames = []
        for x0, x1 in cols:
            sub = op[y0:y1, x0:x1]
            ys = np.flatnonzero(sub.any(1))
            frames.append(im.crop((x0, y0 + ys[0], x1, y0 + ys[-1] + 1)))
        out.append(frames)
    return out


def classify(lab):
    """Material je Rohpixel aus Oklab: rot = Schal, grün = Mütze/Weste, warm hell = Paket, hell = Fell/Hemd,
    braun = Tasche, dunkel = Fell dunkel."""
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    m = np.full(L.shape, MATS.index("FurDark"))
    m[L >= 0.62] = MATS.index("FurLight")
    m[(b > 0.07) & (L > 0.5) & (L < 0.82)] = MATS.index("Parcel")
    m[(a >= 0.03) & (b >= 0.04) & (L < 0.5) & (L >= 0.22)] = MATS.index("Satchel")
    m[(a < -0.01) & (L < 0.62)] = MATS.index("Vest")
    red = (a > 0.07) & (a > 1.1 * b)
    m[red] = MATS.index("Scarf")
    m[(L < 0.2) & ~red] = MATS.index("Eye")
    return m


def cells(frame, height, anchor_x=None):
    """Materialtreue Verkleinerung eines Einzelbilds auf height Zielpixel (Unterkante = Fußsohle)."""
    arr = np.asarray(frame)
    k = height / frame.height
    ys, xs = np.nonzero(arr[..., 3] >= 128)
    lab = oklab(arr[ys, xs, :3].astype(np.float64))
    mat = classify(lab)
    if anchor_x is None:
        top = ys < ys.min() + frame.height * 0.25
        anchor_x = xs[top].mean()
    cw = int(np.ceil(frame.width * k)) + 4
    ax = cw // 2
    X = np.floor((xs + 0.5 - anchor_x) * k + ax).astype(int)
    Y = np.floor((ys + 0.5) * k).astype(int)
    ok = (X >= 0) & (X < cw) & (Y >= 0) & (Y < height)
    X, Y, mat, rgb = X[ok], Y[ok], mat[ok], arr[ys, xs, :3][ok].astype(np.float64)
    cnt = np.zeros((height, cw, len(MATS)))
    np.add.at(cnt, (Y, X, mat), 1)
    csum = np.zeros((height, cw, len(MATS), 3))
    np.add.at(csum, (Y, X, mat), rgb)
    prio = np.ones(len(MATS))
    prio[MATS.index("Eye")] = 1.4
    win = np.argmax(cnt * prio, -1)
    cover = cnt.sum(-1) * k * k
    yy, xx = np.mgrid[0:height, 0:cw]
    n = cnt[yy, xx, win]
    col = csum[yy, xx, win] / np.maximum(n, 1)[..., None]
    win[cover < 0.5] = -1
    return win, col


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", default=str(STYLE / "assets/raw/badger.png"))
    ap.add_argument("--height", type=int, default=48)
    ap.add_argument("--preview")
    a = ap.parse_args()
    rows = extract(a.sheet)
    print("Reihen/Bilder:", [len(r) for r in rows], [[f.size for f in r] for r in rows])
    if a.preview:
        tiles = []
        for r in rows:
            for f in r:
                win, col = cells(f, a.height)
                rgba = np.zeros(win.shape + (4,), np.uint8)
                rgba[win >= 0, :3] = col[win >= 0].astype(np.uint8)
                rgba[win >= 0, 3] = 255
                tiles.append(Image.fromarray(rgba))
        Wt = sum(t.width + 2 for t in tiles)
        sheet = Image.new("RGBA", (Wt, a.height + 4), (60, 60, 90, 255))
        x = 0
        for t in tiles:
            sheet.alpha_composite(t, (x, 2))
            x += t.width + 2
        sheet.resize((sheet.width * 5, sheet.height * 5), Image.NEAREST).save(a.preview)
