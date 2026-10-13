#!/usr/bin/env python3
"""Misst, was die stilisierten Formen (build_harbor_hp.py, Schritt 2) zum Bild beitragen.

    .venv/bin/python styles/handpainted-3d/scripts/compare_shapes.py [--tmp DIR]

Kopiert die Demo (ohne .godot) in ein Temp-Verzeichnis, baut dort den Hafen mit --no-stylize (gleicher
Kaiboden, gleiche Steinflächen und Verdeckung, aber Formen wie in shared/3d), rendert beide Fassungen bei
t = 2,0 s und 4,8 s ohne Oberfläche und gibt den Anteil der Pixel aus, die sich um mehr als 8 Stufen
unterscheiden. Schreibt assets/preview/shapes.png (Häuschen und Fässer: oben ohne, unten mit Formen).
"""
import argparse
import pathlib
import re
import shutil
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw

SD = pathlib.Path(__file__).resolve().parent.parent
ROOT = SD.parent.parent
DEMO = SD / "demo"
TIMES = [2.0, 4.8]


def render(demo, out, t0):
    out.mkdir(parents=True, exist_ok=True)
    cmd = ["godot", "--path", str(demo), "--position", "20000,20000", "--resolution", "1280x720",
           "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", "2", "--", f"--t0={t0}",
           "--no-ui"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    bad = [l for l in (r.stdout + r.stderr).splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR", l)]
    if bad:
        raise SystemExit("Godot-Fehler:\n" + "\n".join(bad[:5]))
    return np.asarray(Image.open(out / "f00000001.png").convert("RGB")).astype(np.int16)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tmp", default=None)
    a = ap.parse_args()
    base = pathlib.Path(a.tmp or tempfile.mkdtemp(prefix="hp3d_shapes_"))
    plain = base / "plain_demo"
    if plain.exists():
        shutil.rmtree(plain)
    shutil.copytree(DEMO, plain, ignore=shutil.ignore_patterns(".godot"))
    r = subprocess.run(["blender", "-b", "--factory-startup", "-P", str(SD / "blender" / "build_harbor_hp.py"), "--",
                        str(ROOT / "shared" / "3d" / "harbor.glb"), str(plain / "models" / "harbor_hp.glb"),
                        "--no-stylize"], capture_output=True, text=True)
    if r.returncode != 0 or "Traceback" in r.stdout + r.stderr:
        raise SystemExit(r.stdout[-2000:] + r.stderr[-2000:])
    for d in (plain, DEMO):
        subprocess.run(["godot", "--headless", "--path", str(d), "--import"], capture_output=True)
    rows = []
    for t0 in TIMES:
        p = render(plain, base / f"plain_{t0}", t0)
        s = render(DEMO, base / f"styl_{t0}", t0)
        d = np.abs(p - s).max(2)
        print(f"t={t0}: Formen ändern {(d > 8).mean() * 100:.1f} % der Pixel (> 8 Stufen), "
              f"mittlere Abweichung {np.abs(p - s).mean():.1f}")
        rows.append((p, s))
    p, s = rows[-1]
    crop = (0, 200, 640, 560)
    sheet = Image.new("RGB", (640, 720))
    for i, (img, txt) in enumerate(((p, "Formen wie shared/3d"), (s, "stilisierte Formen"))):
        sheet.paste(Image.fromarray(img.astype(np.uint8)).crop(crop), (0, 360 * i))
        dr = ImageDraw.Draw(sheet)
        dr.rectangle((0, 360 * i, 8 + 7 * len(txt), 360 * i + 18), fill=(0, 0, 0))
        dr.text((4, 360 * i + 3), txt, fill=(255, 255, 255))
    sheet.save(SD / "assets" / "preview" / "shapes.png")
    print("Temp:", base)


if __name__ == "__main__":
    main()
