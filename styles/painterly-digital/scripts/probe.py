#!/usr/bin/env python3
"""Prüflauf: Demo mit Movie Maker aufnehmen (wie tools/capture.py), Einzelbilder behalten.

    .venv/bin/python styles/painterly-digital/scripts/probe.py OUTDIR [--at 0.5,2,3.6,5] [--frames 180]
          [--method forward_plus|mobile|gl_compatibility] [--keep]

Schreibt OUTDIR/frame_<t>.png für die gewünschten Zeitpunkte und mit --keep alle Bilder nach OUTDIR/all/.
"""
import argparse, pathlib, re, shutil, subprocess, tempfile

S = pathlib.Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--at", default="0.5,2.0,3.6,5.0")
ap.add_argument("--frames", type=int, default=180)
ap.add_argument("--method", default="")
ap.add_argument("--keep", action="store_true")
a = ap.parse_args()
out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
subprocess.run(["godot", "--headless", "--path", str(S / "demo"), "--import"], capture_output=True)
TMP = pathlib.Path(tempfile.gettempdir()) / "painterly-digital"   # eigener Unterordner für Temp-Dateien
TMP.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(dir=TMP) as td:
    cmd = ["godot", "--path", str(S / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
           "--write-movie", f"{td}/f.png", "--fixed-fps", "30", "--quit-after", str(a.frames)]
    if a.method:
        cmd[1:1] = ["--rendering-method", a.method]
    r = subprocess.run(cmd, capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR", l)]
    print("Fehler:", errs[:8])
    pngs = sorted(pathlib.Path(td).glob("f*.png"))
    print("Bilder:", len(pngs))
    for ts in a.at.split(","):
        i = min(len(pngs) - 1, int(round(float(ts) * 30)))
        shutil.copy2(pngs[i], out / f"frame_{ts}.png")
    if a.keep:
        (out / "all").mkdir(exist_ok=True)
        for p in pngs:
            shutil.copy2(p, out / "all" / p.name)
