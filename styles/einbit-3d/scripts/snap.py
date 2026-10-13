#!/usr/bin/env python3
"""Einzelbilder der Demo rendern (wie tools/capture.py, aber nur ausgewählte Bilder, mit Schaltern).

    .venv/bin/python styles/einbit-3d/scripts/snap.py --frames 45,150 --out <Ordner> [--scale 2] \
        [--name probe] [--renderer forward_plus] -- --gray --no-lines

Rendert mit --write-movie und --fixed-fps 30 so viele Bilder wie nötig (bis zum größten gewünschten),
speichert die gewünschten als <name>_fNNN.png (ganzzahlig mit Nearest vergrößert) und gibt Godot-Fehler aus.
"""
import argparse, pathlib, re, shutil, subprocess, sys, tempfile

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent.parent


def render(n, user_args, renderer=None, keep=None):
    """Gibt die Liste der Bildpfade (in einem Temp-Ordner, der bestehen bleibt, wenn keep gesetzt) zurück."""
    td = pathlib.Path(keep or tempfile.mkdtemp(prefix="einbit-3d-"))
    td.mkdir(parents=True, exist_ok=True)
    for old in td.glob("f*.png"):
        old.unlink()
    cmd = ["godot", "--path", str(HERE / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
           "--write-movie", str(td / "f.png"), "--fixed-fps", "30", "--quit-after", str(n)]
    if renderer:
        cmd += ["--rendering-method", renderer]
    if user_args:
        cmd += ["--"] + user_args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    log = r.stdout + r.stderr
    errs = [l for l in log.splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR|WARNING", l)]
    return sorted(td.glob("f*.png")), log, errs


if __name__ == "__main__":
    argv = sys.argv[1:]
    user = []
    if "--" in argv:
        i = argv.index("--")
        argv, user = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--name", default="snap")
    ap.add_argument("--renderer", default=None)
    a = ap.parse_args(argv)
    frames = [int(x) for x in a.frames.split(",")]
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    pngs, log, errs = render(max(frames) + 1, user, a.renderer)
    for l in log.splitlines():
        if l.startswith("Einstellung") or l.startswith("M "):
            print(l)
    for e in errs[:20]:
        print("!!", e)
    for f in frames:
        if f >= len(pngs):
            print(f"Bild {f} fehlt ({len(pngs)} gerendert)")
            continue
        im = Image.open(pngs[f]).convert("RGB")
        if a.scale != 1:
            im = im.resize((im.width * a.scale, im.height * a.scale), Image.NEAREST)
        p = out / f"{a.name}_f{f:03d}.png"
        im.save(p)
        print(p, im.size, "Farben:", len(im.getcolors(1 << 20) or []))
    shutil.rmtree(pngs[0].parent if pngs else "", ignore_errors=True)
