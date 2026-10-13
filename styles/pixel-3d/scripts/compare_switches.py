#!/usr/bin/env python3
"""Vergleichsschalter: Wie stark trägt jedes Merkmal zum Bild bei?

    .venv/bin/python styles/pixel-3d/scripts/compare_switches.py TMP [--frames 60,144]

Nimmt die Demo mit jedem Schalter einzeln auf (scripts/probe.py, Temp-Ordner TMP/<schalter>) und vergleicht
die Fensterbilder (1280×720) mit der vollen Fassung: Anteil der Pixel, die sich um mehr als 24 Stufen
(größter Kanal) unterscheiden. Schreibt assets/preview/switches.png (Ausschnitte nebeneinander) und gibt
die Zahlen aus. Schalter: --no-toon (weiches Lambert), --no-outline, --no-highlight, --no-palette, --no-fog.
"""
import argparse
import pathlib
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROBE = ROOT / "scripts" / "probe.py"
SWITCHES = ["", "--no-toon", "--no-outline", "--no-highlight", "--no-palette", "--no-fog"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tmp")
    ap.add_argument("--frames", default="60,144")
    a = ap.parse_args()
    tmp = pathlib.Path(a.tmp)
    frames = [int(x) for x in a.frames.split(",")]
    imgs = {}
    for sw in SWITCHES:
        name = sw.strip("-") or "voll"
        out = tmp / name
        cmd = [sys.executable, str(PROBE), str(out), "--no-dump", "--frames", a.frames, "--"] + ([sw] if sw else [])
        subprocess.run(cmd, check=True, capture_output=True)
        imgs[name] = {k: np.asarray(Image.open(out / "movie" / f"f{k:08d}.png").convert("RGB"), dtype=np.int16)
                      for k in frames}
    full = imgs["voll"]
    for name, d in imgs.items():
        if name == "voll":
            continue
        vals = []
        for k in frames:
            diff = np.abs(d[k] - full[k]).max(axis=2)
            vals.append(f"Bild {k}: {(diff > 24).mean() * 100:.1f} %")
        print(f"{name:14s} " + ", ".join(vals))
    # Vorschau: Ausschnitt um Dachs, Boot und Leuchtturm aus dem Posterbild, alle Fassungen
    k = frames[-1]
    box = (240, 120, 960, 570)
    w, h = (box[2] - box[0]) // 2, (box[3] - box[1]) // 2
    names = list(imgs)
    sheet = Image.new("RGB", (w * 3, h * 2), "black")
    dr = ImageDraw.Draw(sheet)
    for i, name in enumerate(names):
        im = Image.fromarray(imgs[name][k].astype(np.uint8)).crop(box).resize((w, h), Image.NEAREST)
        x, y = (i % 3) * w, (i // 3) * h
        sheet.paste(im, (x, y))
        dr.rectangle([x, y, x + 8 * len(name) + 8, y + 14], fill="black")
        dr.text((x + 4, y + 2), name, fill="white")
    out = ROOT / "assets" / "preview" / "switches.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print("->", out)


if __name__ == "__main__":
    main()
