#!/usr/bin/env python3
"""Misst den laufenden Dachs in der Vektor-Demo (PIPELINE.md -> Figuren und Animation).

    .venv/bin/python styles/vektor-display/scripts/measure_badger.py [--keep DIR]

Startet die Demo mit "-- --solo": Nur der Dachs wird gezeichnet, vorderes Bein rot, hinteres grün, der
höchste Punkt der Mütze blau; ohne Nachleuchten, Glow und Weißanteil im Strahlkern. Gemessen wird
  1. in der Welt (Ausgabe "M ..." von main.gd): Ein Fuß mit Hub 0 muss über aufeinanderfolgende Bilder an
     derselben Stelle stehen (Abweichung in mm);
  2. im Bild: unterste Zeile jeder Beinmaske (Sohle) und deren vorderes bzw. hinteres Ende
     (Zehe des vorderen, Ferse des hinteren Fußes). Steht ein Fuß (Sohle in der Bodenzeile), darf sich das
     Ende über die Standphase höchstens um 1 px bewegen; in allen Stehbildern (ab Halt) sind die
     Sohlenzeilen gleich.
"""
import argparse, pathlib, shutil, subprocess, sys, tempfile

import numpy as np
from PIL import Image

DEMO = pathlib.Path(__file__).resolve().parent.parent / "demo"
FPS = 30
N = 180
T_STAND = 3.9 + 0.27   # badger.gd: T2 + SETTLE


def run(frames_dir):
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
           "--fixed-fps", str(FPS), "--quit-after", str(N), "--write-movie", str(pathlib.Path(frames_dir) / "f.png"),
           "--", "--solo"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    log = r.stdout + r.stderr
    if "ERROR" in log:
        print(log[-2000:])
    rows = {}
    for line in log.splitlines():
        if line.startswith("M "):
            p = line.split()
            rows[int(p[1])] = [float(x) for x in p[2:]]
    return rows


def masks(path):
    a = np.asarray(Image.open(path).convert("RGB")).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    # Jede Maske hat ihren eigenen Farbkanal (additiv gezeichnet, Kern ohne Weißanteil): Überdeckung stört nicht.
    near = r > 70
    far = g > 70
    top = b > 70
    return near, far, top


def sole(m, front):
    ys, xs = np.nonzero(m)
    if len(ys) == 0:
        return None
    y = ys.max()
    sel = ys >= y - 1
    return int(y), int(xs[sel].max() if front else xs[sel].min())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", help="Einzelbilder hier behalten")
    a = ap.parse_args()
    td = a.keep or tempfile.mkdtemp(prefix="vektor-display-measure-")
    pathlib.Path(td).mkdir(parents=True, exist_ok=True)
    world = run(td)
    pngs = sorted(pathlib.Path(td).glob("f*.png"))
    print(f"{len(pngs)} Bilder, {len(world)} Messzeilen")

    # 1. Welt: Standfuß ortsfest
    worst_mm = 0.0
    contacts = 0
    for j, (ix, iy) in enumerate([(1, 2), (3, 4)]):
        prev = None
        for f in sorted(world):
            v = world[f]
            if v[iy] < 1e-6:
                if prev is not None and prev[0] == f - 1:
                    worst_mm = max(worst_mm, abs(v[ix] - prev[1]) * 1000.0)
                    contacts += 1
                prev = (f, v[ix])
            else:
                prev = None
    print(f"Welt: {contacts} Paare aufeinanderfolgender Standbilder, größte Verschiebung des Standfußes {worst_mm:.3f} mm")

    # 2. Bild
    res = []
    for i, p in enumerate(pngs):
        near, far, top = masks(p)
        res.append((sole(near, True), sole(far, False), np.nonzero(top)[0].min() if top.any() else None))
    ground = max(r[0][0] for r in res if r[0])
    worst_px = 0
    pairs = 0
    for k, name in [(0, "vorn (Zehe)"), (1, "hinten (Ferse)")]:
        run_x = []
        for i, r in enumerate(res):
            s = r[k]
            # am linken Bildrand angeschnittene Füße (x <= 1) nicht werten
            if s and s[1] > 1 and s[0] >= ground - 1 and world.get(i, [0] * 6)[2 if k == 0 else 4] < 1e-6:
                run_x.append((i, s[1]))
            else:
                run_x.append(None)
        for i in range(1, len(run_x)):
            if run_x[i] and run_x[i - 1]:
                d = abs(run_x[i][1] - run_x[i - 1][1])
                worst_px = max(worst_px, d)
                pairs += 1
        print(f"Bild, Fuß {name}: Standbilder {sum(1 for x in run_x if x)}")
    print(f"Bild: {pairs} Paare, größter Sprung des Standfußes {worst_px} px (Soll <= 1)")
    stand = [r for i, r in enumerate(res) if i / FPS >= T_STAND]
    rows_n = sorted({r[0][0] for r in stand if r[0]})
    rows_f = sorted({r[1][0] for r in stand if r[1]})
    tops = [r[2] for r in stand if r[2] is not None]
    print(f"Stehen ab {T_STAND:.2f} s: {len(stand)} Bilder, Sohlenzeilen vorn {rows_n}, hinten {rows_f}, "
          f"Mützenspitze y {min(tops)}..{max(tops)} (Atmen und Nicken bei 4,55-5,35 s)")
    walk = [r for i, r in enumerate(res) if i / FPS < 3.9 and r[2] is not None]
    t = [r[2] for r in walk]
    print(f"Laufen: Mützenspitze y {min(t)}..{max(t)} (Wippen)")
    lifts = [ground - r[0][0] for r in res if r[0]]
    print(f"Schritthöhe vorn im Bild bis {max(lifts)} px")
    ok = worst_mm < 0.01 and worst_px <= 1 and len(rows_n) == 1 and len(rows_f) == 1
    print("ok" if ok else "PRÜFEN")
    if not a.keep:
        shutil.rmtree(td)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
