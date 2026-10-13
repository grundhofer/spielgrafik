#!/usr/bin/env python3
"""Einzelbilder der Demo rendern (Godot --write-movie in ein Temp-Verzeichnis).

    .venv/bin/python styles/realistisch-pbr/scripts/snap.py OUT.png [--frames 40] [--keep 12,40] -- --cam=... --t0=3

Rendert --frames Bilder mit fester Bildrate 30 und speichert das letzte (oder die Bilder aus --keep,
dann OUT_<n>.png). Die zeitliche Glättung (TAA, SDFGI, Nebel) braucht einige Bilder; Standbilder
deshalb erst nach etwa 30 Bildern nehmen. Benutzerargumente nach "--" gehen an main.gd.
"""
import argparse
import pathlib
import shutil
import subprocess
import sys
import tempfile

ENTRY = pathlib.Path(__file__).resolve().parent.parent
DEMO = ENTRY / "demo"


def main():
    argv = sys.argv[1:]
    user = []
    if "--" in argv:
        i = argv.index("--")
        argv, user = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--frames", type=int, default=40)
    ap.add_argument("--keep", default="")
    ap.add_argument("--renderer", default="")
    ap.add_argument("--import", dest="do_import", action="store_true")
    a = ap.parse_args(argv)
    if a.do_import:
        subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    with tempfile.TemporaryDirectory() as td:
        cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
               "--write-movie", str(pathlib.Path(td) / "f.png"), "--fixed-fps", "30",
               "--quit-after", str(a.frames)]
        if a.renderer:
            cmd += ["--rendering-method", a.renderer]
        cmd += ["--"] + user
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        log = r.stdout + r.stderr
        bad = [l for l in log.splitlines() if "ERROR" in l or "WARNING" in l]
        for l in bad[:12]:
            print("  godot:", l[:200])
        frames = sorted(pathlib.Path(td).glob("f*.png"))
        if not frames:
            print(log[-2000:])
            sys.exit("keine Bilder")
        out = pathlib.Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        if a.keep:
            for k in [int(x) for x in a.keep.split(",")]:
                k = min(k, len(frames) - 1)
                shutil.copyfile(frames[k], out.with_name(f"{out.stem}_{k:03d}{out.suffix}"))
        else:
            shutil.copyfile(frames[-1], out)
        print(f"{len(frames)} Bilder, gespeichert: {out}")


if __name__ == "__main__":
    main()
