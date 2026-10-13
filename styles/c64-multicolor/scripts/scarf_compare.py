#!/usr/bin/env python3
"""Vergleichsbild Schalfarbe: Rot (#68372B) gegen Hellrot (#9A6759) vor dem Steg, Standbild bei 5,0 s.

Rendert die Demo zweimal mit dem Prüfschalter --scarf=<Farbnummer> und schreibt assets/scarf_compare.png
(Ausschnitt um den Dachs, 6-fach vergrößert, Beschriftung oben).
"""
import pathlib, subprocess, sys, tempfile

from PIL import Image, ImageDraw

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from c64lib import *  # noqa

DEMO = ROOT / "demo"
BOX = (32 + 110, 20 + 92, 32 + 180, 20 + 146)      # Bildschirm x 110-180, y 92-146 im 384x240-Bild
S = 6


def main():
    tiles = []
    with tempfile.TemporaryDirectory() as td:
        for col in (RED, LRED):
            d = pathlib.Path(td) / str(col)
            d.mkdir()
            subprocess.run(["godot", "--path", str(DEMO), "--position", "20000,20000", "--write-movie",
                            str(d / "f.png"), "--fixed-fps", "30", "--quit-after", "2", "--", "--t0=5.0",
                            f"--scarf={col}"], capture_output=True, check=True)
            tiles.append(Image.open(sorted(d.glob("f*.png"))[-1]).convert("RGB").crop(BOX))
    w, h = tiles[0].size
    out = Image.new("RGB", (2 * w * S + 10, h * S + 30), (0, 0, 0))
    dr = ImageDraw.Draw(out)
    for k, (t, label) in enumerate(zip(tiles, ("Rot #68372B (vorher)", "Hellrot #9A6759 (gewählt)"))):
        out.paste(t.resize((w * S, h * S), Image.NEAREST), (k * (w * S + 10), 30))
        dr.text((k * (w * S + 10) + 10, 8), label, fill=(255, 255, 255))
    out.save(ROOT / "assets/scarf_compare.png")
    print("assets/scarf_compare.png")


if __name__ == "__main__":
    main()
