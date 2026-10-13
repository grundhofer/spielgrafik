#!/usr/bin/env python3
"""Füße und Kopf des Dachses in der Godot-Ausgabe messen, für drei Fassungen derselben Bewegung:
Vorlage (Graustufen aus 3D), klassisch (Skript ohne KI) und KI-Übermalung.

    .venv/bin/python styles/rotoskopie/scripts/measure_feet.py --tmp <scratch>/rotoskopie/m [--frames 180]

Je Fassung zwei Läufe mit --badger-only vor Magenta und Grün; Alpha = 1 − (R_magenta − R_grün)/255.
Je Videobild: Sohlenkontakt = Spalten mit Alpha > 0,5 in den untersten 2 Zeilen der Figur; hintere/vordere
Kante (Ferse/Zehe) in Weltpixeln, dazu Erwartung aus den 3D-Sohlen (art/anim.json + pose_sheet.json).
Kopf: oberste Zeile mit Alpha > 0,5 und Schnauzenspitze (rechteste Spalte im oberen Viertel der Figur).
Auswertung:
  - Fehler gegen 3D je Bild (gemessen − erwartet) für Ferse und Zehe, Spanne über alle Bilder einer Fassung
  - Standfuß: an jedem Phasenwechsel die Kante des Fußes, der laut 3D in beiden Phasen am Boden steht
    (Laufen: Ferse des Standfußes, solange die Ferse aufliegt, sonst Zehe), Versatz in px
  - Kopf der KI-Fassung gegen den Kopf der Vorlage (gleiche Pose, gleicher Fußpunkt): Abweichung je Pose
  - unterste Zeile in allen Steh- und Gestenbildern
Schreibt assets/check/feet.json.
"""
import argparse, json, subprocess

import numpy as np
from PIL import Image

from rs_common import ENTRY

ap = argparse.ArgumentParser()
ap.add_argument("--tmp", required=True)
ap.add_argument("--frames", type=int, default=180)
ap.add_argument("--skip-render", action="store_true")
a = ap.parse_args()

import pathlib
tmp = pathlib.Path(a.tmp)
demo = ENTRY / "demo"
anim = json.loads((demo / "art/anim.json").read_text())
sheet = json.loads((ENTRY / "assets/ref/pose_sheet.json").read_text())
cells = {c["pose"]: c for c in sheet["cells"]}
PPM, GROUND, X0 = anim["ppm"], 640.0, 100.0


def render(variant, key):
    out = tmp / f"{variant}_{key}"
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("*.png"):
        f.unlink()
    subprocess.run(["godot", "--path", str(demo), "--position", "20000,20000", "--resolution", "1280x720",
                    "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", str(a.frames),
                    "--", "--badger-only", f"--key={key}", f"--variant={variant}"],
                   capture_output=True, text=True, check=True)
    return sorted(out.glob("f*.png"))


def timeline(n):
    """wie main.gd: Posennummer und Fußpunkt x (ungerundet) je Videobild."""
    step = anim["step_px"]
    if n < 96:
        p = n // 2
        return p % 8, X0 + p * step
    idx = 8
    for f0, i in [[96, 8], [104, 9], [110, 10], [114, 11], [118, 12], [134, 13]]:
        if n >= f0:
            idx = i
    return idx, X0 + 47 * step + anim["stand_offset_px"]


def expected(n):
    idx, x = timeline(n)
    pose = anim["poses"][idx]
    c = cells[pose]
    down = [s for s in "LR" if c["feet"][s]["sole_z_m"] < 0.01]
    root = round(x)
    return {s: [root + c["feet"][s]["sole_x_m"][0] * PPM, root + c["feet"][s]["sole_x_m"][1] * PPM] for s in down}


if not a.skip_render:
    # geänderte PNGs importiert nur --import neu, ein normaler Lauf nicht
    subprocess.run(["godot", "--headless", "--path", str(demo), "--import"], capture_output=True, text=True, check=True)
