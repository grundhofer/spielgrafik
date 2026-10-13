#!/usr/bin/env python3
"""Misst den Dachs in der gerenderten Demo (Godot-Lauf mit --solo: nur der Dachs auf Schwarz, 640×360).

    .venv/bin/python styles/hibit-pixel/scripts/measure_badger.py [--seconds 6]

Je Aufnahmebild: Kopfoberkante, Kopfmitte (oberes Viertel), unterste Zeile und die Fußsegmente in den beiden
untersten Zeilen. Auswertung:
  * Laufen: Für jeden Bildwechsel des Sprites (alle 2 Aufnahmebilder) wird das Bodensegment gesucht, das im
    nächsten Bild an derselben Stelle liegt (Standfuß). Ausgabe: Versatz des Standfußes je Wechsel (Soll ±1 px).
  * Stehen: Fußzeilen und Bodensegmente aller Stehbilder müssen gleich sein; Kopf ohne Sprung.
"""
import argparse, json, pathlib, sys, tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import probe


def segs(row):
    idx = np.flatnonzero(row)
    if idx.size == 0:
        return []
    out, s, p = [], idx[0], idx[0]
    for i in idx[1:]:
        if i - p > 1:
            out.append((int(s), int(p))); s = i
        p = i
    out.append((int(s), int(p)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=6.0)
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as td:
        n, bad = probe.run(td, a.seconds, 30, "--solo", keep=True)
        pngs = sorted((pathlib.Path(td) / "all").glob("f*.png"))
        rows = []
        prev = None
        for i, p in enumerate(pngs):
            im = np.asarray(Image.open(p).convert("RGB")).astype(int)
            m = im.max(-1) > 0
            ys = np.flatnonzero(m.any(1))
            if ys.size == 0:
                rows.append(None); continue
            top, bot = int(ys[0]), int(ys[-1])
            h = bot - top + 1
            head = m[top:top + h // 4]
            hx = float(np.nonzero(head)[1].mean())
            key = im.tobytes()
            rows.append({"i": i, "top": top, "bot": bot, "head_x": round(hx, 2),
                         "ground": segs(m[bot]), "ground2": segs(m[bot - 1]), "changed": key != prev})
            prev = key
    # Wechsel des Sprites erkennen (Bild ändert sich) und Standfuß-Versatz messen
    changes = [r for r in rows if r and r["changed"]]
    walk_report = []
    for r0, r1 in zip(changes, changes[1:]):
        if r1["i"] - r0["i"] > 3:
            continue
        best = None
        for s0 in r0["ground"]:
            for s1 in r1["ground"]:
                d = max(abs(s0[0] - s1[0]), abs(s0[1] - s1[1]))
                if best is None or d < best[0]:
                    best = (d, s0, s1)
        walk_report.append({"from": r0["i"], "to": r1["i"], "head_dx": round(r1["head_x"] - r0["head_x"], 2),
                            "top": [r0["top"], r1["top"]], "stance_shift": best[0] if best else None,
                            "seg": [best[1], best[2]] if best else None})
    holds = [changes[k + 1]["i"] - changes[k]["i"] for k in range(len(changes) - 1)]
    print(f"{n} Bilder, Godot-Meldungen: {len(bad)}")
    print("Haltezeiten (Aufnahmebilder je Sprite-Bild):", holds)
    for w in walk_report:
        print(f"  {w['from']:3d}->{w['to']:3d}  Kopf dx {w['head_dx']:6.2f}  Kopfoberkante {w['top']}  "
              f"Standfuß-Versatz {w['stance_shift']}  {w['seg']}")
    bots = sorted({r["bot"] for r in rows if r})
    print("unterste Zeilen:", bots)
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps({"rows": rows, "walk": walk_report, "holds": holds}, indent=1))


if __name__ == "__main__":
    main()
