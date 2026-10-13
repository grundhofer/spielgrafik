#!/usr/bin/env python3
"""Füße und Kopf des Dachses messen (PIPELINE.md → Figuren und Animation).

Zwei Läufe der Demo mit --write-movie und 30 fps:
  1. -- --measure: main.gd druckt je Bild Ferse/Zehe beider Füße und den Kopf (Welt und Bild).
     Ausgewertet: Bewegung des Standfußes (Punkte < 1 cm über dem Boden) von Bild zu Bild, in Metern
     und in Pixeln (Pixel nur aussagekräftig, solange die Kamera steht: Totale bis 2,0 s,
     Nahaufnahme ab 3,9 s); im Stehen und Winken die Spanne aller Fußpunkte.
  2. -- --mask: nur der Dachs, weiß auf Schwarz. Ausgewertet in der festen Nahaufnahme (ab 3,9 s):
     unterste weiße Zeile (Fußzeile) und oberste weiße Zeile über dem Kopf (±30 px um den
     gemessenen Kopfpunkt, damit die Winkhand nicht zählt) je Bild, größte Sprünge.

    .venv/bin/python styles/lowpoly-flat/scripts/measure_badger.py [--keep DIR]
"""
import argparse, json, pathlib, re, subprocess, tempfile

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo"
FPS = 30
N = 180
CAM_STATIC = [(0.0, 2.0), (3.9, 6.0)]   # Totale, Nahaufnahme


def run(td, user):
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    r = subprocess.run(["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
                        "--write-movie", str(pathlib.Path(td) / "f.png"), "--fixed-fps", str(FPS),
                        "--quit-after", str(N), "--", *user], capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR", l)]
    return r.stdout, errs


def parse(out):
    rows = []
    for l in out.splitlines():
        if not l.startswith("M "):
            continue
        p = l.split()
        d = {"t": float(p[1]), "rot": float(p[3]), "x": float(p[4]), "z": float(p[5])}
        i = 6
        while i < len(p):
            d[p[i]] = [float(v) for v in p[i + 1:i + 6]]
            i += 6
        rows.append(d)
    return rows


def static(t):
    return any(a <= t < b for a, b in CAM_STATIC)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", help="Ordner für die Maskenbilder (sonst Temp)")
    a = ap.parse_args()
    res = {}
    with tempfile.TemporaryDirectory() as td:
        out, errs = run(td, ["--measure"])
        rows = parse(out)
    res["godot_errors"] = errs[:5]
    res["frames_measured"] = len(rows)
    floor = 0.012

    # 1. Standfuß im Lauf (Phase 0 bis zum Umschalten auf Idle, 3,57 s)
    walk_m, walk_px, stand = [], [], {k: [] for k in ("heel.L", "toe.L", "heel.R", "toe.R")}
    for r0, r1 in zip(rows, rows[1:]):
        if r1["t"] > 3.57:
            break
        for side in "LR":
            pts = [k + "." + side for k in ("heel", "toe")]
            if all(r0[k][1] - floor < 0.01 and r1[k][1] - floor < 0.01 for k in pts):
                for k in pts:
                    walk_m.append(float(np.hypot(r1[k][0] - r0[k][0], r1[k][2] - r0[k][2])))
                    if static(r0["t"]) and static(r1["t"]):
                        walk_px.append(float(np.hypot(r1[k][3] - r0[k][3], r1[k][4] - r0[k][4])))
    # Überblendung Walk -> Idle (3,57–3,95 s): Bodenpunkte beider Füße
    blend = []
    for r0, r1 in zip(rows, rows[1:]):
        if 3.57 <= r0["t"] and r1["t"] <= 3.95:
            for k in stand:
                if r0[k][1] - floor < 0.01 and r1[k][1] - floor < 0.01:
                    blend.append(float(np.hypot(r1[k][0] - r0[k][0], r1[k][2] - r0[k][2])))
    res["blend_ground_points_max_mm_per_frame"] = round(1000 * max(blend), 2) if blend else None
    for r in rows:
        if r["t"] >= 3.9:   # Idle und Wave in der Nahaufnahme
            for k in stand:
                stand[k].append(r[k])
    res["walk_stance_foot_max_mm_per_frame"] = round(1000 * max(walk_m), 2) if walk_m else None
    res["walk_stance_foot_p95_mm_per_frame"] = round(1000 * float(np.percentile(walk_m, 95)), 2) if walk_m else None
    res["walk_stance_foot_max_px_per_frame_static_cam"] = round(max(walk_px), 2) if walk_px else None
    spans = {}
    for k, v in stand.items():
        v = np.array(v)
        spans[k] = {"world_mm": round(1000 * float(np.ptp(v[:, 0:3], axis=0).max()), 2),
                    "px": round(float(np.ptp(v[:, 3:5], axis=0).max()), 2)}
    res["idle_wave_foot_span_from_3.9s"] = spans
    end = rows[-1]
    res["end_position"] = [round(end["x"], 3), round(end["z"], 3)]
    res["end_rotation_deg"] = round(end["rot"], 1)

    # 2. Silhouetten der Nahaufnahme
    head_x = {int(round(r["t"] * FPS)) - 1: r["head"][3] for r in rows}
    keep = pathlib.Path(a.keep) if a.keep else None
    with tempfile.TemporaryDirectory() as td:
        out, errs = run(td, ["--mask"])
        res["godot_errors_mask"] = errs[:5]
        feet, heads, ts = [], [], []
        for i in range(int(3.9 * FPS), N):
            p = pathlib.Path(td) / f"f{i:08d}.png"
            if not p.exists():
                continue
            m = np.asarray(Image.open(p).convert("L")) > 128
            rows_on = np.where(m.any(axis=1))[0]
            if rows_on.size == 0:
                continue
            feet.append(int(rows_on.max()))
            # Kopf: oberste weiße Zeile in ±30 px um den gemessenen Kopfpunkt (ohne Winkhand)
            hx = int(round(head_x.get(i, m.shape[1] / 2)))
            cols = m[:, max(0, hx - 30):hx + 30]
            heads.append(int(np.where(cols.any(axis=1))[0].min()))
            ts.append(i / FPS)
            if keep and i in (int(3.9 * FPS), 150, N - 1):
                keep.mkdir(parents=True, exist_ok=True)
                Image.open(p).save(keep / f"mask_{i:03d}.png")
    feet, heads = np.array(feet), np.array(heads)
    res["closeup_foot_row_min_max"] = [int(feet.min()), int(feet.max())]
    res["closeup_head_row_min_max"] = [int(heads.min()), int(heads.max())]
    res["closeup_head_max_jump_px"] = int(np.abs(np.diff(heads)).max())
    res["closeup_foot_max_jump_px"] = int(np.abs(np.diff(feet)).max())
    res["closeup_badger_height_px"] = int(np.median(feet - heads))
    print(json.dumps(res, indent=1, ensure_ascii=False))
    (ROOT / "assets" / "measure_badger.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
