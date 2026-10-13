#!/usr/bin/env python3
"""Misst den Dachs (PIPELINE.md: Figuren und Animation), zwei Wege:

1. Knochenpunkte: Demo mit "-- --measure --static-cam" (Totale, feste Kamera). Je Bild Ferse und Zehe
   beider Füße und der Kopf in Welt- und Bildkoordinaten, dazu die Drehung der Figur. Geprüft: Ein Fuß am
   Boden (y < 1 cm) bewegt sich von Bild zu Bild höchstens wenige Millimeter bzw. unter 1 px; die Drehung
   läuft ohne Pausen (Schritte je Bild); im Übergang Lauf -> Stehen (ab IDLE_T) rutschen die Füße nicht.
2. Gerenderte Silhouette: Demo mit "-- --mask" (nur der Dachs, weiß auf Schwarz, Kamera wie in der
   Aufnahme). In der festen Nahaufnahme (ab 4,1 s) unterste und oberste weiße Zeile je Bild: Die Fußzeile
   bleibt beim Stehen und Winken gleich, der Kopf springt nicht. In allen Bildern, in denen der Dialogkasten
   offen ist oder aufklappt (BOX_T aus demo/ui.gd), zählt das Skript die weißen Pixel im Kastenrechteck
   (BOX): Der Kasten darf den Dachs nie verdecken.

    .venv/bin/python styles/voxel/scripts/measure_badger.py [--out DIR]
"""
import argparse, pathlib, re, subprocess, sys, tempfile
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
SNAP = HERE / "snap.py"
UI = HERE.parent / "demo" / "ui.gd"
MAIN = HERE.parent / "demo" / "main.gd"
PY = sys.executable


def run(out, frames, args, all_frames=False):
    cmd = [PY, str(SNAP), str(out), "--frames", frames] + (["--all"] if all_frames else []) + ["--"] + args
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout


def const(path, name):
    m = re.search(rf"const {name} := ([^#\n]+)", path.read_text())
    return m.group(1).strip()


