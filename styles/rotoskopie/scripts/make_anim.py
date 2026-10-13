#!/usr/bin/env python3
"""Sprite-Streifen in die Demo kopieren und demo/art/anim.json schreiben (Zeitplan-Daten für main.gd).

    .venv/bin/python styles/rotoskopie/scripts/make_anim.py

anim.json enthält: Rahmen und Fußpunkt der Streifen, Vorschub je Laufphase aus den 3D-Daten
(0,367 m/s × 1/8 s × 148 px/m), Versatz des Fußpunkts beim Übergang walk_7 -> give_0 (Standfuß rechts bleibt
liegen), je Pose die Sohlenspanne der aufgesetzten Füße (für die Markierung im Leuchttisch-Feld) und die
gemessene Deckung KI/Vorlage.
"""
import json, shutil

from rs_common import ENTRY

ART = ENTRY / "demo/art"
ART.mkdir(parents=True, exist_ok=True)
for src, dst in [("assets/ai/badger_ai.png", "badger_ai.png"), ("assets/classic/badger_classic.png", "badger_classic.png"),
                 ("assets/ref/badger_template.png", "badger_template.png")]:
    shutil.copyfile(ENTRY / src, ART / dst)

ai = json.loads((ENTRY / "assets/ai/badger_ai.json").read_text())
cl = json.loads((ENTRY / "assets/classic/badger_classic.json").read_text())
sheet = json.loads((ENTRY / "assets/ref/pose_sheet.json").read_text())
assert ai["frame"] == cl["frame"] and ai["anchor"] == cl["anchor"] and ai["poses"] == cl["poses"]
ppm = ai["ppm"]
STEP_M = 0.367 / 8.0
cells = {c["pose"]: c for c in sheet["cells"]}


def center(c, s):
    a, b = c["feet"][s]["sole_x_m"]
    return (a + b) / 2


# Übergang walk_7 -> give_0: rechter Fuß (in walk_7 aufgesetzt) bleibt in der Welt liegen
stand_off_m = center(cells["walk_7"], "R") - center(cells["give_0"], "R")
soles = []
for p in ai["poses"]:
    c = cells[p]
    down = [s for s in "LR" if c["feet"][s]["sole_z_m"] < 0.01]
    soles.append([[round(ai["anchor"][0] + c["feet"][s]["sole_x_m"][0] * ppm, 1),
                   round(ai["anchor"][0] + c["feet"][s]["sole_x_m"][1] * ppm, 1)] for s in down])
anim = {"frame": ai["frame"], "anchor": ai["anchor"], "ppm": ppm, "poses": ai["poses"],
        "step_px": round(STEP_M * ppm, 4), "stand_offset_px": round(stand_off_m * ppm, 3),
        "soles_px": soles, "iou_placed": ai["summary"]["iou_placed"], "iou_raw": ai["summary"]["iou_raw"]}
(ART / "anim.json").write_text(json.dumps(anim, indent=1))
print(json.dumps({k: anim[k] for k in ("step_px", "stand_offset_px")}))
