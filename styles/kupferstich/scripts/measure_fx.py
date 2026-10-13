#!/usr/bin/env python3
"""Misst, ob die Umgebungsanimationen sichtbar sind: Anteil der Pixel je Bereich, die sich zwischen zwei Bildern im
Abstand von 0,5 s um mehr als 24 Stufen ändern (Mittel über die Aufnahme), mit der Figur ausgeblendet.

    .venv/bin/python styles/kupferstich/scripts/measure_fx.py

Bereiche (Plattenkoordinaten aus assets/scene.json und assets/plate_mask.png): Wasser, Himmel im Band des
Leuchtturmstrahls, Lichtkreis der Laterne (nur Himmel), Rauch über dem Schornstein, übriges Bild (soll ruhig sein).
Ergebnis: assets/measure_fx.json.
"""
import json, pathlib, tempfile

import numpy as np
from PIL import Image

from render_frames import render

SD = pathlib.Path(__file__).resolve().parents[1]


def main():
    lay = json.loads((SD / "scripts/layout.json").read_text())
    sc = json.loads((SD / "assets/scene.json").read_text())
    px, py, pw, ph = lay["plate"]
    mask = np.asarray(Image.open(SD / "assets/plate_mask.png").convert("RGB"), np.float32) / 255
    yy, xx = np.mgrid[0:ph, 0:pw]
    sky, water = mask[..., 0] > 0.8, mask[..., 1] > 0.8
    lx, ly = sc["lantern"]["center"]
    mx, my = sc["lamp"]["center"]
    cx, cy = sc["chimney_top"]
    regions = {
        "wasser": water,
        "strahl_himmel": sky & (np.abs(yy - my) < 70) & (xx < mx - 20),
        "laterne_himmel": sky & ((xx - lx) ** 2 + (yy - ly) ** 2 < 85 ** 2),
        "rauch": (xx > cx - 20) & (xx < cx + 200) & (yy < cy + 10),
    }
    used = np.zeros_like(sky)
    for r in regions.values():
        used |= r
    regions["rest_ohne_effekte"] = ~used & ~((xx - lx) ** 2 + (yy - ly) ** 2 < 95 ** 2) & (yy < ph - 2)
    with tempfile.TemporaryDirectory() as td:
        pngs, errs = render(td, 180, None, ["--probe-no-badger"])
        frames = [np.asarray(Image.open(p).convert("RGB"), np.int16)[py:py + ph, px:px + pw] for p in pngs[::15]]
    res = {}
    for name, r in regions.items():
        shares = [float((np.abs(frames[i + 1] - frames[i]).max(2) > 24)[r].mean()) for i in range(len(frames) - 1)]
        res[name] = {"pixels": int(r.sum()), "share_mean": round(float(np.mean(shares)), 4),
                     "share_max": round(float(np.max(shares)), 4)}
    (SD / "assets/measure_fx.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    for k, v in res.items():
        print(f"{k:18s} {v}")


if __name__ == "__main__":
    main()
