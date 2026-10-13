#!/usr/bin/env python3
"""Misst die prozedural bewegte Figur in der Godot-Ausgabe (PIPELINE.md -> Figuren und Animation).

    .venv/bin/python -I styles/prozedurale-animation/scripts/measure_badger.py [--seconds 6] [--t0 0] [--keep]

Drei Läufe vor Magenta (--only=near_leg, --only=far_leg, --only=body) mit Zustandsprotokoll (--log):
- Standfuß: in jeder Standphase (laut Protokoll) Spanne von Ferse, Zehe und Sohlenzeile in Bildpixeln.
- Stand: Sohlenzeile beider Füße in allen Bildern nach dem Anhalten.
- Kopf: Mützenoberkante und Schnauzenspitze je Bild, größter Sprung von Bild zu Bild und größte
  zweite Differenz (Ruck), damit kein Zittern oder Springen durchrutscht.
- Ketten (aus dem Protokoll): Schalwinkel (Wurzel -> Spitze gegen die Senkrechte, + = nach vorn) beim Gehen und
  größter Ausschlag nach vorn nach dem Halt; Taschenweg relativ zur Hüfte nach dem Halt.
Figur gilt als „Pixel der Figur“, wenn die Summe |R-255| + |G| + |B-255| > 90 ist (Abstand zu Magenta).
Schreibt assets/check/measure.json. Temporäre Bilder in einem eigenen Temp-Ordner (danach gelöscht).
"""
import argparse, json, math, pathlib, shutil, subprocess, sys, tempfile

import numpy as np
from PIL import Image

SD = pathlib.Path(__file__).resolve().parents[1]
DEMO = SD / "demo"


def run(only, frames, t0, td):
    out = td / only
    out.mkdir()
    log = out / "state.jsonl"
    r = subprocess.run(["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
                        "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", str(frames),
                        "--", f"--only={only}", f"--log={log}", f"--t0={t0}"], capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    pngs = sorted(out.glob("f*.png"))
    states = [json.loads(l) for l in log.read_text().splitlines() if l.strip()]
    return pngs, states, errs


def mask_of(p):
    a = np.asarray(Image.open(p).convert("RGB")).astype(int)
    d = np.abs(a - np.array([255, 0, 255])).sum(-1)
    return d > 90


def foot_rows(m, band=4):
    ys = np.nonzero(m.any(1))[0]
    if len(ys) == 0:
        return None
    yb = int(ys.max())
    sub = m[yb - band:yb + 1]
    xs = np.nonzero(sub.any(0))[0]
    return {"bottom": yb, "heel": int(xs.min()), "toe": int(xs.max())}


def runs(flags):
    out, cur = [], []
    for i, f in enumerate(flags):
        if f:
            cur.append(i)
        elif cur:
            out.append(cur); cur = []
    if cur:
        out.append(cur)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=6.0)
    ap.add_argument("--t0", type=float, default=0.0)
    a = ap.parse_args()
    frames = int(round(a.seconds * 30))
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    res = {"t0": a.t0, "frames": frames}
    with tempfile.TemporaryDirectory(prefix="pa-measure-") as tds:
        td = pathlib.Path(tds)
        for leg, idx in [("near_leg", 1), ("far_leg", 0)]:
            pngs, st, errs = run(leg, frames, a.t0, td)
            n = min(len(pngs), len(st))
            fr = [foot_rows(mask_of(pngs[i])) for i in range(n)]
            stance = [not st[i]["feet"][idx]["swing"] for i in range(n)]
            worst = {"heel": 0, "toe": 0, "bottom": 0}
            phases = []
            for r in runs(stance):
                if len(r) < 2:
                    continue
                spans = {k: max(fr[i][k] for i in r) - min(fr[i][k] for i in r) for k in worst}
                phases.append({"frames": [r[0], r[-1]], **spans})
                for k in worst:
                    worst[k] = max(worst[k], spans[k])
            # Stand: ab dem Bild, in dem der letzte Schritt gelandet ist und kein Fuß mehr schwingt
            last = st[n - 1]["steps"]
            idle = [i for i in range(n) if st[i]["steps"] == last and not any(f["swing"] for f in st[i]["feet"])]
            idle_rows = sorted({fr[i]["bottom"] for i in idle}) if idle else []
            res[leg] = {"stance_phases": len(phases), "max_span_px": worst, "phases": phases,
                        "idle_bottom_rows": idle_rows, "godot_errors": errs[:5]}
        pngs, st, errs = run("body", frames, a.t0, td)
        n = min(len(pngs), len(st))
        top, nose = [], []
        for i in range(n):
            m = mask_of(pngs[i])
            ys = np.nonzero(m.any(1))[0]
            top.append(int(ys.min()))
            nose.append(int(np.nonzero(m.any(0))[0].max()))
        top, nose = np.array(top), np.array(nose)
        res["head"] = {"cap_top_range": [int(top.min()), int(top.max())],
                       "cap_top_max_step": int(np.abs(np.diff(top)).max()),
                       "cap_top_max_2nd_diff": int(np.abs(np.diff(top, 2)).max()),
                       "nose_max_2nd_diff": int(np.abs(np.diff(nose - np.round(np.array([s["hip"][0] for s in st[:n]]) * 0.6667).astype(int), 2)).max()),
                       "godot_errors": errs[:5]}
        ang = [math.degrees(math.atan2(s["scarf_tip"][0] - s["scarf_root"][0], s["scarf_tip"][1] - s["scarf_root"][1]))
               for s in st[:n]]
        moving = [i for i in range(n) if any(f["swing"] for f in st[i]["feet"])]
        stop_i = moving[-1] + 1 if moving else 0
        walk_ang = [ang[i] for i in moving[: max(1, len(moving) - 6)]]
        after = ang[stop_i:]
        bag = [st[i]["bag"][0] - st[i]["hip"][0] for i in range(stop_i, n)]
        res["chains"] = {
            "scarf_deg_walking": [round(min(walk_ang), 1), round(max(walk_ang), 1)] if walk_ang else None,
            "scarf_deg_after_stop": {"max_forward": round(max(after), 1) if after else None,
                                      "at_t": round(st[stop_i + after.index(max(after))]["t"], 3) if after else None,
                                      "min": round(min(after), 1) if after else None},
            "bag_x_rel_hip_after_stop_tex": [round(min(bag), 1), round(max(bag), 1)] if bag else None,
            "last_step_t": round(st[stop_i]["t"], 3) if stop_i < n else None,
        }
        res["state"] = {
            "steps_first": st[0]["steps"],
            "steps_total": st[n - 1]["steps"],
            "sy_range": [round(min(s["sy"] for s in st[:n]), 4), round(max(s["sy"] for s in st[:n]), 4)],
            "tilt_deg_range": [round(float(np.degrees(min(s["tilt"] for s in st[:n]))), 2),
                               round(float(np.degrees(max(s["tilt"] for s in st[:n]))), 2)],
        }
    out = SD / "assets" / "check"
    out.mkdir(parents=True, exist_ok=True)
    name = "measure.json" if a.t0 == 0 else f"measure_t{int(a.t0)}.json"
    (out / name).write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n")
    short = {k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != "phases"}) for k, v in res.items()}
    print(json.dumps(short, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
