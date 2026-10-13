#!/usr/bin/env python3
"""Prüft gerenderte Einzelbilder der Demo (Basisauflösung 640x360) gegen die Regeln des Eintrags.

    ../../.venv/bin/python scripts/check_frames.py <ordner mit f00000000.png ...> [--compare <ordner2>]

Bilder erzeugen (Movie Maker schreibt die Basisauflösung):
    godot --path demo --write-movie <ordner>/f.png --fixed-fps 30 --quit-after 180 [--rendering-method mobile]

Geprüft wird:
  1. höchstens 16 Farben je Bild, jeder Kanal auf dem 4-Bit-Raster (Vielfache von 0x11) -> 4096 Farben;
  2. Dachs: nach dem Einblenden ändert sich im Porträt nichts außer in den Augen- und Mundkästen;
  3. Haltezeiten: Augen, Mund und Wasser wechseln nur in ganzen Bildgruppen (keine 1-Bild-Blitzer);
     gemessen werden die Läufe gleicher Zustände je Teil;
  4. mit --compare: Anzahl abweichender Pixel je Bild gegenüber einem zweiten Lauf (z. B. Mobile-Renderer).
"""
import argparse, json, pathlib, sys

import numpy as np
from PIL import Image

SD = pathlib.Path(__file__).resolve().parent.parent


def runs(states):
    out, cur, n = [], states[0], 0
    for s in states:
        if s == cur:
            n += 1
        else:
            out.append((cur, n))
            cur, n = s, 1
    out.append((cur, n))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames")
    ap.add_argument("--compare")
    a = ap.parse_args()
    meta = json.loads((SD / "demo/art/meta.json").read_text())
    files = sorted(pathlib.Path(a.frames).glob("f*.png"))
    if not files:
        sys.exit("keine Bilder")
    imgs = [np.asarray(Image.open(p).convert("RGB")) for p in files]
    h, w, _ = imgs[0].shape
    assert (w, h) == (640, 360), (w, h)
    report = {"frames": len(imgs)}
    ncol = [len(np.unique(im.reshape(-1, 3), axis=0)) for im in imgs]
    off12 = [int((im % 17 != 0).any(-1).sum()) for im in imgs]
    report["colors_per_frame"] = [min(ncol), max(ncol)]
    report["pixels_off_12bit"] = sum(off12)
    allc = np.unique(np.vstack([im.reshape(-1, 3) for im in imgs[::10]]), axis=0)
    report["distinct_colors_whole_clip_sampled"] = int(len(allc))

    bx, by = meta["badger_pos"]
    bw, bh = meta["badger_size"]
    ex, ey = meta["eyes_pos"]
    mx, my = meta["mouth_pos"]
    eh, ew = Image.open(SD / "demo/art/badger_eyes.png").size[1], Image.open(SD / "demo/art/badger_eyes.png").size[0] // meta["eyes_frames"]
    mh, mw = Image.open(SD / "demo/art/badger_mouth.png").size[1], Image.open(SD / "demo/art/badger_mouth.png").size[0] // meta["mouth_frames"]
    body_a = np.asarray(Image.open(SD / "demo/art/badger_body.png"))[..., 3] > 0
    free = body_a.copy()
    free[ey:ey + eh, ex:ex + ew] = False
    free[my:my + mh, mx:mx + mw] = False
    start = 28                                    # Porträt ist ab Bild 28 ganz eingeblendet
    ref = imgs[start][by:by + bh, bx:bx + bw]
    body_diff = [int((im[by:by + bh, bx:bx + bw] != ref).any(-1)[free].sum()) for im in imgs[start:]]
    report["badger_body_changed_px_max"] = max(body_diff)

    def state(im, x, y, ww, hh):
        return im[by + y:by + y + hh, bx + x:bx + x + ww].tobytes()

    eyes = [state(im, ex, ey, ew, eh) for im in imgs[start:]]
    mouth = [state(im, mx, my, mw, mh) for im in imgs[start:]]
    ids = {}
    report["eye_runs"] = [(ids.setdefault(s, len(ids)), n) for s, n in runs(eyes)]
    ids = {}
    report["mouth_runs"] = [(ids.setdefault(s, len(ids)), n) for s, n in runs(mouth)]
    sx, sy = meta["scene"][:2]
    # Wasser: Streifen links vom Dachs (Bildfenster-x 84..190, Zeilen 128..200)
    water = [im[sy + 128:sy + 200, sx + 84:sx + 190].tobytes() for im in imgs]
    ids = {}
    wr = [(ids.setdefault(s, len(ids)), n) for s, n in runs(water)]
    report["water_states"] = len(ids)
    report["water_run_lengths"] = sorted({n for _, n in wr[1:-1]})
    if a.compare:
        other = sorted(pathlib.Path(a.compare).glob("f*.png"))
        diffs = []
        for p, q in zip(files, other):
            x = np.asarray(Image.open(p).convert("RGB")).astype(int)
            y = np.asarray(Image.open(q).convert("RGB")).astype(int)
            diffs.append(int((np.abs(x - y).max(-1) > 0).sum()))
        report["compare_frames"] = len(diffs)
        report["compare_diff_px_total"] = sum(diffs)
        report["compare_diff_px_max"] = max(diffs)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
