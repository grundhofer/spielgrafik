#!/usr/bin/env python3
"""Misst die Puppe in der Godot-Ausgabe (PIPELINE.md: Figuren und Animation).

Rendert die Demo dreimal vor hellem Grund (--badger-only): nur nahes Bein + Fuß, nur fernes Bein + Fuß,
ganze Puppe. Gemessen wird
  - je Standphase Ferse und Zehe (linkestes/rechtestes Puppenpixel 3 px über der Bodenzeile) und die
    unterste Zeile: Spanne über alle Bilder der Phase (Ziel ≤ 1 px),
  - im Stand (nach dem Abbremsen) dieselben Werte über alle Bilder,
  - der Kopf (oberste Zeile der Mütze) von Bild zu Bild und die Bildwechsel (Posen/s).

    .venv/bin/python styles/silhouette-scherenschnitt/scripts/measure_puppet.py <tmpdir>
"""
import json, math, pathlib, sys
import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from render_frames import render  # noqa: E402

SD = pathlib.Path(__file__).resolve().parents[1]
GROUND = 576.5
T_STEP, N_WALK = 0.40, 6


def dark(p):
    a = np.asarray(Image.open(p).convert("RGB")).astype(int)
    return a.sum(2) < 200


def foot_metrics(m):
    rows = np.where(m[540:600].any(1))[0]
    if not len(rows):
        return None
    bottom = 540 + rows.max()
    r = int(GROUND) - 3
    xs = np.where(m[r])[0]
    if not len(xs):
        return {"bottom": int(bottom), "heel": None, "toe": None}
    return {"bottom": int(bottom), "heel": int(xs.min()), "toe": int(xs.max())}


def main():
    tmp = pathlib.Path(sys.argv[1])
    rig = json.loads((SD / "assets" / "puppet" / "rig.json").read_text())
    L = math.hypot(*rig["pieces"]["leg_n"]["ankle_rel"])
    beta = math.asin(10.0 / (2 * L))
    t_stop = N_WALK * T_STEP + T_STEP * (math.radians(18) - beta) / math.radians(18)
    res = {}
    for side in ("n", "f"):
        files, bad = render(tmp / f"leg_{side}", 180, ["--badger-only", f"--only=leg_{side},foot_{side}"])
        assert not bad, bad
        res[side] = [foot_metrics(dark(f)) for f in files]
    out = {"stance": [], "stand": {}}
    for k in range(N_WALK + 1):
        side = "n" if k % 2 == 0 else "f"
        t0 = k * T_STEP
        t1 = (k + 1) * T_STEP if k < N_WALK else t_stop
        fr = [i for i in range(180) if t0 + 1e-6 <= i / 30.0 < t1 - 1e-6 and i > 0]
        # Pose wechselt mit 15/s: Bild i zeigt die Pose von floor(i/2)/15; nur Bilder, deren Pose in der Phase liegt
        fr = [i for i in fr if t0 - 1e-6 <= math.floor(i / 2 + 1e-6) / 15.0 < t1 - 1e-6]
        ms = [res[side][i] for i in fr if res[side][i] and res[side][i]["heel"] is not None]
        if not ms:
            continue
        span = lambda key: max(m[key] for m in ms) - min(m[key] for m in ms)
        out["stance"].append({"step": k, "leg": side, "frames": [fr[0], fr[-1]], "heel_span": span("heel"),
                              "toe_span": span("toe"), "bottom_span": span("bottom"),
                              "bottom": [min(m["bottom"] for m in ms), max(m["bottom"] for m in ms)]})
    stand = [i for i in range(180) if math.floor(i / 2 + 1e-6) / 15.0 >= t_stop]
    for side in ("n", "f"):
        ms = [res[side][i] for i in stand]
        out["stand"][side] = {"frames": [stand[0], stand[-1]],
                              "heel_span": max(m["heel"] for m in ms) - min(m["heel"] for m in ms),
                              "toe_span": max(m["toe"] for m in ms) - min(m["toe"] for m in ms),
                              "bottom": sorted({m["bottom"] for m in ms})}
    # ganze Puppe: Kopf und Bildwechsel
    files, bad = render(tmp / "full", 180, ["--badger-only"])
    assert not bad, bad
    tops, changes, prev = [], 0, None
    for f in files:
        m = dark(f)
        rows = np.where(m.any(1))[0]
        tops.append(int(rows.min()))
        a = np.asarray(Image.open(f).convert("L"))
        if prev is not None and np.any(a != prev):
            changes += 1
        prev = a
    jumps = [abs(tops[i + 1] - tops[i]) for i in range(len(tops) - 1)]
    out["head_top_rows"] = [min(tops), max(tops)]
    out["head_max_jump_px"] = max(jumps)
    out["head_max_jump_walk_px"] = max(jumps[: int(t_stop * 30)])
    out["head_max_jump_stand_px"] = max(jumps[int(t_stop * 30) + 2:])
    out["pose_changes_per_6s"] = changes
    out["t_stop"] = round(t_stop, 3)
    (SD / "assets" / "check" / "puppet_measure.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
