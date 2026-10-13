#!/usr/bin/env python3
"""Vergleicht die Demo unter Forward+, Mobile und Compatibility (gl_compatibility).

Aufruf aus dem Projektordner:
    .venv/bin/python styles/anime-visual-novel/tools/renderers.py [--at 3.0]

Rendert je Renderer ein Bild zum Zeitpunkt --at (feste Bildrate, wie capture.py) in ein Temp-Verzeichnis
und gibt die mittlere und maximale Abweichung zu Forward+ aus. Schreibt die drei Bilder nebeneinander
nach assets/raw/debug/renderers.jpg bzw. --out (nur zur Sichtprüfung, nicht im Git).
"""
import argparse, pathlib, subprocess, tempfile

import numpy as np
from PIL import Image

SD = pathlib.Path(__file__).resolve().parent.parent


def render(method, frames, out):
    cmd = ["godot", "--path", str(SD / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
           "--rendering-method", method, "--write-movie", str(out / "f.png"), "--fixed-fps", "30",
           "--quit-after", str(frames)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    files = sorted(out.glob("f*.png"))
    return (Image.open(files[-1]).convert("RGB") if files else None), errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--at", type=float, default=3.0)
    ap.add_argument("--out", default=str(SD / "assets" / "raw" / "debug" / "renderers.jpg"))
    a = ap.parse_args()
    frames = int(round(a.at * 30))
    ims = {}
    with tempfile.TemporaryDirectory() as td:
        for m in ("forward_plus", "mobile", "gl_compatibility"):
            d = pathlib.Path(td) / m
            d.mkdir()
            im, errs = render(m, frames, d)
            ims[m] = im
            print(f"{m}: {'Bild' if im else 'KEIN Bild'}, {len(errs)} Fehler" + (f" (erster: {errs[0][:120]})" if errs else ""))
    ref = np.asarray(ims["forward_plus"]).astype(np.int16)
    for m in ("mobile", "gl_compatibility"):
        if ims[m] is None:
            continue
        d = np.abs(np.asarray(ims[m]).astype(np.int16) - ref)
        print(f"{m} gegen forward_plus: mittlere Abweichung {d.mean():.2f}, max {d.max()}, "
              f"Anteil Pixel > 8: {(d.max(-1) > 8).mean():.3%}")
    sheet = Image.new("RGB", (1920, 360))
    for i, m in enumerate(("forward_plus", "mobile", "gl_compatibility")):
        if ims[m] is not None:
            sheet.paste(ims[m].resize((640, 360), Image.LANCZOS), (i * 640, 0))
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=85)
    print(f"geschrieben: {out}")


if __name__ == "__main__":
    main()
