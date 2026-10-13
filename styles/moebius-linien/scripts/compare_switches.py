#!/usr/bin/env python3
"""Vergleichsschalter: rendert die Totale (Bild 60) und die Nahaufnahme (Bild 145) voll und ohne je
einen Baustein des Looks und misst den Anteil der Pixel, die sich um mehr als 8 Stufen (von 255)
ändern. Zusätzlich zwei Läufe ohne Schalter (Bitgleichheit = deterministisch).
Schreibt assets/preview/switches_f060.png und switches_f145.png (Raster 4×2, je 426×240) und gibt
die Anteile als JSON aus.

    .venv/bin/python styles/moebius-linien/scripts/compare_switches.py --tmp <Arbeitsordner>
"""
import argparse, json, pathlib, subprocess, sys

import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent
FRAMES = [60, 145]
VARIANTS = [("voll", []), ("ohne Linien", ["--no-lines"]), ("ohne Schraffur", ["--no-hatch"]),
            ("ohne Schattenstufe", ["--no-shade"]), ("ohne Farbgrenzlinien", ["--no-ids"]),
            ("ohne Faltenlinien", ["--no-folds"]), ("voll, 2. Lauf", [])]
COLS = 4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tmp", required=True)
    a = ap.parse_args()
    tmp = pathlib.Path(a.tmp)
    imgs = {}
    for k, (name, args) in enumerate(VARIANTS):
        tag = f"v{k}"
        cmd = [sys.executable, str(HERE / "render_frames.py"), "--frames", ",".join(map(str, FRAMES)),
               "--out", str(tmp), "--tag", tag] + (["--no-import"] if k else []) + (["--"] + args if args else [])
        subprocess.run(cmd, check=True, capture_output=True)
        for f in FRAMES:
            imgs[(k, f)] = np.asarray(Image.open(tmp / f"{tag}_f{f:03d}.png").convert("RGB"), dtype=np.int16)
    res = {}
    for f in FRAMES:
        base = imgs[(0, f)]
        res[f] = {}
        sheet = Image.new("RGB", (426 * COLS, 240 * 2), "white")
        d = ImageDraw.Draw(sheet)
        for k, (name, _) in enumerate(VARIANTS):
            diff = np.abs(imgs[(k, f)] - base).max(axis=2)
            share = float((diff > 8).mean())
            res[f][name] = round(100 * share, 2)
            if k == len(VARIANTS) - 1:
                res[f]["bitgleich"] = bool((diff == 0).all())
            im = Image.fromarray(imgs[(k, f)].astype(np.uint8)).resize((426, 240), Image.LANCZOS)
            x, y = (k % COLS) * 426, (k // COLS) * 240
            sheet.paste(im, (x, y))
            label = name if k == 0 else f"{name}: {100 * share:.1f} %"
            d.rectangle([x, y, x + 8 + 6 * len(label), y + 16], fill="white")
            d.text((x + 4, y + 2), label, fill="black")
        sheet.save(ENTRY / "assets" / "preview" / f"switches_f{f:03d}.png", optimize=True)
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
