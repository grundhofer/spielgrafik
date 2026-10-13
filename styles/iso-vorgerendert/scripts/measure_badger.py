#!/usr/bin/env python3
"""Fuß- und Kopfmessung des Dachses in der gerenderten Godot-Aufnahme (iso-vorgerendert).

  .venv/bin/python styles/iso-vorgerendert/scripts/measure_badger.py --raw <renderordner> --tmp <tempordner>

Zwei Läufe mit --write-movie (180 Bilder): A mit Figur (ohne Verdeckung, Schatten, Ring, Leiste), B ohne Figur.
Die Differenz ist die Figurmaske je Aufnahmebild. Gemessen werden
  - Kopfoberkante und Fußzeile (unterste Maskenzeile) je Bild, getrennt nach Phase (Laufen, Stehen, Winken),
  - der Standfuß: Blender liefert je Laufbild die Sohlenlage beider Füße (badger.json); für jeden Fuß, der in
    aufeinanderfolgenden Laufbildern aufsteht, wird im Bild der Schwerpunkt der Maskenpixel in einem 7×4-Fenster
    über der vorhergesagten Sohle verglichen (Verschiebung in px), auch über Zyklusgrenzen und beim Halt.
Schreibt assets/probe/feet.json.
"""
import argparse
import json
import pathlib
import subprocess

import numpy as np
from PIL import Image

STYLE = pathlib.Path(__file__).resolve().parent.parent
DEMO = STYLE / "demo"


