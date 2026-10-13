"""Dachs-Sprites aus den Blender-Pässen (iso_render.py --job badger) -> Spriteblatt auf der iso-pixel-Palette.

  .venv/bin/python styles/iso-pixel/scripts/build_badger.py

Reihen im Blatt demo/art/badger.png (Zellen 64×64, Bodenpunkt in Bild 0 bei (26, 52)):
  0 walk_se  10 Bilder, ein Laufzyklus nach Südost; der Körper rückt im Bild mit vor (Wurzelbewegung in Blender,
             gemeinsames Raster), nach 10 Bildern genau um (10, 5) px. Godot schiebt die Figur je Zyklus um
             (10, 5) und spielt die Bilder ab: der Standfuß bleibt dadurch pixelgenau stehen.
  1 idle_se  12 Bilder (Atmen, 6 Bilder/s)
  2 idle_s   12 Bilder, zur Kamera gedreht
  3 wave_s   16 Bilder (10 Bilder/s)
Dazu demo/art/badger.json (Anker, Vorschub, Bildraten) und assets/badger/sheet_x4.png zur Ansicht.
"""
import json
import pathlib
import sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pixelize3d as P  # noqa: E402

ENTRY = HERE.parent
RDIR = ENTRY / "assets/render/badger"
ROWS = [("walk_se", 10), ("idle_se", 12), ("idle_s", 12), ("wave_s", 16)]
CELL = 64


def main():
    meta = json.load(open(RDIR / "badger.json"))
    ids = meta["ids"]
    k = meta["frames"][0]["k"]
    sheet = np.zeros((CELL * len(ROWS), CELL * max(n for _, n in ROWS), 4), np.uint8)
    feet = {}
    for r, (name, n) in enumerate(ROWS):
        for i in range(n):
            nm = f"{name}_{i:02d}"
            rgba, mat, tn, names = P.pixelize(RDIR / f"{nm}_id.png", RDIR / f"{nm}_nrm.png", k, ids)
            sheet[r * CELL:(r + 1) * CELL, i * CELL:(i + 1) * CELL] = rgba
            fr = next(f for f in meta["frames"] if f["name"] == nm)
            feet[nm] = fr.get("feet")
    out = ENTRY / "demo/art"
    out.mkdir(parents=True, exist_ok=True)
    Image.fromarray(sheet).save(out / "badger.png")
    info = {"cell": CELL, "anchor": meta["frames"][0]["anchor_px"], "cycle_px": meta["cycle_px"],
            "scale_px_per_m": meta["scale_px"], "stride_m": meta["stride_m"],
            "rows": {name: {"row": r, "frames": n} for r, (name, n) in enumerate(ROWS)}}
    json.dump(info, open(out / "badger.json", "w"), indent=1)
    (ENTRY / "assets/badger").mkdir(parents=True, exist_ok=True)
    Image.fromarray(sheet).save(ENTRY / "assets/badger/sheet.png")
    bg = Image.new("RGBA", (sheet.shape[1], sheet.shape[0]), (58, 52, 80, 255))
    bg.alpha_composite(Image.fromarray(sheet))
    bg.resize((sheet.shape[1] * 4, sheet.shape[0] * 4), Image.NEAREST).save(ENTRY / "assets/badger/sheet_x4.png")
    print("Blatt", sheet.shape, "Maßstab %.2f px/m, Schritt %.4f m" % (meta["scale_px"], meta["stride_m"]))


if __name__ == "__main__":
    main()
