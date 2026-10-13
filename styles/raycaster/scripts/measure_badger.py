#!/usr/bin/env python3
"""Misst den Dachs im gerenderten Godot-Bild (Prüfung nach PIPELINE.md "Figuren und Animation").

Godot läuft mit "-- --measure": nur der Dachs, feste Kamera 1,6 m seitlich vom Laufweg in 0,5 m Höhe
(Figur etwa 100 px hoch, ein Texel etwa 3 px; Seitenansicht beim Laufen, danach Drehung zur Kamera,
Winken). Hintergrund = häufigster Wert je Pixel über alle Bilder.

Geprüft wird:
  * Standfuß beim Laufen: Der Dachs springt wie die Monster der Sektor-Shooter je Laufbild um einen
    festen Schritt (0,0918 m) vor. Zwischen zwei Laufbildern muss eine Bodenkontaktgruppe (unterste
    zwei Zeilen) an derselben Stelle bleiben (Abweichung der Gruppenmitte in px).
  * Bodenzeile in allen Bildern gleich; Kopfoberkante in den Steh- und Winkbildern.

    python3 scripts/measure_badger.py [--keep <ordner>]
"""
import argparse
import json
import pathlib
import subprocess
import tempfile

import numpy as np
from PIL import Image

ENTRY = pathlib.Path(__file__).resolve().parent.parent


def clusters(xs):
    xs = sorted(set(int(x) for x in xs))
    out, cur = [], [xs[0]]
    for x in xs[1:]:
        if x - cur[-1] <= 1:
            cur.append(x)
        else:
            out.append(cur)
            cur = [x]
    out.append(cur)
    return [(c[0], c[-1], (c[0] + c[-1]) / 2) for c in out]


