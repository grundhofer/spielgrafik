#!/usr/bin/env python3
"""Kostümdrift im Vergleich zu ki-spritesheet: Flächenanteile der Kostümteile je Laufbild.

    .venv/bin/python styles/rotoskopie/scripts/compare_kss.py

Je Blatt (8 Laufbilder): jedes deckende Pixel (Alpha > 100) in Oklab der nächsten Kostümfarbe zuordnen
(Mitten je Blatt aus dessen eigenen Messungen; Tuschelinie L < 0,25 zählt nicht), Anteil je Teil an der Figur.
Verglichen wird die Spanne (max − min) der Anteile über die 8 Bilder:
  - Vorlage (3D, aus pose_sheet_ids.png): Änderung allein durch die Pose (Arm verdeckt Weste usw.)
  - rotoskopie-KI, beide Läufe (assets/raw/sheet.png und sheet_b.png, obere Reihe)
  - ki-spritesheet-KI (styles/ki-spritesheet/assets/raw/walk.png, nur gelesen), Blatt ohne Vorlage
Zusätzlich die Höhe der Figur je Bild (Spanne in % der mittleren Höhe). Schreibt assets/check/costume_compare.json.
"""
import json

import numpy as np
from PIL import Image

from rs_common import ENTRY, NUM, label, oklab

KSS = ENTRY.parent / "ki-spritesheet"
runs = {"a": json.loads((ENTRY / "assets/check/measure_a.json").read_text()),
        "b": json.loads((ENTRY / "assets/check/measure_b.json").read_text())}
kss_meta = json.loads((KSS / "assets/sheets.json").read_text())
sheet = json.loads((ENTRY / "assets/ref/pose_sheet.json").read_text())
PARTS = ["fell", "hell", "gruen", "schal", "tasche", "paket"]


def centers_rot(run):
    c = runs[run]["costume_oklab"]
    v = lambda n: np.array(c[n]["per_cell"][0])
    return {"fell": [v("FurDark")], "hell": [v("FurLight"), v("Shirt")], "gruen": [v("Cap"), v("Vest")],
            "schal": [v("Scarf")], "tasche": [v("Satchel")], "paket": [v("Parcel")]}


def centers_kss():
    c = kss_meta["colors"]["by_sheet_frame1"]["walk"]
    v = lambda n: np.array(c[n]["oklab"])
    return {"fell": [v("fell")], "hell": [v("hemd"), v("bauch")], "gruen": [v("muetze"), v("weste")],
            "schal": [v("schal")], "tasche": [v("tasche")], "paket": [v("paket")]}


def shares(rgb, cent):
    lab = oklab(rgb)
    keep = lab[:, 0] >= 0.25                       # Tuschelinie raus
    lab = lab[keep]
    names, cs = [], []
    for k, lst in cent.items():
        for c in lst:
            names.append(k)
            cs.append(c)
    cs = np.array(cs)
    w = np.array([1.0, 2.0, 2.0])                  # Buntheit stärker gewichten als Helligkeit
    d = (((lab[:, None, :] - cs[None]) * w) ** 2).sum(-1)
    cls = np.array(names)[d.argmin(1)]
    return {p: float((cls == p).mean()) for p in PARTS}


def frames_from(path, n_expect, rows=None):
    im = np.asarray(Image.open(path).convert("RGBA")).astype(np.float32)
    if rows is not None:
        im = im[rows[0]:rows[1]]
    mask = im[..., 3] > 100
    lab, n = label(mask)
    sizes = np.bincount(lab.ravel(), minlength=n + 1)
    sizes[0] = 0
    big = list(np.argsort(sizes)[::-1][:n_expect])
    out = []
    for b in sorted(big, key=lambda b: np.nonzero(lab == b)[1].min()):
        sel = lab == b
        ys = np.nonzero(sel.any(1))[0]
        out.append((im[..., :3][sel], int(ys.max() - ys.min() + 1)))
    return out


res = {}
# Vorlage: Anteile direkt aus der Teilkarte
ids = np.asarray(Image.open(ENTRY / "assets/ref/pose_sheet_ids.png"))
part_of = {NUM["FurDark"]: "fell", NUM["FurLight"]: "hell", NUM["Shirt"]: "hell", NUM["Cap"]: "gruen",
           NUM["Vest"]: "gruen", NUM["Scarf"]: "schal", NUM["Satchel"]: "tasche", NUM["Parcel"]: "paket"}
rows_t, h_t = [], []
for ce in sheet["cells"][:8]:
    x0, y0, x1, y1 = ce["box"]
    c = ids[y0:y1, x0:x1]
    m = (c > 0)
    mats = (c[m] - 1) % 16
    tot = len(mats)
    # Nase, Auge, Messing zählen wie Linie (nicht als Teil)
    keep = np.isin(mats, list(part_of))
    sh = {p: 0.0 for p in PARTS}
    for k, p in part_of.items():
        sh[p] += float((mats[keep] == k).sum() / keep.sum())
    rows_t.append(sh)
    ys = np.nonzero(m.any(1))[0]
    h_t.append(int(ys.max() - ys.min() + 1))
res["vorlage_3d"] = (rows_t, h_t)
for run in ("a", "b"):
    fr = frames_from(ENTRY / runs[run]["sheet"], 8, rows=(0, 512))
    res[f"rotoskopie_ki_{run}"] = ([shares(px, centers_rot(run)) for px, _ in fr], [h for _, h in fr])
fr = frames_from(KSS / "assets/raw/walk.png", 8)
res["ki_spritesheet_ki"] = ([shares(px, centers_kss()) for px, _ in fr], [h for _, h in fr])

out = {}
for k, (rows, hs) in res.items():
    out[k] = {"share_span": {p: round(max(r[p] for r in rows) - min(r[p] for r in rows), 4) for p in PARTS},
              "share_mean": {p: round(float(np.mean([r[p] for r in rows])), 4) for p in PARTS},
              "height_px": hs, "height_span_pct": round(100 * (max(hs) - min(hs)) / float(np.mean(hs)), 1)}
    print(k, "Spanne der Anteile:", out[k]["share_span"], "Höhe:", hs, out[k]["height_span_pct"], "%")
(ENTRY / "assets/check").mkdir(parents=True, exist_ok=True)
(ENTRY / "assets/check/costume_compare.json").write_text(json.dumps(out, indent=1))
