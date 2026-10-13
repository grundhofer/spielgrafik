"""Fußmessung des Dachses im gerenderten Godot-Bild (Prüfung nach PIPELINE.md, Figuren und Animation).

  .venv/bin/python styles/iso-pixel/scripts/measure_badger.py [--keep <ordner>]

Nimmt die Demo mit --solo (nur der Dachs auf Schwarz, 426×240) 6 s lang mit 30 fps auf und misst je Aufnahmebild:
  - Standfuß beim Laufen: Blender liefert je Laufbild, welcher Fuß aufsteht (Sohle < 1 cm über dem Boden) und wo
    (Weltlage). Daraus der vorhergesagte Bildpunkt der Sohle. Im Godot-Bild werden die Pixel der Beinfarbe
    (FurDark-Leiter) in einem Fenster um beide vorhergesagten Sohlen dem näheren Fuß zugeordnet; je Fuß zählen
    die unterste Zeile und deren Mitte. Verglichen wird der Standfuß über alle aufeinanderfolgenden Laufbilder,
    in denen er aufsteht (auch über die Zyklusgrenze, an der Godot die Figur um (10, 5) px weiterschiebt).
    Die Bilder werden aus den Aufnahmebildern gruppiert (jedes Laufbild steht 2 Aufnahmebilder).
  - Fußflecken (zusammenhängende Beinpixel der unteren 6 Zeilen) nur zur Ansicht in feet.json.
  - Stehen: unterste Zeile und Kopfoberkante in allen Steh-, Dreh- und Winkbildern.
  - Halt: Verschiebung des zuletzt aufgesetzten Fußes vom letzten Laufbild zum ersten Idle-Bild (soll 0, 0 sein)
    und Haltezeiten der Bilder nach dem Lauf.
Schreibt assets/probe/feet.json und gibt eine Zusammenfassung aus.
"""
import argparse
import json
import pathlib
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isopal  # noqa: E402

ENTRY = HERE.parent
DEMO = ENTRY / "demo"
LEG = np.array(isopal.RAMPS["FurDark"], np.int16)


def label(mask):
    H, W = mask.shape
    lab = np.zeros((H, W), int)
    n = 0
    for y in range(H):
        for x in range(W):
            if mask[y, x] and not lab[y, x]:
                n += 1
                st = [(y, x)]
                lab[y, x] = n
                while st:
                    cy, cx = st.pop()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        yy, xx = cy + dy, cx + dx
                        if 0 <= yy < H and 0 <= xx < W and mask[yy, xx] and not lab[yy, xx]:
                            lab[yy, xx] = n
                            st.append((yy, xx))
    return lab, n


