"""Vorlage für das KI-Requisitenblatt: die aus Blender gepixelten Requisiten (pixelize3d) auf 384×256 Kunstpixeln,
×4 ohne Glättung vergrößert (1536×1024) auf Magenta. Die KI übermalt jedes Objekt an derselben Stelle im selben
Raster; build_props.py schneidet die Objekte an den hier gespeicherten Rechtecken wieder aus.

  .venv/bin/python styles/iso-pixel/scripts/props_layout.py <render-ordner> <ziel.png>
Schreibt zusätzlich <ziel>.json (Rechteck je Objekt in Kunstpixeln, Ankerpunkt).
"""
import json
import pathlib
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import pixelize3d as P  # noqa: E402

SCALE = 4
CANVAS = (384, 256)
# Lage (links oben, Kunstpixel) je Objekt im Blatt; großzügige Abstände
PLACE = {
    "cottage": (14, 40), "lighthouse": (112, 12), "boat_a": (168, 30), "boat_b": (238, 26),
    "barrel": (172, 170), "crates": (224, 160), "rope": (300, 176), "lantern": (334, 140),
}


def main(rdir, out):
    rdir = pathlib.Path(rdir)
    meta = json.load(open(rdir / "props.json"))
    sheet = np.zeros((CANVAS[1], CANVAS[0], 4), np.uint8)
    sheet[..., :3] = (255, 0, 255)
    sheet[..., 3] = 255
    boxes = {}
    for fr in meta["frames"]:
        n = fr["name"]
        rgba, mat, tn, names = P.pixelize(rdir / f"{n}_id.png", rdir / f"{n}_nrm.png", fr["k"], meta["ids"])
        ys, xs = np.nonzero(rgba[..., 3])
        x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        crop = rgba[y0:y1, x0:x1]
        px, py = PLACE[n]
        h, w = crop.shape[:2]
        m = crop[..., 3] > 0
        sheet[py:py + h, px:px + w][m] = crop[m]
        boxes[n] = {"x": int(px), "y": int(py), "w": int(w), "h": int(h),
                    "anchor": [fr["anchor_px"][0] - int(x0), fr["anchor_px"][1] - int(y0)]}
    Image.fromarray(sheet[..., :3]).resize((CANVAS[0] * SCALE, CANVAS[1] * SCALE), Image.NEAREST).save(out)
    Image.fromarray(sheet).save(str(out).replace(".png", "_1x.png"))
    json.dump({"scale": SCALE, "canvas": CANVAS, "boxes": boxes}, open(str(out).replace(".png", ".json"), "w"), indent=1)
    print(json.dumps(boxes))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
