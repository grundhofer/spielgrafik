#!/usr/bin/env python3
"""Prüft die Figur im gerenderten Godot-Bild: Standfuß, Fußzeile, Kopf, ruhige Körperpixel beim Sprechen.

    godot --path styles/zeichentrick-cel/demo --position 20000,20000 --write-movie <tmp>/f.png --fixed-fps 30 \
          --quit-after 180 -- --probe-badger
    .venv/bin/python styles/zeichentrick-cel/scripts/measure_feet.py <tmp>

Der Prüfschalter --probe-badger blendet alles außer dem Dachs aus (Magenta-Hintergrund). Gemessen wird jede
Zeichnung (jedes zweite Videobild, die Figur läuft auf Zweien):
  - Fußzeile (unterste deckende Zeile) in allen Bildern,
  - beim Laufen je Zeichnungspaar der Drehpunkt des Standfußes in Bildschirmkoordinaten (Regel wie in
    measure_walk.py: flach -> beste Verschiebung, Aufsetzen -> Ferse, Abdrücken -> Zehe); Sollwert 0 px,
  - je Standphase (Aufsetzen der Ferse bis Abdrücken der Zehe, wie in measure_walk.py) die Lage von Ferse und
    Zehe in Bildschirmkoordinaten; Spanne = größte minus kleinste Lage (Soll höchstens 1 px),
  - in den Vorderbildern (Stehen, Sprechen, Blinzeln) die Zahl geänderter Pixel außerhalb des Gesichts.
Ergebnis: assets/measure_feet.json
"""
import json, pathlib, sys

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from measure_walk import spans, best_shift  # noqa: E402


def load(p):
    a = np.array(Image.open(p).convert("RGB")).astype(np.int16)
    d = np.abs(a - np.array([255, 0, 255])).sum(-1)
    return a, d > 90


def main():
    tmp = pathlib.Path(sys.argv[1])
    files = sorted(tmp.glob("f*.png"))
    draws = []
    for i in range(0, len(files), 2):
        a, m = load(files[i])
        ys, xs = np.where(m)
        if len(ys) == 0:
            draws.append(None)
            continue
        bot = ys.max()
        c = m[bot - 2:bot + 1].any(0)
        top = ys.min()
        hq = m[top:top + (bot - top) // 4]
        hx = np.where(hq.any(0))[0]
        draws.append({"frame": i, "bottom": int(bot), "top": int(top), "spans": spans(c), "contact": c,
                      "head_x": float((hx.min() + hx.max()) / 2), "rgb": a, "mask": m})
    res = {"drawings": [], "pairs": [], "front": {}}
    for d in draws:
        if d:
            res["drawings"].append({k: d[k] for k in ("frame", "bottom", "top", "spans", "head_x")})
    # Laufpaare: die Figur ist ganz im Bild und beide Zeichnungen haben Kontakt
    walk_ticks = 39
    resid = []
    for k in range(walk_ticks - 1):
        d0, d1 = draws[k], draws[k + 1]
        if not d0 or not d1:
            continue
        xs0 = np.where(d0["mask"].any(0))[0]
        if xs0.min() <= 0:  # Figur noch am Bildrand angeschnitten
            continue
        c0, c1 = d0["contact"], d1["contact"]
        s0, s1 = d0["spans"], d1["spans"]
        iou, dx = best_shift(c0, c1, range(-8, 9))
        if iou >= 0.9:
            r, how = dx, "flach"
        elif len(s0) == 2 and len(s1) == 1:
            r, how = s0[1][0] - s1[0][0], "Ferse"
        elif len(s1) == 2:
            r, how = s0[-1][1] - s1[0][1], "Zehe"
        else:
            r, how = s0[-1][1] - s1[-1][1], "Zehe (Ferse hebt ab)"
        resid.append(r)
        res["pairs"].append({"tick": k, "residual_px": int(r), "rule": how, "iou": round(float(iou), 2)})
    # Standphasen: Ferse und Zehe des Standfußes in Bildschirmkoordinaten
    seq = [(k, draws[k]) for k in range(walk_ticks) if draws[k] and np.where(draws[k]["mask"].any(0))[0].min() > 0]
    longest = max(sp[1] - sp[0] + 1 for _, d in seq for sp in d["spans"])
    starts = [i for i, (k, d) in enumerate(seq) if len(d["spans"]) == 2]
    res["stance"] = []
    for a, b in zip(starts, starts[1:]):
        heel = [seq[a][1]["spans"][1][0]]
        toe = []
        for k, d in seq[a + 1:b]:
            sp = d["spans"][0]
            if sp[1] - sp[0] + 1 >= 0.85 * longest:
                heel.append(sp[0])
            toe.append(sp[1])
        toe.append(seq[b][1]["spans"][0][1])
        res["stance"].append({"ticks": [seq[a][0], seq[b][0]], "heel": [int(v) for v in heel],
                              "toe": [int(v) for v in toe], "heel_span_px": int(max(heel) - min(heel)),
                              "toe_span_px": int(max(toe) - min(toe))})
    res["stance_max_span_px"] = max(max(p["heel_span_px"], p["toe_span_px"]) for p in res["stance"])
    full = [d for d in draws if d and np.where(d["mask"].any(0))[0].min() > 0]  # ganz im Bild
    bottoms = sorted({d["bottom"] for d in full})
    res["bottoms"] = bottoms
    res["residual_max_abs"] = int(max(abs(r) for r in resid)) if resid else None
    res["residual_hist"] = {str(v): resid.count(v) for v in sorted(set(resid))}
    # Vorderbilder: Pixel außerhalb des Gesichts vergleichen (ab Tick 45, nach dem Federn)
    fronts = [d for k, d in enumerate(draws) if d and k >= 45]
    ref = fronts[0]
    face = np.zeros_like(ref["mask"])
    ys, xs = np.where(ref["mask"])
    # Gesicht: Kopfbereich zwischen 22 % und 40 % der Figurhöhe, mittlere Breite
    h = ys.max() - ys.min()
    y0, y1 = ys.min() + int(0.14 * h), ys.min() + int(0.36 * h)
    face[y0:y1, xs.min() + 30:xs.max() - 30] = True
    diffs = []
    for d in fronts[1:]:
        ch = (np.abs(d["rgb"] - ref["rgb"]).sum(-1) > 24) & (d["mask"] | ref["mask"])
        diffs.append(int((ch & ~face).sum()))
    res["front"] = {"face_box": [int(xs.min() + 30), int(y0), int(xs.max() - 30), int(y1)],
                    "changed_outside_face_max": max(diffs) if diffs else 0, "drawings": len(fronts)}
    (ROOT / "assets/measure_feet.json").write_text(json.dumps(res, indent=1))
    print("Fußzeilen (unterste Zeile):", bottoms)
    print("Laufpaare:", len(resid), "Rest des Standfußes je Paar:", res["residual_hist"], "max", res["residual_max_abs"])
    for p in res["pairs"]:
        if abs(p["residual_px"]) > 1:
            print("  Tick", p["tick"], p)
    for p in res["stance"]:
        print("Standphase Ticks %d–%d: Ferse %s (Spanne %d px), Zehe %s (Spanne %d px)" % (
            p["ticks"][0], p["ticks"][1], p["heel"], p["heel_span_px"], p["toe"], p["toe_span_px"]))
    print("größte Spanne in einer Standphase:", res["stance_max_span_px"], "px")
    print("Vorderbilder:", res["front"])


if __name__ == "__main__":
    main()
