#!/usr/bin/env python3
"""Misst, wie stark sich jeder Bereich bewegt (Aufnahme ohne Korn, damit nur echte Bewegung zählt).

    .venv/bin/python styles/fotoreal-standbild/tools/measure_fx.py <Arbeitsordner> [--t0 0]

Je Bereich (aus den Masken und Lagen in demo/art): Anteil der Pixel, die über 6 s um mehr als 12 Stufen schwanken
(sichtbar bewegt), und Anteil der Sprünge > 20 Stufen von Bild zu Bild (Flimmern). Dazu die Helligkeitsspanne der
Laterne, des Fensters und des Leuchtfeuers und der Rest (soll ruhig bleiben).
"""
import argparse, json, pathlib, sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from render import render  # noqa: E402

ART = HERE.parent / "demo" / "art"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--t0", type=float, default=0.0)
    a = ap.parse_args()
    pngs = render(pathlib.Path(a.work) / "fx", 180, None, [f"--t0={a.t0}", "--no-grain", "--no-ui"], quiet=True)
    fr = np.stack([np.asarray(Image.open(p).convert("RGB"), np.float32) for p in pngs])
    L = fr.mean(-1)
    span = L.max(0) - L.min(0)
    jump = np.abs(np.diff(L, axis=0)).max(-1) if False else np.abs(np.diff(L, axis=0))
    ma = np.asarray(Image.open(ART / "mask_a.png"), np.float32) / 255
    mb = np.asarray(Image.open(ART / "mask_b.png"), np.float32) / 255
    mc = np.asarray(Image.open(ART / "mask_c.png"), np.float32) / 255
    scene = json.loads((ART / "scene.json").read_text())
    actor = json.loads((ART / "actor.json").read_text())
    H, W = L.shape[1:]
    yy, xx = np.mgrid[0:H, 0:W]
    fx, fy = actor["feet_screen"]
    sw, sh = actor["size"]
    actor_box = (xx > fx - sw * 0.6) & (xx < fx + sw * 0.75) & (yy > fy - sh - 4) & (yy < fy + 30)
    cx, cy = scene["chimney"]
    smoke = (xx > cx - 30) & (xx < cx + 140) & (yy < cy) & (ma[..., 1] > 0.5)
    regions = {
        "Wasser": (ma[..., 0] > 0.5) & ~actor_box,
        "Himmel": (ma[..., 1] > 0.5) & ~smoke,
        "Boote": (np.maximum(mc[..., 0], mc[..., 1]) > 0.5),
        "Fenster": mb[..., 0] > 0.3,
        "Laterne": mb[..., 1] > 0.3,
        "Leuchtfeuer": mb[..., 2] > 0.3,
        "Rauchzone": smoke,
        "Dachs": actor_box,
    }
    used = np.zeros((H, W), bool)
    out = {}
    for name, m in regions.items():
        used |= m
        if m.sum() == 0:
            continue
        out[name] = {"px": int(m.sum()), "bewegt_%": round(float((span[m] > 12).mean() * 100), 1),
                     "spruenge_%": round(float((jump[:, m] > 20).mean() * 100), 3),
                     "spanne_mittel": round(float(L[:, m].mean(1).max() - L[:, m].mean(1).min()), 2)}
    rest = ~used & (np.abs(yy - 0) >= 0)
    out["Rest"] = {"px": int(rest.sum()), "bewegt_%": round(float((span[rest] > 12).mean() * 100), 1),
                   "spruenge_%": round(float((jump[:, rest] > 20).mean() * 100), 3)}
    print(json.dumps(out, indent=1, ensure_ascii=False))
    Image.fromarray(np.clip(span * 4, 0, 255).astype(np.uint8)).save(pathlib.Path(a.work) / "span.png")


if __name__ == "__main__":
    main()
