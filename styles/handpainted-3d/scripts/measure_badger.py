#!/usr/bin/env python3
"""Misst den Dachs: Standfuß beim Laufen, Füße im Stehen und Winken, Fuß- und Kopfzeile im Bild.

    .venv/bin/python styles/handpainted-3d/scripts/measure_badger.py [--tmp DIR]

1. Knochenpunkte: Godot-Lauf mit --measure (main.gd gibt je Bild Ferse/Zehe beider Füße und den Kopf in
   Welt- und Bildkoordinaten aus). Laufen: Verschiebung des Standfußes (beide Punkte unter 1 cm) von Bild
   zu Bild in Weltkoordinaten. Stehen/Winken: Spannweite der Fußpunkte. Einmal mit Kamerafahrt (wie in der
   Aufnahme) und einmal mit fester Endeinstellung (--static-cam) für die Bildkoordinaten.
   Anhalten: Überblendung Walk -> Idle (IDLE_T bis IDLE_T + 0,35 s), je Fuß größter Schritt je Bild, Weg am
   Boden (beide Punkte unter 1 cm) und Abstand vom ersten zum letzten Bild.
2. Silhouette: Lauf mit --mask --static-cam (Dachs weiß vor Schwarz), je Bild unterste und oberste weiße
   Zeile; in Steh- und Winkbildern muss die Fußzeile gleich bleiben (±1 px), der Kopf darf nicht springen.
"""
import argparse
import pathlib
import re
import subprocess
import tempfile

import numpy as np
from PIL import Image

SD = pathlib.Path(__file__).resolve().parent.parent
DEMO = SD / "demo"
IDLE_T = 3.3      # wie main.gd
WAVE_T = 3.85


def run(args, out_dir, frames=180):
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
           "--write-movie", str(out_dir / "f.png"), "--fixed-fps", "30", "--quit-after", str(frames), "--"] + args
    r = subprocess.run(cmd, capture_output=True, text=True)
    log = r.stdout + r.stderr
    bad = [l for l in log.splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR", l)]
    if bad:
        raise SystemExit("Godot-Fehler:\n" + "\n".join(bad[:10]))
    return log


def parse(log):
    rows = []
    for line in log.splitlines():
        if not line.startswith("M "):
            continue
        p = line.split()
        r = {"t": float(p[1]), "rot": float(p[3]), "x": float(p[4]), "z": float(p[5])}
        i = 6
        while i < len(p):
            k = p[i]
            r[k] = tuple(float(v) for v in p[i + 1:i + 6])   # wx wy wz sx sy
            i += 6
        rows.append(r)
    return rows


def stance_report(rows, label):
    print(f"--- {label}")
    steps = []
    for a, b in zip(rows, rows[1:]):
        if b["t"] > IDLE_T:
            break
        for side in "LR":
            pts_a = [a[k + side] for k in ("heel.", "toe.")]
            pts_b = [b[k + side] for k in ("heel.", "toe.")]
            if all(p[1] < 0.01 for p in pts_a + pts_b):
                other = "R" if side == "L" else "L"
                if any(b[k + other][1] < 0.01 for k in ("heel.", "toe.")):
                    continue   # Doppelstütze: zählt nicht
                dw = max(np.linalg.norm(np.subtract(pb[:3], pa[:3])) for pa, pb in zip(pts_a, pts_b))
                ds = max(np.hypot(pb[3] - pa[3], pb[4] - pa[4]) for pa, pb in zip(pts_a, pts_b))
                steps.append((b["t"], side, dw * 1000.0, ds))
    if steps:
        w = np.array([s[2] for s in steps])
        s = np.array([s[3] for s in steps])
        print(f"Standfuß beim Laufen ({len(steps)} Bildpaare): Welt max {w.max():.1f} mm, Mittel {w.mean():.1f} mm; "
              f"Bild max {s.max():.2f} px, Mittel {s.mean():.2f} px")
        worst = sorted(steps, key=lambda x: -x[2])[:3]
        print("  größte: " + ", ".join(f"t={t:.2f} {sd} {mm:.1f} mm / {px:.2f} px" for t, sd, mm, px in worst))
    stand = [r for r in rows if r["t"] >= IDLE_T + 0.35]
    for k in ("heel.L", "toe.L", "heel.R", "toe.R"):
        arr = np.array([r[k] for r in stand])
        span_w = np.ptp(arr[:, :3], axis=0).max() * 1000.0
        span_s = np.ptp(arr[:, 3:5], axis=0).max()
        print(f"Stehen/Winken {k:7s}: Spannweite Welt {span_w:.1f} mm, Bild {span_s:.2f} px")


def blend_report(rows):
    win = [r for r in rows if IDLE_T - 0.04 <= r["t"] <= IDLE_T + 0.36]
    for side in "LR":
        mid = [np.mean([r[k + side][:3] for k in ("heel.", "toe.")], axis=0) for r in win]
        low = [max(r[k + side][1] for k in ("heel.", "toe.")) < 0.01 for r in win]
        steps = [np.linalg.norm((b - a)[[0, 2]]) * 1000.0 for a, b in zip(mid, mid[1:])]
        ground = sum(s for s, la, lb in zip(steps, low, low[1:]) if la and lb)
        net = np.linalg.norm((mid[-1] - mid[0])[[0, 2]]) * 1000.0
        print(f"Anhalten Fuß {side}: größter Schritt {max(steps):.1f} mm/Bild, Weg am Boden {ground:.1f} mm, "
              f"Abstand Anfang-Ende {net:.1f} mm, am Boden in {sum(low)}/{len(low)} Bildern")


def mask_report(dirp):
    print("--- Silhouette (Maske, feste Endeinstellung)")
    feet, heads, ts = [], [], []
    for i, f in enumerate(sorted(dirp.glob("f*.png"))):
        a = np.asarray(Image.open(f).convert("L"))
        ys = np.where(a.max(1) > 128)[0]
        if len(ys) == 0:
            continue
        ts.append(i / 30.0)
        feet.append(ys.max())
        heads.append(ys.min())
    ts, feet, heads = map(np.array, (ts, feet, heads))
    st = ts >= IDLE_T + 0.35
    print(f"Fußzeile Stehen/Winken: {feet[st].min()}–{feet[st].max()} (Spannweite {np.ptp(feet[st])} px)")
    jumps = np.abs(np.diff(heads[st]))
    print(f"Kopfzeile Stehen/Winken: {heads[st].min()}–{heads[st].max()}, größter Sprung je Bild {jumps.max()} px")
    print(f"Figurenhöhe im Stehen: {np.median(feet[st] - heads[st]):.0f} px")
    wk = ts < IDLE_T
    print(f"Fußzeile beim Laufen: {feet[wk].min()}–{feet[wk].max()} (nah/fern abwechselnd)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tmp", default=None)
    a = ap.parse_args()
    base = pathlib.Path(a.tmp or tempfile.mkdtemp(prefix="hp3d_measure_"))
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    rows = parse(run(["--measure"], base / "moving"))
    stance_report(rows, "mit Kamerafahrt (wie Aufnahme)")
    blend_report(rows)
    rows_s = parse(run(["--measure", "--static-cam"], base / "static"))
    stance_report(rows_s, "feste Endeinstellung")
    run(["--mask", "--static-cam"], base / "mask")
    mask_report(base / "mask")
    print("Temp:", base)


if __name__ == "__main__":
    main()
