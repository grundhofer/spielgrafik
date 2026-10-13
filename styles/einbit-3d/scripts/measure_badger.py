#!/usr/bin/env python3
"""Misst den animierten Dachs in der Demo (PIPELINE.md -> Figuren und Animation).

    .venv/bin/python styles/einbit-3d/scripts/measure_badger.py

1. Knochen: startet die Demo mit "-- --measure" und liest je Bild Ferse/Zehe beider Füße und den Kopf
   (Welt- und Bildkoordinaten in 640×360). Ein Fußpunkt, der den Boden berührt (y < 1 cm), soll über
   aufeinanderfolgende Bilder ortsfest bleiben: Weltverschiebung in mm, in der festen Totale auch in px.
2. Bild: nimmt die Demo mit "-- --mask" auf (nur der Dachs, weiß auf Schwarz, ohne Nachbearbeitung) und misst
   die unterste Zeile der Silhouette (Füße) und die Kopfzeile (oberste weiße Zeile in einem 16 px breiten
   Streifen um den Kopfpunkt, damit der Winkarm nicht mitzählt): feste Totale (0–2,4 s), Lauf in Einstellung 2
   (2,4 s bis IDLE_T) und Ruhe in Einstellung 2 (ab 4,25 s, Überblenden und Schwenk beendet, Stehen und Winken).
"""
import pathlib, subprocess, tempfile

import numpy as np
from PIL import Image

DEMO = pathlib.Path(__file__).resolve().parent.parent / "demo"
FPS = 30
TOTALE = (0.0, 2.4)      # CUT_T in main.gd
IDLE_T = 3.73            # wie main.gd
BLEND_END = IDLE_T + 0.35  # IDLE_BLEND
PIN_END = IDLE_T + 0.5     # PIN_TIME: bis hierher wird der Standfuß festgehalten, die Kamera folgt noch
WALK2 = (2.4, IDLE_T)    # Lauf in Einstellung 2
REST = (PIN_END + 0.02, 6.01)


def run(args, frames_dir=None, n=180):
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
           "--fixed-fps", str(FPS), "--quit-after", str(n)]
    if frames_dir:
        cmd += ["--write-movie", str(pathlib.Path(frames_dir) / "f.png")]
    cmd += ["--"] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    return r.stdout + r.stderr


def bones():
    rows = []
    for line in run(["--measure"]).splitlines():
        if not line.startswith("M "):
            continue
        p = line.split()
        d = {"t": float(p[1]), "shot": int(p[3]), "rot": [float(v) for v in p[5:8]]}
        i = 8
        while i < len(p):
            d[p[i]] = [float(v) for v in p[i + 1:i + 6]]
            i += 6
        rows.append(d)
    print(f"Knochen: {len(rows)} Bilder")

    def ground(r, side):
        pts = [r[k + side] for k in ("heel.", "toe.") if r[k + side][1] < 0.01]
        return np.mean(pts, axis=0) if pts else None

    worst = {}
    for side in ("L", "R"):
        for a, b in zip(rows, rows[1:]):
            ga, gb = ground(a, side), ground(b, side)
            if ga is None or gb is None:
                continue
            same = all((a[k + side][1] < 0.01) == (b[k + side][1] < 0.01) for k in ("heel.", "toe."))
            if not same:
                continue
            seg = "Laufen" if b["t"] < IDLE_T else ("Überblendung" if b["t"] < PIN_END else "Stehen/Winken")
            mm = np.hypot(gb[0] - ga[0], gb[2] - ga[2]) * 1000
            px = np.hypot(gb[3] - ga[3], gb[4] - ga[4]) if b["t"] < TOTALE[1] else 0.0
            n, wm, wp, sm = worst.get(seg, (0, 0.0, 0.0, 0.0))
            worst[seg] = (n + 1, max(wm, mm), max(wp, px), sm + mm)
    for seg, (n, wm, wp, sm) in worst.items():
        extra = f", in der festen Totale höchstens {wp:.2f} px" if seg == "Laufen" else ""
        print(f"  Standfuß {seg}: {n} Bildpaare, größte Verschiebung {wm:.1f} mm (Mittel {sm / n:.1f} mm){extra}")
    last = rows[-1]
    print(f"  Drehung am Ende {last['rot'][0]:.1f}° (Ziel −72°), Endpunkt x {last['rot'][1]:.3f} z {last['rot'][2]:.3f}")
    for name, (t0, t1) in [("Totale", TOTALE), ("Ruhe Einstellung 2", REST)]:
        sel = [r for r in rows if t0 <= r["t"] < t1]
        low = [min(r[k][1] for k in ["heel.L", "toe.L", "heel.R", "toe.R"]) for r in sel]
        print(f"  {name}: tiefster Fußpunkt {min(low) * 1000:.1f}–{max(low) * 1000:.1f} mm über dem Boden")
    still = [r for r in rows if r["t"] >= REST[0]]
    drift = max(max(np.hypot(r[k][0] - still[0][k][0], r[k][2] - still[0][k][2]) for r in still)
                for k in ["heel.L", "heel.R", "toe.L", "toe.R"]) * 1000
    print(f"  Stehen/Winken ab {REST[0]} s: Fersen und Zehen verschieben sich höchstens {drift:.1f} mm")
    return rows


def silhouettes(rows):
    head_x = {round(r["t"] * FPS): r["head"][3] for r in rows}
    with tempfile.TemporaryDirectory(prefix="einbit-3d-") as td:
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
            hx = int(round(head_x.get(i + 1, head_x.get(i, 0))))
            band = a[:, max(hx - 8, 0):hx + 8]
            hy = np.nonzero(band.any(1))[0]
            res.append(((i + 1) / FPS, int(hy.min()) if len(hy) else -1, int(ys.max()), int(xs.min()), int(xs.max())))
    for name, (t0, t1) in [("Totale", TOTALE), ("Lauf Einstellung 2", WALK2), ("Ruhe Einstellung 2", REST)]:
        sel = [r for r in res if r and t0 <= r[0] < t1]
        bottoms = [r[2] for r in sel]
        tops = [r[1] for r in sel]
        jumps = max(abs(b - a) for a, b in zip(tops, tops[1:]))
        heights = [b - t for b, t in zip(bottoms, tops)]
        print(f"  {name} ({len(sel)} Bilder): Fußzeile {min(bottoms)}–{max(bottoms)}, Kopfzeile "
              f"{min(tops)}–{max(tops)} (größter Sprung {jumps} px), Höhe je Bild {min(heights)}–{max(heights)} px")
    return res


if __name__ == "__main__":
    silhouettes(bones())
