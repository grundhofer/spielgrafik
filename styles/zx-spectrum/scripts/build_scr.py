#!/usr/bin/env python3
"""KI-Hintergrund -> Spectrum-Bildschirm (demo/rom/harbour.scr) nach Zell- und Attributregel.

Schritte:
  1. Jeden Quellpixel einer Palettenfarbe zuordnen (Oklab, nächste Farbe; Braun -> Gelb, Grau -> Weiß/Schwarz).
  2. Auf das Bildraster 256×144 (Zeilen 0..17 des Bildschirms): x = Quelle / 4,9375, y = 72 + (Quelle − 429) / 5,075
     (Horizont der Quelle bei Bildzeile 72 = Zellgrenze), je Zielpixel die häufigste Farbe im Blockinneren.
  3. Bildaufbau nach Bereichen: Himmel als Farbbänder je Zellzeile mit Wolke in Linienfarbe (Code, Umriss aus der
     Quelle), Wasser, Kai mit Platten und Landzunge aus der Quelle; Häuschen, Leuchtturm, Boote, Steg, Fässer,
     Kisten, Tau und Laterne zellgenau neu gezeichnet (Code und Pixeltext in props.py).
  4. Zellregel: je 8×8-Zelle das Paar (INK, PAPER) und BRIGHT mit dem kleinsten Oklab-Fehler (erschöpfend);
     feste Attribute für animierte Zellen (Leuchtfeuer mit FLASH, Laterne) und INK Weiß in leeren Himmelszellen
     (Rauch und Möwen übernehmen die Zellfarbe).
Ausgabe: demo/rom/harbour.scr (6912 Bytes), demo/rom/scene.json, assets/bg_preview.png (×3),
assets/bg_mapped.png (×3, Schritt 3 vor der Zellregel).
"""
import json, pathlib, sys

import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent
sys.path.insert(0, str(HERE))
import zxlib as zx  # noqa: E402
import props  # noqa: E402

SRC = ENTRY / "assets/raw/bg.png"
SX, SY, HSRC, HY = 1264 / 256, 5.075, 429, 72   # Maßstab und Horizont (Quelle -> Ziel)
PIC_ROWS = 18          # Bildzeilen 0..17 (144 px); darunter Textbereich
QUAY_Y = 112           # Kaikante (Zellgrenze); darüber Wasser

K, b, r, m, g, c, y, w = range(8)
B, R, M, G, C, Y, W = 9, 10, 11, 12, 13, 14, 15
LETTER = {ch: i for i, ch in enumerate("kbrmgcyw")} | {ch: i + 8 for i, ch in enumerate("KBRMGCYW") if ch != "K"}

PROTO = [(tuple(int(v) for v in zx.PAL16[i]), i) for i in range(16) if i != 8]
PROTO += [
    ((128, 96, 64), y), ((150, 105, 60), y), ((110, 75, 40), y), ((128, 96, 32), y),
    ((45, 30, 19), K), ((70, 45, 25), K), ((32, 0, 0), K), ((64, 64, 64), K), ((32, 32, 32), K),
    ((160, 160, 160), w), ((192, 192, 192), w), ((128, 128, 128), w),
    ((239, 100, 107), R), ((211, 106, 93), R),
    ((130, 10, 241), M), ((96, 0, 224), M), ((160, 0, 224), M),
]


def classify(rgb):
    lab = zx.oklab(rgb.reshape(-1, 3))
    plab = zx.oklab(np.array([p[0] for p in PROTO]))
    tgt = np.array([p[1] for p in PROTO])
    best = np.zeros(lab.shape[0], np.int32)
    bd = np.full(lab.shape[0], np.inf)
    for k in range(len(PROTO)):
        d = ((lab - plab[k]) ** 2).sum(1)
        mk = d < bd
        bd[mk] = d[mk]
        best[mk] = tgt[k]
    return best.reshape(rgb.shape[:2])


