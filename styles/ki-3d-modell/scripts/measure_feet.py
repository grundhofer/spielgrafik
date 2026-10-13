#!/usr/bin/env python3
"""Füße und Kopf des KI-Dachses in der Aufnahme messen (PIPELINE.md → Figuren und Animation).

1. Knochenpunkte: demo/main.gd --measure schreibt je Bild die Bildlage der Fußspitzen (Ballen, Knochenspitze
   foot.L/foot.R) samt Höhe über dem Kai und des Kopfgelenks. Ein Fuß gilt als aufgesetzt, wenn seine
   Knochenspitze höchstens 4 mm über ihrer Ruhehöhe (20,1 mm) liegt. Gemessen wird, wie weit ein aufgesetzter
   Fuß von Bild zu Bild im Bild wandert (Soll: höchstens 1 px).
2. Silhouetten: demo/main.gd --mask rendert nur den Dachs weiß auf Schwarz. Gemessen werden die unterste und
   oberste weiße Zeile je Bild (Fußlinie und Kopf) und der größte Sprung von Bild zu Bild.

    godot --path demo --write-movie <tmp>/mv/f.png --fixed-fps 30 --quit-after 180 -- --measure --no-ui | grep '^M ' > <tmp>/measure.txt
    godot --path demo --write-movie <tmp>/mask/f.png --fixed-fps 30 --quit-after 180 -- --mask
    .venv/bin/python styles/ki-3d-modell/scripts/measure_feet.py <tmp>/measure.txt <tmp>/mask > styles/ki-3d-modell/assets/measure/feet_report.txt
"""
import sys, glob, pathlib
import numpy as np
from PIL import Image

REST = 0.0201
TOL = 0.004

rows = []
for line in open(sys.argv[1]):
    p = line.split()
    d = {"frame": int(p[1]), "t": float(p[2])}
    for i in range(3, len(p), 4):
        d[p[i]] = (float(p[i + 1]), float(p[i + 2]), float(p[i + 3]))
    rows.append(d)

print("Knochenpunkte (Bildlage in px, 1280×720), aufgesetzt = Spitze <= %.1f mm über Kai" % ((REST + TOL) * 1000))
phases = {"Laufen (bis 3,15 s)": (0, 3.15), "Bremsen (3,15-3,6 s)": (3.15, 3.6),
          "Überblenden Walk→Idle (3,6-4,4 s)": (3.6, 4.4), "Stehen/Idle (ab 4,4 s)": (4.4, 9)}
worst = {k: 0.0 for k in phases}
for a, b in zip(rows, rows[1:]):
    for foot in ("foot.L", "foot.R"):
        fa, fb = a[foot], b[foot]
        if fa[2] <= REST + TOL and fb[2] <= REST + TOL:
            dpx = float(np.hypot(fb[0] - fa[0], fb[1] - fa[1]))
            for k, (t0, t1) in phases.items():
                if t0 <= b["t"] < t1:
                    worst[k] = max(worst[k], dpx)
for k, v in worst.items():
    print(f"  {k:36s} größte Wanderung eines aufgesetzten Fußes: {v:.2f} px/Bild")

# Standphasen: zusammenhängende Bilder mit aufgesetztem Fuß, Spanne der Bildlage
print("Standphasen im Laufen (Fuß, Bilder, Spanne x/y in px):")
for foot in ("foot.L", "foot.R"):
    run = []
    for r in rows + [None]:
        on = r is not None and r[foot][2] <= REST + TOL and r["t"] < 3.6
        if on:
            run.append(r)
        elif run:
            if len(run) >= 2:
                xs = [q[foot][0] for q in run]; ys = [q[foot][1] for q in run]
                print(f"  {foot} t {run[0]['t']:.2f}-{run[-1]['t']:.2f} s  {len(run):2d} Bilder  "
                      f"x {max(xs) - min(xs):.2f}  y {max(ys) - min(ys):.2f}")
            run = []

files = sorted(glob.glob(str(pathlib.Path(sys.argv[2]) / "f*.png")))
bot, top = [], []
for f in files:
    a = np.array(Image.open(f).convert("L")) > 128
    ys = np.where(a.any(1))[0]
    bot.append(ys.max() if len(ys) else -1)
    top.append(ys.min() if len(ys) else -1)
bot, top = np.array(bot), np.array(top)
t = np.arange(len(files)) / 30.0
print("Silhouetten (%d Bilder): Fußlinie = unterste weiße Zeile, Kopf = oberste" % len(files))
for k, (t0, t1) in phases.items():
    m = (t >= t0) & (t < t1)
    if m.sum():
        print(f"  {k:36s} Fußlinie {bot[m].min()}-{bot[m].max()}  Kopf {top[m].min()}-{top[m].max()}")
st = t >= 4.4
print("  größter Sprung der Fußlinie von Bild zu Bild im Stehen: %d px" % np.abs(np.diff(bot[st])).max())
print("  größter Sprung des Kopfes von Bild zu Bild (alle Bilder): %d px" % np.abs(np.diff(top)).max())
print("  Dachshöhe am Ende: %d px" % (bot[-1] - top[-1]))
