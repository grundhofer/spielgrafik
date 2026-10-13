#!/usr/bin/env python3
"""Die Demo mit Forward+, Mobile und Compatibility aufnehmen und vergleichen (PIPELINE.md → mobile).

    .venv/bin/python styles/blender-rig/scripts/compare_renderers.py --tmp <Temp-Ordner>

Je Renderer ein Lauf mit fester Bildrate bis Bild 143; verglichen werden Bild 50 (Laufen mit Drahtgitter
und Knochen) und Bild 142 (Winken mit Knochen, Poster). Ausgabe: Godot-Fehler und -Warnungen je Renderer,
Anteil der Pixel mit mehr als 8 Stufen Abweichung zum Forward+-Bild, Vergleichsbild
assets/measure/renderers.png (Spalten Forward+, Mobile, Compatibility; Zeilen Bild 50 und 142).
"""
import argparse
import pathlib
import re
import subprocess

import numpy as np
from PIL import Image, ImageDraw

ENTRY = pathlib.Path(__file__).resolve().parents[1]
DEMO = ENTRY / "demo"
FRAMES = [50, 142]
ap = argparse.ArgumentParser()
ap.add_argument("--tmp", required=True)
a = ap.parse_args()
tmp = pathlib.Path(a.tmp)

shots = {}
for method in ("forward_plus", "mobile", "gl_compatibility"):
    d = tmp / method
    d.mkdir(parents=True, exist_ok=True)
    for p in d.glob("*.png"):
        p.unlink()
    r = subprocess.run(["godot", "--rendering-method", method, "--path", str(DEMO), "--position", "20000,20000",
                        "--resolution", "1280x720", "--write-movie", str(d / "f.png"), "--fixed-fps", "30",
                        "--quit-after", str(max(FRAMES) + 1)], capture_output=True, text=True, timeout=600)
    log = r.stdout + r.stderr
    errs = [l.strip() for l in log.splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR|WARNING", l)]
    print(f"{method}: {len(errs)} Fehler/Warnungen" + ("".join(f"\n   {e[:150]}" for e in errs[:6])))
    pngs = sorted(d.glob("f*.png"))
    shots[method] = [np.asarray(Image.open(pngs[f]).convert("RGB"), dtype=np.int16) for f in FRAMES]

for method in ("mobile", "gl_compatibility"):
    for k, f in enumerate(FRAMES):
        diff = np.abs(shots[method][k] - shots["forward_plus"][k]).max(axis=2)
        print(f"{method:17s} Bild {f:3d}: {100 * (diff > 8).mean():5.1f} % der Pixel > 8 Stufen anders,"
              f" mittlere Abweichung {diff.mean():4.1f}")

W, H = 640, 360
sheet = Image.new("RGB", (W * 3, H * len(FRAMES)), "black")
dr = ImageDraw.Draw(sheet)
for c, method in enumerate(("forward_plus", "mobile", "gl_compatibility")):
    for r_, im in enumerate(shots[method]):
        sheet.paste(Image.fromarray(im.astype(np.uint8)).resize((W, H), Image.LANCZOS), (c * W, r_ * H))
        dr.rectangle([c * W, r_ * H, c * W + 230, r_ * H + 18], fill="black")
        dr.text((c * W + 4, r_ * H + 3), f"{method}  Bild {FRAMES[r_]}", fill="white")
out = ENTRY / "assets" / "measure" / "renderers.png"
out.parent.mkdir(parents=True, exist_ok=True)
sheet.save(out)
print("Vergleichsbild:", out)
