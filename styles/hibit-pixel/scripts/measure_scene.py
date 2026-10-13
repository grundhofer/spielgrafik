#!/usr/bin/env python3
"""Messwerte für style.json: Farbzahl je Bild und Wirkung von Licht, Normal Maps, Lichtstufen und Renderern.

    .venv/bin/python styles/hibit-pixel/scripts/measure_scene.py [--frames 0,143,144,151] [--renderers]

Nimmt die Demo in 640×360 auf (scripts/probe.py) – normal, --nolight, --flatnormals, --smooth – und misst:
  * Farben je Bild (ganzes Bild mit Oberfläche) in den gewählten Bildern, dazu Spanne über alle 180 Bilder.
  * Szene = Zeilen 0–277 ohne Ortsschild (x ≥ 440, y < 32); „geändert“ = ein Kanal weicht um mehr als 8 ab.
  * --nolight: Anteil geänderter Szenenpixel (= beleuchtete Fläche).
  * --flatnormals: Anteil geänderter Pixel in der beleuchteten Fläche und mittlere Abweichung dort.
  * --smooth: Anteil geänderter Szenenpixel und Farbzahl ohne Lichtstufen.
  * --renderers: mobile und gl_compatibility gegen Forward+ in den gewählten Bildern.
"""
import argparse, glob, json, pathlib, sys, tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import probe


def load_all(td):
    return [np.asarray(Image.open(p).convert("RGB")).astype(np.int16) for p in sorted(glob.glob(f"{td}/all/f*.png"))]


def ncolors(im):
    flat = im.astype(np.int32)
    return int(np.unique((flat[..., 0] << 16) | (flat[..., 1] << 8) | flat[..., 2]).size)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", default="0,143,144,151")
    ap.add_argument("--renderers", action="store_true")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    frames = [int(x) for x in a.frames.split(",")]
    scene = np.zeros((360, 640), bool)
    scene[:278] = True
    scene[:32, 440:] = False
    res = {"frames": frames}
    runs = {}
    for name, args in (("normal", ""), ("nolight", "--nolight"), ("flat", "--flatnormals"), ("smooth", "--smooth")):
        with tempfile.TemporaryDirectory(prefix="hibit-pixel-") as td:
            n, bad = probe.run(td, 6.0, 30, args, keep=True)
            runs[name] = load_all(td)
            res[f"{name}_godot_messages"] = len(bad)
    nrm = runs["normal"]
    res["colors"] = {i: ncolors(nrm[i]) for i in frames}
    allc = [ncolors(f) for f in nrm]
    res["colors_all"] = {"min": min(allc), "min_frame": int(np.argmin(allc)), "max": max(allc),
                         "max_frame": int(np.argmax(allc))}
    res["colors_smooth"] = {i: ncolors(runs["smooth"][i]) for i in frames}
    for i in frames:
        base = nrm[i]
        dl = np.abs(base - runs["nolight"][i]).max(-1) > 8
        lit = dl & scene
        df = np.abs(base - runs["flat"][i]).max(-1)
        ds = np.abs(base - runs["smooth"][i]).max(-1) > 8
        res[f"f{i}"] = {
            "nolight_changed_scene": round(float(lit.sum() / scene.sum()), 4),
            "flat_changed_in_lit": round(float((df[lit] > 8).mean()), 3),
            "flat_mean_dev_in_lit": round(float(df[lit].mean()), 1),
            "smooth_changed_scene": round(float((ds & scene).sum() / scene.sum()), 4),
        }
    if a.renderers:
        for method in ("mobile", "gl_compatibility"):
            with tempfile.TemporaryDirectory(prefix="hibit-pixel-") as td:
                n, bad = probe.run(td, 6.0, 30, "", method=method, keep=True)
                other = load_all(td)
            out = {"godot_messages": len(bad)}
            for i in frames:
                d = np.abs(nrm[i] - other[i]).max(-1)
                out[f"f{i}"] = {"identical": bool((d == 0).all()), "gt8": round(float((d > 8).mean()), 5),
                                "changed": round(float((d > 0).mean()), 5),
                                "le2_of_changed": round(float((d[d > 0] <= 2).mean()), 3) if (d > 0).any() else 1.0}
            res[method] = out
    print(json.dumps(res, indent=1))
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
