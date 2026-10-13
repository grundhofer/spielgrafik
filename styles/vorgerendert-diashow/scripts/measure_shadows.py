"""Misst die harten Schatten der beiden Sonnen im gebackenen 256-Farben-Bild (Vergleichsschalter).

    # Messbilder: dieselbe Ansicht ohne Schatten der Hauptsonne bzw. der Gegensonne (alles andere gleich)
    for n in kai steg tuer; do for s in key fill; do
      blender -b --factory-startup -P styles/vorgerendert-diashow/blender/render_nodes.py -- \
          --node $n --what still --no-shadow $s --prefix meas_no$s; done; done
    for s in key fill; do
      blender -b --factory-startup -P styles/vorgerendert-diashow/blender/render_nodes.py -- \
          --node steg --what badger --frames 100 --no-shadow $s --prefix meas_badger_no$s; done
    .venv/bin/python styles/vorgerendert-diashow/scripts/measure_shadows.py

Schattenmaske aus den Rohbildern: Pixel, die ohne den Schatten einer Sonne um mehr als 15 % (mindestens 6 Stufen)
heller sind. Gemessen wird im gebackenen Bild: mit Schatten = Standbild base.png bzw. Bild 100 aus steg/badger.png
(genau diese Pixel zeigt Godot, siehe check_demo.py), ohne Schatten = Messbild mit derselben Palette und
Floyd-Steinberg gebacken. Abfall = 1 − mittlere Helligkeit (Y, 8 Bit) mit Schatten / ohne Schatten in der Maske.
Dachs-Schatten: zusätzlich nur Pixel, die der Dachs gegenüber der Umgebungsschleife derselben Phase abdunkelt,
ohne die Figur selbst (Deckungsmaske mask_0100.png).
Schreibt assets/shadow_measure.json.
"""
import json
import pathlib

import numpy as np
from PIL import Image

STYLE = pathlib.Path(__file__).resolve().parent.parent
RAW = STYLE / "assets" / "raw" / "render"
NODES = STYLE / "assets" / "nodes"
DATA = json.loads((STYLE / "demo" / "data" / "nodes.json").read_text())
LOOP_N = int(round(DATA["loop_s"] * DATA["fps"]))
J = 100      # Dachs-Bild: steht und winkt


def rgb(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(np.float64)


def lum(a):
    return a @ np.array([0.299, 0.587, 0.114])


def shadow_mask(lit, shad):
    yl, ys = lum(lit), lum(shad)
    return (yl - ys) > np.maximum(6.0, 0.15 * yl)


def bake_like(raw_path, pal_img):
    im = Image.open(raw_path).convert("RGB")
    return np.asarray(im.quantize(palette=pal_img, dither=Image.Dither.FLOYDSTEINBERG).convert("RGB")).astype(np.float64)


def stats(m, with_s, without_s, raw_with, raw_without):
    if not m.any():
        return {"pixels": 0}
    yw, yo = lum(with_s)[m].mean(), lum(without_s)[m].mean()
    rw, ro = lum(raw_with)[m].mean(), lum(raw_without)[m].mean()
    return {"pixels": int(m.sum()), "share": round(float(m.mean()), 4),
            "baked_Y_with": round(float(yw), 1), "baked_Y_without": round(float(yo), 1),
            "baked_drop": round(float(1 - yw / yo), 3), "raw_drop": round(float(1 - rw / ro), 3)}


def main():
    pal = np.asarray(Image.open(NODES / "palette.png").convert("RGB")).reshape(-1).tolist()
    pal_img = Image.new("P", (1, 1))
    pal_img.putpalette(pal)
    meta = json.loads((NODES / "nodes_meta.json").read_text())
    out = {}
    for name in DATA["nodes"]:
        raw = rgb(RAW / name / "loop_0000.png")
        base = rgb(NODES / name / "base.png")
        out[name] = {}
        for sun in ("key", "fill"):
            p = RAW / name / f"meas_no{sun}_0000.png"
            if not p.exists():
                continue
            raw_no = rgb(p)
            m = shadow_mask(raw_no, raw)
            out[name][sun] = stats(m, base, bake_like(p, pal_img), raw, raw_no)
    # Dachs auf dem Steg
    c = next(c for c in meta["nodes"]["steg"]["clips"] if c["kind"] == "badger")
    x, y, w, h = c["rect"]
    sheet = rgb(NODES / "steg" / c["file"])
    fr = sheet[(J // c["cols"]) * h:(J // c["cols"] + 1) * h, (J % c["cols"]) * w:(J % c["cols"] + 1) * w]
    raw_b = rgb(RAW / "steg" / f"badger_{J:04d}.png")
    raw_env = rgb(RAW / "steg" / f"loop_{J % LOOP_N:04d}.png")
    cover = np.asarray(Image.open(RAW / "steg" / f"mask_{J:04d}.png").convert("RGBA"))[..., 3] > 0
    darker = shadow_mask(raw_env, raw_b) & ~cover
    out["badger"] = {"frame": J}
    for sun in ("key", "fill"):
        p = RAW / "steg" / f"meas_badger_no{sun}_{J:04d}.png"
        if not p.exists():
            continue
        raw_no = rgb(p)
        m = shadow_mask(raw_no, raw_b) & darker
        mm = m[y:y + h, x:x + w]
        out["badger"][sun] = stats(mm, fr, bake_like(p, pal_img)[y:y + h, x:x + w], raw_b[y:y + h, x:x + w],
                                   raw_no[y:y + h, x:x + w])
        if mm.any():
            ys, xs = np.nonzero(mm)
            out["badger"][sun]["bbox"] = [int(xs.min() + x), int(ys.min() + y), int(xs.max() + x), int(ys.max() + y)]
    (STYLE / "assets" / "shadow_measure.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    for k, v in out.items():
        print(k, v)


if __name__ == "__main__":
    main()
