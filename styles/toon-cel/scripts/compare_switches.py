#!/usr/bin/env python3
"""Misst, wie viel jedes Stilmerkmal im Bild ausmacht (PIPELINE.md: Effekte mit Vergleichsschalter messen).

    .venv/bin/python styles/toon-cel/scripts/compare_switches.py [--frames 60,144] [--preview]

Nimmt die Demo mit und ohne Schalter auf (--no-post: keine Konturen aus der Nachbearbeitung,
--no-hull: keine Hüllenkontur um die Figur, --no-ids: keine Linien an Farbgrenzen, --no-toon: weiches
Lambert statt Stufenlicht) und gibt den Anteil der Pixel aus, die sich um mehr als 8 Stufen (0..255)
in einem Kanal unterscheiden; ohne UI-Bereich. Zwei Läufe ohne Schalter prüfen die Reproduzierbarkeit.
Mit --preview werden Vergleichsbilder nach assets/preview/ geschrieben.
"""
import argparse, pathlib, subprocess, sys, tempfile
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
SNAP = HERE / "snap.py"
PREVIEW = HERE.parent / "assets" / "preview"
SWITCHES = ["", "--no-post", "--no-hull", "--no-ids", "--no-toon"]


def render(out, frames, switch):
    args = [sys.executable, str(SNAP), str(out), "--frames", ",".join(map(str, frames))]
    if switch:
        args += ["--", switch]
    subprocess.run(args, check=True, capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", default="60,144")
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args()
    frames = [int(f) for f in a.frames.split(",")]
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        for i, sw in enumerate(SWITCHES):
            render(td / f"s{i}", frames, sw)
        render(td / "again", frames, "")
        for f in frames:
            base = np.asarray(Image.open(td / "s0" / f"f{f:03d}.png").convert("RGB")).astype(int)
            mask = np.ones(base.shape[:2], bool)
            if f >= 119:                       # Dialogkasten unten rechts ausnehmen
                mask[500:, 470:] = False
            mask[:90, :360] = False            # Ortsschild
            again = np.asarray(Image.open(td / "again" / f"f{f:03d}.png").convert("RGB")).astype(int)
            d0 = (np.abs(again - base).max(axis=2) > 0)[mask].mean() * 100
            print(f"Bild {f}: zweiter Lauf ohne Schalter: {d0:.3f} % der Pixel anders")
            for i, sw in enumerate(SWITCHES[1:], 1):
                im = np.asarray(Image.open(td / f"s{i}" / f"f{f:03d}.png").convert("RGB")).astype(int)
                d = (np.abs(im - base).max(axis=2) > 8)[mask].mean() * 100
                print(f"Bild {f}: {sw:10s} {d:5.1f} % der Pixel anders")
            if a.preview:
                PREVIEW.mkdir(parents=True, exist_ok=True)
                tiles = [Image.open(td / f"s{i}" / f"f{f:03d}.png").convert("RGB") for i in range(len(SWITCHES))]
                w, h = 640, 360
                sheet = Image.new("RGB", (w * 3, h * 2), "black")
                for i, t in enumerate(tiles):
                    sheet.paste(t.resize((w, h), Image.LANCZOS), ((i % 3) * w, (i // 3) * h))
                sheet.save(PREVIEW / f"switches_f{f:03d}.png")


if __name__ == "__main__":
    main()
