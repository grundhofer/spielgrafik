#!/usr/bin/env python3
"""Schnelle Probeaufnahme der Demo für die Entwicklung (ohne media/ anzufassen).

    .venv/bin/python styles/toon-cel/scripts/snap.py OUT_DIR --frames 0,75,140 [--seconds 6] [-- --no-post ...]

Nimmt mit Godots Movie Maker (feste Bildrate 30) bis zum letzten gewünschten Bild auf und kopiert
die gewünschten Bilder als OUT_DIR/f<nnn>.png. Argumente nach "--" gehen an die Demo
(Vergleichsschalter aus main.gd). Gibt Fehlerzeilen aus dem Godot-Protokoll aus.
"""
import argparse, pathlib, re, shutil, subprocess, sys, tempfile

DEMO = pathlib.Path(__file__).resolve().parent.parent / "demo"


def main():
    argv = sys.argv[1:]
    user = []
    if "--" in argv:
        i = argv.index("--")
        argv, user = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--frames", default="0,60,120,170")
    ap.add_argument("--resolution", default="1280x720")
    ap.add_argument("--renderer", default="")
    ap.add_argument("--all", action="store_true", help="alle Bilder behalten")
    a = ap.parse_args(argv)
    frames = [int(x) for x in a.frames.split(",")]
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", a.resolution,
               "--write-movie", str(pathlib.Path(td) / "f.png"), "--fixed-fps", "30",
               "--quit-after", str(max(frames) + 1)]
        if a.renderer:
            cmd += ["--rendering-method", a.renderer]
        if user:
            cmd += ["--"] + user
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        log = r.stdout + r.stderr
        for line in log.splitlines():
            if re.search(r"ERROR|WARNING|SCRIPT", line):
                print(line)
        pngs = sorted(pathlib.Path(td).glob("f*.png"))
        print(f"{len(pngs)} Bilder")
        if a.all:
            for i, p in enumerate(pngs):
                shutil.copy(p, out / f"f{i:03d}.png")
        else:
            for f in frames:
                if f < len(pngs):
                    shutil.copy(pngs[f], out / f"f{f:03d}.png")


if __name__ == "__main__":
    main()
