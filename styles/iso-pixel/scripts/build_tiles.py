"""Isometrische Würfelkacheln (2:1) und Hafenkarte für den Eintrag iso-pixel, vollständig im Code.

  .venv/bin/python styles/iso-pixel/scripts/build_tiles.py

Kachel: 32×24 px = Raute 32×16 (Oberseite) + 8 px Seitenflächen (links und rechts). Die Raute ist exakt 2:1:
Zeilenbreiten 2, 6, 10 … 30, 30 … 2 (Pixelmitten-Test |dx|/16 + |dy|/8 < 1), Kanten springen 2 px waagrecht je
1 px senkrecht, Nachbarkacheln im Abstand (16, 8) und (−16, 8) schließen lückenlos und ohne Überlappung an.
Eine Säule der Karte ist ein Stapel solcher Würfel (Ebenen −3 … 2, je 8 px); Godot legt je Ebene einen
TileMapLayer an, 8 px höher als der darunter.

Muster hängen nur von Flächenkoordinaten ab (u entlang der Fläche 0..16, absolute Höhe h in px), mit Periode
einer Kachel: Mauerfugen, Erdschichten und Wasserquerschnitt laufen über alle Kacheln und Ebenen durch.
Seitenflächen kennen zwei Arten: 'exposed' (zum Wasser oder tieferen Gelände: Kaimauer, Fels, Erde mit
Grasüberhang) und 'cut' (Schnittkante des Dioramas: Schichten aus Pflaster, Erde, Fels; beim Wasser der blaue
Querschnitt mit Meeresgrund).

Ausgaben:
  demo/art/tiles.png        Atlas, je Kachel 32×24, animierte Wasserkacheln als 8 Bilder nebeneinander
  demo/art/jetty.png        Stegkachel 32×32 (Planken quer, Pfähle bis zur Wasserlinie)
  demo/map/harbour.json     Ebenen mit Zellen und Atlaskoordinaten, Ursprung, Kachelmaße
  assets/tiles/tiles.png, jetty.png (Kopien), atlas_x4.png Übersicht, preview_map.png Python-Zusammensetzung
                            der Karte (Referenz; Godot-Bild mit --tiles ist pixelgleich)
"""
import hashlib
import json
import pathlib
import sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isopal  # noqa: E402

ENTRY = HERE.parent
TW, TT, BH = 32, 16, 8          # Kachelbreite, Rautenhöhe, Würfelhöhe
CH = TT + BH                    # Kachelbild 32×24
WATER_DROP = 4                  # Wasseroberfläche 4 px unter der Oberkante der Ebene −1 (h = −4)
FRAMES = 8                      # Wasseranimation
LAYERS = range(-3, 3)
EXTRA = {
    "WaterLight": isopal.dusk(isopal.hx("#5f95a6")),
    "Glint": isopal.hx("#e89a58"),                      # Abendrot auf dem Wasser (nicht abgedunkelt)
    "Foam": isopal.dusk(isopal.hx("#a9cdd2")),
    "Algae": isopal.dusk(isopal.hx("#2f4a35")),
    "Seabed": [isopal.dusk(isopal.hx(c)) for c in ("#2a2430", "#3d3338", "#574940", "#6f5d4c")],
}

# ---------------------------------------------------------------------------------------------------------
# Karte: Code + oberste Ebene. x läuft nach rechts unten, y nach links unten (Godot DIAMOND_DOWN).
#   Q Kai (Pflaster), G Gras, H Hügel (Gras), R Fels mit Gras, r Fels, S Sand, W Wasser, J Wasser mit Steg
MAP = """
H1 H1 W  W  W  W  W  W  R1 R2 R2
H1 G0 S- W  W  J  W  W  r0 R2 R2
G0 G0 S- W  W  J  W  W  W  R1 R1
G0 G0 Q0 W  W  J  W  W  W  r0 W
Q0 Q0 Q0 Q0 Q0 Q0 Q0 W  W  W  W
Q0 Q0 Q0 Q0 Q0 Q0 Q0 Q0 W  W  W
Q0 Q0 Q0 Q0 Q0 Q0 Q0 Q0 W  W  W
"""
ORIGIN = (120, 66)              # Bildpunkt der oberen Ecke von Zelle (0, 0) auf Höhe 0 (426×240)


