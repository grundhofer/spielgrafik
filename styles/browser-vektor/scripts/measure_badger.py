#!/usr/bin/env python3
"""Misst den Dachs in der gerenderten Demo (30 fps wie capture.py).

    .venv/bin/python styles/browser-vektor/scripts/measure_badger.py [--keep DIR]

Rendert die Demo zweimal mit --probe-measure (ohne Zeiger, Schild, Klickring und Bodenschatten), einmal mit und
einmal ohne Dachs (--probe-no-badger). Das Differenzbild ist der Dachs. Gemessen werden je Bild:
  * Fußzeile (unterste Zeile der Maske) und Kopfzeile (oberste Zeile),
  * Bodenkontakt: Pixelgruppen in den untersten 3 Zeilen; für jedes Folgebild-Paar im Gang wird die Gruppe
    gesucht, die in beiden Bildern liegt (aufstehender Fuß), und ihr Versatz links/rechts gemessen,
  * 24-fps-Raster: Anteil der Bilder, die dem Vorgängerbild pixelgleich sind (ganzes Bild, normale Aufnahme).
Ergebnis: assets/badger_measure.json
"""
import argparse, json, pathlib, subprocess, sys, tempfile
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent.parent
DEMO = HERE / "demo"
FPS, N = 30, 180
GROUND_Y = 322 * 1.8          # Bodenlinie in Bildpixeln
WALK_END = 12 * 5 / 24        # 11 Schritte + Schlussschritt
HOP = (5.30, 5.84)            # Freudenhüpfer: Füße verlassen den Boden


def render(out, *flags):
    subprocess.run(["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
                    "--write-movie", str(out / "f.png"), "--fixed-fps", str(FPS), "--quit-after", str(N), "--", *flags],
                   capture_output=True, text=True, check=False)
    return sorted(out.glob("f*.png"))


