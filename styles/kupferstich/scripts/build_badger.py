#!/usr/bin/env python3
"""Zerlegt den KI-Laufbogen (assets/raw/walk_small.png) in Spielbilder für Godot und misst den Laufzyklus.

    .venv/bin/python styles/kupferstich/scripts/build_badger.py

Schritte:
 1. Zellen aus assets/ref/layouts.json (walk_small, 2x5); je Zelle Alpha (Codex liefert echte Transparenz) und
    Tuschedichte D = 1 - Helligkeit (Papier im Bild ist reinweiß), Kontrast wie bei der Platte.
 2. Ausrichtung: Sohle (unterste deckende Zeile) aller Bilder auf eine gemeinsame Grundlinie; waagerecht bleibt die
    Lage in der Zelle (das Bildmodell hielt sich an die Zellen des Blender-Layouts, Kopfmitte 160-171 px).
 3. Bodenkontakt je Bild in Spielgröße (Läufe deckender Spalten in den untersten 2/4/8 Zeilen) für die Vorschub-
    Tabelle in assets/badger_override.json (von Hand gelesen; ein automatischer IoU-Abgleich der Sohlen ergab
    Unsinn, weil beide Füße zu einem Lauf verschmelzen und die KI die Füße beim Abrollen umformt).
    Mit --runs werden die Läufe ausgegeben.
 4. Verkleinern auf Spielgröße (Faktor SCALE, vormultipliziert, Lanczos), Kammfeld (für Licht im Shader) aus der
    verkleinerten Tusche.
 5. Blinzeln: in der Dreiviertelansicht das sichtbare Auge (dunkler Fleck mit Glanzpunkt) mit dem Fell links daneben
    überdecken und ein heller Lidstrich (Papier) als Bogen darunter.
Ausgabe: assets/badger.png (alle Bilder nebeneinander, RGBA: R = Tusche, G = Kammfeld, A = Deckung),
assets/badger.json (Bildgröße, Fußpunkt, Bodenkontakt je Bild); Kopien in demo/art.
"""
import json, shutil, sys

import numpy as np
from PIL import Image

import inklib as K

SCALE = 0.63
NAMES = [f"walk_{i}" for i in range(8)] + ["stand", "turn", "blink"]


def contrast(D):
    return np.clip((D - 0.08) / 0.84, 0, 1) ** 0.9


def runs(mask):
    out, start = [], None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        if not v and start is not None:
            out.append([start, i - 1])
            start = None
    if start is not None:
        out.append([start, len(mask) - 1])
    return out