def analyse(path):
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.int16)
    opaque = a.sum(-1) > 0
    ys, xs = np.nonzero(opaque)
    if len(ys) == 0:
        return None
    top, bottom = int(ys.min()), int(ys.max())
    leg = (np.abs(a[..., None, :] - LEG[None, None]).sum(-1) <= 6).any(-1)
    zone = np.zeros_like(leg)
    zone[bottom - 6:bottom + 1] = True
    lab, n = label(leg & zone)
    feet = []
    for k in range(1, n + 1):
        yy, xx = np.nonzero(lab == k)
        if len(yy) < 3:
            continue
        low = yy.max()
        feet.append([float(xx[yy == low].mean()), int(low), int(len(yy))])
    return {"top": top, "bottom": bottom, "feet": feet}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", default="")
    A = ap.parse_args()
    td = pathlib.Path(A.keep) if A.keep else pathlib.Path(tempfile.mkdtemp(prefix="iso-pixel-feet-"))
    td.mkdir(parents=True, exist_ok=True)
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    r = subprocess.run(["godot", "--path", str(DEMO), "--position", "20000,20000", "--write-movie",
                        str(td / "f.png"), "--fixed-fps", "30", "--quit-after", "180", "--", "--solo"],
                       capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    frames = sorted(td.glob("f*.png"))
    res = [analyse(p) for p in frames]
    walk_imgs = 50                                      # 5 Zyklen × 10 Bilder, je 2 Aufnahmebilder
    arrs = [np.asarray(Image.open(p).convert("RGB")) for p in frames]
    groups = [[0]]
    for k in range(1, len(arrs)):
        if np.array_equal(arrs[k], arrs[groups[-1][-1]]):
            groups[-1].append(k)
        else:
            groups.append([k])
    hold = [len(g) for g in groups[:walk_imgs]]
    # Vorhersage der Sohlen aus Blender
    bm = json.load(open(ENTRY / "assets/render/badger/badger.json"))
    binfo = json.load(open(DEMO / "art/badger.json"))
    s = bm["scale_px"]
    R = np.array([0.70710678, 0.70710678, 0.0])
    U = np.array([-0.35355339, 0.35355339, 0.8660254])
    start = np.array([120 + 16 * (1.0 - 5.375), 66 + 8 * (1.0 + 5.375) - 8]).round()
    anchor = np.array(binfo["anchor"], float)
    fmeta = {f["name"]: f for f in bm["frames"]}
    stance = []
    for i in range(walk_imgs):
        g = groups[i][0]
        a = arrs[g].astype(np.int16)
        leg = (np.abs(a[..., None, :] - LEG[None, None]).sum(-1) <= 6).any(-1)
        fm = fmeta["walk_se_%02d" % (i % 10)]
        cyc = i // 10
        pred = {}
        for side, fd in fm["feet"].items():
            P = np.array([fd["x"], fd["y"], 0.0])
            cell = anchor + s * np.array([P @ R, -(P @ U)])
            pred[side] = start - anchor + cell + np.array([10, 5]) * cyc
        ys, xs = np.nonzero(leg)
        meas = {}
        for side, pp in pred.items():
            other = [q for sd, q in pred.items() if sd != side][0]
            d_own = np.hypot(xs + 0.5 - pp[0], ys + 0.5 - pp[1])
            d_oth = np.hypot(xs + 0.5 - other[0], ys + 0.5 - other[1])
            sel = (d_own < 7) & (d_own <= d_oth)
            if sel.any():
                yb = ys[sel].max()
                xb = xs[sel][ys[sel] == yb]
                meas[side] = [float(xb.mean()), int(yb), [int(xb.min()), int(xb.max())]]
        planted = [sd for sd, fd in fm["feet"].items() if fd["zmin"] < 0.01]
        stance.append({"image": i, "planted": planted, "pred": {k: [round(float(v[0]), 1), round(float(v[1]), 1)]
                                                                for k, v in pred.items()}, "meas": meas})
    # Standfuß: nur Bilder mit flach aufstehendem Fuß (Sohle ≤ 4 mm). Für aufeinanderfolgende Bilder desselben
    # Standfußes: Beinpixel im Fenster um die vorhergesagte Sohle (11×7 px) vergleichen und die Verschiebung
    # (dx, dy in ±3 px) mit der größten Überdeckung suchen. (0, 0) heißt: der Fuß steht pixelgenau still.
    def leg_mask(i):
        a = arrs[groups[i][0]].astype(np.int16)
        return (np.abs(a[..., None, :] - LEG[None, None]).sum(-1) <= 6).any(-1)

    masks = {}
    devs = []
    runs = []
    for side in ("L", "R"):
        run = []
        for st in stance + [None]:
            fm = fmeta["walk_se_%02d" % (st["image"] % 10)] if st else None
            if st is not None and fm["feet"][side]["zmin"] <= 0.004:
                run.append(st)
                continue
            if len(run) >= 2:
                shifts = []
                p0 = np.array(run[0]["pred"][side])
                for r0, r1 in zip(run, run[1:]):
                    for r in (r0, r1):
                        if r["image"] not in masks:
                            masks[r["image"]] = leg_mask(r["image"])
                    cx, cy = int(round(p0[0])), int(round(p0[1]))
                    m0 = masks[r0["image"]][cy - 5:cy + 2, cx - 5:cx + 6]
                    best = None
                    for dy in range(-3, 4):
                        for dx in range(-3, 4):
                            m1 = masks[r1["image"]][cy - 5 + dy:cy + 2 + dy, cx - 5 + dx:cx + 6 + dx]
                            iou = (m0 & m1).sum() / max(1, (m0 | m1).sum())
                            if best is None or iou > best[0] + 1e-9 or (abs(iou - best[0]) < 1e-9 and abs(dx) + abs(dy) < abs(best[1]) + abs(best[2])):
                                best = (iou, dx, dy)
                    shifts.append([best[1], best[2], round(float(best[0]), 2)])
                d = max(max(abs(sh[0]), abs(sh[1])) for sh in shifts)
                devs.append(float(d))
                runs.append({"side": side, "images": [r["image"] for r in run], "shift_iou": shifts,
                             "max_dev_px": float(d), "pred_sole": [round(float(v), 1) for v in p0]})
            run = []
    dev1, dev2 = [], []
    for i in range(walk_imgs - 1):
        a, b = res[groups[i][0]]["feet"], res[groups[i + 1][0]]["feet"]
        if a and b:
            dev1.append(round(float(min(np.hypot(fa[0] - fb[0], fa[1] - fb[1]) for fa in a for fb in b)), 2))
    walk = [res[groups[i][0]] for i in range(walk_imgs)]
    dup_ok = hold
    # Halt: letztes Laufbild -> erstes Idle-Bild. Der im letzten Laufbild aufgesetzte Fuß soll pixelgleich bleiben
    # (Fenster um seine vorhergesagte Sohle, Verschiebung mit größter Überdeckung wie oben). Dazu Kopfoberkante und
    # Mitte der Figur (Spalten der oberen 12 Zeilen), um zu sehen, wie weit der Körper beim Halt nachrückt.
    halt = None
    if len(groups) > walk_imgs:
        last, first = walk_imgs - 1, walk_imgs
        st = stance[last]
        side = [sd for sd in st["planted"]][0] if st["planted"] else "R"
        cx, cy = (int(round(v)) for v in st["pred"][side])
        m0 = leg_mask(last)[cy - 5:cy + 2, cx - 5:cx + 6]
        m1_full = (np.abs(arrs[groups[first][0]].astype(np.int16)[..., None, :] - LEG[None, None]).sum(-1) <= 6).any(-1)
        best = None
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                m1 = m1_full[cy - 5 + dy:cy + 2 + dy, cx - 5 + dx:cx + 6 + dx]
                iou = (m0 & m1).sum() / max(1, (m0 | m1).sum())
                if best is None or iou > best[0] + 1e-9 or (abs(iou - best[0]) < 1e-9 and abs(dx) + abs(dy) < abs(best[1]) + abs(best[2])):
                    best = (iou, dx, dy)

        def head_centre(i):
            op = arrs[groups[i][0]].sum(-1) > 0
            ys, xs = np.nonzero(op)
            top = ys.min()
            sel = ys < top + 12
            return [round(float(xs[sel].mean()), 1), int(top)]
        halt = {"foot": side, "window_centre": [cx, cy], "shift_dx_dy": [best[1], best[2]], "iou": round(float(best[0]), 2),
                "head_last_walk": head_centre(last), "head_first_idle": head_centre(first),
                "recording_frames": [groups[last][-1], groups[first][0]]}
    after = [{"first_frame": g[0], "hold": len(g), "bottom": res[g[0]]["bottom"], "top": res[g[0]]["top"]}
             for g in groups[walk_imgs:]]
    stand = [x for x in res[100:]]
    bottoms = sorted(set(s["bottom"] for s in stand))
    tops = sorted(set(s["top"] for s in stand))
    walk_bottoms = [w["bottom"] for w in walk]
    out = {
        "frames": len(frames), "godot_errors": errs[:5], "walk_images": walk_imgs,
        "hold_frames_per_walk_image": sorted(set(dup_ok)),
        "stance_runs": runs,
        "stance_max_dev_px": max(devs) if devs else None,
        "stance_runs_over_1px": int(sum(d > 1.0 for d in devs)),
        "blob_dev_next_image_px (nur Ansicht, Flecken verschmelzen beim Durchgang)": dev1,
        "stance_detail": stance,
        "walk_bottom_rows": [min(walk_bottoms), max(walk_bottoms)],
        "stand_bottom_rows": bottoms, "stand_top_rows": tops,
        "halt": halt,
        "after_walk_images (Idle SO, Drehung, Winken, Idle Süd)": after,
        "per_frame": res,
    }
    (ENTRY / "assets/probe").mkdir(parents=True, exist_ok=True)
    json.dump(out, open(ENTRY / "assets/probe/feet.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k not in ("per_frame", "stance_detail")}, indent=1)[:4000])


if __name__ == "__main__":
    main()
