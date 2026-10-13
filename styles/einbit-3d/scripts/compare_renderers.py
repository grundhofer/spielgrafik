#!/usr/bin/env python3
"""Probeläufe mit den Renderern Mobile und Compatibility (PIPELINE.md -> Selbstprüfung, Punkt 5).

    .venv/bin/python styles/einbit-3d/scripts/compare_renderers.py [--frames 30,156]

Rendert die gewählten Bilder mit Forward+, Mobile und Compatibility (main.gd setzt außerhalb von Forward+ den
Nachbearbeitungs-Shader ohne Normalenpuffer ein), gibt Godot-Fehler und den Anteil abweichender Pixel gegenüber
Forward+ aus (nur Szene, ohne Ortsschild und Dialog) und schreibt assets/preview/renderers.png
(Spalten Forward+, Mobile, Compatibility; Zeilen = Bilder).
"""
import argparse, pathlib, shutil, sys

import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from snap import render  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--frames", default="30,156")
a = ap.parse_args()
frames = [int(x) for x in a.frames.split(",")]
names = ["forward_plus", "mobile", "gl_compatibility"]
imgs = {}
for r in names:
    pngs, log, errs = render(max(frames) + 1, [], renderer=r)
    print(f"{r}: {len(pngs)} Bilder, {len(errs)} Fehler/Warnungen" + (f" (erste: {errs[0][:140]})" if errs else ""))
    imgs[r] = {f: Image.open(pngs[f]).convert("RGB") for f in frames}
    shutil.rmtree(pngs[0].parent, ignore_errors=True)

mask = np.ones((360, 640), bool)
mask[0:44, 0:228] = False
mask[240:360, 296:640] = False
sheet = Image.new("RGB", (3 * 644, len(frames) * 382), (200, 40, 40))
d = ImageDraw.Draw(sheet)
for row, f in enumerate(frames):
    base = np.asarray(imgs["forward_plus"][f])
    for col, r in enumerate(names):
        im = np.asarray(imgs[r][f])
        share = float((np.any(im != base, axis=2) & mask).sum() / mask.sum())
        if r != "forward_plus":
            print(f"  Bild {f}: {r} weicht in {share * 100:.1f} % der Pixel von Forward+ ab")
        sheet.paste(imgs[r][f], (col * 644, row * 382 + 20))
        d.text((col * 644 + 4, row * 382 + 4), f"{r}, Bild {f}", fill="white")
out = HERE.parent / "assets" / "preview" / "renderers.png"
sheet.save(out)
print("->", out)
