#!/usr/bin/env python3
"""Misst den Dachs in gerenderten Bildern der Demo (Godot Movie Maker, Basisauflösung 426x240).

    .venv/bin/python styles/sprite-stacking/scripts/measure_badger.py <Temp-Ordner> [weitere Schalter, z. B. --static-cam]

Zwei Läufe mit main.gd --mask (nur der Dachs; R = absolute Schicht, G = Schicht im Modell, B = 0):
  1. --mask-layers=1: nur die Sohlen (Schichten 0-1), so verdeckt kein Bein den anderen Fuß.
  2. ohne Grenze: ganze Figur, für den Kopf (oberste 6 Schichten).
Jedes Pixel wird mit der protokollierten Kameradrehung in Weltkoordinaten zurückgerechnet
(Bodenpunkt = Bildpunkt + Schichthöhe nach unten). Ausgabe: Standfuß-Drift beim Laufen, Lage der Füße
und des Kopfes im Stehen, Sprünge zwischen aufeinanderfolgenden Bildern.
"""
import json, math, pathlib, re, sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from render_frames import render  # noqa: E402

CFG = json.loads((pathlib.Path(__file__).resolve().parent.parent / "demo" / "stacks" / "stacks.json").read_text())
PIVOT = np.array(CFG["layout"]["pivot"])
CENTER = np.array(CFG["layout"]["center"])


def poses(log):
    rows = [l.split() for l in log.splitlines() if l.startswith("MASK ")]
    rows = rows[1:]                       # erste Zeile stammt aus _ready (t = 0, vor dem ersten Bild)
    return [{"t": float(r[2]), "theta": float(r[3]), "state": r[4], "frame": int(r[5]),
             "x": float(r[6]), "y": float(r[7]), "angle": float(r[8])} for r in rows]


def to_world(xs, ys, hs, theta):
    gx, gy = xs + 0.5 - CENTER[0], ys + 0.5 + hs - CENTER[1]
    c, s = math.cos(theta), math.sin(theta)
    return PIVOT[0] + c * gx + s * gy, PIVOT[1] - s * gx + c * gy


def pixels(png):
    a = np.asarray(Image.open(png).convert("RGB")).astype(int)
    m = a[..., 2] == 0
    ys, xs = np.nonzero(m)
    return xs, ys, a[ys, xs, 0], a[ys, xs, 1]


