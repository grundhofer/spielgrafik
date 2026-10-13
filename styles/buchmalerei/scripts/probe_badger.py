#!/usr/bin/env python3
"""Misst den gleitenden Dachs in den gerenderten Godot-Bildern (PIPELINE.md → Figuren und Animation).

    .venv/bin/python styles/buchmalerei/scripts/probe_badger.py [--tmp <ordner>]

Zwei deterministische Läufe (6 s, 30 Bilder/s): normal und mit --probe-no-badger. Die Differenz ist genau die
Figur. Gemessen je Bild:
  sole_y   unterste Zeile mit mindestens 8 Figurpixeln (Sohlenlinie)
  foot_x   Mitte der Figurpixel in den untersten 6 Zeilen
  cap_y    oberste Figurzeile im linken 60 % der Figur (Mütze; die erhobene Hand liegt rechts)
Prüfungen:
  - Gleiten: Vorschub je Bild folgt der Smoothstep-Kurve ohne Rückschritt, kein Sprung > 9 px.
  - Stehen (ab Bild 85 = 2,83 s): Sohlenlinie und Mützenoberkante in allen Bildern gleich; außerhalb des
    Unterarms ändert sich zwischen aufeinanderfolgenden Bildern kein Figurpixel.
Ergebnis: assets/measure_badger.json
"""
import argparse, json, pathlib, sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from render_frames import render  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
WIN = (64, 48, 792, 524)
STAND_FROM = 85


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tmp", default="/tmp/buchmalerei_probe")
    ap.add_argument("--frames", type=int, default=180)
    a = ap.parse_args()
    tmp = pathlib.Path(a.tmp)
    A = render(tmp / "with", a.frames)
    B = render(tmp / "without", a.frames, ["--probe-no-badger"])
    badger = json.loads((ROOT / "assets/badger.json").read_text())
    x0, y0, w, h = WIN
    rows = []
    prev_rgb = None
    prev_mask = None
    for i, (pa, pb) in enumerate(zip(A, B)):
        ia = np.array(Image.open(pa).convert("RGB")).astype(np.int16)[y0:y0 + h, x0:x0 + w]
        ib = np.array(Image.open(pb).convert("RGB")).astype(np.int16)[y0:y0 + h, x0:x0 + w]
        m = np.abs(ia - ib).sum(-1) > 24
        r = {"frame": i, "t": round(i / 30.0, 3), "px": int(m.sum())}
        if m.sum() > 50:
            ys, xs = np.nonzero(m)
            cnt = m.sum(1)
            sole = int(max(y for y in range(h) if cnt[y] >= 8))
            bottom = m[sole - 5:sole + 1]
            bx = np.nonzero(bottom.any(0))[0]
            left, right = xs.min(), xs.max()
            cols = (xs <= left + 0.6 * (right - left))
            r.update({"sole_y": sole, "foot_x": round(float(bx.mean()), 2), "cap_y": int(ys[cols].min()),
                      "bbox": [int(left), int(ys.min()), int(right), int(ys.max())]})
            # Körperpixel (ohne Unterarm): alles unterhalb der Manschette und links der Arm-Spalten
            if prev_rgb is not None and i >= STAND_FROM:
                piv_y = r["sole_y"] - (badger["foot"][1] - badger["pivot"][1])
                piv_x = r["foot_x"] - (badger["foot"][0] - badger["pivot"][0])
                yy, xx = np.mgrid[0:h, 0:w]
                arm_zone = (yy < piv_y + 14) & (xx > piv_x - 40)
                body = (m | prev_mask) & ~arm_zone
                changed = (np.abs(ia - prev_rgb).sum(-1) > 24) & body
                r["body_changed_px"] = int(changed.sum())
        rows.append(r)
        prev_rgb, prev_mask = ia, m

    vis = [r for r in rows if "sole_y" in r]
    full = [r for r in vis if r["bbox"][0] > 0]          # Figur ganz im Fenster
    stand = [r for r in vis if r["frame"] >= STAND_FROM]
    adv = [round(b["foot_x"] - a_["foot_x"], 2) for a_, b in zip(full, full[1:]) if b["frame"] < STAND_FROM + 1]
    res = {
        "frames": len(rows),
        "visible_from_frame": vis[0]["frame"] if vis else None,
        "fully_inside_from_frame": full[0]["frame"] if full else None,
        "glide_advance_px": adv,
        "glide_max_step_px": max(adv) if adv else None,
        "glide_backward_steps": sum(1 for v in adv if v < -0.5),
        "glide_sole_y_range": [min(r["sole_y"] for r in full if r["frame"] < STAND_FROM),
                               max(r["sole_y"] for r in full if r["frame"] < STAND_FROM)] if full else None,
        "stand_sole_y": sorted({r["sole_y"] for r in stand}),
        "stand_cap_y": sorted({r["cap_y"] for r in stand}),
        "stand_foot_x": sorted({r["foot_x"] for r in stand}),
        "stand_body_changed_px_max": max(r.get("body_changed_px", 0) for r in stand) if stand else None,
        "per_frame": rows,
    }
    out = ROOT / "assets/measure_badger.json"
    out.write_text(json.dumps(res, indent=1))
    summary = {k: v for k, v in res.items() if k != "per_frame"}
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
