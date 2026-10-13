#!/usr/bin/env python3
"""Misst den Dachs in der Godot-Aufnahme: nur die Figur auf Schwarz (--measure), 180 Bilder.

    .venv/bin/python styles/sprite-skalierung/scripts/measure_badger.py <tmpdir>

Je Bild: Kopfoberkante, Fußzeile (unterste Zeile), unterste Zeile des linken und rechten Fußes, Kopfmitte x
(oberstes Viertel). Erwartung: Fußzeile in jedem Bild gleich, Kopfoberkante je Laufbild gleich, Kopfmitte
verschiebt sich nur um die Neigung (Zeilenversatz). Schreibt assets/measure_badger.json.
"""
import json, pathlib, subprocess, sys

import numpy as np
from PIL import Image

SD = pathlib.Path(__file__).resolve().parents[1]


def main():
    td = pathlib.Path(sys.argv[1])
    td.mkdir(parents=True, exist_ok=True)
    for p in td.glob("m*.png"):
        p.unlink()
    dump = td / "measure.jsonl"
    subprocess.run(["godot", "--headless", "--path", str(SD / "demo"), "--import"], capture_output=True)
    r = subprocess.run(["godot", "--path", str(SD / "demo"), "--position", "20000,20000", "--write-movie",
                        str(td / "m.png"), "--fixed-fps", "30", "--quit-after", "180", "--", "--measure",
                        f"--dump={dump}"], capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    frames = sorted(td.glob("m*.png"))
    states = [json.loads(l) for l in dump.read_text().splitlines()]
    rows = []
    for i, f in enumerate(frames):
        a = np.asarray(Image.open(f).convert("RGB")).astype(int)
        m = a.sum(-1) > 0
        ys, xs = np.nonzero(m)
        top, bot = int(ys.min()), int(ys.max())
        h = bot - top + 1
        q = m[top:top + h // 4]
        qy, qx = np.nonzero(q)
        head_cx = float(qx.mean())
        mid = int(round(head_cx))
        low = m[bot - 13:bot + 1]
        lb = [bot - 13 + int(np.nonzero(low[:, :mid].any(1))[0].max()) if low[:, :mid].any() else -1,
              bot - 13 + int(np.nonzero(low[:, mid:].any(1))[0].max()) if low[:, mid:].any() else -1]
        # Zustand aus dem Dump: Movie Maker schreibt ein Bild nach jedem _process; Zeile 0 ist _ready
        st = states[i + 1] if i + 1 < len(states) else states[-1]
        rows.append({"i": i, "t": st["t"], "frame": st["frame"], "lean": st["lean"], "top": top, "feet": bot,
                     "foot_l": lb[0], "foot_r": lb[1], "head_cx": round(head_cx, 2)})
    res = {"frames": len(rows), "godot_errors": errs[:5]}
    res["feet_rows"] = sorted({r["feet"] for r in rows})
    by = {}
    for r in rows:
        by.setdefault(r["frame"], []).append(r)
    res["per_walk_frame"] = {}
    for k, rs in sorted(by.items()):
        base = [r for r in rs if r["lean"] == 0] or rs
        res["per_walk_frame"][str(k)] = {
            "count": len(rs),
            "top_rows": sorted({r["top"] for r in rs}),
            "foot_l_rows": sorted({r["foot_l"] for r in rs}),
            "foot_r_rows": sorted({r["foot_r"] for r in rs}),
            "head_cx_at_lean0": sorted({r["head_cx"] for r in base}),
        }
    # Neigung: Kopfmitte gegen Neigung (alle Laufbilder zusammen, relativ zum Wert bei Neigung 0)
    lean_fit = {}
    for k, rs in by.items():
        z = [r["head_cx"] for r in rs if r["lean"] == 0]
        if not z:
            continue
        for r in rs:
            lean_fit.setdefault(str(int(r["lean"])), []).append(round(r["head_cx"] - z[0], 2))
    res["head_shift_by_lean"] = {k: [min(v), max(v)] for k, v in sorted(lean_fit.items(), key=lambda x: int(x[0]))}
    # Wechsel des Laufbilds nur alle 3 Aufnahmebilder (10 Bilder/s)
    changes = [i for i in range(1, len(rows)) if rows[i]["frame"] != rows[i - 1]["frame"]]
    res["walk_frame_holds"] = sorted({b - a for a, b in zip(changes, changes[1:])})
    res["rows"] = rows
    out = SD / "assets" / "measure_badger.json"
    out.write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    main()
