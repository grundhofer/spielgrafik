#!/usr/bin/env python3
"""Füße und Kopf des Dachses in der Demo messen (PIPELINE.md → Figuren und Animation).

    .venv/bin/python styles/blender-rig/scripts/measure_feet.py [--tmp DIR] [--out styles/blender-rig/assets/measure]

Ein Godot-Lauf mit fester Bildrate (180 Bilder, 30 fps) und den Schaltern --measure --mask:
  1. Knochenpunkte: main.gd druckt je Bild Ferse und Ballen beider Füße und den Mützendeckel, in Welt- und
     Bildkoordinaten (Camera3D.unproject_position, feste Kamera). Ein Punkt gilt als aufgesetzt, wenn er
     höchstens 6 mm über dem Kai liegt (Sohle in Ruhe: 3 mm). Gemessen wird, wie weit ein aufgesetzter
     Punkt von Bild zu Bild wandert (mm in der Welt, px im Bild), getrennt nach Laufen, Bremsen/Überblenden
     und Stehen; mit --detail jedes Paar über 1 px einzeln.
  2. Silhouetten: derselbe Lauf schreibt den Dachs weiß auf Schwarz (--write-movie). Je Bild unterste und
     oberste weiße Zeile; im Stehen (Idle, Winken) muss die Fußzeile gleich bleiben, der Kopf darf nicht
     springen. Zur Kontrolle der Knochenmessung: unterste Silhouettenzeile gegen tiefsten Knochen-Fußpunkt
     (nur Bilder, in denen der Dachs ganz im Bild ist).
Ausgabe: Bericht auf stdout und <out>/feet_report.txt, Kurven als <out>/feet_plot.png.
"""
import argparse
import pathlib
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[3]
DEMO = ROOT / "styles" / "blender-rig" / "demo"
GROUND = 0.006          # m; die Sohle steht in Ruhe bei 3 mm
PHASES = [("Laufen", 0.0, 3.15), ("Bremsen + Walk->Idle", 3.15, 3.80), ("Stehen (Idle, Wave)", 3.80, 6.01)]

ap = argparse.ArgumentParser()
ap.add_argument("--tmp", default="")
ap.add_argument("--out", default=str(ROOT / "styles" / "blender-rig" / "assets" / "measure"))
ap.add_argument("--detail", action="store_true", help="jedes Paar über 1 px einzeln ausgeben")
a = ap.parse_args()
out = pathlib.Path(a.out)
out.mkdir(parents=True, exist_ok=True)

tmp = pathlib.Path(a.tmp) if a.tmp else pathlib.Path(tempfile.mkdtemp(prefix="blender-rig-measure-"))
tmp.mkdir(parents=True, exist_ok=True)
for p in tmp.glob("m*.png"):
    p.unlink()
run = subprocess.run(["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
                      "--write-movie", str(tmp / "m.png"), "--fixed-fps", "30", "--quit-after", "180",
                      "--", "--measure", "--mask"], capture_output=True, text=True, timeout=600)
lines = [l.split() for l in run.stdout.splitlines() if l.startswith("M ")]
errs = [l for l in (run.stdout + run.stderr).splitlines() if "ERROR" in l]
if errs:
    print("Godot-Fehler:", *errs[:5], sep="\n  ")
# M frame rate weight phase stance  [x y z sx sy] * 5  (L-Ferse, L-Ballen, R-Ferse, R-Ballen, Kopf)
rows = {}
for l in lines:
    f = int(l[1])
    vals = np.array([float(v) for v in l[6:]]).reshape(5, 5)
    rows[f] = {"rate": float(l[2]), "weight": float(l[3]), "phase": float(l[4]), "stance": l[5], "pts": vals}
frames = sorted(rows)
names = ["L-Ferse", "L-Ballen", "R-Ferse", "R-Ballen"]
report = []


def say(s=""):
    print(s)
    report.append(s)


say(f"Bilder mit Messwerten: {len(frames)} (0 = Startzustand, danach 1..180)")
say("")
say("1) Knochenpunkte: Wandern aufgesetzter Punkte von Bild zu Bild")
for label, t0, t1 in PHASES:
    mm, px, n = [], [], 0
    for f in frames:
        if f == 0 or f - 1 not in rows or not (t0 <= f / 30 < t1):
            continue
        p0, p1 = rows[f - 1]["pts"], rows[f]["pts"]
        for k in range(4):
            if p0[k, 1] <= GROUND and p1[k, 1] <= GROUND:
                n += 1
                mm.append(1000 * np.hypot(p1[k, 0] - p0[k, 0], p1[k, 2] - p0[k, 2]))
                px.append(np.hypot(p1[k, 3] - p0[k, 3], p1[k, 4] - p0[k, 4]))
                if a.detail and px[-1] > 1.0:
                    print(f"      Bild {f - 1}->{f} {names[k]}: {mm[-1]:.1f} mm, {px[-1]:.2f} px, Höhe {1000 * p0[k, 1]:.1f}"
                          f" -> {1000 * p1[k, 1]:.1f} mm, Phase {rows[f]['phase']:.2f}, Gewicht Walk {rows[f]['weight']:.2f}")
    if n:
        mm, px = np.array(mm), np.array(px)
        say(f"   {label:24s} {n:4d} Paare: Welt Median {np.median(mm):5.2f} mm, 95 % {np.percentile(mm, 95):5.2f} mm,"
            f" max {mm.max():5.2f} mm | Bild Median {np.median(px):4.2f} px, 95 % {np.percentile(px, 95):4.2f} px,"
            f" max {px.max():4.2f} px; über 1 px: {(px > 1.0).sum()}")
    else:
        say(f"   {label:24s} keine aufgesetzten Punkte")
