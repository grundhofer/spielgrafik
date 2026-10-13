#!/usr/bin/env python3
"""Misst den Dachs in den gerenderten Bildern eines Masken-Laufs (Godot-Aufnahme, keine Einzelbilder).

    .venv/bin/python styles/textoberflaeche/scripts/grab.py OUT --mask
    .venv/bin/python styles/textoberflaeche/scripts/measure_walk.py OUT [--region x0,y0,x1,y1]

Im Masken-Lauf zeichnet harbor.gd nur den Dachs mit hartem Alpha: Rumpf blau, nahes Bein rot, fernes Bein grün.
Gemessen wird im Bildband der Oberfläche „Bild oben, Text unten“ (links unten im 1280×720-Bild, ohne Panels).
Geprüft wird:
  1. Sohle: unterste Zeile der Figur. In allen Stehbildern gleich; beim Gehen höchstens 1 px Abweichung
     (Ferse und Zehe sind gemalt rund, beim Aufsetzen deckt die Ecke weniger als ein halbes Pixel).
  2. Standfuß je Bein: Solange ein Bein in zwei aufeinanderfolgenden Bildern auf der Sohlenzeile steht, bleibt eine
     Kante seines Bodenkontakts (untere 2 Zeilen) auf ±1 px an derselben Stelle (der Fuß rollt über Ferse und
     Zehe, eine Kante bleibt stehen).
  3. Kopf: Kopf-x (oberes Viertel) je Bild, damit Sprünge auffallen.
Ausgabe: Tabelle je Bild, Zusammenfassung; Rückgabewert 0 nur, wenn alle Prüfungen bestehen.
"""
import argparse, collections, pathlib, sys

import numpy as np
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("dir")
ap.add_argument("--region", default="0,360,640,594")
a = ap.parse_args()
x0, y0, x1, y1 = map(int, a.region.split(","))
frames = []
for p in sorted(pathlib.Path(a.dir).glob("f*.png")):
    im = np.asarray(Image.open(p).convert("RGB"))[y0:y1, x0:x1].astype(int)
    body = (im[..., 2] > 128) & (im[..., 0] < 128) & (im[..., 1] < 128)
    near = (im[..., 0] > 128) & (im[..., 1] < 128) & (im[..., 2] < 128)
    far = (im[..., 1] > 128) & (im[..., 0] < 128) & (im[..., 2] < 128)
    allm = body | near | far
    if not allm.any():
        frames.append(None)
        continue
    ys, xs = np.nonzero(allm)
    top, bot = int(ys.min()), int(ys.max())
    h = bot - top + 1
    hy, hx = np.nonzero(allm[top:top + h // 4])
    legs = {}
    for name, m in (("nah", near), ("fern", far)):
        if m.any():
            legs[name] = {"bot": int(np.nonzero(m)[0].max()), "mask": m}
    frames.append({"frame": int(p.stem[1:]), "top": top, "bot": bot, "head_x": round(float(hx.mean()) + x0, 1),
                   "legs": legs})

valid = [f for f in frames if f]
if not valid:
    sys.exit("keine Figur im Bereich gefunden")
g = collections.Counter(f["bot"] for f in valid).most_common(1)[0][0]
# Stehbilder: Kopf-x ändert sich nicht mehr bis zum Ende
last_x = valid[-1]["head_x"]
stand_from = len(valid)
for i in range(len(valid) - 1, -1, -1):
    if abs(valid[i]["head_x"] - last_x) > 0.6:
        break
    stand_from = i
standing, walking = valid[stand_from:], valid[:stand_from]


def contact(leg):
    m = leg["mask"][g - 1:g + 1].any(0)
    cols = np.nonzero(m)[0]
    return (int(cols.min()) + x0, int(cols.max()) + x0) if len(cols) else None


print(f"{len(valid)} Bilder mit Dachs; Sohlenzeile (häufigste) {g}; gehend {len(walking)}, stehend {len(standing)}")
print("Bild  Sohle Scheitel Kopf-x  nah:Kontakt        fern:Kontakt")
rows = []
for f in valid:
    c = {}
    for name in ("nah", "fern"):
        leg = f["legs"].get(name)
        c[name] = contact(leg) if leg and leg["bot"] >= g - 1 else None
    rows.append(c)
    print(f"{f['frame']:4d}  {f['bot']:5d} {f['top']:8d} {f['head_x']:6.1f}  {str(c['nah']):18s} {str(c['fern'])}")

bad_slip, checked = 0, 0
for i in range(1, len(valid)):
    if valid[i]["head_x"] == valid[i - 1]["head_x"]:
        continue
    for name in ("nah", "fern"):
        c0, c1 = rows[i - 1][name], rows[i][name]
        if not c0 or not c1:
            continue
        checked += 1
        d = min(abs(c0[0] - c1[0]), abs(c0[1] - c1[1]))
        if d > 1:
            bad_slip += 1
            print(f"RUTSCHT {name}: Bild {valid[i - 1]['frame']}->{valid[i]['frame']} {c0} -> {c1} ({d} px)")
walk_bots = sorted({f["bot"] for f in walking})
stand_bots = sorted({f["bot"] for f in standing})
walk_ok = all(abs(b - g) <= 1 for b in walk_bots)
stand_ok = len(stand_bots) <= 1
print(f"Sohle stehend: {stand_bots} {'ok' if stand_ok else 'UNTERSCHIEDLICH'}; "
      f"gehend: {walk_bots} {'ok (±1 px)' if walk_ok else 'ZU GROSS'}")
print(f"Standfuß: {checked - bad_slip}/{checked} Bildwechsel je Bein ok")
sys.exit(0 if stand_ok and walk_ok and bad_slip == 0 else 1)