res = {}
for variant in ("template", "classic", "ai"):
    if not a.skip_render:
        render(variant, "ff00ff")
        render(variant, "00ff00")
    fm = sorted((tmp / f"{variant}_ff00ff").glob("f*.png"))
    fg = sorted((tmp / f"{variant}_00ff00").glob("f*.png"))
    rows = []
    for n, (pm, pg) in enumerate(zip(fm, fg)):
        m = np.asarray(Image.open(pm).convert("RGB")).astype(np.float32)
        g = np.asarray(Image.open(pg).convert("RGB")).astype(np.float32)
        alpha = np.clip(1.0 - (m[..., 0] - g[..., 0]) / 255.0, 0, 1)
        op = alpha > 0.5
        ys = np.nonzero(op.any(1))[0]
        low, top = int(ys.max()), int(ys.min())
        band = op[low - 1:low + 1].any(0)
        xs = np.nonzero(band)[0]
        h = low - top
        upper = op[top:top + h // 4]
        nose = int(np.nonzero(upper.any(0))[0].max())
        exp = expected(n)
        e0 = min(v[0] for v in exp.values())
        e1 = max(v[1] for v in exp.values())
        rows.append({"n": n, "pose": anim["poses"][timeline(n)[0]], "low": low, "top": top, "nose": nose,
                     "rear": int(xs.min()), "front": int(xs.max()), "exp_rear": round(e0, 1), "exp_front": round(e1, 1)})
    res[variant] = rows
    print(variant, "Bilder:", len(rows))


def changes(rows):
    """Phasenwechsel beim Laufen: Versatz der Kante des Fußes, der in beiden Phasen am Boden steht."""
    out = []
    for i in range(1, len(rows)):
        a_, b_ = rows[i - 1], rows[i]
        if a_["pose"] == b_["pose"]:
            continue
        pa, pb = cells[a_["pose"]], cells[b_["pose"]]
        both = [s for s in "LR" if pa["feet"][s]["sole_z_m"] < 0.01 and pb["feet"][s]["sole_z_m"] < 0.01]
        # Ferse des gemeinsamen Standfußes: ist er in beiden Bildern der hinterste Fuß, zählt die hintere Kante
        rec = {"n": b_["n"], "from": a_["pose"], "to": b_["pose"], "foot": both}
        rear_a = min(pa["feet"][s]["sole_x_m"][0] for s in "LR" if pa["feet"][s]["sole_z_m"] < 0.01)
        rear_b = min(pb["feet"][s]["sole_x_m"][0] for s in "LR" if pb["feet"][s]["sole_z_m"] < 0.01)
        front_a = max(pa["feet"][s]["sole_x_m"][1] for s in "LR" if pa["feet"][s]["sole_z_m"] < 0.01)
        front_b = max(pb["feet"][s]["sole_x_m"][1] for s in "LR" if pb["feet"][s]["sole_z_m"] < 0.01)
        if both:
            s = both[0]
            if abs(pa["feet"][s]["sole_x_m"][0] - rear_a) < 1e-4 and abs(pb["feet"][s]["sole_x_m"][0] - rear_b) < 1e-4:
                rec["edge"] = "rear"
                rec["shift"] = b_["rear"] - a_["rear"]
                rec["shift_3d"] = round(b_["exp_rear"] - a_["exp_rear"], 1)
            elif abs(pa["feet"][s]["sole_x_m"][1] - front_a) < 1e-4 and abs(pb["feet"][s]["sole_x_m"][1] - front_b) < 1e-4:
                rec["edge"] = "front"
                rec["shift"] = b_["front"] - a_["front"]
                rec["shift_3d"] = round(b_["exp_front"] - a_["exp_front"], 1)
        out.append(rec)
    return out


summary = {}
for variant, rows in res.items():
    ch = changes(rows)
    walk = [r for r in rows if r["n"] < 96]
    stand = [r for r in rows if r["n"] >= 96]
    er = [r["rear"] - r["exp_rear"] for r in walk]
    ef = [r["front"] - r["exp_front"] for r in walk]
    summary[variant] = {
        "walk_rear_err_px": [round(min(er), 1), round(max(er), 1)],
        "walk_front_err_px": [round(min(ef), 1), round(max(ef), 1)],
        "plant_shift_at_changes": [[c["from"], c["to"], c.get("edge"), c.get("shift"), c.get("shift_3d")] for c in ch],
        "stand_low_rows": sorted(set(r["low"] for r in stand)),
        "walk_low_rows": sorted(set(r["low"] for r in walk)),
        "stand_rear_cols": sorted(set(r["rear"] for r in stand)),
    }
# Kopf der KI-Fassung gegen die Vorlage, je Pose (erstes Videobild der Pose)
head = {}
seen = set()
for ra, rt in zip(res["ai"], res["template"]):
    if ra["pose"] in seen:
        continue
    seen.add(ra["pose"])
    head[ra["pose"]] = {"top_dy": ra["top"] - rt["top"], "nose_dx": ra["nose"] - rt["nose"]}
summary["ai_head_vs_template"] = head
(ENTRY / "assets/check").mkdir(parents=True, exist_ok=True)
(ENTRY / "assets/check/feet.json").write_text(json.dumps({"summary": summary, "frames": res}, indent=1))
print(json.dumps(summary, indent=1))
