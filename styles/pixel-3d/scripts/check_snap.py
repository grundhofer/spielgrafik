#!/usr/bin/env python3
"""Pixelstabile Kamera messen: Wie viele Pixel ändern sich beim Schwenk, wenn man die Verschiebung des
Bildes herausrechnet?

    .venv/bin/python styles/pixel-3d/scripts/probe.py OUT_SNAP   -- --freeze --measure --no-palette
    .venv/bin/python styles/pixel-3d/scripts/probe.py OUT_NOSNAP -- --freeze --measure --no-palette --no-snap
    .venv/bin/python styles/pixel-3d/scripts/check_snap.py OUT_SNAP OUT_NOSNAP

--freeze hält Figur, Wasser, Licht, Rauch und Wolken an; nur die Kamera fährt (wie in der Aufnahme).
Gemessen wird an den Fensterbildern (1280×720, dump/f*.png, ohne Oberfläche oberhalb des Dialogkastens):
Bild k+1 wird mit Bild k verglichen, nachdem es um die bekannte Verschiebung in Bildschirmpixeln
zurückgeschoben wurde (mit Schnappen: 3 × Pan exakt ganzzahlig; ohne: gerundet). Gezählt werden Pixel, die
sich um mehr als 24 Stufen (max. Kanal) ändern, im Bereich y 70..570 und ohne die Ränder, in die neuer
Bildinhalt hineinläuft. Ausgabe: Mittel, Maximum und Anteil der Bildpaare mit Änderungen.
"""
import json
import pathlib
import re
import sys

import numpy as np
from PIL import Image


def load(run):
    run = pathlib.Path(run)
    pans = {}
    for line in (run / "godot.log").read_text().splitlines():
        if line.startswith("MEASURE "):
            d = json.loads(line[8:])
            pans[d["frame"]] = (d["pan"], d["sx"])
    return run, pans


def measure(run, pans, snapped):
    frames = sorted(pans)
    shares = []
    moved = 0
    for a, b in zip(frames, frames[1:]):
        fa, fb = run / "dump" / f"f{a:04d}.png", run / "dump" / f"f{b:04d}.png"
        if not (fa.exists() and fb.exists()):
            continue
        pa, sa = pans[a]
        pb, sb = pans[b]
        if snapped:
            # Inhalt wandert um ganze Renderpixel (frustum_offset) plus Restversatz des Sprite2D
            ia, ib = np.floor(pa), np.floor(pb)
            dx = int(round(3 * (ib - ia) - (sb - sa)))
        else:
            dx = int(round(3 * (pb - pa)))
        if dx == 0 and abs(pb - pa) < 1e-6:
            continue
        moved += 1
        A = np.asarray(Image.open(fa).convert("RGB"), dtype=np.int16)[70:570]
        B = np.asarray(Image.open(fb).convert("RGB"), dtype=np.int16)[70:570]
        # B an der Stelle x zeigt, was A an x + dx zeigte
        m = 12 + abs(dx)
        if dx >= 0:
            a_cut, b_cut = A[:, m + dx:1280 - m], B[:, m:1280 - m - dx]
        else:
            a_cut, b_cut = A[:, m:1280 - m + dx], B[:, m - dx:1280 - m]
        diff = np.abs(a_cut - b_cut).max(axis=2) > 24
        shares.append(float(diff.mean()))
    s = np.array(shares) if shares else np.zeros(1)
    return {"pairs": len(shares), "mean": round(float(s.mean()) * 100, 3), "max": round(float(s.max()) * 100, 3),
            "pairs_with_change": int((s > 0.0005).sum())}


def main():
    run_s, pans_s = load(sys.argv[1])
    print("mit Schnappen:   ", measure(run_s, pans_s, True))
    if len(sys.argv) > 2:
        run_n, pans_n = load(sys.argv[2])
        print("ohne Schnappen:  ", measure(run_n, pans_n, False))


if __name__ == "__main__":
    main()
