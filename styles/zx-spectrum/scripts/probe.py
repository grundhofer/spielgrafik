#!/usr/bin/env python3
"""Prüfungen am gerenderten Bild der Demo (Godot Movie Maker, Basisauflösung 320×240).

  --badger   rendert mit --only=badger und misst je Bild Fußzeile, Kopf und Fußläufe in der Sohlenzeile;
             prüft, dass der Standfuß über jeden Posenwechsel ortsfest bleibt (±1 px).
  --rules    rendert den normalen Lauf (0–6 s) und einen Dauerlauf ab t0 = 30 s und prüft jedes Bild:
             nur die 15 Farben, je 8×8-Zelle höchstens 2 Farben aus derselben Helligkeitsgruppe, Rahmen nur
             die 8 Grundfarben ohne BRIGHT.
  --compare  rendert ein Bild mit --rendering-method gl_compatibility und mobile und vergleicht mit Forward+.
Ergebnis: media/probe.json (Zusammenfassung), Ausgabe auf der Konsole.
"""
import argparse, json, pathlib, subprocess, sys, tempfile

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent
sys.path.insert(0, str(HERE))
import zxlib as zx  # noqa: E402

SX, SY = 32, 24          # Bildschirmursprung im 320×240-Bild
FEET_Y = 135


def render(td, frames, *user, method=None):
    td = pathlib.Path(td)
    cmd = ["godot", "--path", str(ENTRY / "demo"), "--position", "20000,20000", "--write-movie", str(td / "f.png"),
           "--fixed-fps", "30", "--quit-after", str(frames)]
    if method:
        cmd += ["--rendering-method", method]
    if user:
        cmd += ["--", *user]
    r = subprocess.run(cmd, capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    pngs = sorted(td.glob("f*.png"))
    return [np.asarray(Image.open(p).convert("RGB")) for p in pngs], errs


def runs(row):
    idx = np.flatnonzero(row)
    out = []
    if idx.size == 0:
        return out
    s = p = idx[0]
    for i in idx[1:]:
        if i != p + 1:
            out.append((int(s), int(p)))
            s = i
        p = i
    out.append((int(s), int(p)))
    return out


def check_badger():
    with tempfile.TemporaryDirectory() as td:
        probe = pathlib.Path(td) / "probe.jsonl"
        frames, errs = render(td, 180, "--only=badger", f"--probe={probe}")
        info = [json.loads(l) for l in probe.read_text().splitlines()]
    by_f = {d["f"]: d for d in info}
    res = {"errors": errs, "frames": []}
    prev = None
    worst = 0
    feet_rows, heads = set(), set()
    changes = 0
    for i, img in enumerate(frames):
        scr = img[SY:SY + 192, SX:SX + 256]
        ink = scr.max(-1) > 0
        if not ink.any():
            continue
        ys = np.flatnonzero(ink.any(1))
        top, bot = int(ys[0]), int(ys[-1])
        foot = runs(ink[FEET_Y])
        d = by_f.get(i + 1, {})
        rec = {"i": i, "pose": d.get("pose"), "x": d.get("x"), "top": top, "bottom": bot, "foot_runs": foot}
        res["frames"].append(rec)
        if foot and min(r[0] for r in foot) > 0:
            feet_rows.add(bot)
            heads.add(top)
        if prev and prev["pose"] != rec["pose"] and prev["foot_runs"] and foot and prev["x"] is not None:
            # Standfuß: ein Fußlauf, der in beiden Bildern (fast) an derselben Stelle liegt
            best = min(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a in prev["foot_runs"] for b in foot)
            if min(r[0] for r in foot) > 0 and min(r[0] for r in prev["foot_runs"]) > 0:
                worst = max(worst, best)
                changes += 1
                print(f"{prev['pose']:>8} -> {rec['pose']:<8} x {prev['x']:>4}->{rec['x']:<4} "
                      f"Füße {prev['foot_runs']} -> {foot}  Standfuß-Abweichung {best}")
        prev = rec
    res.update({"pose_changes": changes, "standfoot_max_dev_px": worst, "feet_rows": sorted(feet_rows),
                "head_rows": sorted(heads)})
    print(f"Posenwechsel {changes}, größte Standfuß-Abweichung {worst} px, Fußzeilen {sorted(feet_rows)}, "
          f"Kopfzeilen {sorted(heads)}")
    return res


PAL = {tuple(int(v) for v in c) for c in zx.PAL16}
BORDER = {tuple(int(v) for v in c) for c in zx.NORMAL}


def check_frame(img):
    cols = {tuple(c) for c in np.unique(img.reshape(-1, 3), axis=0)}
    foreign = cols - PAL
    scr = img[SY:SY + 192, SX:SX + 256]
    bad = [k for k, v in zx.cell_colours(scr).items() if not zx.cell_ok(v)]
    bmask = np.ones(img.shape[:2], bool)
    bmask[SY:SY + 192, SX:SX + 256] = False
    bcols = {tuple(c) for c in np.unique(img[bmask].reshape(-1, 3), axis=0)}
    return foreign, bad, bcols - BORDER, cols


def check_rules():
    res = {}
    for name, user, n in [("lauf_0_6s", [], 180), ("dauer_ab_30s", ["--t0=30"], 60)]:
        with tempfile.TemporaryDirectory() as td:
            frames, errs = render(td, n, *user)
            if name == "dauer_ab_30s":
                Image.fromarray(frames[-1]).resize((960, 720), Image.NEAREST).save(ENTRY / "media/probe_t30.png")
        all_cols, n_bad, n_foreign, n_border = set(), 0, 0, 0
        worst_cells = 0
        for img in frames:
            foreign, bad, bborder, cols = check_frame(img)
            all_cols |= cols
            n_bad += bool(bad)
            worst_cells = max(worst_cells, len(bad))
            n_foreign += bool(foreign)
            n_border += bool(bborder)
        res[name] = {"frames": len(frames), "errors": errs, "frames_with_foreign_colours": n_foreign,
                     "frames_with_cell_rule_violations": n_bad, "max_bad_cells": worst_cells,
                     "frames_with_bright_border": n_border, "colours_used": len(all_cols)}
        print(name, res[name])
    return res


def compare():
    res = {}
    with tempfile.TemporaryDirectory() as td:
        ref, _ = render(td, 160)
    for m in ("gl_compatibility", "mobile"):
        with tempfile.TemporaryDirectory() as td:
            imgs, errs = render(td, 160, method=m)
        diff = [float((np.abs(a.astype(int) - b.astype(int)).max(-1) > 0).mean()) for a, b in zip(ref, imgs)]
        res[m] = {"frames": len(imgs), "errors": errs, "max_share_pixels_different": max(diff) if diff else None}
        print(m, res[m])
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--badger", action="store_true")
    ap.add_argument("--rules", action="store_true")
    ap.add_argument("--compare", action="store_true")
    a = ap.parse_args()
    subprocess.run(["godot", "--headless", "--path", str(ENTRY / "demo"), "--import"], capture_output=True)
    out_p = ENTRY / "media/probe.json"
    out = json.loads(out_p.read_text()) if out_p.exists() else {}
    if a.badger:
        r = check_badger()
        out["badger"] = {k: v for k, v in r.items() if k != "frames"}
    if a.rules:
        out["rules"] = check_rules()
    if a.compare:
        out["renderers"] = compare()
    out_p.parent.mkdir(exist_ok=True)
    out_p.write_text(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
