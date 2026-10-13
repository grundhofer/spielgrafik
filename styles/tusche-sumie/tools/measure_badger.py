#!/usr/bin/env python3
"""Misst die Figur in der Godot-Aufnahme (Prüfmodus: nur Figur vor Magenta).

    .venv/bin/python styles/tusche-sumie/tools/measure_badger.py --tmp <Arbeitsordner>

Prüft:
  - Fußlinie: unterste Figurenzeile in allen 180 Bildern (soll konstant sein).
  - Standfuß beim Laufen: Bei jedem Bildwechsel im Laufzyklus die unterste 5-px-Sohlenzone vergleichen; gesucht
    wird die waagerechte Verschiebung (−4…+4 px) mit der besten Überdeckung (IoU). 0 ±1 px heißt: der Fuß, der
    am Boden steht, bleibt am Boden stehen. An den Fußwechseln (Doppelstand, Ferse setzt auf) ist die IoU
    kleiner, weil der neue Fuß dazukommt; dort zählt, dass die beste Verschiebung trotzdem bei 0 ±1 liegt.
  - Spitze des stehenden Fußes (rechtes Ende der Sohlenzone) über die Bilder mit demselben Standfuß.
  - Kopf: oberste Zeile und waagerechte Lage des oberen Viertels; Sprünge zwischen Bildern.
Schreibt assets/badger_measure.json.
"""
import argparse, json, pathlib, subprocess

import numpy as np
from PIL import Image

from inkutil import ROOT


def mask_of(p):
    a = np.asarray(Image.open(p).convert("RGB"), np.int16)
    mag = (np.abs(a[..., 0] - 255) < 40) & (a[..., 1] < 40) & (np.abs(a[..., 2] - 255) < 40)
    return ~mag


def best_shift(a, b, rng=12):
    best = (-1.0, 0)
    for s in range(-rng, rng + 1):
        bb = np.roll(b, -s, axis=1)
        inter = (a & bb).sum()
        uni = (a | bb).sum()
        iou = inter / uni if uni else 0
        if iou > best[0]:
            best = (float(iou), s)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tmp", required=True)
    a = ap.parse_args()
    tmp = pathlib.Path(a.tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    for f in tmp.glob("m*.png"):
        f.unlink()
    subprocess.run(["godot", "--headless", "--path", str(ROOT / "demo"), "--import"], capture_output=True, timeout=600)
    subprocess.run(["godot", "--path", str(ROOT / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
                    "--write-movie", str(tmp / "m.png"), "--fixed-fps", "30", "--quit-after", "180",
                    "--", "--figure-only"], capture_output=True, text=True, timeout=600)
    pngs = sorted(tmp.glob("m*.png"))
    scene = json.loads((ROOT / "demo/art/scene.json").read_text())
    tl = scene["badger"]["timeline"]
    rows = []
    masks = []
    for i, p in enumerate(pngs[:len(tl)]):
        m = mask_of(p)
        masks.append(m)
        ys, xs = np.where(m)
        if len(ys) == 0:
            rows.append(None)
            continue
        top, bot = int(ys.min()), int(ys.max())
        q = ys < top + (bot - top) * 0.25
        rows.append({"i": i, "name": tl[i][0], "x": tl[i][1], "foot": bot, "top": top,
                     "head_x": round(float(xs[q].mean()), 1)})
    vis = [r for r in rows if r and r["x"] > 60]          # ganz im Bild
    feet = sorted(set(r["foot"] for r in vis))
    slips = []
    for k in range(1, len(rows)):
        r0, r1 = rows[k - 1], rows[k]
        if not r0 or not r1 or r0["name"] == r1["name"] or not r1["name"].startswith("walk") \
                or not r0["name"].startswith("walk") or r1["x"] < 60:
            continue
        fy = r1["foot"]
        a0 = masks[k - 1][fy - 4:fy + 1]
        a1 = masks[k][fy - 4:fy + 1]
        iou, s = best_shift(a0, a1, rng=4)
        slips.append({"frame": k, "from": r0["name"], "to": r1["name"], "shift": s, "iou": round(iou, 3)})
    toes = []
    for r, m in zip(rows, masks):
        if r and r["name"] in ("walk_1", "walk_2", "walk_3", "walk_5", "walk_6", "walk_7") and r["x"] > 60:
            occ = m[r["foot"] - 4:r["foot"] + 1].any(axis=0)
            toes.append([r["i"], r["name"], int(np.where(occ)[0].max())])
    jumps = []
    for k in range(1, len(rows)):
        r0, r1 = rows[k - 1], rows[k]
        # Kopf nur zwischen Lauf- und Stehbildern messen; in den Winkbildern liegt der Arm im oberen Viertel
        if r0 and r1 and r0["x"] > 60 and not r0["name"].startswith("wave") and not r1["name"].startswith("wave"):
            dx = (r1["head_x"] - r0["head_x"]) - (r1["x"] - r0["x"])
            dy = r1["top"] - r0["top"]
            if abs(dy) > 3 or abs(dx) > 6:
                jumps.append({"frame": k, "from": r0["name"], "to": r1["name"], "head_dx_rel": round(dx, 1), "top_dy": dy})
    out = {"frames": len(rows), "foot_lines": feet, "stance_slip": slips, "stance_toe_x": toes, "head_jumps": jumps,
           "max_abs_slip": max((abs(s["shift"]) for s in slips), default=0)}
    (ROOT / "assets/badger_measure.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print("Fußlinien (ganz im Bild):", feet)
    print("Standfuß-Verschiebung je Laufbildwechsel:", [s["shift"] for s in slips])
    print("IoU:", [s["iou"] for s in slips])
    print("Spitze des Standfußes (Bild, Name, x):", toes[:12])
    print("Kopfsprünge (>3 px senkrecht oder >6 px waagerecht gegen den Vorschub):", jumps)


if __name__ == "__main__":
    main()