# Ein Standfuß über mehrere Bilder (Ballen und Ferse zusammen am Boden): Spanne der Bildposition
say("")
say("   Standphasen im Laufen (Ferse und Ballen am Boden, ab 3 Bildern): Spanne der Bildlage in px")
for side, (hi, bi) in (("L", (0, 1)), ("R", (2, 3))):
    run_f = []
    spans = []
    for f in frames + [10_000]:
        r = rows.get(f)
        down = r is not None and f / 30 < 3.15 and r["pts"][hi, 1] <= GROUND and r["pts"][bi, 1] <= GROUND
        if down:
            run_f.append(f)
            continue
        if len(run_f) >= 3:
            pts = np.array([rows[g]["pts"][bi, 3:5] for g in run_f])
            sp = np.ptp(pts, axis=0)
            spans.append((run_f[0], run_f[-1], sp[0], sp[1]))
        run_f = []
    for f0, f1, sx, sy in spans:
        say(f"     {side}: Bild {f0:3d}-{f1:3d} ({f1 - f0 + 1:2d} Bilder): Ballen x {sx:4.2f} px, y {sy:4.2f} px")

# --- 2. Silhouetten --------------------------------------------------------------------------------------
pngs = sorted(tmp.glob("m*.png"))
say("")
say(f"2) Silhouetten ({len(pngs)} Bilder, weiß auf Schwarz)")
bottom, top, full = [], [], []
for p in pngs:
    m = np.asarray(Image.open(p).convert("L")) > 128
    ys, xs = np.nonzero(m)
    if len(ys) == 0:
        bottom.append(np.nan)
        top.append(np.nan)
        full.append(False)
        continue
    bottom.append(ys.max())
    top.append(ys.min())
    full.append(xs.min() > 2)          # ganz im Bild (berührt den linken Rand nicht)
bottom, top, full = np.array(bottom, float), np.array(top, float), np.array(full)
idx = np.arange(len(pngs))
vis = ~np.isnan(bottom)
first = int(idx[vis][0]) if vis.any() else -1
first_full = int(idx[full][0]) if full.any() else -1
say(f"   Dachs zuerst sichtbar in Bild {first} (t = {first / 30:.2f} s), ganz im Bild ab Bild {first_full}"
    f" (t = {first_full / 30:.2f} s)")
vis = full
stand = (idx / 30 >= 3.80) & vis
if stand.any():
    say(f"   Stehen (ab 3,80 s, {stand.sum()} Bilder): unterste Zeile {int(np.nanmin(bottom[stand]))}"
        f"–{int(np.nanmax(bottom[stand]))}, oberste Zeile (Mütze/Hand) {int(np.nanmin(top[stand]))}"
        f"–{int(np.nanmax(top[stand]))}")
    jumps = np.abs(np.diff(top[stand]))
    say(f"   Kopf/Hand im Stehen: größter Sprung der obersten Zeile von Bild zu Bild {jumps.max():.0f} px")
walk = (idx / 30 < 3.15) & vis
if walk.any():
    j = np.abs(np.diff(top[walk]))
    say(f"   Laufen: oberste Zeile {int(np.nanmin(top[walk]))}–{int(np.nanmax(top[walk]))}, größter Sprung {j.max():.0f} px"
        f" (Wippen + Perspektive, die Figur kommt näher)")

# Kontrolle: Silhouette gegen Knochenpunkte (unterste Zeile vs. tiefster projizierter Fußpunkt)
diff = []
for f in frames:
    if 1 <= f <= len(pngs) and vis[f - 1]:
        lowest = max(rows[f]["pts"][k, 4] for k in range(4))
        diff.append(bottom[f - 1] - lowest)
if diff:
    d = np.array(diff)
    say(f"   Kontrolle unterste Silhouettenzeile minus tiefster Knochen-Fußpunkt: Median {np.median(d):.1f} px,"
        f" Spanne {d.min():.1f} bis {d.max():.1f} px")

# --- Kurven ----------------------------------------------------------------------------------------------
W, H = 900, 420
img = Image.new("RGB", (W, H), "white")
dr = ImageDraw.Draw(img)
dr.text((10, 6), "Ballen L (blau) / R (rot): Bild-x je Bild; Punkte = am Boden; grau: Phasengrenzen", fill="black")
xs_all = np.array([[rows[f]["pts"][1, 3], rows[f]["pts"][3, 3]] for f in frames])
lo, hi = np.nanmin(xs_all), np.nanmax(xs_all)


def sx(f):
    return 40 + f * (W - 60) / 180


def sy(v):
    return H - 30 - (v - lo) / max(hi - lo, 1) * (H - 70)


for tb in (3.15, 3.80):
    dr.line([(sx(tb * 30), 24), (sx(tb * 30), H - 20)], fill=(180, 180, 180))
for k, col in ((1, (40, 90, 220)), (3, (220, 50, 60))):
    prev = None
    for f in frames:
        v = rows[f]["pts"][k]
        pt = (sx(f), sy(v[3]))
        if prev:
            dr.line([prev, pt], fill=col)
        if v[1] <= GROUND:
            dr.ellipse([pt[0] - 2, pt[1] - 2, pt[0] + 2, pt[1] + 2], fill=col)
        prev = pt
img.save(out / "feet_plot.png")
(out / "feet_report.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
print(f"\nBericht: {out / 'feet_report.txt'}  Kurven: {out / 'feet_plot.png'}  Masken: {tmp}")
