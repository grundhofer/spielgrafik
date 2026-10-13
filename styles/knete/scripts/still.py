#!/usr/bin/env python3
"""Einzelbilder der Knete-Demo rendern (für Sichtprüfung und Messung).

    .venv/bin/python styles/knete/scripts/still.py OUT_DIR --t0 4.3 [--frames 1] [-- --no-ui ...]

Startet Godot mit --write-movie ab --t0 (main.gd spult in denselben Stufen vor) und legt die Bilder als
OUT_DIR/f00000000.png … ab. Gibt Godot-Fehler aus.
"""
import argparse, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    argv = sys.argv[1:]
    extra = []
    if "--" in argv:
        i = argv.index("--")
        argv, extra = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--t0", type=float, default=0.0)
    ap.add_argument("--frames", type=int, default=1)
    ap.add_argument("--method", default="", help="rendering-method (mobile, gl_compatibility)")
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for p in out.glob("f*.png"):
        p.unlink()
    cmd = ["godot", "--path", str(ROOT / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
           "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", str(a.frames)]
    if a.method:
        cmd += ["--rendering-method", a.method]
    cmd += ["--", f"--t0={a.t0}"] + extra
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    log = r.stdout + r.stderr
    (out / "godot.log").write_text(log)
    errs = [l for l in log.splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR|WARNING", l)]
    for l in errs[:20]:
        print(l)
    print(f"{len(list(out.glob('f*.png')))} Bilder in {out}")


if __name__ == "__main__":
    main()
