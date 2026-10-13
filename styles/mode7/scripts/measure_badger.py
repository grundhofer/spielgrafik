"""Misst den Dachs in der gerenderten Godot-Aufnahme (PIPELINE.md: Figuren und Animation).

Aufruf: .venv/bin/python styles/mode7/scripts/measure_badger.py [--out <tmp>]

Startet die Demo mit "-- --measure": Kamera fest in der Endstellung, nur der Dachs auf Schwarz (alle anderen
Ebenen und Sprites aus), 180 Bilder bei 30 fps. Je Bild: Kopfoberkante, Bodenzeile (unterste deckende Zeile),
Fußgruppen in den untersten 5 Zeilen. Standfuß: In Phasen mit gleicher unterster Zeile steht derselbe Fuß;
seine vordere Kante (Zehen) in der untersten Zeile soll über alle Laufbilder der Phase stehen bleiben (±1 px).
"""
import argparse
import json
import pathlib
import subprocess
import tempfile

import numpy as np
from PIL import Image

STYLE = pathlib.Path(__file__).resolve().parent.parent


def runs(row):
    xs = np.nonzero(row)[0]
    if len(xs) == 0:
        return []
    out, start, prev = [], xs[0], xs[0]
    for x in xs[1:]:
        if x != prev + 1:
            out.append((start, prev))
            start = x
        prev = x
    out.append((start, prev))
    return out


def blobs(band):
    """Zusammenhängende Gruppen (8er-Nachbarschaft) im Fußband -> [x0, x1, unterste Zeile im Band]."""
    h, w = band.shape
    seen = np.zeros_like(band, bool)
    out = []
    for y0 in range(h):
        for x0 in range(w):
            if band[y0, x0] and not seen[y0, x0]:
                stack, pts = [(y0, x0)], []
                seen[y0, x0] = True
                while stack:
                    y, x = stack.pop()
                    pts.append((y, x))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            yy, xx = y + dy, x + dx
                            if 0 <= yy < h and 0 <= xx < w and band[yy, xx] and not seen[yy, xx]:
                                seen[yy, xx] = True
                                stack.append((yy, xx))
                xs = [p[1] for p in pts]
                out.append((min(xs), max(xs), max(p[0] for p in pts)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    tmp = pathlib.Path(a.out or tempfile.mkdtemp(prefix="mode7_measure_"))
    tmp.mkdir(parents=True, exist_ok=True)
    for p in tmp.glob("f*.png"):
        p.unlink()
    demo = STYLE / "demo"
    subprocess.run(["godot", "--headless", "--path", str(demo), "--import"], capture_output=True)
    dump = tmp / "dump.jsonl"
    r = subprocess.run(["godot", "--path", str(demo), "--position", "20000,20000", "--write-movie",
                        str(tmp / "f.png"), "--fixed-fps", "30", "--quit-after", "180", "--",
                        "--measure", f"--dump={dump}"], capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    frames = sorted(tmp.glob("f*.png"))
    log = [json.loads(l) for l in dump.read_text().splitlines()]
    rows = []
    for k, p in enumerate(frames):
        im = np.asarray(Image.open(p).convert("RGB")).astype(int)
        m = im.sum(axis=2) > 0
        ys, xs = np.nonzero(m)
        if len(ys) == 0:
            continue
        top, bot = int(ys.min()), int(ys.max())
        feet = blobs(m[bot - 4:bot + 1])
        sheet = log[k + 1]["oam"][0][0] if k + 1 < len(log) and log[k + 1]["oam"] else "?"
        rows.append(dict(frame=k, sheet=sheet, top=top, bottom=bot, feet=[list(map(int, f)) for f in feet],
                         height=bot - top + 1))
    # Standfuß: Im Höhenwinkel von 18° liegt die Sohle des nahen Fußes tiefer als die des fernen. Phasen mit
    # gleicher unterster Zeile = derselbe Fuß steht. Gemessen wird die vordere Kante (Zehen) der untersten
    # Pixelgruppe in der untersten Zeile; innerhalb einer Phase soll sie stehen bleiben (±1 px).
    walk = [r for r in rows if r["sheet"] == "badger_walk"]
    for r in walk:
        im = np.asarray(Image.open(frames[r["frame"]]).convert("RGB")).astype(int).sum(axis=2) > 0
        rr = runs(im[r["bottom"]])
        r["toe"] = int(max(x1 for _, x1 in rr))
    phases, cur = [], [walk[0]]
    for r in walk[1:]:
        if r["bottom"] == cur[-1]["bottom"]:
            cur.append(r)
        else:
            phases.append(cur)
            cur = [r]
    phases.append(cur)
    drift = []
    for ph in phases:
        toes = [r["toe"] for r in ph]
        n_img = len(set((r["toe"], r["top"], tuple(map(tuple, r["feet"]))) for r in ph))
        if n_img >= 2:          # nur Phasen über mindestens 2 verschiedene Laufbilder
            drift.append(max(toes) - min(toes))
    stand = [r for r in rows if r["sheet"] in ("badger_idle", "badger_wave", "badger_turn")]
    contact = [r["bottom"] for r in walk]
    res = {
        "frames": len(rows), "godot_errors": errs[:5],
        "walk_frames": len(walk),
        "stance_phases": len(drift),
        "stance_drift_px_max": max(drift) if drift else None,
        "stance_drift_hist": {str(v): drift.count(v) for v in sorted(set(drift))},
        "walk_bottom_rows": sorted(set(contact)),
        "walk_top_rows": sorted(set(r["top"] for r in walk)),
        "stand_bottom_rows": sorted(set(r["bottom"] for r in stand)),
        "stand_top_rows": sorted(set(r["top"] for r in stand)),
        "height_px": sorted(set(r["height"] for r in rows)),
    }
    print(json.dumps(res, indent=1))
    (STYLE / "assets/measure_badger.json").write_text(json.dumps(dict(res, rows=rows), indent=1))


if __name__ == "__main__":
    main()
