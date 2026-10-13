"""Baut die Horizontebenen über der Horizontzeile (Mode 1): BG2 = Wolken, BG1 = ferne Felsnase mit
Leuchtturm, Inseln und Hügel. Beide 512×93 Pixel (64×12 Kacheln, die Karte läuft waagrecht um), je Pixel
der CGRAM-Index, 0 = durchsichtig (dort scheint die Hintergrundfarbe durch, die HDMA je Zeile zum
Himmelsverlauf umschreibt).

Aufruf: .venv/bin/python styles/mode7/scripts/build_backdrop.py

Prüft die Regeln einer 4bpp-Ebene: jede 8×8-Kachel nutzt nur Farben aus genau einer Palette (BG1: 2 oder 3,
BG2: 1) und zählt die verschiedenen Kacheln (mit Spiegelung). Ausgabe: demo/art/bg1.png, demo/art/bg2.png,
demo/data/backdrop.json, assets/backdrop_preview.png
"""
import json
import math
import pathlib
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import palette as P            # noqa: E402
from m7lib import STYLE, Y_H   # noqa: E402

BW, BH = 512, Y_H + 1
cl = lambda n: P.bg_idx("clouds", n)     # noqa: E731
ld = lambda n: P.bg_idx("land", n)       # noqa: E731
tw = lambda n: P.bg_idx("tower", n)      # noqa: E731
rng = np.random.default_rng(1993)

LIGHTHOUSE_X = 268      # Bildspalte der Turmmitte in der Ebene
LAMP_ROW = 0            # wird gesetzt


