#!/usr/bin/env python3
"""Füße und Kopf des Dachses in gerenderten Bildern messen (PIPELINE.md → Figuren und Animation).

Zwei Messläufe der Demo mit `-- --badger-only`: nur der Dachs im ID-Puffer, Hafen ausgeblendet.

1. `--measure-cam=bottom` (Hauptmessung): orthografische Kamera unter dem Boden, Blick nach oben, 1 px = 2,8 mm.
   Der Shader gibt im Rotkanal den Bodenkontakt aus (Flächen höchstens 1,2 cm über dem Boden). Je Fuß wird die
   Kontaktfläche verfolgt; steht ein Fuß in zwei Bildern nacheinander auf dem Boden, darf Ferse (linke Kante)
   oder Zehe (rechte Kante) höchstens 1 px wandern (beim Abrollen bleibt die Zehe, beim Aufsetzen die Ferse).
2. `--measure-cam` (Seitenansicht von vorn, perspektivisch wie im Spiel, ~120 px Figurhöhe): Bodenzeile,
   Kopfzeile, Figurhöhe; nach dem Anhalten (Stand, Drehen, Winken) muss die Bodenzeile gleich bleiben.

    .venv/bin/python styles/neon-synthwave/scripts/measure_badger.py [--keep DIR]
Schreibt styles/neon-synthwave/assets/check/badger_measure.json.
"""
import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent
DEMO = ENTRY / "demo"
FPS = 30
STOP_T = 3.6          # walker.gd: Ende des Bremsens
BLEND_END = 4.0       # walker.gd: STOP_T + BLEND_LEN


def render(out: pathlib.Path, frames: int, cam: str = "1") -> list[pathlib.Path]:
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True, text=True)
    out.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
                        "--write-movie", str(out / "m.png"), "--fixed-fps", str(FPS), "--quit-after", str(frames),
                        "--", "--badger-only", "--measure-cam=" + cam], capture_output=True, text=True)
    log = r.stdout + r.stderr
    bad = [l for l in log.splitlines() if "ERROR" in l]
    if bad:
        print("\n".join(bad[:10]))
    return sorted(out.glob("m*.png"))


