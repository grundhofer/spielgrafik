#!/usr/bin/env python3
"""Misst den Dachs in der gerenderten Godot-Aufnahme (nur Dachs auf Magenta, --probe-badger).

  .venv/bin/python styles/polygon-kino/scripts/measure_badger.py <passes-ordner> [--keep <ordner>]

Standfuß beim Laufen: Die Fußkennbilder aus blender/rotoscope.py (<clip>_NN_feet.png, linker Fuß rot, rechter grün)
geben je Phase die Fläche jedes Fußes; mit derselben Verschiebung wie in main.gd über das Godot-Bild gelegt (1 px
erweitert) liefern sie die gerenderten Pixel dieses Fußes. Für jedes Paar aufeinanderfolgender Laufphasen, in denen
ein Fuß laut Blender aufsteht (tiefster Punkt < 1 cm, Aufsetzpunkt in der Welt < 1 cm verschoben), wird die
unterste Pixelzeile dieses Fußes und ihre Spanne in x verglichen.

Je Bild (30 fps, 6 s): Kopfzeile (oberste Zeile der Figur), Fußzeile (unterste Zeile) und die Sohlen
(Läufe in den untersten 2 Zeilen). Laufen (Totale): Für jeden Phasenwechsel wird geprüft, ob eine Sohle an
derselben Stelle bleibt (Standfuß, Versatz in px). Stehen und Winken: Fußzeile und Sohlen müssen gleich bleiben.
Brodeln: geänderte Pixel zwischen aufeinanderfolgenden Stehphasen (Totale und Nahe ohne Winken).
Ergebnis: assets/badger_measure.json
"""
import argparse
import json
import re
import pathlib
import shutil
import subprocess
import tempfile

import numpy as np
from PIL import Image

ENTRY = pathlib.Path(__file__).resolve().parent.parent
CUT = 3.6
WALK_END = 44 / 15.0


def soles(mask):
    ys = np.nonzero(mask.any(axis=1))[0]
    bottom = ys.max()
    rows = mask[bottom - 1:bottom + 1].any(axis=0)
    xs = np.nonzero(rows)[0]
    runs = []
    if xs.size:
        start = xs[0]
        for a, b in zip(xs[:-1], xs[1:]):
            if b != a + 1:
                runs.append((int(start), int(a)))
                start = b
        runs.append((int(start), int(xs[-1])))
    return int(ys.min()), int(bottom), runs


def const(src, name):
    m = re.search(rf"^const {name} := ([-0-9.]+)", src, re.M)
    return float(m.group(1))


def foot_regions(path, ss):
    a = np.asarray(Image.open(path))
    h, w = a.shape[0] // ss, a.shape[1] // ss
    out = {}
    for side, ch in (("L", 0), ("R", 1)):
        m = (a[..., ch] > 127) & (a[..., 3] > 0)
        frac = m[:h * ss, :w * ss].reshape(h, ss, w, ss).mean(axis=(1, 3))
        out[side] = frac > 0.25
    return out


