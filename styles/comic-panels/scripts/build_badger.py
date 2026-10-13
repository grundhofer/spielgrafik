#!/usr/bin/env python3
"""Zerlegt den KI-Laufbogen (assets/raw/walk.png, Layout aus assets/ref/layout.json) in Einzelbilder für die Demo,
misst den Vorschub je Bildwechsel am Standfuß und schreibt das Blatt für Godot.

    .venv/bin/python styles/comic-panels/scripts/build_badger.py

Ergebnis:
  assets/badger.png    10 Bilder nebeneinander (walk_0 … walk_7, stand, turn), je 122×184, RGBA (nicht vormultipliziert):
                       Farbflächen ohne Tusche (inkcolor.py), Alpha = Figur
  assets/badger_ink.png dasselbe Raster: Tusche (schwarz, Alpha = Deckung)
  assets/badger.json   Bildgröße, Fußlinie, Vorschub je Bildwechsel in Bildpixeln (gemessen)

Verfahren:
  Fester Ausschnitt je Zelle (x 1–306, y 30–490). Senkrecht wird jedes Bild ganzzahlig so verschoben, dass die
  Sohle (unterste Zeile mit mindestens 10 deckenden Pixeln) auf der Bodenlinie 485 liegt: Die zweite Reihe des
  KI-Bogens steht 3 px höher als die erste. Waagerecht hat das Bildmodell die Füße der Blender-Posen auf 0–7 KI-px
  genau gehalten; jedes Bild wird ganzzahlig so verschoben, dass die Ferse des flach stehenden bzw. aufsetzenden
  Fußes (Tabelle ANCHOR) in Zeile 482 auf der Ferse der Blender-Pose liegt. Damit gilt der Vorschub des 3D-Modells: 0,367 m je Zyklus / 8 Bilder × 409,6 px/m × 0,4 = 7,52 px je Bild.
  Eine erste Fassung suchte den Vorschub per Schablonenvergleich der Sohlen zweier KI-Bilder; an den Kontakt-
  wechseln (Ferse setzt auf, Spitze hebt ab) dreht sich der Fuß, der Vergleich lieferte Unsinn (Zyklus 74 statt
  150 KI-px). Verworfen.
  Alpha des KI-Bilds endet bei 253: auf 0–1 gestreckt. Tusche und Farbflächen getrennt (inkcolor.py); zusätzlich
  Kolorierung auf reine Druckfarben (Tabelle PALETTE, dunkles Fell blauschwarz) und eine Außenkontur von
  5 KI-px um die Silhouette (nach der ersten Prüfung: ohne sie ging die kleine Figur im
  Punktraster des Pflasters unter). Verkleinern um 0,4 vormultipliziert mit Lanczos.
"""
import json, pathlib

import numpy as np
from PIL import Image, ImageFilter

from inkcolor import separate, ink_curve

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "assets/raw/walk.png"
LAYOUT = json.loads((ROOT / "assets/ref/layout.json").read_text())
SCALE = 0.4
CX0, CY0, CX1, CY1 = 1, 30, 306, 490          # Ausschnitt je Zelle (305×460 → 122×184)
GROUND = 485                                   # Bodenlinie im Layout (485,4)
OUTER = 5                                      # Außenkontur in KI-Pixeln (2 px im Spiel)
# Fuß, an dessen Ferse jedes Bild waagerecht auf das Layout gelegt wird (flach stehender bzw. aufsetzender Fuß)
ANCHOR = {"walk_0": "L", "walk_1": "L", "walk_2": "L", "walk_3": "L", "walk_4": "R", "walk_5": "R",
          "walk_6": "R", "walk_7": "R", "stand": "L", "turn": "L"}


def cells():
    im = np.asarray(Image.open(RAW).convert("RGBA")).astype(np.float64) / 255.0
    out = {}
    for c in LAYOUT["cells"]:
        x, y = c["x"], c["y"]
        cell = im[y:y + 512, x:x + 307].copy()
        cell[..., 3] = np.clip(cell[..., 3] / (253 / 255.0), 0, 1)
        out[c["name"]] = cell
    return out


def sole_row(cell):
    rows = np.where((cell[..., 3] > 0.5).sum(axis=1) >= 10)[0]
    return int(rows[-1])


