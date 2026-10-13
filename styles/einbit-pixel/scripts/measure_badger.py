#!/usr/bin/env python3
"""Misst den Dachs in einer Aufnahme ohne Szene (Schalter --solo: nur der Dachs auf Magenta, ohne Palette).

Je Bild: Sohlenzeile (unterste schwarze Zeile), Läufe schwarzer Pixel in der Sohlenzeile (Füße am Boden),
Kopfoberkante und Lage des Auges (weißes Pixel im schwarzen Augenstreif). Für das Laufen wird je Bildwechsel
geprüft, ob ein Fuß am Boden liegen bleibt: Für jeden Fußlauf im Bild n wird der Lauf im Bild n+1 gesucht,
dessen Ferse bzw. Spitze am nächsten liegt; der kleinere Versatz ist der Rutsch des Standfußes.

    .venv/bin/python styles/einbit-pixel/scripts/measure_badger.py [--frames 180] [--out media/measure.json]
"""
import argparse, json, pathlib, subprocess, sys, tempfile

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]


def runs(row):
    r, s = [], None
    for x, v in enumerate(row):
        if v and s is None:
            s = x
        if not v and s is not None:
            r.append((s, x - 1))
            s = None
    if s is not None:
        r.append((s, len(row) - 1))
    return r


def analyse(img):
    a = np.asarray(img.convert("RGB")).astype(int)
    mag = (a[..., 0] > 200) & (a[..., 1] < 60) & (a[..., 2] > 200)
    fig = ~mag
    blk = fig & (a.sum(-1) < 300)
    if not blk.any():
        return None
    ys = np.where(blk.any(1))[0]
    sole = int(ys.max())
    feet = runs(blk[sole])
    top = int(np.where(fig.any(1))[0].min())
    # Auge: weißes Pixel mit vier schwarzen Nachbarn in den Kopfzeilen 9–12 unter der Mützenoberkante
    eye = None
    xs = np.where(fig[top:top + 16].any(0))[0]
    for y in range(top + 8, top + 13):
        for x in range(max(1, int(xs.min())), min(a.shape[1] - 1, int(xs.max()) + 1)):
            if fig[y, x] and not blk[y, x] and blk[y, x - 1] and blk[y, x + 1] and blk[y - 1, x] and blk[y + 1, x]:
                eye = [x, y]
    return {"sole": sole, "feet": feet, "top": top, "eye": eye, "xmin": int(np.where(fig.any(0))[0].min()),
            "xmax": int(np.where(fig.any(0))[0].max())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=180)
    ap.add_argument("--out", default=str(ROOT / "media" / "measure.json"))
    a = ap.parse_args()
    demo = ROOT / "demo"
    subprocess.run(["godot", "--headless", "--path", str(demo), "--import"], capture_output=True)
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["godot", "--path", str(demo), "--position", "20000,20000", "--write-movie",
                        str(pathlib.Path(td) / "f.png"), "--fixed-fps", "30", "--quit-after", str(a.frames),
                        "--", "--solo"], capture_output=True)
        frames = sorted(pathlib.Path(td).glob("f*.png"))
        data = [analyse(Image.open(f)) for f in frames]
    # Laufbilder wechseln alle 2 Aufnahmebilder (15 Bilder/s): Wechsel n -> n+2 prüfen
    slips = []
    for n in range(0, len(data) - 2):
        d0, d1 = data[n], data[n + 1]
        if d0 is None or d1 is None or d0["feet"] == d1["feet"]:
            continue
        # Standfuß = Paar mit der größten Überdeckung; Rutsch = kleinerer Versatz von Ferse bzw. Spitze
        best = None
        for f0 in d0["feet"]:
            for f1 in d1["feet"]:
                ov = min(f0[1], f1[1]) - max(f0[0], f1[0]) + 1
                if best is None or ov > best[0]:
                    best = (ov, f0, f1)
        ov, f0, f1 = best
        slip = min(abs(f1[0] - f0[0]), abs(f1[1] - f0[1])) if ov > 0 else None
        slips.append({"frame": n + 1, "slip": slip, "toe": f1[1] - f0[1], "heel": f1[0] - f0[0],
                      "from": f0, "to": f1})
    soles = sorted({d["sole"] for d in data if d})
    tops = sorted({d["top"] for d in data if d})
    eyes = [d["eye"] for d in data if d]
    known = [s_["slip"] for s_ in slips if s_["slip"] is not None]
    out = {"frames": len(data), "sole_rows": soles, "top_rows": tops, "slips": slips,
           "max_slip": max(known) if known else None,
           "no_overlap": [s_["frame"] for s_ in slips if s_["slip"] is None], "per_frame": data}
    pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(a.out).write_text(json.dumps(out, indent=1))
    print("Sohlenzeilen", soles, "Kopfoberkanten", tops)
    print("Rutschen je Bildwechsel (Bild, Rutsch, Spitze, Ferse):", [(s["frame"], s["slip"], s["toe"], s["heel"]) for s in slips])
    print("größter Rutsch", out["max_slip"], "Wechsel ohne gemeinsamen Fuß", out["no_overlap"])
    # Auge relativ zum Fußpunkt der Figur (Kopf ist ein festes Teil: Abstand nur durch Wippen)
    rel = sorted({(e[1] - d["sole"]) for d, e in zip([d for d in data if d], eyes) if e})
    out["eye_rows_rel_sole"] = rel
    out["eye_found"] = sum(1 for e in eyes if e)
    pathlib.Path(a.out).write_text(json.dumps(out, indent=1))
    print("Auge gefunden in", out["eye_found"], "von", len(eyes), "Bildern; Augenzeile über der Sohle", rel)


if __name__ == "__main__":
    main()