def map_source():
    """Quelle -> 256×144 Palettenindizes (häufigste Klasse im Blockinneren)."""
    rgb = np.asarray(Image.open(SRC).convert("RGB")).astype(np.float64)
    cls = classify(rgb)
    out = np.zeros((144, 256), np.int32)
    inner = 0.2
    for j in range(144):
        sy0 = HSRC + (j - HY + inner) * SY
        sy1 = HSRC + (j - HY + 1 - inner) * SY
        y0, y1 = int(round(sy0)), max(int(round(sy1)), int(round(sy0)) + 1)
        if y0 < 0 or y1 > cls.shape[0]:
            continue
        for i in range(256):
            x0, x1 = int(round((i + inner) * SX)), int(round((i + 1 - inner) * SX))
            blk = cls[y0:y1, x0:max(x1, x0 + 1)].ravel()
            out[j, i] = np.bincount(blk, minlength=16).argmax()
    return out


# Himmel je Bildzeile: (Papier, Linie). Zellzeilen: 0 Sterne, 1 Raster, 2-3 Blau, 4-6 Blau mit Magentalinien
# (nach unten dichter), 7 Rot mit Magentalinien, 8 Rot mit gelben Linien (Abendglut).
SKY_ROWS = ([K] * 8 + [None] * 8 + [B] * 16
            + [B, B, B, M, B, B, B, M]          # Zeile 4
            + [B, M, B, B, M, B, B, M]          # Zeile 5
            + [B, M, B, M, B, M, B, M]          # Zeile 6
            + [M, R, M, R, R, M, R, R]          # Zeile 7
            + [R, R, Y, R, R, Y, R, Y])         # Zeile 8
SKY_PAPER = {0: K, 1: K, 2: B, 3: B, 4: B, 5: B, 6: B, 7: R, 8: R}
SKY_INK = {1: B, 4: M, 5: M, 6: M, 7: M, 8: Y}


def sky_px(xx, yy):
    if 8 <= yy < 16:
        return B if (xx + yy) % 2 == 0 else K
    return SKY_ROWS[yy]


def stamp(idx, art, x0, y0):
    rows = [l for l in art.strip("\n").split("\n")]
    for j, line in enumerate(rows):
        for i, ch in enumerate(line):
            if ch == ".":
                continue
            yy, xx = y0 + j, x0 + i
            if ch == "p":
                idx[yy, xx] = b if yy < QUAY_Y else K
            else:
                idx[yy, xx] = LETTER[ch]


def draw_boat(idx, x0, gy, length, cabin=False, mast=None):
    """Boot im Profil (Bug rechts), massiv gelb, Planken in Papierfarbe (Blau)."""
    spans = [(0, length), (1, length - 1), (1, length - 2), (2, length - 3), (3, length - 4),
             (4, length - 6), (6, length - 9)]
    idx[gy - 1, x0] = y                                   # Heck-Spitze
    idx[gy - 2, x0 + length - 1:x0 + length + 1] = y      # Bug-Spitze
    idx[gy - 1, x0 + length - 2:x0 + length + 1] = y
    for j, (a, e) in enumerate(spans):
        idx[gy + j, x0 + a:x0 + e] = y
    idx[gy + 2, x0 + 2:x0 + length - 3] = b               # Planke
    idx[gy + 4, x0 + 4:x0 + length - 6] = b               # Planke
    if cabin:
        cx = x0 + length // 2 - 5
        idx[gy - 7:gy, cx:cx + 10] = y
        idx[gy - 5:gy - 2, cx + 2:cx + 4] = b             # Fenster
        idx[gy - 5:gy - 2, cx + 6:cx + 8] = b
        idx[gy - 8, cx - 1:cx + 11] = y                   # Dach
    if mast is not None:
        mx, top = mast
        idx[top:gy, mx] = y
        idx[gy - 3, mx - 9:mx + 1] = y                    # Baum
        for k in range(1, 9):                             # Stag zum Bug
            idx[top + k * 2 - 1:top + k * 2 + 1, mx + k] = y


WALL = r


