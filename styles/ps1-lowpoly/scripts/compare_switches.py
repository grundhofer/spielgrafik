#!/usr/bin/env python3
"""Die PS1-Merkmale mit den Vergleichsschaltern von main.gd messen (PIPELINE.md -> Blender: Vergleichsschalter).

    .venv/bin/python styles/ps1-lowpoly/scripts/compare_switches.py [--switches no-snap,no-affine,no-affine-vc,zbuffer,mipmaps,no-vc]

Nimmt die Demo verlustfrei in 320×240 auf (alle 180 Bilder), einmal normal und einmal je Schalter, und gibt
den Anteil der Pixel aus, die sich ändern (deutlich: ein Kanal um mehr als 24 Stufen). Bilder 45/60 liegen in
der Totale (Fahrt und Schwenk, Bild 0–118), 136/150 in der Nahaufnahme (Winken, Bild 119–179). Für --mipmaps
zusätzlich das Flimmern in der Ferne: Anteil der Pixel im Streifen um den Horizont der Totale (Zeilen 70–112:
Felsnase, Meer, Inseln, Boote), die sich von Bild zu Bild deutlich ändern, gemittelt über die Totale (Bild
1–118). Dazu für alle Bilder die Farbzahl (kleinste/größte), die 15-Bit-Prüfung und Bilder mit ganz schwarzer Zeile.
"""
import argparse, pathlib, subprocess, tempfile

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent.parent
FRAMES = (45, 60, 136, 150)
HORIZON = slice(70, 112)
CUT = 119                     # erstes Bild der Nahaufnahme

ap = argparse.ArgumentParser()
ap.add_argument("--switches", default="no-snap,no-affine,no-affine-vc,zbuffer,mipmaps,no-vc")
a = ap.parse_args()


def render(args):
    with tempfile.TemporaryDirectory(prefix="ps1-lowpoly-") as td:
        r = subprocess.run(["godot", "--path", str(HERE / "demo"), "--position", "20000,20000", "--write-movie",
                            str(pathlib.Path(td) / "f.png"), "--fixed-fps", "30", "--quit-after", "180"]
                           + (["--"] + args if args else []), capture_output=True, text=True)
        errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
        if errs:
            print("\n".join(errs[:5]))
        return np.stack([np.asarray(Image.open(p).convert("RGB")) for p in sorted(pathlib.Path(td).glob("f*.png"))])


def changed(x, y):
    d = np.abs(x.astype(int) - y.astype(int)).max(-1)
    return float((d > 0).mean()), float((d > 24).mean())


def shimmer(seq):
    d = np.abs(seq[1:CUT, HORIZON].astype(int) - seq[0:CUT - 1, HORIZON].astype(int)).max(-1)
    return float((d > 24).mean())


ref = render([])
allowed = set(round(i * 255 / 31) for i in range(32))
ncol = [len(np.unique(f.reshape(-1, 3), axis=0)) for f in ref]
ok15 = all(set(np.unique(f).tolist()) <= allowed for f in ref)
black = [i for i, f in enumerate(ref) if (f.max(axis=(1, 2)) == 0).any()]
print(f"Referenz ({len(ref)} Bilder): {min(ncol)}–{max(ncol)} Farben je Bild, 15 Bit in allen Bildern: {ok15}, "
      f"Bilder mit ganz schwarzer Zeile: {black if black else 'keine'}")
for sw in [s for s in a.switches.split(",") if s]:
    alt = render(["--" + sw])
    parts = []
    for i in FRAMES:
        c, cd = changed(ref[i], alt[i])
        parts.append(f"{i}: {c * 100:.1f} % ({cd * 100:.1f} % deutlich)")
    tot = np.mean([changed(ref[i], alt[i])[0] for i in range(0, CUT)])
    cu = np.mean([changed(ref[i], alt[i])[0] for i in range(CUT, len(ref))])
    print(f"--{sw}: " + "; ".join(parts) + f"; Mittel Totale {tot * 100:.1f} %, Nahaufnahme {cu * 100:.1f} %")
    if sw == "mipmaps":
        print(f"  Flimmern am Horizont der Totale (Bild zu Bild deutlich geändert): ohne Mipmaps "
              f"{shimmer(ref) * 100:.1f} %, mit Mipmaps {shimmer(alt) * 100:.1f} %")