def vshift(cell, dy):
    out = np.zeros_like(cell)
    if dy >= 0:
        out[dy:] = cell[:512 - dy]
    else:
        out[:512 + dy] = cell[-dy:]
    return out


def hshift(cell, dx):
    out = np.zeros_like(cell)
    if dx >= 0:
        out[:, dx:] = cell[:, :307 - dx]
    else:
        out[:, :307 + dx] = cell[:, -dx:]
    return out


def runs(row):
    out, start = [], None
    for x, v in enumerate(list(row) + [False]):
        if v and start is None:
            start = x
        elif not v and start is not None:
            out.append((start, x - 1))
            start = None
    return out


def foot_edges(mask, f, row):
    """Ferse (linkes Ende) und Spitze (rechtes Ende) des Laufs in Zeile row, der den Fuß f am meisten überdeckt."""
    best = None
    for x0, x1 in runs(mask[row]):
        ov = min(x1, f["x1_px"]) - max(x0, f["x0_px"])
        if best is None or ov > best[0]:
            best = (ov, x0, x1)
    return (best[1], best[2]) if best and best[0] > 0 else (None, None)


# Kolorierung der kleinen Figur wie im Comic: Jede Kostümfarbe des KI-Bilds (k-means-Mittel aus raw/walk.png,
# gerundet) wird einer reinen Druckfarben-Mischung zugeordnet; Schwarz und Dunkelbraun werden Tusche.
# Ziel = RGB; in Klammern die Druckfarben, die print.gdshader daraus macht (Grauanteil zu 60 % entfernt, ucr = 0,6).
PALETTE = [
    ((55, 62, 72), (0.0, 0.2, 0.6)),     # dunkles Fell: Blauschwarz wie im Comic (C76 M56 Y16)
    ((5, 4, 4), "ink"),
    ((42, 32, 24), "ink"),
    ((77, 86, 43), (0.38, 0.68, 0.0)),   # Mütze, Weste: Oliv (C43 M13 Y81)
    ((250, 232, 198), (1.0, 1.0, 1.0)),  # Gesichtsstreif, Bauch, Hemd: Papier (keine Punkte)
    ((250, 241, 214), (1.0, 1.0, 1.0)),
    ((213, 9, 20), (1.0, 0.0, 0.0)),     # Schal: Rot voll (M100 Y100)
    ((213, 157, 92), (1.0, 0.72, 0.3)),  # Paket (M28 Y70)
    ((145, 127, 97), (1.0, 0.72, 0.3)),
    ((120, 50, 32), (0.72, 0.32, 0.0)),  # Tasche (C11 M51 Y83)
]


def recolor(col, ink, alpha):
    ref = np.array([c for c, _ in PALETTE], float) / 255.0
    d = ((col[:, :, None, :] - ref[None, None]) ** 2).sum(axis=3)
    idx = d.argmin(axis=2)
    out = np.zeros_like(col)
    fur = np.zeros(idx.shape, bool)
    for i, (_, tgt) in enumerate(PALETTE):
        m = idx == i
        if tgt == "ink":
            fur |= m
        else:
            out[m] = tgt
    ink = np.maximum(ink, fur * alpha)
    return out, ink


def contour(alpha, r=OUTER):
    """Kräftige Außenkontur wie bei Comicfiguren: Ring um die Silhouette, r KI-Pixel breit (vor dem Verkleinern)."""
    m = Image.fromarray(((alpha > 0.5) * 255).astype(np.uint8))
    dil = np.asarray(m.filter(ImageFilter.MaxFilter(2 * r + 1))).astype(np.float64) / 255.0
    ring = np.clip(dil - alpha, 0.0, 1.0)
    return np.asarray(Image.fromarray((ring * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))) / 255.0


def downscale_ink(cov):
    c = cov[CY0:CY1, CX0:CX1]
    w, h = round((CX1 - CX0) * SCALE), round((CY1 - CY0) * SCALE)
    return ink_curve(np.clip(np.asarray(Image.fromarray(c.astype(np.float32), "F").resize((w, h), Image.LANCZOS)), 0, 1))


