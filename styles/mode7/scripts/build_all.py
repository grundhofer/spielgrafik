"""Baut alle Daten des Eintrags mode7 neu (deterministisch, ohne KI-Bilder).

Aufruf: .venv/bin/python styles/mode7/scripts/build_all.py [--raw <tmp>/spr] [--skip-blender]

1. Blender: Rohbilder der Sprite-Größenstufen (blender/render_sprites.py, Spezifikation sprites_spec.json)
2. build_plane.py: Mode-7-Kachelsatz und -Karte
3. build_backdrop.py: Horizontebenen BG1/BG2
4. build_sprites.py: Sprite-Atlas
5. CGRAM-Übersicht assets/cgram_sheet.png (16×16 Einträge, Bereiche beschriftet)
"""
import argparse
import pathlib
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
STYLE = HERE.parent
ROOT = STYLE.parent.parent
PY = sys.executable


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="")
    ap.add_argument("--skip-blender", action="store_true")
    a = ap.parse_args()
    raw = pathlib.Path(a.raw or tempfile.mkdtemp(prefix="mode7_spr_"))
    if not a.skip_blender:
        subprocess.run(["blender", "-b", "--factory-startup", "-P", str(STYLE / "blender/render_sprites.py"), "--",
                        "--spec", str(STYLE / "blender/sprites_spec.json"), "--out", str(raw)],
                       cwd=ROOT, check=True, capture_output=True)
    for s in ("build_plane.py", "build_backdrop.py"):
        subprocess.run([PY, str(HERE / s)], cwd=ROOT, check=True)
    subprocess.run([PY, str(HERE / "build_sprites.py"), str(raw)], cwd=ROOT, check=True)
    cg = np.asarray(Image.open(STYLE / "demo/art/cgram.png").convert("RGB"))[0]
    z = 24
    img = Image.new("RGB", (16 * z + 150, 16 * z), (20, 20, 28))
    d = ImageDraw.Draw(img)
    for i in range(256):
        x, y = (i % 16) * z, (i // 16) * z
        d.rectangle([x + 1, y + 1, x + z - 2, y + z - 2], fill=tuple(int(v) for v in cg[i]))
    for row, label in [(0, "BG3 Fenster"), (1, "BG2 Wolken"), (2, "BG1 Land"), (3, "BG1 Turm"),
                       (4, "Mode 7 (64..127)"), (8, "OBJ 0 Dachs"), (9, "OBJ 1 Boote"), (10, "OBJ 2 Haus"),
                       (11, "OBJ 3 Requisiten"), (13, "OBJ 5 Rauch (1/2 Add.)"), (14, "OBJ 6 Schein (1/2 Add.)"),
                       (15, "OBJ 7 Schatten (1/2 Add.)")]:
        d.text((16 * z + 6, row * z + 6), label, fill=(220, 220, 230))
    img.save(STYLE / "assets/cgram_sheet.png")
    print("fertig; Blender-Rohbilder in", raw)


if __name__ == "__main__":
    main()