def components(mask):
    """4-Nachbarschaft; -> Liste (ys, xs)."""
    seen = np.zeros_like(mask)
    out = []
    H, W = mask.shape
    for y, x in zip(*np.nonzero(mask)):
        if seen[y, x]:
            continue
        stack, ys, xs = [(y, x)], [], []
        seen[y, x] = True
        while stack:
            cy, cx = stack.pop()
            ys.append(cy)
            xs.append(cx)
            for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        out.append((ys, xs))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", default="")
    ap.add_argument("--render", default="", help="Ordner der Blender-Renderings (für die Knochenprobe)")
    a = ap.parse_args()
    td = pathlib.Path(a.keep) if a.keep else pathlib.Path(tempfile.mkdtemp(prefix="raycaster-measure-"))
    td.mkdir(parents=True, exist_ok=True)
    demo = ENTRY / "demo"
    subprocess.run(["godot", "--headless", "--path", str(demo), "--import"], capture_output=True)
    r = subprocess.run(["godot", "--path", str(demo), "--position", "20000,20000", "--write-movie",
                        str(td / "m.png"), "--fixed-fps", "30", "--quit-after", "180", "--", "--measure"],
                       capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    frames = sorted(td.glob("m*.png"))
    arr = np.stack([np.asarray(Image.open(f).convert("RGB")) for f in frames]).astype(np.int32)
    key = arr[..., 0] * 65536 + arr[..., 1] * 256 + arr[..., 2]
    # Hintergrund: häufigster Wert je Pixel
    bg = np.zeros(key.shape[1:], np.int64)
    for y in range(key.shape[1]):
        for x in range(key.shape[2]):
            v, c = np.unique(key[:, y, x], return_counts=True)
            bg[y, x] = v[c.argmax()]
    res = {"frames": len(frames), "godot_errors": errs[:5], "walk": [], "stand": []}
    lum = arr[..., 0] * 0.299 + arr[..., 1] * 0.587 + arr[..., 2] * 0.114
    for i in range(len(frames)):
        m = key[i] != bg
        m[168:] = False
        ys, xs = np.nonzero(m)
        if len(ys) == 0:
            continue
        bottom, top = int(ys.max()), int(ys.min())
        t = i / 30.0
        # Pfoten: dunkle Fellpixel im untersten Achtel der Figur, zusammenhängende Gruppen
        h = bottom - top + 1
        y0 = bottom - max(6, h // 8)
        paw = m & (lum[i] < 75)
        paw[:y0] = False
        comps = components(paw)
        feet = []
        for cy, cx in comps:
            if len(cy) < 6:
                continue
            cy, cx = np.array(cy), np.array(cx)
            low = cx[cy == cy.max()]          # Sohle: unterste Zeile der Pfote (Ferse = rechtes Ende,
            feet.append((int(low.min()), int(low.max()), int(cy.max())))   # Zehen = linkes, Lauf nach links)
        rec = {"frame": i, "t": round(t, 3), "bottom": bottom, "top": top, "height": h, "feet": feet}
        (res["walk"] if t < 3.0 else res["stand"]).append(rec)
    # Laufbilder ändern sich alle 3 Bilder: je Laufschritt das erste Bild nehmen
    steps = [w for w in res["walk"] if w["frame"] % 3 == 0]
    dev = []
    stance = []
    for k, (p, q) in enumerate(zip(steps, steps[1:])):
        if not p["feet"] or not q["feet"]:
            continue
        # ein Fuß steht, wenn Ferse ODER Zehenspitze seiner Sohle am selben Fleck bleibt (Abrollen)
        best = min(min(abs(a[0] - b[0]), abs(a[1] - b[1])) + abs(a[2] - b[2]) for a in p["feet"] for b in q["feet"])
        dev.append(best)
        if k % 2 == 0:            # A->B (linker Fuß steht) und C->D (rechter Fuß steht)
            stance.append(best)
    res["summary"] = {
        "messung": "Pfotengruppen (dunkles Fell im untersten Achtel der Figur), Sohle = unterste Zeile; je "
                   "Laufschritt die kleinste Verschiebung von Ferse oder Zehen (|dx| + |dy|, px) einer Sohle zum "
                   "nächsten Laufbild; Standphasen = Bildpaare A->B und C->D",
        "kamera": "1,6 m seitlich, 0,5 m hoch, Figur etwa 100 px hoch (ein Texel etwa 3 px)",
        "walk_steps": len(steps),
        "standphasen_abweichung_px": stance,
        "standphasen_abweichung_px_max": max(stance) if stance else None,
        "alle_schritte_abweichung_px": dev,
        "pfoten_je_schritt": [s["feet"] for s in steps],
        "bodenzeile_laufen": sorted({w["bottom"] for w in res["walk"]}),
        "bodenzeile_stehen_winken": sorted({w["bottom"] for w in res["stand"]}),
        "kopf_oben_stehen_winken": sorted({w["top"] for w in res["stand"]}),
        "hoehe_px_stehen": sorted({w["height"] for w in res["stand"]}),
    }
    # Gegenprobe in Weltkoordinaten aus den Knochen (blender/render_sprites.py schreibt die Fußgelenke je
    # Pose): Gelenk in Laufrichtung = Sprite-Vorschub (0,0918 m je Bild) + Gelenk im Modell
    meta_p = pathlib.Path(a.render) / "badger_meta.json" if a.render else None
    if meta_p and meta_p.exists():
        poses = {q["name"]: q for q in json.loads(meta_p.read_text())["poses"]}
        drift = {}
        for foot, (p0, p1) in (("foot.L", ("walk0", "walk1")), ("foot.R", ("walk2", "walk3"))):
            x0 = poses[p0]["ankle"][foot][0]
            x1 = poses[p1]["ankle"][foot][0] + 0.0918
            drift[foot] = round(x1 - x0, 4)
        res["summary"]["knochen_standfuss_drift_m"] = drift
    out = ENTRY / "scripts" / "measure_badger.json"
    out.write_text(json.dumps(res["summary"], indent=1))
    print(json.dumps(res["summary"], indent=1))
    if errs:
        print("Godot-Fehler:", errs[:3])


if __name__ == "__main__":
    main()
