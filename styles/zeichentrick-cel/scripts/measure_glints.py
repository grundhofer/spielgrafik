#!/usr/bin/env python3
"""Prüft im gerenderten Godot-Bild, dass die Glitzerstriche nur auf Wasser liegen (nicht auf Holz oder Booten).

    godot --path styles/zeichentrick-cel/demo --write-movie <tmp>/f.png --fixed-fps 30 --quit-after 180 -- --probe-glints
    godot --path styles/zeichentrick-cel/demo --write-movie <full>/f.png --fixed-fps 30 --quit-after 180
    .venv/bin/python styles/zeichentrick-cel/scripts/measure_glints.py <tmp> [<full>]
(Fenster mit --position 20000,20000 außerhalb des Bildschirms öffnen wie tools/capture.py; ein verdecktes Fenster
liefert unter macOS ab einem Punkt nur noch dasselbe Bild.)

Der Prüfschalter --probe-glints zeigt vor Magenta nur die Glitzerebene und darüber die Boote ohne Spiegelbild (wie im
Spiel liegt der Glitzer unter den Booten). Glitzerpixel sind die exakten Strichfarben 255/204/133 (Widerschein) und
158/189/235 (Wasser). Geprüft wird jede Zeichnung (jedes zweite Videobild) gegen
  - eine Holzmaske aus assets/bg.png, unabhängig von der Wassermaske des Spiels gebaut: braune Pixel (Farbton < 45°
    oder > 340°, Sättigung > 0,25, Helligkeit < 0,56) und dunkle, wenig gesättigte Pixel (Sättigung < 0,3,
    Helligkeit < 0,33) im Wasserband; davon nur Flächen, die mindestens 10 px hoch sind (die Streifen des
    Sonnen-Widerscheins sind ebenfalls bräunlich, aber flach), um 1 px verbreitert (Steg, Pfähle, Laternenpfahl,
    Poller, Fässer),
  - die Boote im selben Bild (alle Pixel, die weder Magenta noch Glitzer sind): Ist die normale Aufnahme <full>
    angegeben, wird gezählt, wie viele Pixel in den Bootsflächen dort die exakte Glitzerfarbe haben (Soll 0).
Ergebnis: assets/measure_glints.json
"""
import json, pathlib, sys

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_water_mask import hsv  # noqa: E402
from celutil import components, max_filter  # noqa: E402

COLS = {"orange": (255, 204, 133), "blue": (158, 189, 235)}
BAND = (280, 360, 1110, 560)


def wood_mask():
    rgb = np.array(Image.open(ROOT / "assets/bg.png").convert("RGB")).astype(np.float64)
    H, S, V = hsv(rgb)
    brown = ((H < 45) | (H > 340)) & (S > 0.25) & (V < 0.56)
    dark = (S < 0.3) & (V < 0.33)
    m = np.zeros(H.shape, bool)
    x0, y0, x1, y1 = BAND
    m[y0:y1, x0:x1] = (brown | dark)[y0:y1, x0:x1]
    comp = components(m)
    keep = np.zeros_like(m)
    for i in np.unique(comp[m]):
        ys = np.where(comp == i)[0]
        if ys.max() - ys.min() + 1 >= 10:
            keep |= comp == i
    return max_filter(keep.astype(np.uint8), 1).astype(bool)


def main():
    tmp = pathlib.Path(sys.argv[1])
    files = sorted(tmp.glob("f*.png"))
    full = sorted(pathlib.Path(sys.argv[2]).glob("f*.png")) if len(sys.argv) > 2 else None
    wood = wood_mask()
    res = {"ticks": 0, "ticks_with_wood": 0, "strokes_on_wood": 0, "max_wood_strokes_tick": 0,
           "glint_px_on_boats": 0, "strokes_visible_mean": 0.0, "examples": []}
    vis = []
    for i in range(0, len(files), 2):
        a = np.array(Image.open(files[i]).convert("RGB")).astype(np.int16)
        g = np.zeros(a.shape[:2], bool)
        for c in COLS.values():
            g |= (np.abs(a - np.array(c)).sum(-1) <= 3)
        magenta = np.abs(a - np.array([255, 0, 255])).sum(-1) <= 3
        boats = ~magenta & ~g
        comp = components(g)
        n_strokes = int(comp.max())
        vis.append(n_strokes)
        on_wood = np.unique(comp[g & wood])
        on_wood = on_wood[on_wood > 0]
        res["ticks"] += 1
        if len(on_wood):
            res["ticks_with_wood"] += 1
            res["strokes_on_wood"] += int(len(on_wood))
            res["max_wood_strokes_tick"] = max(res["max_wood_strokes_tick"], int(len(on_wood)))
            if len(res["examples"]) < 10:
                ys, xs = np.where(np.isin(comp, on_wood))
                res["examples"].append({"frame": i, "x": int(xs.mean()), "y": int(ys.mean())})
        if full:
            b = np.array(Image.open(full[i]).convert("RGB")).astype(np.int16)
            gb = np.zeros(g.shape, bool)
            for c in COLS.values():
                gb |= (np.abs(b - np.array(c)).sum(-1) <= 3)
            res["glint_px_on_boats"] += int((gb & boats).sum())
        else:
            res["glint_px_on_boats"] = None
    res["strokes_visible_mean"] = round(float(np.mean(vis)), 2)
    res["strokes_visible_min_max"] = [int(min(vis)), int(max(vis))]
    (ROOT / "assets/measure_glints.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
