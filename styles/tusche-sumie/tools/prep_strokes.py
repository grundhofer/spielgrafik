#!/usr/bin/env python3
"""Pinselstrich-Bogen (KI) -> einzelne Tusche-Elemente.

    .venv/bin/python styles/tusche-sumie/tools/prep_strokes.py            # Kandidaten + Übersicht
    .venv/bin/python styles/tusche-sumie/tools/prep_strokes.py --pick     # Auswahl laut assets/strokes_pick.json

Tuschedichte d = 1 - Helligkeit / Papierhelligkeit (weißes Papier des Bogens), Papierstruktur unter ink_floor
entfernt. Elemente = Zusammenhangskomponenten der leicht geweiteten Tuschemaske. Gespeichert wird RGB = Tusche,
A = Dichte, damit der multiplizierende Shader (ink_mul) Papier * (1 - A (1 - INK)) rechnet.
"""
import argparse, json

import numpy as np
from PIL import Image, ImageDraw

from components import label
from inkutil import ROOT, INK_RGB, blur

SCRATCH = None


def density(path, floor=0.05):
    rgb = np.asarray(Image.open(path).convert("RGB"), np.float32) / 255.0
    L = rgb.mean(axis=2)
    paper = np.quantile(L, 0.6)
    d = np.clip(1 - L / paper, 0, 1)
    return np.clip((d - floor) / (1 - floor), 0, 1)


def element(d, box, pad=6, mask=None):
    y0, x0, y1, x1 = box[:4]
    y0, x0 = max(0, y0 - pad), max(0, x0 - pad)
    y1, x1 = min(d.shape[0], y1 + pad), min(d.shape[1], x1 + pad)
    a = d[y0:y1, x0:x1].copy()
    if mask is not None:
        a *= mask[y0:y1, x0:x1]
    rgba = np.dstack([np.ones_like(a)[..., None] * INK_RGB, a[..., None]])
    return Image.fromarray((np.clip(rgba, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick", action="store_true")
    ap.add_argument("--scratch", default=str(ROOT / "assets/strokes_cand"))
    a = ap.parse_args()
    d = density(ROOT / "assets/raw/strokes.png")
    grown = blur((d > 0.04).astype(np.float32), 5.0) > 0.08
    boxes = [b for b in label(grown) if b[4] > 400]
    if not a.pick:
        out = __import__("pathlib").Path(a.scratch)
        out.mkdir(parents=True, exist_ok=True)
        prev = Image.open(ROOT / "assets/raw/strokes.png").convert("RGB")
        dr = ImageDraw.Draw(prev)
        for i, b in enumerate(boxes):
            element(d, b, mask=grown).save(out / f"c{i:02d}.png")
            dr.rectangle([b[1], b[0], b[3], b[2]], outline=(255, 0, 0), width=2)
            dr.text((b[1] + 3, b[0] + 3), str(i), fill=(255, 0, 0))
        prev.save(out / "overview.png")
        (out / "boxes.json").write_text(json.dumps(boxes))
        print(len(boxes), "Kandidaten ->", out)
        return
    pick = json.loads((ROOT / "assets/strokes_pick.json").read_text())
    fx = ROOT / "assets/fx"
    fx.mkdir(parents=True, exist_ok=True)
    dl = density(ROOT / "assets/raw/strokes.png", floor=0.015)     # für blasse Rauchfahnen
    for name, spec in pick.items():
        if isinstance(spec, int):
            el = element(d, boxes[spec], mask=grown)
        else:
            # feste Box [y0, x0, y1, x1] ohne Komponentenmaske, niedrige Schwelle (blasse Lasuren)
            src = dl if spec.get("pale") else d
            el = element(src, spec["box"], pad=0)
            if "anchor" in spec:
                # auf gemeinsame Fläche, Anker (Körper der Möwe) in die Mitte: Flügelschlag ohne Springen
                cw, ch = spec["canvas"]
                ax, ay = spec["anchor"]
                c = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
                c.paste(el, (cw // 2 - (ax - spec["box"][1]), ch // 2 - (ay - spec["box"][0])))
                el = c
        el.save(fx / f"{name}.png")
        print(name, spec, el.size)


if __name__ == "__main__":
    main()
