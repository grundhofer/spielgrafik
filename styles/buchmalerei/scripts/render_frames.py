#!/usr/bin/env python3
"""Rendert die Demo mit Godots Movie Maker in einen Ordner (deterministisch, 30 Bilder/s) und legt optional
einen Kontaktbogen ausgewählter Bilder an.

    .venv/bin/python styles/buchmalerei/scripts/render_frames.py --out <ordner> [--frames 180]
        [--sheet 0,30,90,150] [--crop x,y,w,h] [--scale 1.0] [-- --probe-no-badger --t0=30]

Benutzerargumente nach "--" gehen an main.gd (siehe OS.get_cmdline_user_args()).
"""
import argparse, pathlib, shutil, subprocess, sys

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]


def render(out, frames, user_args=(), rendering_method=None):
    out = pathlib.Path(out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    demo = ROOT / "demo"
    subprocess.run(["godot", "--headless", "--path", str(demo), "--import"], capture_output=True, timeout=300)
    cmd = ["godot", "--path", str(demo), "--position", "20000,20000", "--resolution", "1280x720",
           "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", str(frames)]
    if rendering_method:
        cmd[1:1] = ["--rendering-method", rendering_method]
    if user_args:
        cmd += ["--"] + list(user_args)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    log = r.stdout + r.stderr
    (out / "godot.log").write_text(log)
    bad = [l for l in log.splitlines() if "ERROR" in l or "SCRIPT ERROR" in l]
    if bad:
        print("\n".join(bad[:10]), file=sys.stderr)
    return sorted(out.glob("f*.png"))


def main():
    argv = sys.argv[1:]
    user = []
    if "--" in argv:
        i = argv.index("--")
        user = argv[i + 1:]
        argv = argv[:i]
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--frames", type=int, default=180)
    ap.add_argument("--sheet", default="")
    ap.add_argument("--crop", default="")
    ap.add_argument("--scale", type=float, default=0.5)
    ap.add_argument("--method", default=None)
    a = ap.parse_args(argv)
    pngs = render(a.out, a.frames, user, a.method)
    print(len(pngs), "Bilder in", a.out)
    if a.sheet:
        idx = [int(v) for v in a.sheet.split(",")]
        ims = []
        for i in idx:
            im = Image.open(pngs[min(i, len(pngs) - 1)]).convert("RGB")
            if a.crop:
                x, y, w, h = map(int, a.crop.split(","))
                im = im.crop((x, y, x + w, y + h))
            ims.append(im.resize((round(im.width * a.scale), round(im.height * a.scale)), Image.LANCZOS))
        cols = 2 if len(ims) > 1 else 1
        rows = (len(ims) + cols - 1) // cols
        sw, sh = ims[0].size
        sheet = Image.new("RGB", (sw * cols, sh * rows), "white")
        for k, im in enumerate(ims):
            sheet.paste(im, ((k % cols) * sw, (k // cols) * sh))
        sheet.save(pathlib.Path(a.out) / "sheet.png")
        print("Kontaktbogen", pathlib.Path(a.out) / "sheet.png")


if __name__ == "__main__":
    main()
