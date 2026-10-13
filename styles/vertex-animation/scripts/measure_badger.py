#!/usr/bin/env python3
"""Füße und Kopf des Dachses in der Demo messen (PIPELINE.md → Figuren und Animation).

    .venv/bin/python styles/vertex-animation/scripts/measure_badger.py [--tmp DIR]

Zwei Godot-Läufe mit fester Bildrate (180 Bilder, 30 fps, 1280×720):
  1. --measure: main.gd druckt je Bild Knöchel (Kopf des Knochens foot.L/R), Zehen (Knochenspitze) und
     Mützendeckel in Welt- und Bildkoordinaten (Camera3D.unproject_position, feste Kamera).
     Ein Fuß gilt als aufgesetzt, wenn die Zehe höchstens 3 cm und der Knöchel höchstens 7,5 cm über dem Kai
     liegt. Gemessen wird, wie weit ein aufgesetzter Fuß von Bild zu Bild wandert (mm Welt, px Bild).
  2. --mask: Dachs weiß auf Schwarz; je Bild unterste und oberste weiße Zeile. Im Stehen (nach dem Drehen)
     muss die Fußzeile gleich bleiben; der Kopf darf nicht springen.
Ausgabe: Bericht auf stdout und assets/measure/badger_report.txt.
"""
import argparse
import pathlib
import subprocess
import tempfile

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[3]
DEMO = ROOT / "styles" / "vertex-animation" / "demo"
OUT = ROOT / "styles" / "vertex-animation" / "assets" / "measure"
PHASES = [("Laufen", 0.0, 1.85), ("Abbiegen im Gehen", 1.85, 2.6), ("Bremsen + Überblenden", 2.6, 3.3),
          ("Stehen (Idle, Winken, Idle)", 3.3, 6.01)]

ap = argparse.ArgumentParser()
ap.add_argument("--tmp", default="")
a = ap.parse_args()
tmp = pathlib.Path(a.tmp) if a.tmp else pathlib.Path(tempfile.mkdtemp(prefix="vertex-animation-measure-"))
tmp.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)


def godot(args, movie):
    for p in tmp.glob(movie + "*.png"):
        p.unlink()
    r = subprocess.run(["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
                        "--write-movie", str(tmp / (movie + ".png")), "--fixed-fps", "30", "--quit-after", "180",
                        "--"] + args, capture_output=True, text=True, timeout=600)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    if errs:
        print("Godot-Fehler:", *errs[:5], sep="\n  ")
    return r.stdout


subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True, timeout=600)
out = godot(["--measure"], "m")
rows = {}
for l in out.splitlines():
    if not l.startswith("M "):
        continue
    v = l.split()
    pts = np.array([float(x) for x in v[5:]]).reshape(5, 5)   # L-Knöchel, L-Zehe, R-Knöchel, R-Zehe, Mütze
    rows[int(v[1])] = {"t": float(v[2]), "phase": int(v[3]), "rate": float(v[4]), "pts": pts}
frames = sorted(rows)
rep = [f"Messbilder: {len(frames)} (t = {rows[frames[0]]['t']:.3f} … {rows[frames[-1]]['t']:.3f} s)"]


def phase_of(t):
    for name, t0, t1 in PHASES:
        if t0 <= t < t1:
            return name
    return PHASES[-1][0]


drift = {name: [] for name, _, _ in PHASES}
for f0, f1 in zip(frames, frames[1:]):
    r0, r1 = rows[f0], rows[f1]
    for side, (ia, it) in (("L", (0, 1)), ("R", (2, 3))):
        a0, t0_, a1, t1_ = r0["pts"][ia], r0["pts"][it], r1["pts"][ia], r1["pts"][it]
        on0 = t0_[1] <= 0.03 and a0[1] <= 0.075
        on1 = t1_[1] <= 0.03 and a1[1] <= 0.075
        if on0 and on1:
            mm = 1000 * np.linalg.norm(t1_[[0, 2]] - t0_[[0, 2]])
            px = float(np.hypot(*(t1_[3:5] - t0_[3:5])))
            drift[phase_of(r1["t"])].append((mm, px, f1, side))
rep.append("Aufgesetzter Fuß (Zehe), Wanderung von Bild zu Bild:")
for name, _, _ in PHASES:
    d = drift[name]
    if not d:
        rep.append(f"  {name:30s} keine Bildpaare mit aufgesetztem Fuß")
        continue
    mm = np.array([x[0] for x in d])
    px = np.array([x[1] for x in d])
    worst = max(d, key=lambda x: x[1])
    rep.append(f"  {name:30s} Paare {len(d):3d}  max {mm.max():5.1f} mm / {px.max():4.2f} px  Mittel {mm.mean():4.1f} mm / "
               f"{px.mean():4.2f} px  (schlimmstes: Bild {worst[2]}, Fuß {worst[3]}); über 1 px: {(px > 1).sum()}")
head = np.array([rows[f]["pts"][4][3:5] for f in frames])
hj = np.abs(np.diff(head[:, 1]))
rep.append(f"Mützendeckel (Bild-y) Sprung von Bild zu Bild: max {hj.max():.2f} px, Mittel {hj.mean():.2f} px")

# Silhouette
godot(["--mask"], "k")
pngs = sorted(tmp.glob("k*.png"))
foot, top, left, right = [], [], [], []
for p in pngs:
    m = np.asarray(Image.open(p).convert("L")) > 128
    ys = np.where(m.any(axis=1))[0]
    xs = np.where(m.any(axis=0))[0]
    foot.append(ys.max() if len(ys) else -1)
    top.append(ys.min() if len(ys) else -1)
    left.append(xs.min() if len(xs) else -1)
    right.append(xs.max() if len(xs) else -1)
foot, top = np.array(foot), np.array(top)
times = np.arange(len(pngs)) / 30.0
stand = times >= 3.3
rep.append(f"Silhouette: {len(pngs)} Bilder; Höhe im Stehen {int(np.median(foot[stand] - top[stand]))} px")
rep.append(f"  Fußzeile im Stehen (t ≥ 3,3 s): Werte {sorted(set(foot[stand].tolist()))}  "
           f"Spanne {foot[stand].max() - foot[stand].min()} px")
walk = times < 1.85
rep.append(f"  Fußzeile im Laufen: {foot[walk].min()} … {foot[walk].max()} px (Schritte heben die Füße)")
tj = np.abs(np.diff(top))
rep.append(f"  oberste Zeile, Sprung von Bild zu Bild: max {tj.max()} px (Bild {int(np.argmax(tj)) + 1}), "
           f"Mittel {tj.mean():.2f} px")
txt = "\n".join(rep)
print(txt)
(OUT / "badger_report.txt").write_text(txt + "\n")
