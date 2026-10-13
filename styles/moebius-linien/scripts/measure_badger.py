#!/usr/bin/env python3
"""Misst den animierten Dachs (PIPELINE.md → Figuren und Animation) auf zwei Wegen:

1. Knochenpunkte (main.gd --measure): Ferse und Zehe beider Füße und Kopf je Bild in Welt- und
   Bildkoordinaten. Geprüft wird, wie weit der Standfuß (Punkt unter 1 cm Höhe) von Bild zu Bild
   wandert, getrennt nach Totale (Schnitt bei 2,7 s) und Nahaufnahme, und wie ruhig Füße und Kopf
   im Stehen und Winken bleiben.
2. Gerenderte Silhouette (main.gd --mask: nur der Dachs, weiß auf Schwarz): unterste und oberste
   Zeile der Figur je Bild; im Stehen muss die Fußzeile gleich bleiben, der Kopf darf nicht springen.

    .venv/bin/python styles/moebius-linien/scripts/measure_badger.py --out <tmp>

Schreibt <out>/measure.json und gibt eine Zusammenfassung aus. Die Bilder bleiben im Temp-Ordner.
"""
import argparse, json, pathlib, re, subprocess, sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
DEMO = HERE.parent / "demo"
CUT_T = 2.7
IDLE_T = 3.6    # Überblendung Walk -> Idle 3,6–3,9 s (main.gd)
STAND_T = 4.1   # ab hier steht er (Idle, Wave, Idle)


def run(out, args, tag):
    fdir = out / tag
    fdir.mkdir(parents=True, exist_ok=True)
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
           "--write-movie", str(fdir / "f.png"), "--fixed-fps", "30", "--quit-after", "180", "--"] + args
    r = subprocess.run(cmd, capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if re.search(r"ERROR", l)]
    if errs:
        print("Godot-Fehler:", errs[:3])
    return r.stdout, fdir


def parse(stdout):
    rows = []
    for line in stdout.splitlines():
        if not line.startswith("M "):
            continue
        p = line.split()
        d = {"t": float(p[1]), "shot": int(p[3]), "rot": float(p[5])}
        i = 9
        while i < len(p):
            name = p[i]
            d[name] = [float(v) for v in p[i + 1:i + 6]]   # x y z sx sy
            i += 6
        rows.append(d)
    return rows


def stance_steps(rows, flat=False):
    """Wanderung des Standfußes je Bild: Punkte unter 1 cm in beiden Bildern. flat=True: nur Füße,
    bei denen Ferse und Zehe am Boden sind (Fußmitte); sonst jeder Punkt einzeln (auch Abrollen)."""
    out = []
    for a, b in zip(rows, rows[1:]):
        if a["shot"] != b["shot"]:
            continue
        if flat:
            for side in ("L", "R"):
                h, o = "heel." + side, "toe." + side
                if max(a[h][1], a[o][1], b[h][1], b[o][1]) < 0.01:
                    pa = (np.array(a[h]) + np.array(a[o])) / 2
                    pb = (np.array(b[h]) + np.array(b[o])) / 2
                    out.append({"t": b["t"], "shot": b["shot"], "point": "mid." + side,
                                "mm": 1000 * np.linalg.norm(pb[:3] - pa[:3]), "px": float(np.hypot(*(pb[3:5] - pa[3:5])))})
            continue
        for k in ("heel.L", "toe.L", "heel.R", "toe.R"):
            if a[k][1] < 0.01 and b[k][1] < 0.01:
                dw = np.linalg.norm(np.array(b[k][:3]) - np.array(a[k][:3]))
                ds = np.hypot(b[k][3] - a[k][3], b[k][4] - a[k][4])
                out.append({"t": b["t"], "shot": b["shot"], "point": k, "mm": 1000 * dw, "px": ds})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)

    stdout, _ = run(out, ["--measure", "--no-ui"], "measure")
    rows = parse(stdout)
    if len(rows) < 170:
        sys.exit(f"nur {len(rows)} Messzeilen")
    steps = stance_steps(rows)
    res = {"frames": len(rows)}
    flat = stance_steps(rows, flat=True)
    for label, src in (("walk", steps), ("walk_flat", flat)):
        for shot, (t0, t1) in {1: (0.0, CUT_T), 2: (CUT_T, IDLE_T)}.items():
            s = [x for x in src if x["shot"] == shot and t0 < x["t"] <= t1]
            if s:
                worst = max(s, key=lambda x: x["mm"])
                res[f"{label}_shot{shot}"] = {"steps": len(s), "max_mm": round(worst["mm"], 2),
                                              "max_px": round(max(x["px"] for x in s), 2),
                                              "mean_px": round(float(np.mean([x["px"] for x in s])), 3),
                                              "worst_t": round(worst["t"], 3), "worst_point": worst["point"]}
    blend = [x for x in steps if IDLE_T < x["t"] < STAND_T]
    if blend:
        res["blend_walk_idle"] = {"max_mm": round(max(x["mm"] for x in blend), 2),
                                 "max_px": round(max(x["px"] for x in blend), 2)}
    stand = [r for r in rows if r["t"] >= STAND_T]
    feet = np.array([[r[k][3:5] for k in ("heel.L", "toe.L", "heel.R", "toe.R")] for r in stand])
    head = np.array([r["head"][3:5] for r in stand])
    res["stand"] = {"frames": len(stand),
                    "feet_range_px": round(float((feet.max(axis=0) - feet.min(axis=0)).max()), 2),
                    "feet_y_max_px": round(float(feet[:, :, 1].max()), 2),
                    "head_step_max_px": round(float(np.abs(np.diff(head, axis=0)).max()), 2)}

    # Silhouette aus dem Maskenlauf
    _, mdir = run(out, ["--mask"], "mask")
    pngs = sorted(mdir.glob("f*.png"))
    sil = []
    for i, p in enumerate(pngs):
        m = np.asarray(Image.open(p).convert("L")) > 128
        ys = np.where(m.any(axis=1))[0]
        if len(ys) == 0:
            continue
        sil.append({"i": i, "t": (i + 1) / 30.0, "top": int(ys[0]), "bottom": int(ys[-1]),
                    "height": int(ys[-1] - ys[0] + 1)})
    st = [s for s in sil if s["t"] >= STAND_T]
    tops = [s["top"] for s in st]
    res["mask_stand"] = {"frames": len(st), "foot_rows": sorted({s["bottom"] for s in st}),
                         "top_min": min(tops), "top_max": max(tops),
                         "top_step_max": int(np.abs(np.diff(tops)).max()) if len(tops) > 1 else 0}
    s1 = [s for s in sil if s["t"] < CUT_T]
    s2 = [s for s in sil if CUT_T + 0.05 < s["t"] < 3.65]
    res["mask_walk_height_px"] = {"shot1": [min(s["height"] for s in s1), max(s["height"] for s in s1)],
                                  "shot2": [min(s["height"] for s in s2), max(s["height"] for s in s2)]}
    res["mask_stand_height_px"] = [min(s["height"] for s in st), max(s["height"] for s in st)]
    (out / "measure.json").write_text(json.dumps({"summary": res, "silhouette": sil}, indent=1))
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
