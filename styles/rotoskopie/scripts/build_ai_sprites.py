#!/usr/bin/env python3
"""KI-Blatt (assets/raw/sheet.png) zerlegen, an der Vorlage messen, an den Fußpunkten der Vorlage ausrichten und
als Sprite-Streifen in Szenengröße schreiben.

    .venv/bin/python styles/rotoskopie/scripts/build_ai_sprites.py

Ablauf je Figur (Blattpixel, 270 px/m):
  1. Alpha säubern: deckend ab Alpha 100 (Codex liefert innen 253 und einen schwachen Schleier außen),
     Komponenten unter 150 px weg (Krümel), jede Komponente der Zelle mit der größten Überdeckung zuordnen.
  2. Messen gegen die Vorlage (pose_sheet_ids.png, gleiche Zelle):
     - Deckung roh: IoU der Silhouetten so, wie das Modell sie hingelegt hat
     - beste Deckung: IoU nach Suche über Verschiebung (±16 px) und Maßstab (0,90–1,10 um den Fußpunkt)
     - Fußversatz: Verschiebung, die das unterste Band (9 px) der KI-Figur am besten auf das der Vorlage legt
     - Kopfversatz: Verschiebung, die den Kopf (Vorlage oberhalb des Halsansatzes) am besten deckt
     - Phasentreue: IoU jeder KI-Laufzelle mit jeder Vorlagen-Laufzelle (beide am Fußpunkt), Diagonale gegen Rest
     - Kostüm: Oklab-Median der KI-Farben in jeder Teilfläche der Vorlage (3 px erodiert), Spanne über alle Zellen
  3. Ausrichten: Fußpunkt der Vorlage + Fußversatz (waagerecht) und Bodenzeile (senkrecht).
  4. In einer einzigen Lanczos-Abtastung auf 148 px/m verkleinern, Fußpunkt auf (58, 162) im 136×168-Rahmen.
Ausgaben: assets/ai/badger_ai.png (+ .json mit Messwerten), assets/ref/badger_template.png (Vorlage im selben
Rahmen, für das Leuchttisch-Feld der Demo).
"""
import argparse, json

import numpy as np
from PIL import Image

from rs_common import ENTRY, MATS, NUM, erode, label, oklab

ap = argparse.ArgumentParser()
ap.add_argument("--sheet", default="assets/raw/sheet_b.png",
                help="KI-Blatt relativ zum Eintragsordner (eingebaut: sheet_b.png, zweiter Lauf; sheet.png nur gemessen)")
ap.add_argument("--tag", default="", help="nur messen: Ergebnis nach assets/check/measure_<tag>.json, keine Sprites")
args = ap.parse_args()
SHEET = ENTRY / args.sheet
REF = ENTRY / "assets/ref"
OUT = ENTRY / "assets/ai"
OUT.mkdir(parents=True, exist_ok=True)
meta = json.loads((REF / "pose_sheet.json").read_text())
ids = np.asarray(Image.open(REF / "pose_sheet_ids.png"))
tmpl_rgb = np.asarray(Image.open(REF / "pose_sheet.png").convert("RGB"))
raw = np.asarray(Image.open(SHEET).convert("RGBA")).astype(np.float32)
SCENE_PPM, FW, FH, AX, AY = 148.0, 136, 168, 58, 162
K = SCENE_PPM / meta["ppm"]
cells = meta["cells"]


def iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 0.0


def shifted(m, dy, dx):
    o = np.zeros_like(m)
    h, w = m.shape
    o[max(0, dy):h + min(0, dy), max(0, dx):w + min(0, dx)] = m[max(0, -dy):h + min(0, -dy), max(0, -dx):w + min(0, -dx)]
    return o


