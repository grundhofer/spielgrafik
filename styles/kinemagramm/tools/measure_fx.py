#!/usr/bin/env python3
"""Misst, wie viel sich in jedem Maskenbereich der Demo bewegt (ohne Figur und Textfeld).

    .venv/bin/python styles/kinemagramm/tools/measure_fx.py WORKDIR [--frames 180] [--demo DIR]

Rendert die Demo (render.py, --no-badger --no-ui) und berechnet je Pixel die Spannweite über alle Bilder
(max - min, 0..255) und den mittleren Unterschied von Bild zu Bild. Ausgewertet je Bereich aus demo/art:
Wasser, Himmel, Sterne, Boote, Lichter (Fenster/Laterne/Leuchtfeuer), Strahlzone (Himmel auf Höhe der Lampe),
Rauchzone (über dem Schornstein) und Rest (Land, Kai, Häuser: sollte fast ruhig sein).
Ergebnis: WORKDIR/fx_measure.json und WORKDIR/fx_range.png (Spannweite als Graubild, zum Ansehen).
Grenzen: Ein Effekt gilt als sichtbar, wenn mindestens 5 % seines Bereichs um mehr als 12 Stufen schwanken;
ein Sprung von Bild zu Bild über 6 Stufen im Mittel eines Bereichs deutet auf Flackern oder Ruckeln hin
(bei der Laterne gewollt, bei Wasser, Himmel, Booten und Sternen nicht). jump20_share: Anteil der Pixel, die je
Bildwechsel um mehr als 20 Stufen springen (Salzrauschen im Glitzern; im fernen Wasserband war es vorher ~5 %).
"""
import argparse, json, pathlib, subprocess, sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--frames", type=int, default=180)
    ap.add_argument("--demo", default=str(HERE.parent / "demo"))
    a = ap.parse_args()
    work = pathlib.Path(a.work)
    out = work / "fx_frames"
    subprocess.run([sys.executable, str(HERE / "render.py"), str(out), "--frames", str(a.frames), "--demo", a.demo,
                    "--", "--no-badger", "--no-ui"], check=True)
    frames = sorted(out.glob("f*.png"))
    lo = hi = prev = None
    step_sum = None
    jump_sum = None   # Anzahl Bildwechsel je Pixel mit Sprung > 20 Stufen (Salzrauschen, Ruckeln)
    for f in frames:
        im = np.asarray(Image.open(f).convert("RGB"), np.int16)
        g = im.max(-1)
        if lo is None:
            lo, hi = g.copy(), g.copy()
            step_sum = np.zeros(g.shape, np.float64)
            jump_sum = np.zeros(g.shape, np.float64)
        else:
            lo = np.minimum(lo, g)
            hi = np.maximum(hi, g)
            step_sum += np.abs(g - prev)
            jump_sum += np.abs(g - prev) > 20
        prev = g
    rng = (hi - lo).astype(np.float32)
    step = step_sum / max(len(frames) - 1, 1)
    jump = jump_sum / max(len(frames) - 1, 1)
    art = pathlib.Path(a.demo) / "art"
    ma = np.asarray(Image.open(art / "mask_a.png").convert("RGB"), np.float32) / 255
    mb = np.asarray(Image.open(art / "mask_b.png").convert("RGB"), np.float32) / 255
    mc = np.asarray(Image.open(art / "mask_c.png").convert("RGB"), np.float32) / 255
    scene = json.loads((art / "scene.json").read_text())
    H, W = rng.shape
    yy, xx = np.mgrid[0:H, 0:W]
    reg = {
        "wasser": ma[..., 0] > 0.5,
        "himmel": (ma[..., 1] > 0.5) & (ma[..., 2] < 0.2),
        "sterne": ma[..., 2] > 0.5,
        "boote": (mc[..., 0] > 0.5) | (mc[..., 1] > 0.5),
        "fenster": mb[..., 0] > 0.3,
        "laterne": mb[..., 1] > 0.3,
        "leuchtfeuer": mb[..., 2] > 0.3,
    }
    lx, ly = scene.get("lamp", [W * 0.8, H * 0.2])
    reg["strahlzone"] = (ma[..., 1] > 0.5) & (np.abs(yy - ly) < 40)
    hz = scene.get("horizon_y", 332)
    reg["wasser_fern"] = (ma[..., 0] > 0.5) & (yy >= hz) & (yy < hz + 68)   # fernes Band (Glitzern)
    cx, cy = scene.get("chimney", [W * 0.1, H * 0.15])
    reg["rauchzone"] = (np.abs(xx - cx - 40) < 70) & (yy < cy) & (yy > cy - 200)
    anyreg = np.zeros((H, W), bool)
    for m in reg.values():
        anyreg |= m
    # Lichthöfe und Rauch reichen über ihre Masken hinaus; der Rest wird ohne deren Umkreis gezählt
    glow = np.zeros((H, W), bool)
    for li in scene.get("lights", []):
        glow |= np.hypot(xx - li["pos"][0], yy - li["pos"][1]) < li.get("glow", 60) * 1.6
    reg["rest"] = ~anyreg & ~glow & ~reg["rauchzone"]
    res = {}
    for k, m in reg.items():
        n = int(m.sum())
        if not n:
            res[k] = {"px": 0}
            continue
        res[k] = {"px": n, "moving_share": round(float((rng[m] > 12).mean()), 3),
                  "range_mean": round(float(rng[m].mean()), 1), "step_mean": round(float(step[m].mean()), 2),
                  "step_p99": round(float(np.percentile(step[m], 99)), 1),
                  "jump20_share": round(float(jump[m].mean()), 4)}
    verdict = {k: ("sichtbar" if v.get("moving_share", 0) >= 0.05 else "kaum") for k, v in res.items() if k != "rest"}
    out_j = {"frames": len(frames), "regions": res, "visible": verdict,
             "rest_moving_share": res["rest"].get("moving_share")}
    print(json.dumps(out_j, ensure_ascii=False, indent=1))
    (work / "fx_measure.json").write_text(json.dumps(out_j, ensure_ascii=False, indent=1))
    Image.fromarray(np.clip(rng * 3, 0, 255).astype(np.uint8), "L").save(work / "fx_range.png")


if __name__ == "__main__":
    main()
