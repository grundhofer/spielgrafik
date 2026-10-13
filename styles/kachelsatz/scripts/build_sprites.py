#!/usr/bin/env python3
"""Requisiten und Dachs-Kurier aus den KI-Blättern auf das 16-px-Raster der Karte bringen.

    .venv/bin/python styles/kachelsatz/scripts/build_sprites.py

Je Objekt: Ausschnitt (Alpha >= 200, Codex liefert Alpha ~250 plus Dunst 1-15), eigene Palette (k-means in
Oklab, echte Bildfarben), Mehrheitsfarbe je Zielpixel, 1-Bit-Alpha. Ziel: demo/art/*.png und sprites.json mit
Größen und Ankerpunkten (unten Mitte).
"""
import json, pathlib, sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pxlib import palette_from, snap_sprite, save_zoom  # noqa: E402

ENTRY = HERE.parent
RAW = ENTRY / "assets" / "raw"
OUT_A = ENTRY / "assets" / "sprites"
OUT_D = ENTRY / "demo" / "art"

# Name: (Quellbox, Verkleinerung, Farben). Verkleinerung: Bildpixel je Zielpixel (KI-Kunstpixel ~6,5 px).
PROPS = {
    "cottage":    ((104, 56, 676, 516), 6.0, 24),
    "lighthouse": ((680, 36, 1032, 916), 8.0, 20),
    "gull":       ((1248, 92, 1512, 216), 8.0, 8),
    "barrel_a":   ((1068, 256, 1180, 404), 6.5, 10),
    "barrel_b":   ((1208, 256, 1316, 404), 6.5, 10),
    "boat_a":     ((88, 556, 624, None), 7.5, 14),
    "boat_b":     ((88, None, 624, 972), 7.5, 16),
    "crates":     ((1068, 424, 1292, 628), 7.5, 12),
    "rope":       ((1340, 476, 1492, 612), 7.5, 8),
    "lantern":    ((1092, 648, 1220, 824), 5.5, 14),
    "parcel":     ((1328, 700, 1456, 800), 7.0, 8),
    "rock_a":     ((1048, 836, 1220, 992), 6.5, 8),
    "rock_b":     ((1244, 864, 1376, 976), 6.5, 8),
    "rock_c":     ((1404, 900, 1496, 972), 6.5, 6),
}


def tight(crop, cut=200):
    a = crop[..., 3] >= cut
    ys, xs = np.nonzero(a)
    return crop[ys.min():ys.max() + 1, xs.min():xs.max() + 1], (xs.min(), ys.min())


def boat_split(img):
    """Die beiden Boote berühren sich im Blatt (Mast): Trennzeile = Zeile mit wenigsten deckenden Pixeln."""
    a = img[600:820, 88:624, 3] >= 200
    return 600 + int(np.argmin(a.sum(1)))


def build_props():
    img = np.asarray(Image.open(RAW / "props.png").convert("RGBA"))
    split = boat_split(img)
    info = {}
    for name, (box, f, k) in PROPS.items():
        x0, y0, x1, y1 = box
        y0 = split if y0 is None else y0
        y1 = split if y1 is None else y1
        crop, _ = tight(img[y0:y1, x0:x1])
        pal = palette_from(crop[..., :3][crop[..., 3] >= 200], k, seed=5)
        w, h = int(round(crop.shape[1] / f)), int(round(crop.shape[0] / f))
        spr = snap_sprite(crop, pal, w, h)
        save(spr, name + ".png")
        info[name] = {"size": [w, h], "source_box": [int(x0), int(y0), int(x1), int(y1)], "scale": f, "colors": k}
    return info, split


def save(arr, name):
    for d in (OUT_A, OUT_D):
        d.mkdir(parents=True, exist_ok=True)
        Image.fromarray(arr).save(d / name)


def main():
    info, split = build_props()
    (OUT_A / "props.json").write_text(json.dumps({"boat_split_row": split, "props": info}, indent=1))
    # Kontrollblatt
    sprites = [np.asarray(Image.open(OUT_A / (n + ".png"))) for n in PROPS]
    H = max(s.shape[0] for s in sprites)
    W = sum(s.shape[1] + 3 for s in sprites)
    sheet = np.zeros((H, W, 4), np.uint8)
    sheet[..., :3] = (70, 110, 140)
    sheet[..., 3] = 255
    x = 0
    for s in sprites:
        m = s[..., 3] > 0
        sub = sheet[H - s.shape[0]:H, x:x + s.shape[1]]
        sub[m] = s[m]
        x += s.shape[1] + 3
    save_zoom(sheet, OUT_A / "props_check.png", 4)
    print(json.dumps({k: v["size"] for k, v in info.items()}))


