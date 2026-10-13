#!/usr/bin/env python3
"""Vergleicht Einzelbilder (320x200) der Renderer Forward+, Mobile und Compatibility.

  .venv/bin/python styles/polygon-kino/scripts/compare_renderers.py
Ergebnis: assets/renderers.json (Anteil abweichender Pixel je Zeitpunkt gegen Forward+)
"""
import json
import pathlib
import shutil
import subprocess
import tempfile

import numpy as np
from PIL import Image

ENTRY = pathlib.Path(__file__).resolve().parent.parent
TIMES = [0.5, 1.5, 3.3, 4.4, 5.0, 30.0]


def frame(method, t, td):
    out = td / f"{method}_{t}"
    out.mkdir()
    subprocess.run(["godot", "--path", str(ENTRY / "demo"), "--position", "20000,20000", "--rendering-method", method,
                    "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", "1", "--", f"--t0={t}"],
                   capture_output=True)
    return np.asarray(Image.open(sorted(out.glob("f*.png"))[0]).convert("RGB")).astype(int)


def main():
    td = pathlib.Path(tempfile.mkdtemp())
    res = {}
    for t in TIMES:
        ref = frame("forward_plus", t, td)
        row = {}
        for m in ("mobile", "gl_compatibility"):
            im = frame(m, t, td)
            diff = np.abs(im - ref).max(axis=2) > 0
            row[m] = {"changed_px": int(diff.sum()), "share": round(float(diff.mean()), 5)}
        res[str(t)] = row
    (ENTRY / "assets/renderers.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res))
    shutil.rmtree(td)


if __name__ == "__main__":
    main()
