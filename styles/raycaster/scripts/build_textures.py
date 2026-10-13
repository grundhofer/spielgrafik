#!/usr/bin/env python3
"""Baut alle Wand- und Bodentexturen (Indexbilder in der 256er-Palette) und den Himmel.

Quelle: ein KI-Texturblatt (assets/raw/textures.png, 4x4 Zellen mit schwarzen Fugen). Jede Zelle wird
auf 64x64 Texel verkleinert (32 Texel je Meter, eine Kachel = 2 m, wie 64 Karteneinheiten), auf eine
Zielhelligkeit gebracht, nahtlos gemacht und ohne Dithering in die Palette eingerastet. Fassaden mit
Fenster und Tür, Leuchtturm, Lampenglas, Wasser (4 Bilder) und Himmel entstehen hier per Code.

    python3 scripts/build_textures.py          # schreibt assets/textures/*.png + demo/textures/

Ausgabe: 8-Bit-Graustufen-PNG, Grauwert = Palettenindex (Godot liest den Index im Shader).
"""
import json
import math
import pathlib
import shutil
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import rc_palette as P  # noqa: E402

ENTRY = pathlib.Path(__file__).resolve().parent.parent
RAW = ENTRY / "assets" / "raw" / "textures.png"
OUT = ENTRY / "assets" / "textures"
DEMO = ENTRY / "demo" / "textures"
TEXEL_PER_M = 32

XS = [(12, 304), (323, 617), (636, 930), (949, 1241)]
YS = [(10, 306), (322, 618), (634, 926), (942, 1240)]
CELLS = ["pave", "quaywall_dry", "cottage", "slate", "deck", "tarboard", "plaster", "cliff",
         "grass", "crate_src", "boatwhite", "brick", "door_src", "window_src", "iron", "quaywall"]

# Zielhelligkeit (Median der Luminanz, sRGB 0..255) und Nahtausgleich je Zelle
TARGET = {"pave": 112, "quaywall_dry": 112, "cottage": 118, "slate": 88, "deck": 112, "tarboard": 62,
          "plaster": 196, "cliff": 92, "grass": 96, "crate_src": 110, "boatwhite": 178, "brick": 92,
          "door_src": 78, "window_src": None, "iron": 74, "quaywall": 70}
SEAM = {"pave": 6, "cottage": 6, "slate": 0, "deck": 0, "tarboard": 0, "plaster": 8, "cliff": 8, "grass": 8,
        "boatwhite": 0, "brick": 0, "iron": 0, "quaywall": 0, "quaywall_dry": 0}


def lum(a):
    return a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114


def cell(sheet, k, size=(64, 64), margin=6):
    r, c = divmod(k, 4)
    x0, x1 = XS[c]
    y0, y1 = YS[r]
    return sheet.crop((x0 + margin, y0 + margin, x1 - margin + 1, y1 - margin + 1))


def to_size(img, w, h, seam=0):
    """Auf w x h verkleinern; mit seam > 0 wird ein Überstand weich in den Gegenrand geblendet."""
    if seam <= 0:
        return np.asarray(img.resize((w, h), Image.LANCZOS), dtype=np.float64)
    big = np.asarray(img.resize((w + seam, h + seam), Image.LANCZOS), dtype=np.float64)
    a = big.copy()
    # waagrecht: Spalten w..w+seam in 0..seam überblenden
    for i in range(seam):
        t = (i + 0.5) / seam
        a[:, i] = big[:, w + i] * (1 - t) + big[:, i] * t
    a = a[:, :w]
    b = a.copy()
    for i in range(seam):
        t = (i + 0.5) / seam
        b[i, :] = a[h + i, :] * (1 - t) + a[i, :] * t
    return b[:h]


def set_brightness(a, target):
    if target is None:
        return a
    med = np.median(lum(a))
    g = math.log(target / 255.0) / math.log(max(med, 1) / 255.0)
    return 255.0 * (np.clip(a, 0, 255) / 255.0) ** g


