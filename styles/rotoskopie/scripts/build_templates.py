#!/usr/bin/env python3
"""Aus den Blender-Datenpässen (blender/rotoscope.py) zwei Dinge bauen:

1. Die Posen-Vorlage für das Bildmodell: assets/ref/pose_sheet.png (1536×1024, weiß), oben 8 Laufphasen in Zellen
   à 192 px, unten 6 Phasen „Paket überreichen“ in Zellen à 256 px; jede Figur als flache Graustufen je Material
   (abgewandte Seite dunkler) mit Innenlinien, Füße auf einer Grundlinie je Reihe (y 390 bzw. 902), 270 px/m.
   Dazu pose_sheet.json (Zellen, Fußpunkt, Sohlen, Kopf, Pfote, Paket je Figur in Blattpixeln) und
   pose_sheet_ids.png (Teilkarte in Blattgröße: 0 leer, 1 + Material, +16 abgewandte Seite) für die Messung.
2. Den klassischen Weg ohne KI: assets/classic/badger_classic.png, alle 14 Posen in Szenengröße (148 px/m)
   nebeneinander, flache Farben mit einer harten Schattenstufe aus dem Lichtpass und Tuschelinien aus
   Material-/Seiten-/Tiefengrenzen; badger_classic.json mit Bildgröße und Fußpunkt.

    .venv/bin/python styles/rotoskopie/scripts/build_templates.py --passes <scratch>/rotoskopie/passes
"""
import argparse, json, pathlib

import numpy as np
from PIL import Image

from rs_common import ENTRY, MATS, NUM, dilate, hexrgb, ink_edges, load_pose

ap = argparse.ArgumentParser()
ap.add_argument("--passes", required=True)
ap.add_argument("--sheet-ppm", type=float, default=270.0)
ap.add_argument("--scene-ppm", type=float, default=148.0)
a = ap.parse_args()

pdir = pathlib.Path(a.passes)
info = json.loads((pdir / "passes.json").read_text())
PPM = info["ppm"]
OX, OY = info["origin_px"]
poses = list(info["poses"])
walk = [p for p in poses if p.startswith("walk_")]
give = [p for p in poses if p.startswith("give_")]

# Vorlage: Grauwerte je Material (sRGB), abgewandte Seite × FAR
GRAY = {"FurDark": 72, "FurLight": 236, "Cap": 108, "Brass": 205, "Vest": 128, "Shirt": 216, "Scarf": 156,
        "Satchel": 92, "Parcel": 184, "Nose": 34, "Eye": 26}
FAR = 0.78
TEMPLATE_INK = 24
# Klassischer Weg: Farben nah am glTF-Material, für den Zeichentrick etwas klarer
COLOR = {"FurDark": "4f4541", "FurLight": "f2e6cf", "Cap": "4f5c33", "Brass": "d6a33e", "Vest": "5f6c3d",
         "Shirt": "efdcbc", "Scarf": "b8292c", "Satchel": "7b4228", "Parcel": "c99561", "Nose": "2a201d",
         "Eye": "1e140f"}
SHADE = np.array([0.74, 0.72, 0.82], np.float32)
CLASSIC_INK = hexrgb("231a1c")


def frame_rgba(name, mode):
    idx, far, paw, z, light = load_pose(pdir, name, info)
    edge = ink_edges(idx, far, paw, z)
    alpha = idx >= 0
    if mode == "template":
        r = 2.0 * PPM / 540.0                              # 6 px bei 540 px/m = 3 px im Blatt
        lut = np.array([GRAY[m] for m in MATS], np.float32)
        g = np.where(alpha, lut[np.clip(idx, 0, None)], 255.0) * np.where(far, FAR, 1.0)
        rgb = np.repeat(g[..., None], 3, axis=2)
        ink = dilate(edge, r)
        rgb[ink] = TEMPLATE_INK
    else:
        line = 2.0 * PPM / a.scene_ppm                     # 2 px Linie in Szenengröße
        r = max(0.0, (line - 2.0) / 2.0)
        lut = np.array([hexrgb(COLOR[m]) for m in MATS], np.float32)
        rgb = lut[np.clip(idx, 0, None)]
        shadow = alpha & (light < 0.2) & ~np.isin(idx, [NUM["Eye"], NUM["Nose"]])
        rgb = np.where(shadow[..., None], rgb * SHADE, rgb)
        rgb = np.where(far[..., None], rgb * 0.85, rgb)
        ink = dilate(edge, r)
        rgb[ink] = CLASSIC_INK
    a_ = (alpha | ink).astype(np.float32) * 255
    return np.dstack([rgb, a_]).astype(np.uint8)


