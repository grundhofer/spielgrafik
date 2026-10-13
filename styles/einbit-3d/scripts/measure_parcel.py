#!/usr/bin/env python3
"""Wie gut ist das Paket des Dachses zu sehen? Vergleich mit und ohne Paket-Mesh (Schalter --no-parcel).

    .venv/bin/python styles/einbit-3d/scripts/measure_parcel.py [--frames 130,156,179] [--out <Ordner>]

Zählt je Bild (640×360) die Pixel, die sich ändern, wenn das Paket fehlt, und gibt ihren Umriss (Rahmen) aus. Mit --out
wird zusätzlich ein vergrößerter Ausschnitt um den Dachs gespeichert: links mit, rechts ohne Paket, geänderte
Pixel in der Mitte weiß. Mitgezählt wird auch der Schatten des Pakets.
"""
import argparse, pathlib, sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from snap import render  # noqa: E402


def frames_of(args, n):
    pngs, _log, errs = render(n, args)
    for e in errs[:10]:
        print("!!", e)
    return [np.asarray(Image.open(p).convert("L")) for p in pngs]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", default="130,156,179")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    want = [int(f) for f in a.frames.split(",")]
    n = max(want) + 1
    full = frames_of([], n)
    bare = frames_of(["--no-parcel"], n)
    for f in want:
        d = full[f] != bare[f]
        ys, xs = np.nonzero(d)
        if len(ys) == 0:
            print(f"Bild {f}: Paket unsichtbar (0 Pixel)")
            continue
        print(f"Bild {f}: {int(d.sum())} Pixel ändern sich, Rahmen x {xs.min()}–{xs.max()}, y {ys.min()}–{ys.max()}")
        if a.out:
            out = pathlib.Path(a.out)
            out.mkdir(parents=True, exist_ok=True)
            cx, cy = (xs.min() + xs.max()) // 2, (ys.min() + ys.max()) // 2
            box = (max(cx - 60, 0), max(cy - 70, 0), max(cx - 60, 0) + 120, max(cy - 70, 0) + 140)
            tiles = [Image.fromarray(full[f]).crop(box), Image.fromarray((d * 255).astype(np.uint8)).crop(box),
                     Image.fromarray(bare[f]).crop(box)]
            im = Image.new("L", (380, 140), 128)
            for i, t in enumerate(tiles):
                im.paste(t, (i * 130, 0))
            im.resize((1520, 560), Image.NEAREST).save(out / f"parcel_f{f:03d}.png")
