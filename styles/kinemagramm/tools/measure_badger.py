#!/usr/bin/env python3
"""Misst den Dachs in der gerenderten Demo: Fußzeile, Fußspalten, Kopfoberkante und Schalende je Bild.

Rendert zweimal (mit und ohne Dachs, beide ohne Schatten); der Unterschied ist genau die Figur.
    .venv/bin/python styles/kinemagramm/tools/measure_badger.py WORKDIR
Erwartung für ein lebendes Standbild: Füße in allen Bildern auf derselben Zeile und Spalte (±0 px),
Kopf hebt und senkt sich mit dem Atem um wenige Pixel, glatt (keine Sprünge > 1 px je Bild).
"""
import json, pathlib, subprocess, sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
work = pathlib.Path(sys.argv[1])
py = sys.executable
for name, extra in (("with", ["--no-shadow", "--no-ui"]), ("without", ["--no-badger", "--no-ui"])):
    subprocess.run([py, str(HERE / "render.py"), str(work / name), "--frames", "180", "--", *extra], check=True)

rows = []
for i in range(180):
    a = np.asarray(Image.open(work / "with" / f"f{i:08d}.png").convert("RGB"), np.int16)
    b = np.asarray(Image.open(work / "without" / f"f{i:08d}.png").convert("RGB"), np.int16)
    m = np.abs(a - b).max(-1) > 18
    ys, xs = np.where(m)
    if not len(ys):
        rows.append(None)
        continue
    feet = ys.max()
    low = m[feet - 8:feet + 1]
    fx = np.where(low.any(0))[0]
    top = ys.min()
    # Schalende: unterste Zeile mit rotem, deutlich geändertem Pixel
    red = (a[..., 0] > a[..., 1] * 1.6) & (a[..., 0] > 70) & m
    ry, rx = np.where(red)
    rows.append({"frame": i, "feet_y": int(feet), "feet_x0": int(fx.min()), "feet_x1": int(fx.max()),
                 "top_y": int(top), "height": int(feet - top), "scarf_x_mean": float(rx.mean()) if len(rx) else None})

ok = [r for r in rows if r]
def span(k):
    v = [r[k] for r in ok]
    return min(v), max(v)
jumps = max(abs(ok[i + 1]["top_y"] - ok[i]["top_y"]) for i in range(len(ok) - 1))
summary = {k: span(k) for k in ("feet_y", "feet_x0", "feet_x1", "top_y", "height")}
summary["max_top_jump_per_frame"] = jumps
sx = [r["scarf_x_mean"] for r in ok if r["scarf_x_mean"] is not None]
summary["scarf_x_mean_range"] = [round(min(sx), 1), round(max(sx), 1)]
print(json.dumps(summary))
(work / "badger_measure.json").write_text(json.dumps({"summary": summary, "frames": rows}, indent=1))
