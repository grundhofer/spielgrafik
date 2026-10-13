#!/usr/bin/env python3
"""Dachs in der Godot-Aufnahme messen: Lauf mit Figur minus Lauf ohne Figur (--probe-no-badger).

    .venv/bin/python styles/minimal-geometrisch/scripts/measure_badger.py [--keep DIR]

Beide Läufe sind deterministisch (feste Bildrate, feste Saat); die Differenz ist genau die Figur samt Schatten.
Gemessen werden nur Pixel in der Fellfarbe NIGHT (Beine, Füße), damit der Schattenstrich nicht mitzählt.

Prüfungen:
  * Fußlinie: unterste Zeile der Füße ist in allen 180 Bildern gleich (eine Sohle steht immer auf dem Kai).
  * Standfuß: zwischen zwei aufeinanderfolgenden Bildern gibt es einen Bodenkontakt (Pixelläufe in den untersten
    5 Zeilen), dessen linke und rechte Kante sich um höchstens 1 px verschieben.
  * Stand (nach dem Anhalten): Bodenkontakte und Fußlinie ändern sich gar nicht mehr.
  * Kopf: oberste Zeile der Figur (Mütze) je Bild, für die Auf-und-ab-Bewegung beim Gehen.
"""
import argparse, json, pathlib, re, subprocess, sys, tempfile

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent.parent
NIGHT = np.array([0x19, 0x1A, 0x32], np.int16)
GROUND = 578          # Fußlinie im Skript (main.gd)
UI_TOP = 598
_SRC = (HERE / "demo" / "main.gd").read_text()
_K = {k: float(re.search(rf"^const {k} := ([\d.]+)", _SRC, re.M).group(1)) for k in ("N_STEPS", "STEP", "STEP_T", "GAP")}
T_WALK = _K["N_STEPS"] * _K["STEP_T"]
# Ende des Gehens laut main.gd: Schritte plus Abbremsen über (STEP/2 + GAP/2) mit Anfangstempo STEP/STEP_T
T_STOP = T_WALK + 2 * (_K["STEP"] / 2 + _K["GAP"] / 2) / (_K["STEP"] / _K["STEP_T"])


def record(d, extra):
    d.mkdir(parents=True, exist_ok=True)
    for f in d.glob("f*.png"):
        f.unlink()
    cmd = ["godot", "--path", str(HERE / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
           "--write-movie", str(d / "f.png"), "--fixed-fps", "30", "--quit-after", "180"] + extra
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    bad = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    if bad:
        sys.exit("Godot-Fehler: " + bad[0])
    return sorted(d.glob("f*.png"))


def runs(cols):
    out, start = [], None
    for i, c in enumerate(cols):
        if c and start is None:
            start = i
        if not c and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(cols) - 1))
    return out


ap = argparse.ArgumentParser()
ap.add_argument("--keep", help="Einzelbilder hierhin schreiben statt in ein Temp-Verzeichnis")
a = ap.parse_args()
base = pathlib.Path(a.keep) if a.keep else pathlib.Path(tempfile.mkdtemp())
with_b = record(base / "with", [])
without = record(base / "without", ["--", "--probe-no-badger"])
n = min(len(with_b), len(without))

frames = []
for i in range(n):
    A = np.asarray(Image.open(with_b[i]).convert("RGB"), np.int16)
    B = np.asarray(Image.open(without[i]).convert("RGB"), np.int16)
    diff = np.abs(A - B).max(2) > 24
    diff[UI_TOP:] = False
    fur = diff & (np.abs(A - NIGHT).max(2) < 40)
    ys, xs = np.nonzero(diff)
    fys, fxs = np.nonzero(fur[GROUND - 30:])
    bottom = int(fys.max()) + GROUND - 30 if len(fys) else None
    contact = runs(fur[GROUND - 4:GROUND + 2].any(0)) if bottom is not None else []
    frames.append({"i": i, "t": round(i / 30, 3), "top": int(ys.min()) if len(ys) else None,
                   "x0": int(xs.min()) if len(xs) else None, "x1": int(xs.max()) if len(xs) else None,
                   "bottom": bottom, "contact": contact})

def shift(r0, r1):
    """Verschiebung eines Bodenkontakts. Setzt der zweite Fuß direkt neben dem Standfuß auf (oder hebt dort ab),
    verschmelzen beide zu einem Lauf: Dann bleibt eine Kante fest und der Lauf enthält den anderen. Das ist kein
    Rutschen; gezählt wird es unter "merges"."""
    d = max(abs(r0[0] - r1[0]), abs(r0[1] - r1[1]))
    inner, outer = (r0, r1) if (r1[0] <= r0[0] and r1[1] >= r0[1]) else (r1, r0)
    if outer[0] <= inner[0] and outer[1] >= inner[1] and min(abs(outer[0] - inner[0]), abs(outer[1] - inner[1])) <= 1:
        return min(d, 0), d > 1
    return d, False


bottoms = sorted({f["bottom"] for f in frames})
slides, merges, worst = [], [], 0
for f0, f1 in zip(frames, frames[1:]):
    cands = [shift(r0, r1) for r0 in f0["contact"] for r1 in f1["contact"]]
    best, merged = min(cands, default=(99, False))
    worst = max(worst, best)
    if merged:
        merges.append((f0["i"], f1["i"], f0["contact"], f1["contact"]))
    if best > 1:
        slides.append((f0["i"], f1["i"], best, f0["contact"], f1["contact"]))
idle = [f for f in frames if f["t"] > T_STOP + 0.05]
idle_contacts = {tuple(map(tuple, f["contact"])) for f in idle}
walk = [f for f in frames if f["t"] < T_WALK]
tops_walk = [f["top"] for f in walk]
tops_idle = sorted({f["top"] for f in idle})

summary = {
    "frames": n,
    "foot_line_rows": bottoms,
    "max_contact_shift_px": worst,
    "frames_with_slide": len(slides),
    "touchdown_merges": [[m[0], m[1]] for m in merges],
    "idle_frames": len(idle),
    "idle_contact_variants": len(idle_contacts),
    "idle_contacts": [list(c) for c in idle_contacts],
    "head_top_walk_min_max": [min(tops_walk), max(tops_walk)],
    "head_top_idle_values": tops_idle,
    "badger_height_px_idle": (idle[-1]["bottom"] - idle[-1]["top"] + 1) if idle else None,
    "x_extent_first_last": [[frames[0]["x0"], frames[0]["x1"]], [frames[-1]["x0"], frames[-1]["x1"]]],
}
print(json.dumps(summary, indent=1))
for s in slides[:12]:
    print("Rutschen zwischen Bild %d und %d: %d px  %s -> %s" % s)
ok = len(bottoms) == 1 and worst <= 1 and len(idle_contacts) == 1
print("ok" if ok else "PROBLEME")
sys.exit(0 if ok else 2)
