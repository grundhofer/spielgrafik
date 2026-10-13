#!/usr/bin/env python3
"""Renderer und Kosten vergleichen (PIPELINE.md → Selbstprüfung, Punkt 5).

    .venv/bin/python styles/vertex-animation/scripts/compare_renderers.py [--tmp DIR]

1. Bild 90 (t = 3,0 s) mit Forward+, Mobile und Compatibility rendern (--write-movie, 30 fps) und die
   Abweichung zu Forward+ messen (mittlere Abweichung je Kanal, Anteil Pixel mit > 24 Stufen Abweichung).
   Verkleinerte Gegenüberstellung: assets/measure/renderers.jpg.
2. Bildzeit ohne V-Sync (--disable-vsync --max-fps 0, 1280×720, 600 Bilder) für die Varianten der Demo:
   volles feines Gitter, feines Gitter ohne Wellen (--variant=flat), Gerstner auf dem groben Original-Gitter
   (--variant=coarse); dazu Mobile und Compatibility. main.gd --perf druckt Median der Bildzeit,
   Skriptzeit je Bild (Schwimmer, Möwen, Dachs), Dreiecke und Draw-Calls.
Ausgabe: assets/measure/perf_report.txt
"""
import argparse
import pathlib
import subprocess
import tempfile

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[3]
DEMO = ROOT / "styles" / "vertex-animation" / "demo"
OUT = ROOT / "styles" / "vertex-animation" / "assets" / "measure"
ap = argparse.ArgumentParser()
ap.add_argument("--tmp", default="")
a = ap.parse_args()
tmp = pathlib.Path(a.tmp) if a.tmp else pathlib.Path(tempfile.mkdtemp(prefix="vertex-animation-renderers-"))
OUT.mkdir(parents=True, exist_ok=True)
lines = []


def run(args, timeout=600):
    r = subprocess.run(["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720"] + args,
                       capture_output=True, text=True, timeout=timeout)
    return r.stdout + r.stderr


imgs = {}
for r in ("forward_plus", "mobile", "gl_compatibility"):
    d = tmp / r
    d.mkdir(parents=True, exist_ok=True)
    for p in d.glob("f*.png"):
        p.unlink()
    log = run(["--rendering-method", r, "--write-movie", str(d / "f.png"), "--fixed-fps", "30", "--quit-after", "91"])
    warn = sorted({l.strip() for l in log.splitlines() if "WARNING" in l or "ERROR" in l})
    imgs[r] = Image.open(d / "f00000090.png").convert("RGB")
    if warn:
        lines.append(f"{r}: " + " | ".join(warn))
ref = np.asarray(imgs["forward_plus"], float)
for r in ("mobile", "gl_compatibility"):
    diff = np.abs(np.asarray(imgs[r], float) - ref)
    lines.append(f"{r} gegen Forward+ (Bild 90): mittlere Abweichung {diff.mean():.2f}, "
                 f"Anteil > 24 Stufen {(diff.max(axis=2) > 24).mean():.3f}")
sheet = Image.new("RGB", (960, 180))
for k, r in enumerate(("forward_plus", "mobile", "gl_compatibility")):
    sheet.paste(imgs[r].resize((320, 180), Image.LANCZOS), (k * 320, 0))
sheet.save(OUT / "renderers.jpg", quality=82)

for label, args in (("Forward+ voll", []), ("Forward+ flach (ohne Wellen)", ["--variant=flat"]),
                    ("Forward+ grobes Gitter", ["--variant=coarse"]),
                    ("Mobile voll", ["--rendering-method", "mobile"]),
                    ("Compatibility voll", ["--rendering-method", "gl_compatibility"])):
    extra = [x for x in args if x.startswith("--variant")]
    rend = [x for x in args if not x.startswith("--variant")]
    log = run(rend + ["--disable-vsync", "--max-fps", "0", "--quit-after", "600", "--", "--perf"] + extra)
    perf = [l for l in log.splitlines() if l.startswith("PERF")]
    lines.append(f"{label}: " + " / ".join(perf))
txt = "\n".join(lines)
print(txt)
(OUT / "perf_report.txt").write_text(txt + "\n")
