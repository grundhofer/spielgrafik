#!/usr/bin/env python3
"""Haftet das Dithermuster beim Schwenken an der Welt? Messung mit eingefrorener Szene (--freeze).

    .venv/bin/python styles/einbit-3d/scripts/dither_lock.py [--keep <Ordner>]

Zwei Aufnahmen, in denen sich nur die Kamera bewegt (Wasser, Rauch, Licht, Dachs stehen still): einmal mit dem an
die Blickrichtung gekoppelten Muster (Standard), einmal mit --screen-dither (Muster fest im Bildschirm).

1. Feste Kamera (Totale, Bild 1–70): Anteil geänderter Pixel zwischen aufeinanderfolgenden Bildern (soll 0 sein).
2. Schwenk (Einstellung 2, Bild 73–131): Die Bewegung der Welt je Bildpaar kommt aus einer dritten Aufnahme ohne
   Raster (--nodither, Schwelle 0,5: nur Flächen und Linien): ganzzahlige Verschiebung (±4 px), mit der sich ein
   Streifen am besten deckt (zehn senkrechte Streifen je 64 px Breite, y 50–230 in 640×360, ohne Oberfläche;
   je Streifen eigene Verschiebung, weil sich der Bildrand beim Schwenken schneller bewegt als die Mitte). Mit
   genau dieser Verschiebung wird in beiden Dither-Aufnahmen verglichen: Haftet das Muster an der Welt, wandert es mit und es
   bleiben nur Abweichungen an Kanten (Perspektive, Rasterung). Steht es im Bildschirm, kippen die gerasterten
   Flächen bei jeder Verschiebung um (Duschtür-Effekt).
3. Ruhelage am Ende des Schwenks (Bild 132–179 ohne Oberfläche; bis 4,23 s rückt der Dachs beim
   Überblenden noch um wenige Zentimeter, die Kamera folgt): Muster genau auf dem Pixelraster? Vergleich mit
   --static-cam (Kamera von Anfang an in der Ruhelage): Bilder müssen gleich sein.
"""
import argparse, pathlib, shutil, sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from snap import render  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--keep", default="")
a = ap.parse_args()

ROWS = slice(50, 230)
STRIPS = [slice(x, x + 64) for x in range(8, 632, 64)][:9]   # x 8..584, Rand für die Verschiebung


def load(pngs):
    return [np.asarray(Image.open(p).convert("L")) > 128 for p in pngs]


def mismatch(prev, cur, dx, dy, xs):
    ys = ROWS
    moved = cur[ys.start + dy:ys.stop + dy, xs.start + dx:xs.stop + dx]
    return float((moved != prev[ys, xs]).mean())


def best_shift(prev, cur, xs, r=4):
    best = (1.0, 0, 0)
    ys = ROWS
    base = prev[ys, xs]
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            moved = cur[ys.start + dy:ys.stop + dy, xs.start + dx:xs.stop + dx]
            mm = float((moved != base).mean())
            if mm < best[0]:
                best = (mm, dx, dy)
    return best


pngs, log, errs = render(133, ["--freeze", "--nodither"])
geo = load(pngs)
geo_fit = {(i, k): best_shift(geo[i - 1], geo[i], xs) for i in range(73, 132) for k, xs in enumerate(STRIPS)}
motion = {key: v[1:] for key, v in geo_fit.items()}
shutil.rmtree(pngs[0].parent, ignore_errors=True)
floor = np.array([v[0] for v in geo_fit.values()])
print("Weltbewegung je Bild und Streifen (aus --nodither): dx", sorted(set(m[0] for m in motion.values())),
      "dy", sorted(set(m[1] for m in motion.values())),
      f"; ohne Raster weichen danach im Mittel {floor.mean():.4f} der Pixel ab (Kanten, Perspektive: Untergrenze)")

results = {}
strips_txt = {}
for name, args in (("Kugel", ["--freeze"]), ("Bildschirm", ["--freeze", "--screen-dither"])):
    pngs, log, errs = render(180, args)
    for e in errs[:5]:
        print("!!", e)
    fr = load(pngs)
    static = [float((fr[i] != fr[i - 1]).mean()) for i in range(1, 71)]
    pan = []
    per_strip = np.zeros(len(STRIPS))
    n_mov = sum(1 for i in range(73, 132) if motion[(i, len(STRIPS) // 2)][0] != 0)
    for i in range(73, 132):
        ms = [mismatch(fr[i - 1], fr[i], *motion[(i, k)], xs) for k, xs in enumerate(STRIPS)]
        if motion[(i, len(STRIPS) // 2)][0] != 0:
            per_strip += np.array(ms) / n_mov
        raw = float((fr[i][ROWS, 8:584] != fr[i - 1][ROWS, 8:584]).mean())
        pan.append((i, float(np.mean(ms)), 0, 0, raw))
    results[name] = (static, pan, fr)
    strips_txt[name] = " ".join(f"{v:.3f}" for v in per_strip)
    if a.keep:
        k = pathlib.Path(a.keep)
        k.mkdir(parents=True, exist_ok=True)
        for i in (72, 80, 90, 100, 110, 130):
            Image.fromarray((fr[i] * 255).astype(np.uint8)).save(k / f"lock_{name}_{i:03d}.png")
    shutil.rmtree(pngs[0].parent, ignore_errors=True)

# Bilder, in denen sich die Welt in der Bildmitte tatsächlich verschiebt (mittlerer Streifen dx != 0)
mid = len(STRIPS) // 2
moving = {i for i in range(73, 132) if motion[(i, mid)][0] != 0}
print(f"Bilder mit Bewegung in der Bildmitte: {len(moving)} ({min(moving)}–{max(moving)})")
for name, (static, pan, fr) in results.items():
    mms = np.array([p[1] for p in pan if p[0] in moving])
    raws = np.array([p[4] for p in pan if p[0] in moving])
    print(f"{name}: feste Kamera Bild 1–70: höchstens {max(static):.4f} der Pixel geändert")
    print(f"  Schwenk (Bilder mit Bewegung): ohne Ausgleich {raws.mean():.3f} der Pixel anders; um die Weltbewegung "
          f"verschoben im Mittel {mms.mean():.4f} (Median {np.median(mms):.4f}, höchstens {mms.max():.4f})")
    print("   je Bild:", " ".join(f"{p[0]}:{p[1]:.3f}" for p in pan[::4]))
    print("   je Streifen von links nach rechts:", strips_txt[name])

# Ruhelage: Muster wie bei einer festen Kamera in der Endlage?
pngs, log, errs = render(180, ["--freeze", "--static-cam", "--shot2"])
st = load(pngs)
fr = results["Kugel"][2]
same = [float((st[i][:230] != fr[i][:230]).mean()) for i in range(132, 180)]
print(f"Ruhelage Bild 132–179 gegen Kamera fest in der Endlage: höchstens {max(same):.5f} der Pixel anders (oberer Teil, ohne Dialog)")
shutil.rmtree(pngs[0].parent, ignore_errors=True)
