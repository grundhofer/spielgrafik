#!/usr/bin/env python3
"""Dachs in der Godot-Aufnahme vermessen: Höhe, Fußlinie, Standfuß in allen Phasen.

Ein Lauf wie die Aufnahme (--write-movie, --fixed-fps 30, 6 s) ohne Nachbearbeitung mit --badger-mask (Dachs
unbeleuchtet magenta, ohne Schatten) und --log-feet (Zehenspitzen beider Fußknochen je Bild in Welt- und
Bildkoordinaten, nach dem Bild-Update, also wie gerendert).

1. Bildmessung (nur Nahkamera, ab dem Schnitt bei 0,6 s): Kopf (oberste Zeile) und Fußlinie (unterste Zeile) der
   Figur je Bild. In Steh- und Winkbildern soll die Fußlinie gleich bleiben.
2. Standfuß über das ganze Video (Laufen, Bremsen, Drehen, Überblenden, Winken): Ein Fuß gilt als aufgesetzt,
   solange seine Zehe tiefer als 2,5 cm liegt (aufgesetzt 2,0 cm). Je Bildpaar mit aufgesetztem Fuß die
   Verschiebung in mm (Welt, waagerecht) und px (Bild; Paare über den Kameraschnitt nur in mm), dazu je
   Bodenkontakt die größte Abweichung vom ersten Kontaktbild (fängt langsames Gleiten über viele Bilder).
   Der nahe und der ferne Fuß stehen in der Perspektive auf verschiedenen Bildzeilen, deshalb wird je Fuß
   gemessen und nicht über die unterste Zeile der Figur.

    .venv/bin/python styles/nachbearbeitung/scripts/measure_badger.py --tmp <scratch>/measure [--keep]

Schreibt eine Zusammenfassung nach stdout und die Messwerte als JSON nach assets/measure_badger.json.
"""
import argparse
import json
import pathlib
import shutil
import subprocess

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent.parent
FPS = 30
PLANT_Y = 0.025
CUT_T = 0.6          # Schnitt Totale -> Nahkamera (main.gd CUT_T)
# Phasen nach main.gd: BRAKE_T 2,45 (+0,4), TURN_T 2,62 (+0,56), Settle 2,85–3,27, WAVE_T 3,36
PHASES = [(0.0, 2.45, "Laufen"), (2.45, 2.85, "Bremsen, Drehung beginnt"), (2.85, 3.4, "Drehen und Aufsetzen"),
          (3.4, 99.0, "Stehen und Winken")]


