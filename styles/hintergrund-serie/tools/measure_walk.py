#!/usr/bin/env python3
"""Misst den Dachs in der laufenden Godot-Demo (nicht im Blatt): Fußlinie, Standfuß, Kopf.

Aufruf aus dem Projektordner:
    .venv/bin/python styles/hintergrund-serie/tools/measure_walk.py [--out DIR]

Startet die Demo im Prüfmodus (`-- --badger-only`: nur der Dachs vor Magenta, ohne LUT, Schatten und Textbox),
nimmt die ersten 2,0 s (bis zum ersten Szenenwechsel) mit 30 fps auf und misst je Bild:
  - Fußlinie (unterste deckende Zeile): muss in allen Bildern gleich sein (±1 px)
  - Standfuß: bei jedem Bildwechsel wird das Fußband (unterste Zeilen der Figur) des neuen Bildes gegen das alte
    verschoben, bis es am besten deckt. Bleibt der Standfuß stehen, liegt die beste Verschiebung bei 0 px
    (Grenze ±1 px). Verglichen wird im Bildschirm, also mit dem tatsächlichen Vorschub aus walk.json.
  - Kopf-x (Mitte des oberen Viertels): Vorschub je Bildwechsel, keine Sprünge rückwärts
Ergebnis: <out>/walk_measure.json (Standard assets/) und eine Zusammenfassung auf der Konsole.
Mit Platzhaltern in demo/art (siehe demo/art/placeholders.json) --out in einen Temp-Ordner legen.
"""
import argparse, json, pathlib, subprocess, sys, tempfile

import numpy as np
from PIL import Image

SD = pathlib.Path(__file__).resolve().parent.parent
DEMO = SD / "demo"
FPS, SECS = 30, 2.0


def best_shift(a, b, smax=20):
    """Verschiebung s, bei der b[x] = a[x + s] am besten deckt (bool-Bänder gleicher Größe). Alle s, die mindestens
    98 % der besten Deckung erreichen, gelten als gleich gut; genommen wird davon das betragsmäßig kleinste (bleibt
    der Fuß stehen, ist das 0). Zweiter Wert: Deckung bei s = 0 relativ zur besten."""
    w = a.shape[1]
    shifts = list(range(-smax, smax + 1))
    score = []
    for s in shifts:
        if s >= 0:
            score.append(int((a[:, s:] & b[:, :w - s]).sum()))
        else:
            score.append(int((a[:, :w + s] & b[:, -s:]).sum()))
    score = np.array(score, np.float64)
    top = score.max()
    good = [s for s, v in zip(shifts, score) if v >= 0.98 * top]
    zero = score[smax] / max(1.0, top)
    return min(good, key=abs), float(zero)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(SD / "assets"))
    a = ap.parse_args()
    out_dir = pathlib.Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        out = pathlib.Path(td) / "f.png"
        r = subprocess.run(["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
                            "--write-movie", str(out), "--fixed-fps", str(FPS), "--quit-after", str(int(FPS * SECS)),
                            "--", "--badger-only"], capture_output=True, text=True, timeout=300)
        errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
        if errs:
            print("\n".join(errs[:10]))
        frames = sorted(pathlib.Path(td).glob("f*.png"))[:int(FPS * SECS)]
        masks, rows = [], []
        for i, f in enumerate(frames):
            px = np.asarray(Image.open(f).convert("RGB"), np.int16)
            key = (px[..., 0] > 200) & (px[..., 1] < 60) & (px[..., 2] > 200)
            m = ~key
            masks.append(m)
            ys, xs = np.nonzero(m)
            if len(ys) == 0:
                rows.append({"frame": i, "t": round(i / FPS, 3), "visible": False})
                continue
            top, bot = int(ys.min()), int(ys.max())
            h = bot - top + 1
            head = m[top:top + max(1, h // 4)]
            rows.append({"frame": i, "t": round(i / FPS, 3), "visible": True, "top": top, "bottom": bot,
                         "left": int(xs.min()), "right": int(xs.max()),
                         "head_x": round(float(np.nonzero(head)[1].mean()), 1)})
    vis = [r for r in rows if r["visible"]]
    if not vis:
        print("Dachs nicht sichtbar")
        return 1
    bottoms = sorted({r["bottom"] for r in vis})
    feet_y = int(np.median([r["bottom"] for r in vis]))
    height = int(np.median([r["bottom"] - r["top"] + 1 for r in vis]))
    band = max(4, round(height * 0.04))
    changes = []
    for a_, b_ in zip(vis, vis[1:]):
        ma, mb = masks[a_["frame"]], masks[b_["frame"]]
        ba = ma[feet_y - band + 1:feet_y + 1]
        bb = mb[feet_y - band + 1:feet_y + 1]
        if (ba == bb).all() and abs(b_["head_x"] - a_["head_x"]) < 0.5:
            continue  # kein Bildwechsel (Atmen ändert nur den Kopf um Bruchteile)
        s, zero = best_shift(ba, bb)
        changes.append({"t": b_["t"], "frame": b_["frame"], "stance_shift_px": s, "overlap_at_0": round(zero, 2),
                        "head_dx": round(b_["head_x"] - a_["head_x"], 1), "bottom": b_["bottom"]})
    walk = [c for c in changes if abs(c["head_dx"]) >= 0.5]
    shifts = [abs(c["stance_shift_px"]) for c in walk]
    summary = {
        "frames_visible": len(vis), "frame_changes": len(walk), "figure_height_px": height,
        "foot_band_rows": band, "bottom_rows": bottoms,
        "bottom_ok": bottoms[-1] - bottoms[0] <= 1,
        "stance_shift_max_px": max(shifts) if shifts else None,
        "stance_shift_mean_px": round(float(np.mean(shifts)), 2) if shifts else None,
        "stance_shift_le_1px_share": round(float(np.mean([s <= 1.0 for s in shifts])), 2) if shifts else None,
        "head_dx": [c["head_dx"] for c in walk],
        "backward_steps": sum(c["head_dx"] < -0.5 for c in walk),
    }
    path = out_dir / "walk_measure.json"
    path.write_text(json.dumps({"summary": summary, "changes": changes, "frames": rows}, indent=1) + "\n")
    print(json.dumps(summary, indent=1))
    for c in walk:
        print(c)
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
