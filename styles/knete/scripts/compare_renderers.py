#!/usr/bin/env python3
"""Knete-Demo mit Forward+, Mobile und Compatibility rendern und vergleichen (für ratings.mobile).

    .venv/bin/python styles/knete/scripts/compare_renderers.py TMP_DIR [--t0 4.3]

Rendert je Renderer ein Bild (mit UI) und meldet Godot-Fehler sowie den Anteil der Pixel, die um mehr als
8 Stufen vom Forward+-Bild abweichen. Schreibt styles/knete/assets/measure/renderers.json und ein kleines
Vergleichsbild renderers.jpg (drei Bilder nebeneinander, 426 px breit).
"""
import argparse, json, pathlib, re, shutil, subprocess

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]


def render(out, method, t0):
    out.mkdir(parents=True, exist_ok=True)
    cmd = ["godot", "--path", str(ROOT / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
           "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", "1"]
    if method:
        cmd += ["--rendering-method", method]
    cmd += ["--", f"--t0={t0}"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    log = r.stdout + r.stderr
    errs = [l.strip() for l in log.splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR|WARNING", l)]
    return Image.open(sorted(out.glob("f*.png"))[0]).convert("RGB"), errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tmp")
    ap.add_argument("--t0", type=float, default=4.3)
    a = ap.parse_args()
    tmp = pathlib.Path(a.tmp)
    res, ims = {}, []
    base = None
    for name, method in (("forward_plus", ""), ("mobile", "mobile"), ("gl_compatibility", "gl_compatibility")):
        im, errs = render(tmp / name, method, a.t0)
        arr = np.asarray(im, dtype=np.int16)
        if base is None:
            base = arr
        diff = float((np.abs(arr - base).max(axis=2) > 8).mean())
        res[name] = {"changed_share": round(diff, 4), "errors_warnings": errs[:8],
                     "mean_luma": round(float(arr.mean()), 1)}
        ims.append(im.resize((426, 240), Image.LANCZOS))
    sheet = Image.new("RGB", (426 * 3, 240))
    for i, im in enumerate(ims):
        sheet.paste(im, (426 * i, 0))
    out = ROOT / "assets" / "measure"
    out.mkdir(parents=True, exist_ok=True)
    sheet.save(out / "renderers.jpg", quality=85)
    (out / "renderers.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(json.dumps(res, indent=1, ensure_ascii=False))
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