def noise1d(n, scale, seed):
    r = np.random.default_rng(seed)
    pts = r.uniform(-1, 1, n // scale + 3)
    x = np.arange(n) / scale
    i = np.floor(x).astype(int)
    f = x - i
    f = f * f * (3 - 2 * f)
    return pts[i] * (1 - f) + pts[i + 1] * f


# ---------------------------------------------------------------------------------------------
# BG2: Wolken
# ---------------------------------------------------------------------------------------------
def clouds():
    """Wolken auf 256 px Breite, zweimal nebeneinander: BG2 kommt so mit einer 32×32-Kachelkarte aus und
    braucht halb so viele Kacheln; auf dem Bildschirm ist immer genau eine Periode zu sehen."""
    CW = 256
    img = np.zeros((BH, CW), np.uint8)
    specs = [  # (Mitte x, Unterkante y, Länge, Dicke)
        (20, 66, 90, 5), (110, 60, 110, 6), (200, 64, 90, 5), (236, 57, 60, 4),
        (60, 74, 110, 4), (160, 76, 100, 3), (226, 80, 80, 3), (10, 84, 70, 2), (120, 85, 80, 2),
        (170, 55, 70, 4), (40, 51, 90, 5), (140, 47, 100, 6), (220, 45, 80, 5), (80, 40, 70, 4),
    ]
    for k, (cx, by, L, T) in enumerate(specs):
        bump = noise1d(CW, 7, 100 + k)
        bump2 = noise1d(CW, 3, 200 + k)
        bot = noise1d(CW, 11, 300 + k)
        for dx in range(-L // 2, L // 2 + 1):
            x = (cx + dx) % CW
            u = 2 * dx / L
            prof = max(0.0, 1 - u * u) ** 0.55
            th = T * prof * (0.75 + 0.45 * bump[x]) + 0.8 * bump2[x] * prof
            if th < 0.6:
                continue
            ybot = by + int(round(0.8 * bot[x] * prof))
            ytop = ybot - int(round(th))
            # Licht von unten: Unterkante hell (je tiefer die Wolke, desto wärmer), oben dunkel
            warm = min(1.0, max(0.0, (by - 38) / 46))
            for y in range(ytop, ybot + 1):
                if not 0 <= y < BH:
                    continue
                d = ybot - y                     # Abstand von der Unterkante
                if d == 0:
                    tone = 6 + int(round(3 * warm))
                elif d == 1:
                    tone = 5 + int(round(2 * warm))
                elif d <= 3:
                    tone = 3 + int(round(2 * warm))
                else:
                    tone = 1 + int(round(1.5 * warm))
                if y == ytop and th > 2:
                    tone = max(0, tone - 2)
                img[y, x] = cl(f"c{min(9, tone)}")
    # einzelne Sterne zwischen den Wolken
    for _ in range(14):
        x, y = int(rng.integers(0, CW)), int(rng.integers(1, 64))
        if img[y, x] == 0:
            img[y, x] = cl("star0") if rng.random() < 0.4 else cl("star1")
    return np.tile(img, (1, BW // CW))


# ---------------------------------------------------------------------------------------------
# BG1: Land
# ---------------------------------------------------------------------------------------------
def land():
    img = np.zeros((BH, BW), np.uint8)
    base = BH - 1                # Horizontzeile
    # ferne Inseln (flach, dunstig)
    for (x0, x1, hgt, seed) in [(58, 132, 5, 1), (146, 196, 3, 2), (360, 420, 4, 3), (436, 470, 2, 4)]:
        n = noise1d(BW, 5, 50 + seed)
        for x in range(x0, x1):
            u = (x - x0) / (x1 - x0)
            h = hgt * math.sin(math.pi * u) ** 0.7 + 0.8 * n[x]
            top = base - int(round(h))
            for y in range(top, base + 1):
                img[y, x] = ld("isl1")
            if top < base:
                img[top, x] = ld("isl3") if u < 0.5 else ld("isl2")
    # Hügel links (näher, dunkler)
    n = noise1d(BW, 9, 77)
    for x in list(range(0, 58)) + list(range(480, 512)):
        xx = x if x < 256 else x - 512
        u = (xx + 32) / 90
        h = 9 * math.sin(math.pi * min(1, max(0, u))) ** 0.8 + 1.5 * n[x]
        top = base - int(round(h))
        for y in range(top, base + 1):
            img[y, x] = ld("k2")
        img[top, x] = ld("rim1")
        if top + 1 <= base:
            img[top + 1, x] = ld("k3")
    # Felsnase mit Plateau für den Leuchtturm
    L = LIGHTHOUSE_X
    prof = {}
    n1 = noise1d(BW, 4, 11)
    n2 = noise1d(BW, 2, 12)
    for x in range(L - 48, L + 66):
        u = x - L
        if u < -30:            # flacher Ausläufer links
            h = 3 + (u + 48) * 0.35
        elif u < -12:          # Steilhang
            h = 9.3 + (u + 30) * 0.26
        elif u < 22:           # Plateau
            h = 14 + 0.6 * n1[x]
        elif u < 40:           # Abbruch rechts
            h = 14 - (u - 22) * 0.4
        else:
            h = max(0.0, 7 - (u - 40) * 0.28)
        h += 0.9 * n2[x]
        prof[x] = max(0, int(round(h)))
    for x, h in prof.items():
        top = base - h
        for y in range(top, base + 1):
            d = y - top
            # Schichten: hellere Kanten oben links, waagrechte Bänder
            band = y % 5 == 0 and (x // 9) % 3 != 0
            col = ld("k1") if d > 3 else ld("k2")
            if band and d > 2:
                col = ld("k3")
            if d > 9 and (x + y) % 7 == 0:
                col = ld("k0")
            img[y, x] = col
        if h > 0:
            # Lichtkante (Glut am Horizont von links)
            left_h = prof.get(x - 1, 0)
            img[top, x] = ld("rim2") if left_h < h else ld("rim1")
            if top + 1 <= base:
                img[top + 1, x] = ld("k4")
    # Gras auf dem Plateau
    for x in range(L - 12, L + 22):
        top = base - prof[x]
        img[top, x] = ld("grass2")
        img[top + 1, x] = ld("grass1")
    # Brandung am Fuß der Felsnase: helle Pixel auf der Horizontzeile
    for x in range(L - 40, L + 60, 3):
        if prof.get(x, 0) > 1:
            img[base, x] = ld("isl3")
    plateau = base - prof[L]
    return img, plateau


TOWER = [  # Turm von oben nach unten, Mitte = Spalte 4; L Licht, D dunkel, w/W weiß, r/R rot, g Galerie
    "....D....",
    "...DDD...",
    "..DDDDD..",
    "...LLL...",
    "...LLL...",
    "..ggggg..",
    "..gDDDg..",
    "...WWw...",
    "...WWw...",
    "...WWw...",
    "...RRr...",
    "...RRr...",
    "...RRr...",
    "...RRr...",
    "..WWWww..",
    "..WWWww..",
    "..WWWww..",
    "..WWWww..",
    "..WWDww..",
    "..WWWww..",
    "..WWWww..",
    "..WWWww..",
    "..WWWww..",
    ".DDDDDDD.",
]


def tower(img, plateau):
    h = len(TOWER)
    top = plateau - h + 1
    x0 = LIGHTHOUSE_X - 4
    cmap = {"D": tw("dark"), "L": tw("lamp1"), "g": tw("k0"), "W": tw("white2"), "w": tw("white1"),
            "R": tw("red2"), "r": tw("red1")}
    lamp = []
    for r, row in enumerate(TOWER):
        for c, ch in enumerate(row):
            if ch == ".":
                continue
            img[top + r, x0 + c] = cmap[ch]
            if ch == "L":
                lamp.append((top + r, x0 + c))
    # Wärterhaus neben dem Turm (klein, dunkel, ein Fenster)
    hx = LIGHTHOUSE_X + 6
    for y in range(plateau - 5, plateau + 1):
        for x in range(hx, hx + 9):
            img[y, x] = tw("k3") if y > plateau - 4 else tw("dark")
    img[plateau - 6, hx + 1:hx + 8] = tw("dark")
    img[plateau - 3, hx + 5] = tw("win")
    img[plateau - 3, hx + 6] = tw("win")
    for y in range(plateau - 4, plateau + 1):
        img[y, hx] = tw("rim1")
    return top, lamp


def enforce_palettes(img, allowed):
    """Jede 8×8-Kachel auf genau eine Palette bringen: die Palette mit den meisten Treffern, fremde Farben
    auf die nächste Farbe dieser Palette. Gibt (Bild, Palette je Kachel, Zahl der Korrekturen) zurück."""
    tab = np.array(P.table())
    out = img.copy()
    fixes = 0
    pal_of = np.zeros((BH // 8 + 1, BW // 8), np.int8)
    for ty in range(0, BH, 8):
        for tx in range(0, BW, 8):
            t = out[ty:ty + 8, tx:tx + 8]
            used = t[t > 0]
            if used.size == 0:
                pal_of[ty // 8, tx // 8] = -1
                continue
            best = max(allowed, key=lambda p: np.sum((used >= 16 * p) & (used < 16 * p + 16)))
            pal_of[ty // 8, tx // 8] = best
            for (y, x) in zip(*np.nonzero(t)):
                v = int(t[y, x])
                if not (16 * best < v < 16 * best + 16):
                    cand = [i for i in range(16 * best + 1, 16 * best + 16) if any(tab[i])]
                    t[y, x] = min(cand, key=lambda i: np.sum((tab[i] - tab[v]) ** 2))
                    fixes += 1
    return out, pal_of, fixes


def unique_tiles(img):
    seen = set()
    for ty in range(0, BH, 8):
        for tx in range(0, BW, 8):
            t = img[ty:ty + 8, tx:tx + 8]
            if t.shape != (8, 8):
                t = np.pad(t, ((0, 8 - t.shape[0]), (0, 8 - t.shape[1])))
            keys = [t.tobytes(), t[:, ::-1].tobytes(), t[::-1, :].tobytes(), t[::-1, ::-1].tobytes()]
            if not any(k in seen for k in keys):
                seen.add(keys[0])
    return len(seen)


def main():
    bg2 = clouds()
    bg1, plateau = land()
    ttop, lamp = tower(bg1, plateau)
    bg1, pal1, fix1 = enforce_palettes(bg1, [2, 3])
    bg2, pal2, fix2 = enforce_palettes(bg2, [1])
    n1, n2 = unique_tiles(bg1), unique_tiles(bg2)
    print(f"BG1: {n1} Kacheln, {fix1} Farbkorrekturen; BG2: {n2} Kacheln, {fix2} Korrekturen")
    art = STYLE / "demo/art"
    Image.fromarray(bg1, "L").save(art / "bg1.png")
    Image.fromarray(bg2, "L").save(art / "bg2.png")
    lamp_c = [float(np.mean([p[1] for p in lamp])), float(np.mean([p[0] for p in lamp]))]
    (STYLE / "demo/data/backdrop.json").write_text(json.dumps({
        "size": [BW, BH], "lighthouse_x": LIGHTHOUSE_X, "lamp": lamp_c, "tower_top": ttop, "plateau": plateau,
        "tiles_bg1": n1, "tiles_bg2": n2, "palette_fixes": [fix1, fix2],
        "sky": [[r, list(P.c5(h))] for r, h in P.SKY],
    }, indent=1))
    tab = P.write_cgram()
    lut = np.array([P.rgb8(c) for c in tab], np.uint8)
    # Vorschau mit Himmelsverlauf
    sky = np.zeros((BH, BW, 3), np.uint8)
    rows = [r for r, _ in P.SKY]
    cols = [np.array(P.c5(h), float) for _, h in P.SKY]
    for y in range(BH):
        k = max(i for i, r in enumerate(rows) if r <= y)
        if k == len(rows) - 1:
            c = cols[k]
        else:
            f = (y - rows[k]) / (rows[k + 1] - rows[k])
            c = cols[k] * (1 - f) + cols[k + 1] * f
        sky[y] = np.round(np.round(c) * 255 / 31)
    prev = sky.copy()
    prev[bg2 > 0] = lut[bg2[bg2 > 0]]
    prev[bg1 > 0] = lut[bg1[bg1 > 0]]
    Image.fromarray(prev).resize((BW * 3, BH * 3), Image.NEAREST).save(STYLE / "assets/backdrop_preview.png")


if __name__ == "__main__":
    main()
