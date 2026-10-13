#!/usr/bin/env python3
"""Rendert die Demo bildgenau in einen Ordner (wie tools/capture.py, aber mit Prüfschaltern und ohne Medien).

    .venv/bin/python styles/noir/scripts/render_frames.py OUTDIR [--frames 180] [--rendering-method mobile] \
        [-- --probe-badger-only | --probe-no-badger]

Schreibt OUTDIR/f00000000.png … (1280×720, Godot Movie Maker, 30 fps fest).
"""
import argparse, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    argv = sys.argv[1:]
    user = []
    if "--" in argv:
        i = argv.index("--")
        argv, user = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--frames", type=int, default=180)
    ap.add_argument("--rendering-method", default="")
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for p in out.glob("f*.png"):
        p.unlink()
    cmd = ["godot", "--path", str(ROOT / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
           "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", str(a.frames)]
    if a.rendering_method:
        cmd += ["--rendering-method", a.rendering_method]
    if user:
        cmd += ["--"] + user
    r = subprocess.run(cmd, capture_output=True, text=True)
    log = r.stdout + r.stderr
    (out / "godot.log").write_text(log)
    bad = [l for l in log.splitlines() if "ERROR" in l or "SCRIPT ERROR" in l]
    n = len(list(out.glob("f*.png")))
    print(f"{n} Bilder in {out}", "| Fehler: " + bad[0][:200] if bad else "")


if __name__ == "__main__":
    main()
