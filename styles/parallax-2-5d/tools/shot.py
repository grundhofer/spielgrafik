#!/usr/bin/env python3
"""Einzelbilder aus der Godot-Demo (Movie Maker, feste Bildrate) für Prüfungen.

    .venv/bin/python -I styles/parallax-2-5d/tools/shot.py OUT_DIR [--frames N] [--method forward_plus] -- --t0=3 ...

Schreibt OUT_DIR/f00000000.png … und OUT_DIR/godot.log; Argumente nach "--" gehen als Benutzerargumente an main.gd.
"""
import argparse, pathlib, re, shutil, subprocess, sys

S = pathlib.Path(__file__).resolve().parent.parent


def render(out, frames=1, user=(), method=None, resolution="1280x720"):
    out = pathlib.Path(out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    # geänderte Bilder neu importieren (ein normaler Lauf nimmt sonst die alten .ctex aus .godot/imported)
    subprocess.run(["godot", "--headless", "--path", str(S / "demo"), "--import"], capture_output=True, timeout=600)
    cmd = ["godot", "--path", str(S / "demo"), "--position", "20000,20000", "--resolution", resolution,
           "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", str(frames)]
    if method:
        cmd += ["--rendering-method", method]
    if user:
        cmd += ["--", *user]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    log = p.stdout + p.stderr
    (out / "godot.log").write_text(log)
    errs = [l for l in log.splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR", l)]
    return sorted(out.glob("f*.png")), errs


def main():
    argv = sys.argv[1:]
    user = []
    if "--" in argv:
        i = argv.index("--")
        argv, user = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--frames", type=int, default=1)
    ap.add_argument("--method")
    a = ap.parse_args(argv)
    pngs, errs = render(a.out, a.frames, user, a.method)
    print(len(pngs), "Bilder;", len(errs), "Fehler")
    for e in errs[:10]:
        print(e)


if __name__ == "__main__":
    main()
