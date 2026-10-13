#!/usr/bin/env python3
"""Misst die Schärfe der Figur in jedem Bild der Aufnahme (pumpt sie mit Atmen und Gewichtsverlagerung?).

    .venv/bin/python styles/fotoreal-standbild/tools/measure_sharp.py <Arbeitsordner> [--frames 180] [--skip 51 111]
        [-- --look=0 ...]

Rendert zweimal (mit und ohne Dachs, ohne Oberfläche, Korn und Schatten); der Unterschied ist die Figur. Je Bild:
  gesicht_laplace  Standardabweichung des Laplace-Filters (4er-Nachbarschaft) der Helligkeit im Gesicht (oberste 50
                   Zeilen der Figur, 3 px vom Rand entfernt)
  figur_detail     Verhältnis feinster Details (Bandpass 1 px) zu mittleren (1-3 px) im Inneren der ganzen Figur, wie
                   measure_match.py (gleiche Werte wie das Foto = gleich scharf)
Gibt Minimum, Maximum und Mittel aus (alle Bilder, mit --skip zusätzlich ohne die genannten Bilder) und schreibt
sharp.json. Mit "-- --look=0" bleibt der Kopf vorn: dann misst es nur das Pumpen durch Atmen und Gewicht.
"""
import argparse, json, pathlib, sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from render import render  # noqa: E402
from prep_actor import gauss  # noqa: E402


def laplace_std(L, m):
    lap = -4 * L[1:-1, 1:-1] + L[:-2, 1:-1] + L[2:, 1:-1] + L[1:-1, :-2] + L[1:-1, 2:]
    return float(lap[m[1:-1, 1:-1]].std())


def detail_ratio(L, m):
    g1, g3 = gauss(L, 1.0), gauss(L, 3.0)
    return float((L - g1)[m].std() / max((g1 - g3)[m].std(), 1e-6))


def main():
    argv = sys.argv[1:]
    user = []
    if "--" in argv:
        i = argv.index("--")
        argv, user = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--frames", type=int, default=180)
    ap.add_argument("--skip", type=int, nargs="*", default=[], help="Bilder, die nur zusätzlich ausgelassen werden "
                    "(z. B. die Zwischenbilder der Kopfdrehung)")
    a = ap.parse_args(argv)
    work = pathlib.Path(a.work)
    common = ["--no-ui", "--no-grain", "--no-shadow"] + user
    w = render(work / "with", a.frames, None, common, quiet=True)
    wo = render(work / "without", a.frames, None, common + ["--no-actor"], quiet=True)
    rows = []
    for i, (p, q) in enumerate(zip(w, wo)):
        A = np.asarray(Image.open(p).convert("RGB"), np.float32)
        B = np.asarray(Image.open(q).convert("RGB"), np.float32)
        m = np.abs(A - B).max(-1) > 18
        inner = gauss(m.astype(np.float32), 1.5) > 0.98
        ys = np.nonzero(m.any(1))[0]
        top = int(ys.min())
        face = inner.copy()
        face[:top] = False
        face[top + 50:] = False
        L = A.mean(-1)
        rows.append({"frame": i, "gesicht_laplace": round(laplace_std(L, face), 2),
                     "figur_detail": round(detail_ratio(L, inner), 3), "top_y": top})

    def stats(sel, k):
        v = [r[k] for r in sel]
        return {"min": min(v), "max": max(v), "mittel": round(float(np.mean(v)), 3),
                "bild_min": sel[int(np.argmin(v))]["frame"], "bild_max": sel[int(np.argmax(v))]["frame"]}

    summary = {k: stats(rows, k) for k in ("gesicht_laplace", "figur_detail")}
    if a.skip:
        rest = [r for r in rows if r["frame"] not in a.skip]
        for k in ("gesicht_laplace", "figur_detail"):
            summary[k + "_ohne_" + "_".join(map(str, a.skip))] = stats(rest, k)
    print(json.dumps(summary, ensure_ascii=False))
    (work / "sharp.json").write_text(json.dumps({"summary": summary, "frames": rows}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
