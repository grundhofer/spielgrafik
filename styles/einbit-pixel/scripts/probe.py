#!/usr/bin/env python3
"""Prüfläufe der Demo in ein Temp-Verzeichnis (Basisauflösung 400×240) mit Vergleichen:

  * Farben je Bild (müssen genau 2 sein: Tinte und Papier)
  * Vergleichsschalter --fx=1 (ohne Licht, Rauch, Funkeln): Anteil geänderter Pixel je Bild
  * Dauerlauf ab --t0=30 (Wasser, Rauch, Leuchtfeuer nach 30 s)
  * Renderer Mobile und Compatibility gegen Forward+ (Anteil abweichender Pixel)

    .venv/bin/python styles/einbit-pixel/scripts/probe.py [--out media/probe.json] [--keep <ordner>]
"""
import argparse, json, pathlib, shutil, subprocess, tempfile

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"


def record(td, name, frames, extra=(), user=()):
    d = pathlib.Path(td) / name
    d.mkdir()
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", *extra, "--write-movie", str(d / "f.png"),
           "--fixed-fps", "30", "--quit-after", str(frames)]
    if user:
        cmd += ["--", *user]
    r = subprocess.run(cmd, capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    return d, errs


def load(d, n):
    return np.asarray(Image.open(d / f"f{n:08d}.png").convert("RGB")).astype(int)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "media" / "probe.json"))
    ap.add_argument("--keep")
    a = ap.parse_args()
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    res = {}
    with tempfile.TemporaryDirectory() as td:
        base, e0 = record(td, "base", 180)
        nofx, e1 = record(td, "nofx", 180, user=("--fx=1",))
        late, e2 = record(td, "late", 60, user=("--t0=30",))
        mob, e3 = record(td, "mobile", 180, extra=("--rendering-method", "mobile"))
        comp, e4 = record(td, "compat", 180, extra=("--rendering-method", "gl_compatibility"))
        res["errors"] = e0 + e1 + e2 + e3 + e4
        cols = set()
        for n in range(0, 180, 5):
            f = load(base, n).reshape(-1, 3)
            cols |= {tuple(c) for c in np.unique(f, axis=0)}
        res["colours"] = sorted("#%02X%02X%02X" % c for c in cols)
        diff = []
        for n in range(0, 180, 6):
            diff.append(float((load(base, n) != load(nofx, n)).any(-1).mean()))
        res["fx_changed_mean"] = round(float(np.mean(diff)), 4)
        res["fx_changed_max"] = round(float(np.max(diff)), 4)
        res["fx_changed_frame_144"] = round(float((load(base, 144) != load(nofx, 144)).any(-1).mean()), 4)
        lcol = set()
        for n in range(0, 60, 5):
            lcol |= {tuple(c) for c in np.unique(load(late, n).reshape(-1, 3), axis=0)}
        res["late_colours"] = len(lcol)
        res["late_motion"] = round(float(np.mean([(load(late, n) != load(late, n + 1)).any(-1).mean()
                                                  for n in range(0, 58, 4)])), 4)
        for name, d in (("mobile", mob), ("compat", comp)):
            dd = [float((load(base, n) != load(d, n)).any(-1).mean()) for n in range(0, 180, 6)]
            res[name + "_diff_max"] = round(float(np.max(dd)), 5)
        if a.keep:
            k = pathlib.Path(a.keep)
            k.mkdir(parents=True, exist_ok=True)
            for name, d, n in (("base", base, 144), ("nofx", nofx, 144), ("late", late, 30), ("compat", comp, 144)):
                shutil.copy(d / f"f{n:08d}.png", k / f"{name}_{n}.png")
    pathlib.Path(a.out).write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
