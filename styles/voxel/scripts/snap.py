#!/usr/bin/env python3
"""Rendert die Demo mit Godots Movie Maker (30 fps) und legt ausgewählte Bilder ab.

    .venv/bin/python styles/voxel/scripts/snap.py OUTDIR --frames 0,60,150 [--res 1280x720] [-- --close-cam ...]
"""
import argparse, pathlib, shutil, subprocess, sys, tempfile

DEMO = pathlib.Path(__file__).resolve().parent.parent / "demo"


def main():
    argv = sys.argv[1:]
    user = []
    if "--" in argv:
        k = argv.index("--"); user = argv[k + 1:]; argv = argv[:k]
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--frames", default="0")
    ap.add_argument("--res", default="1280x720")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--renderer", default="", help="forward_plus, mobile oder gl_compatibility")
    a = ap.parse_args(argv)
    frames = [int(f) for f in a.frames.split(",")]
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    n = max(frames) + 1
    with tempfile.TemporaryDirectory() as td:
        cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", a.res,
               "--write-movie", str(pathlib.Path(td) / "f.png"), "--fixed-fps", "30", "--quit-after", str(n)]
        if a.renderer:
            cmd += ["--rendering-method", a.renderer]
        if user:
            cmd += ["--"] + user
        r = subprocess.run(cmd, capture_output=True, text=True)
        log = r.stdout + r.stderr
        (out / "godot.log").write_text(log)
        for l in log.splitlines():
            if "ERROR" in l or "WARNING" in l or l.startswith("M "):
                print(l)
        pngs = sorted(pathlib.Path(td).glob("f*.png"))
        sel = range(len(pngs)) if a.all else frames
        for f in sel:
            if f < len(pngs):
                shutil.copy(pngs[f], out / f"f{f:04d}.png")
    print("ok", len(pngs), "Bilder")


if __name__ == "__main__":
    main()