def measure(p: pathlib.Path) -> dict | None:
    a = np.asarray(Image.open(p).convert("L"), dtype=np.float32) / 255.0
    m = a >= 0.5
    rows = np.where(m.any(axis=1))[0]
    if rows.size == 0:
        return None
    ground, top = int(rows.max()), int(rows.min())
    feet = []
    band = m[ground - 3:ground + 1]
    cols = band.any(axis=0)
    x = 0
    w = cols.size
    while x < w:
        if cols[x]:
            x0 = x
            while x < w and cols[x]:
                x += 1
            x1 = x - 1
            seg = m[:ground + 1, x0:x1 + 1]
            low = int(np.where(seg.any(axis=1))[0].max())
            # Kanten nur in der Bodenzeile dieser Pfote
            row = np.where(m[low, x0:x1 + 1])[0]
            feet.append({"x0": x0, "x1": x1, "low": low,
                         "heel": int(x0 + row.min()), "toe": int(x0 + row.max())})
        x += 1
    head_rows = m[top:top + max(4, (ground - top) // 4)]
    hx = np.where(head_rows.any(axis=0))[0]
    return {"ground": ground, "top": top, "height": ground - top + 1, "feet": feet,
            "head_cx": float((hx.min() + hx.max()) / 2) if hx.size else None}


PX_MM = 2000.0 / 720.0   # Messkamera von unten: orthografisch, 2,0 m Bildhöhe


def contacts(p: pathlib.Path) -> dict:
    """Bodenkontakt je Fuß in der Ansicht von unten (R-Kanal). Bild oben = +z = rechter Fuß (zur Hafenkamera)."""
    a = np.asarray(Image.open(p).convert("RGB"), dtype=np.float32) / 255.0
    c = a[..., 0] >= 0.5
    res = {}
    for name, sl in (("R", slice(0, 360)), ("L", slice(360, 720))):
        ys, xs = np.nonzero(c[sl])
        if xs.size < 3:
            res[name] = None
        else:
            res[name] = {"x0": int(xs.min()), "x1": int(xs.max()), "n": int(xs.size)}
    return res


def bottom_analysis(pngs: list[pathlib.Path]) -> dict:
    cs = [contacts(p) for p in pngs]
    pairs = []
    for i in range(1, len(cs)):
        for f in ("L", "R"):
            a, b = cs[i - 1][f], cs[i][f]
            if a and b:
                d0, d1 = b["x0"] - a["x0"], b["x1"] - a["x1"]
                pairs.append({"frame": i, "t": round(i / FPS, 3), "foot": f, "heel": d0, "toe": d1,
                              "min_px": min(abs(d0), abs(d1))})
    walk = [p for p in pairs if p["t"] <= STOP_T + 0.01]
    blend = [p for p in pairs if STOP_T + 0.01 < p["t"] <= BLEND_END + 0.01]
    turn = [p for p in pairs if 4.05 < p["t"] <= 4.55]
    rest = [p for p in pairs if p["t"] > 4.55]
    def mx(lst, k="min_px"):
        return max((abs(p[k]) for p in lst), default=None)
    return {
        "px_mm": round(PX_MM, 2),
        "walk_contact_pairs": len(walk),
        "walk_stance_max_px": mx(walk),
        "walk_stance_hist": {str(k): sum(1 for p in walk if p["min_px"] == k) for k in range(0, (mx(walk) or 0) + 1)},
        "blend_max_px": mx(blend),
        "turn_max_px": mx(turn),
        "after_turn_max_px": mx(rest),
        "frames_without_contact": [i for i, c in enumerate(cs) if not c["L"] and not c["R"]],
        "pairs": pairs,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", help="Bilder hierhin kopieren (sonst gelöscht)")
    ap.add_argument("--frames", type=int, default=180)
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as td:
        out = pathlib.Path(td)
        pngs = render(out / "front", a.frames, "1")
        res = [measure(p) for p in pngs]
        bpngs = render(out / "bottom", a.frames, "bottom")
        bottom = bottom_analysis(bpngs)
        if a.keep:
            k = pathlib.Path(a.keep)
            for sub, lst in (("front", pngs), ("bottom", bpngs)):
                (k / sub).mkdir(parents=True, exist_ok=True)
                for p in lst:
                    shutil.copy(p, k / sub / p.name)
    walk = []
    worst = 0
    for i in range(1, len(res)):
        r0, r1 = res[i - 1], res[i]
        t = i / FPS
        if r0 is None or r1 is None or t > STOP_T + 0.01:
            continue
        g = max(r0["ground"], r1["ground"])
        best = None
        for f0 in r0["feet"]:
            if f0["low"] < g - 1:
                continue
            for f1 in r1["feet"]:
                if f1["low"] < g - 1 or f1["x1"] < f0["x0"] - 3 or f1["x0"] > f0["x1"] + 3:
                    continue
                d = min(abs(f1["heel"] - f0["heel"]), abs(f1["toe"] - f0["toe"]))
                if best is None or d < best[0]:
                    best = (d, f1["heel"] - f0["heel"], f1["toe"] - f0["toe"])
        if best is None:
            walk.append({"frame": i, "t": round(t, 3), "stance": None})
            continue
        worst = max(worst, best[0])
        walk.append({"frame": i, "t": round(t, 3), "stance_min_shift": best[0], "heel_shift": best[1],
                     "toe_shift": best[2], "ground": g})
    stand = [r["ground"] for i, r in enumerate(res) if r and i / FPS >= BLEND_END]
    blend = [{"frame": i, "t": round(i / FPS, 3), "feet": r["feet"], "ground": r["ground"]}
             for i, r in enumerate(res) if r and STOP_T - 0.05 <= i / FPS < BLEND_END + 0.05]
    summary = {
        "frames": len(res),
        "front_note": "Seitenansicht von vorn: beide Pfoten überdecken sich, die Zuordnung Standfuß/Schwungfuß ist "
                      "dort unsicher (Kontaktwechsel); maßgeblich für den Standfuß ist bottom_view.",
        "front_walk_pairs": len(walk),
        "front_walk_pairs_without_stance": sum(1 for w in walk if "stance_min_shift" not in w),
        "front_walk_max_shift_px": worst,
        "front_walk_shift_histogram": {str(k): sum(1 for w in walk if w.get("stance_min_shift") == k)
                                       for k in range(0, worst + 1)},
        "front_ground_rows_walk": sorted({w["ground"] for w in walk if "ground" in w}),
        "front_ground_rows_after_stop": sorted(set(stand)),
        "front_height_px_range": [min(r["height"] for r in res if r), max(r["height"] for r in res if r)],
    }
    out = ENTRY / "assets" / "check"
    out.mkdir(parents=True, exist_ok=True)
    summary["bottom_view"] = {k: v for k, v in bottom.items() if k != "pairs"}
    (out / "badger_measure.json").write_text(json.dumps({"summary": summary, "front_walk": walk, "front_blend": blend,
                                                         "bottom_pairs": bottom["pairs"]},
                                                        indent=1, ensure_ascii=False))
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
