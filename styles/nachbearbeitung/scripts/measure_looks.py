#!/usr/bin/env python3
"""Wie stark verändert jeder Look das Bild, und wie gleich rechnen die Renderer?

1. Je Look ein Bild bei t (Standard 3,6 s) mit festgehaltenem Look (--look=N, ohne Beschriftung) und ein Rohbild
   ohne Nachbearbeitung (--look=-1). Anteil der Pixel, deren größte Kanalabweichung über 24 liegt, und mittlere
   Abweichung: im ganzen Bild und nur in der Welt (ohne Textbox).
2. Mit --renderers dieselben Bilder mit --rendering-method mobile und gl_compatibility und Vergleich zu Forward+.

    .venv/bin/python styles/nachbearbeitung/scripts/measure_looks.py --tmp <scratch>/looks [--renderers] [--t 3.6]

Schreibt die Werte nach assets/measure_looks.json.
"""
import argparse
import json
import pathlib
import shutil
import subprocess

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent.parent
UI_BOX = (796, 460, 1262, 706)          # Textbox mit Schatten (x0, y0, x1, y1), siehe demo/ui.gd
NAMES = {-1: "ohne", 0: "Bloom", 1: "Filmkorn & Vignette", 2: "Farb-LUT", 3: "CRT", 4: "Halbton",
         5: "Paletten-Reduktion"}


def render(out, t, look, renderer=None):
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("f*"):
        f.unlink()
    cmd = ["godot", "--path", str(HERE / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
           "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", "2"]
    if renderer:
        cmd += ["--rendering-method", renderer]
    # zwei Bilder, das zweite gilt: Im Mobile-Renderer ist im ersten Bild die Schattenkarte der Sonne noch leer
    # (alles liegt im Schatten); Forward+ und Compatibility zeigen das nicht
    cmd += ["--", f"--t0={t - 1 / 30:.5f}", f"--look={look}", "--no-label"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    pngs = sorted(out.glob("f*.png"))
    return np.asarray(Image.open(pngs[-1]).convert("RGB"), dtype=np.int16), errs


def compare(a, b):
    d = np.abs(a - b).max(axis=2)
    world = np.ones(d.shape, bool)
    x0, y0, x1, y1 = UI_BOX
    world[y0:y1, x0:x1] = False
    return {"changed_share": round(float((d > 24).mean()), 4),
            "changed_share_world": round(float((d[world] > 24).mean()), 4),
            "mean_abs": round(float(np.abs(a - b).mean()), 2),
            "mean_abs_world": round(float(np.abs(a - b)[world].mean()), 2),
            "max": int(d.max())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tmp", required=True)
    ap.add_argument("--t", type=float, default=3.6)
    ap.add_argument("--renderers", action="store_true")
    a = ap.parse_args()
    tmp = pathlib.Path(a.tmp)
    subprocess.run(["godot", "--headless", "--path", str(HERE / "demo"), "--import"], capture_output=True)
    res = {"t": a.t, "looks": {}, "renderers": {}}
    imgs = {}
    for look in [-1, 0, 1, 2, 3, 4, 5]:
        imgs[look], errs = render(tmp / "fp", a.t, look)
        if errs:
            print("Fehler:", errs[:3])
    for look in range(6):
        res["looks"][NAMES[look]] = compare(imgs[look], imgs[-1])
        print(f"{NAMES[look]:22s}", res["looks"][NAMES[look]])
    if a.renderers:
        for rm in ["mobile", "gl_compatibility"]:
            res["renderers"][rm] = {}
            for look in [-1, 0, 1, 2, 3, 4, 5]:
                img, errs = render(tmp / rm, a.t, look, rm)
                c = compare(img, imgs[look])
                c["errors"] = errs[:3]
                res["renderers"][rm][NAMES[look]] = c
                print(f"{rm:17s} {NAMES[look]:22s} mittlere Abw. {c['mean_abs']:6.2f}  Anteil >24: "
                      f"{c['changed_share']:.4f}  max {c['max']}" + (f"  FEHLER {errs[:1]}" if errs else ""))
                if look in (-1, 0):
                    Image.fromarray(img.astype(np.uint8)).save(tmp / f"{rm}_{look}.png")
    (HERE / "assets" / "measure_looks.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for d in ["fp", "mobile", "gl_compatibility"]:
        shutil.rmtree(tmp / d, ignore_errors=True)


if __name__ == "__main__":
    main()
