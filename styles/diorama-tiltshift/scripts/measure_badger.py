#!/usr/bin/env python3
"""Füße und Kopf des Dachses nachmessen (PIPELINE.md → Figuren und Animation).

    .venv/bin/python styles/diorama-tiltshift/scripts/measure_badger.py [TMP_DIR]

1. Weltmaß: Godot-Lauf mit --measure (6 s, 30 fps, Movie-Writer). main.gd gibt je Bild Ferse und Zehenspitze
   beider Füße (Knochen foot.L/foot.R) und die Kopfspitze aus. Ein Fuß gilt als aufgesetzt, wenn sein tiefster
   Punkt unter 6 mm liegt (die Sohle steht bei 3 mm); gemessen wird, wie weit dieser Punkt von Bild zu Bild über den Boden wandert
   (Rutschen), getrennt nach Laufen, Abbiegen, Bremsen und Stehen/Winken.
2. Bildmaß: derselbe Ablauf mit fester Kamera (Nahaufnahme) und --mask (Dachs weiß, Rest schwarz). Je Bild
   unterste und oberste Zeile der Silhouette; in den Steh- und Winkbildern muss die Fußzeile gleich bleiben,
   der Kopf darf nicht springen.
"""
import json, pathlib, re, subprocess, sys, tempfile

import numpy as np
from PIL import Image

DEMO = pathlib.Path(__file__).resolve().parent.parent / "demo"
CLOSE = "-7.25,4.5,9.45,-3.38,0.427,2.168,24"      # CLOSE_B aus main.gd
PHASES = [("Laufen", 0.0, 1.95), ("Abbiegen", 1.95, 3.2), ("Bremsen", 3.2, 3.58), ("Stehen/Winken", 3.6, 6.1)]
CONTACT = 0.006      # Ferse aufgesetzt (Sohle bei 3 mm); höhere Werte zählen das Aufsetzen als Rutschen mit


def run(extra, td):
    r = subprocess.run(["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
                        "--write-movie", f"{td}/f.png", "--fixed-fps", "30", "--quit-after", "180", "--", *extra],
                       capture_output=True, text=True)
    return r.stdout + r.stderr


def world(td):
    out = run(["--measure"], td)
    rows = []
    for line in out.splitlines():
        if not line.startswith("M "):
            continue
        p = line.split()
        t = float(p[1])
        feet = []
        for f in p[2:4]:
            v = [float(x) for x in f.split(",")]
            feet.append((np.array(v[0:3]), np.array(v[3:6])))
        rows.append((t, feet))
    res = {}
    worst = []
    for name, a, b in PHASES:
        slides = []
        for (t0, f0), (t1, f1) in zip(rows, rows[1:]):
            if not (a <= t1 < b):
                continue
            for k in range(2):
                # Auflagepunkt = tieferer von Ferse und Zehe; nur vergleichen, wenn es in beiden Bildern derselbe
                # Punkt ist (beim Abrollen wechselt er von der Ferse zur Zehe, das ist kein Rutschen)
                j0 = 0 if f0[k][0][1] <= f0[k][1][1] else 1
                j1 = 0 if f1[k][0][1] <= f1[k][1][1] else 1
                p0, p1 = f0[k][j0], f1[k][j1]
                if j0 == j1 and p0[1] < CONTACT and p1[1] < CONTACT:
                    d = float(np.hypot(*(p1 - p0)[[0, 2]]))
                    slides.append(d)
                    worst.append((round(1000 * d, 2), round(t1, 3), ["L", "R"][k], ["Ferse", "Zehe"][j0]))
        res[name] = {"Kontaktpaare": len(slides),
                     "Rutschen max mm": round(1000 * max(slides), 2) if slides else None,
                     "Rutschen Mittel mm": round(1000 * float(np.mean(slides)), 2) if slides else None}
    res["größte Werte (mm, s, Fuß, Punkt)"] = sorted(worst, reverse=True)[:6]
    lows = [min(f[k][j][1] for k in range(2) for j in range(2)) for _, f in rows]
    res["tiefster Fußpunkt (m), min/max je Bild"] = [round(min(lows), 4), round(max(lows), 4)]
    return res, len(rows)


def image(td):
    run([f"--cam={CLOSE}", "--mask"], td)
    frames = sorted(pathlib.Path(td).glob("f*.png"))
    out = []
    for i, f in enumerate(frames):
        a = np.asarray(Image.open(f).convert("L")) > 128
        ys, xs = np.nonzero(a)
        if len(ys) == 0:
            out.append(None)
            continue
        out.append((i / 30.0, int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())))
    stand = [o for o in out if o and o[0] >= 3.9]
    walk = [o for o in out if o and o[0] < 3.55]
    feet = sorted({o[2] for o in stand})
    heads = [o[1] for o in stand]
    jumps = [abs(b - a) for a, b in zip(heads, heads[1:])]
    return {"Bilder mit Dachs": sum(1 for o in out if o),
            "Fußzeile beim Stehen/Winken (alle Werte)": feet,
            "Kopfzeile beim Stehen/Winken min/max": [min(heads), max(heads)] if heads else None,
            "größter Kopfsprung von Bild zu Bild (px)": max(jumps) if jumps else None,
            "Höhe Dachs im Stehen (px)": (stand[0][2] - stand[0][1]) if stand else None,
            "Fußzeile beim Laufen min/max": [min(o[2] for o in walk), max(o[2] for o in walk)] if walk else None}


def main():
    base = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(tempfile.mkdtemp())
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    (base / "w").mkdir(parents=True, exist_ok=True)
    (base / "m").mkdir(parents=True, exist_ok=True)
    w, n = world(base / "w")
    im = image(base / "m")
    print(json.dumps({"Weltmaß (Knochen)": w, "Messbilder": n, "Bildmaß (feste Nahaufnahme, Maske)": im},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
