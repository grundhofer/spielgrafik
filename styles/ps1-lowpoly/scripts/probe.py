#!/usr/bin/env python3
"""Nimmt die Demo verlustfrei in Basisauflösung (320×240) auf und speichert ausgewählte Bilder und Ausschnitte.

    .venv/bin/python styles/ps1-lowpoly/scripts/probe.py OUTDIR [--frames 0,60,108,170] [--crop x,y,w,h] [--scale 4]
        [--user "--no-snap --no-affine --no-dither"]   (Vergleichsschalter von main.gd)

Misst außerdem die Farbzahl je Bild (15-Bit-Prüfung: alle Kanäle müssen Vielfache von 255/31 sein) und
den Anteil der Pixel, die sich zwischen zwei aufeinanderfolgenden Bildern ändern.
"""
import argparse, pathlib, subprocess, sys, tempfile

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent.parent

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--frames", default="0,60,108,170")
ap.add_argument("--crop", default="")
ap.add_argument("--scale", type=int, default=4)
ap.add_argument("--user", default="", help="Schalter für main.gd, z. B. '--no-snap --no-affine'")
a = ap.parse_args()
out = pathlib.Path(a.out)
out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="ps1-lowpoly-") as td:
    r = subprocess.run(["godot", "--path", str(HERE / "demo"), "--position", "20000,20000", "--write-movie",
                        str(pathlib.Path(td) / "f.png"), "--fixed-fps", "30", "--quit-after", "180"] + (["--"] + a.user.split() if a.user else []),
                       capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    if errs:
        print("\n".join(errs[:10]))
    pngs = sorted(pathlib.Path(td).glob("f*.png"))
    print(len(pngs), "Bilder", Image.open(pngs[0]).size)
    allowed = set(round(i * 255 / 31) for i in range(32))
    for i in [int(x) for x in a.frames.split(",")]:
        im = Image.open(pngs[i]).convert("RGB")
        arr = np.asarray(im)
        cols = len(np.unique(arr.reshape(-1, 3), axis=0))
        ok15 = set(np.unique(arr).tolist()) <= allowed
        nxt = np.asarray(Image.open(pngs[min(i + 1, len(pngs) - 1)]).convert("RGB"))
        ch = float((np.abs(nxt.astype(int) - arr.astype(int)).max(2) > 0).mean())
        print(f"Bild {i}: {cols} Farben, 15 Bit: {ok15}, geändert zum nächsten Bild: {ch:.3f}")
        im.save(out / f"f{i:03d}.png")
        if a.crop:
            x, y, w, h = map(int, a.crop.split(","))
            im.crop((x, y, x + w, y + h)).resize((w * a.scale, h * a.scale), Image.NEAREST).save(out / f"c{i:03d}.png")
        im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(out / f"x{i:03d}.png")
