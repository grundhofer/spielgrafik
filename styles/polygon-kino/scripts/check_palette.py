#!/usr/bin/env python3
"""Prüft die 16-Farben-Regel im gerenderten Bild: nimmt die Demo in nativer Auflösung (320x200) auf und zählt je
Bild die Farben. Jede Farbe muss in der Palette der gerade gezeigten Einstellung stehen (data/scenes.json).

  .venv/bin/python styles/polygon-kino/scripts/check_palette.py [--seconds 6] [-- weitere Godot-Schalter]
Ergebnis: assets/palette_check.json
"""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

ENTRY = pathlib.Path(__file__).resolve().parent.parent


def main():
    extra = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    seconds = 6.0
    if "--seconds" in sys.argv:
        seconds = float(sys.argv[sys.argv.index("--seconds") + 1])
    method = None
    if "--rendering-method" in sys.argv:
        method = sys.argv[sys.argv.index("--rendering-method") + 1]
    data = json.load(open(ENTRY / "demo/data/scenes.json"))
    pals = {k: {tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for h in v} for k, v in data["palettes"].items()}
    src = (ENTRY / "demo/main.gd").read_text()
    cut = float(src.split("const CUT := ")[1].split()[0])
    t0 = 0.0
    for e in extra:
        if e.startswith("--t0="):
            t0 = float(e.split("=")[1])
    td = pathlib.Path(tempfile.mkdtemp())
    cmd = ["godot", "--path", str(ENTRY / "demo"), "--position", "20000,20000", "--write-movie", str(td / "f.png"),
           "--fixed-fps", "30", "--quit-after", str(int(seconds * 30))]
    if method:
        cmd += ["--rendering-method", method]
    subprocess.run(cmd + (["--"] + extra if extra else []), capture_output=True)
    files = sorted(td.glob("f*.png"))
    worst = {"A": 0, "B": 0}
    foreign = []
    counts = []
    for i, f in enumerate(files):
        a = np.asarray(Image.open(f).convert("RGB")).reshape(-1, 3)
        cols = {tuple(c) for c in np.unique(a, axis=0)}
        t = t0 + i / 30.0
        shot = "A" if t < cut else "B"
        worst[shot] = max(worst[shot], len(cols))
        counts.append(len(cols))
        bad = cols - pals[shot]
        if bad:
            foreign.append({"frame": i, "shot": shot, "colors": sorted("#%02x%02x%02x" % c for c in bad)[:8]})
    res = {"frames": len(files), "size": list(Image.open(files[0]).size) if files else None,
           "max_colors": worst, "frames_with_foreign_colors": len(foreign), "examples": foreign[:5],
           "rendering_method": method or "forward_plus"}
    print(json.dumps(res, ensure_ascii=False))
    if not extra and not method:
        (ENTRY / "assets/palette_check.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    shutil.rmtree(td)


if __name__ == "__main__":
    main()
