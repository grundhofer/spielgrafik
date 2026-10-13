#!/usr/bin/env python3
"""Misst die Figur in der echten Godot-Ausgabe (Prüfmodus --badger-only: nur der Dachs vor Magenta).

    .venv/bin/python styles/skelett-2d/scripts/measure_badger.py [--frames 180] [--t0 0] [--extra "--rigid"]

Drei Läufe: ganze Figur, nur nahes Bein, nur fernes Bein. Gemessen je Bild:
 - Kopf: oberste Zeile der Figur (Mützenspitze) und deren Sprünge von Bild zu Bild,
 - je Bein: unterste Zeile (Sohle), Ferse/Zehe in den drei untersten Zeilen; in Standphasen (Sohle auf dem
   Boden) darf der aufliegende Fuß nicht wandern: Drift der Zehe (bleibt beim Abrollen stehen) und der Ferse
   (bis sie sich hebt) über alle Bilder der Standphase.
Schreibt assets/check/measure_badger.json.
"""
import argparse, json, pathlib, shutil, subprocess, tempfile

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parents[1]
DEMO = HERE / "demo"


def render(td, frames, args):
    out = pathlib.Path(td)
    out.mkdir(parents=True, exist_ok=True)
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
           "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", str(frames), "--",
           "--badger-only"] + args
    r = subprocess.run(cmd, capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    if errs:
        raise SystemExit("\n".join(errs[:10]))
    return sorted(out.glob("f*.png"))


def mask(p):
    a = np.asarray(Image.open(p).convert("RGB")).astype(int)
    mag = (np.abs(a[..., 0] - 255) + a[..., 1] + np.abs(a[..., 2] - 255))
    return mag > 140


def leg_track(pngs):
    """Fuß in festen Zeilen knapp über der Bodenzeile vermessen (unabhängig vom Kantenflimmern der Sohle)."""
    ms = [mask(p) for p in pngs]
    bottoms = [int(np.nonzero(m)[0].max()) if m.any() else -1 for m in ms]
    ground = max(bottoms)
    band = slice(ground - 4, ground - 1)          # drei Zeilen 2–4 px über der Bodenzeile
    rows = []
    for i, m in enumerate(ms):
        ys, xs = np.nonzero(m[band])
        on = bottoms[i] >= ground - 1 and len(xs) > 0
        rows.append({"i": i, "on": on, "heel": int(xs.min()) if len(xs) else None,
                     "toe": int(xs.max()) if len(xs) else None,
                     "w": int(xs.max() - xs.min()) if len(xs) else 0})
    runs, cur = [], []
    for r in rows:
        if r["on"]:
            cur.append(r)
        else:
            if len(cur) >= 2:
                runs.append(cur)
            cur = []
    if len(cur) >= 2:
        runs.append(cur)
    res = []
    for run in runs:
        wmax = max(r["w"] for r in run)
        flat = [r for r in run if r["w"] >= wmax - 2]
        res.append({
            "frames": [run[0]["i"], run[-1]["i"]],
            "toe_drift": int(max(r["toe"] for r in run) - min(r["toe"] for r in run)),
            "heel_drift_flat": int(max(r["heel"] for r in flat) - min(r["heel"] for r in flat)),
            "flat_frames": len(flat),
        })
    return {"ground_row": ground, "band_rows": [ground - 4, ground - 2], "stance_runs": res,
            "max_toe_drift": max(r["toe_drift"] for r in res), "max_heel_drift_flat": max(r["heel_drift_flat"] for r in res)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=180)
    ap.add_argument("--t0", type=float, default=0.0)
    ap.add_argument("--extra", default="")
    ap.add_argument("--out", default=str(HERE / "assets" / "check" / "measure_badger.json"))
    a = ap.parse_args()
    extra = ([f"--t0={a.t0}"] if a.t0 else []) + (a.extra.split() if a.extra else [])
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    result = {"t0": a.t0, "frames": a.frames, "extra": extra}
    with tempfile.TemporaryDirectory() as td:
        full = render(pathlib.Path(td) / "full", a.frames, extra)
        tops, bottoms, xs_r = [], [], []
        for p in full:
            m = mask(p)
            ys, xs = np.nonzero(m)
            tops.append(int(ys.min()))
            bottoms.append(int(ys.max()))
            xs_r.append(int(xs.max()))
        jumps = [abs(tops[i + 1] - tops[i]) for i in range(len(tops) - 1)]
        result["head_top"] = {"min": min(tops), "max": max(tops), "max_jump_per_frame": max(jumps),
                              "series": tops}
        result["figure_height_px"] = [min(b - t for b, t in zip(bottoms, tops)), max(b - t for b, t in zip(bottoms, tops))]
        for leg in ("leg_n", "leg_f"):
            pngs = render(pathlib.Path(td) / leg, a.frames, extra + [f"--only={leg}"])
            result[leg] = leg_track(pngs)
    pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(a.out).write_text(json.dumps(result, indent=1))
    print(json.dumps({k: v for k, v in result.items() if k not in ("head_top",)}, indent=1)[:3000])
    print("Kopf:", {k: v for k, v in result["head_top"].items() if k != "series"})


if __name__ == "__main__":
    main()
