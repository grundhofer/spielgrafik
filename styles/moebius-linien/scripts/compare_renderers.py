#!/usr/bin/env python3
"""Probelauf mit den Renderern Mobile und Compatibility: rendert Bild 60 (Totale) und 145 (Nahaufnahme),
misst den Anteil der Pixel, die vom Forward+-Bild um mehr als 8 Stufen abweichen, sammelt Fehler und
Warnungen und schreibt assets/preview/renderers.png (Spalten Forward+, Mobile, Compatibility).

    .venv/bin/python styles/moebius-linien/scripts/compare_renderers.py --tmp <Arbeitsordner>
"""
import argparse, json, pathlib, re, subprocess, sys

import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent
FRAMES = [60, 145]
METHODS = ["forward_plus", "mobile", "gl_compatibility"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tmp", required=True)
    a = ap.parse_args()
    tmp = pathlib.Path(a.tmp)
    imgs, logs = {}, {}
    for k, m in enumerate(METHODS):
        cmd = [sys.executable, str(HERE / "render_frames.py"), "--frames", ",".join(map(str, FRAMES)),
               "--out", str(tmp), "--tag", m, "--method", m] + (["--no-import"] if k else [])
        subprocess.run(cmd, check=True, capture_output=True)
        log = (tmp / f"{m}.log").read_text()
        logs[m] = sorted({l.strip()[:160] for l in log.splitlines() if re.search(r"ERROR|WARNING", l)})
        for f in FRAMES:
            imgs[(m, f)] = np.asarray(Image.open(tmp / f"{m}_f{f:03d}.png").convert("RGB"), dtype=np.int16)
    res = {"meldungen": logs}
    sheet = Image.new("RGB", (426 * 3, 240 * len(FRAMES)), "white")
    d = ImageDraw.Draw(sheet)
    for r, f in enumerate(FRAMES):
        base = imgs[("forward_plus", f)]
        for c, m in enumerate(METHODS):
            diff = np.abs(imgs[(m, f)] - base).max(axis=2)
            share = round(100 * float((diff > 8).mean()), 2)
            res[f"{m}_f{f}"] = share
            im = Image.fromarray(imgs[(m, f)].astype(np.uint8)).resize((426, 240), Image.LANCZOS)
            x, y = c * 426, r * 240
            sheet.paste(im, (x, y))
            label = f"{m} f{f}" + ("" if c == 0 else f": {share:.1f} % anders")
            d.rectangle([x, y, x + 8 + 6 * len(label), y + 16], fill="white")
            d.text((x + 4, y + 2), label, fill="black")
    sheet.save(ENTRY / "assets" / "preview" / "renderers.png", optimize=True)
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