def runs(row):
    xs = np.flatnonzero(row)
    if xs.size == 0:
        return []
    out, start = [], xs[0]
    for a, b in zip(xs[:-1], xs[1:]):
        if b - a > 3:
            out.append((int(start), int(a)))
            start = b
    out.append((int(start), int(xs[-1])))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep")
    a = ap.parse_args()
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(a.keep) if a.keep else pathlib.Path(td)
        (td / "with").mkdir(parents=True, exist_ok=True)
        (td / "without").mkdir(exist_ok=True)
        (td / "plain").mkdir(exist_ok=True)
        fa = render(td / "with", "--probe-measure")
        fb = render(td / "without", "--probe-measure", "--probe-no-badger")
        fp = render(td / "plain")
        ffs = {}
        for key in ("near", "far"):
            (td / key).mkdir(exist_ok=True)
            ffs[key] = render(td / key, "--probe-measure", "--probe-feet=" + key)
        rows = []
        for i, (pa, pb) in enumerate(zip(fa, fb)):
            A = np.asarray(Image.open(pa).convert("RGB"), dtype=np.int16)
            B = np.asarray(Image.open(pb).convert("RGB"), dtype=np.int16)
            m = np.abs(A - B).max(axis=2) > 40
            m[int(GROUND_Y) + 6:, :] = False       # Leiste unten ausschließen
            ys = np.flatnonzero(m.sum(axis=1) >= 4)
            if ys.size == 0:
                rows.append({"frame": i, "t": round(i / FPS, 3), "empty": True})
                continue
            bot, top = int(ys[-1]), int(ys[0])
            contact = runs(m[bot - 2:bot + 1].any(axis=0))
            rows.append({"frame": i, "t": round(i / FPS, 3), "foot_row": bot, "head_row": top, "contact": contact})
        # aufstehender Fuß: Gruppe, die in zwei Folgebildern (fast) gleich liegt
        slips, pairs = [], 0
        for r0, r1 in zip(rows[:-1], rows[1:]):
            if r0.get("empty") or r1.get("empty") or r1["t"] > WALK_END + 0.05 or r0["t"] < 0.5:
                continue
            best = None
            for c0 in r0["contact"]:
                for c1 in r1["contact"]:
                    d = max(abs(c0[0] - c1[0]), abs(c0[1] - c1[1]))
                    if best is None or d < best[0]:
                        best = (d, c0, c1)
            if best is not None:
                pairs += 1
                slips.append({"frame": r1["frame"], "slip_px": best[0], "from": best[1], "to": best[2]})
        # Füße einzeln (eingefärbt): Lage je Bild, Versatz in Folgebildern, in denen der Fuß aufsteht
        feet = {"near": [], "far": []}
        lo = int(GROUND_Y) - 24
        for key in ("near", "far"):
            for i, p in enumerate(ffs[key]):
                F = np.asarray(Image.open(p).convert("RGB"), dtype=np.int16)[lo:int(GROUND_Y) + 6]
                R_, G_ = F[..., 0], F[..., 1]
                msk = ((R_ > 2 * G_ + 10) & (R_ > 50)) if key == "near" else ((G_ > 2 * R_ + 10) & (G_ > 50))
                ys, xs = np.nonzero(msk)
                if xs.size < 8:
                    feet[key].append(None)
                    continue
                feet[key].append({"bottom": int(ys.max()) + lo, "xmin": int(xs.min()), "xmax": int(xs.max()), "n": int(xs.size)})
        ground = max(f["bottom"] for k in feet for f in feet[k] if f)
        foot_stats, detail = {}, []
        for key in feet:
            slips, occl = [], 0
            for i in range(1, len(ffs[key])):
                a0, a1 = feet[key][i - 1], feet[key][i]
                if not a0 or not a1 or i / FPS > WALK_END + 0.05 or i / FPS < 0.5:
                    continue
                if a0["bottom"] >= ground - 1 and a1["bottom"] >= ground - 1:
                    d = max(abs(a0["xmin"] - a1["xmin"]), abs(a0["xmax"] - a1["xmax"]))
                    if abs(a0["n"] - a1["n"]) > 0.08 * a0["n"]:
                        occl += 1   # Fläche geändert: teilweise verdeckt (z. B. vom nahen Bein)
                    slips.append(d)
                    if d > 0:
                        detail.append({"foot": key, "frame": i, "d": d, "a0": a0, "a1": a1})
            foot_stats[key] = {"ground_pairs": len(slips), "slip_hist": {str(k): slips.count(k) for k in sorted(set(slips))},
                               "pairs_with_area_change": occl}
        walk_rows = [r for r in rows if not r.get("empty") and 0.5 <= r["t"] <= WALK_END]
        stand_rows = [r for r in rows if not r.get("empty") and r["t"] > WALK_END + 0.7 and not (HOP[0] <= r["t"] <= HOP[1] + 0.05)]
        hop_rows = [r for r in rows if not r.get("empty") and HOP[0] <= r["t"] <= HOP[1] + 0.05]
        # 24-fps-Raster in der normalen Aufnahme
        prev, dup = None, []
        for i, p in enumerate(fp):
            cur = np.asarray(Image.open(p).convert("RGB"))
            if prev is not None and np.array_equal(cur, prev):
                dup.append(i)
            prev = cur
        res = {
            "frames": len(rows),
            "feet_ground_row": ground,
            "feet_slip_walk": foot_stats,
            "feet_slip_nonzero": detail,
            "walk": {
                "frames": len(walk_rows),
                "foot_rows": sorted({r["foot_row"] for r in walk_rows}),
                "head_rows": [min(r["head_row"] for r in walk_rows), max(r["head_row"] for r in walk_rows)],
                "max_head_jump_px": max(abs(a["head_row"] - b["head_row"]) for a, b in zip(walk_rows[:-1], walk_rows[1:])),
            },
            "stand": {"frames": len(stand_rows), "foot_rows": sorted({r["foot_row"] for r in stand_rows}),
                      "head_rows": sorted({r["head_row"] for r in stand_rows})},
            "hop": {"frames": len(hop_rows), "foot_rows": [r["foot_row"] for r in hop_rows]},
            "anim_24fps": {"duplicate_frames": len(dup), "share": round(len(dup) / max(1, len(fp) - 1), 3),
                           "first": dup[:12]},
            "per_frame": [{k: r[k] for k in ("frame", "foot_row", "head_row") if k in r} for r in rows],
        }
        (HERE / "assets" / "badger_measure.json").write_text(json.dumps(res, indent=1))
        print(json.dumps({k: v for k, v in res.items() if k != "per_frame"}, indent=1))


if __name__ == "__main__":
    sys.exit(main())
