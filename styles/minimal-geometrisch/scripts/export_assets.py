#!/usr/bin/env python3
"""Belegbilder für den Katalog aus der Demo erzeugen (keine Eingabe-Assets: die Demo zeichnet alles per Code).

    .venv/bin/python styles/minimal-geometrisch/scripts/export_assets.py

  assets/construction.png  Bild 132 (4,4 s) mit --probe-construction: jede Grundform mit dünnem Umriss
  assets/palette.png       die acht Farben aus main.gd mit Namen und Hexwert
  assets/shapes.json       Zahl der Grundformen je Art im Bild bei 4,4 s (--probe-count)
"""
import json, pathlib, re, shutil, subprocess, sys, tempfile

from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent.parent
DEMO, ASSETS = HERE / "demo", HERE / "assets"
FRAME = 132


def godot(out_dir, frames, extra):
    out_dir.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
                        "--write-movie", str(out_dir / "f.png"), "--fixed-fps", "30", "--quit-after", str(frames),
                        "--", *extra], capture_output=True, text=True, timeout=600)
    log = r.stdout + r.stderr
    bad = [l for l in log.splitlines() if "ERROR" in l]
    if bad:
        sys.exit("Godot-Fehler: " + bad[0])
    return log


ASSETS.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as td:
    log = godot(pathlib.Path(td), FRAME + 1, ["--probe-construction", "--probe-count"])
    shutil.copy(pathlib.Path(td) / f"f{FRAME:08d}.png", ASSETS / "construction.png")
m = re.search(r"GRUNDFORMEN t=([\d.]+) gesamt=(\d+) (\{.*\})", log)
if not m:
    sys.exit("keine Zählung im Godot-Log")
shapes = {"t": float(m.group(1)), "total": int(m.group(2)), "by_kind": json.loads(m.group(3))}
(ASSETS / "shapes.json").write_text(json.dumps(shapes, indent=1, ensure_ascii=False) + "\n")

src = (DEMO / "main.gd").read_text()
pal = re.findall(r'^const (\w+) := Color\("#([0-9a-f]{6})"\)\s+# (.*)$', src, re.M)
sw, pad = 150, 16
im = Image.new("RGB", (len(pal) * sw, 190), "#" + pal[0][1])
d = ImageDraw.Draw(im)
font_path = DEMO / "fonts" / "Jost-wght.ttf"
f_big = ImageFont.truetype(str(font_path), 22)
f_small = ImageFont.truetype(str(font_path), 15)
for i, (name, hexv, _role) in enumerate(pal):
    x = i * sw
    d.rectangle([x, 0, x + sw - 1, 130], fill="#" + hexv)
    d.text((x + pad, 142), name, font=f_big, fill="#f2e8d4")
    d.text((x + pad, 168), "#" + hexv, font=f_small, fill="#a35d80")
im.save(ASSETS / "palette.png")
print(json.dumps(shapes, ensure_ascii=False))
print("Palette:", ", ".join(f"{n} #{h}" for n, h, _ in pal))
