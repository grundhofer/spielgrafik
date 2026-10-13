#!/usr/bin/env python3
"""Rendert die Demo in Basisauflösung (426x240) in einen Ordner, ohne tools/capture.py.

    .venv/bin/python styles/sprite-stacking/scripts/render_frames.py OUT_DIR [--frames 180] [--pick 0,60,120]
        [--scale 3] [--method forward_plus|mobile|gl_compatibility] [-- user-args für main.gd]

Schreibt OUT_DIR/f########.png (Godot Movie Maker, 30 fps, deterministisch) und mit --pick einen
Kontaktbogen OUT_DIR/pick.png (ganzzahlig vergrößert). Die Ausgabe von Godot steht in OUT_DIR/godot.log.
"""
import argparse, pathlib, re, subprocess, sys

from PIL import Image

DEMO = pathlib.Path(__file__).resolve().parent.parent / "demo"


def render(out, frames=180, method=None, user=()):
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for p in out.glob("f*.png"):
        p.unlink()
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--write-movie", str(out / "f.png"),
           "--fixed-fps", "30", "--quit-after", str(frames)]
    if method:
        cmd += ["--rendering-method", method]
    if user:
        cmd += ["--", *user]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    log = r.stdout + r.stderr
    (out / "godot.log").write_text(log)
    errs = [l for l in log.splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR|SHADER ERROR", l)]
    return sorted(out.glob("f*.png")), errs, log


def main():
    argv = sys.argv[1:]
    user = []
    if "--" in argv:
        i = argv.index("--")
        argv, user = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--frames", type=int, default=180)
    ap.add_argument("--pick", default="")
    ap.add_argument("--scale", type=int, default=3)
    ap.add_argument("--method", default=None)
    a = ap.parse_args(argv)
    pngs, errs, _ = render(a.out, a.frames, a.method, user)
    print(f"{len(pngs)} Bilder, {len(errs)} Fehlerzeilen")
    for e in errs[:20]:
        print("  ", e)
    if a.pick:
        idx = [int(v) for v in a.pick.split(",")]
        ims = [Image.open(pngs[min(i, len(pngs) - 1)]).convert("RGB") for i in idx]
        w, h = ims[0].size
        cols = 2 if len(ims) > 1 else 1
        rows = (len(ims) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * w * a.scale + (cols - 1) * 4, rows * h * a.scale + (rows - 1) * 4), "white")
        for k, im in enumerate(ims):
            sheet.paste(im.resize((w * a.scale, h * a.scale), Image.NEAREST),
                        ((k % cols) * (w * a.scale + 4), (k // cols) * (h * a.scale + 4)))
        sheet.save(pathlib.Path(a.out) / "pick.png")


if __name__ == "__main__":
    main()