def downscale(cell):
    c = cell[CY0:CY1, CX0:CX1]
    a = c[..., 3:4]
    pm = np.concatenate([c[..., :3] * a, a], axis=2)
    w, h = round((CX1 - CX0) * SCALE), round((CY1 - CY0) * SCALE)
    chans = [np.asarray(Image.fromarray(pm[..., k].astype(np.float32), "F").resize((w, h), Image.LANCZOS))
             for k in range(4)]
    pm = np.clip(np.stack(chans, axis=2), 0, 1)
    a = pm[..., 3:4]
    rgb = np.where(a > 1e-4, pm[..., :3] / np.maximum(a, 1e-4), 0)
    return np.concatenate([np.clip(rgb, 0, 1), a], axis=2)


def main():
    cs = cells()
    names = [c["name"] for c in LAYOUT["cells"]]
    feet = {c["name"]: c["feet"] for c in LAYOUT["cells"]}
    dys = {}
    for n in names:
        dys[n] = GROUND - sole_row(cs[n])
        cs[n] = vshift(cs[n], dys[n])
    L = np.asarray(Image.open(ROOT / LAYOUT["file"]).convert("RGB")).astype(int)
    lmask = ~((L[..., 0] > 200) & (L[..., 1] < 60) & (L[..., 2] > 200))
    row = GROUND - 3

    def residual(n, lm):
        am = cs[n][..., 3] > 0.5
        r = {}
        for side, f in feet[n].items():
            if f["lift_px"] > 3.0:
                continue
            ah, at = foot_edges(am, f, row)
            lh, lt = foot_edges(lm, f, row)
            if ah is not None and lh is not None:
                r[side] = {"heel": int(ah - lh), "toe": int(at - lt)}
        return r

    resid, dxs = {}, {}
    for c in LAYOUT["cells"]:
        n = c["name"]
        lm = lmask[c["y"]:c["y"] + 512, c["x"]:c["x"] + 307]
        before = residual(n, lm)
        dxs[n] = -before[ANCHOR[n]]["heel"]
        cs[n] = hshift(cs[n], dxs[n])
        resid[n] = {"before": before, "after": residual(n, lm)}
        print("%-7s Ferse/Spitze gegen Layout vorher %s, Verschiebung %+d -> %s" % (n, before, dxs[n], resid[n]["after"]))
    step_ai = 0.367 / 8 * LAYOUT["px_per_m"]
    stand_ai = feet["walk_2"]["L"]["x0_px"] - feet["stand"]["L"]["x0_px"]
    frames, inks = [], []
    for n in names:
        col, ink = separate(cs[n][..., :3], cs[n][..., 3])
        col, ink = recolor(col, ink, cs[n][..., 3])
        ink = np.maximum(ink, contour(cs[n][..., 3]))
        frames.append(downscale(np.concatenate([col, cs[n][..., 3:4]], axis=2)))
        inks.append(downscale_ink(ink))
    fw, fh = frames[0].shape[1], frames[0].shape[0]
    sheet = np.concatenate(frames, axis=1)
    Image.fromarray((sheet * 255 + 0.5).astype(np.uint8), "RGBA").save(ROOT / "assets/badger.png")
    ink = np.concatenate(inks, axis=1)
    out = np.zeros(ink.shape + (4,), np.uint8)
    out[..., 3] = (ink * 255 + 0.5).astype(np.uint8)
    Image.fromarray(out, "RGBA").save(ROOT / "assets/badger_ink.png")
    info = {
        "file": "assets/badger.png", "frames": names, "frame_w": fw, "frame_h": fh, "scale": SCALE,
        "foot_y": round((GROUND + 1 - CY0) * SCALE, 2),
        "crop": [CX0, CY0, CX1, CY1],
        "sole_shift_ai_px": dys,
        "heel_shift_ai_px": dxs,
        "foot_residual_ai_px": resid,
        "walk_step_px": round(step_ai * SCALE, 3),
        "walk2_to_stand_px": round(stand_ai * SCALE, 3),
        "note": "walk_step_px = Vorschub je Laufbild (aus dem 3D-Modell); Halt nur aus walk_2 (Standfuß L wandert 7,5 KI-px)",
    }
    (ROOT / "assets/badger.json").write_text(json.dumps(info, indent=1))
    print("ok", fw, fh, "Fußlinie", info["foot_y"], "Schritt", info["walk_step_px"], "Halt", info["walk2_to_stand_px"], "Senkrecht", dys)


if __name__ == "__main__":
    main()
