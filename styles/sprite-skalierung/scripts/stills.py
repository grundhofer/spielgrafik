#!/usr/bin/env python3
"""Rendert Einzelbilder der Demo zu bestimmten Zeiten und legt sie ×2 nebeneinander (Sichtprüfung).

    .venv/bin/python styles/sprite-skalierung/scripts/stills.py <outdir> 0.5 2.0 3.9 [--args --nostripes]
"""
import pathlib, subprocess, sys, tempfile

from PIL import Image

SD = pathlib.Path(__file__).resolve().parents[1]


def render(t, extra, td, n=2):
    out = pathlib.Path(td) / f"t{t:.2f}"
    out.mkdir(parents=True, exist_ok=True)
    cmd = ["godot", "--path", str(SD / "demo"), "--position", "20000,20000", "--write-movie", str(out / "f.png"),
           "--fixed-fps", "30", "--quit-after", str(n), "--", f"--t0={t}"] + extra
    r = subprocess.run(cmd, capture_output=True, text=True)
    bad = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    if bad:
        print("\n".join(bad[:10]))
    return sorted(out.glob("f*.png"))[0]


def main():
    outdir = pathlib.Path(sys.argv[1])
    outdir.mkdir(parents=True, exist_ok=True)
    args = sys.argv[2:]
    extra = []
    if "--args" in args:
        i = args.index("--args")
        extra = args[i + 1:]
        args = args[:i]
    times = [float(a) for a in args]
    subprocess.run(["godot", "--headless", "--path", str(SD / "demo"), "--import"], capture_output=True)
    with tempfile.TemporaryDirectory(dir=outdir) as td:
        ims = [Image.open(render(t, extra, td)).convert("RGB") for t in times]
        for t, im in zip(times, ims):
            im.save(outdir / f"still_{t:.2f}.png")
    k = 2
    cols = 2 if len(ims) > 1 else 1
    rows = (len(ims) + cols - 1) // cols
    w, h = ims[0].size
    sheet = Image.new("RGB", (cols * w * k + (cols - 1) * 4, rows * h * k + (rows - 1) * 4), "white")
    for i, im in enumerate(ims):
        sheet.paste(im.resize((w * k, h * k), Image.NEAREST), ((i % cols) * (w * k + 4), (i // cols) * (h * k + 4)))
    sheet.save(outdir / "stills.png")
    print(outdir / "stills.png")


if __name__ == "__main__":
    main()
