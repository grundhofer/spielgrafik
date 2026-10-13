#!/usr/bin/env python3
"""Demo mit Forward+, Mobile und Compatibility rendern und Bild 132 (Poster) vergleichen.

    .venv/bin/python styles/minimal-geometrisch/scripts/compare_renderers.py [--keep DIR]

Gibt je Renderer Godot-Fehler, Anteil abweichender Pixel (größte Kanalabweichung > 24 und > 0) und mittlere
Abweichung aus.
"""
import argparse, pathlib, subprocess, sys, tempfile

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent.parent
FRAME = 132
ap = argparse.ArgumentParser()
ap.add_argument("--keep")
a = ap.parse_args()
base = pathlib.Path(a.keep) if a.keep else pathlib.Path(tempfile.mkdtemp())
imgs = {}
for method in ("forward_plus", "mobile", "gl_compatibility"):
    d = base / method
    d.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["godot", "--path", str(HERE / "demo"), "--rendering-method", method, "--position", "20000,20000",
                        "--resolution", "1280x720", "--write-movie", str(d / "f.png"), "--fixed-fps", "30",
                        "--quit-after", str(FRAME + 1)], capture_output=True, text=True, timeout=600)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    imgs[method] = np.asarray(Image.open(d / f"f{FRAME:08d}.png").convert("RGB"), np.int16)
    print(f"{method}: {len(errs)} Fehler" + (f" (erster: {errs[0][:140]})" if errs else ""))
ref = imgs["forward_plus"]
for m in ("mobile", "gl_compatibility"):
    diff = np.abs(imgs[m] - ref).max(2)
    print(f"{m} gegen forward_plus: {(diff > 24).mean() * 100:.3f} % Pixel deutlich anders (> 24 je Kanal), "
          f"{(diff > 0).mean() * 100:.3f} % überhaupt verschieden, "
          f"mittlere Abweichung {np.abs(imgs[m] - ref).mean():.3f}, größte {int(diff.max())}")
