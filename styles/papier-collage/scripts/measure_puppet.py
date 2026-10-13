#!/usr/bin/env python3
"""Misst die Puppe in der echten Godot-Ausgabe (PIPELINE.md, Figuren und Animation).

Rendert 6 s mit --badger-only --no-shadows und jeweils nur einem Teil (--only=...) vor hellem Grund und misst:
  - je Fuß: Standphasen (Sohle auf der Bodenzeile) und darin die Spanne von Ferse und Zehe (Ziel <= 1 px)
  - Sohlenzeilen beider Füße in allen Stehbildern nach dem Anhalten (Ziel: gleich)
  - Kopf (Mützenspitze): Sprung von Bild zu Bild beim Gehen und im Stand
  - Posenwechsel: Anzahl Bilder, in denen sich die Puppe ändert (Legetrick-Takt 15/s => jedes zweite Bild)
Ergebnis: assets/check/puppet_measure.json

    .venv/bin/python styles/papier-collage/scripts/measure_puppet.py
"""
import json, pathlib, subprocess, sys, tempfile
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent.parent
DEMO = HERE / "demo"
BG = np.array([237, 237, 230])


def render(only, frames=180):
    tmp_root = pathlib.Path(tempfile.gettempdir()) / "papier-collage"
    tmp_root.mkdir(exist_ok=True)
    td = pathlib.Path(tempfile.mkdtemp(prefix="measure-", dir=tmp_root))
    args = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
            "--write-movie", str(td / "f.png"), "--fixed-fps", "30", "--quit-after", str(frames), "--",
            "--badger-only", "--no-shadows"] + ([f"--only={only}"] if only else [])
    r = subprocess.run(args, capture_output=True, text=True, timeout=600)
    if "SCRIPT ERROR" in r.stdout + r.stderr:
        sys.exit(r.stdout + r.stderr)
    out = []
    for p in sorted(td.glob("f*.png"))[:frames]:
        a = np.asarray(Image.open(p).convert("RGB")).astype(int)
        out.append(np.abs(a - BG).sum(-1) > 40)
    return out


def bbox(m):
    ys, xs = np.nonzero(m)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())


def stance_spans(masks):
    """Standphasen: Folgen von Bildern, deren Sohle auf der tiefsten Zeile liegt. Spanne von Ferse/Zehe."""
    bbs = [bbox(m) for m in masks]
    ground = max(b[3] for b in bbs if b)
    runs, cur = [], []
    for i, b in enumerate(bbs):
        if b and b[3] >= ground - 0:
            cur.append(i)
        else:
            if len(cur) >= 2:
                runs.append(cur)
            cur = []
    if len(cur) >= 2:
        runs.append(cur)
    res = []
    for r in runs:
        heel = [bbs[i][0] for i in r]
        toe = [bbs[i][1] for i in r]
        # Ferse/Zehe auf der Sohlenzeile messen (unterste 3 Zeilen), robuster als die Gesamtbox
        hs, ts = [], []
        for i in r:
            m = masks[i][ground - 3:ground + 1]
            xs = np.nonzero(m.any(0))[0]
            hs.append(int(xs.min())); ts.append(int(xs.max()))
        res.append({"frames": [r[0], r[-1]], "n": len(r), "heel_span": max(hs) - min(hs),
                    "toe_span": max(ts) - min(ts), "box_heel_span": max(heel) - min(heel),
                    "box_toe_span": max(toe) - min(toe)})
    return ground, res


def main():
    out = {}
    feet = {}
    for part in ("foot_n", "foot_f"):
        masks = render(part)
        ground, runs = stance_spans(masks)
        feet[part] = masks
        out[part] = {"ground_row": ground, "stance_runs": runs,
                     "max_heel_span": max(r["heel_span"] for r in runs),
                     "max_toe_span": max(r["toe_span"] for r in runs)}
    # Stehbilder nach dem Anhalten (ab 3,6 s): Sohlenzeilen
    idle = range(int(3.6 * 30), 180)
    out["idle_sole_rows"] = {p: sorted({bbox(feet[p][i])[3] for i in idle}) for p in feet}
    # Kopf
    masks = render("head")
    tops = [bbox(m)[2] for m in masks]
    walk = [abs(tops[i + 1] - tops[i]) for i in range(0, 95)]
    stand = [abs(tops[i + 1] - tops[i]) for i in range(110, 179)]
    out["head_top_rows"] = tops
    out["head_jump_walk_max"] = max(walk)
    out["head_jump_stand_max"] = max(stand)
    # Posenwechsel der ganzen Puppe
    masks = render(None)
    changes = [i for i in range(1, len(masks)) if (masks[i] != masks[i - 1]).any()]
    out["pose_changes"] = len(changes)
    out["pose_changes_on_odd_frames"] = sum(1 for i in changes if i % 2 == 1)
    bb = [bbox(m) for m in masks]
    out["figure_height_px"] = [min(b[3] - b[2] + 1 for b in bb), max(b[3] - b[2] + 1 for b in bb)]
    out["figure_x_first_last"] = [bb[0][0], bb[-1][0]]
    (HERE / "assets" / "check").mkdir(parents=True, exist_ok=True)
    (HERE / "assets" / "check" / "puppet_measure.json").write_text(json.dumps(out, indent=1))
    summary = {k: v for k, v in out.items() if k not in ("head_top_rows",)}
    for p in ("foot_n", "foot_f"):
        summary[p] = {k: v for k, v in out[p].items() if k != "stance_runs"} | {"runs": len(out[p]["stance_runs"])}
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
