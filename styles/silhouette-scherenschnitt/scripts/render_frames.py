#!/usr/bin/env python3
"""Rendert die Demo in ein Temp-Verzeichnis (Movie Maker, 30 fps) für eigene Prüfungen.

    .venv/bin/python styles/silhouette-scherenschnitt/scripts/render_frames.py <outdir> [--frames 180] [-- <godot user args>]

Schreibt <outdir>/f%08d.png. Vorher wird --import ausgeführt (geänderte PNGs).
"""
import pathlib, shutil, subprocess, sys

SD = pathlib.Path(__file__).resolve().parents[1]


def render(outdir, frames=180, user_args=(), import_first=True):
    out = pathlib.Path(outdir)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    if import_first:
        subprocess.run(["godot", "--headless", "--path", str(SD / "demo"), "--import"], capture_output=True, text=True)
    cmd = ["godot", "--path", str(SD / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
           "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", str(frames)]
    if user_args:
        cmd += ["--"] + list(user_args)
    r = subprocess.run(cmd, capture_output=True, text=True)
    log = r.stdout + r.stderr
    bad = [l for l in log.splitlines() if "ERROR" in l or "WARNING" in l]
    return sorted(out.glob("f*.png")), bad


if __name__ == "__main__":
    args = sys.argv[1:]
    user = []
    if "--" in args:
        i = args.index("--")
        args, user = args[:i], args[i + 1:]
    n = 180
    if "--frames" in args:
        n = int(args[args.index("--frames") + 1])
    files, bad = render(args[0], n, user)
    print(len(files), "Bilder")
    for b in bad[:20]:
        print(b)
