#!/usr/bin/env python3
"""Füße und Kopf des Dachses in der laufenden Godot-Demo messen.

    .venv/bin/python styles/vorgerenderte-sprites/scripts/measure_feet.py [--seconds 6] [--t0 0]

Nimmt die Demo mit --mask auf (nur der Dachs, weiß auf Schwarz, 426×240, 30 Bilder/s) in einen
Temp-Ordner unter dem Scratchpad bzw. $TMPDIR und misst je Bild:
  * unterste Zeile der Figur (Bodenkontakt), oberste Zeile (Kopf)
  * Fußstücke in den untersten zwei Zeilen (zusammenhängende Spaltenbereiche)
Beim Laufen wird jedes Fußstück ins nächste Sprite-Bild verfolgt: Ein Standfuß darf sich höchstens
1 px bewegen. Ausgabe: Tabelle je Sprite-Bild und Zusammenfassung.
"""
import argparse
import os
import pathlib
import subprocess
import tempfile

import numpy as np
from PIL import Image

STYLE = pathlib.Path(__file__).resolve().parent.parent


def runs(row):
    xs = np.nonzero(row)[0]
    if len(xs) == 0:
        return []
    out, s = [], xs[0]
    for a, b in zip(xs, xs[1:]):
        if b != a + 1:
            out.append((int(s), int(a)))
            s = b
    out.append((int(s), int(xs[-1])))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=6.0)
    ap.add_argument("--t0", type=float, default=0.0)
    a = ap.parse_args()
    n = int(round(a.seconds * 30))
    with tempfile.TemporaryDirectory(prefix="vorgerenderte-sprites-feet-") as td:
        subprocess.run(["godot", "--headless", "--path", str(STYLE / "demo"), "--import"], capture_output=True)
        r = subprocess.run(["godot", "--path", str(STYLE / "demo"), "--position", "20000,20000",
                            "--write-movie", os.path.join(td, "f.png"), "--fixed-fps", "30",
                            "--quit-after", str(n), "--", "--mask", f"--t0={a.t0}"],
                           capture_output=True, text=True)
        errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
        files = sorted(pathlib.Path(td).glob("f*.png"))
        rows = []
        for i, p in enumerate(files):
            m = np.asarray(Image.open(p).convert("L")) > 128
            ys, xs = np.nonzero(m)
            if len(ys) == 0:
                rows.append(None)
                continue
            bot, top = int(ys.max()), int(ys.min())
            feet = runs(m[bot - 1:bot + 1].any(0))
            rows.append({"i": i, "t": a.t0 + i / 30, "top": top, "bottom": bot, "left": int(xs.min()),
                         "right": int(xs.max()), "feet": feet})
    print(f"{len(files)} Bilder, Godot-Fehler: {len(errs)}")
    print(" Bild    t    Kopf  Boden  Fußstücke (Spalten in den untersten 2 Zeilen)")
    for r in rows[::2]:
        if r:
            print(f"{r['i']:5d} {r['t']:5.2f}  {r['top']:4d}  {r['bottom']:5d}  {r['feet']}")
    # Verfolgen: Fußstücke zwischen aufeinanderfolgenden Sprite-Bildern (je 2 Aufnahmebilder)
    moves = []
    for r0, r1 in zip(rows[::2], rows[2::2]):
        if not r0 or not r1:
            continue
        for f0 in r0["feet"]:
            if f0[1] - f0[0] < 2:
                continue
            best = min((abs((f1[0] + f1[1]) - (f0[0] + f0[1])) / 2 for f1 in r1["feet"]), default=None)
            if best is not None:
                moves.append((r0["i"], f0, best))
    planted = [mv for mv in moves if mv[2] <= 1.0]
    print(f"Fußstücke verfolgt: {len(moves)}, davon ≤ 1 px bewegt: {len(planted)}")
    bottoms = sorted({r["bottom"] for r in rows if r})
    print("Bodenzeilen über alle Bilder:", bottoms)
    tops = [r["top"] for r in rows if r]
    print("Kopfzeile min/max:", min(tops), max(tops))


if __name__ == "__main__":
    main()