def recolor(a, rgb_from, rgb_to):
    """Farbe einer Textur verschieben, Helligkeitsverlauf behalten (für rote Farbe auf Putz und Planken)."""
    L = lum(a)[..., None] / max(1.0, lum(np.array(rgb_from, float)))
    return np.clip(L * np.array(rgb_to, float), 0, 255)


def q(a, ramps=None):
    allowed = P.ramp_mask(ramps) if ramps else None
    return P.quantize(np.clip(np.round(a), 0, 255).astype(np.uint8), allowed)


def save(name, idx, meta, note):
    P.save_index_png(idx, OUT / f"{name}.png")
    meta[name] = {"size": [int(idx.shape[1]), int(idx.shape[0])], "colors": int(len(np.unique(idx))), "note": note}


def seam_error(idx):
    rgb = P.PALETTE[idx].astype(float)
    inner = np.abs(np.diff(rgb, axis=1)).mean()
    edge = np.abs(rgb[:, 0] - rgb[:, -1]).mean()
    inner_v = np.abs(np.diff(rgb, axis=0)).mean()
    edge_v = np.abs(rgb[0] - rgb[-1]).mean()
    return round(edge / inner, 2), round(edge_v / inner_v, 2)


# ---------------------------------------------------------------------------------------------
# Code-Texturen

def water_frames(n=4, size=64):
    """Wasser als Bodentextur mit 4 Bildern (Schleife), nahtlos: Wellenlinien aus periodischem Rauschen."""
    rng = np.random.default_rng(7)
    y, x = np.mgrid[0:size, 0:size] / size
    frames = []
    # periodische Grundwellen (ganzzahlige Frequenzen -> nahtlos)
    comps = [(rng.integers(1, 4), rng.integers(-3, 4), rng.uniform(0, 2 * np.pi), rng.uniform(0.5, 1.0))
             for _ in range(7)]
    for f in range(n):
        ph = 2 * np.pi * f / n
        h = np.zeros_like(x)
        for i, (fx, fy, p0, amp) in enumerate(comps):
            k = 1 if i % 2 == 0 else -1
            h += amp * np.sin(2 * np.pi * (fx * x + fy * y * 2) + p0 + k * ph * (1 + i % 3))
        h = (h - h.min()) / (h.max() - h.min())
        # Kämme der Wellen hell, Täler dunkel: Bänder wie gemalte Wasserflächen
        base = np.array([40, 92, 104], float)
        dark = np.array([18, 44, 62], float)
        light = np.array([120, 178, 186], float)
        col = dark[None, None] * (1 - h[..., None]) + base[None, None] * h[..., None]
        crest = np.clip((h - 0.82) / 0.18, 0, 1)[..., None]
        col = col * (1 - crest) + light[None, None] * crest
        frames.append(q(col, ["meer", "blau"]))
    return frames


