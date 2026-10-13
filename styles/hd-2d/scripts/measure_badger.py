#!/usr/bin/env python3
"""Misst den Dachs in der gerenderten Demo (PIPELINE.md, Figuren und Animation).

    .venv/bin/python styles/hd-2d/scripts/measure_badger.py [--tmp <ordner>] [--keep]

Nimmt die Demo mit `-- --solo --static-cam` auf (nur der Dachs als weiße Fläche vor Schwarz, Kamera steht in der
Anfangsstellung, sonst gleiche Abläufe) und misst je Aufnahmebild: oberste und unterste Zeile, Bodenkontakt
(deckende Pixel in den untersten KONTAKT Zeilen) als zusammenhängende Spannen.
Laufen: Für jeden Wechsel des Laufbildes wird jede Kontaktspanne mit der am besten überlappenden Spanne des
nächsten Laufbildes verglichen. Steht ein Fuß, bleiben linke und rechte Kante gleich. Ausgegeben wird je Wechsel
die kleinste Kantenverschiebung (Standfuß) in Bildschirmpixeln und in Sprite-Pixeln.
Stehen: unterste Zeile und Fußspannen in allen Bildern ab der Drehung.
"""
import argparse
import json
import pathlib
import shutil
import subprocess
import tempfile

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
FPS = 30
WALK_FPS = 15
TURN_T = 3.2
KONTAKT = 4      # Bildschirmzeilen über der untersten Zeile, die als Bodenkontakt zählen


def _unused_spans(row):
    xs = np.flatnonzero(row)
    if not len(xs):
        return []
    out, s, p = [], xs[0], xs[0]
    for x in xs[1:]:
        if x - p > 1:
            out.append((int(s), int(p)))
            s = x
        p = x
    out.append((int(s), int(p)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tmp", default="")
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    td = pathlib.Path(a.tmp or tempfile.mkdtemp(prefix="hd-2d_measure_"))
    td.mkdir(parents=True, exist_ok=True)
    demo = ROOT / "demo"
    subprocess.run(["godot", "--headless", "--path", str(demo), "--import"], capture_output=True)
    r = subprocess.run(["godot", "--path", str(demo), "--position", "20000,20000", "--resolution", "1280x720",
                        "--write-movie", str(td / "f.png"), "--fixed-fps", str(FPS), "--quit-after", "180",
                        "--", "--solo", "--static-cam"], capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    pngs = sorted(td.glob("f*.png"))
    rows = []
    for i, p in enumerate(pngs):
        c = np.asarray(Image.open(p).convert("RGB")).astype(np.int64)
        g = c.max(2) > 8                           # alles außer dem schwarzen Hintergrund
        ys = np.flatnonzero(g.any(1))
        if not len(ys):
            rows.append(None)
            continue
        rec = {"i": i, "t": round(i / FPS, 3), "top": int(ys[0]), "bottom": int(ys[-1])}
        # Füße aus dem Messbild: grün = nahes Bein, blau = fernes Bein (nur Laufbilder)
        for name, m in (("near", (c[..., 1] > 150) & (c[..., 0] < 100) & (c[..., 2] < 100)),
                        ("far", (c[..., 2] > 150) & (c[..., 0] < 100) & (c[..., 1] < 100))):
            yy = np.flatnonzero(m.any(1))
            if len(yy):
                lo = int(yy[-1])
                band = m[lo - 2:lo + 1].any(0)
                xs = np.flatnonzero(band)
                rec[name] = {"low": lo, "x0": int(xs[0]), "x1": int(xs[-1])}
        rows.append(rec)
    stand = [r for r in rows if r and r["t"] >= TURN_T + 0.05]
    px_per_sprite = float(np.median([r["bottom"] - r["top"] + 1 for r in stand])) / 60.0
    walk = [r for r in rows if r and r["t"] < TURN_T - 1e-6]
    step = FPS // WALK_FPS
    wf = walk[::step]                              # je Laufbild ein Aufnahmebild
    # Standphasen aus dem Rig (blender/pose_layout.py, FOOT-Ausgabe): fernes Bein (L) steht in den Phasen
    # 0-4, nahes Bein (R) in 4-7 und 0 des nächsten Zyklus. Phase = Laufbild modulo 8.
    STANCE = {"near": [4, 5, 6, 7, 8], "far": [0, 1, 2, 3, 4]}
    stance = []
    for f, ph in STANCE.items():
        for c0 in range(0, len(wf), 8):
            run = [wf[c0 + p] for p in ph if c0 + p < len(wf) and f in wf[c0 + p]]
            if len(run) < 3:
                continue
            x0 = [r[f]["x0"] for r in run]
            x1 = [r[f]["x1"] for r in run]
            lo = [r[f]["low"] for r in run]
            stance.append({"foot": f, "frames": [r["i"] for r in run], "heel_x0": x0, "toe_x1": x1, "low": lo,
                           "toe_spread_px": int(max(x1) - min(x1)), "heel_spread_px": int(max(x0) - min(x0)),
                           "toe_step_max_px": int(max(abs(np.diff(x1)))) if len(x1) > 1 else 0})
    res = {
        "frames": len(pngs), "godot_errors": errs[:5], "px_per_sprite_px": round(px_per_sprite, 3),
        "walk": {"stance_phases": stance,
                 "near_toe_spread_max_px": max(s["toe_spread_px"] for s in stance if s["foot"] == "near"),
                 "near_toe_step_max_px": max(s["toe_step_max_px"] for s in stance if s["foot"] == "near"),
                 "far_toe_spread_max_px": max(s["toe_spread_px"] for s in stance if s["foot"] == "far"),
                 "top_rows": sorted(set(r["top"] for r in walk))},
        "stand": {"frames": len(stand), "bottom_rows": sorted(set(r["bottom"] for r in stand)),
                  "top_rows": sorted(set(r["top"] for r in stand))},
    }
    out = ROOT / "assets" / "measure_badger.json"
    out.write_text(json.dumps({"summary": res, "frames": rows}, indent=1))
    print(json.dumps(res, indent=1))
    if not a.keep and not a.tmp:
        shutil.rmtree(td)


if __name__ == "__main__":
    main()