def parse_map():
    rows = [r.split() for r in MAP.strip().splitlines()]
    cells = {}
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            code = c[0]
            lv = c[1:]
            top = -1 if code in "WJ" or lv == "-" else int(lv)
            cells[(x, y)] = (code, top)
    return cells, len(rows[0]), len(rows)


# ---------------------------------------------------------------------------------------------------------
# Geometrie der Kachel
yy, xx = np.mgrid[0:CH, 0:TW]
SX, SY = xx + 0.5, yy + 0.5
TOP = (np.abs(SX - 16) / 16 + np.abs(SY - 8) / 8) < 1
LEFT = (SX <= 16) & (SY >= 8 + SX / 2) & (SY < 16 + SX / 2)
RIGHT = (SX >= 16) & (SY >= 24 - SX / 2) & (SY < 32 - SX / 2)
GX = ((SX - 16) / 16 + SY / 8) / 2          # Rautenkoordinaten 0..1
GY = (SY / 8 - (SX - 16) / 16) / 2
LU, LV = SX, SY - (8 + SX / 2)              # linke Fläche: u 0..16, v 0..8 (Tiefe unter der Kante)
RU, RV = SX - 16, SY - (24 - SX / 2)        # rechte Fläche


def rnd(*key):
    h = hashlib.md5(repr(key).encode()).digest()
    return int.from_bytes(h[:4], "little") / 2 ** 32


BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0


def ramp(name):
    return EXTRA[name] if name in EXTRA else isopal.RAMPS[name]


# ---------------------------------------------------------------------------------------------------------
# Muster der Seitenflächen: (u in px entlang der Fläche, h absolute Höhe in px, Seite) -> Farbe
# Basisstufe: linke Fläche 2, rechte Fläche 1 (Licht von links oben vorn)

