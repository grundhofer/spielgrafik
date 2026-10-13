#!/usr/bin/env python3
"""Zeitverhalten von Eingabe und Auswahl in gerenderten Einzelbildern prüfen.

    scripts/render_frames.sh <ordner> 180
    .venv/bin/python styles/minimal-geometrisch/scripts/check_ui_timing.py <ordner>

  * Tippen: Position der Schreibmarke (Bernstein-Rechteck in der Eingabezeile) je Bild; jede Haltezeit
    zwischen zwei Zeichen muss gleich lang sein (in 30 fps aufgehen).
  * Auswahl: Farbe des Zeigerings um das Paket (Rot oder Creme) und Textfarbe der zweiten Handlung
    („Das Paket ansehen“: Creme = aktiv, Rose = inaktiv) je Bild; beide müssen im selben Bild wechseln.
"""
import pathlib, sys

import numpy as np
from PIL import Image

AMBER = np.array([0xF5, 0xA5, 0x4A])
CREAM = np.array([0xF2, 0xE8, 0xD4])
RED = np.array([0xE4, 0x47, 0x3B])
ROSE = np.array([0xA3, 0x5D, 0x80])
PARCEL_C = (640, 565)


def near(A, c, tol=30):
    return np.abs(A.astype(np.int16) - c).max(2) <= tol


src = pathlib.Path(sys.argv[1])
files = sorted(src.glob("f*.png"))
cursor, ring_col, text_col = [], [], []
yy, xx = np.mgrid[0:720, 0:1280]
rr = np.hypot(xx - PARCEL_C[0], yy - PARCEL_C[1])
annulus = (rr >= 17) & (rr <= 31.5) & ~((np.abs(xx - 640) <= 17) & (yy >= 553) & (yy <= 578))
for f in files:
    A = np.asarray(Image.open(f).convert("RGB"))
    band = near(A[688:708, 40:400], AMBER, 20)
    cols = np.nonzero(band.sum(0) >= 15)[0]          # senkrechte Kante der Schreibmarke (19 px hoch)
    cursor.append(int(cols.min()) + 40 if len(cols) else None)
    red = (near(A, RED) & annulus).sum()
    cream = (near(A, CREAM) & annulus).sum()
    ring_col.append("rot" if red > cream else "creme")
    T = A[646:668, 922:1100]
    text_col.append("aktiv" if near(T, CREAM, 40).sum() > near(T, ROSE, 40).sum() else "inaktiv")

# Haltezeiten der Schreibmarke während des Tippens (bis zum letzten Positionswechsel)
holds, pos, run = [], None, 0
changes = [i for i in range(1, len(cursor)) if cursor[i] is not None and cursor[i - 1] is not None and cursor[i] != cursor[i - 1]]
for i in range(changes[0], changes[-1] + 1) if changes else []:
    if cursor[i] != pos:
        if pos is not None:
            holds.append(run)
        pos, run = cursor[i], 1
    else:
        run += 1
print("Schreibmarke: erster Wechsel Bild", changes[0] if changes else None, "letzter", changes[-1] if changes else None,
      "Haltezeiten zwischen Zeichen (Bilder):", holds)
sw_ring = next((i for i in range(1, len(files)) if ring_col[i] != ring_col[i - 1]), None)
sw_text = next((i for i in range(1, len(files)) if text_col[i] != text_col[i - 1]), None)
print("Zeigering wechselt in Bild", sw_ring, f"({ring_col[sw_ring - 1]} -> {ring_col[sw_ring]})" if sw_ring else "")
print("Text „Das Paket ansehen“ wechselt in Bild", sw_text, f"({text_col[sw_text - 1]} -> {text_col[sw_text]})" if sw_text else "")
ok = bool(holds) and len(set(holds)) == 1 and sw_ring is not None and sw_ring == sw_text
print("ok" if ok else "PROBLEME")
sys.exit(0 if ok else 2)
