#!/usr/bin/env python3
"""Vergleichsschalter: Wie viel trägt jeder Baustein zum Bild bei? (PIPELINE.md -> Blender/Effekte messen)

    .venv/bin/python styles/einbit-3d/scripts/compare_switches.py [--frames 30,156]

Rendert die Demo ohne Schalter und mit je einem Schalter (main.gd) und gibt für die gewählten Bilder den
Anteil der Pixel an, die sich gegenüber der vollen Fassung ändern (nur Szene, ohne Ortsschild und Dialog).
Schreibt assets/preview/switches_fNNN.png (Ausschnitte nebeneinander, 640×360 je Feld) und assets/preview/
gray_fNNN.png (Tonwerte vor dem Rastern).
"""
import argparse, pathlib, shutil, sys

import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from snap import render  # noqa: E402

VARIANTS = [
    ("voll", []),
    ("ohne Raster (Schwelle 0,5)", ["--nodither"]),
    ("nur Bayer", ["--bayer"]),
    ("nur Blue Noise", ["--bluenoise"]),
    ("ohne Linien", ["--no-lines"]),
    ("ohne Materiallinien", ["--no-ids"]),
    ("ohne Figurenrand", ["--no-figure-outline"]),
]

ap = argparse.ArgumentParser()
ap.add_argument("--frames", default="30,156")
a = ap.parse_args()
frames = [int(x) for x in a.frames.split(",")]
out = HERE.parent / "assets" / "preview"
out.mkdir(parents=True, exist_ok=True)


def scene_mask(shape):
    m = np.ones(shape, bool)
    m[0:44, 0:228] = False            # Ortsschild
    m[240:360, 296:640] = False       # Dialogkasten mit Schatten
    return m


imgs = {}
for name, args in VARIANTS + [("grau", ["--gray"])]:
    pngs, log, errs = render(max(frames) + 1, args)
    for e in errs[:3]:
        print("!!", name, e)
    imgs[name] = {f: Image.open(pngs[f]).convert("RGB") for f in frames}
    shutil.rmtree(pngs[0].parent, ignore_errors=True)

for f in frames:
    full = np.asarray(imgs["voll"][f])
    m = scene_mask(full.shape[:2])
    print(f"Bild {f} ({f / 30:.1f} s):")
    for name, _ in VARIANTS[1:]:
        other = np.asarray(imgs[name][f])
        share = float((np.any(other != full, axis=2) & m).sum() / m.sum())
        print(f"  {name:28s} {share * 100:5.1f} % der Pixel anders")
    cols = 4
    rows = (len(VARIANTS) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 644, rows * 380), (200, 40, 40))
    d = ImageDraw.Draw(sheet)
    for k, (name, _) in enumerate(VARIANTS):
        x, y = (k % cols) * 644, (k // cols) * 380
        sheet.paste(imgs[name][f], (x, y + 18))
        d.text((x + 4, y + 3), name, fill="white")
    sheet.save(out / f"switches_f{f:03d}.png")
    imgs["grau"][f].save(out / f"gray_f{f:03d}.png")
    print("  ->", out / f"switches_f{f:03d}.png")
