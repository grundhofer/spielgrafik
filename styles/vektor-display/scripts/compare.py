#!/usr/bin/env python3
"""Vergleichsschalter und Renderer der Vektor-Demo (PIPELINE.md -> Effekte messen, mobile prüfen).

    .venv/bin/python styles/vektor-display/scripts/compare.py [--keep DIR]

Rendert je Fassung 12 Bilder ab t = 3,2 s (das letzte entspricht dem Poster bei 3,6 s, mit Vorlauf für das
Nachleuchten) und vergleicht das letzte Bild mit der Standardfassung (Forward+, alle Effekte an):
Anteil der Pixel, die sich um mehr als 24 (0..255, größter Kanal) unterscheiden, und mittlere Abweichung.
Schalter: --noocclude (keine Verdeckung), --nopersist (kein Nachleuchten), --noglow (kein Glow),
Renderer: --rendering-method mobile und gl_compatibility.
"""
import argparse, pathlib, shutil, subprocess, sys, tempfile

import numpy as np
from PIL import Image

DEMO = pathlib.Path(__file__).resolve().parent.parent / "demo"
VARIANTS = {
    "standard": ([], []),
    "ohne Verdeckung": ([], ["--noocclude"]),
    "ohne Nachleuchten": ([], ["--nopersist"]),
    "ohne Glow": ([], ["--noglow"]),
    "Mobile": (["--rendering-method", "mobile"], []),
    "Compatibility": (["--rendering-method", "gl_compatibility"], []),
}


def render(td, name, pre, user):
    d = pathlib.Path(td) / name.replace(" ", "_")
    d.mkdir(parents=True, exist_ok=True)
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720", *pre,
           "--fixed-fps", "30", "--quit-after", "12", "--write-movie", str(d / "f.png"), "--", "--t0=3.2", *user]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    pngs = sorted(d.glob("f*.png"))
    return (np.asarray(Image.open(pngs[-1]).convert("RGB")).astype(int) if pngs else None), errs, pngs[-1] if pngs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep")
    a = ap.parse_args()
    td = a.keep or tempfile.mkdtemp(prefix="vektor-display-compare-")
    base, errs, _ = render(td, "standard", *VARIANTS["standard"])
    for name, (pre, user) in VARIANTS.items():
        if name == "standard":
            continue
        im, errs, path = render(td, name, pre, user)
        if im is None:
            print(f"{name}: keine Bilder; {errs[:2]}")
            continue
        diff = np.abs(im - base).max(axis=2)
        print(f"{name:18s}: {100 * (diff > 24).mean():5.2f} % Pixel > 24, mittlere Abweichung {np.abs(im - base).mean():.2f}"
              f"{'  FEHLER: ' + errs[0][:120] if errs else ''}  ({path})")
    if not a.keep:
        shutil.rmtree(td)


if __name__ == "__main__":
    sys.exit(main())
