#!/usr/bin/env python3
"""Probelauf der Demo mit Schaltern; legt Einzelbilder und einen Kontaktbogen in einem Temp-Ordner ab.

    .venv/bin/python styles/pixel-3d/scripts/probe.py OUT [--frames 30,90,150] [--seconds 6] [-- --no-snap ...]

OUT ist ein eigener Temp-Ordner (z. B. <Scratchpad>/pixel-3d/probe). Godot schreibt mit --write-movie
die 1280×720-Bilder (f*.png) und mit --dump die Renderbilder in 428×242 ohne Palette (dump/r*.png) und
die Fensterbilder (dump/f*.png). Ausgegeben werden Fehlerzeilen aus dem Godot-Protokoll; sheet.png zeigt
die gewählten Bilder.
"""
import argparse
import pathlib
import re
import shutil
import subprocess
import sys

from PIL import Image

DEMO = pathlib.Path(__file__).resolve().parent.parent / "demo"


def main():
    argv = sys.argv[1:]
    extra = []
    if "--" in argv:
        i = argv.index("--")
        argv, extra = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--frames", default="30,90,150")
    ap.add_argument("--seconds", type=float, default=6.0)
    ap.add_argument("--no-dump", action="store_true")
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    (out / "movie").mkdir(parents=True)
    n = int(round(a.seconds * 30))
    # neue oder geänderte Dateien (z. B. palette.png) erst importieren, sonst nutzt Godot den alten Stand
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True, text=True)
    user = list(extra)
    if not a.no_dump:
        user.append(f"--dump={out / 'dump'}")
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
           "--write-movie", str(out / "movie" / "f.png"), "--fixed-fps", "30", "--quit-after", str(n), "--"] + user
    r = subprocess.run(cmd, capture_output=True, text=True)
    log = r.stdout + r.stderr
    (out / "godot.log").write_text(log)
    errs = [l for l in log.splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR|WARNING", l)]
    for e in errs[:20]:
        print(e)
    frames = [int(x) for x in a.frames.split(",")]
    ims = []
    for k in frames:
        p = out / "movie" / f"f{k:08d}.png"
        if p.exists():
            ims.append(Image.open(p).convert("RGB"))
    if ims:
        w, h = 640, 360
        cols = 2 if len(ims) > 1 else 1
        rows = (len(ims) + cols - 1) // cols
        sheet = Image.new("RGB", (w * cols, h * rows))
        for i, im in enumerate(ims):
            sheet.paste(im.resize((w, h), Image.LANCZOS), ((i % cols) * w, (i // cols) * h))
        sheet.save(out / "sheet.png")
    print(f"{len(list((out / 'movie').glob('f*.png')))} Bilder, Fehlerzeilen: {len(errs)} -> {out}")


if __name__ == "__main__":
    main()
