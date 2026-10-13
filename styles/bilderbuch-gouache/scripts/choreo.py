#!/usr/bin/env python3
"""Rechnet den Ablauf der Figur für alle 180 Bilder (6 s, 30 fps) voraus: assets/timeline.json.
Demo (main.gd) und Prüfskript (measure_badger.py) lesen dieselbe Tabelle.

    .venv/bin/python styles/bilderbuch-gouache/scripts/choreo.py

Ablauf: 60 Laufbilder auf Zweien (15 Bilder/s, 4,0 s) mit gleichmäßigem Vorschub, Start bei walk_3, Ende bei
walk_6 (Durchgangspose, Standfuß unter dem Körper), dann 0,2 s Stehen (Seitenansicht) und ab 4,2 s die
Dreiviertel-Ansicht mit sanftem Atmen und zweimal Blinzeln. Beim Anhalten und Drehen ein kleines Nachfedern
(Stauchen/Strecken um den Fußpunkt) – das sanfte „Wackeln“ des Bilderbuch-Stils.
Jeder Eintrag: [Bogen, Bild, x (Zellkante links, ganze Pixel), sx, sy]."""
import json, math, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
FPS, N = 30, 180
WALK_IMAGES, WALK_START = 60, 3
END_CENTER = 560.0         # Figurenmitte beim Anhalten (vor dem Steg)
STAND_FRAMES = 6
BLINKS = [(159, 4), (172, 3)]   # (erstes Bild, Dauer in Bildern)


def main():
    b = json.loads((ROOT / "assets/badger.json").read_text())
    dx = b["walk_dx"]
    info = b["src_info"]["walk_6"]
    fig_center = ((info["x0"] + info["x1"]) / 2.0) * b["scale"] + 6   # PAD
    x_end = END_CENTER - fig_center
    x0 = x_end - (WALK_IMAGES - 1) * dx - b["stand_dx"]
    rows = []
    for f in range(N):
        t = f / FPS
        if f < WALK_IMAGES * 2:
            k = f // 2
            rows.append(["walk", (WALK_START + k) % 8, round(x0 + k * dx), 1.0, 1.0])
            continue
        xs = x0 + (WALK_IMAGES - 1) * dx + b["stand_dx"]
        if f < WALK_IMAGES * 2 + STAND_FRAMES:
            u = (f - WALK_IMAGES * 2) / STAND_FRAMES
            sq = 0.025 * math.sin(math.pi * u)            # kurzes Einfedern beim Anhalten
            rows.append(["idle", 0, round(xs), 1.0 + sq * 0.5, 1.0 - sq])
            continue
        xt = xs + b["turn_dx"]
        tt = t - (WALK_IMAGES * 2 + STAND_FRAMES) / FPS
        settle = 0.03 * math.exp(-tt * 5.0) * math.cos(tt * 14.0)   # Nachfedern nach dem Drehen
        breathe = 0.010 * math.sin(2 * math.pi * tt / 1.7)
        sy = 1.0 + settle + breathe
        sx = 1.0 - 0.5 * (settle + breathe)
        img = 1
        for s, d in BLINKS:
            if s <= f < s + d:
                img = 2
        rows.append(["idle", img, round(xt), round(sx, 5), round(sy, 5)])
    out = {"fps": FPS, "feet_y": json.loads((ROOT / "assets/scene.json").read_text())["feet_y"],
           "pivot_x": round(fig_center, 2), "rows": rows}
    (ROOT / "assets/timeline.json").write_text(json.dumps(out))
    print("ok x0", round(x0, 1), "x_end", round(x_end, 1), "rows", len(rows))


if __name__ == "__main__":
    main()
