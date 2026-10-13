#!/usr/bin/env python3
"""Nimmt die Demo in einen beliebigen Ordner auf (für Prüfungen, nicht für media/).

    .venv/bin/python styles/fotoreal-standbild/tools/render.py <Ordner> [--frames 180] [--method mobile|gl_compatibility]
        [-- --t0=30 --raw ...]

Ruft vorher --import auf (neue PNGs). Gibt die Pfade der Einzelbilder aus und bricht bei ERROR ab.
"""
import argparse, pathlib, re, shutil, subprocess, sys

DEMO = pathlib.Path(__file__).resolve().parent.parent / "demo"


def render(out, frames=180, method=None, user_args=(), quiet=False):
    out = pathlib.Path(out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    imp = subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True, text=True)
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
           "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", str(frames)]
    if method:
        cmd += ["--rendering-method", method]
    if user_args:
        cmd += ["--"] + list(user_args)
    run = subprocess.run(cmd, capture_output=True, text=True)
    log = imp.stdout + imp.stderr + run.stdout + run.stderr
    errs = [l for l in log.splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR", l)]
    (out / "godot.log").write_text(log)
    if errs:
        sys.exit("Godot-Fehler:\n" + "\n".join(errs[:20]))
    pngs = sorted(out.glob("f*.png"))
    if not quiet:
        print(f"{len(pngs)} Bilder in {out}")
    return pngs


def main():
    argv = sys.argv[1:]
    user = []
    if "--" in argv:
        i = argv.index("--")
        argv, user = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--frames", type=int, default=180)
    ap.add_argument("--method")
    a = ap.parse_args(argv)
    render(a.out, a.frames, a.method, user)


if __name__ == "__main__":
    main()
