#!/usr/bin/env python3
"""Wie stark flackert die Laterne im Bild? Helligkeit von Glas, Pfahl und Umgebung je Bild.

Rendert die Nahkamera (ab t0 = 0,6 s, Standard 162 Bilder bis 6 s) ohne Nachbearbeitung, ohne Beschriftung und
ohne Textbox, einmal mit Flackern und einmal mit --no-flicker (zeigt, was andere Lichter wie der kreisende
Leuchtturm-Spot allein bewirken). Je Bereich die mittlere Helligkeit (Rec. 709 auf den sRGB-Werten) und die
Schwankung (max − min) / max sowie (p95 − p5) / Mittel.

Bereiche (Bildpunkte, Nahkamera, siehe main.gd CAM_*): Glas 1020–1052 × 372–408; Pfahl 1078–1100 × 318–470;
Umgebung = Rechteck 960–1160 × 300–470 ohne die Laterne (1010–1062 × 330–425); Boden unter der Laterne
1000–1180 × 470–560 (liegt im Spiel hinter der Textbox).

    .venv/bin/python styles/nachbearbeitung/scripts/measure_lantern.py --tmp <scratch>/lantern

Schreibt die Werte nach assets/measure_lantern.json.
"""
import argparse
import json
import pathlib
import shutil
import subprocess

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent.parent
REGIONS = {"Glas": (1020, 372, 1052, 408), "Pfahl": (1078, 318, 1100, 470),
           "Umgebung": (960, 300, 1160, 470), "Boden (hinter Textbox)": (1000, 470, 1180, 560)}
HOLE = (1010, 330, 1062, 425)


def render(out, t0, frames, extra):
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("f*"):
        f.unlink()
    cmd = ["godot", "--path", str(HERE / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
           "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", str(frames),
           "--", f"--t0={t0}", "--look=-1", "--no-label", "--no-ui", "--cam=nah"] + extra
    r = subprocess.run(cmd, capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    return sorted(out.glob("f*.png")), errs


def series(pngs):
    res = {k: [] for k in REGIONS}
    for p in pngs:
        im = np.asarray(Image.open(p).convert("RGB"), dtype=np.float64)
        lum = 0.2126 * im[..., 0] + 0.7152 * im[..., 1] + 0.0722 * im[..., 2]
        for k, (x0, y0, x1, y1) in REGIONS.items():
            m = np.zeros(lum.shape, bool)
            m[y0:y1, x0:x1] = True
            if k == "Umgebung":
                hx0, hy0, hx1, hy1 = HOLE
                m[hy0:hy1, hx0:hx1] = False
            res[k].append(float(lum[m].mean()))
    return res


def stats(v):
    v = np.array(v)
    return {"mittel": round(float(v.mean()), 1), "min": round(float(v.min()), 1), "max": round(float(v.max()), 1),
            "spanne_rel": round(float((v.max() - v.min()) / v.max()), 3),
            "p5_p95_rel": round(float((np.percentile(v, 95) - np.percentile(v, 5)) / v.mean()), 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tmp", required=True)
    ap.add_argument("--t0", type=float, default=0.6)
    ap.add_argument("--frames", type=int, default=162)
    a = ap.parse_args()
    tmp = pathlib.Path(a.tmp)
    subprocess.run(["godot", "--headless", "--path", str(HERE / "demo"), "--import"], capture_output=True)
    out = {"t0": a.t0, "frames": a.frames, "regions": REGIONS}
    for name, extra in [("flackern", []), ("ohne_flackern", ["--no-flicker"])]:
        pngs, errs = render(tmp / name, a.t0, a.frames, extra)
        if errs:
            print("Fehler:", errs[:3])
        s = series(pngs)
        out[name] = {k: stats(v) for k, v in s.items()}
        if name == "flackern":
            out["verlauf_glas"] = [round(x, 1) for x in s["Glas"]]
        for k, st in out[name].items():
            print(f"{name:14s} {k:24s} {st}")
        shutil.rmtree(tmp / name, ignore_errors=True)
    (HERE / "assets" / "measure_lantern.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
