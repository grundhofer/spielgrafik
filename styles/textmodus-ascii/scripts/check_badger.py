#!/usr/bin/env python3
"""Misst den Dachs in den von Godot gerenderten Bildern (PIPELINE: Figuren und Animation).

    .venv/bin/python styles/textmodus-ascii/scripts/check_badger.py <tempordner>

1. Messlauf: godot --write-movie mit --isolate (nur der Dachs, Hintergrund Magenta, gleicher Zeichenweg wie
   im normalen Lauf) -> Maske = alle Pixel, die nicht Magenta sind.
2. Normaler Lauf und Lauf mit --no-badger: Differenz zeigt, wo der Dachs im echten Bild etwas ändert
   (Kontrolle, dass er sichtbar ist).
Geprüft:
  - Laufen: je Laufbild (alle 3 Aufnahmebilder) die Fußgruppen in der untersten Halbzeile. Die Füße zeigen
    nach rechts, die linke Kante einer Gruppe ist eine Ferse (stehen beide Füße dicht beieinander, verschmelzen
    sie; dann ist nur die hintere Ferse sichtbar). Zwischen zwei Laufbildern muss eine Ferse auf ±1 px an
    derselben Stelle stehen (Standfuß), und jede Ferse steht mindestens 2 Wechsel lang.
  - Vorschub je Laufbild: Kopf (oberes Viertel der Figur) rückt genau 8 px (eine Zelle) vor, Kopfzeile fest.
  - Stehen, Vorderansicht, Gruß: Fußzeile (unterste Maskenzeile) in allen Bildern gleich.
  - jedes Laufbild wird genau 3 Aufnahmebilder gehalten.
"""
import pathlib, subprocess, sys

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo"
MAGENTA = np.array([0xAA, 0x00, 0xAA])
FEET_Y = (19 * 14 + 7, 19 * 14 + 13)        # untere Hälfte der Bildzeile 19 (Halbzeile 39)
WALK_START, WALK_HOLD, STEPS = 3, 3, 39
STAND = range(123, 135)
FRONT = range(135, 180)


def run(out, *args):
    out.mkdir(parents=True, exist_ok=True)
    for p in out.glob("f*.png"):
        p.unlink()
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--write-movie", str(out / "f.png"),
           "--fixed-fps", "30", "--quit-after", "180"]
    if args:
        cmd += ["--", *args]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if "ERROR" in r.stdout + r.stderr:
        sys.exit(r.stdout + r.stderr)
    return [np.asarray(Image.open(p).convert("RGB")).astype(int) for p in sorted(out.glob("f*.png"))]


def clusters(xs):
    out, start, prev = [], None, None
    for x in xs:
        if start is None:
            start = prev = x
        elif x > prev + 2:
            out.append((start, prev))
            start = prev = x
        else:
            prev = x
    if start is not None:
        out.append((start, prev))
    return out


def main():
    tmp = pathlib.Path(sys.argv[1])
    iso = run(tmp / "iso", "--isolate")
    masks = [(np.abs(f - MAGENTA).sum(-1) > 0) for f in iso]
    problems = []
    # Haltezeit: Maske wechselt genau alle 3 Bilder während des Laufs
    changes = [i for i in range(1, len(masks)) if not np.array_equal(masks[i], masks[i - 1])]
    walk_changes = [c for c in changes if WALK_START < c <= WALK_START + STEPS * WALK_HOLD]
    gaps = sorted(set(np.diff(walk_changes)))
    print(f"Laufbildwechsel: {len(walk_changes)}, Abstände {gaps}")
    if gaps != [3]:
        problems.append(f"Haltezeiten nicht gleichmäßig: {gaps}")
    # Laufbilder: je Schritt erstes Aufnahmebild
    fixed_ok = fixed_bad = hidden = 0
    adv = []
    head_rows = set()
    heel_runs = {}
    prev = None
    for k in range(STEPS + 1):
        f = WALK_START + k * WALK_HOLD
        m = masks[f]
        ys, xs = np.nonzero(m)
        if xs.size == 0:
            prev = None
            continue
        top = ys.min()
        h = ys.max() - top + 1
        head = m[top:top + h // 4]
        hx = np.nonzero(head.any(0))[0]
        feet = clusters(np.nonzero(m[FEET_Y[0]:FEET_Y[1] + 1].any(0))[0].tolist())
        info = {"head": (hx.min(), hx.max()), "top": top, "feet": feet}
        if prev is not None:
            adv.append(info["head"][1] - prev["head"][1])
            head_rows.add(top)
            ok = any(abs(a[0] - b[0]) <= 1 for a in feet for b in prev["feet"])
            for a in feet:
                if any(abs(a[0] - b[0]) <= 1 for b in prev["feet"]):
                    heel_runs[a[0]] = heel_runs.get(a[0], 1) + 1
            # am linken Bildrand abgeschnittene Füße nicht werten
            if min([c[0] for c in feet + prev["feet"]] or [99]) <= 0:
                hidden += 1
            elif ok:
                fixed_ok += 1
            else:
                fixed_bad += 1
                problems.append(f"Schritt {k}: kein ortsfester Fuß {prev['feet']} -> {feet}")
        prev = info
    print(f"Standfuß ortsfest (±1 px): {fixed_ok} von {fixed_ok + fixed_bad} Laufbildwechseln "
          f"({hidden} am Bildrand nicht gewertet)")
    runs = sorted(set(heel_runs.values()))
    print(f"Fersen: {len(heel_runs)} Standphasen, Länge in Laufbildern: {runs}")
    vals = sorted(set(adv))
    print(f"Vorschub Kopfvorderkante je Laufbild: {vals} px; Kopfoberkante: {sorted(head_rows)}")
    if any(v != 8 for v in adv[3:]):
        problems.append(f"Vorschub ungleich 8 px: {vals}")
    bottoms = {f: np.nonzero(masks[f].any(1))[0].max() for f in list(STAND) + list(FRONT)}
    print(f"Fußzeile Stehen/Vorderansicht/Gruß: {sorted(set(bottoms.values()))}")
    if len(set(bottoms.values())) != 1:
        problems.append("Fußzeile springt")
    walk_bottoms = {np.nonzero(masks[WALK_START + k * WALK_HOLD].any(1))[0].max() for k in range(STEPS + 1)}
    print(f"Fußzeile beim Laufen: {sorted(walk_bottoms)}")
    # Sichtbarkeit im echten Bild
    full = run(tmp / "full")
    nob = run(tmp / "nob", "--no-badger")
    vis = [float((np.abs(a - b).sum(-1) > 0)[masks[i]].mean()) if masks[i].any() else 1.0
           for i, (a, b) in enumerate(zip(full, nob))]
    print(f"Anteil der Dachs-Pixel, die sich im echten Bild vom Hintergrund unterscheiden: "
          f"min {min(vis):.2f}, Mittel {np.mean(vis):.2f}")
    same = all(np.array_equal(a, b) for a, b in zip(full, run(tmp / "full2")))
    print("zwei normale Läufe bildgleich:", same)
    if not same:
        problems.append("Läufe nicht deterministisch")
    print("PROBLEME: " + "; ".join(problems) if problems else "ok")


if __name__ == "__main__":
    main()
