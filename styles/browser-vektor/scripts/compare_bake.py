#!/usr/bin/env python3
"""Prüft, dass das Zusammenfassen unbewegter Formen (vec.gd bake) das Bild nicht ändert.

    .venv/bin/python styles/browser-vektor/scripts/compare_bake.py
Rendert die 6 s einmal normal und einmal mit --probe-nobake und vergleicht Bild für Bild.
Ergebnis: assets/bake_check.json"""
import json, pathlib, subprocess, tempfile
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent.parent


def render(out, *flags):
    out.mkdir()
    subprocess.run(["godot", "--path", str(HERE / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
                    "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", "180", "--", *flags],
                   capture_output=True, text=True)
    return sorted(out.glob("f*.png"))


with tempfile.TemporaryDirectory() as td:
    td = pathlib.Path(td)
    a, b = render(td / "baked"), render(td / "nobake", "--probe-nobake")
    share, gt24, worst = [], [], (0, -1)
    for i, (pa, pb) in enumerate(zip(a, b)):
        A = np.asarray(Image.open(pa).convert("RGB"), dtype=np.int16)
        B = np.asarray(Image.open(pb).convert("RGB"), dtype=np.int16)
        d = np.abs(A - B).max(axis=2)
        share.append(float((d > 0).mean()))
        gt24.append(float((d > 24).mean()))
        if gt24[-1] > worst[0]:
            worst = (gt24[-1], i)
res = {"frames": len(share), "changed_any_mean": round(float(np.mean(share)), 5), "changed_any_max": round(max(share), 5),
       "changed_gt24_max": round(max(gt24), 5), "worst_frame": worst[1]}
(HERE / "assets" / "bake_check.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res))
