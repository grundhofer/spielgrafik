#!/usr/bin/env python3
"""Rendert die Parameter-Extreme des Porträts einzeln in Godot und setzt sie zu einem Blatt zusammen.

    .venv/bin/python styles/lebendes-portraet/tools/pose_sheet.py

Je Pose ein Godot-Lauf mit `-- --measure --pose=<name>` (nur Figur vor Magenta), Ausschnitt um den Kopf.
Ausgabe: assets/pose_sheet.png (Prüfbild und Katalog-Asset).
"""
import json, pathlib, re, subprocess, sys, tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent.parent
DEMO = HERE / "demo"
POSES = [("rest", "Ruhe"), ("turn_l", "Kopf X -1"), ("turn_r", "Kopf X +1"), ("nod", "Kopf Y +1"),
         ("tilt", "Neigung +1"), ("half", "Augen 0,5"), ("blink", "Augen 0"), ("mouth_half", "Mund 0,5"),
         ("mouth", "Mund 1"), ("gaze_r", "Blick rechts")]


def main():
    rig = json.loads((HERE / "assets" / "rig.json").read_text())
    m = re.search(r'\[node name="Portrait".*?\nposition = Vector2\(([-\d.]+), ([-\d.]+)\)', (DEMO / "main.tscn").read_text(), re.S)
    px, py = (float(m.group(1)), float(m.group(2))) if m else (0.0, 0.0)
    k = rig["scale"]
    hl = rig["layers"]["head"]
    x0, y0 = hl["offset"][0] + px - 10, hl["offset"][1] + py - 10
    box = (int(x0), int(max(0, y0)), int(x0 + hl["size"][0] + 20), int(y0 + hl["size"][1] + 4))
    tiles = []
    # neue oder geänderte PNGs erst importieren (ohne Editor nutzt Godot sonst den alten Import)
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    with tempfile.TemporaryDirectory() as td:
        for name, label in POSES:
            out = pathlib.Path(td) / name
            out.mkdir()
            r = subprocess.run(["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
                                "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", "3",
                                "--", "--measure", f"--pose={name}"], capture_output=True, text=True)
            if re.search(r"\bERROR\b|SCRIPT ERROR", r.stdout + r.stderr):
                sys.exit(f"Godot-Fehler bei {name}")
            im = Image.open(sorted(out.glob("f*.png"))[-1]).convert("RGB").crop(box)
            a = np.asarray(im).copy()
            mag = (a[..., 0] > 200) & (a[..., 2] > 200) & (a[..., 1] < 60)
            a[mag] = (46, 48, 66)
            im = Image.fromarray(a)
            tiles.append((im, label))
    s = 0.62
    tw, th = int(tiles[0][0].width * s), int(tiles[0][0].height * s)
    cols = 5
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (tw * cols, (th + 26) * rows), (30, 31, 44))
    d = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(str(DEMO / "fonts" / "Fraunces-var.ttf"), 15)
    for i, (im, label) in enumerate(tiles):
        x, y = (i % cols) * tw, (i // cols) * (th + 26)
        sheet.paste(im.resize((tw, th), Image.LANCZOS), (x, y))
        d.text((x + 8, y + th + 4), label, fill=(235, 225, 200), font=font)
    sheet.save(HERE / "assets" / "pose_sheet.png")
    print("assets/pose_sheet.png", sheet.size)


if __name__ == "__main__":
    main()
