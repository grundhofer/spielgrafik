#!/usr/bin/env python3
"""Vergleicht die Demo mit zusammengefassten Netzen (Standard) gegen --probe-nobake (jedes Polygon ein Polygon2D).

  .venv/bin/python styles/polygon-kino/scripts/compare_bake.py
Ergebnis: assets/bake_check.json
"""
import json
import pathlib
import shutil
import subprocess
import tempfile

import numpy as np
from PIL import Image

ENTRY = pathlib.Path(__file__).resolve().parent.parent


def movie(td, name, extra):
    out = td / name
    out.mkdir()
    subprocess.run(["godot", "--path", str(ENTRY / "demo"), "--position", "20000,20000", "--write-movie",
                    str(out / "f.png"), "--fixed-fps", "30", "--quit-after", "180", "--"] + extra, capture_output=True)
    return sorted(out.glob("f*.png"))


def main():
    td = pathlib.Path(tempfile.mkdtemp())
    a = movie(td, "bake", [])
    b = movie(td, "nobake", ["--probe-nobake"])
    changed = []
    for fa, fb in zip(a, b):
        x = np.asarray(Image.open(fa).convert("RGB")).astype(int)
        y = np.asarray(Image.open(fb).convert("RGB")).astype(int)
        changed.append(int((np.abs(x - y).max(axis=2) > 0).sum()))
    res = {"frames": len(changed), "frames_with_differences": sum(c > 0 for c in changed),
           "max_changed_px": max(changed) if changed else None}
    (ENTRY / "assets/bake_check.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res))
    shutil.rmtree(td)


if __name__ == "__main__":
    main()
