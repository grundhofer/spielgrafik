#!/usr/bin/env python3
"""Probelauf mit den drei Renderern (PIPELINE.md: mobile gilt nur nach diesem Test als geprüft).

    .venv/bin/python styles/toon-cel/scripts/compare_renderers.py [--frames 60,144]

Nimmt die Demo mit Forward+, Mobile und Compatibility auf (Temp-Verzeichnis), gibt Fehlerzeilen,
den Anteil abweichender Pixel (> 8 und > 24 Stufen) gegenüber Forward+ und die mittlere Helligkeit aus
und schreibt assets/preview/renderers.png (Spalten: Forward+, Mobile, Compatibility).
"""
import argparse, pathlib, subprocess, sys, tempfile
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
RENDERERS = ["forward_plus", "mobile", "gl_compatibility"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", default="60,144")
    a = ap.parse_args()
    frames = [int(f) for f in a.frames.split(",")]
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        for r in RENDERERS:
            p = subprocess.run([sys.executable, str(HERE / "snap.py"), str(td / r), "--frames", a.frames,
                                "--renderer", r], capture_output=True, text=True)
            msgs = [l for l in p.stdout.splitlines() if "ERROR" in l or "WARNING" in l]
            print(f"{r}: {len(msgs)} Meldungen" + "".join(f"\n   {m}" for m in msgs))
        w, h = 640, 360
        sheet = Image.new("RGB", (w * 3, h * len(frames)), "black")
        for j, f in enumerate(frames):
            base = np.asarray(Image.open(td / "forward_plus" / f"f{f:03d}.png").convert("RGB")).astype(int)
            for i, r in enumerate(RENDERERS):
                im = Image.open(td / r / f"f{f:03d}.png").convert("RGB")
                sheet.paste(im.resize((w, h), Image.LANCZOS), (i * w, j * h))
                if r == "forward_plus":
                    continue
                arr = np.asarray(im).astype(int)
                d = np.abs(arr - base).max(axis=2)
                print(f"Bild {f}, {r}: {(d > 8).mean() * 100:.1f} % der Pixel > 8 Stufen anders, "
                      f"{(d > 24).mean() * 100:.1f} % > 24; Helligkeit {base.mean():.0f} -> {arr.mean():.0f}")
        out = HERE.parent / "assets" / "preview" / "renderers.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(out)
        print(out)


if __name__ == "__main__":
    main()
