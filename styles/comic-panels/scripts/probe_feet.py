#!/usr/bin/env python3
"""Misst den Dachs in der gerenderten Demo: Fußlinie und Standfuß je Laufbild.

    .venv/bin/python styles/comic-panels/scripts/probe_feet.py [--keep DIR]

Zwei Godot-Läufe mit --probe-flat --probe-no-shadow (Farbflächen ohne Raster, deterministisch), einmal zusätzlich mit
--probe-no-badger. Die Differenz ist genau der Dachs (Farbflächen + Tusche + Außenkontur). Je 15-fps-Bild (jedes
zweite Video-Bild) werden gemessen: unterste Zeile (Fußlinie), Läufe deckender Pixel in den untersten 4 Zeilen
(Sohlen, nur Läufe ab 6 px), Kopf (oberste Zeile). Für jedes Bildpaar im Laufen: Gibt es eine Sohle, deren beide
Enden im Folgebild um höchstens 1 px verschoben sind („ganze Sohle hält“)? Sonst: kleinste Verschiebung eines
einzelnen Sohlenendes (Ferse = linkes Ende, Spitze = rechtes Ende; Fuß rollt über Ferse oder Spitze ab).
Ein Paar gilt als „Standfuß hält“, wenn eine der beiden Messungen ≤ 1 px ergibt.
Ergebnis: assets/measure_feet.json und eine Zusammenfassung auf der Konsole.
"""
import argparse, json, pathlib, subprocess, sys, tempfile

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
PANEL = (16, 16)


def render(out, extra):
    subprocess.run([sys.executable, str(ROOT / "scripts/render_frames.py"), str(out), "--", "--probe-flat",
                    "--probe-no-shadow"] + extra, check=True)


def runs(row):
    out, start = [], None
    for x, v in enumerate(list(row) + [False]):
        if v and start is None:
            start = x
        elif not v and start is not None:
            out.append((start, x - 1))
            start = None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep")
    a = ap.parse_args()
    base = pathlib.Path(a.keep) if a.keep else pathlib.Path(tempfile.mkdtemp(prefix="comic-panels-"))
    with_b, without_b = base / "with", base / "without"
    render(with_b, [])
    render(without_b, ["--probe-no-badger"])
    frames = []
    for i in range(0, 180, 2):
        x = np.asarray(Image.open(with_b / f"f{i:08d}.png").convert("RGB")).astype(int)
        y = np.asarray(Image.open(without_b / f"f{i:08d}.png").convert("RGB")).astype(int)
        m = np.abs(x - y).max(axis=2) > 40
        m[:, 838:] = False      # nur Panel A
        m[598:] = False
        ys, xs = np.where(m)
        if len(ys) == 0:
            frames.append(None)
            continue
        bottom = int(ys.max())
        soles = []
        for r in range(bottom - 3, bottom + 1):
            soles += [q for q in runs(m[r]) if q[1] - q[0] + 1 >= 6]
        frames.append({"video_frame": i, "t": round(i / 30, 3), "foot_y": bottom, "head_y": int(ys.min()),
                       "x0": int(xs.min()), "x1": int(xs.max()),
                       "soles": [list(map(int, s)) for s in sorted(set(soles))]})
    pairs = []
    for k in range(len(frames) - 1):
        f0, f1 = frames[k], frames[k + 1]
        if not f0 or not f1 or not f0["soles"] or not f1["soles"]:
            continue
        best, whole = None, None
        for s0 in f0["soles"]:
            for s1 in f1["soles"]:
                dh, dt = s1[0] - s0[0], s1[1] - s0[1]
                w = max(abs(dh), abs(dt))
                if whole is None or w < whole:
                    whole = w
                for d, e in ((dh, "Ferse"), (dt, "Spitze")):
                    if best is None or abs(d) < abs(best[0]):
                        best = (d, e)
        held = "ganze Sohle" if whole <= 1 else best[1]
        pairs.append({"t0": f0["t"], "whole_sole_max_shift": whole, "edge_shift": best[0], "held_by": held,
                      "shift": min(whole, abs(best[0])), "foot_y": [f0["foot_y"], f1["foot_y"]]})
    # nur Bilder, in denen der Dachs ganz im Panel steht (links bei x 20 beschnitten) und das Panel aufgedeckt ist
    walk = [p for p in pairs if 0.6 <= p["t0"] < 3.6 - 1e-6]
    hold = [p for p in walk if abs(p["shift"]) <= 1]
    still = [f for f in frames if f and f["t"] >= 3.6]
    res = {"frames": frames, "pairs": pairs,
           "walk_pairs": len(walk), "walk_pairs_holding": len(hold),
           "walk_pairs_fail": [p for p in walk if abs(p["shift"]) > 1],
           "walk_pairs_whole_sole": sum(1 for p in walk if p["whole_sole_max_shift"] <= 1),
           "foot_y_walk": sorted(set(f["foot_y"] for f in frames if f and 0.6 <= f["t"] < 3.6)),
           "foot_y_still": sorted(set(f["foot_y"] for f in still))}
    (ROOT / "assets/measure_feet.json").write_text(json.dumps(res, indent=1))
    print(f"Laufen: {len(hold)}/{len(walk)} Bildpaare mit Standfuß ≤ 1 px, davon ganze Sohle: {res['walk_pairs_whole_sole']}")
    for p in walk:
        print("  t=%.3f  ganze Sohle max %2d px, Einzelende %+d px (%s), Fußlinie %s" % (
            p["t0"], p["whole_sole_max_shift"], p["edge_shift"], p["held_by"], p["foot_y"]))
    for p in res["walk_pairs_fail"]:
        print("  nicht gehalten:", p)
    print("Fußlinie beim Laufen:", res["foot_y_walk"], " im Stand/Drehung:", res["foot_y_still"])


if __name__ == "__main__":
    main()
