#!/usr/bin/env python3
"""Nimmt die Demo in Basisauflösung (640×360) auf und legt ausgewählte Bilder ab bzw. misst.

    .venv/bin/python styles/hibit-pixel/scripts/probe.py --out <ordner> [--frames 0,60,108] [--seconds 6]
        [--args "--nolight"] [--method forward_plus|mobile|gl_compatibility] [--keep]

Ruft vorher `godot --headless --import` auf (geänderte PNGs). Schreibt die gewählten Bilder als PNG (nativ)
und mit --keep alle Bilder nach <ordner>/all/. Gibt Fehler/Warnungen aus Godot aus.
"""
import argparse, pathlib, re, shutil, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"


def run(out, seconds=6.0, fps=30, args="", method="", keep=False, frames=()):
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    imp = subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True, text=True)
    n = int(round(seconds * fps))
    with tempfile.TemporaryDirectory() as td:
        cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--write-movie", str(pathlib.Path(td) / "f.png"),
               "--fixed-fps", str(fps), "--quit-after", str(n)]
        if method:
            cmd += ["--rendering-method", method]
        if args:
            cmd += ["--"] + args.split()
        r = subprocess.run(cmd, capture_output=True, text=True)
        log = imp.stdout + imp.stderr + r.stdout + r.stderr
        bad = [l for l in log.splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR|\bWARNING\b", l)]
        pngs = sorted(pathlib.Path(td).glob("f*.png"))
        for i in frames:
            if i < len(pngs):
                shutil.copy(pngs[i], out / f"f{i:04d}.png")
        if keep:
            (out / "all").mkdir(exist_ok=True)
            for p in pngs:
                shutil.copy(p, out / "all" / p.name)
    return len(pngs), bad


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--frames", default="")
    ap.add_argument("--seconds", type=float, default=6.0)
    ap.add_argument("--args", default="")
    ap.add_argument("--method", default="")
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    fr = [int(x) for x in a.frames.split(",") if x]
    n, bad = run(a.out, a.seconds, 30, a.args, a.method, a.keep, fr)
    print(f"{n} Bilder; Meldungen: {len(bad)}")
    for l in bad[:10]:
        print("  ", l[:200])
