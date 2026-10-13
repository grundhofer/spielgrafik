#!/usr/bin/env python3
"""Merkmale des N64-Looks mit Vergleichsschaltern messen.

    .venv/bin/python styles/n64/scripts/compare_switches.py <temp-ordner> [--frames 15,75,142]
        [--switches no-3pt,no-mip,...] [--method forward_plus|mobile|gl_compatibility]

Nimmt die Demo je Schalter mit dem Movie Maker auf (feste 30 fps, 960×720 wie in der Aufnahme) und vergleicht
die gewählten Bilder mit dem Lauf ohne Schalter: Anteil der Pixel, deren größte Kanalabweichung über 8 bzw.
24 Stufen liegt, und mittlere Abweichung. Außerdem:
  --check-16bit   Lauf mit --sharp --no-vifilter: Jeder Kanal muss ein Vielfaches von 255/31 sein
                  (5-Bit-Bildspeicher, ohne den weichzeichnenden Filter der Videoausgabe).
"""
import argparse
import pathlib
import subprocess

import numpy as np
from PIL import Image

DEMO = pathlib.Path(__file__).resolve().parent.parent / "demo"
ALL = ["nearest-tex", "no-3pt", "no-mip", "no-fog", "no-vc", "no-dither", "no-vifilter", "sharp", "no-msaa"]


def run(out, n, user_args, method=None):
    out.mkdir(parents=True, exist_ok=True)
    for p in out.glob("f*.png"):
        p.unlink()
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--write-movie", str(out / "f.png"),
           "--fixed-fps", "30", "--quit-after", str(n)]
    if method:
        cmd += ["--rendering-method", method]
    cmd += ["--"] + user_args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    log = r.stdout + r.stderr
    errs = [l for l in log.splitlines() if "ERROR" in l or "WARNING" in l]
    return errs


def load(d, i):
    return np.asarray(Image.open(d / f"f{i:08d}.png").convert("RGB"), dtype=np.int16)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tmp")
    ap.add_argument("--frames", default="15,75,142")
    ap.add_argument("--switches", default=",".join(ALL))
    ap.add_argument("--method", default=None)
    ap.add_argument("--check-16bit", action="store_true")
    a = ap.parse_args()
    tmp = pathlib.Path(a.tmp)
    frames = [int(x) for x in a.frames.split(",")]
    n = max(frames) + 1
    base = tmp / "base"
    errs = run(base, n, [])
    print("base", "Fehler/Warnungen:", errs[:3] if errs else "keine")
    if a.method:
        other = tmp / a.method
        errs = run(other, n, [], a.method)
        print(a.method, "Fehler/Warnungen:", errs[:3] if errs else "keine")
        for i in frames:
            A, B = load(base, i), load(other, i)
            d = np.abs(A - B).max(axis=2)
            mean_ch = (B - A).reshape(-1, 3).mean(0)
            print(f"  Bild {i}: >8: {100 * (d > 8).mean():5.1f} %  >24: {100 * (d > 24).mean():5.1f} %  "
                  f"Mittel {np.abs(A - B).mean():.2f}  Kanalmittel (B-A) {mean_ch.round(1)}")
        return
    if a.check_16bit:
        d = tmp / "fb16"
        errs = run(d, n, ["--sharp", "--no-vifilter"])
        lv = np.round(np.arange(32) * 255 / 31).astype(int)
        for i in frames:
            im = load(d, i)
            # nur das 960×720-Bild selbst (keine Ränder)
            vals = np.unique(im)
            bad = np.setdiff1d(vals, lv)
            flat = im.reshape(-1, 3).astype(np.int64)
            cols = len(np.unique(flat[:, 0] * 65536 + flat[:, 1] * 256 + flat[:, 2]))
            print(f"  16 Bit Bild {i}: {len(vals)} Kanalwerte, davon nicht 5-Bit: {len(bad)}; {cols} Farben")
        return
    for sw in a.switches.split(","):
        d = tmp / sw
        errs = run(d, n, ["--" + sw])
        line = []
        for i in frames:
            A, B = load(base, i), load(d, i)
            dd = np.abs(A - B).max(axis=2)
            line.append(f"Bild {i}: >8 {100 * (dd > 8).mean():5.1f} %, >24 {100 * (dd > 24).mean():5.1f} %, "
                        f"Mittel {np.abs(A - B).mean():5.2f}")
        print(f"--{sw:12s} " + " | ".join(line) + ("" if not errs else f"  FEHLER {errs[:2]}"))


if __name__ == "__main__":
    main()
