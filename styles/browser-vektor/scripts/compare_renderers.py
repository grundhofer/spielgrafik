#!/usr/bin/env python3
"""Vergleicht ein Standbild (t = 3,4 s) in Forward+, Mobile und Compatibility.

    .venv/bin/python styles/browser-vektor/scripts/compare_renderers.py
Ergebnis: assets/renderers.json (Anteil abweichender Pixel, mittlere Abweichung)."""
import json, pathlib, subprocess, tempfile
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent.parent


def still(td, method):
    out = td / method
    out.mkdir()
    r = subprocess.run(["godot", "--rendering-method", method, "--path", str(HERE / "demo"), "--position", "20000,20000",
                        "--resolution", "1280x720", "--write-movie", str(out / "f.png"), "--fixed-fps", "30",
                        "--quit-after", "2", "--", "--t0=3.4"], capture_output=True, text=True)
    log = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l or "WARNING" in l]
    return np.asarray(Image.open(out / "f00000000.png").convert("RGB"), dtype=np.int16), log


def main():
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        ref, log0 = still(td, "forward_plus")
        res = {"t": 3.4, "forward_plus_log": log0}
        for m in ("mobile", "gl_compatibility"):
            im, log = still(td, m)
            d = np.abs(im - ref).max(axis=2)
            res[m] = {"changed_any": round(float((d > 0).mean()), 4), "changed_gt24": round(float((d > 24).mean()), 4),
                      "mean_abs": round(float(np.abs(im - ref).mean()), 3), "log": log[:6]}
    (HERE / "assets" / "renderers.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
