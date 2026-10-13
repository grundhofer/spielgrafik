#!/usr/bin/env python3
"""Entwicklungshilfe: nimmt die Demo auf und legt Einzelbilder zu gewählten Zeitpunkten nebeneinander.

    .venv/bin/python styles/hintergrund-serie/tools/peek.py out.png 2.1 2.3 3.6 [--scale 0.5] [-- user-args]
"""
import pathlib, subprocess, sys, tempfile

from PIL import Image

SD = pathlib.Path(__file__).resolve().parent.parent


def main():
    args = sys.argv[1:]
    user = []
    if "--" in args:
        k = args.index("--")
        args, user = args[:k], args[k + 1:]
    scale = 0.5
    if "--scale" in args:
        k = args.index("--scale")
        scale = float(args[k + 1])
        del args[k:k + 2]
    out, times = args[0], [float(x) for x in args[1:]]
    n = int(max(times) * 30) + 2
    subprocess.run(["godot", "--headless", "--path", str(SD / "demo"), "--import"], capture_output=True, timeout=300)
    with tempfile.TemporaryDirectory() as td:
        cmd = ["godot", "--path", str(SD / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
               "--write-movie", str(pathlib.Path(td) / "f.png"), "--fixed-fps", "30", "--quit-after", str(n)]
        if user:
            cmd += ["--"] + user
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        for l in (r.stdout + r.stderr).splitlines():
            if "ERROR" in l:
                print(l)
        frames = sorted(pathlib.Path(td).glob("f*.png"))
        ims = [Image.open(frames[min(len(frames) - 1, round(t * 30))]).convert("RGB") for t in times]
        w, h = int(1280 * scale), int(720 * scale)
        cols = 2 if len(ims) > 1 else 1
        rows = (len(ims) + cols - 1) // cols
        sheet = Image.new("RGB", (w * cols, h * rows))
        for i, im in enumerate(ims):
            sheet.paste(im.resize((w, h), Image.LANCZOS), ((i % cols) * w, (i // cols) * h))
        sheet.save(out)
        print(out)


if __name__ == "__main__":
    main()
