#!/usr/bin/env python3
"""Misst, ob der Rauch auf dem Schornstein ansetzt (Godot-Aufnahme gegen den fertigen Hintergrund).

    .venv/bin/python styles/tusche-sumie/tools/measure_smoke.py --tmp <Arbeitsordner> [--frames <Ordner mit f*.png>]

Je Bild (ab dem Zeitpunkt, an dem die Tusche ganz eingezogen ist): unterste Zeile über der Schornsteinkante, in der
sich das Bild in einem Fenster um den Schornstein um mehr als 8 (von 255) von assets/bg.png unterscheidet. Lücke =
Schornsteinkante − diese Zeile; soll ≤ 3 px sein. Schornsteinkante = oberste Zeile mit Tusche (Dichte) über dem
Schornstein in assets/bg.png. Schreibt assets/smoke_measure.json.
"""
import argparse, json, pathlib, subprocess

import numpy as np
from PIL import Image

from inkutil import ROOT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tmp", required=True)
    ap.add_argument("--frames")
    a = ap.parse_args()
    meta = json.loads((ROOT / "assets/bg_meta.json").read_text())
    sm, anim = meta["smoke"], meta["bg_anim"]
    if a.frames:
        fdir = pathlib.Path(a.frames)
    else:
        fdir = pathlib.Path(a.tmp)
        fdir.mkdir(parents=True, exist_ok=True)
        for f in fdir.glob("s*.png"):
            f.unlink()
        subprocess.run(["godot", "--path", str(ROOT / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
                        "--write-movie", str(fdir / "s.png"), "--fixed-fps", "30", "--quit-after", "180"],
                       capture_output=True, text=True, timeout=600)
    pngs = sorted(p for p in fdir.glob("*.png") if p.stem[-8:].isdigit())
    bg = np.asarray(Image.open(ROOT / "assets/bg.png").convert("RGB"), np.int16)
    x0, x1 = int(sm["x"]) - 22, int(sm["x"]) + 22
    col = bg[:, x0:x1].mean(axis=2)
    top = int(np.where((col < 120).any(axis=1))[0].min())          # Schornsteinkante (erste dunkle Zeile)
    t_full = anim["start"] + anim["dur"]
    gaps = []
    for i, p in enumerate(pngs):
        if i / 30.0 < t_full:
            continue
        f = np.asarray(Image.open(p).convert("RGB"), np.int16)
        d = np.abs(f[:top, x0:x1] - bg[:top, x0:x1]).max(axis=2)
        rows = np.where((d > 8).any(axis=1))[0]
        low = int(rows.max()) if len(rows) else None
        gaps.append({"frame": i, "lowest_smoke_row": low, "gap": None if low is None else top - 1 - low})
    g = [x["gap"] for x in gaps if x["gap"] is not None]
    out = {"chimney_top": top, "window_x": [x0, x1], "frames": len(gaps), "max_gap": max(g) if g else None,
           "mean_gap": round(float(np.mean(g)), 2) if g else None, "missing": sum(1 for x in gaps if x["gap"] is None),
           "per_frame": gaps}
    (ROOT / "assets/smoke_measure.json").write_text(json.dumps(out, indent=1))
    print("Schornsteinkante y", top, "| Bilder", len(gaps), "| Lücke max", out["max_gap"], "Mittel", out["mean_gap"],
          "| ohne Rauch", out["missing"])


if __name__ == "__main__":
    main()