def main():
    tmp = pathlib.Path(sys.argv[1])
    extra = sys.argv[2:]
    feet_png, e1, log1 = render(tmp / "feet", 180, user=["--mask", "--mask-layers=1", *extra])
    full_png, e2, log2 = render(tmp / "full", 180, user=["--mask", *extra])
    if e1 or e2:
        print("Godot-Fehler:", (e1 + e2)[:5])
    P = poses(log1)
    assert len(P) >= len(feet_png), (len(P), len(feet_png))
    rep = {"frames": len(feet_png)}

    feet = []
    for i, png in enumerate(feet_png):
        xs, ys, hs, ls = pixels(png)
        wx, wy = to_world(xs, ys, hs, P[i]["theta"])
        # Füße trennen: quer zur Blickrichtung des Dachses (lokale y-Achse)
        a = P[i]["angle"]
        lat = -(wx - P[i]["x"]) * math.sin(a) + (wy - P[i]["y"]) * math.cos(a)
        f = {}
        for name, sel in (("links", lat < 0), ("rechts", lat >= 0)):
            if sel.sum() >= 2:
                f[name] = (float(wx[sel].mean()), float(wy[sel].mean()), int(sel.sum()))
        feet.append(f)

    # Laufen: je Laufbild (2 Aufnahmebilder) der Fuß, der sich am wenigsten bewegt, ist der Standfuß
    walk = [i for i, p in enumerate(P[:len(feet)]) if p["state"] == "badger_walk"]
    per_anim = {}
    for i in walk:
        per_anim.setdefault(int(round(P[i]["t"] * 15 - 0.5)), i)
    keys = sorted(per_anim)
    drift, stance_runs = [], []
    run = []
    for k0, k1 in zip(keys, keys[1:]):
        a, b = feet[per_anim[k0]], feet[per_anim[k1]]
        moves = {n: math.hypot(b[n][0] - a[n][0], b[n][1] - a[n][1]) for n in ("links", "rechts") if n in a and n in b}
        if not moves:
            continue
        n = min(moves, key=moves.get)
        drift.append(moves[n])
    rep["walk_anim_frames"] = len(keys)
    rep["stance_drift_px"] = {"max": round(max(drift), 2), "mean": round(float(np.mean(drift)), 2),
                              "over_1px": int(sum(d > 1.0 for d in drift)), "n": len(drift)}
    # Standfuß über drei Laufbilder (zwei Übergänge)
    three = []
    for k0, k1, k2 in zip(keys, keys[1:], keys[2:]):
        fs = [feet[per_anim[k]] for k in (k0, k1, k2)]
        for n in ("links", "rechts"):
            if all(n in f for f in fs):
                xs_ = [f[n][0] for f in fs]
                ys_ = [f[n][1] for f in fs]
                three.append(max(max(xs_) - min(xs_), max(ys_) - min(ys_)))
    three.sort()
    rep["stance_over_3_frames_px"] = {"best_foot_per_window_max": None}
    best = []
    for k0, k1, k2 in zip(keys, keys[1:], keys[2:]):
        fs = [feet[per_anim[k]] for k in (k0, k1, k2)]
        cands = []
        for n in ("links", "rechts"):
            if all(n in f for f in fs):
                xs_ = [f[n][0] for f in fs]
                ys_ = [f[n][1] for f in fs]
                cands.append(max(max(xs_) - min(xs_), max(ys_) - min(ys_)))
        if cands:
            best.append(min(cands))
    rep["stance_over_3_frames_px"] = {"max": round(max(best), 2), "median": round(float(np.median(best)), 2),
                                      "over_1px": int(sum(b > 1.0 for b in best)), "n": len(best)}

    # Stehen (nach der Drehung): Füße und Kopf
    stand = [i for i, p in enumerate(P[:len(feet)]) if p["state"] != "badger_walk" and p["t"] > 3.6]
    for n in ("links", "rechts"):
        pts = np.array([feet[i][n][:2] for i in stand if n in feet[i]])
        rep[f"stand_foot_{n}_range_px"] = [round(float(np.ptp(pts[:, 0])), 2), round(float(np.ptp(pts[:, 1])), 2)]
    head = []
    for i, png in enumerate(full_png):
        xs, ys, hs, ls = pixels(png)
        if len(xs) == 0:
            head.append(None)
            continue
        top = ls >= ls.max() - 5
        wx, wy = to_world(xs[top], ys[top], hs[top], P[i]["theta"])
        head.append((float(wx.mean()), float(wy.mean()), int(hs.max()), int(ys.min())))
    jumps = []
    for i in range(1, len(head)):
        if head[i] and head[i - 1] and P[i]["state"] == P[i - 1]["state"] != "badger_walk" and P[i]["t"] > 3.6:
            jumps.append(math.hypot(head[i][0] - head[i - 1][0], head[i][1] - head[i - 1][1]))
    idle = [head[i] for i in stand if head[i] and P[i]["state"] == "badger_idle"]
    rep["head_jump_between_frames_px"] = {"max": round(max(jumps), 2), "median": round(float(np.median(jumps)), 2)}
    rep["idle_head_top_layer"] = sorted({h[2] for h in idle})
    walk_head = [head[i] for i in walk if head[i]]
    rep["walk_head_top_layer"] = sorted({h[2] for h in walk_head})
    # Wechsel Laufen -> Stehen: Füße und Kopf im letzten Lauf- und ersten Stehbild
    sw = next(i for i in range(1, len(P)) if P[i - 1]["state"] == "badger_walk" and P[i]["state"] != "badger_walk")
    a, b = feet[sw - 1], feet[sw]
    rep["walk_to_idle"] = {
        "bild": sw,
        "fuesse_px": {n: [round(b[n][0] - a[n][0], 2), round(b[n][1] - a[n][1], 2)] for n in ("links", "rechts") if n in a and n in b},
        "kopf_px": [round(head[sw][0] - head[sw - 1][0], 2), round(head[sw][1] - head[sw - 1][1], 2)],
    }
    print(json.dumps(rep, indent=1, ensure_ascii=False))
    (tmp / "measure.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
