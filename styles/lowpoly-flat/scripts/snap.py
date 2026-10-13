#!/usr/bin/env python3
"""Einzelbilder der Demo rendern (für Prüfungen außerhalb von capture.py).

    .venv/bin/python styles/lowpoly-flat/scripts/snap.py OUTDIR 30,150 [-- --smooth]

Ruft vorher --import auf, rendert mit --write-movie und --fixed-fps 30 bis zum letzten gewünschten Bild
in ein Temp-Verzeichnis und kopiert die gewünschten Bilder als OUTDIR/f<nr>.png. Godot-Fehler werden
ausgegeben. Weitere Godot-Argumente (z. B. --rendering-method mobile) vor dem "--" über --godot.
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
    ap.add_argument("frames")
    ap.add_argument("--godot", default="", help="zusätzliche Godot-Argumente, mit Leerzeichen getrennt")
    a = ap.parse_args(argv)
    want = [int(x) for x in a.frames.split(",")]
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    imp = subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True, text=True)
    with tempfile.TemporaryDirectory() as td:
        cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
               "--write-movie", str(pathlib.Path(td) / "f.png"), "--fixed-fps", "30",
               "--quit-after", str(max(want) + 1)] + a.godot.split() + (["--"] + user if user else [])
        run = subprocess.run(cmd, capture_output=True, text=True)
        log = imp.stdout + imp.stderr + run.stdout + run.stderr
        for l in log.splitlines():
            if re.search(r"\bERROR\b|SCRIPT ERROR|WARNING", l):
                print(l)
        (out / "godot.log").write_text(run.stdout + run.stderr)
        for n in want:
            src = pathlib.Path(td) / f"f{n:08d}.png"
            if src.exists():
                shutil.copy(src, out / f"f{n:03d}.png")
            else:
                print("fehlt:", src.name)


if __name__ == "__main__":
    main()
