#!/usr/bin/env python3
"""Einzelbilder oder kurze Folgen der Demo rendern (für Prüfungen und Standbilder).

    .venv/bin/python styles/nachbearbeitung/scripts/snap.py --out <tmp> --t0 3.6 --frames 1 [--look 3] \
        [--extra="--no-badger --no-ui"] [--renderer gl_compatibility] [--keep-last NAME.png]

Ruft vorher `godot --headless --import` auf (ein normaler Lauf importiert geänderte PNGs nicht neu) und dann
Godot mit --write-movie und --fixed-fps 30; Benutzerargumente gehen nach "--" an main.gd.
"""
import argparse
import pathlib
import re
import shutil
import subprocess
import sys

DEMO = pathlib.Path(__file__).resolve().parent.parent / "demo"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--t0", type=float, default=0.0)
    ap.add_argument("--frames", type=int, default=1)
    ap.add_argument("--look", type=int, default=None)
    ap.add_argument("--renderer", default=None)
    ap.add_argument("--extra", default="", help='weitere Benutzerargumente in einem String, z. B. --extra="--no-ui --no-label"')
    ap.add_argument("--no-import", action="store_true")
    ap.add_argument("--keep-last", default=None, help="letztes Bild unter diesem Namen behalten, Rest löschen")
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for f in list(out.glob("f0*.png")) + list(out.glob("f.wav")):
        f.unlink()
    if not a.no_import:
        subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True, text=True)
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
           "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", str(a.frames)]
    if a.renderer:
        cmd += ["--rendering-method", a.renderer]
    user = [f"--t0={a.t0}"] + ([f"--look={a.look}"] if a.look is not None else []) + a.extra.split()
    cmd += ["--"] + user
    r = subprocess.run(cmd, capture_output=True, text=True)
    log = r.stdout + r.stderr
    bad = [l for l in log.splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR|WARNING", l)]
    if bad:
        print("\n".join(bad[:20]))
    pngs = sorted(out.glob("f0*.png"))
    if (out / "f.wav").exists():
        (out / "f.wav").unlink()      # Movie Maker schreibt immer auch eine Tonspur
    print(f"{len(pngs)} Bilder in {out}")
    if a.keep_last and pngs:
        shutil.move(str(pngs[-1]), str(out / a.keep_last))
        for p in pngs[:-1]:
            p.unlink()
        print("behalten:", out / a.keep_last)
    return 1 if any("ERROR" in l for l in bad) else 0


if __name__ == "__main__":
    sys.exit(main())
