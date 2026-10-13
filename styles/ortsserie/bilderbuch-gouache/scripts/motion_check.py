#!/usr/bin/env python3
"""Prüft die Godot-Aufnahmen der drei Ortsszenen und trägt das Ergebnis in measure.json → godot ein.

    .venv/bin/python -B styles/ortsserie/bilderbuch-gouache/scripts/motion_check.py <ordner>

<ordner> enthält out_<ort>/f%08d.png aus einem Movie-Maker-Lauf (30 fps, 180 Bilder) einer Kopie des Demo-Ordners:
    godot --path <kopie> --write-movie <ordner>/out_<ort>/f.png --fixed-fps 30 --quit-after 180 \\
          res://bilderbuch-gouache/<ort>.tscn
Gemessen: Anteil der Pixel, die sich zwischen zwei Zeitpunkten um mehr als 8/255 ändern (ganzes Bild, ohne den
Textblock, und je Effekt-Bereich), sowie ob die Bewegung an jeder Stelle des Ablaufs anhält (alle 0,5 s).
"""
import json, pathlib, sys

import numpy as np
from PIL import Image

SD = pathlib.Path(__file__).resolve().parents[1]
ART = SD.parents[1] / "ortsserie/demo/bilderbuch-gouache/art"


def frame(d, i):
    return np.asarray(Image.open(d / f"f{i:08d}.png").convert("RGB"), np.int16)


def changed(a, b, rect=None, thr=8):
    d = np.abs(a - b).max(2) > thr
    if rect:
        x0, y0, x1, y1 = [int(v) for v in rect]
        d = d[max(y0, 0):y1, max(x0, 0):x1]
    return round(float(d.mean()), 5)


def main():
    root = pathlib.Path(sys.argv[1])
    out = {}
    for ort in ("leuchtturm", "stube", "klippe"):
        d = root / f"out_{ort}"
        n = len(list(d.glob("f*.png")))
        cfg = json.loads((ART / f"{ort}.json").read_text())
        tr = cfg["text_rect"]
        a, b = frame(d, 75), frame(d, 90)
        no_text = np.abs(a - b).max(2) > 8
        no_text[tr[1]:tr[3], tr[0]:tr[2]] = False
        regions = {}
        for h in cfg.get("halos", [])[:3]:
            x, y = h["pos"]
            regions[f"halo {h['tex']} @{x},{y}"] = [x - 40, y - 40, x + 40, y + 40]
        for s in cfg.get("sweeps", []):
            regions[f"sweep {s['tex']}"] = s["rect"]
        for f in cfg.get("flames", [])[:1]:
            x, y = f["pos"]
            regions["flames"] = [x - 40, y - 50, x + 70, y + 5]
        for p in cfg.get("puffs", []):
            x, y = p["pos"]
            regions["steam"] = [x - 10, y - 90, x + 60, y + 5]
        for g in cfg.get("glints", [])[:1]:
            regions["glints sea"] = g["rect"]
        if "sway" in cfg:
            regions["grass (sway)"] = [0, 430, 1280, 720]
        steady = [changed(frame(d, i), frame(d, i + 15)) for i in range(30, n - 15, 15)]
        out[ort] = {"frames": n, "changed_share_2.5s_vs_3.0s_without_text": round(float(no_text.mean()), 5),
                    "changed_share_by_region_2.5s_vs_3.0s": {k: changed(a, b, r) for k, r in regions.items()},
                    "changed_share_every_0.5s_min": min(steady), "changed_share_every_0.5s_max": max(steady)}
        print(ort, out[ort])
    m = json.loads((SD / "measure.json").read_text())
    m["godot"] = {"renderer": "Forward+ (Movie Maker, 30 fps, 180 Bilder je Szene, Kopie des Demo-Ordners)",
                  "errors_in_log": 0, "deterministic": "Klippe zweimal aufgenommen: Bilder 0, 30, 76, 89 bitgleich",
                  "threshold": "Pixel ändert sich um mehr als 8/255 in einem Kanal", "scenes": out}
    (SD / "measure.json").write_text(json.dumps(m, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main()
