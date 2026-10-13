#!/usr/bin/env python3
"""Leitet aus der KI-Farbcode-Maske (assets/raw/mask.png) die Effektmasken und Lichtpunkte der Platte ab.

    .venv/bin/python styles/kupferstich/scripts/build_scene.py

Die Maske kam von gpt-image mit raw/bg2.png als Referenz und liegt deckungsgleich auf dem Stich (geprüft mit einer
Kantenüberlagerung, Versatz 0 px), daher keine Ausrichtung. Jedes Pixel bekommt den nächsten Farbcode; vereinzelte
Mischpixel an Codegrenzen (z. B. Orange zwischen Rot und Schwarz) fallen weg, weil für Punkte nur die größte
zusammenhängende Fläche zählt.
Ausgabe:
  assets/plate_mask.png  RGB in Plattengröße: R = Himmel, G = Wasser, B = Boote (weich verkleinert)
  assets/scene.json      Lichtpunkte und Schornstein in Plattenkoordinaten (Pixel), Horizont
Kopien in demo/art/.
"""
import json, shutil

import numpy as np
from PIL import Image

import inklib as K

CODES = {"sky": (0, 0, 255), "water": (0, 255, 255), "boat": (255, 0, 255), "window": (255, 255, 0),
         "lantern": (255, 128, 0), "lamp": (255, 0, 0), "chimney": (0, 255, 0), "other": (0, 0, 0)}


def components(mask):
    """Zusammenhangskomponenten (4er-Nachbarschaft) ohne SciPy: Liste von (n, ys, xs)."""
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    out = []
    cur = 0
    for y0, x0 in zip(*np.nonzero(mask)):
        if lab[y0, x0]:
            continue
        cur += 1
        stack = [(y0, x0)]
        lab[y0, x0] = cur
        ys, xs = [], []
        while stack:
            y, x = stack.pop()
            ys.append(y)
            xs.append(x)
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = cur
                    stack.append((yy, xx))
        out.append((len(ys), np.array(ys), np.array(xs)))
    return sorted(out, key=lambda c: -c[0])


def main():
    lay = K.LAYOUT
    x0, y0, x1, y1 = lay["src_crop"]
    px, py, pw, ph = lay["plate"]
    s = pw / (x1 - x0)
    m = np.asarray(Image.open(K.SD / "assets/raw/mask.png").convert("RGB")).astype(np.int32)
    names = list(CODES)
    cols = np.array([CODES[n] for n in names])
    lab = ((m[:, :, None, :] - cols[None, None]) ** 2).sum(-1).argmin(-1)

    def plate_xy(xs, ys):
        return [round(float((xs - x0) * s), 1), round(float((ys - y0) * s), 1)]

    scene = {"scale": s, "plate": [px, py, pw, ph]}
    for name in ("lantern", "lamp", "window"):
        n, ys, xs = components(lab == names.index(name))[0]
        scene[name] = {"center": plate_xy(xs.mean(), ys.mean()),
                       "radius": round(float(np.sqrt(n / np.pi) * s), 1),
                       "bbox": [round(float((xs.min() - x0) * s), 1), round(float((ys.min() - y0) * s), 1),
                                round(float((xs.max() - x0) * s), 1), round(float((ys.max() - y0) * s), 1)]}
    n, ys, xs = components(lab == names.index("chimney"))[0]
    top = ys.min()
    tx = xs[ys <= top + 4]
    scene["chimney_top"] = plate_xy(tx.mean(), top)
    sky = lab == names.index("sky")
    water = lab == names.index("water")
    cols_h = [int(np.nonzero(water[:, x])[0].min()) for x in range(water.shape[1]) if water[:, x].any()]
    scene["horizon_y"] = round(float((np.median(cols_h) - y0) * s), 1)

    planes = []
    for name in ("sky", "water", "boat"):
        a = (lab == names.index(name)).astype(np.float32)[y0:y1, x0:x1]
        planes.append(K.resize_f(a, (pw, ph), Image.BOX).clip(0, 1))
    rgb = np.stack(planes, -1)
    out = K.SD / "assets/plate_mask.png"
    Image.fromarray(np.clip(rgb * 255 + 0.5, 0, 255).astype(np.uint8)).save(out)
    (K.SD / "assets/scene.json").write_text(json.dumps(scene, indent=1))
    for f in (out, K.SD / "assets/scene.json"):
        shutil.copy(f, K.SD / "demo/art" / f.name)
    print(json.dumps(scene))


if __name__ == "__main__":
    main()