def scaled(m, s, cx, cy):
    """Binärmaske um (cx, cy) skalieren (nächster Nachbar)."""
    h, w = m.shape
    ys, xs = np.mgrid[0:h, 0:w]
    sx = np.rint((xs - cx) / s + cx).astype(int)
    sy = np.rint((ys - cy) / s + cy).astype(int)
    ok = (sx >= 0) & (sx < w) & (sy >= 0) & (sy < h)
    o = np.zeros_like(m)
    o[ok] = m[sy[ok], sx[ok]]
    return o


def best_shift(a, t, rng, rows=None):
    """Verschiebung (dy, dx) von a, die die IoU mit t (optional nur in rows) maximiert."""
    best = (-1.0, 0, 0)
    for dy in range(-rng, rng + 1):
        for dx in range(-rng, rng + 1):
            s = shifted(a, dy, dx)
            if rows is not None:
                v = iou(s[rows], t[rows])
            else:
                v = iou(s, t)
            if v > best[0]:
                best = (v, dy, dx)
    return best


# 1. Alpha säubern und Komponenten den Zellen zuordnen
alpha = raw[..., 3]
mask = alpha > 100
lab, n = label(mask)
sizes = np.bincount(lab.ravel(), minlength=n + 1)
cell_of = np.full(n + 1, -1)
tmask_full = ids > 0
for c in range(1, n + 1):
    if sizes[c] < 150:
        continue
    ys, xs = np.nonzero(lab == c)
    scores = []
    for i, ce in enumerate(cells):
        x0, y0, x1, y1 = ce["box"]
        tm = tmask_full[y0:y1, x0:x1]
        inside = (xs >= x0) & (xs < x1) & (ys >= y0) & (ys < y1)
        scores.append(int(tm[ys[inside] - y0, xs[inside] - x0].sum()) + int(inside.sum()) // 100)
    cell_of[c] = int(np.argmax(scores))
dropped = int(sum(sizes[c] for c in range(1, n + 1) if cell_of[c] < 0))
print(f"Komponenten {n}, verworfen (< 150 px): {sum(1 for c in range(1, n + 1) if cell_of[c] < 0)} mit {dropped} px")

# 2. je Zelle messen
res = []
parts_lab = {}
for i, ce in enumerate(cells):
    x0, y0, x1, y1 = ce["box"]
    pad = 40                                         # Rand: KI-Figuren dürfen etwas über die Zelle ragen
    X0, X1 = max(0, x0 - pad), min(1536, x1 + pad)
    A = np.isin(lab[y0:y1, X0:X1], np.nonzero(cell_of == i)[0])
    T = np.zeros_like(A)
    T[:, x0 - X0:x1 - X0] = tmask_full[y0:y1, x0:x1]
    rx, ry = ce["root"][0] - X0, ce["root"][1] - y0
    raw_iou = iou(A, T)
    best = (raw_iou, 1.0, 0, 0)
    for s in np.arange(0.90, 1.101, 0.01):
        v, dy, dx = best_shift(scaled(A, s, rx, ry), T, 6)
        if v > best[0]:
            best = (v, round(float(s), 2), dy, dx)
    v, dy, dx = best_shift(scaled(A, best[1], rx, ry), T, 16)
    res.append({"pose": ce["pose"], "iou_raw": round(raw_iou, 3), "iou_best": round(v, 3),
                "scale_best": best[1], "shift_best": [dx, dy], "area_ratio": round(float(A.sum() / T.sum()), 3)})
    parts_lab[i] = (A, X0, T, rx, ry)

# Ein Maßstab je Reihe (Median der besten Maßstäbe): das Modell hat die Reihen verschieden groß gezeichnet
row_scale = {}
for row in (0, 1):
    row_scale[row] = float(np.median([r["scale_best"] for r, c in zip(res, cells) if c["row"] == row]))


def foot_dx(A, T, rng=6, rows=4):
    """Waagerechter Versatz der Sohle: Spaltenbelegung der untersten Zeilen (je Maske ab ihrer eigenen
    untersten Zeile) gegeneinander verschieben, beste IoU."""
    la, lt = np.nonzero(A.any(1))[0].max(), np.nonzero(T.any(1))[0].max()
    pa, pt = A[la - rows + 1:la + 1].any(0), T[lt - rows + 1:lt + 1].any(0)
    best = (-1.0, 0)
    for d in range(-rng, rng + 1):
        q = np.roll(pa, d)
        u = (q | pt).sum()
        v = (q & pt).sum() / u if u else 0
        if v > best[0]:
            best = (v, d)
    return best[1], round(float(best[0]), 3), int(lt - la)


for i, ce in enumerate(cells):
    A, X0, T, rx, ry = parts_lab[i]
    As = scaled(A, row_scale[ce["row"]], rx, ry)
    fdx, fiou, fdy = foot_dx(As, T)
    hy = int(ce["head"][0][1] - ce["box"][1])                # Kopf: oberhalb des Halsansatzes
    hv, hdy, hdx = best_shift(shifted(As, fdy, fdx), T, 16, rows=slice(0, hy))
    res[i].update({"row_scale": row_scale[ce["row"]], "foot_shift": [fdx, fdy], "foot_iou": fiou,
                   "head_shift_after_feet": [hdx, hdy], "head_iou": round(hv, 3),
                   "iou_after_scale_and_feet": round(iou(shifted(As, fdy, fdx), T), 3)})
    print(ce["pose"], res[i])
print("Maßstab je Reihe:", row_scale)
# Platzierung: ein fester Sohlenversatz je Reihe (Median), nicht je Bild. Je Bild gemessen war er in den
# Doppelstand-Bildern unzuverlässig (zwei Füße im Band, das Modell zeichnet den vorderen Fuß länger).
row_foot = {}
for row in (0, 1):
    fs = [r["foot_shift"] for r, c in zip(res, cells) if c["row"] == row]
    row_foot[row] = [int(np.median([f[0] for f in fs])), int(np.median([f[1] for f in fs]))]
for i, ce in enumerate(cells):
    A, X0, T, rx, ry = parts_lab[i]
    fdx, fdy = row_foot[ce["row"]]
    As = shifted(scaled(A, row_scale[ce["row"]], rx, ry), fdy, fdx)
    hy = int(ce["head"][0][1] - ce["box"][1])
    hv, hdy, hdx = best_shift(As, T, 16, rows=slice(0, hy))
    fx, fiou, fy = foot_dx(As, T)
    res[i].update({"placed_shift": [fdx, fdy], "head_residual": [hdx, hdy], "sole_residual_x": fx,
                   "iou_placed": round(iou(As, T), 3)})
print("Sohlenversatz je Reihe:", row_foot)
for r in res:
    print(r["pose"], "Kopf-Rest", r["head_residual"], "Sohle-Rest", r["sole_residual_x"], "IoU", r["iou_placed"])

# Phasentreue der Laufzellen: jede KI-Zelle gegen jede Vorlagenzelle, beide am Fußpunkt ausgerichtet
walk_idx = [i for i, c in enumerate(cells) if c["pose"].startswith("walk_")]


def at_root(m, X0, ce, W=200, H=330):
    rx, ry = int(round(ce["root"][0] - X0)), int(round(ce["root"][1] - ce["box"][1]))
    o = np.zeros((H, W), bool)
    ys, xs = np.nonzero(m)
    yy, xx = ys - ry + H - 10, xs - rx + 100
    ok = (yy >= 0) & (yy < H) & (xx >= 0) & (xx < W)
    o[yy[ok], xx[ok]] = True
    return o


tw = []
for i in walk_idx:
    ce = cells[i]
    x0, y0, x1, y1 = ce["box"]
    T = tmask_full[y0:y1, x0:x1]
    tw.append(at_root(T, x0, ce))
aw = [at_root(scaled(parts_lab[i][0], row_scale[0], parts_lab[i][3], parts_lab[i][4]), parts_lab[i][1], cells[i]) for i in walk_idx]
legs = slice(330 - 10 - int(0.30 * meta["ppm"]), 330)        # Beinbereich: unterste 0,30 m
conf = [[round(iou(aw[a][legs], tw[b][legs]), 3) for b in range(8)] for a in range(8)]
tconf = [[round(iou(tw[a][legs], tw[b][legs]), 3) for b in range(8)] for a in range(8)]
aiconf = [[round(iou(aw[a][legs], aw[b][legs]), 3) for b in range(8)] for a in range(8)]
diag_ok = sum(1 for a in range(8) if int(np.argmax(conf[a])) in (a, (a + 4) % 8))
margin = [round(max(conf[a][a], conf[a][(a + 4) % 8]) - max(conf[a][b] for b in range(8) if b not in (a, (a + 4) % 8)), 3) for a in range(8)]

# Kostüm: Oklab-Median der KI-Farben je Teilfläche der Vorlage (4 px erodiert, zugewandte Seite), abgetastet über
# die beste Lage je Zelle (Maßstab + Verschiebung), damit Verschiebungen nicht als Farbwechsel zählen
rgb = raw[..., :3]
costume = {}
for name in ["FurDark", "FurLight", "Cap", "Vest", "Shirt", "Scarf", "Satchel", "Parcel"]:
    vals = []
    for i, ce in enumerate(cells):
        A, X0, T, rx, ry = parts_lab[i]
        x0, y0, x1, y1 = ce["box"]
        part = np.zeros_like(T)
        part[:, x0 - X0:x1 - X0] = ids[y0:y1, x0:x1] == 1 + NUM[name]
        part = erode(part, 4)
        ys, xs = np.nonzero(part)
        s_, (dx, dy) = res[i]["scale_best"], res[i]["shift_best"]
        qx = np.rint(rx + (xs - dx - rx) / s_).astype(int)
        qy = np.rint(ry + (ys - dy - ry) / s_).astype(int)
        ok = (qx >= 0) & (qx < A.shape[1]) & (qy >= 0) & (qy < A.shape[0])
        qx, qy = qx[ok], qy[ok]
        sel = A[qy, qx]
        if sel.sum() < 30:
            vals.append(None)
            continue
        px = rgb[y0 + qy[sel], X0 + qx[sel]]
        vals.append([round(float(v), 4) for v in np.median(oklab(px), axis=0)])
    ok_ = np.array([v for v in vals if v is not None])
    costume[name] = {"per_cell": vals, "cells_measured": int(len(ok_)), "span_L": round(float(np.ptp(ok_[:, 0])), 4),
                     "span_a": round(float(np.ptp(ok_[:, 1])), 4), "span_b": round(float(np.ptp(ok_[:, 2])), 4)}
    print("Kostüm", name, len(ok_), costume[name]["span_L"], costume[name]["span_a"], costume[name]["span_b"])

if args.tag:
    (ENTRY / "assets/check").mkdir(parents=True, exist_ok=True)
    (ENTRY / f"assets/check/measure_{args.tag}.json").write_text(json.dumps({
        "sheet": args.sheet, "cells": res, "row_scale": row_scale, "placed_shift_per_row": row_foot,
        "walk_phase_match": f"{diag_ok}/8", "walk_phase_margin": margin, "costume_oklab": costume,
        "leg_iou_ai_vs_template": conf}, indent=1))
    raise SystemExit(0)

# 3./4. Sprites: ausrichten und verkleinern
alpha_n = np.clip((alpha - 20.0) / (253.0 - 20.0), 0, 1)
strip = Image.new("RGBA", (FW * len(cells), FH), (0, 0, 0, 0))
tstrip = Image.new("RGBA", (FW * len(cells), FH), (0, 0, 0, 0))
P = 200
for i, ce in enumerate(cells):
    A, X0 = parts_lab[i][:2]
    x0, y0, x1, y1 = ce["box"]
    keep = np.zeros(alpha.shape, bool)
    keep[y0:y1, X0:X0 + A.shape[1]] = A
    # Schleier am Rand behalten, aber nur direkt an der eigenen Figur (1 px)
    grow = keep.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            grow |= np.roll(np.roll(keep, dy, 0), dx, 1)
    a_ = np.where(grow, alpha_n, 0.0)
    rgba = np.dstack([raw[..., :3], a_ * 255]).astype(np.uint8)
    r = res[i]
    # Fußpunkt der Vorlage, KI-Figur um den Reihenmaßstab skaliert und mit der Sohle auf die Vorlagensohle gelegt:
    # ein Punkt q der KI-Figur landet bei root + s·(q − root) + Fußversatz
    s_ = r["row_scale"]
    Ks = K * s_
    ax = ce["root"][0] - r["placed_shift"][0] / s_
    ay = ce["root"][1] - r["placed_shift"][1] / s_
    padded = np.zeros((rgba.shape[0] + 2 * P, rgba.shape[1] + 2 * P, 4), np.uint8)
    padded[P:-P, P:-P] = rgba
    box = (ax + P - AX / Ks, ay + P - AY / Ks, ax + P - AX / Ks + FW / Ks, ay + P - AY / Ks + FH / Ks)
    im = Image.fromarray(padded, "RGBA").convert("RGBa").resize((FW, FH), Image.LANCZOS, box=box).convert("RGBA")
    strip.alpha_composite(im, (i * FW, 0))
    # Vorlage im selben Rahmen (ohne Fußversatz)
    own_cell = np.zeros(ids.shape, bool)
    own_cell[y0:y1, x0:x1] = ids[y0:y1, x0:x1] > 0
    tp = np.dstack([tmpl_rgb, own_cell.astype(np.uint8) * 255])
    tpad = np.zeros((tp.shape[0] + 2 * P, tp.shape[1] + 2 * P, 4), np.uint8)
    tpad[P:-P, P:-P] = tp
    ax, ay = ce["root"]
    box = (ax + P - AX / K, ay + P - AY / K, ax + P - AX / K + FW / K, ay + P - AY / K + FH / K)
    tim = Image.fromarray(tpad, "RGBA").convert("RGBa").resize((FW, FH), Image.LANCZOS, box=box).convert("RGBA")
    tstrip.alpha_composite(tim, (i * FW, 0))
strip.save(OUT / "badger_ai.png", optimize=True)
tstrip.save(REF / "badger_template.png", optimize=True)
summary = {
    "iou_raw": [r["iou_raw"] for r in res], "iou_best": [r["iou_best"] for r in res],
    "scale_best": [r["scale_best"] for r in res], "foot_shift": [r["foot_shift"] for r in res],
    "head_shift_after_feet": [r["head_shift_after_feet"] for r in res],
    "placed_shift_per_row": row_foot, "head_residual": [r["head_residual"] for r in res],
    "sole_residual_x": [r["sole_residual_x"] for r in res], "iou_placed": [r["iou_placed"] for r in res],
    "iou_after_scale_and_feet": [r["iou_after_scale_and_feet"] for r in res],
    "walk_phase_match": f"{diag_ok}/8 KI-Laufzellen decken sich im Beinbereich am besten mit ihrer eigenen Vorlagenphase oder der um 4 versetzten (gleiche Silhouette, Beine getauscht)", "walk_phase_margin": margin, "row_scale": row_scale,
}
(OUT / "badger_ai.json").write_text(json.dumps({
    "frame": [FW, FH], "anchor": [AX, AY], "ppm": SCENE_PPM, "poses": [c["pose"] for c in cells],
    "cells": res, "summary": summary, "leg_iou_ai_vs_template": conf, "leg_iou_template_vs_template": tconf,
    "leg_iou_ai_vs_ai": aiconf, "costume_oklab": costume, "dropped_px": dropped}, indent=1))
print(json.dumps(summary, indent=1, ensure_ascii=False))
print("Phasen (Beine, KI gegen Vorlage):")
for a in range(8):
    print("  ", a, conf[a])