if __name__ == "__main__" and len(sys.argv) == 1:
    main()


# ---------------------------------------------------------------- Dachs-Kurier
BADGER_BOXES = {  # Quellboxen im KI-Blatt assets/raw/badger.png
    "walk": [(40, 84, 388, 512), (420, 84, 768, 512), (788, 84, 1132, 512), (1160, 84, 1500, 512)],
    "front": [(240, 528, 580, 964), (604, 528, 920, 964), (952, 528, 1296, 964)],
}
BADGER_H = 30          # Zielhöhe Mützenoberkante bis Sohle
CELL = (40, 36)        # Zelle im Blatt; Anker (Fußmitte) bei (20, 34)
ANCHOR = (20, 34)
OUTLINE = (26, 15, 22)


def badger_palette(crops):
    px = np.concatenate([c[..., :3][c[..., 3] >= 200] for c in crops])
    uniq = np.unique((px // 6) * 6, axis=0)   # seltene Farben (Augen, Knöpfe) nicht von großen Flächen verdrängen
    return palette_from(np.concatenate([px[::7], uniq]), 32, seed=4)


def outline(spr, col=OUTLINE, thresh=70):
    """Geschlossene Kontur: transparente Nachbarn heller Randpixel werden dunkel (außen, 4er-Nachbarschaft)."""
    a = spr[..., 3] > 0
    lum = spr[..., :3].astype(int) @ np.array([299, 587, 114]) / 1000
    light = a & (lum > thresh)
    out = spr.copy()
    h, w = a.shape
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        src = np.zeros_like(light)
        ys = slice(max(dy, 0), h + min(dy, 0)); xs = slice(max(dx, 0), w + min(dx, 0))
        ys2 = slice(max(-dy, 0), h + min(-dy, 0)); xs2 = slice(max(-dx, 0), w + min(-dx, 0))
        src[ys, xs] = light[ys2, xs2]
        m = src & ~a & (out[..., 3] == 0)
        out[m, :3] = col
        out[m, 3] = 255
    return out


def head_cx(spr):
    a = spr[..., 3] > 0
    ys, xs = np.nonzero(a)
    top = ys.min() + (ys.max() - ys.min()) // 4
    sel = ys <= top
    return xs[sel].mean()


def build_badger():
    img = np.asarray(Image.open(RAW / "badger.png").convert("RGBA"))
    crops = {k: [tight(img[y0:y1, x0:x1])[0] for (x0, y0, x1, y1) in v] for k, v in BADGER_BOXES.items()}
    pal = badger_palette(crops["walk"] + crops["front"])
    frames, meta = [], []
    for kind in ("walk", "front"):
        for i, c in enumerate(crops[kind]):
            f = c.shape[0] / BADGER_H
            spr = outline(snap_sprite(c, pal, int(round(c.shape[1] / f)), BADGER_H, inner=0.6))
            # Anker: x nach Kopfmitte (oberes Viertel), y nach unterster Zeile
            a = spr[..., 3] > 0
            ys, xs = np.nonzero(a)
            cx = int(round(head_cx(spr)))
            cell = np.zeros((CELL[1], CELL[0], 4), np.uint8)
            ox, oy = ANCHOR[0] - cx, ANCHOR[1] - ys.max()
            for y, x in zip(ys, xs):
                if 0 <= y + oy < CELL[1] and 0 <= x + ox < CELL[0]:
                    cell[y + oy, x + ox] = spr[y, x]
            frames.append(cell)
            meta.append({"kind": kind, "index": i, "scale": round(f, 3), "head_cx": cx, "offset": [int(ox), int(oy)]})
    # Die vier KI-Laufbilder haben fast dieselbe Beinstellung (gemessen: hinterer Fuß x 10-14, vorderer 19-26 in
    # drei von vier Bildern, kein Durchgang). Deshalb: fester Oberkörper aus Bild 0, Beine gezeichnet (8 Phasen).
    walk = [draw_walk(frames[0], frames[1], k) for k in range(WALK_N)]
    idle = frames[4]
    blink = window(idle, frames[5], EYE_WIN)
    wave = window(idle, frames[6], ARM_WIN)
    out = walk + [idle, blink, wave]
    sheet = np.concatenate(out, 1)
    save(sheet, "badger.png")
    save_zoom(sheet, OUT_A / "badger_check.png", 6)
    save_zoom(np.concatenate(frames, 1), OUT_A / "badger_ai_frames.png", 6)
    names = [f"walk{k}" for k in range(WALK_N)] + ["front", "front_blink", "front_wave"]
    return {"cell": CELL, "anchor": ANCHOR, "frames": meta, "order": names, "walk_frames": WALK_N,
            "walk_fps": WALK_FPS, "walk_advance_px": WALK_STEP, "stride_px": STRIDE,
            "walk_lift": [lift(k) for k in range(WALK_N)]}


WALK_N = 8          # Phasen je Doppelschritt
WALK_FPS = 15       # geht in 30 fps auf (je 2 Bilder)
STRIDE = 8          # Standfuß wandert in WALK_N/2 Phasen von +4 nach -4 relativ zur Hüfte
WALK_STEP = STRIDE // (WALK_N // 2)   # Vorschub je Phase = 2 px, Standfuß steht damit in der Welt still
HIP_Y = 30          # Oberkörper bis einschließlich Zeile 30, Beine Zeilen 31-34
HIPS = {"near": 18, "far": 15}
EYE_WIN = (slice(6, 16), slice(10, 30))    # Zeilen, Spalten der Zelle: Augenpartie (Blinzeln)
ARM_WIN = (slice(0, 31), slice(25, 40))   # rechte Zellenhälfte: Gruß-Arm
LEG_COL = {"near": [(73, 62, 60), (80, 68, 65)], "far": [(57, 45, 44), (64, 53, 51)]}
LEG_OUT = (19, 11, 20)


def lift(k):
    return 0


def foot_x(leg, k):
    """Fußposition relativ zur Hüfte je Phase. Nahes Bein: Stand in Phasen 0-3 (vorn -> hinten), Schwung 4-7."""
    ph = (k + (0 if leg == "near" else WALK_N // 2)) % WALK_N
    half = WALK_N // 2
    if ph < half:   # Standbein: linear nach hinten, genau WALK_STEP je Phase
        return STRIDE // 2 - ph * WALK_STEP, 0
    t = (ph - half) / half          # Schwungbein: vor, in der Mitte 1 px angehoben
    x = -STRIDE // 2 + (ph - half) * WALK_STEP
    return x, (1 if 0 < t < 1 else 0)


def draw_leg(cell, leg, k):
    fx, up = foot_x(leg, k)
    hip = HIPS[leg]
    c_mid, c_lit = LEG_COL[leg]
    ground = ANCHOR[1] - up
    rows = list(range(HIP_Y + 1, ground + 1))
    for i, y in enumerate(rows):
        t = (i + 1) / len(rows)
        x = int(round(hip + t * fx))
        last = y == ground
        x0, x1 = (x - 1, x + 3) if last else (x - 1, x + 2)
        for xx in range(x0, x1 + 1):
            edge = xx in (x0, x1) or last
            col = LEG_OUT if edge else (c_lit if xx == x0 + 1 else c_mid)
            if 0 <= xx < CELL[0]:
                cell[y, xx, :3] = col
                cell[y, xx, 3] = 255


def draw_walk(body_src, scarf_src, k):
    cell = np.zeros_like(body_src)
    cell[:HIP_Y + 1] = body_src[:HIP_Y + 1]
    bob = 1 if k % (WALK_N // 2) in (1, 2) else 0      # Körper beim Durchgang 1 px höher
    if bob:
        cell[:-1] = cell[1:].copy()
        cell[-1] = 0
    # Schalende flattert: links vom Körper (Spalten < 11) abwechselnd aus KI-Bild 0 und 1
    if (k // 2) % 2 == 1:
        win = (slice(0, HIP_Y - 8), slice(0, 11))
        part = scarf_src[win].copy()
        if bob:
            part = np.concatenate([part[1:], np.zeros_like(part[:1])])
        cell[win] = part
    draw_leg(cell, "far", k)
    draw_leg(cell, "near", k)
    return cell


def window(base, other, win):
    out = base.copy()
    out[win] = other[win]
    return out


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "badger":
    (OUT_A / "badger.json").write_text(json.dumps(build_badger(), indent=1))
