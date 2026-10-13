#!/usr/bin/env python3
"""16-Farben-Palette aus einem Bild der Szene (k-means in OKLab, feste Seed) für den Look Paletten-Reduktion.

    .venv/bin/python styles/nachbearbeitung/scripts/make_palette.py frame.png [--colors 16] \
        [--without-figure frame_ohne_dachs.png --figure-weight 12] [--ids frame_ids.png]

Schreibt assets/palette16.png und demo/textures/palette16.png (N×1 px, nach Helligkeit sortiert) und gibt die
Farben als Hex aus. Die Ränder der Farbwolke werden betont: Nach dem k-means ersetzt das Skript die hellste und die
dunkelste Mitte durch das 99,5- bzw. 0,5-Perzentil der Helligkeit, sonst fehlen Lampenlicht und tiefe Schatten.
Mit --without-figure (dasselbe Bild ohne Dachs) zählen die Pixel der Figur figure-weight-fach: Die Figur ist klein,
ihre Farben (roter Schal, grüne Weste) gingen im k-means sonst unter.
Mit --ids (dasselbe Bild mit main.gd --badger-ids: Mütze grün, Weste blau, Rest magenta) werden zwei Mitten fest
vorgegeben: der Median (OKLab) der Mützen- und der Westenpixel im Bild. Im Abendlicht sind Mütze und Weste
olivbraun (OKLab a ≈ 0,02 statt 0,04–0,07 der Umgebung); ohne eigene Mitte fielen sie auf ein rötliches Braun und
verschmolzen mit Gesicht und Fell. Die übrigen Mitten sucht der k-means, die festen bleiben stehen.
"""
import argparse
import pathlib

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent.parent


def srgb_to_lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
               [0.2119034982, 0.6806995451, 0.1073969566],
               [0.0883024619, 0.2817188376, 0.6299787005]])
M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
               [1.9779984951, -2.4285922050, 0.4505937099],
               [0.0259040371, 0.7827717662, -0.8086757660]])


def to_lab(rgb):
    lms = np.cbrt(srgb_to_lin(rgb) @ M1.T)
    return lms @ M2.T


def from_lab(lab):
    lms = lab @ np.linalg.inv(M2).T
    return lin_to_srgb((lms ** 3) @ np.linalg.inv(M1).T)


def kmeans(x, k, w, iters=40, seed=20261013, fixed=()):
    """k-means++ (gewichtet); die Mitten in fixed stehen fest und zählen zu den k."""
    rng = np.random.default_rng(seed)
    nf = len(fixed)
    c = [np.asarray(f, float) for f in fixed]
    if not c:
        c = [x[rng.choice(len(x), p=w / w.sum())]]
    while len(c) < k:
        d = np.min(((x[:, None, :] - np.array(c)[None]) ** 2).sum(-1), axis=1) * w
        c.append(x[rng.choice(len(x), p=d / d.sum())])
    c = np.array(c)
    for _ in range(iters):
        lab = ((x[:, None, :] - c[None]) ** 2).sum(-1).argmin(1)
        for j in range(nf, k):
            m = lab == j
            if np.any(m):
                c[j] = (x[m] * w[m, None]).sum(0) / w[m].sum()
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--colors", type=int, default=16)
    ap.add_argument("--sample", type=int, default=40000)
    ap.add_argument("--without-figure", default=None)
    ap.add_argument("--figure-weight", type=float, default=12.0)
    ap.add_argument("--ids", default=None, help="Bild mit --badger-ids: Mütze grün, Weste blau -> feste Mitten")
    ap.add_argument("--green-shift", type=float, default=0.0,
                    help="OKLab-a der festen Mitten um diesen Wert senken (Richtung Grün), z. B. 0.03")
    a = ap.parse_args()
    img = np.asarray(Image.open(a.image).convert("RGB"), dtype=np.float64) / 255.0
    px = img.reshape(-1, 3)
    wt = np.ones(len(px))
    if a.without_figure:
        nob = np.asarray(Image.open(a.without_figure).convert("RGB"), dtype=np.float64) / 255.0
        fig = (np.abs(img - nob).max(-1) > 0.04).reshape(-1)
        wt[fig] = a.figure_weight
        print(f"Figur: {fig.sum()} px, Gewicht {a.figure_weight}")
    fixed = []
    if a.ids:
        if not a.without_figure:
            ap.error("--ids braucht --without-figure (nur Pixel der Figur zählen, der Himmel ist auch blau)")
        ids = np.asarray(Image.open(a.ids).convert("RGB"), dtype=np.int16).reshape(-1, 3)
        r, g, b = ids[:, 0], ids[:, 1], ids[:, 2]
        for name, m in [("Mütze", fig & (g - r > 40) & (g - b > 40)), ("Weste", fig & (b - r > 40) & (b - g > 40))]:
            med = np.median(to_lab(px[m]), axis=0)
            med[1] -= a.green_shift
            fixed.append(med)
            rgb_m = (np.clip(from_lab(med[None]), 0, 1)[0] * 255 + 0.5).astype(int)
            print(f"{name}: {m.sum()} px, feste Mitte OKLab {np.round(med, 3)} = #%02x%02x%02x" % tuple(rgb_m))
    rng = np.random.default_rng(1)
    idx = rng.choice(len(px), size=min(a.sample, len(px)), replace=False)
    px, wt = px[idx], wt[idx]
    lab = to_lab(px)
    # Farbabstand wie im Shader: a und b stärker gewichtet
    w = np.array([1.0, 1.4, 1.4])
    cent = kmeans(lab * w, a.colors, wt, fixed=[f * w for f in fixed]) / w
    order = np.argsort(cent[:, 0])
    cent = cent[order]
    lo, hi = np.percentile(lab[:, 0], [0.5, 99.5])
    cent[0, 0] = min(cent[0, 0], lo)
    cent[-1] = lab[lab[:, 0] >= hi].mean(0)
    rgb = np.clip(from_lab(cent), 0, 1)
    out = (rgb * 255 + 0.5).astype(np.uint8)[None]
    for o in [HERE / "assets" / "palette16.png", HERE / "demo" / "textures" / "palette16.png"]:
        o.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(out, "RGB").save(o)
        print("geschrieben:", o)
    print(" ".join("#%02x%02x%02x" % tuple(c) for c in out[0]))


if __name__ == "__main__":
    main()
