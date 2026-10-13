#!/usr/bin/env python3
"""Füße und Kopf des Dachses in den gerenderten Bildern messen.

    .venv/bin/python styles/pixel-3d/scripts/probe.py MASK -- --mask --measure
    .venv/bin/python styles/pixel-3d/scripts/measure_feet.py MASK

--mask rendert den Dachs weiß, alles andere schwarz (Renderbilder dump/r*.png, 428×242, mit derselben
Kamerafahrt wie die Aufnahme); --measure schreibt je Bild Pan und die Bildlage der Fußknochen ins Protokoll.
Alle x-Werte werden auf den Bildinhalt bezogen (Renderspalte + ganzzahliger Pan), damit die Kamerafahrt
herausfällt: Ein Fuß, der auf dem Kai steht, muss dann auf derselben Spalte bleiben.

1. Laufen (bis 3,2 s): In den untersten 3 Zeilen der Silhouette werden die Pixel in zwei Gruppen geteilt
   (Lücke in x) und dem nächstgelegenen Fußknochen zugeordnet. Der Standfuß ist der Fuß, dessen Knochen
   flach am Boden liegt (Knöchel unter 8,5 cm und Zehenende unter 4,5 cm über dem Kai; in Ruhe 7,7 bzw.
   3,5 cm). Gemessen wird seine hintere Kante (kleinstes x) über alle Bilder einer
   Standphase: Spannweite in Pixeln.
2. Stehen, Drehen, Winken (ab 3,3 s): unterste Zeile der Silhouette in allen Bildern (soll gleich bleiben)
   und oberste Zeile (Kopf, Mütze).
"""
import json
import pathlib
import sys

import numpy as np
from PIL import Image


def main():
    run = pathlib.Path(sys.argv[1])
    meas = {}
    for line in (run / "godot.log").read_text().splitlines():
        if line.startswith("MEASURE "):
            d = json.loads(line[8:])
            meas[d["frame"]] = d
    rows = []
    for f in sorted(meas):
        p = run / "dump" / f"r{f:04d}.png"
        if not p.exists():
            continue
        m = np.asarray(Image.open(p).convert("L")) > 128
        ys, xs = np.nonzero(m)
        if len(ys) == 0:
            continue
        d = meas[f]
        ip = int(np.floor(d["pan"]))
        y_max, y_min = ys.max(), ys.min()
        low = ys >= y_max - 2
        lx = np.sort(np.unique(xs[low]))
        # Gruppen trennen, wo in x eine Lücke von mehr als 1 Pixel ist
        groups = np.split(lx, np.where(np.diff(lx) > 1)[0] + 1)
        rows.append({"frame": f, "t": d["t"], "ip": ip, "y_max": int(y_max), "y_min": int(y_min),
                     "groups": [(int(g.min()) + ip, int(g.max()) + ip) for g in groups],
                     "L": d["foot.L.heel"], "R": d["foot.R.heel"],
                     "Ltoe": d["foot.L.toe"], "Rtoe": d["foot.R.toe"], "mask": m})

    # 1. Laufen: Standphasen. Je Bild das Fenster um den Standfuß (Knochen von Knöchel bis Zehenende,
    # ±4 px, Zeilen um das Zehenende) in der Maske; hintere Kante = kleinstes x darin. Steht der ferne
    # Fuß (L, 25 cm hinter dem nahen), kann der schwingende nahe Fuß (R) davor vorbeiziehen: Bilder, in
    # denen der nahe Fuß im Fenster liegt, zählen als verdeckt und werden nicht gewertet.
    print("Laufen: Standfuß (Fußknochen flach am Boden), hintere Kante im Fenster um den Fuß")
    phases = []
    cur = None
    for r in rows:
        if r["t"] > 3.2:
            break
        planted = None
        for side in ("L", "R"):
            if r[side][3] < 0.085 and r[side + "toe"][3] < 0.045:
                planted = side if planted is None or r[side][3] < r[planted][3] else planted
        if planted is None:
            cur = None
            continue
        if cur is None or cur["side"] != planted:
            cur = {"side": planted, "frames": [], "back": [], "bone_x": [], "hidden": 0}
            phases.append(cur)
        off = 1.0 / 3.0 + r["ip"]          # sichtbare Koordinate -> Bildinhalt (Renderspalte + Pan)
        hx, tx = r[planted][0] + off, r[planted + "toe"][0] + off
        x0, x1 = int(np.floor(min(hx, tx))) - 4, int(np.ceil(max(hx, tx))) + 4
        ty = int(round(r[planted + "toe"][1] + 1.0))
        other = "R" if planted == "L" else "L"
        ox = [r[other][0] + off, r[other + "toe"][0] + off]
        if planted == "L" and any(x0 - 3 <= v <= x1 + 3 for v in ox):
            cur["hidden"] += 1
            continue
        m = r["mask"]
        win = m[max(ty - 2, 0):ty + 3, max(x0 - r["ip"], 0):max(x1 - r["ip"], 0)]
        ys, xs = np.nonzero(win)
        if len(xs) == 0:
            cur["hidden"] += 1
            continue
        cur["frames"].append(r["frame"])
        cur["back"].append(int(xs.min()) + max(x0 - r["ip"], 0) + r["ip"])
        cur["bone_x"].append(r[planted][2])
    spans = []
    for ph in phases:
        if len(ph["frames"]) < 2:
            print(f"  Fuß {ph['side']}: {len(ph['frames'])} sichtbare Bilder, {ph['hidden']} verdeckt")
            continue
        span = max(ph["back"]) - min(ph["back"])
        wspan = (max(ph["bone_x"]) - min(ph["bone_x"])) * 1000
        spans.append(span)
        print(f"  Fuß {ph['side']} Bilder {ph['frames'][0]}–{ph['frames'][-1]} ({len(ph['frames'])} sichtbar, "
              f"{ph['hidden']} verdeckt): Kante {min(ph['back'])}..{max(ph['back'])} -> Spanne {span} px; "
              f"Knochen in der Welt {wspan:.1f} mm")
    if spans:
        print(f"  größte Spanne: {max(spans)} px in {len(spans)} Standphasen")

    # 2. Stehen
    st = [r for r in rows if r["t"] >= 3.3]
    if st:
        ym = sorted({r["y_max"] for r in st})
        yn = [r["y_min"] for r in st]
        print(f"Stehen/Drehen/Winken ({len(st)} Bilder ab 3,3 s): unterste Zeile {ym}, oberste Zeile {min(yn)}..{max(yn)}")
        hb = [r["y_max"] - r["y_min"] + 1 for r in st]
        print(f"  Höhe der Silhouette {min(hb)}..{max(hb)} px")
    allh = [r["y_max"] - r["y_min"] + 1 for r in rows if r["t"] <= 3.2]
    if allh:
        print(f"Laufen: Höhe der Silhouette {min(allh)}..{max(allh)} px, unterste Zeile "
              f"{min(r['y_max'] for r in rows if r['t'] <= 3.2)}..{max(r['y_max'] for r in rows if r['t'] <= 3.2)}")


if __name__ == "__main__":
    main()
