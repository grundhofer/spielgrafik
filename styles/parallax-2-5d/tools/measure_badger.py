#!/usr/bin/env python3
"""Misst den Gang des Dachses in der echten Godot-Ausgabe (Prüfmodus --badger-only: nur die Figur vor Magenta,
Kamera fest in der Gemälde-Position, 1280×720, 30 Bilder/s).

    .venv/bin/python -I styles/parallax-2-5d/tools/measure_badger.py

Je Bild: Maske = nicht Magenta. Sohlenzeile = unterste Zeile der Maske (muss in allen Bildern gleich sein, solange
ein Fuß steht). Kopf = oberste Zeile (Höhe der Figur, Auf und Ab der Hüfte).
Standfuß je Fuß einzeln (--parts=near_foot / far_foot): in jeder Standphase darf er sich um höchstens 1 px
bewegen (feet → max_spread_px).
Ergebnis: assets/measure_badger.json und eine Spur der Fußränder als assets/measure_badger.png.
"""
import json, pathlib, sys
import numpy as np
from PIL import Image, ImageDraw

S = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(S / "tools"))
from shot import render  # noqa: E402

SP = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else S / "assets" / "_measure_tmp"


def feet(sp):
    """Je Fuß einzeln gerendert (--parts): Lage des Fußes je Bild; in der Standphase (unterste Zeile = Sohlenzeile)
    darf er sich höchstens um 1 px bewegen."""
    out = {}
    for foot in ("near_foot", "far_foot"):
        pngs, _ = render(sp / foot, frames=180, user=["--badger-only", "--parts=" + foot])
        rec = []
        for p in pngs:
            a = np.asarray(Image.open(p).convert("RGB")).astype(int)
            m = ~((a[..., 0] > 200) & (a[..., 1] < 60) & (a[..., 2] > 200))
            ys, xs = np.nonzero(m)
            rec.append(None if len(ys) == 0 else (int(xs.min()), int(xs.max()), int(ys.max())))
        sole = max(r[2] for r in rec if r)
        phases, cur = [], []
        for i, r in enumerate(rec):
            on = r is not None and r[2] == sole and r[0] > 2 and r[1] < 1277
            if on:
                cur.append((i, r[0], r[1]))
            elif cur:
                phases.append(cur); cur = []
        if cur:
            phases.append(cur)
        out[foot] = {
            "sole_row": sole,
            "stance_phases": [{"frames": [ph[0][0], ph[-1][0]],
                               "x_spread_px": max(max(q[1] for q in ph) - min(q[1] for q in ph),
                                                  max(q[2] for q in ph) - min(q[2] for q in ph))} for ph in phases],
        }
        out[foot]["max_spread_px"] = max((s["x_spread_px"] for s in out[foot]["stance_phases"]), default=None)
    return out


def main():
    pngs, errs = render(SP, frames=180, user=["--badger-only"])
    rows = []
    for i, p in enumerate(pngs):
        a = np.asarray(Image.open(p).convert("RGB")).astype(int)
        mag = (a[..., 0] > 200) & (a[..., 1] < 60) & (a[..., 2] > 200)
        m = ~mag
        ys, xs = np.nonzero(m)
        if len(ys) == 0:
            rows.append({"frame": i, "visible": False})
            continue
        sole = int(ys.max())
        band = m[sole - 2:sole + 1]
        bx = np.nonzero(band.any(0))[0]
        rows.append({"frame": i, "visible": True, "sole": sole, "head": int(ys.min()),
                     "foot_l": int(bx.min()), "foot_r": int(bx.max()), "x_min": int(xs.min()), "x_max": int(xs.max())})
    vis = [r for r in rows if r["visible"] and r["x_min"] > 2 and r["x_max"] < 1277]
    soles = [r["sole"] for r in vis]
    # Standphasen: aufeinanderfolgende Bilder, in denen sich der linke Fußrand (Ferse) nicht stark ändert
    jumps, phases, cur = [], [], []
    for r0, r1 in zip(vis[:-1], vis[1:]):
        d = r1["foot_l"] - r0["foot_l"]
        if abs(d) <= 3:
            cur.append((r0, r1, d))
        else:
            if cur:
                phases.append(cur)
            cur = []
            jumps.append(d)
    if cur:
        phases.append(cur)
    drift = [max(abs(r1["foot_l"] - ph[0][0]["foot_l"]) for _, r1, _ in ph) for ph in phases if len(ph) >= 2]
    res = {
        "frames": len(pngs), "godot_errors": errs[:5], "visible_frames": len(vis),
        "sole_rows": sorted(set(soles)), "sole_spread_px": (max(soles) - min(soles)) if soles else None,
        "height_px": [min(r["sole"] - r["head"] for r in vis), max(r["sole"] - r["head"] for r in vis)] if vis else None,
        "feet": feet(SP.parent / (SP.name + "_feet")),
        "rows": rows,
    }
    (S / "assets" / "measure_badger.json").write_text(json.dumps(res, indent=1))
    # Spur
    im = Image.new("RGB", (len(rows) * 4, 260), (20, 20, 28))
    d = ImageDraw.Draw(im)
    for r in rows:
        if r["visible"]:
            x = r["frame"] * 4
            d.rectangle([x, 255 - (r["foot_l"] % 250), x + 2, 257 - (r["foot_l"] % 250)], fill=(240, 200, 80))
            d.rectangle([x, 255 - (r["sole"] - 400) * 2, x + 2, 257 - (r["sole"] - 400) * 2], fill=(90, 200, 240))
    im.save(S / "assets" / "measure_badger.png")
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    main()