def run(tmp, tag, extra):
    d = tmp / tag
    d.mkdir(parents=True, exist_ok=True)
    for p in d.glob("*.png"):
        p.unlink()
    subprocess.run(["godot", "--path", str(DEMO), "--position", "20000,20000", "--write-movie", str(d / "f.png"),
                    "--fixed-fps", "30", "--quit-after", "180", "--"] + extra, capture_output=True, check=True)
    return sorted(d.glob("f*.png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--tmp", required=True)
    a = ap.parse_args()
    tmp = pathlib.Path(a.tmp)
    fa = run(tmp, "A", ["--noocc", "--noshadow", "--noring", "--noui"])
    fb = run(tmp, "B", ["--nobadger", "--noui"])
    n = min(len(fa), len(fb))
    bake = json.load(open(DEMO / "data" / "bake.json"))
    vr = bake["scene"]["map"]["view_row"]
    masks = []
    for i in range(n):
        A = np.asarray(Image.open(fa[i]).convert("RGB"), np.int16)
        B = np.asarray(Image.open(fb[i]).convert("RGB"), np.int16)
        masks.append(np.abs(A - B).sum(-1) > 0)
    rows = []
    for i, m in enumerate(masks):
        ys, xs = np.nonzero(m)
        rows.append({"frame": i, "px": int(m.sum()), "top": int(ys.min()) if len(ys) else None,
                     "bottom": int(ys.max()) if len(ys) else None,
                     "left": int(xs.min()) if len(xs) else None, "right": int(xs.max()) if len(xs) else None})

    # Vorhergesagte Sohlen aus Blender (Weltpunkt relativ zum Anker) -> Kartenpixel
    raw = json.load(open(pathlib.Path(a.raw) / "badger" / "badger.json"))
    R = np.array(bake["R"])
    U = np.array(bake["U"])
    s = bake["px_per_m"]
    walk = {f["name"]: f for f in raw["frames"] if f["anim"] == "Walk"}
    # Lage des Ankers je Aufnahmebild aus main.gd nachrechnen
    import math
    cam_o = np.array(bake["cam_location"])
    W, H = bake["map_size"]
    p0 = bake["scene"]["badger_path"]["start"]
    pw = np.array([p0[0], -p0[2], p0[1]])
    q = pw - cam_o
    start = np.array([round(q @ R * s + W / 2), round(-(q @ U) * s + H / 2)])
    cyc = np.round(np.array(bake["badger"]["cycle_px"]["SE"])).astype(int)
    zmax = 0.008 * raw["scale"]
    stance = []
    prev = None
    for i in range(min(n, 112)):
        if i % 2:
            continue
        j = i // 2
        nm = "walk_SE_%d" % (j % 8)
        org = start + cyc * (j // 8)
        feet = walk[nm]["feet"]
        rec = {"frame": i, "sprite": nm}
        for side, (fx, fy, fz) in feet.items():
            fpx = org + np.array([np.dot([fx, fy, fz], R) * s, -np.dot([fx, fy, fz], U) * s])
            fpx_view = fpx - np.array([0, vr])
            planted = fz < zmax
            x0, y0 = int(round(fpx_view[0])), int(round(fpx_view[1]))
            win = masks[i][max(0, y0 - 3):y0 + 1, max(0, x0 - 3):x0 + 4]
            yy, xx = np.nonzero(win)
            cen = [float(xx.mean() + max(0, x0 - 3)), float(yy.mean() + max(0, y0 - 3))] if len(yy) else None
            rec[side] = {"pred": [round(float(fpx_view[0]), 2), round(float(fpx_view[1]), 2)], "planted": bool(planted),
                         "centroid": cen}
        stance.append(rec)
    drift = []
    for r0, r1 in zip(stance, stance[1:]):
        for side in ("L", "R"):
            if side in r0 and side in r1 and r0[side]["planted"] and r1[side]["planted"]:
                p_a, p_b = np.array(r0[side]["pred"]), np.array(r1[side]["pred"])
                c_a, c_b = r0[side]["centroid"], r1[side]["centroid"]
                d_img = None if c_a is None or c_b is None else (np.array(c_b) - np.array(c_a)).round(2).tolist()
                drift.append({"from": r0["frame"], "to": r1["frame"], "foot": side,
                              "pred_shift_px": (p_b - p_a).round(2).tolist(), "img_shift_px": d_img})
    # Halt: letztes Laufbild -> Stehbild
    halt = {}
    if n > 113:
        a_, b_ = masks[110], masks[112]
        lowa = np.nonzero(a_)[0].max()
        lowb = np.nonzero(b_)[0].max()
        best = None
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                sa = np.roll(np.roll(a_, dy, 0), dx, 1)
                win = slice(lowb - 5, lowb + 1)
                inter = (sa[win] & b_[win]).sum()
                uni = (sa[win] | b_[win]).sum()
                iou = inter / max(uni, 1)
                if best is None or iou > best[0]:
                    best = (float(iou), dx, dy)
        halt = {"bottom_walk_last": int(lowa), "bottom_stand": int(lowb),
                "best_shift_feet_window": {"iou": round(best[0], 3), "dx": best[1], "dy": best[2]}}

    def phase(i):
        return "walk" if i < 112 else "stand" if i < 122 else "idle" if i < 132 else "wave" if i < 177 else "idle"
    summary = {}
    for r in rows:
        ph = phase(r["frame"])
        if ph == "walk" or r["bottom"] is None:
            continue
        summary.setdefault(ph, {"bottom": set(), "top": set()})
        summary[ph]["bottom"].add(r["bottom"])
        summary[ph]["top"].add(r["top"])
    summary = {k: {kk: sorted(vv) for kk, vv in v.items()} for k, v in summary.items()}
    # Stand im engen Sinn: Blender sagt keine Bewegung der Sohle voraus (< 0,3 px); Aufsetzen und Abrollen
    # (Sohle berührt den Boden, rollt aber noch) sind Übergänge der Animation und werden getrennt gezählt
    stance_pairs = [d for d in drift if max(abs(x) for x in d["pred_shift_px"]) < 0.3]
    planted_img = [d["img_shift_px"] for d in stance_pairs if d["img_shift_px"] is not None]
    maxdev = max((max(abs(x) for x in v) for v in planted_img), default=None)
    out = {"stance_pairs": len(stance_pairs), "frames": rows, "stance": stance, "planted_shifts": drift, "halt": halt, "still_lines": summary,
           "max_planted_shift_img_px": maxdev,
           "max_planted_shift_pred_px": max((max(abs(x) for x in d["pred_shift_px"]) for d in stance_pairs), default=None),
           "contact_transitions_pred_px": sorted({tuple(d["pred_shift_px"]) for d in drift if d not in stance_pairs})}
    (STYLE / "assets" / "probe").mkdir(parents=True, exist_ok=True)
    json.dump(out, open(STYLE / "assets" / "probe" / "feet.json", "w"), indent=1)
    print(json.dumps({"stance_pairs": len(stance_pairs), "max_planted_shift_img_px": out["max_planted_shift_img_px"],
                      "max_planted_shift_pred_px": out["max_planted_shift_pred_px"], "n_pairs": len(drift),
                      "halt": halt, "still_lines": summary}, indent=1))


if __name__ == "__main__":
    main()
