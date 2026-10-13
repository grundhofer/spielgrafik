#!/usr/bin/env python3
"""Misst, wie deutlich Line-Boil und Umgebungsanimationen im Bild stehen.

    .venv/bin/python styles/bleistift-skizze/scripts/measure_fx.py [--keep DIR]

Rendert die Demo zweimal (mit und ohne Line-Boil, Schalter --no-boil) und gibt aus:
  - Boil: Anteil der Pixel der Zeichnung (ohne Dachs, Effekte und Notizen), die sich zwischen zwei Fassungen
    (3 Takte Abstand) um mehr als 24 Stufen ändern, und Anteil, der sich zwischen Boil an/aus im selben Takt ändert.
  - Effekte (ohne Boil): Anteil geänderter Pixel (> 24 Stufen) je Bereich zwischen Bildern im Abstand von 0,5 s.
Ergebnis: assets/measure_fx.json
"""
import argparse, json, pathlib, sys, tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from render_frames import render  # noqa: E402

SD = pathlib.Path(__file__).resolve().parents[1]
# Bereiche in Bildschirmpixeln: x0, y0, x1, y1
REGIONS = {
    "Rauch": (85, 30, 190, 118),
    "Leuchtturmstrahl (Himmel)": (470, 100, 1095, 190),
    "Laternenschein": (300, 70, 470, 250),
    "Wasser rechts": (740, 345, 935, 470),
    "Wasser unter den Booten": (560, 395, 720, 470),
    "Möwen (Himmel oben)": (560, 50, 1000, 110),
}
STILL = (900, 230, 1240, 340)   # Felsen unter dem Leuchtturm: ohne Effekte (Kontrolle)


def load(p):
    return np.asarray(Image.open(p).convert("RGB"), np.int16)


def share(a, b, box=None):
    d = np.abs(a - b).max(2) > 24
    if box:
        x0, y0, x1, y1 = box
        d = d[y0:y1, x0:x1]
    return float(d.mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep")
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as td:
        base = pathlib.Path(a.keep or td)
        on, e1 = render(base / "boil", 180)
        off, e2 = render(base / "noboil", 180, None, ["--no-boil"])
        if e1 or e2:
            raise SystemExit("Godot-Fehler: " + (e1 + e2)[0])
        # Zeichnung ohne Dachs/Effekte/Notizen: Maske aus Bereichen, die sich ohne Boil nie ändern
        offs = [load(p) for p in off[::15]]
        moving = np.zeros(offs[0].shape[:2], bool)
        for i in range(len(offs) - 1):
            moving |= np.abs(offs[i + 1] - offs[i]).max(2) > 8
        draw = np.zeros_like(moving)
        draw[38:576, 32:1248] = True
        mask = draw & ~moving
        boil_phase = []
        boil_vs_off = []
        for i in range(30, 170, 9):
            b0, b1 = load(on[i]), load(on[i + 3])
            d = np.abs(b1 - b0).max(2) > 24
            boil_phase.append(float(d[mask].mean()))
            d2 = np.abs(load(on[i]) - load(off[i])).max(2) > 24
            boil_vs_off.append(float(d2[mask].mean()))
        fx = {}
        for name, box in REGIONS.items():
            vals = [share(offs[i], offs[i + 1], box) for i in range(len(offs) - 1)]
            fx[name] = {"mean": round(float(np.mean(vals)), 4), "max": round(float(np.max(vals)), 4)}
        still = [share(offs[i], offs[i + 1], STILL) for i in range(len(offs) - 1)]
    res = {"boil_change_between_phases": round(float(np.mean(boil_phase)), 4),
           "boil_vs_off": round(float(np.mean(boil_vs_off)), 4),
           "drawing_mask_share": round(float(mask[38:576, 32:1248].mean()), 3),
           "fx_change_per_0_5s": fx,
           "still_area_without_boil": round(float(np.mean(still)), 4)}
    (SD / "assets/measure_fx.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(f"Boil: {res['boil_change_between_phases'] * 100:.1f} % der Zeichnungspixel ändern sich je Fassungswechsel "
          f"(> 24 Stufen), {res['boil_vs_off'] * 100:.1f} % gegenüber ohne Boil "
          f"(gemessen auf {res['drawing_mask_share'] * 100:.0f} % der Zeichnung ohne Dachs/Effekte)")
    for k, v in fx.items():
        print(f"  {k}: {v['mean'] * 100:.1f} % je 0,5 s (bis {v['max'] * 100:.1f} %)")
    print(f"  ruhiger Bereich ohne Boil: {res['still_area_without_boil'] * 100:.2f} %")


if __name__ == "__main__":
    main()
