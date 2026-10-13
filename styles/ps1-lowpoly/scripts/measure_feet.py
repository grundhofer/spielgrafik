#!/usr/bin/env python3
"""Füße und Kopf des Dachses in gerenderten Bildern messen (PIPELINE.md -> Figuren und Animation).

    .venv/bin/python styles/ps1-lowpoly/scripts/measure_feet.py [--keep DIR]

Zwei Aufnahmen mit main.gd-Schaltern, nur der Dachs vor Schwarz (--figure-only, ohne Dithering):
  1. Laufen: feste Messkamera 3,4 m vor dem Laufweg (--measure-cam), Dachs ca. 68 px hoch. Bild 0–92 läuft er
     mit voller Geschwindigkeit, 93–103 bremst er. Je Standphase (gleiche unterste Zeile) wird die Zehenkante
     des Standfußes verfolgt: Sie soll stehen bleiben (±1 px, Vertex-Snapping rundet auf ganze Pixel).
  2. Drehen auf der Stelle (in der Demo noch in der Totale, 3,5–3,95 s = Bild 104–118), ebenfalls mit der
     Messkamera: Fußabdruck (unterste 6 Zeilen, beide Pfoten) und vorderer Fuß (unterste 3 Zeilen).
  3. Stehen und Winken in der Nahaufnahme (Kamera wie in der Demo), Bild 119–179: Bodenzeile und linke/
     rechte Kante der Füße in allen Bildern; Kopf (oberste Zeile) zur Kontrolle.
"""
import argparse, pathlib, subprocess, tempfile

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent.parent

ap = argparse.ArgumentParser()
ap.add_argument("--keep", default="", help="Bilder hierhin kopieren (zum Ansehen)")
a = ap.parse_args()


