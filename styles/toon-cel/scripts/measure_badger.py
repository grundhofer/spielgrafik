#!/usr/bin/env python3
"""Misst den animierten Dachs in der Demo (PIPELINE.md -> Figuren und Animation).

    .venv/bin/python styles/toon-cel/scripts/measure_badger.py [--out DIR]

1. Knochen: startet die Demo mit "-- --measure" und liest je Bild Ferse/Zehe beider Füße und den
   Kopf (Welt- und Bildkoordinaten). Prüft: Ein Fußpunkt, der den Boden berührt (y < 1 cm), bleibt
   über aufeinanderfolgende Bilder ortsfest (Weltverschiebung in mm, in der festen Totale auch in px).
2. Bild: nimmt die Demo mit "-- --mask" auf (nur der Dachs, weiß auf Schwarz) und misst in den
   gerenderten Bildern die unterste Zeile der Silhouette (Füße) und die oberste (Kopf), getrennt für
   die feste Totale (0–2,4 s) und die feste Nahaufnahme (ab 4,3 s).
"""
import argparse, pathlib, re, subprocess, sys, tempfile
import numpy as np
from PIL import Image

DEMO = pathlib.Path(__file__).resolve().parent.parent / "demo"
FPS = 30
TOTALE = (0.0, 2.4)      # Kamera fest (CAM_T0 in main.gd)
CLOSE = (4.3, 6.0)       # Kamera fest (CAM_T1)
IDLE_T = 3.57            # Umschalten auf Idle (main.gd)


def run(args, frames_dir=None, n=180):
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
           "--fixed-fps", str(FPS), "--quit-after", str(n)]
    if frames_dir:
        cmd += ["--write-movie", str(pathlib.Path(frames_dir) / "f.png")]
    cmd += ["--"] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    return r.stdout + r.stderr


def bones():
    log = run(["--measure"])
    rows = []
    for line in log.splitlines():
        if not line.startswith("M "):
            continue
        p = line.split()
        t = float(p[1])
        d = {"t": t}
        i = 2
        while i < len(p):
            d[p[i]] = [float(v) for v in p[i + 1:i + 6]]
            i += 6
        rows.append(d)
    print(f"Knochen: {len(rows)} Bilder")
    # Bodenpunkt je Fuß: Mittel seiner Punkte unter 1 cm (Ferse, Zehe oder beide, wenn flach)
    def ground(r, side):
        pts = [r[k + side] for k in ("heel.", "toe.") if r[k + side][1] < 0.01]
        return np.mean(pts, axis=0) if pts else None
    worst = {}
    for side in ("L", "R"):
        for a, b in zip(rows, rows[1:]):
            ga, gb = ground(a, side), ground(b, side)
            if ga is None or gb is None:
                continue
            # gleiche Kontaktart in beiden Bildern (sonst wandert der Bodenpunkt beim Abrollen)
            same = all((a[k + side][1] < 0.01) == (b[k + side][1] < 0.01) for k in ("heel.", "toe."))
            if not same:
                continue
            seg = "Laufen" if b["t"] < IDLE_T else ("Überblendung" if b["t"] < 3.95 else "Stehen")
            mm = np.hypot(gb[0] - ga[0], gb[2] - ga[2]) * 1000
            px = np.hypot(gb[3] - ga[3], gb[4] - ga[4]) if b["t"] <= TOTALE[1] else 0.0
            n, wm, wp = worst.get(seg, (0, 0.0, 0.0))
            worst[seg] = (n + 1, max(wm, mm), max(wp, px))
    for seg, (n, wm, wp) in worst.items():
        extra = f", in der festen Totale höchstens {wp:.2f} px" if seg == "Laufen" else ""
        print(f"  Standfuß {seg}: {n} Bildpaare, größte Verschiebung {wm:.1f} mm{extra}")
    rot = [r["rot"][0] for r in rows]
    print(f"  Drehung am Ende des Laufs {rot[-1]:.1f}° (Ziel −60°), Endpunkt x {rows[-1]['rot'][1]:.2f} z {rows[-1]['rot'][2]:.2f}")
    for name, (t0, t1) in [("Totale", TOTALE), ("Nahaufnahme", CLOSE)]:
        sel = [r for r in rows if t0 <= r["t"] <= t1]
        low = [min(r[k][1] for k in ["heel.L", "toe.L", "heel.R", "toe.R"]) for r in sel]
        print(f"  {name}: tiefster Fußpunkt {min(low) * 1000:.1f}–{max(low) * 1000:.1f} mm über dem Boden")
    still = [r for r in rows if r["t"] >= 3.9]
    drift = max(max(abs(r[k][0] - still[0][k][0]) for r in still) for k in ["heel.L", "heel.R"]) * 1000
    print(f"  Stehen/Winken ab 3,9 s: Fersen verschieben sich höchstens {drift:.1f} mm")
    return rows


def silhouettes():
    with tempfile.TemporaryDirectory() as td:
        run(["--mask"], td)
        pngs = sorted(pathlib.Path(td).glob("f*.png"))
        print(f"Silhouette: {len(pngs)} Bilder")
        res = []
        for i, p in enumerate(pngs):
            a = np.asarray(Image.open(p).convert("L")) > 128
            ys, xs = np.nonzero(a)
            if len(ys) == 0:
                res.append(None)
                continue
            res.append((i / FPS, ys.min(), ys.max(), xs.min(), xs.max()))
    for name, (t0, t1) in [("Totale", TOTALE), ("Nahaufnahme", CLOSE)]:
        sel = [r for r in res if r and t0 <= r[0] < t1]
        bottoms = [r[2] for r in sel]
        tops = [r[1] for r in sel]
        heights = [r[2] - r[1] for r in sel]
        jumps = max(abs(b - a) for a, b in zip(tops, tops[1:]))
        print(f"  {name} ({len(sel)} Bilder): Fußzeile {min(bottoms)}–{max(bottoms)}, Kopfzeile "
              f"{min(tops)}–{max(tops)} (größter Sprung {jumps} px), Höhe {min(heights)}–{max(heights)} px")
    return res


if __name__ == "__main__":
    bones()
    silhouettes()