def place(rgba, k, out_w, out_h, ax, ay):
    """Verkleinern um k so, dass der Fußpunkt (OX, OY) genau auf (ax, ay) im Ausgabebild liegt."""
    P = 800                                                 # Rand, damit der Ausschnitt nie über den Rand reicht
    pad = np.zeros((rgba.shape[0] + 2 * P, rgba.shape[1] + 2 * P, 4), np.uint8)
    pad[P:P + rgba.shape[0], P:P + rgba.shape[1]] = rgba
    bx0, by0 = OX + P - ax / k, OY + P - ay / k
    box = (bx0, by0, bx0 + out_w / k, by0 + out_h / k)
    im = Image.fromarray(pad, "RGBA").convert("RGBa")
    return im.resize((out_w, out_h), Image.LANCZOS, box=box).convert("RGBA")


def to_px(p, k, ax, ay):
    return [round((p[0] - OX) * k + ax, 2), round((p[1] - OY) * k + ay, 2)]


# 1. Vorlage
ks = a.sheet_ppm / PPM
sheet = Image.new("RGBA", (1536, 1024), (255, 255, 255, 255))
ids = np.zeros((1024, 1536), np.uint8)
cells = []
for row, (names, cw, rootx, ground) in enumerate([(walk, 192, 100, 390), (give, 256, 110, 902)]):
    for i, n in enumerate(names):
        cx = i * cw
        fr = place(frame_rgba(n, "template"), ks, cw, 512, rootx, ground - row * 512)
        sheet.alpha_composite(fr, (cx, row * 512))
        idx, far, *_ = load_pose(pdir, n, info)
        lab = np.where(idx >= 0, 1 + idx + 16 * far, 0).astype(np.uint8)
        P = 800
        labp = np.zeros((lab.shape[0] + 2 * P, lab.shape[1] + 2 * P), np.uint8)
        labp[P:P + lab.shape[0], P:P + lab.shape[1]] = lab
        lim = Image.fromarray(labp, "L")
        bx0, by0 = OX + P - rootx / ks, OY + P - (ground - row * 512) / ks
        lim = lim.resize((cw, 512), Image.NEAREST, box=(bx0, by0, bx0 + cw / ks, by0 + 512 / ks))
        ids[row * 512:(row + 1) * 512, cx:cx + cw] = np.asarray(lim)
        P = info["poses"][n]
        ax, ay = cx + rootx, ground
        feet = {s: {"sole_x": [round((P["feet"][s]["sole_px"][0] - OX) * ks + ax, 2),
                               round((P["feet"][s]["sole_px"][1] - OX) * ks + ax, 2)],
                    "sole_z_m": P["feet"][s]["sole_z_m"],
                    "sole_x_m": [P["feet"][s]["sole_x0_m"], P["feet"][s]["sole_x1_m"]]} for s in "LR"}
        cells.append({"pose": n, "row": row, "box": [cx, row * 512, cx + cw, (row + 1) * 512],
                      "root": [ax, ay], "feet": feet,
                      "head": [to_px(P["head_px"][0], ks, ax, ay), to_px(P["head_px"][1], ks, ax, ay)],
                      "hand_r": to_px(P["hand_r_px"], ks, ax, ay), "parcel": to_px(P["parcel_px"], ks, ax, ay),
                      "bbox_m": P["bbox_m"]})
ref = ENTRY / "assets/ref"
ref.mkdir(parents=True, exist_ok=True)
sheet.convert("RGB").save(ref / "pose_sheet.png", optimize=True)
Image.fromarray(ids, "L").save(ref / "pose_sheet_ids.png", optimize=True)
(ref / "pose_sheet.json").write_text(json.dumps({"ppm": a.sheet_ppm, "size": [1536, 1024], "ground": [390, 902],
                                                 "mats": MATS, "id_code": "0 leer, 1+Material, +16 abgewandt",
                                                 "cells": cells}, indent=1))
print("Vorlage:", ref / "pose_sheet.png", len(cells), "Figuren")

# 2. Klassischer Weg in Szenengröße
kc = a.scene_ppm / PPM
FW, FH, AX, AY = 136, 168, 58, 162          # Rahmen je Bild, Fußpunkt
strip = Image.new("RGBA", (FW * len(poses), FH), (0, 0, 0, 0))
for i, n in enumerate(poses):
    strip.alpha_composite(place(frame_rgba(n, "classic"), kc, FW, FH, AX, AY), (i * FW, 0))
cl = ENTRY / "assets/classic"
cl.mkdir(parents=True, exist_ok=True)
strip.save(cl / "badger_classic.png", optimize=True)
alpha = np.asarray(strip)[..., 3]
cols = [alpha[:, i * FW:(i + 1) * FW] for i in range(len(poses))]
edges = [(int(np.nonzero(c.any(0))[0].min()), int(np.nonzero(c.any(0))[0].max()), int(np.nonzero(c.any(1))[0].min()))
         for c in cols]
(cl / "badger_classic.json").write_text(json.dumps({"frame": [FW, FH], "anchor": [AX, AY], "ppm": a.scene_ppm,
                                                    "poses": poses, "extent_x_top": edges}, indent=1))
print("klassisch:", strip.size, "Ränder je Bild (x0, x1, oben):", edges)