def walk_feet(passes, rows_img):
    src = (ENTRY / "demo/main.gd").read_text()
    data = json.load(open(ENTRY / "demo/data/scenes.json"))
    cl = data["shots"]["A"]["clips"]["walk"]
    k = cl["px_per_m_x"][0]
    at = cl["at"][0]
    start_px, steps = const(src, "WALK_START_PX"), int(const(src, "WALK_STEPS"))
    nph, m_ph = int(const(src, "WALK_PHASES")), 0.367 / 8.0
    x_start = at + (start_px - cl["foot_px"][0]) / k
    ss = json.load(open(pathlib.Path(passes) / "frames.json"))["ss"]
    regs = [foot_regions(pathlib.Path(passes) / f"A_walk_{i:02d}_feet.png", ss) for i in range(nph)]
    feet = cl["feet"]
    res = []
    for s in range(steps - 1):
        p0, p1 = s % nph, (s + 1) % nph
        for side in "LR":
            z0, xw0 = feet[p0][side]
            z1, xw1 = feet[p1][side]
            if z0 > 0.01 or z1 > 0.01:
                continue
            if abs((xw0 + s * m_ph) - (xw1 + (s + 1) * m_ph)) > 0.01:
                continue
            # Aufsetzpunkt aus Blender (Welt) mit der ganzzahligen Verschiebung aus main.gd, in Bildpunkten
            cpx = []
            for st, xw in ((s, xw0), (s + 1, xw1)):
                dx = int(round((x_start + st * m_ph - at) * k))
                cpx.append(round(cl["foot_px"][0] + (xw - at) * k + dx, 2))
            meas = []
            for st, ph in ((s, p0), (s + 1, p1)):
                dx = int(round((x_start + st * m_ph - at) * k))
                reg = np.roll(regs[ph][side], dx, axis=1)
                reg = reg | np.roll(reg, 1, 0) | np.roll(reg, -1, 0) | np.roll(reg, 1, 1) | np.roll(reg, -1, 1)
                img = rows_img[2 * st]
                if img is None:
                    meas = None
                    break
                fm = img[:reg.shape[0]] & reg
                ys, xs = np.nonzero(fm)
                if ys.size == 0 or xs.min() <= 0:
                    meas = None
                    break
                b = ys.max()
                bx = xs[ys == b]
                meas.append((int(b), int(bx.min()), int(bx.max())))
            d = None
            if meas:
                d = max(abs(meas[0][0] - meas[1][0]), abs(meas[0][1] - meas[1][1]), abs(meas[0][2] - meas[1][2]))
            res.append({"step": s, "foot": side, "near": side == "R", "sole_px": meas, "shift_px": d,
                        "contact_px": cpx, "contact_shift_px": round(abs(cpx[1] - cpx[0]), 2)})
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("passes")
    ap.add_argument("--keep", default="")
    a = ap.parse_args()
    td = pathlib.Path(a.keep) if a.keep else pathlib.Path(tempfile.mkdtemp())
    td.mkdir(parents=True, exist_ok=True)
    subprocess.run(["godot", "--headless", "--path", str(ENTRY / "demo"), "--import"], capture_output=True)
    subprocess.run(["godot", "--path", str(ENTRY / "demo"), "--position", "20000,20000", "--write-movie",
                    str(td / "f.png"), "--fixed-fps", "30", "--quit-after", "180", "--", "--probe-badger"],
                   capture_output=True)
    files = sorted(td.glob("f*.png"))
    rows = []
    masks = []
    imgs = []
    for i, f in enumerate(files):
        im = np.asarray(Image.open(f).convert("RGB")).astype(int)
        imgs.append(im[:148])
        mask = ~((im[..., 0] == 255) & (im[..., 1] == 0) & (im[..., 2] == 255))
        mask[148:] = False
        masks.append(mask if mask.any() else None)
        if not mask.any():
            rows.append(None)
            continue
        top, bottom, runs = soles(mask)
        rows.append({"frame": i, "t": round(i / 30, 3), "head": top, "foot": bottom, "soles": runs,
                     "hash": hash(mask.tobytes())})
    res = {"frames": len(files)}
    src_main = (ENTRY / "demo/main.gd").read_text()
    walk = [r for r in rows if r and r["t"] < WALK_END - 1e-6]
    # Fußzeile beim Laufen: naher Fuß setzt 2 px tiefer auf als der ferne (Perspektive, beide stehen auf z = 0);
    # Zeilen über 130 stammen aus den Bildern, in denen der Dachs noch halb außerhalb steht.
    res["walk_rows"] = {"foot_rows": sorted({r["foot"] for r in walk}), "head_rows": sorted({r["head"] for r in walk})}
    wf = walk_feet(a.passes, masks)
    near = [w["shift_px"] for w in wf if w["near"] and w["shift_px"] is not None]
    far = [w["shift_px"] for w in wf if not w["near"] and w["shift_px"] is not None]
    cs = [w["contact_shift_px"] for w in wf]
    res["stance_feet"] = wf
    res["stance_summary"] = {
        "pairs": len(wf),
        "near_foot_rendered_shift_px": {str(v): near.count(v) for v in sorted(set(near))},
        "far_foot_rendered_shift_px": {str(v): far.count(v) for v in sorted(set(far))},
        "far_foot_note": "ferner Fuß meist vom nahen Bein verdeckt; sichtbare Restpixel wechseln mit der Verdeckung",
        "contact_shift_px_max": max(cs) if cs else None}
    print("Standfuß (Paare aufeinanderfolgender Phasen):", json.dumps(res["stance_summary"]))
    for key, sel in (("stand_A", lambda r: WALK_END + 1e-6 < r["t"] < CUT - 1e-6),
                     ("stand_B", lambda r: r["t"] >= CUT)):
        st = [r for r in rows if r and sel(r)]
        res[key] = {"frames": len(st), "foot_rows": sorted({r["foot"] for r in st}),
                    "soles": sorted({json.dumps(r["soles"]) for r in st}),
                    "head_rows": sorted({r["head"] for r in st})}
    # Brodeln beim Stehen: geänderte Pixel der Figur zwischen aufeinanderfolgenden Stehphasen (nur Bilder, in denen
    # die Phase wechselt). Bild i zeigt t = (i + 1) / 30 (Zeit nach dem ersten delta).
    wave_start = const(src_main, "WAVE_START")
    wave_end = wave_start + len(json.load(open(ENTRY / "demo/data/scenes.json"))["shots"]["B"]["clips"]["wave"]["times"]) / const(src_main, "WAVE_FPS")
    for key, sel in (("idle_change_A", lambda tt: WALK_END + 1e-6 < tt < CUT - 1e-6),
                     ("idle_change_B", lambda tt: CUT + 1e-6 < tt < wave_start - 1e-6 or tt > wave_end + 1e-6)):
        ch = []
        for i in range(1, len(imgs)):
            if sel((i + 1) / 30.0) and sel(i / 30.0):
                d = int((np.abs(imgs[i] - imgs[i - 1]).max(axis=2) > 0).sum())
                if d:
                    ch.append(d)
        fig = [int(m.sum()) for i, m in enumerate(masks) if m is not None and sel((i + 1) / 30.0)]
        res[key] = {"phase_changes": len(ch), "changed_px": ch,
                    "figure_px_mean": round(float(np.mean(fig)), 1) if fig else None}
    out = ENTRY / "assets/badger_measure.json"
    out.write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print("Laufen:", json.dumps(res["walk_rows"], ensure_ascii=False))
    print("Stehen A:", json.dumps(res["stand_A"], ensure_ascii=False))
    print("Stehen/Winken B:", json.dumps(res["stand_B"], ensure_ascii=False))
    print("Brodeln:", json.dumps({k: res[k] for k in ("idle_change_A", "idle_change_B")}, ensure_ascii=False))
    if not a.keep:
        shutil.rmtree(td)


if __name__ == "__main__":
    main()