def render(td, args):
    out = pathlib.Path(td)
    r = subprocess.run(["godot", "--path", str(HERE / "demo"), "--position", "20000,20000", "--write-movie",
                        str(out / "f.png"), "--fixed-fps", "30", "--quit-after", "180", "--"] + args,
                       capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    if errs:
        print("\n".join(errs[:5]))
    return [np.asarray(Image.open(p).convert("RGB")) for p in sorted(out.glob("f*.png"))]


def mask_of(img):
    return img.max(2) > 8


def bottom_profile(m, rows=2):
    ys = np.where(m.any(1))[0]
    yb = ys.max()
    prof = m[yb - rows + 1:yb + 1].sum(0).astype(float)
    return yb, ys.min(), prof


with tempfile.TemporaryDirectory(prefix="ps1-lowpoly-") as td:
    walk = render(td, ["--figure-only", "--measure-cam"])
with tempfile.TemporaryDirectory(prefix="ps1-lowpoly-") as td:
    cu = render(td, ["--figure-only"])

# --- 1. Laufen ---------------------------------------------------------------------------------------
# Die Messkamera steht 0,5 m hoch: Die Sohle des hinteren (kameraferneren) Fußes liegt dadurch etwa 3 px
# höher im Bild als die des vorderen. Die unterste Zeile (154 bzw. 151) zeigt also, welcher Fuß aufsteht.
# Je Lauf von Bildern mit gleicher unterster Zeile (Standphase eines Fußes) wird die Zehenkante (rechte
# Kante der untersten zwei Zeilen, er läuft nach rechts) verfolgt; ohne erstes und letztes Bild der Phase
# (Aufsetzen, Abrollen).
info = []
for i in range(0, 93):
    m = mask_of(walk[i])
    ys = np.where(m.any(1))[0]
    yb = ys.max()
    xs = np.where(m[yb - 1:yb + 1].any(0))[0]
    info.append((i, yb, ys.min(), xs.max()))
ybs = np.array([r[1] for r in info])
heights = np.array([r[1] - r[2] + 1 for r in info])
runs, cur = [], [info[0]]
for r in info[1:]:
    if r[1] == cur[-1][1]:
        cur.append(r)
    else:
        runs.append(cur)
        cur = [r]
runs.append(cur)
stance = [r for r in runs if len(r) >= 4]
dev = [int(max(x[3] for x in r[1:-1]) - min(x[3] for x in r[1:-1])) for r in stance]
print(f"Laufen (Bild 0–92, Messkamera 3,4 m vor dem Laufweg): Figur {heights.min()}–{heights.max()} px hoch; "
      f"unterste Zeile {sorted(set(int(y) for y in ybs))} (vorderer Fuß 154, hinterer 151, dazwischen Abrollen)")
print(f"  {len(stance)} Standphasen mit 4–{max(len(r) for r in stance)} Bildern; Zehenkante des Standfußes "
      f"verschiebt sich innerhalb einer Phase um {min(dev)}–{max(dev)} px (je Phase: {dev})")
brake = [bottom_profile(mask_of(walk[i]))[0] for i in range(93, 104)]
print(f"  Bremsen (Bild 93–103): unterste Zeile {min(brake)}–{max(brake)}")

# --- 2. Drehen auf der Stelle (Messkamera) -----------------------------------------------------------------
# Die Drehung hat keine Schritte: Jede Pfote schwenkt um die Mitte der Pfoten (FEET_MID in main.gd). Gemessen
# werden der ganze Fußabdruck (beide Pfoten, unterste 6 Zeilen) und der vordere Fuß (unterste 3 Zeilen).
turn = []
for i in range(103, 120):
    m = mask_of(walk[i])
    yb = np.where(m.any(1))[0].max()
    x6 = np.where(m[yb - 5:yb + 1].any(0))[0]
    x3 = np.where(m[yb - 2:yb + 1].any(0))[0]
    turn.append((i, int(yb), int(x6.min()), int(x6.max()), int(x3.min()), int(x3.max())))
c6 = [(r[2] + r[3]) / 2 for r in turn]
print(f"Drehen (Bild 103–119, Messkamera): Fußabdruck {turn[0][2]}–{turn[0][3]} -> {turn[-1][2]}–{turn[-1][3]}, "
      f"Mitte {min(c6):.1f}–{max(c6):.1f}; vorderer Fuß links {min(r[4] for r in turn)}–{max(r[4] for r in turn)}, "
      f"rechts {min(r[5] for r in turn)}–{max(r[5] for r in turn)}; Bodenzeile {min(r[1] for r in turn)}–{max(r[1] for r in turn)}")
print("  je Bild (Bild, Bodenzeile, Abdruck links/rechts, vorderer Fuß links/rechts): "
      + " ".join(f"{r[0]}:{r[1]},{r[2]}-{r[3]},{r[4]}-{r[5]}" for r in turn))

# --- 3. Stehen und Winken in der Nahaufnahme ----------------------------------------------------------
yb_l, xl_l, xr_l, top_l = [], [], [], []
for i in range(119, 180):
    m = mask_of(cu[i])
    yb, yt, prof = bottom_profile(m, rows=3)
    xs = np.where(prof > 0)[0]
    yb_l.append(yb), xl_l.append(xs.min()), xr_l.append(xs.max()), top_l.append(yt)
yb_l, xl_l, xr_l, top_l = map(np.array, (yb_l, xl_l, xr_l, top_l))
print(f"Nahaufnahme (Bild 119–179, Stehen/Winken): Bodenzeile {yb_l.min()}–{yb_l.max()}, "
      f"linke Kante des vorderen Fußes {xl_l.min()}–{xl_l.max()}, rechte Kante {xr_l.min()}–{xr_l.max()} "
      f"(schließt den hinteren Fuß ein), Kopf oben {top_l.min()}–{top_l.max()}")

if a.keep:
    k = pathlib.Path(a.keep)
    k.mkdir(parents=True, exist_ok=True)
    for i in (0, 10, 20, 30, 40, 92, 104, 108, 112, 118):
        Image.fromarray(walk[i]).save(k / f"walk{i:03d}.png")
    for i in (119, 130, 139, 150, 179):
        Image.fromarray(cu[i]).save(k / f"cu{i:03d}.png")