def main():
    lay = json.loads((K.SD / "assets/ref/layouts.json").read_text())["walk_small"]
    sheet = np.asarray(Image.open(K.SD / "assets/raw/walk_small.png").convert("RGBA"), np.float32) / 255
    cells = {c["name"]: c for c in lay["cells"]}
    raw = {}
    for name in NAMES[:-1]:
        c = cells[name]
        a = sheet[c["y"]:c["y"] + c["h"], c["x"]:c["x"] + c["w"]]
        A = a[..., 3]
        L = K.lum(np.clip(a[..., :3] * 255, 0, 255))
        D = contrast(np.clip(1.0 - L, 0, 1)) * (A > 0.02)
        ys, xs = np.nonzero(A > 0.5)
        raw[name] = {"A": A, "D": D, "sole": int(ys.max()), "top": int(ys.min())}

    # Gemeinsamer Rahmen in Quellpixeln: Sohle bei y = FOOT_Y, Zellenbreite bleibt
    cw = lay["cells"][0]["w"]
    tops = [r["sole"] - r["top"] for r in raw.values()]
    FOOT_Y = max(tops) + 12
    HH = FOOT_Y + 4
    frames = {}
    for name, r in raw.items():
        A = np.zeros((HH, cw), np.float32)
        D = np.zeros((HH, cw), np.float32)
        s0 = r["sole"] - FOOT_Y
        src0, dst0 = max(0, s0), max(0, -s0)
        n = min(r["A"].shape[0] - src0, HH - dst0)
        A[dst0:dst0 + n] = r["A"][src0:src0 + n]
        D[dst0:dst0 + n] = r["D"][src0:src0 + n]
        frames[name] = {"A": A, "D": D}

    # Blinzeln aus der Dreiviertelansicht
    A, D = frames["turn"]["A"].copy(), frames["turn"]["D"].copy()
    eye = find_eye(D, A)
    ex, ey, er = eye
    patch = D[ey - er - 1:ey + er + 2, ex - er - 1 - 2 * er - 3:ex + er + 2 - 2 * er - 3].copy()
    D[ey - er - 1:ey + er + 2, ex - er - 1:ex + er + 2] = np.maximum(patch, 0.75)
    for k in range(-er - 1, er + 2):     # heller Lidstrich, leicht gebogen
        yy = ey + 1 + int(round(0.25 * k * k / max(er, 1)))
        D[yy, ex + k] = min(D[yy, ex + k], 0.15)
    frames["blink"] = {"A": A, "D": D}

    # Verkleinern
    W = int(round(cw * SCALE))
    H = int(round(HH * SCALE))
    out = np.zeros((H, W * len(NAMES), 4), np.float32)
    contact = {}
    for i, name in enumerate(NAMES):
        A, D = frames[name]["A"], frames[name]["D"]
        Ap = K.resize_f(A, (W, H)).clip(0, 1)
        Dp = K.resize_f(D * A, (W, H)).clip(0, 1)
        Dn = np.where(Ap > 1e-3, Dp / np.maximum(Ap, 1e-3), 0).clip(0, 1)
        ridge = K.blur(Dn, 0.9)
        ridge = np.clip(ridge / max(1e-3, float(np.percentile(ridge[Ap > 0.5], 99.5))), 0, 1)
        out[:, i * W:(i + 1) * W] = np.stack([Dn, ridge, np.zeros_like(Dn), Ap], -1)
        sole = int(np.nonzero(Ap > 0.5)[0].max())
        contact[name] = {f"rows{k}": runs((Ap[sole - k + 1:sole + 1] > 0.5).any(0)) for k in (2, 4, 8)}
    png = K.SD / "assets/badger.png"
    Image.fromarray(np.clip(out * 255 + 0.5, 0, 255).astype(np.uint8), "RGBA").save(png)
    meta = {
        "frames": NAMES, "frame_w": W, "frame_h": H, "scale": SCALE,
        "foot": [None, round(FOOT_Y * SCALE, 2)],
        "height_px": round(float(np.mean(tops)) * SCALE, 1),
        "eye_turn_src": [int(ex), int(ey), int(er)],
        "contact": contact,
    }
    (K.SD / "assets/badger.json").write_text(json.dumps(meta, indent=1))
    for f in (png, K.SD / "assets/badger.json"):
        shutil.copy(f, K.SD / "demo/art" / f.name)
    print(json.dumps({k: meta[k] for k in ("frame_w", "frame_h", "height_px", "eye_turn_src")}))
    if "--runs" in sys.argv:
        for name, c in contact.items():
            print(f"{name:7s}", c)


def find_eye(D, A):
    """Auge in der Dreiviertelansicht: kleiner heller Glanzpunkt, rundum dunkel, im oberen Kopfdrittel."""
    ys, xs = np.nonzero(A > 0.5)
    top = ys.min()
    h = ys.max() - top
    best = None
    for y in range(top + int(0.12 * h), top + int(0.30 * h)):
        for x in range(xs.min() + 20, xs.max() - 10):
            if D[y, x] > 0.3 or A[y, x] < 0.9:
                continue
            ring = np.concatenate([D[y - 4, x - 4:x + 5], D[y + 4, x - 4:x + 5], D[y - 4:y + 5, x - 4],
                                   D[y - 4:y + 5, x + 4]])
            score = ring.mean() - D[y, x]
            if best is None or score > best[0]:
                best = (score, x, y)
    _, x, y = best
    return x, y + 2, 5


if __name__ == "__main__":
    main()
