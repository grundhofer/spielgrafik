#!/usr/bin/env python3
"""Prüft, ob die Rig-Ansicht (Gitter auf der CPU verformt) mit der GPU-Verformung von Polygon2D übereinstimmt.

    .venv/bin/python styles/skelett-2d/scripts/check_overlay.py

Lauf 1 (--overlay-check=gpu): die Figur der Rig-Ansicht trägt statt der Textur rote Linien genau auf den
Rasterlinien ihres Gitters; die GPU verformt sie. Lauf 2 (--overlay-check=cpu): dieselben Rasterkanten,
auf der CPU mit denselben Gewichten verformt, als grüne Linien. Gemessen wird je Bild der Abstand jedes
grünen Linienpixels zum nächsten roten (0–4 px). Schreibt assets/check/overlay_check.json.
"""
import json, pathlib, subprocess, tempfile

import numpy as np
from PIL import Image, ImageFilter

HERE = pathlib.Path(__file__).resolve().parents[1]
FRAMES = [5, 18, 45, 102, 150]


def run(td, mode):
    out = pathlib.Path(td) / mode
    out.mkdir(parents=True)
    subprocess.run(["godot", "--path", str(HERE / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
                    "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", str(max(FRAMES) + 2),
                    "--", f"--overlay-check={mode}"], capture_output=True)
    return out


def main():
    res = {}
    with tempfile.TemporaryDirectory() as td:
        g, c = run(td, "gpu"), run(td, "cpu")
        for i in FRAMES:
            a = np.asarray(Image.open(g / f"f{i:08d}.png").convert("RGB")).astype(int)
            b = np.asarray(Image.open(c / f"f{i:08d}.png").convert("RGB")).astype(int)
            red = (a[..., 0] > 90) & (a[..., 1] < 60)
            green = (b[..., 1] > 120) & (b[..., 0] < 80)
            dist = np.full(green.shape, 99, int)
            cur = Image.fromarray((red * 255).astype(np.uint8))
            for r in range(0, 5):
                m = np.asarray(cur) > 0
                dist[(dist == 99) & m & green] = r
                cur = cur.filter(ImageFilter.MaxFilter(3))
            d = dist[green]
            res[str(i)] = {"green_px": int(green.sum()), "red_px": int(red.sum()),
                           "within_0": round(float((d == 0).mean()), 3), "within_1": round(float((d <= 1).mean()), 3),
                           "within_2": round(float((d <= 2).mean()), 3), "beyond_4": round(float((d == 99).mean()), 4)}
    out = HERE / "assets" / "check" / "overlay_check.json"
    out.write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
