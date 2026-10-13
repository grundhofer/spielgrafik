#!/usr/bin/env python3
"""Probelauf mit den drei Renderern (PIPELINE.md: mobile gilt nur nach diesem Test als geprüft).

    .venv/bin/python styles/raymarching-sdf/scripts/compare_renderers.py [--times 0.5,4.8]

Nimmt Einzelbilder mit Forward+, Mobile und Compatibility auf (Temp-Verzeichnis), gibt Fehler- und
Warnzeilen aus, den Anteil abweichender Pixel (> 8 und > 24 Stufen) gegenüber Forward+ und schreibt
assets/preview/renderers.png (Spalten: Forward+, Mobile, Compatibility; Zeilen: Zeitpunkte).
"""
import argparse, pathlib, sys, tempfile
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from snap import snap  # noqa: E402

RENDERERS = ["forward_plus", "mobile", "gl_compatibility"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--times", default="0.5,4.8")
    a = ap.parse_args()
    times = [float(x) for x in a.times.split(",")]
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        shots = {}
        for r in RENDERERS:
            (td / r).mkdir()
            for tt in times:
                o, errs, _ = snap(td / r, tt, "" if r == "forward_plus" else r)
                shots[(r, tt)] = o
                print(f"{r} t={tt}: {len(errs)} Meldungen" + "".join(f"\n   {e}" for e in errs[:6]))
        w, h = 640, 360
        sheet = Image.new("RGB", (w * 3, h * len(times)), "black")
        for j, tt in enumerate(times):
            base = np.asarray(Image.open(shots[("forward_plus", tt)]).convert("RGB")).astype(int)
            for i, r in enumerate(RENDERERS):
                if shots[(r, tt)] is None:
                    continue
                im = Image.open(shots[(r, tt)]).convert("RGB")
                sheet.paste(im.resize((w, h), Image.LANCZOS), (i * w, j * h))
                if r == "forward_plus":
                    continue
                arr = np.asarray(im).astype(int)
                d = np.abs(arr - base).max(axis=2)
                print(f"t={tt}, {r}: {(d > 8).mean() * 100:.1f} % der Pixel > 8 Stufen anders, "
                      f"{(d > 24).mean() * 100:.1f} % > 24; Helligkeit {base.mean():.1f} -> {arr.mean():.1f}")
        out = HERE.parent / "assets" / "preview" / "renderers.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(out)
        print(out)


if __name__ == "__main__":
    main()
