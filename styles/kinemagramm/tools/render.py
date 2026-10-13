#!/usr/bin/env python3
"""Rendert die Demo in einen Ordner (PNG je Bild) für Messungen, ohne media/ anzufassen.

    .venv/bin/python styles/kinemagramm/tools/render.py OUTDIR [--frames 180] [--method forward_plus|mobile|gl_compatibility]
        [--demo DIR] [-- extra args]
"""
import argparse, pathlib, subprocess, sys

DEMO = pathlib.Path(__file__).resolve().parent.parent / "demo"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--frames", type=int, default=180)
    ap.add_argument("--method", default="")
    ap.add_argument("--demo", default=str(DEMO), help="anderes Godot-Projekt (z. B. Kopie für Tests)")
    ap.add_argument("extra", nargs="*")
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("f*.png"):
        f.unlink()
    cmd = ["godot", "--path", str(a.demo), "--position", "20000,20000", "--resolution", "1280x720",
           "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", str(a.frames)]
    if a.method:
        cmd += ["--rendering-method", a.method]
    if a.extra:
        cmd += ["--"] + a.extra
    p = subprocess.run(cmd, capture_output=True, text=True)
    log = p.stdout + p.stderr
    (out / "godot.log").write_text(log)
    bad = [l for l in log.splitlines() if "ERROR" in l]
    print(f"{len(list(out.glob('f*.png')))} Bilder, {len(bad)} Fehlerzeilen")
    for l in bad[:10]:
        print(l)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
