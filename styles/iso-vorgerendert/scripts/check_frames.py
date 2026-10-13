#!/usr/bin/env python3
"""Prüfungen an gerenderten Godot-Bildern (iso-vorgerendert).

  .venv/bin/python styles/iso-vorgerendert/scripts/check_frames.py --tmp <tempordner> [--raw <renderordner>]

1. Palette: Jedes Pixel der Spielfläche (Zeilen 0..275 des 640×360-Bilds) muss eine der 256 Palettenfarben sein
   (auch Lichtkreise, Strahl, Schatten, Dachs, Ring); die Bedienleiste getrennt (Schrift ist geglättet).
2. Verdeckung: Lauf mit und ohne --noocc; Anteil der verdeckten Dachspixel je Bild (Figurmaske aus --nobadger).
3. Renderer: Forward+, Mobile und Compatibility, Anteil abweichender Pixel.
4. Wiederholbarkeit: zwei Forward+-Läufe bytegleich.
5. Dauerlauf: ab --t0=30 s, 60 Bilder, Godot-Fehler und Palette.
Schreibt assets/probe/checks.json.
"""
import argparse
import json
import pathlib
import subprocess

import numpy as np
from PIL import Image

STYLE = pathlib.Path(__file__).resolve().parent.parent
DEMO = STYLE / "demo"
SCENE_ROWS = 276


def run(tmp, tag, frames, extra=(), renderer=None):
    d = tmp / tag
    d.mkdir(parents=True, exist_ok=True)
    for p in d.glob("*.png"):
        p.unlink()
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000"]
    if renderer:
        cmd += ["--rendering-method", renderer]
    cmd += ["--write-movie", str(d / "f.png"), "--fixed-fps", "30", "--quit-after", str(frames), "--"] + list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l or "SCRIPT ERROR" in l]
    return sorted(d.glob("f*.png")), errs


def load(p):
    return np.asarray(Image.open(p).convert("RGB"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tmp", required=True)
    a = ap.parse_args()
    tmp = pathlib.Path(a.tmp)
    lut = np.asarray(Image.open(DEMO / "art" / "lut.png").convert("RGB")).reshape(-1, 3)
    pal = {tuple(c) for c in lut}
    pal_key = set(int(c[0]) << 16 | int(c[1]) << 8 | int(c[2]) for c in lut)
    out = {}

    def offpal(img, rows):
        sub = img[rows].reshape(-1, 3).astype(np.int64)
        keys = sub[:, 0] << 16 | sub[:, 1] << 8 | sub[:, 2]
        ok = np.isin(keys, np.array(sorted(pal_key)))
        return int((~ok).sum()), int(len(np.unique(keys)))

    # 1 + 4: Forward+ zweimal
    f1, e1 = run(tmp, "fwd1", 180)
    f2, e2 = run(tmp, "fwd2", 180)
    same = all(open(x, "rb").read() == open(y, "rb").read() for x, y in zip(f1, f2)) and len(f1) == len(f2)
    off_scene, off_ui, colors = 0, 0, set()
    for p in f1[::6]:
        im = load(p)
        o, _ = offpal(im, slice(0, SCENE_ROWS))
        off_scene += o
        o2, _ = offpal(im, slice(SCENE_ROWS, 360))
        off_ui += o2
    im = load(f1[140])
    out["palette"] = {"frames_checked": len(f1[::6]), "scene_pixels_off_palette": off_scene,
                      "ui_pixels_off_palette": off_ui,
                      "scene_unique_colors_frame140": offpal(im, slice(0, SCENE_ROWS))[1]}
    out["deterministic_two_runs"] = bool(same)
    out["godot_errors"] = e1 + e2

    # 2: Verdeckung
    fo, _ = run(tmp, "occ_on", 90, ["--noui", "--noshadow", "--noring"])
    fn, _ = run(tmp, "occ_off", 90, ["--noui", "--noshadow", "--noring", "--noocc"])
    fb, _ = run(tmp, "nobadger", 90, ["--noui", "--nobadger"])
    occ = []
    for i in range(0, 90, 6):
        A, N, B = load(fo[i]).astype(int), load(fn[i]).astype(int), load(fb[i]).astype(int)
        full = np.abs(N - B).sum(-1) > 0
        vis = np.abs(A - B).sum(-1) > 0
        occ.append({"frame": i, "badger_px": int(full.sum()), "visible_px": int((vis & full).sum()),
                    "hidden_share": round(1 - (vis & full).sum() / max(full.sum(), 1), 3)})
    out["occlusion"] = occ

    # 3: Renderer
    picks = [0, 60, 140]
    ren = {}
    for rm in ("mobile", "gl_compatibility"):
        fr, er = run(tmp, rm, 141, renderer=rm)
        diffs = []
        for i in picks:
            A, R = load(f1[i]).astype(int), load(fr[i]).astype(int)
            d = np.abs(A - R).sum(-1)
            diffs.append({"frame": i, "changed_share": round(float((d > 0).mean()), 5),
                          "max_abs": int(np.abs(A - R).max())})
        ren[rm] = {"errors": er, "diffs": diffs}
    out["renderers"] = ren

    # 5: Dauerlauf
    fl, el = run(tmp, "long", 60, ["--t0=30"])
    offl = sum(offpal(load(p), slice(0, SCENE_ROWS))[0] for p in fl[::10])
    out["long_run"] = {"t0": 30, "frames": len(fl), "errors": el, "scene_pixels_off_palette": offl}
    (STYLE / "assets" / "probe").mkdir(parents=True, exist_ok=True)
    json.dump(out, open(STYLE / "assets" / "probe" / "checks.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
