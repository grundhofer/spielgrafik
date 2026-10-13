#!/usr/bin/env python3
"""Vergleichsbild assets/clash_compare.png: Dachs mit Attribut-Clash (setzt INK/BRIGHT seiner Zellen, wie in der
Demo) und ohne (--noclash: Sprite übernimmt die Farben der Zellen, die es überdeckt), je vor der Hauswand
(t = 2,0 s) und am Ziel vor dem Wasser (t = 5,0 s). Ausschnitt 96×72 Bildpunkte, ×4."""
import pathlib, subprocess, tempfile

from PIL import Image, ImageDraw

ENTRY = pathlib.Path(__file__).resolve().parent.parent


def frames(extra):
    td = tempfile.mkdtemp()
    subprocess.run(["godot", "--path", str(ENTRY / "demo"), "--position", "20000,20000", "--write-movie",
                    f"{td}/f.png", "--fixed-fps", "30", "--quit-after", "152", "--", *extra],
                   capture_output=True, check=True)
    return td


def main():
    runs = {"mit Clash (Demo)": frames([]), "ohne Attributwechsel": frames(["--noclash"])}
    shots = [(59, 32 + 4, 24 + 72, "t = 2,0 s"), (149, 32 + 72, 24 + 72, "t = 5,0 s")]
    sc = 4
    w, h = 96, 72
    out = Image.new("RGB", (len(shots) * len(runs) * (w * sc + 8), h * sc + 24), (40, 40, 40))
    d = ImageDraw.Draw(out)
    x = 0
    for i, x0, y0, label in shots:
        for name, td in runs.items():
            im = Image.open(f"{td}/f{i:08d}.png").convert("RGB").crop((x0, y0, x0 + w, y0 + h))
            out.paste(im.resize((w * sc, h * sc), Image.NEAREST), (x, 24))
            d.text((x + 4, 6), f"{name}, {label}", fill=(255, 255, 255))
            x += w * sc + 8
    out.save(ENTRY / "assets/clash_compare.png")


if __name__ == "__main__":
    main()
