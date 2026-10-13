#!/usr/bin/env python3
"""Schätzt Teilung und Versatz des Pseudo-Pixelrasters eines KI-Pixelbildes.

    .venv/bin/python styles/snes-16bit/scripts/gridfind.py bild.png [--min 4 --max 6] [--y0 .. --y1 ..]

Für jede Kandidatenteilung p (0,005er-Schritte) und jeden Versatz o wird die mittlere Kantenenergie (Farbsprung
zwischen Nachbarspalten bzw. -zeilen) auf den Rasterlinien o + k·p durch die mittlere Kantenenergie insgesamt
geteilt. Ein sauberes Raster ergibt Werte weit über 1; Werte um 1,2–1,3 heißen: das Raster ist ungleichmäßig
(hier beim Hafenbild, Teilung schwankt um 4,5–4,9 px).
"""
import argparse
import numpy as np
from PIL import Image


def profile(a, axis):
    d = np.abs(np.diff(a.astype(np.int32), axis=axis)).sum(-1)
    return d.sum(0 if axis == 1 else 1).astype(np.float64)


def find(prof, pmin, pmax):
    best = (0.0, 0.0, 0.0)
    for p in np.arange(pmin, pmax, 0.005):
        for o in np.arange(0, p, 0.1):
            idx = np.floor(np.arange(o, len(prof) - 1, p)).astype(int)
            r = prof[idx].mean() / prof.mean()
            if r > best[0]:
                best = (r, p, o)
    return best


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('img')
    ap.add_argument('--min', type=float, default=4.0)
    ap.add_argument('--max', type=float, default=6.0)
    ap.add_argument('--y0', type=int, default=0)
    ap.add_argument('--y1', type=int, default=0)
    a = ap.parse_args()
    im = np.asarray(Image.open(a.img).convert('RGB'))
    if a.y1:
        im = im[a.y0:a.y1]
    for name, axis, n in (('x', 1, im.shape[1]), ('y', 0, im.shape[0])):
        r, p, o = find(profile(im, axis), a.min, a.max)
        print(f"{name}: Teilung {p:.3f} px, Versatz {o:.1f}, Kantenverhältnis {r:.2f}, ergibt {n / p:.1f} Pixel")
