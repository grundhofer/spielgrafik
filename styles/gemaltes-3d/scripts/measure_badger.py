#!/usr/bin/env python3
"""Misst den animierten Dachs in der Demo (PIPELINE.md -> Figuren und Animation).

    .venv/bin/python styles/gemaltes-3d/scripts/measure_badger.py

Nach styles/toon-cel/scripts/measure_badger.py, angepasst an diesen Eintrag (eigener Kaiboden auf 12 mm,
Kamerafahrt bis 4,3 s, danach feste Einstellung).

1. Knochen: startet die Demo mit "-- --measure --raw" und liest je Bild Ferse/Zehe beider Füße und den
   Kopf (Welt- und Bildkoordinaten). Prüft: Ein Fußpunkt, der den Boden berührt (unter 1 cm über dem
   Kaiboden), bleibt über aufeinanderfolgende Bilder ortsfest (Weltverschiebung in mm).
2. Bild: nimmt die Demo mit "-- --mask" auf (nur der Dachs, weiß auf Schwarz, ohne Malen) und misst in
   der festen Endeinstellung (ab 4,3 s) die unterste Zeile der Silhouette (Füße) und die oberste (Kopf).
3. Gemalt: dieselbe Messung im gemalten Bild ist nicht möglich (keine Maske); stattdessen vergleicht
   compare_switches.py die Kanten des Dachses im gemalten und im ungemalten Bild.
"""
import pathlib, subprocess, sys, tempfile
import numpy as np
from PIL import Image

DEMO = pathlib.Path(__file__).resolve().parent.parent / "demo"
FPS = 30
FLOOR_Y = 0.012          # main.gd
IDLE_T = 3.31            # Umschalten auf Idle (main.gd)
BLEND_END = IDLE_T + 0.3
STATIC = (4.3, 6.0)      # Kamera fest (CAM_T1)


def run(args, frames_dir=None, n=180):
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
           "--fixed-fps", str(FPS), "--quit-after", str(n)]
    if frames_dir:
        cmd += ["--write-movie", str(pathlib.Path(frames_dir) / "f.png")]
    cmd += ["--"] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    return r.stdout + r.stderr


def bones():
    log = run(["--measure", "--raw"])
    rows = []
    for line in log.splitlines():
        if not line.startswith("M "):
            continue
        p = line.replace(",", ".").split()
        d = {"t": float(p[1]), "rot": [float(p[3]), float(p[4]), float(p[5])]}
        i = 6
        while i < len(p):
            d[p[i]] = [float(v) for v in p[i + 1:i + 6]]
            i += 6
        rows.append(d)
    print(f"Knochen: {len(rows)} Bilder")

    def down(r, side, k):
        return r[k + side][1] - FLOOR_Y < 0.01

    def ground(r, side):
        pts = [r[k + side] for k in ("heel.", "toe.") if down(r, side, k)]
        return np.mean(pts, axis=0) if pts else None

    worst = {}
    for side in ("L", "R"):
        for a, b in zip(rows, rows[1:]):
            ga, gb = ground(a, side), ground(b, side)
            if ga is None or gb is None:
                continue
            if not all(down(a, side, k) == down(b, side, k) for k in ("heel.", "toe.")):
                continue
            seg = "Laufen" if b["t"] < IDLE_T else ("Überblendung" if b["t"] < BLEND_END + 0.05 else "Stehen/Winken")
            mm = float(np.hypot(gb[0] - ga[0], gb[2] - ga[2]) * 1000)
            n, wm = worst.get(seg, (0, 0.0))
            worst[seg] = (n + 1, max(wm, mm))
    for seg, (n, wm) in worst.items():
        print(f"  Standfuß {seg}: {n} Bildpaare, größte Verschiebung je Bild {wm:.1f} mm")
    print(f"  Drehung am Ende {rows[-1]['rot'][0]:.1f}°, Endpunkt x {rows[-1]['rot'][1]:.2f} z {rows[-1]['rot'][2]:.2f}")
    # Schwungfuß beim Anhalten: wie weit bewegt er sich in den Bildern, in denen er unter 1 cm hängt?
    for side in ("L", "R"):
        sel = [r for r in rows if IDLE_T - 0.4 <= r["t"] <= BLEND_END + 0.2]
        h = [min(r["heel." + side][1], r["toe." + side][1]) - FLOOR_Y for r in sel]
        print(f"  Fuß {side} beim Anhalten ({sel[0]['t']:.2f}–{sel[-1]['t']:.2f} s): Höhe "
              f"{min(h) * 1000:.1f}–{max(h) * 1000:.1f} mm")
    still = [r for r in rows if r["t"] >= BLEND_END + 0.05]
    drift = max(max(np.hypot(r[k][0] - still[0][k][0], r[k][2] - still[0][k][2]) for r in still)
                for k in ["heel.L", "heel.R", "toe.L", "toe.R"]) * 1000
    print(f"  Stehen/Winken ab {BLEND_END + 0.05:.2f} s: Fußpunkte verschieben sich höchstens {drift:.1f} mm")
    low = [min(r[k][1] for k in ["heel.L", "toe.L", "heel.R", "toe.R"]) - FLOOR_Y for r in rows]
    print(f"  tiefster Fußpunkt je Bild: {min(low) * 1000:.1f}–{max(low) * 1000:.1f} mm über dem Kaiboden")
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
            res.append((i / FPS, ys.min(), ys.max(), xs.min(), xs.max()) if len(ys) else None)
    t0, t1 = STATIC
    sel = [r for r in res if r and t0 <= r[0] < t1]
    bottoms = [r[2] for r in sel]
    tops = [r[1] for r in sel]
    heights = [r[2] - r[1] for r in sel]
    jumps = max(abs(b - a) for a, b in zip(tops, tops[1:]))
    print(f"  feste Endeinstellung ({len(sel)} Bilder): Fußzeile {min(bottoms)}–{max(bottoms)}, Kopfzeile "
          f"{min(tops)}–{max(tops)} (größter Sprung {jumps} px), Höhe {min(heights)}–{max(heights)} px")
    return res


if __name__ == "__main__":
    bones()
    silhouettes()