def render(tmp, frames):
    tmp.mkdir(parents=True, exist_ok=True)
    for f in tmp.glob("f*"):
        f.unlink()
    subprocess.run(["godot", "--headless", "--path", str(HERE / "demo"), "--import"], capture_output=True)
    r = subprocess.run(["godot", "--path", str(HERE / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
                        "--write-movie", str(tmp / "f.png"), "--fixed-fps", str(FPS), "--quit-after", str(frames),
                        "--", "--look=-1", "--no-ui", "--no-label", "--badger-mask", "--log-feet"],
                       capture_output=True, text=True)
    feet = {}
    for line in r.stdout.splitlines():
        if not line.startswith("FEET "):
            continue
        p = line.split()
        fr = int(p[1])
        feet[fr] = {"t": float(p[2]), "cam": p[15].split("=")[1]}
        for k in (3, 9):
            feet[fr][p[k]] = {"x": float(p[k + 1]), "y": float(p[k + 2]), "z": float(p[k + 3]),
                              "sx": float(p[k + 4]), "sy": float(p[k + 5])}
    return sorted(tmp.glob("f*.png")), feet


def phase_of(t):
    return next(n for a, b, n in PHASES if a <= t < b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tmp", required=True)
    ap.add_argument("--frames", type=int, default=180)
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    tmp = pathlib.Path(a.tmp)
    pngs, feet = render(tmp, a.frames)

    # 1. Bildmessung (Bild i der Aufnahme = Zeitpunkt i/30; feet[i+1] ist der Zustand dieses Bildes)
    rows = []
    for i, p in enumerate(pngs):
        im = np.asarray(Image.open(p).convert("RGB"), dtype=np.int16)
        r, g, b = im[..., 0], im[..., 1], im[..., 2]
        m = (r - g > 90) & (b - g > 90)
        ys, xs = np.nonzero(m)
        cam = feet.get(i + 1, {}).get("cam", "?")
        if len(ys) < 50 or cam != "nah":
            rows.append({"frame": i, "visible": False, "cam": cam})
            continue
        rows.append({"frame": i, "visible": True, "cam": cam, "top": int(ys.min()), "bottom": int(ys.max()),
                     "left": int(xs.min()), "right": int(xs.max()), "height": int(ys.max() - ys.min() + 1),
                     "fully_in": bool(xs.min() > 0)})
    walk = [r for r in rows if r["visible"] and r["fully_in"] and r["frame"] < int(2.45 * FPS)]
    stand = [r for r in rows if r["visible"] and r["frame"] >= int(3.4 * FPS)]

    # 2. Standfuß
    pairs, contacts = [], []
    for bn in ("foot.L", "foot.R"):
        seg = []
        for fr in sorted(feet):
            on = feet[fr][bn]["y"] < PLANT_Y
            if on:
                seg.append(fr)
            if (not on or fr == max(feet)) and len(seg) > 1:
                f0 = feet[seg[0]][bn]
                dev_mm = max(1000 * np.hypot(feet[f][bn]["x"] - f0["x"], feet[f][bn]["z"] - f0["z"]) for f in seg)
                same = [f for f in seg if feet[f]["cam"] == feet[seg[0]]["cam"]]
                dev_px = max(max(abs(feet[f][bn]["sx"] - f0["sx"]), abs(feet[f][bn]["sy"] - f0["sy"])) for f in same)
                contacts.append({"foot": bn, "t0": feet[seg[0]]["t"], "t1": feet[seg[-1]]["t"], "frames": len(seg),
                                 "drift_mm": round(float(dev_mm), 1), "drift_px": round(float(dev_px), 2)})
            if not on:
                seg = []
        for fr in sorted(feet):
            if fr + 1 not in feet:
                continue
            f0, f1 = feet[fr][bn], feet[fr + 1][bn]
            if f0["y"] < PLANT_Y and f1["y"] < PLANT_Y:
                same = feet[fr]["cam"] == feet[fr + 1]["cam"]
                pairs.append({"frame": fr + 1, "t": feet[fr + 1]["t"], "phase": phase_of(feet[fr + 1]["t"]), "foot": bn,
                              "mm": round(1000 * float(np.hypot(f1["x"] - f0["x"], f1["z"] - f0["z"])), 2),
                              "px": round(max(abs(f1["sx"] - f0["sx"]), abs(f1["sy"] - f0["sy"])), 2) if same else None})
    by_phase = {}
    for _, _, n in PHASES:
        pp = [p for p in pairs if p["phase"] == n]
        if pp:
            by_phase[n] = {"pairs": len(pp), "max_mm": max(p["mm"] for p in pp),
                           "max_px": max(p["px"] for p in pp if p["px"] is not None)}
    ts = [feet[f]["t"] for f in sorted(feet)]
    steps = np.diff(ts)
    summary = {
        "frames": len(pngs),
        "height_px_walk": [min(r["height"] for r in walk), max(r["height"] for r in walk)],
        "height_px_stand": [min(r["height"] for r in stand), max(r["height"] for r in stand)],
        "bottom_y_stand": sorted(set(r["bottom"] for r in stand)),
        "top_y_stand": [min(r["top"] for r in stand), max(r["top"] for r in stand)],
        "stand_x": [min(r["left"] for r in stand), max(r["right"] for r in stand)],
        "planted_pairs": len(pairs),
        "planted_max_px": max(p["px"] for p in pairs if p["px"] is not None),
        "planted_max_mm": max(p["mm"] for p in pairs),
        "planted_by_phase": by_phase,
        "contact_drift_max_mm": max(c["drift_mm"] for c in contacts),
        "contact_drift_max_px": max(c["drift_px"] for c in contacts),
        "time_step_s": [round(float(steps.min()), 4), round(float(steps.max()), 4)],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    for c in contacts:
        print(f"{c['foot']} {c['t0']:.2f}–{c['t1']:.2f} s ({c['frames']} Bilder): Abweichung {c['drift_mm']} mm / {c['drift_px']} px")
    (HERE / "assets" / "measure_badger.json").write_text(json.dumps(
        {"summary": summary, "contacts": contacts, "pairs": pairs}, ensure_ascii=False, indent=1))
    if not a.keep:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
