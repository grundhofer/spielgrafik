#!/usr/bin/env python3
"""Füße und Kopf des Dachses in gerenderten Bildern messen.

    .venv/bin/python styles/n64/scripts/measure_feet.py <temp-ordner>

Zwei Läufe der Demo mit --figure-only (nur der Dachs vor grauem Grund, sonst alles wie in der Aufnahme,
also auch Videoausgabe mit Dithering und Weichzeichnung, 960×720 = 320×240 ×3):
  A  --cam=fix: feste Messkamera von vorn auf den Laufweg (Seitenansicht). Laufen (Bild 0–103):
     Zehenkante der Pfoten in den untersten 2 Zeilen (320er-Raster) je Bild, verkettet über Bilder: Eine
     Pfote, deren Vorderkante über mindestens 3 Bilder höchstens ±1 px wandert, steht. Drehen (Bild 104–125):
     Mitte des Fußabdrucks (beide Pfoten, unterste 5 Zeilen) je Bild.
  B  echte Kamerafahrt: in der festen Schlusseinstellung (ab Bild 120) Bodenzeile (unterste Zeile der Figur)
     und oberste Zeile je Bild.
Alle Angaben in Pixeln des 320×240-Rasters (Ausgabe / 3).
"""
import pathlib
import subprocess
import sys

import numpy as np
from PIL import Image

DEMO = pathlib.Path(__file__).resolve().parent.parent / "demo"
N = 180
K = 3          # Ausgabe-Pixel je Rasterpixel


def run(out, args):
    out.mkdir(parents=True, exist_ok=True)
    for p in out.glob("f*.png"):
        p.unlink()
    subprocess.run(["godot", "--path", str(DEMO), "--position", "20000,20000", "--write-movie", str(out / "f.png"),
                    "--fixed-fps", "30", "--quit-after", str(N), "--", "--figure-only"] + args,
                   capture_output=True, text=True, timeout=900)


def mask(d, i):
    a = np.asarray(Image.open(d / f"f{i:08d}.png").convert("RGB"), dtype=np.int16)
    bg = np.median(a[:8, :8].reshape(-1, 3), axis=0)
    return np.abs(a - bg).max(axis=2) > 28


def clusters(cols, gap=3):
    xs = np.flatnonzero(cols)
    if xs.size == 0:
        return []
    out, s = [], xs[0]
    for a, b in zip(xs, xs[1:]):
        if b - a > gap:
            out.append((s, a))
            s = b
    out.append((s, xs[-1]))
    return out


def main():
    tmp = pathlib.Path(sys.argv[1])
    a_dir, b_dir = tmp / "feet_fix", tmp / "feet_cam"
    run(a_dir, ["--cam=fix"])
    run(b_dir, [])

    # --- A: Laufen ---------------------------------------------------------------------------------------
    masks = [mask(a_dir, i) for i in range(N)]
    ground = max(int(np.flatnonzero(m.any(axis=1)).max()) for m in masks[:104])
    print(f"A  Bodenzeile (Ausgabe) {ground}  = Raster {ground / K:.1f}")
    per = []
    for i in range(104):
        band = masks[i][ground - 2 * K + 1:ground + 1]
        per.append(clusters(band.any(axis=0)))
    # Ketten: Vorderkante (rechts, Laufrichtung) bleibt von Bild zu Bild innerhalb ±1 Rasterpixel
    chains, active = [], []
    for i, cl in enumerate(per):
        nxt = []
        used = set()
        for ch in active:
            last = ch[-1][1]
            best = None
            for k, (x0, x1) in enumerate(cl):
                if k not in used and abs(x1 - last) <= K:
                    best = k
                    break
            if best is not None:
                used.add(best)
                ch.append((i, cl[best][1]))
                nxt.append(ch)
            else:
                chains.append(ch)
        for k, (x0, x1) in enumerate(cl):
            if k not in used:
                nxt.append([(i, x1)])
        active = nxt
    chains += active
    stance = [c for c in chains if len(c) >= 3]
    stance.sort(key=lambda c: c[0][0])
    print("A  Standphasen (Bild von–bis, Länge, Wanderung der Vorderkante max−min in Rasterpixeln):")
    worst = 0.0
    for c in stance:
        xs = [x for _, x in c]
        span = (max(xs) - min(xs)) / K
        worst = max(worst, span)
        print(f"   Bild {c[0][0]:3d}–{c[-1][0]:3d}  {len(c):2d} Bilder  {span:.1f} px  (x {min(xs) / K:.1f}…{max(xs) / K:.1f})")
    print(f"A  {len(stance)} Standphasen, größte Wanderung {worst:.1f} px")
    heights = []
    for i in range(104):
        rows = np.flatnonzero(masks[i].any(axis=1))
        heights.append((rows.max() - rows.min() + 1) / K)
    print(f"A  Figurhöhe beim Laufen {min(heights):.1f}–{max(heights):.1f} px")

    # --- A: Drehen ---------------------------------------------------------------------------------------
    # Beim Drehen liegen die Pfoten verschieden tief im Bild (die nähere tiefer): 5 Zeilen statt 2
    mids = []
    for i in range(100, 126):
        rows = np.flatnonzero(masks[i].any(axis=1))
        g = rows.max()
        band = masks[i][g - 5 * K + 1:g + 1]
        cols = np.flatnonzero(band.any(axis=0))
        mids.append((i, g / K, (cols.min() + cols.max()) / 2 / K, cols.min() / K, cols.max() / K))
    m = [x[2] for x in mids if x[0] >= 104]
    print(f"A  Drehen Bild 104–125: Mitte des Fußabdrucks {min(m):.1f}…{max(m):.1f} px "
          f"(Spanne {max(m) - min(m):.1f}), Bodenzeile {min(x[1] for x in mids):.1f}…{max(x[1] for x in mids):.1f}")
    for x in mids[::5]:
        print(f"   Bild {x[0]}: Boden {x[1]:.1f}  Fußabdruck {x[3]:.1f}…{x[4]:.1f}")

    # --- B: Schlusseinstellung ---------------------------------------------------------------------------
    rows_b = []
    for i in range(120, N):
        mk = mask(b_dir, i)
        rows = np.flatnonzero(mk.any(axis=1))
        cols = np.flatnonzero(mk[rows.max() - 2 * K + 1:rows.max() + 1].any(axis=0))
        rows_b.append((i, rows.max() / K, rows.min() / K, cols.min() / K, cols.max() / K))
    g = [x[1] for x in rows_b]
    top = [x[2] for x in rows_b]
    fl = [x[3] for x in rows_b]
    fr = [x[4] for x in rows_b]
    print(f"B  Schlusseinstellung Bild 120–179: Bodenzeile {min(g):.1f}…{max(g):.1f}, oberste Zeile "
          f"{min(top):.1f}…{max(top):.1f}, Fußabdruck links {min(fl):.1f}…{max(fl):.1f}, rechts {min(fr):.1f}…{max(fr):.1f}, "
          f"Figurhöhe {min(g) - max(top):.1f}…{max(g) - min(top):.1f}")


if __name__ == "__main__":
    main()