def lamp_glass(w=32, h=64):
    """Laternenhaus des Leuchtturms: helle Scheiben, dunkles Eisengitter (eine Fläche = 1 m breit)."""
    a = np.zeros((h, w, 3), float)
    yy, xx = np.mgrid[0:h, 0:w]
    glow = 1.0 - np.abs(yy - h * 0.55) / (h * 0.6)
    a[:] = np.array([255, 236, 150])[None, None] * 0.75 + np.array([255, 250, 220])[None, None] * 0.25
    a *= (0.82 + 0.18 * np.clip(glow, 0, 1))[..., None]
    iron = np.array([46, 44, 52], float)
    for x0 in (0, w // 2):
        a[:, x0:x0 + 2] = iron
    a[:, w - 1:] = iron
    for y0 in (0, 1, h // 3, 2 * h // 3, h - 2, h - 1):
        a[y0] = iron
    return q(a, ["gelb", "orange", "nacht", "grau"])


def sky(w=256, h=128, horizon=100):
    """Himmelspanorama 256x128 (viermal je Umdrehung), Horizont in Zeile `horizon` (Bildmitte).

    Abendhimmel in 256 Farben: Verlauf in Bändern (keine Zwischenfarben), flache Wolkenbänke mit
    orange beleuchteter Unterseite, erste Sterne oben. Nahtlos über die Breite (periodisches Rauschen)."""
    rng = np.random.default_rng(11)
    y, x = np.mgrid[0:h, 0:w].astype(float)
    t = np.clip((horizon - y) / horizon, 0, 1)        # 0 am Horizont, 1 oben
    stops = [(0.00, (255, 168, 72)), (0.07, (246, 128, 70)), (0.16, (214, 104, 104)), (0.28, (158, 92, 132)),
             (0.45, (96, 78, 140)), (0.65, (54, 58, 118)), (0.85, (30, 36, 84)), (1.0, (20, 24, 60))]
    col = np.zeros((h, w, 3))
    for (t0, c0), (t1, c1) in zip(stops[:-1], stops[1:]):
        m = (t >= t0) & (t <= t1)
        s = ((t - t0) / (t1 - t0))[..., None]
        col[m] = (np.array(c0) * (1 - s) + np.array(c1) * s)[m]
    below = y > horizon
    col[below] = np.array([255, 168, 72]) * 0.85

    def vnoise(cx, cy, seed):
        """Wertrauschen, waagrecht periodisch (Periode w, damit das Panorama nahtlos ist)."""
        r = np.random.default_rng(seed)
        gx, gy = w // cx, h // cy + 2
        grid = r.random((gy, gx))
        xs, ys = np.arange(w) / cx, np.arange(h) / cy
        x0 = np.floor(xs).astype(int)
        fx = xs - x0
        x1 = (x0 + 1) % gx
        x0 %= gx
        y0 = np.floor(ys).astype(int)
        fy = ys - y0
        sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        top = grid[y0][:, x0] * (1 - sx) + grid[y0][:, x1] * sx
        bot = grid[y0 + 1][:, x0] * (1 - sx) + grid[y0 + 1][:, x1] * sx
        return top * (1 - sy[:, None]) + bot * sy[:, None]

    def fbm(seed, base=(64, 8)):
        out, amp, tot = np.zeros((h, w)), 1.0, 0.0
        cx, cy = base
        for o in range(4):
            out += amp * vnoise(max(1, cx >> o), max(1, cy >> o), seed + o)
            tot += amp
            amp *= 0.5
        return out / tot

    # Wolkenbänke: (Mitte, halbe Dicke, Schwelle, Seed, Körper oben, Körper unten, beleuchteter Rand)
    clouds = [(horizon - 11, 7.0, 0.40, 3, (124, 74, 104), (176, 90, 96), (255, 156, 92)),
              (horizon - 30, 10.0, 0.43, 5, (86, 64, 116), (128, 76, 120), (246, 128, 118)),
              (horizon - 53, 9.0, 0.47, 8, (56, 52, 104), (78, 60, 116), (184, 110, 146)),
              (horizon - 74, 6.0, 0.52, 13, (36, 38, 84), (48, 46, 96), (110, 84, 136))]
    taken = np.zeros((h, w), bool)
    for cy, thick, thr, seed, body_top, body_low, rim in clouds:
        dens = fbm(seed, (48, 12)) * np.exp(-((y - cy) / thick) ** 2 * 0.7)
        dens += 0.18 * (vnoise(16, 2, seed + 40) - 0.5)
        mask = (dens > thr) & ~taken & (y < horizon - 1)
        below1 = np.roll(mask, -1, axis=0)
        below2 = np.roll(mask, -2, axis=0)
        above1 = np.roll(mask, 1, axis=0)
        rel = np.clip((y - (cy - thick)) / (2 * thick), 0, 1)[..., None]
        body = (np.array(body_top)[None, None] * (1 - rel) + np.array(body_low)[None, None] * rel) * 0.84
        col[mask] = body[mask]
        top_edge = mask & ~above1
        col[top_edge] = (body * 0.82)[top_edge]
        rim2 = mask & below1 & ~below2
        rim1 = mask & ~below1
        col[rim2] = (np.array(rim) * 0.55 + body * 0.45)[rim2]
        col[rim1] = np.broadcast_to(np.array(rim, float), col.shape)[rim1]
        taken |= mask
    # Sterne: nur im oberen Drittel, ein Pixel
    stars = rng.integers(0, w, 42), rng.integers(0, int(horizon * 0.45), 42)
    for sx, sy in zip(*stars):
        if not taken[max(0, sy - 1):sy + 2, max(0, sx - 1):sx + 2].any():
            col[sy, sx] = (255, 250, 230) if rng.random() < 0.3 else (180, 180, 210)
    idx = q(col, ["orange", "rosa", "violett", "blau", "nacht", "gelb", "rot", "creme"])
    return idx


# ---------------------------------------------------------------------------------------------

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sheet = Image.open(RAW).convert("RGB")
    meta = {}
    src = {}
    for k, name in enumerate(CELLS):
        c = cell(sheet, k)
        a = to_size(c, 64, 64, SEAM.get(name, 0))
        a = set_brightness(a, TARGET[name])
        src[name] = a

    plain = ["pave", "slate", "deck", "tarboard", "plaster", "cliff", "grass", "boatwhite", "brick", "iron",
             "quaywall", "quaywall_dry", "cottage"]
    for name in plain:
        idx = q(src[name])
        save(name, idx, meta, "KI-Zelle, 64x64")
        meta[name]["seam_lr_tb"] = seam_error(idx)

    # Rote Fassungen per Umfärben
    red = recolor(src["plaster"], (196, 196, 196), (205, 60, 48))
    save("plasterred", q(red, ["rot", "rostbraun", "rosa"]), meta, "plaster umgefärbt")
    boatred = recolor(src["boatwhite"], (178, 178, 178), (196, 58, 44))
    save("boatred", q(boatred, ["rot", "rostbraun", "rosa", "creme", "granit"]), meta, "boatwhite umgefärbt")

    # Boote: weiß mit rotem Rand bzw. rot mit weißem Rand (obere 5 Texelzeilen)
    a = src["boatwhite"].copy()
    a[:5] = red[:5] * 0.95
    a[5] *= 0.45
    save("boat_a", q(a), meta, "weiße Planken, roter Rand")
    b = boatred.copy()
    b[:5] = src["boatwhite"][:5]
    b[5] *= 0.45
    save("boat_b", q(b), meta, "rote Planken, weißer Rand")

    # Kiste: eine Seite = 1 m (32 Texel)
    crate = set_brightness(np.asarray(cell(sheet, 9, margin=3).resize((32, 32), Image.LANCZOS), float), 112)
    save("crate", q(crate), meta, "Kistenseite 1 m")

    # Häuschen: Wand mit Fenster bzw. Tür, 64 x 128 (Unterkante = Boden)
    cot = np.tile(src["cottage"], (2, 1, 1))
    lintel = np.array([150, 144, 134], float)
    win = cell(sheet, 13, margin=4)
    wa = np.asarray(win.resize((30, 34), Image.LANCZOS), float)
    wa = 255.0 * (wa / 255.0) ** 0.8
    w = cot.copy()
    y0, x0 = 128 - 32 - 34, 17
    w[y0 - 1:y0 + 35, x0 - 1:x0 + 31] *= 0.35         # dunkle Laibung
    w[y0:y0 + 34, x0:x0 + 30] = wa
    w[y0 - 4:y0 - 1, x0 - 3:x0 + 33] = lintel * np.array([1.0, 0.98, 0.95]) * (0.9 + 0.1 * np.random.default_rng(1).random((3, 36, 1)))
    w[y0 + 34:y0 + 36, x0 - 2:x0 + 32] = lintel * 0.95
    save("cottage_win", q(w), meta, "Fieldstone + KI-Fenster (1,0 m Brüstung)")
    door = set_brightness(np.asarray(cell(sheet, 12, margin=4).resize((30, 61), Image.LANCZOS), float), 82)
    d = cot.copy()
    y0, x0 = 128 - 61, 17
    d[y0 - 1:, x0 - 1:x0 + 31] *= 0.35
    d[y0:, x0:x0 + 30] = door
    d[y0 - 4:y0 - 1, x0 - 3:x0 + 33] = lintel * (0.9 + 0.1 * np.random.default_rng(2).random((3, 36, 1)))
    save("cottage_door", q(d), meta, "Fieldstone + KI-Tür")
    # Tür allein für die Türnische: 40 x 64 (1,25 m x 2 m), dunkler Rahmen, Tür 34 x 62
    fr = np.zeros((64, 40, 3)) + np.array([46, 34, 26], float)
    fr[2:, 3:37] = set_brightness(np.asarray(cell(sheet, 12, margin=4).resize((34, 62), Image.LANCZOS), float), 84)
    save("door", q(fr), meta, "KI-Tür mit Rahmen (Türnische)")

    # Leuchtturm: 64 x 256 (8 m), Unterkante = Sockeloberkante; rotes Band 3,0–4,4 m über dem Sockel
    pl = np.tile(src["plaster"], (4, 1, 1))
    rd = np.tile(red, (4, 1, 1))
    tower = pl.copy()
    b0, b1 = 256 - int(4.4 * TEXEL_PER_M), 256 - int(3.0 * TEXEL_PER_M)
    tower[b0:b1] = rd[b0:b1]
    tower[b1:b1 + 1] *= 0.7
    save("lh_tower", q(tower), meta, "Putz weiß mit rotem Band")
    tw = tower.copy()
    for wy in (256 - int(1.9 * TEXEL_PER_M), 256 - int(6.2 * TEXEL_PER_M)):
        tw[wy - 10:wy, 26:38] = np.array([30, 28, 34])
        tw[wy - 11:wy - 10, 25:39] *= 0.6
        tw[wy - 6:wy - 2, 28:36] = np.array([255, 200, 110])   # Licht im Turm
    save("lh_tower_win", q(tw), meta, "Turmseite mit zwei Fensterschlitzen")
    td = tower.copy()
    dd = set_brightness(np.asarray(cell(sheet, 12, margin=4).resize((22, 60), Image.LANCZOS), float), 70)
    td[256 - 61:256, 20:44] = np.array([40, 34, 30])
    td[256 - 60:256, 21:43] = dd
    save("lh_door", q(td), meta, "Turmseite mit Tür")
    save("lamp", lamp_glass(), meta, "Laternenhaus, Code")

    for i, f in enumerate(water_frames()):
        save(f"water{i}", f, meta, "Wasser Bild %d/4, Code" % (i + 1))
    s = sky()
    save("sky", s, meta, "Himmel 256x128, Code, Horizont Zeile 100")

    # Vorschau (RGB) und Kopie für Godot
    names = sorted(meta)
    tiles = []
    for n in names:
        idx = np.asarray(Image.open(OUT / f"{n}.png"))
        rgb = P.PALETTE[idx]
        reps = (2, 2) if rgb.shape[0] <= 64 else (1, 2)
        tiles.append((n, np.tile(rgb, (reps[0], reps[1], 1))))
    W = sum(t.shape[1] + 4 for _, t in tiles)
    H = max(t.shape[0] for _, t in tiles)
    prev = Image.new("RGB", (W, H), (255, 0, 255))
    x = 0
    for n, t in tiles:
        prev.paste(Image.fromarray(t.astype(np.uint8)), (x, 0))
        x += t.shape[1] + 4
    prev.save(ENTRY / "assets" / "textures_preview.png")
    (OUT / "textures.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    DEMO.mkdir(parents=True, exist_ok=True)
    for n in names:
        shutil.copy2(OUT / f"{n}.png", DEMO / f"{n}.png")
    for n in names:
        print(f"{n:14s} {meta[n]['size']} {meta[n]['colors']:3d} Farben  {meta[n].get('seam_lr_tb', '')}")


if __name__ == "__main__":
    main()