def cottage(idx):
    """Häuschen links (Längsseite): Dach als schwarze Fläche mit blauen Schieferlinien, Wand Schwarz mit
    gelben Steinlagen, Tür (weißer Rahmen) und Fenster (hellgelb) zellgenau."""
    # Dach: First y 50 (x 0..42), rechte Schräge bis Traufe y 73 bei x 63
    for j in range(50, 74):
        right = 42 + (j - 50) * 21 // 23
        idx[j, 0:right + 1] = K
    for j in (56, 61, 66):                                 # Schieferlagen
        right = 42 + (j - 50) * 21 // 23
        idx[j, 0:right - 2] = b
        for x in range((j // 5) % 6, right - 3, 6):
            idx[j + 1:j + 3, x] = b
    # Schornstein auf dem First
    idx[33:50, 33:39] = K
    idx[32, 32:40] = K
    # Wand x 0..55, y 74..119
    idx[74:120, 0:56] = K
    for row, j in enumerate(range(80, 120, 6)):
        idx[j, 0:56] = WALL
        off = 0 if row % 2 else 6
        for x in range(off, 56, 12):
            idx[j - 5:j, x] = WALL
    idx[74, 0:56] = WALL                                   # Traufkante
    # Tür in den Zellen x 8..23, y 88..119 (weiß), Fenster x 32..47, y 80..95 (hellgelb)
    idx[88:120, 8:24] = K
    idx[89:120, 9] = w
    idx[89:120, 22] = w
    idx[89, 9:23] = w
    for x in (13, 18):
        idx[91:120, x] = w
    idx[104, 20:22] = w                                    # Klinke
    idx[80:96, 32:48] = K
    idx[81:95, 33:47] = Y
    idx[81:95, 39:41] = K
    idx[87:89, 33:47] = K


def lighthouse(idx):
    """Leuchtturm zellgenau, Achse auf der Zellgrenze x = 232 (Zellspalten 28 und 29)."""
    for j in range(16, 64):                                # Turmzellen: nur Himmelspapier
        for i in range(224, 240):
            idx[j, i] = SKY_PAPER[j // 8]
    for j, hw in zip(range(17, 24), [1, 2, 3, 4, 5, 6, 7]):   # Dach (Zeile 2): schwarzer Kegel
        idx[j, 232 - hw:232 + hw] = K
    idx[16, 231:233] = K
    idx[24:32, 226:238] = Y                                # Laternenraum (Zeile 3): Glas gelb, FLASH
    idx[24:32, 231:233] = B
    idx[24, 225:239] = B
    idx[25:31, 226] = B
    idx[25:31, 237] = B
    idx[32:34, 224:240] = R                                # Galerie und rotes Band (Zeile 4)
    idx[34:40, 227:237] = R
    for j in range(40, 64):                                # weißer Turm (Zeilen 5..7)
        hw = 5 + (j - 40) // 10
        idx[j, 232 - hw:232 + hw] = W
    for j in range(64, 72):                                # Sockel auf dem Fels (Zeile 8)
        idx[j, 224:240] = K
        idx[j, 225:239] = w
    idx[66:72, 230:234] = K                                # Tür


def lantern(idx):
    """Laternenpfahl auf dem Kai, Ausleger über dem Wasser; Laterne allein in Zelle (26, 11)."""
    idx[85:127, 220:222] = y
    idx[85, 211:222] = y
    idx[86, 217:219] = y
    idx[87, 211:213] = y                                   # Haken
    idx[88:96, 208:216] = b
    stamp(idx, props.LANTERN, 208, 89)


def build_idx():
    src = map_source()
    idx = src.copy()
    yy, xx = np.mgrid[0:144, 0:256]
    # Himmel
    for j in range(72):
        for i in range(256):
            idx[j, i] = sky_px(i, j)
    # Wolke: Umriss der schwarzen Quellwolke, gefüllt in Linienfarbe Magenta (Zellzeilen 5..6)
    cloud = (src == K) & (yy >= 40) & (yy < 56) & (xx >= 112) & (xx < 212)
    idx[cloud] = M
    # Wasser normal hell
    low = idx[72:]
    low[low == B] = b
    low[low == C] = c
    low[low == Y] = y
    low[low == M] = b
    # Felslinien und Kaiplatten in normalem Weiß (sonst wird die ganze Zelle hell)
    idx[(yy >= 56) & (idx == W)] = w
    # Verirrte schwarze Striche im Wasser (Reste der Quell-Requisiten): kurze Läufe zwischen Wasserpixeln
    for j in range(72, QUAY_Y):
        row = idx[j]
        i = 0
        while i < 256:
            if row[i] == K:
                e = i
                while e < 256 and row[e] == K:
                    e += 1
                left = row[i - 1] if i > 0 else b
                right = row[e] if e < 256 else b
                if e - i <= 6 and left in (b, c) and right in (b, c):
                    row[i:e] = b
                i = e
            else:
                i += 1
    # Landzunge rechts aus der Quelle (schwarzer Fels mit weißen Linien)
    head = (xx >= 188) & (yy >= 56) & (yy < 72) & np.isin(src, [K, w, W])
    idx[head] = np.where(src[head] == W, w, src[head])
    # Bereich der Quell-Requisiten (Boote, Steg, Fässer, Kisten, Laterne, Tau) leeren
    water = (xx >= 56) & (xx < 228) & (yy >= 72) & (yy < QUAY_Y)
    idx[water & ~np.isin(idx, [b, c])] = b
    quay = (xx < 224) & (yy > QUAY_Y) & (yy < 144)
    idx[quay & ~np.isin(idx, [K, w, W])] = K
    idx[quay & (idx == W)] = w
    idx[(yy >= QUAY_Y) & (idx == W)] = w
    idx[120:128, 0:56] = K                                 # Reste des Quell-Häuschens vor der Tür
    cottage(idx)
    lighthouse(idx)
    # Boote und Steg
    draw_boat(idx, 124, 97, 36, mast=(140, 62))
    draw_boat(idx, 168, 98, 38, cabin=True)
    idx[104:106, 116:170] = y                              # Steg-Belag
    idx[106, 116:170] = b
    for px in (117, 131, 145, 159, 168):
        idx[106:112, px:px + 2] = y
    # Fässer, Kisten, Tau
    stamp(idx, props.BARREL, 57, 115)
    stamp(idx, props.BARREL, 70, 115)
    stamp(idx, props.CRATE, 83, 114)
    stamp(idx, props.CRATE, 84, 101)
    stamp(idx, props.ROPE, 186, 117)
    lantern(idx)
    # Sonnenglitzern unter der Abendglut: Wellenstriche in Zeile 9, x 128..183 gelb
    gl = idx[72:80, 128:184]
    gl[gl == c] = y
    for k, (gx, gyy, gw) in enumerate([(130, 74, 3), (139, 77, 4), (147, 73, 5), (156, 76, 4), (163, 74, 3),
                                        (171, 77, 4), (178, 75, 3)]):
        idx[gyy, gx:gx + gw] = y
    # Wellenstriche in Zellen mit Gelb entfernen (sonst drei Farben)
    for cy in range(9, 14):
        for cx in range(32):
            blk = idx[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8]
            if (blk == y).any():
                blk[blk == c] = b
    # Sterne
    for sx, sy in [(12, 2), (29, 5), (45, 1), (210, 3), (233, 6), (250, 2), (221, 1)]:
        idx[sy, sx] = W
    # Trennlinie Bild/Text in der letzten Bildzeile
    idx[143, :] = w
    return idx, src


def solve(idx, lab16, cy, cx, force=None):
    blk = idx[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8].ravel()
    best = None
    # Helligkeit nach der Mehrheit der farbigen Quellpixel (Schwarz zählt nicht), sonst kippen ganze Zellen
    n_hi = int(((blk >= 9)).sum())
    n_lo = int(((blk >= 1) & (blk <= 7)).sum())
    brs = (1,) if n_hi > n_lo else (0,) if n_lo > n_hi else (0, 1)
    cands = [force] if force else [(br, i, p) for br in brs for i in range(8) for p in range(i, 8)]
    for br, ink, paper in cands:
        ci, cp = br * 8 + ink, br * 8 + paper
        di = ((lab16[blk] - lab16[ci]) ** 2).sum(1)
        dp = ((lab16[blk] - lab16[cp]) ** 2).sum(1)
        err = np.minimum(di, dp).sum()
        if best is None or err < best[0] - 1e-9:
            best = (err, ink, paper, br, (di < dp).reshape(8, 8))
    _, ink, paper, br, bits = best
    if force is None and (bits.sum() > 32 or (ink == 0 and paper != 0 and bits.any())):
        ink, paper, bits = paper, ink, ~bits
    if ink == paper:
        bits = np.zeros((8, 8), bool)
    return ink, paper, br, bits.astype(np.uint8)


FORCE = {
    (28, 3): (1, 6, 1), (29, 3): (1, 6, 1),     # Leuchtfeuer: INK Gelb, PAPER Blau, hell (dazu FLASH)
    (26, 11): (1, 6, 1),                        # Laterne: INK Gelb, PAPER Blau; flackert über INK/BRIGHT
}


def main():
    idx, src = build_idx()
    Image.fromarray(zx.PAL16[idx]).resize((768, 432), Image.NEAREST).save(ENTRY / "assets/bg_mapped.png")
    lab16 = zx.oklab(zx.PAL16.astype(np.float64))
    full = np.zeros((192, 256), np.int32)
    full[:144] = idx
    bits = np.zeros((192, 256), np.uint8)
    attrs = np.zeros((24, 32), np.uint8)
    for cy in range(PIC_ROWS):
        for cx in range(32):
            ink, paper, br, bb = solve(full, lab16, cy, cx, FORCE.get((cx, cy)))
            bits[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8] = bb
            attrs[cy, cx] = zx.attr_byte(ink, paper, br)
    for cx in (28, 29):
        attrs[3, cx] |= 0x80                       # FLASH
    # Leere Himmelszellen (nur Papier): INK Weiß, damit Rauch und Möwen weiß erscheinen
    empty_sky = []
    for cy in range(2, 7):
        for cx in range(32):
            if not bits[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8].any():
                attrs[cy, cx] = zx.attr_byte(7, (attrs[cy, cx] >> 3) & 7, (attrs[cy, cx] >> 6) & 1)
                empty_sky.append([cx, cy])
    attrs[PIC_ROWS:] = zx.attr_byte(7, 0, 0)
    # Wasserzellen (Papier Blau normal, nur Blau/Cyan) für die Wellenanimation
    water = []
    for cy in range(9, 14):
        for cx in range(32):
            blk = idx[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8]
            if np.isin(blk, [b, c]).all():
                water.append([cx, cy])
                attrs[cy, cx] = zx.attr_byte(5, 1, 0)       # alle Wasserzellen INK Cyan (Wellen wandern)
    out = zx.render(bits, attrs)
    Image.fromarray(out).resize((768, 576), Image.NEAREST).save(ENTRY / "assets/bg_preview.png")
    (ENTRY / "demo/rom").mkdir(parents=True, exist_ok=True)
    (ENTRY / "demo/rom/harbour.scr").write_bytes(zx.pack(bits, attrs))
    # Glitzerzellen am Horizont (Zeile 9: Papier Blau, INK Gelb, nicht Mast) und Sternzellen (Zeile 0)
    glints = [[cx, 9] for cx in range(32) if (attrs[9, cx] & 7) == 6 and ((attrs[9, cx] >> 3) & 7) == 1
              and cx != 17]                              # Spalte 17 = Mast
    stars = [[cx, 0] for cx in range(32) if bits[0:8, cx * 8:cx * 8 + 8].any()]
    scene = {"water_cells": water, "empty_sky_cells": empty_sky, "lamp_cells": [[28, 3], [29, 3]],
             "lantern_cell": [26, 11], "chimney_top": [35, 31], "quay_y": QUAY_Y, "glint_cells": glints,
             "star_cells": stars}
    (ENTRY / "demo/rom/scene.json").write_text(json.dumps(scene))
    changed = int((zx.PAL16[full] != out).any(-1)[:144].sum())
    print(f"Zellregel: {changed} von {144 * 256} Pixeln umgefärbt; Wasserzellen {len(water)}")


if __name__ == "__main__":
    main()