def face_color(style, side, u, h, top_h, v, is_top=True):
    base = 2 if side == "L" else 1
    up = 0 if side == "L" else 1                      # Phasenversatz der Fugen zwischen den Flächen
    lip = v < 1.0 and is_top                          # oberste Zeile unter der Kante, nur am obersten Würfel
    if style == "brick":
        r = ramp("StoneDark") if h < -4 else ramp("Stone")
        course = int(np.floor((h + 64) / 4))
        hu = (u + (4 if course % 2 else 0) + up * 2) % 8
        joint_h = ((h + 64) % 4) < 1
        joint_v = hu < 1
        if -6 <= h < -3:
            return ramp("Algae") if (int(u) + course) % 3 else r[max(0, base - 1)]
        if lip:
            return r[min(3, base + 1)]
        if joint_h or joint_v:
            return r[max(0, base - 1)]
        if hu < 2 and ((h + 64) % 4) < 2:
            return r[min(3, base + 1)] if side == "L" else r[base]
        return r[base]
    if style in ("soil", "soilgrass", "paving"):
        r = ramp("Earth")
        if style == "paving" and h > top_h - 3:
            s = ramp("Stone")
            if h > top_h - 1:
                return s[min(3, base + 1)]
            return s[max(0, base - 1)] if (int(u) % 8) == 0 else s[base]
        if style == "soilgrass":
            fr = 2 + (1 if rnd("fr", int(u) // 2, side) > 0.5 else 0) + (1 if rnd("fr2", int(u)) > 0.8 else 0)
            if h > top_h - fr:
                g = ramp("Grass")
                return g[min(3, base + 1)] if h > top_h - 1 else g[base]
        # Steine in der Erde: deterministische Klumpen
        cell_u, cell_h = int(u) // 4, int(np.floor(h / 3))
        if rnd("st", cell_u, cell_h, side) > 0.86 and (int(u) % 4) < 3:
            return ramp("Rock")[base]
        if (int(u) + int(h)) % 7 == 0 and rnd("dot", int(u), int(h)) > 0.5:
            return r[max(0, base - 1)]
        return r[base]
    if style in ("bedrock", "cliff", "cliffgrass"):
        r = ramp("Rock")
        if style == "cliffgrass":
            fr = 1 + (1 if rnd("fr", int(u) // 2, side, 7) > 0.4 else 0) + (1 if rnd("fr3", int(u)) > 0.85 else 0)
            if h > top_h - fr:
                g = ramp("Grass")
                return g[min(3, base + 1)] if h > top_h - 1 else g[base]
        if style == "bedrock":
            band = int(np.floor((h + 64) / 5))
            if ((h + 64) % 5) < 1 and rnd("bd", int(u) // 3, band) > 0.25:
                return r[max(0, base - 1)]
            return r[max(0, base - 1)] if band % 2 == 0 and base > 0 and rnd("bb", int(u), int(h)) > 0.8 else r[base]
        # Fels: unregelmäßige Brocken (Voronoi über u und h, periodisch in u mit 16 px), Risse an den Grenzen
        best, second, cid = 1e9, 1e9, None
        for ci in range(-1, 3):
            for hj in range(-12, 6):
                for k in range(2):
                    px_ = ci * 8 + 1 + rnd("vx", ci % 2, hj, k) * 7
                    py_ = hj * 6 + rnd("vy", ci % 2, hj, k) * 6
                    d = ((u - px_) ** 2 + ((h - py_) * 1.3) ** 2) ** 0.5
                    if d < best:
                        best, second, cid = d, best, (ci % 2, hj, k)
                    elif d < second:
                        second = d
        if second - best < 1.1:
            return r[max(0, base - 1)]
        lit = rnd("rk", *cid, side)
        if lip or (second - best < 2.2 and lit > 0.5 and side == "L"):
            return r[min(3, base + 1)]
        return r[min(3, base + 1)] if lit > 0.82 else r[base]
    if style == "sandside":
        r = ramp("Sand")
        if lip:
            return r[min(3, base + 1)]
        return r[max(0, base - 1)] if ((h + 64) % 3) < 1 and rnd("sd", int(u) // 2, int(h)) > 0.3 else r[base]
    if style == "water":
        r = ramp("Water")
        depth = -WATER_DROP - h                     # px unter der Oberfläche
        if depth < 0:
            return None                              # über der Wasserlinie: leer
        if depth < 1:
            return EXTRA["Foam"] if side == "L" else EXTRA["WaterLight"]
        t = 2.6 - depth / 6.0 - (0.0 if side == "L" else 0.6)
        b = BAYER4[int(h) % 4, int(u) % 4]
        k = int(np.clip(np.floor(t + b - 0.5 + 0.5), 0, 3))
        if rnd("bub", int(u), int(h)) > 0.985:
            return EXTRA["WaterLight"]
        return r[k]
    if style == "seabed":
        r = EXTRA["Seabed"]
        if h > -16 - 2:
            return ramp("Sand")[base] if rnd("sb", int(u) // 2, side) > 0.3 else r[base + 1]
        return r[base] if rnd("sb2", int(u) // 3, int(h) // 2) > 0.25 else r[max(0, base - 1)]
    raise ValueError(style)


# ---------------------------------------------------------------------------------------------------------
# Oberseiten: (gx, gy in 0..1, Variante, Bild für Animation) -> Farbe

def top_color(kind, gx, gy, var, frame=0):
    if kind == "flag":
        r = ramp("Stone")
        # 2×2 Platten je Kachel, Fugen an gx, gy = 0 und 0,5 (je eine Fugenlinie pro Grenze)
        fx, fy = (gx * 2) % 1.0, (gy * 2) % 1.0
        sx, sy = int(gx * 2), int(gy * 2)
        if fx < 1 / 16 or fy < 1 / 16 * 2:
            return r[1]
        tone = 3 if rnd("fl", sx, sy, var) > 0.45 else 2
        if fx < 3 / 16 or fy < 3 / 16:
            return r[3]
        if fx > 14 / 16 or fy > 14 / 16:
            return r[max(1, tone - 1)]
        if rnd("fs", int(gx * 32), int(gy * 32), var) > 0.93:
            return r[tone - 1]
        return r[tone]
    if kind in ("grass", "grass_hi"):
        r = ramp("Grass")
        cx, cy = int(gx * 16), int(gy * 16)
        v = rnd("g", cx // 2, cy // 2, var)
        w = rnd("g2", cx, cy, var)
        if v > 0.82 and w > 0.3:
            return r[3]
        if v < 0.12:
            return r[1]
        if w > 0.993:
            return isopal.RAMPS["Sand"][3] if rnd("fl", cx, cy, var) > 0.5 else isopal.RAMPS["Scarf"][3]
        return r[2]
    if kind == "rocktop":
        r = ramp("Rock")
        cx, cy = int(gx * 8), int(gy * 8)
        if rnd("rt", cx, cy, var) > 0.8:
            return r[2]
        if rnd("rc", int(gx * 16), int(gy * 16), var) > 0.92:
            return r[1]
        return r[3]
    if kind == "sandtop":
        r = ramp("Sand")
        cx, cy = int(gx * 16), int(gy * 16)
        return r[2] if rnd("sa", cx, cy // 2, var) > 0.86 else r[3]
    if kind == "water":
        r = ramp("Water")
        # Muster im Bildraster, periodisch im Kachelgitter (32, 0) und (16, 8): passt über alle Kacheln.
        # Kurze Kräuselstriche (3 px) blitzen nacheinander auf (je 3 von 8 Bildern), dabei wandern sie 1 px.
        sx = int(round(16 * (gx - gy) + 16 - 0.5))
        sy = int(round(8 * (gx + gy) - 0.5))
        sx2 = (sx - 16 * (sy // 8)) % 32
        sy2 = sy % 8
        for k in range(5):
            dx = int(rnd("wx", k, var) * 32)
            dy = int(rnd("wy", k, var) * 8)
            ph = int(rnd("wp", k, var) * FRAMES)
            age = (frame + ph) % FRAMES
            if age < 3 and sy2 == dy and 0 <= (sx2 - dx - (1 if age >= 1 else 0)) % 32 < 3:
                return EXTRA["WaterLight"] if age == 1 else r[3]
        if rnd("wg", var) > 0.6 and sy2 == 5 and (sx2 - 9) % 32 < 2 and frame % 4 < 2:
            return EXTRA["Glint"]
        return r[1] if ((sx2 // 2) + sy2 * 3) % 7 else r[2]
    raise ValueError(kind)


# ---------------------------------------------------------------------------------------------------------

def make_cube(top_kind, var, lstyle, rstyle, layer, frame=0):
    img = np.zeros((CH, TW, 4), np.uint8)
    top_h = 8 * layer + 8
    water_top = top_kind == "water"
    for y in range(CH):
        for x in range(TW):
            c = None
            if TOP[y, x] and top_kind:
                if water_top:
                    continue
                c = top_color(top_kind, GX[y, x], GY[y, x], var, frame)
            elif LEFT[y, x] and lstyle:
                v = LV[y, x]
                h = top_h - v
                c = face_color(lstyle, "L", LU[y, x], h, top_h, v, top_kind is not None)
            elif RIGHT[y, x] and rstyle:
                v = RV[y, x]
                h = top_h - v
                c = face_color(rstyle, "R", RU[y, x], h, top_h, v, top_kind is not None)
            if c is not None:
                img[y, x, :3] = c
                img[y, x, 3] = 255
    if water_top:
        # Oberfläche WATER_DROP px tiefer: Raute verschoben zeichnen, Seiten darunter bleiben (schon gesetzt)
        for y in range(CH):
            for x in range(TW):
                sy = y - WATER_DROP
                if 0 <= sy < CH and TOP[sy, x]:
                    img[y, x, :3] = top_color("water", GX[sy, x], GY[sy, x], var, frame)
                    img[y, x, 3] = 255
    return img


def make_jetty(var=0):
    """Stegkachel 32×32: Deck auf Höhe 8 (Oberkante der Ebene 0), Planken quer, 2 px Stirnseite, Pfähle bis h = −4."""
    img = np.zeros((32, TW, 4), np.uint8)
    w = ramp("Wood")
    wd = ramp("WoodDark")
    yy2, xx2 = np.mgrid[0:32, 0:TW]
    sx, sy = xx2 + 0.5, yy2 + 0.5
    gx = ((sx - 16) / 16 + sy / 8) / 2
    gy = (sy / 8 - (sx - 16) / 16) / 2
    a0, a1 = 0.25, 0.75                               # Stegbreite quer (in x)
    deck = (gx > a0) & (gx < a1) & (gy > 0) & (gy < 1)
    # Pfähle: an beiden Rändern bei gy = 0.25 und 0.75, je 2 px breit, 12 px hoch (Deck bis Wasserlinie)
    posts = []
    for px_ in (a0 + 0.02, a1 - 0.02):
        for py_ in (0.25, 0.75):
            psx = 16 + 16 * (px_ - py_)
            psy = 8 * (px_ + py_)
            posts.append((psx, psy))
    for y in range(32):
        for x in range(TW):
            c = None
            for psx, psy in posts:
                if abs(sx[y, x] - psx) < 1.0 and psy + 1 <= sy[y, x] < psy + 13:
                    c = wd[1] if sx[y, x] > psx else wd[2]
                    if sy[y, x] > psy + 11:
                        c = EXTRA["Foam"]
            if c is not None:
                img[y, x, :3] = c
                img[y, x, 3] = 255
    # Stirnseiten (2 px) unter den Vorderkanten des Decks
    for y in range(32):
        for x in range(TW):
            for d in (1, 2):
                sy0 = y - d
                if sy0 < 0:
                    continue
                if deck[sy0, x] and not deck[y, x] and not (img[y, x, 3] and d == 2):
                    if not any(deck[y - k, x] for k in range(0, 1)):
                        img[y, x, :3] = wd[1] if gx[sy0, x] > 0.5 and gy[sy0, x] < 0.98 else wd[2]
                        img[y, x, 3] = 255
    for y in range(32):
        for x in range(TW):
            if deck[y, x]:
                plank = int(np.floor(gy[y, x] * 6))
                fy = (gy[y, x] * 6) % 1.0
                if fy < 0.17:
                    c = wd[2]
                elif (gx[y, x] - a0) < 0.04 or (a1 - gx[y, x]) < 0.04:
                    c = w[2]
                else:
                    c = w[3] if rnd("pl", plank, var) > 0.5 else w[2]
                    if rnd("nail", plank, int(gx[y, x] * 12)) > 0.97:
                        c = wd[1]
                img[y, x, :3] = c
                img[y, x, 3] = 255
    return img


# ---------------------------------------------------------------------------------------------------------

def column_kinds(code, top):
    """Würfel je Ebene: (Ebene, Oberseite oder None, Art exposed, Art cut)."""
    out = []
    for L in LAYERS:
        if L > top:
            break
        is_top = L == top
        if code in "WJ":
            if L == -3:
                out.append((L, None, "seabed", "seabed"))
            else:
                out.append((L, "water" if is_top else None, "water", "water"))
        elif code == "Q":
            out.append((L, "flag" if is_top else None, "brick", "paving" if is_top else ("bedrock" if L == -3 else "soil")))
        elif code in "GH":
            if is_top:
                out.append((L, "grass", "soilgrass", "soilgrass"))
            else:
                out.append((L, None, "soil", "bedrock" if L <= -2 else "soil"))
        elif code == "R":
            out.append((L, "grass_hi" if is_top else None, "cliffgrass" if is_top else "cliff",
                        "cliffgrass" if is_top else ("bedrock" if L <= -2 else "cliff")))
        elif code == "r":
            out.append((L, "rocktop" if is_top else None, "cliff", "bedrock" if L <= -2 else "cliff"))
        elif code == "S":
            out.append((L, "sandtop" if is_top else None, "sandside", "sandside" if L >= -1 else "bedrock"))
    return out


def main():
    cells, W, H = parse_map()
    tiles = {}          # key -> atlas index (Spalte, Zeile)
    atlas_imgs = []
    layers = {L: [] for L in LAYERS}
    jetty = []
    for (x, y), (code, top) in sorted(cells.items()):
        var = int(rnd("var", x, y) * 3)
        for L, top_kind, exp, cut in column_kinds(code, top):
            def neighbour_style(dx, dy):
                n = cells.get((x + dx, y + dy))
                if n is None:
                    return cut
                return exp
            ls = neighbour_style(0, 1)                 # linke Fläche zeigt nach +y
            rs = neighbour_style(1, 0)                 # rechte Fläche zeigt nach +x
            # Wasserquerschnitt nur, wo kein Wasser davor liegt
            v = var if top_kind in ("flag", "grass", "grass_hi", "rocktop", "sandtop", "water") else 0
            key = (top_kind, v, ls, rs, L)
            if key not in tiles:
                nfr = FRAMES if top_kind == "water" else 1
                col = 0
                row = len(atlas_imgs)
                imgs = [make_cube(top_kind, v, ls, rs, L, f) for f in range(nfr)]
                atlas_imgs.append(imgs)
                tiles[key] = (col, row, nfr)
            c, r, nfr = tiles[key]
            layers[L].append([x, y, c, r])
        if code == "J":
            jetty.append([x, y, 0, 0])
    # Atlas: eine Zeile je Kachel, Animationsbilder nebeneinander
    nrow = len(atlas_imgs)
    atlas = np.zeros((nrow * CH, FRAMES * TW, 4), np.uint8)
    for r, imgs in enumerate(atlas_imgs):
        for f, im in enumerate(imgs):
            atlas[r * CH:(r + 1) * CH, f * TW:(f + 1) * TW] = im
    (ENTRY / "demo/art").mkdir(parents=True, exist_ok=True)
    (ENTRY / "demo/map").mkdir(parents=True, exist_ok=True)
    (ENTRY / "assets/tiles").mkdir(parents=True, exist_ok=True)
    Image.fromarray(atlas).save(ENTRY / "demo/art/tiles.png")
    Image.fromarray(atlas).save(ENTRY / "assets/tiles/tiles.png")
    jet = make_jetty()
    Image.fromarray(jet).save(ENTRY / "demo/art/jetty.png")
    Image.fromarray(jet).save(ENTRY / "assets/tiles/jetty.png")
    meta = {
        "tile_size": [TW, TT], "cube": [TW, CH], "block_h": BH, "water_drop": WATER_DROP, "frames": FRAMES,
        "origin": list(ORIGIN), "size": [W, H],
        "layers": {str(L): v for L, v in layers.items()},
        "animated_rows": sorted(r for (k, _, _, _, _), (c, r, n) in tiles.items() if n > 1),
        "jetty": jetty, "jetty_layer": 0,
        "tiles": [{"key": list(map(str, k)), "row": r, "frames": n} for k, (c, r, n) in tiles.items()],
        "cells": {f"{x},{y}": [code, top] for (x, y), (code, top) in cells.items()},
    }
    json.dump(meta, open(ENTRY / "demo/map/harbour.json", "w"), indent=1)
    Image.fromarray(atlas).resize((atlas.shape[1] * 4, atlas.shape[0] * 4), Image.NEAREST).save(
        ENTRY / "assets/tiles/atlas_x4.png")
    # Vorschau: Python-Zusammensetzung (gleiche Reihenfolge wie Godot: Ebene für Ebene, darin hinten nach vorn)
    prev = compose(meta, atlas, jet, frame=0)
    Image.fromarray(prev).save(ENTRY / "assets/tiles/preview_map.png")
    print("Kacheln", len(tiles), "Atlaszeilen", nrow, "Zellen", sum(len(v) for v in layers.values()))


def compose(meta, atlas, jet, frame=0, size=(426, 240)):
    out = np.zeros((size[1], size[0], 4), np.uint8)
    ox, oy = meta["origin"]

    def blit(im, px, py):
        h, w = im.shape[:2]
        for j in range(h):
            yy_ = py + j
            if not 0 <= yy_ < size[1]:
                continue
            for i in range(w):
                xx_ = px + i
                if 0 <= xx_ < size[0] and im[j, i, 3]:
                    out[yy_, xx_] = im[j, i]
    for L in LAYERS:
        cl = sorted(meta["layers"][str(L)], key=lambda c: (c[0] + c[1], c[0]))
        for x, y, c, r in cl:
            f = frame % FRAMES if r in meta["animated_rows"] else 0
            im = atlas[r * CH:(r + 1) * CH, f * TW:(f + 1) * TW]
            px = ox + 16 * (x - y) - 16
            py = oy + 8 * (x + y) - 8 * L - 8
            blit(im, px, py)
        if L == -1:
            for x, y, _, _ in sorted(meta["jetty"], key=lambda c: c[0] + c[1]):
                px = ox + 16 * (x - y) - 16
                py = oy + 8 * (x + y) - 8 * 0 - 8
                blit(jet, px, py)
    return out


if __name__ == "__main__":
    main()