def step(a, b, k):
    return np.linalg.norm(np.array(b[k][:3]) - np.array(a[k][:3])) * 1000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    td = pathlib.Path(a.out or tempfile.mkdtemp())
    report = []
    idle_t = float(const(MAIN, "IDLE_T"))

    # 1. Knochenpunkte (Totale, feste Kamera)
    txt = run(td / "probe", "179", ["--measure", "--static-cam"])
    rows = []
    for l in txt.splitlines():
        if not l.startswith("M "):
            continue
        p = l.split()
        d = {"t": float(p[1]), "rot": float(p[3]), "x": float(p[4])}
        i = 6
        while i < len(p):
            d[p[i]] = [float(v) for v in p[i + 1:i + 6]]
            i += 6
        rows.append(d)
    feet = ("heel.L", "toe.L", "heel.R", "toe.R")
    worst_mm, worst_px = 0.0, 0.0
    worst_at = None
    for prev, cur in zip(rows, rows[1:]):
        for k in feet:
            if prev[k][1] < 0.01 and cur[k][1] < 0.01:
                dw = step(prev, cur, k)
                dp = np.linalg.norm(np.array(cur[k][3:]) - np.array(prev[k][3:]))
                if dw > worst_mm:
                    worst_mm, worst_at = dw, (cur["t"], k)
                worst_px = max(worst_px, dp)
    report.append(f"Knochenpunkte ({len(rows)} Bilder): Fuß am Boden bewegt sich höchstens {worst_mm:.1f} mm "
                  f"je Bild (bei t={worst_at[0]:.2f} s, {worst_at[1]}), in der festen Totale höchstens {worst_px:.2f} px")

    def max_ground_step(sel):
        m, at = 0.0, None
        for prev, cur in zip(sel, sel[1:]):
            for k in feet:
                if prev[k][1] < 0.01 and cur[k][1] < 0.01 and step(prev, cur, k) > m:
                    m, at = step(prev, cur, k), (cur["t"], k)
        return m, at

    walk = [r for r in rows if r["t"] < 3.2]
    m, _ = max_ground_step(walk)
    report.append(f"  davon im geraden Lauf und beim Abbiegen (t < 3,2 s): höchstens {m:.1f} mm je Bild")
    trans = [r for r in rows if idle_t - 0.04 <= r["t"] < 3.95]
    m, at = max_ground_step(trans)
    both = [cur for prev, cur in zip(trans, trans[1:])
            if all(prev[k][1] < 0.012 and cur[k][1] < 0.012 for k in feet)]
    mb = max((step(p, c, k) for p, c in zip(trans, trans[1:]) if c in both for k in feet), default=0.0)
    report.append(f"  Übergang Lauf -> Stehen ({idle_t:.2f}-3,95 s): Fuß am Boden höchstens {m:.1f} mm je Bild "
                  f"(t={at[0]:.2f} s, {at[1]}), im Doppelstand ({len(both)} Bilder) höchstens {mb:.1f} mm")
    stand = [r for r in rows if r["t"] >= 3.95]
    feet_y = [max(r[k][1] for k in feet) for r in stand]
    ms = max(step(p, c, k) for p, c in zip(stand, stand[1:]) for k in feet)
    report.append(f"  Stehen/Winken ab 3,95 s: höchster Fußpunkt {max(feet_y) * 1000:.1f} mm über dem Boden, "
                  f"Fußpunkte bewegen sich höchstens {ms:.1f} mm je Bild")
    rot = np.array([r["rot"] for r in rows])
    tt = np.array([r["t"] for r in rows])
    dr = np.diff(rot)
    turning = np.nonzero(np.abs(dr) > 1e-3)[0]
    if len(turning):
        i0, i1 = turning[0], turning[-1]
        seg = np.abs(dr[i0:i1 + 1])
        report.append(f"  Drehung {tt[i0]:.2f}-{tt[i1 + 1]:.2f} s: Schritte je Bild {seg.min():.2f}-{seg.max():.2f}°, "
                      f"Bilder ohne Drehung dazwischen: {int((seg < 1e-3).sum())}")

    # 2. Silhouette (Kamera wie in der Aufnahme)
    run(td / "mask", "179", ["--mask"], all_frames=True)
    box = [float(v) for v in re.findall(r"[-\d.]+", const(UI, "BOX").split("(", 1)[1])]
    bx0, by0, bw, bh = box
    box_t = float(const(UI, "BOX_T"))
    bottoms, tops = [], []
    occ_worst, occ_frames = (0.0, None), 0
    for f in range(0, 180):
        p = td / "mask" / f"f{f:04d}.png"
        if not p.exists():
            continue
        im = np.array(Image.open(p).convert("L")) > 128
        if (f + 1) / 30 >= box_t:
            inside = im[int(by0):int(by0 + bh), int(bx0):int(bx0 + bw)].sum()
            share = inside / max(im.sum(), 1)
            occ_frames += 1
            if share > occ_worst[0]:
                occ_worst = (share, f)
        if f >= 124:
            ys, xs = np.nonzero(im)
            bottoms.append(ys.max()); tops.append(ys.min())
    b = np.array(bottoms); tp = np.array(tops)
    report.append(f"Silhouette Nahaufnahme (Bild 124-179): Fußzeile {b.min()}-{b.max()}, "
                  f"Kopf/Hand oben {tp.min()}-{tp.max()}, größter Sprung oben je Bild {np.abs(np.diff(tp)).max()} px, "
                  f"Figur {b.max() - tp.max()} px hoch (ohne erhobene Pfote)")
    report.append(f"Verdeckung durch den Dialogkasten (ab {box_t:.1f} s, {occ_frames} Bilder, Rechteck {box}): "
                  f"höchstens {occ_worst[0] * 100:.1f} % der Figur"
                  + (f" (Bild {occ_worst[1]})" if occ_worst[1] is not None else ""))
    print("\n".join(report))
    (HERE.parent / "assets" / "measure_badger.txt").write_text("\n".join(report) + "\n")


if __name__ == "__main__":
    main()
