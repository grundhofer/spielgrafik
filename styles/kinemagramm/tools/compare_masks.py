#!/usr/bin/env python3
"""Vergleicht die KI-Farbcode-Maske mit den von Hand (Polygone + Guided Filter) erzeugten Masken.

    .venv/bin/python styles/kinemagramm/tools/compare_masks.py tools/scene_hand.json tools/scene_ai.json OUTDIR

Beide Konfigurationen laufen durch prep.py (in OUTDIR/hand und OUTDIR/ai). Ausgabe: IoU je Klasse
(Wasser, Himmel), Fläche, mittlerer Kantenabstand und die beste Verschiebung der KI-Maske gegenüber dem Bild
(Suche ±12 px, Maß: Übereinstimmung der Maskenkante mit Bildkanten).
"""
import json, pathlib, subprocess, sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import imgops as K  # noqa: E402

hand_cfg, ai_cfg, out = map(pathlib.Path, sys.argv[1:4])
for name, cfg in (("hand", hand_cfg), ("ai", ai_cfg)):
    subprocess.run([sys.executable, str(HERE / "prep.py"), str(cfg), "--out", str(out / name),
                    "--debug", str(out / name / "dbg")], check=True)


def load(name):
    a = np.asarray(Image.open(out / name / "mask_a.png").convert("RGB"), np.float32) / 255
    return {"water": a[..., 0] > 0.5, "sky": a[..., 1] > 0.5}


def edge(m):
    m = m.astype(np.float32)
    gx = np.abs(np.diff(m, axis=1, prepend=0))
    gy = np.abs(np.diff(m, axis=0, prepend=0))
    return (gx + gy) > 0


h, a = load("hand"), load("ai")
img = np.asarray(Image.open(out / "hand" / "still.png").convert("RGB"), np.float32) / 255
L = K.luma(img)
grad = np.hypot(np.diff(L, axis=1, prepend=L[:, :1]), np.diff(L, axis=0, prepend=L[:1]))
res = {}
for k in ("water", "sky"):
    inter = (h[k] & a[k]).sum()
    union = (h[k] | a[k]).sum()
    eh, ea = edge(h[k]), edge(a[k])
    # mittlerer Abstand der KI-Kante zur Hand-Kante (über Distanz-Näherung mit Box-Weitung)
    dist = np.full(eh.shape, 99.0)
    grow = eh.astype(np.float32)
    for r in range(1, 31):
        hit = K.box(eh.astype(np.float32), r) > 0
        dist = np.where((dist == 99.0) & hit, r, dist)
    best = None
    for dy in range(-12, 13, 2):
        for dx in range(-12, 13, 2):
            sh = np.roll(np.roll(ea, dy, 0), dx, 1)
            score = float(grad[sh].mean())
            if best is None or score > best[0]:
                best = (score, dx, dy)
    res[k] = {"iou": round(float(inter / max(union, 1)), 3), "hand_share": round(float(h[k].mean()), 3),
              "ai_share": round(float(a[k].mean()), 3),
              "ai_edge_to_hand_edge_px_median": float(np.median(dist[ea])),
              "ai_edge_to_hand_edge_px_p90": float(np.percentile(dist[ea], 90)),
              "best_shift_dxdy": [best[1], best[2]]}
print(json.dumps(res, indent=1))
(out / "compare.json").write_text(json.dumps(res, indent=1))
