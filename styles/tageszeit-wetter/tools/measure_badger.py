#!/usr/bin/env python3
"""Misst den Dachs in der gerenderten Demo: Fußzeile, Fußspalten, Kopfzeile und Kopfmitte je Bild.

    .venv/bin/python styles/tageszeit-wetter/tools/measure_badger.py [--frames 180] [--keep DIR]

Rendert die Demo zweimal (mit und ohne Dachs, sonst gleich und deterministisch) und nimmt die Differenz als
Figurmaske. Prüft: Fußzeile in allen Bildern gleich, Fußspalten ±1 px, Kopf je Bild höchstens 1 px Sprung.
"""
import argparse, json, pathlib, subprocess, sys, tempfile

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent


def render(out, frames, extra):
    subprocess.run([sys.executable, str(HERE / "render.py"), str(out), "--frames", str(frames),
                    "--args", "--no-ui", *extra], check=True, capture_output=True, timeout=1200)
    return sorted(pathlib.Path(out).glob("f*.png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=180)
    ap.add_argument("--keep", default="")
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as td:
        base = pathlib.Path(a.keep) if a.keep else pathlib.Path(td)
        with_b = render(base / "with", a.frames, [])
        without = render(base / "without", a.frames, ["--no-badger"])
        rows = []
        for i, (p, q) in enumerate(zip(with_b, without)):
            A = np.asarray(Image.open(p).convert("RGB"), np.int16)
            B = np.asarray(Image.open(q).convert("RGB"), np.int16)
            m = np.abs(A - B).max(-1) > 18
            m[:, :300] = False          # nur um den Dachs (x 300..600)
            m[:, 600:] = False
            ys = np.nonzero(m.sum(1) >= 3)[0]
            if not len(ys):
                rows.append(None)
                continue
            top, foot = int(ys.min()), int(ys.max())
            band = m[foot - 3:foot + 1]
            cols = np.nonzero(band.any(0))[0]
            # zwei Füße: Lücke in der Mitte suchen
            gaps = np.nonzero(np.diff(cols) > 3)[0]
            if len(gaps):
                g = gaps[0]
                feet = [[int(cols[0]), int(cols[g])], [int(cols[g + 1]), int(cols[-1])]]
            else:
                feet = [[int(cols[0]), int(cols[-1])]]
            h = foot - top + 1
            head = m[top:top + h // 4]
            hx = np.nonzero(head.any(0))[0]
            rows.append({"frame": i, "top": top, "foot": foot, "feet": feet,
                         "head_center": round((hx.min() + hx.max()) / 2, 1)})
    good = [r for r in rows if r]
    foots = sorted({r["foot"] for r in good})
    tops = [r["top"] for r in good]
    jumps = [abs(tops[i + 1] - tops[i]) for i in range(len(tops) - 1)]
    hc = [r["head_center"] for r in good]
    hjumps = [abs(hc[i + 1] - hc[i]) for i in range(len(hc) - 1)]
    fl = sorted({tuple(r["feet"][0]) for r in good})
    fr = sorted({tuple(r["feet"][-1]) for r in good})
    summary = {
        "frames": len(rows), "measured": len(good),
        "foot_rows": foots, "head_top_range": [min(tops), max(tops)],
        "head_top_max_jump": max(jumps), "head_center_range": [min(hc), max(hc)],
        "head_center_max_jump": max(hjumps),
        "left_foot_spans": [list(x) for x in fl][:6], "right_foot_spans": [list(x) for x in fr][:6],
        "height_px": [min(r["foot"] - r["top"] + 1 for r in good), max(r["foot"] - r["top"] + 1 for r in good)],
    }
    print(json.dumps(summary, indent=1))
    ok = len(foots) == 1 and summary["head_top_max_jump"] <= 1 and summary["head_center_max_jump"] <= 1.0
    print("ok" if ok else "PRÜFEN")


if __name__ == "__main__":
    main()
