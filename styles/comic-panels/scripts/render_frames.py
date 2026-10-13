#!/usr/bin/env python3
"""Rendert die Demo mit Godots Movie Maker in einen Ordner (für Prüfskripte und Einzelbilder).

    .venv/bin/python styles/comic-panels/scripts/render_frames.py OUTDIR [--seconds 6] [--method forward_plus]
        [-- --probe-flat --probe-no-badger --t0=30]

Schreibt OUTDIR/f00000000.png … und OUTDIR/godot.log. Ruft vorher --import auf (sonst bleiben geänderte PNGs alt).
"""
import argparse, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"


def main():
    argv = sys.argv[1:]
    user = []
    if "--" in argv:
        i = argv.index("--")
        argv, user = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--seconds", type=float, default=6.0)
    ap.add_argument("--method", default="")
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("f*.png"):
        f.unlink()
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True, text=True)
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
           "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", str(int(round(a.seconds * 30)))]
    if a.method:
        cmd += ["--rendering-method", a.method]
    if user:
        cmd += ["--"] + user
    r = subprocess.run(cmd, capture_output=True, text=True)
    (out / "godot.log").write_text(r.stdout + r.stderr)
    bad = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l or "WARNING" in l]
    print(f"{len(list(out.glob('f*.png')))} Bilder in {out}; {len(bad)} Meldungen")
    for l in bad[:10]:
        print("  ", l[:200])


if __name__ == "__main__":
    main()
