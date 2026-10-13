#!/usr/bin/env python3
"""Rendert die Demo in einen Ordner (Einzelbilder, 30 fps, 1280x720), optional mit Prüfschaltern.
Nach styles/kupferstich/scripts/render_frames.py.

    .venv/bin/python styles/bleistift-skizze/scripts/render_frames.py OUTDIR [--frames 180] [--method mobile]
                     [-- --probe-badger-only | --no-boil | --probe-log]

Wie tools/capture.py (Movie Maker mit fester Bildrate), aber ohne Medien zu schreiben: für Messungen
(scripts/probe_feet.py, scripts/measure_boil.py) und den Vergleich der Renderer.
Bild i (ab 0) zeigt Takt i + 1 der Ablauftabelle (Movie Maker schreibt nach dem ersten _process).
"""
import argparse, pathlib, subprocess, sys

SD = pathlib.Path(__file__).resolve().parents[1]


def render(out, frames=180, method=None, user_args=()):
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("f*.png"):
        f.unlink()
    cmd = ["godot", "--path", str(SD / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
           "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", str(frames)]
    if method:
        cmd += ["--rendering-method", method]
    if user_args:
        cmd += ["--", *user_args]
    r = subprocess.run(cmd, capture_output=True, text=True)
    log = r.stdout + r.stderr
    (out / "godot.log").write_text(log)
    errs = [l for l in log.splitlines() if "ERROR" in l]
    return sorted(out.glob("f*.png")), errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--frames", type=int, default=180)
    ap.add_argument("--method")
    a, rest = ap.parse_known_args()
    user = [x for x in rest if x != "--"]
    pngs, errs = render(a.out, a.frames, a.method, user)
    print(len(pngs), "Bilder;", len(errs), "Fehler")
    for e in errs[:10]:
        print(e)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
