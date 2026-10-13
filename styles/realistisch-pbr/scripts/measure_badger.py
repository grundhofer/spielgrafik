#!/usr/bin/env python3
"""Misst den animierten Dachs in der Demo (PIPELINE.md -> Figuren und Animation).

    .venv/bin/python styles/realistisch-pbr/scripts/measure_badger.py [--json OUT]

Die Kamera der Aufnahme fährt die ganze Zeit; gemessen wird deshalb mit fester Kamera in der
Endeinstellung (--cam, Werte wie CAM_KEYS[2] in main.gd), dann bedeuten Pixelverschiebungen
wirklich Bewegung der Figur.
1. Knochen ("-- --measure"): je Bild Ferse/Zehe beider Füße und Kopf (Welt- und Bildkoordinaten).
   Prüft: Ein Fußpunkt am Boden (y < 1 cm) bleibt über aufeinanderfolgende Bilder ortsfest
   (Weltverschiebung in mm und Bildverschiebung in px); tiefster Fußpunkt (nichts im Boden).
2. Bild ("-- --mask"): nur der Dachs weiß auf Schwarz (ohne Fellschalen); misst unterste Zeile
   (Füße) und oberste (Kopf) der Silhouette im Stehen/Winken und die größten Sprünge von Bild zu Bild.
"""
import argparse
import json
import pathlib
import subprocess
import tempfile

import numpy as np
from PIL import Image

DEMO = pathlib.Path(__file__).resolve().parent.parent / "demo"
FPS = 30
CAM = "--cam=-0.95,1.2,5.0,-0.1,1.04,-0.4,52"
IDLE_T = 3.41      # Umschalten auf Idle (main.gd)
STAND_T = 3.75     # Überblendung auf Idle beendet (Walk eingefroren, Schwungfuß aufgesetzt)


def run(args, frames_dir=None, n=180):
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
           "--fixed-fps", str(FPS), "--quit-after", str(n)]
    if frames_dir:
        cmd += ["--write-movie", str(pathlib.Path(frames_dir) / "f.png")]
    cmd += ["--", CAM, "--no-ui"] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    return r.stdout + r.stderr


def bones(out):
    log = run(["--measure"])
    rows = []
    for line in log.splitlines():
        if not line.startswith("M "):
            continue
        p = line.split()
        d = {"t": float(p[1])}
        i = 2
        while i < len(p):
            d[p[i]] = [float(v) for v in p[i + 1:i + 6]]
            i += 6
        rows.append(d)
    print(f"Knochen: {len(rows)} Bilder")
    res = {}
    for seg_name, (t0, t1) in [("Laufen", (0.0, IDLE_T)), ("Überblendung", (IDLE_T, STAND_T)),
                               ("Stehen/Winken", (STAND_T, 6.1))]:
        # getrennt nach Kontaktart: flach (Ferse und Zehe am Boden) = Standfuß; nur Zehe = Abdrücken
        # (die Zehenspitze schleift, während die Ferse schon 3–5 cm hoch ist); nur Ferse = Aufsetzen
        stats = {}
        for side in ("L", "R"):
            for a, b in zip(rows, rows[1:]):
                if not (t0 <= b["t"] < t1):
                    continue
                da = [k for k in ("heel.", "toe.") if a[k + side][1] < 0.01]
                db = [k for k in ("heel.", "toe.") if b[k + side][1] < 0.01]
                if not da or da != db:
                    continue
                kind = "flach" if len(da) == 2 else ("Zehe" if da == ["toe."] else "Ferse")
                pa = np.mean([a[k + side] for k in da], axis=0)
                pb = np.mean([b[k + side] for k in db], axis=0)
                mm = float(np.hypot(pb[0] - pa[0], pb[2] - pa[2]) * 1000)
                px = float(np.hypot(pb[3] - pa[3], pb[4] - pa[4]))
                n, m0, p0 = stats.get(kind, (0, 0.0, 0.0))
                stats[kind] = (n + 1, max(m0, mm), max(p0, px))
        res[seg_name] = {k: {"pairs": v[0], "max_mm": round(v[1], 2), "max_px": round(v[2], 2)} for k, v in stats.items()}
        txt = ", ".join(f"{k}: {v[0]} Paare, höchstens {v[1]:.1f} mm / {v[2]:.2f} px" for k, v in stats.items())
        print(f"  Bodenpunkt {seg_name}: {txt}")
    low = [min(r[k][1] for k in ("heel.L", "toe.L", "heel.R", "toe.R")) for r in rows]
    res["lowest_mm"] = [round(min(low) * 1000, 1), round(max(low) * 1000, 1)]
    print(f"  tiefster Fußpunkt je Bild: {min(low) * 1000:.1f} bis {max(low) * 1000:.1f} mm über dem Pflaster")
    end = rows[-1]["rot"]
    res["end"] = {"rot_deg": end[0], "x": end[1], "z": end[2]}
    print(f"  Ende: Drehung {end[0]:.1f}°, x {end[1]:.2f}, z {end[2]:.2f}")
    out["bones"] = res


def silhouettes(out):
    with tempfile.TemporaryDirectory() as td:
        run(["--mask"], td)
        pngs = sorted(pathlib.Path(td).glob("f*.png"))
        rows = []
        for i, p in enumerate(pngs):
            a = np.asarray(Image.open(p).convert("L")) > 128
            ys, xs = np.nonzero(a)
            # angeschnittene Bilder (Figur am Bildrand) nicht werten
            ok = len(ys) > 0 and xs.min() > 0 and xs.max() < a.shape[1] - 1 and ys.max() < a.shape[0] - 1
            rows.append((i / FPS, int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())) if ok else None)
    print(f"Silhouette: {len(pngs)} Bilder")
    res = {}
    for name, (t0, t1) in [("Laufen", (0.0, IDLE_T)), ("Stehen/Winken", (STAND_T, 6.1))]:
        sel = [r for r in rows if r and t0 <= r[0] < t1]
        bottoms = [r[2] for r in sel]
        tops = [r[1] for r in sel]
        jb = max(abs(b - a) for a, b in zip(bottoms, bottoms[1:]))
        jt = max(abs(b - a) for a, b in zip(tops, tops[1:]))
        res[name] = {"frames": len(sel), "foot_row": [min(bottoms), max(bottoms)], "head_row": [min(tops), max(tops)],
                     "max_jump_foot_px": jb, "max_jump_head_px": jt,
                     "height_px": [min(r[2] - r[1] for r in sel), max(r[2] - r[1] for r in sel)]}
        print(f"  {name} ({len(sel)} Bilder): Fußzeile {min(bottoms)}–{max(bottoms)} (Sprung höchstens {jb} px), "
              f"Kopfzeile {min(tops)}–{max(tops)} (Sprung höchstens {jt} px)")
    out["silhouette"] = res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    out = {}
    bones(out)
    silhouettes(out)
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(out, indent=1, ensure_ascii=False))
