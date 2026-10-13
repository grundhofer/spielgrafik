"""Misst den Dachs im gerenderten Bild (PIPELINE.md, Figuren und Animation).

Rendert die Demo mit dem Prüfschalter --probe-badger (nur die Figur vor Magenta, ohne Filmabzug) in ein
Temp-Verzeichnis und misst je Bild:
  - Bodenkontakt: deckende Pixel in den Zeilen 588–591 (die Sohle reicht bis y 592), als Segmente in x
  - Standfuß: Segmente, die sich zwischen zwei aufeinanderfolgenden Posen überdecken, gelten als derselbe
    stehende Fuß; deren linke und rechte Kante dürfen sich höchstens um 1 px verschieben
  - unterste Zeile der Figur (Sohle) in allen Steh- und Winkbildern
  - oberste Zeile (Mützenoberkante) je Pose: zeigt das gewollte Auf und Ab, Sprünge nur beim Drehen
Ergebnis: assets/measure_badger.json

    .venv/bin/python styles/gummischlauch/scripts/measure_badger.py [--keep]
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent.parent
DEMO = HERE / "demo"
TMP = pathlib.Path(os.environ.get("GUMMI_TMP", pathlib.Path(tempfile.gettempdir()) / "gummischlauch")) / "probe_badger"
CONTACT_ROWS = (588, 592)
TURN_TICK = 60
STOP_TICK = 54


def render():
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir(parents=True)
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    r = subprocess.run(["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
                        "--write-movie", str(TMP / "f.png"), "--fixed-fps", "30", "--quit-after", "180", "--",
                        "--probe-badger"], capture_output=True, text=True)
    bad = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    if bad:
        print("\n".join(bad[:10]))
    return sorted(TMP.glob("f*.png"))


def segments(row_mask):
    xs = np.nonzero(row_mask)[0]
    if xs.size == 0:
        return []
    segs, start = [], xs[0]
    for a, b in zip(xs[:-1], xs[1:]):
        if b != a + 1:
            segs.append((int(start), int(a)))
            start = b
    segs.append((int(start), int(xs[-1])))
    return segs


def main():
    files = render()
    frames = []
    for f in files:
        a = np.asarray(Image.open(f).convert("RGB")).astype(int)
        fig = ~((a[..., 0] > 240) & (a[..., 1] < 20) & (a[..., 2] > 240))
        ys = np.nonzero(fig.any(axis=1))[0]
        rows = fig[CONTACT_ROWS[0]:CONTACT_ROWS[1]].any(axis=0)
        frames.append({"top": int(ys.min()), "bottom": int(ys.max()), "contact": segments(rows),
                       "md5": hash(a.tobytes())})
    # Posen: auf Zweien, also Bildpaare (Bild 2k und 2k+1 gehören zu Tick k)
    same_in_tick = sum(frames[2 * k]["md5"] == frames[2 * k + 1]["md5"] for k in range(len(frames) // 2))
    ticks = [frames[2 * k] for k in range(len(frames) // 2)]
    max_shift, pairs, worst = 0, 0, None
    for k in range(len(ticks) - 1):
        for s0 in ticks[k]["contact"]:
            for s1 in ticks[k + 1]["contact"]:
                if s1[0] <= s0[1] and s0[0] <= s1[1]:  # überdecken sich: derselbe stehende Fuß
                    # Segmente, die mit dem anderen Fuß verschmelzen oder sich teilen, auslassen
                    if abs((s1[1] - s1[0]) - (s0[1] - s0[0])) > 3:
                        continue
                    d = max(abs(s1[0] - s0[0]), abs(s1[1] - s0[1]))
                    pairs += 1
                    if d > max_shift:
                        max_shift, worst = d, (k, s0, s1)
    stand = [t["bottom"] for k, t in enumerate(ticks) if k >= TURN_TICK]
    walk_bottom = [t["bottom"] for k, t in enumerate(ticks) if k < TURN_TICK]
    tops = [t["top"] for t in ticks]
    res = {
        "frames": len(frames),
        "ticks": len(ticks),
        "frames_identical_within_tick": f"{same_in_tick}/{len(frames) // 2}",
        "stance_pairs_checked": pairs,
        "stance_max_shift_px": max_shift,
        "stance_worst": worst,
        "sole_bottom_front_view": sorted(set(stand)),
        "sole_bottom_walk": sorted(set(walk_bottom)),
        "head_top_per_tick": tops,
        "head_top_range_walk": [min(tops[:STOP_TICK]), max(tops[:STOP_TICK])],
        "head_top_jumps_gt8": [(k, tops[k], tops[k + 1]) for k in range(len(tops) - 1) if abs(tops[k + 1] - tops[k]) > 8],
        "contacts_per_tick": [t["contact"] for t in ticks],
    }
    (HERE / "assets" / "measure_badger.json").write_text(json.dumps(res, indent=1))
    for k in ["frames_identical_within_tick", "stance_pairs_checked", "stance_max_shift_px", "stance_worst",
              "sole_bottom_front_view", "sole_bottom_walk", "head_top_range_walk", "head_top_jumps_gt8"]:
        print(k, res[k])
    if "--keep" not in sys.argv:
        shutil.rmtree(TMP)


if __name__ == "__main__":
    main()
