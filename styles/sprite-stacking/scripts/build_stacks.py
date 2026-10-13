#!/usr/bin/env python3
"""Baut aus Voxeln die Schichtblätter (Sprite-Stacks) der Demo.

    .venv/bin/python styles/sprite-stacking/scripts/build_stacks.py

Eingaben: assets/voxels/*.npz (von blender/voxelize.py aus shared/3d), dazu prozedurale Modelle aus einfachen
Formen (Gelände mit Kai, Steg, Poller, Paket, Möwe, Rauch).
Ausgaben in demo/stacks/:
  <name>.png     Datenblatt: je Zelle (Bild x Schicht) R = Material (Zeile in ramps.png), G = Verdeckung,
                 B = Musterversatz (Bits 0-3, 8 = 0) + Eigenschatten (Bit 4), A = belegt
  <name>_n.png   Normalen (xyz * 0,5 + 0,5) im Modellraum
  ramps.png      8 Tonstufen je Material (Spalte 0 = tiefster Schatten, 7 = Spitzlicht)
  water.png      Wasserkarte in Weltkoordinaten: R = Ufernähe, G = Schatten des Geländes auf dem Wasser
  stacks.json    Zellen, Drehpunkte, Szenenaufbau, Licht
Vorschauen in assets/preview/.
"""
import json, math, pathlib, sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from voxlib import LAYER_H, blur3, exposed, hash3, normals, occlusion, self_shadow, shelf_pack  # noqa: E402

ENTRY = pathlib.Path(__file__).resolve().parent.parent
VOX = ENTRY / "assets" / "voxels"
OUT = ENTRY / "demo" / "stacks"
PREV = ENTRY / "assets" / "preview"

# Licht in Weltkoordinaten (x Osten, y Süden, z oben): tief stehende Abendsonne aus Westsüdwest
SUN = np.array([-0.86, 0.22, 0.34])
SUN = SUN / np.linalg.norm(SUN)
# Schlagschatten bewusst kürzer als bei dieser tiefen Sonne (sonst lägen Häuschen und Leuchtturm 140 px lang über
# dem Kai): gleiche Richtung, 0,6 Rasterweiten je Schicht Höhe. Eigenschatten und Wasserschatten nutzen dasselbe.
SHADOW_LEN = 0.6
_az = -SUN[:2] / np.linalg.norm(SUN[:2])
SHADOW_STEP = _az * SHADOW_LEN                       # Weltversatz des Schattens je Schicht Höhe
SHADOW_SUN = np.array([-_az[0], -_az[1], LAYER_H / SHADOW_LEN])
SHADOW_SUN = SHADOW_SUN / np.linalg.norm(SHADOW_SUN)

# ---------------------------------------------------------------- Materialien und Farbleitern
MATERIALS = [  # Name, Grundfarbe (sRGB), Art
    ("Stone", "958C7D", "lit"), ("StoneDark", "625A53", "lit"), ("Wood", "9C6B40", "lit"),
    ("WoodDark", "5A3B2A", "lit"), ("WhitePaint", "EDE6D6", "lit"), ("RedPaint", "C8332B", "lit"),
    ("Roof", "56628A", "lit"), ("Rope", "CCAE78", "lit"), ("Metal", "44464E", "lit"),
    ("Rock", "7C6F64", "lit"), ("Sand", "D2BB8A", "lit"), ("Grass", "5E7C3A", "lit"),
    ("FurDark", "4B3F3C", "lit"), ("FurLight", "F4E8D0", "lit"), ("Cap", "3E6534", "lit"),
    ("Brass", "DDA93C", "lit"), ("Vest", "4F803A", "lit"), ("Shirt", "F2E0BC", "lit"),
    ("Scarf", "D0302E", "lit"), ("Satchel", "844628", "lit"), ("Parcel", "CC945A", "lit"),
    ("Nose", "221917", "lit"), ("Eye", "160D0A", "lit"), ("Cobble", "8E857A", "lit"),
    ("Kerb", "AAA192", "lit"), ("Plank", "93683F", "lit"), ("Gull", "F4F1EC", "lit"),
    ("GullWing", "A4ABB8", "lit"), ("Beak", "EBA230", "lit"), ("Smoke", "C4BCC4", "lit"),
    ("Moss", "526036", "lit"),
    ("GlassWindow", "FFC860", "glow"), ("GlassLantern", "FFD070", "glow"), ("GlassLamp", "FFF0B0", "glow"),
]
MID = {n: i + 1 for i, (n, _, _) in enumerate(MATERIALS)}       # Zeile in ramps.png
GLOW_START = MID["GlassWindow"]

# Tonstufen: Helligkeit e und Sonnenanteil f je Stufe; Schatten bekommen das kühle Himmelslicht, Lichter das warme
E = [0.15, 0.25, 0.37, 0.51, 0.67, 0.85, 1.05, 1.28]
F = [0.0, 0.04, 0.12, 0.28, 0.48, 0.66, 0.82, 0.92]
SKY = np.array([0.50, 0.55, 1.00])
SUNC = np.array([1.00, 0.62, 0.40])
GLOW = ["4A2412", "7A3412", "B25214", "E07A1C", "F6A232", "FFC456", "FFE08C", "FFF6D2"]


def srgb2lin(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin2srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def hexrgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)]) / 255.0


def lum(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def build_ramps():
    img = np.zeros((len(MATERIALS) + 1, 8, 4), np.uint8)
    img[0] = (255, 0, 255, 255)
    for i, (name, base, kind) in enumerate(MATERIALS):
        if kind == "glow":
            for k in range(8):
                img[i + 1, k, :3] = (hexrgb(GLOW[k]) * 255).round()
        else:
            b = srgb2lin(hexrgb(base))
            for k in range(8):
                light = (1 - F[k]) * SKY + F[k] * SUNC
                light = light / lum(light)
                c = lin2srgb(b * light * E[k] * 1.25)
                img[i + 1, k, :3] = (c * 255).round()
        img[i + 1, :, 3] = 255
    return img


# ---------------------------------------------------------------- Muster (Versatz in Tonstufen, -2..+2)
def pat_blocks(X, Y, Z, bw=5, bh=3, seed=1):
    u = X + Y
    row = Z // bh
    off = (row % 2) * (bw // 2 + 1)
    joint = (Z % bh == 0) | ((u + off) % bw == 0)
    blk = hash3((u + off) // bw, row, 0, seed)
    v = np.where(blk < 0.25, -1, np.where(blk > 0.85, 1, 0))
    return np.where(joint, -1, v)


def pat_rows(X, Y, Z, period=3, seed=2):
    """Planken bzw. Schindeln: jede Reihe eigener Ton, dunkle Fuge."""
    row = Z // period
    r = hash3(row, (X + Y) // 7, 0, seed)
    v = np.where(r < 0.3, -1, np.where(r > 0.8, 1, 0))
    return np.where(Z % period == 0, -1, v)


def pat_noise(X, Y, Z, p_dark=0.18, p_light=0.10, seed=3, cell=1):
    r = hash3(X // cell, Y // cell, Z // cell, seed)
    return np.where(r < p_dark, -1, np.where(r > 1 - p_light, 1, 0))


def pat_slate(X, Y, Z, seed=4):
    row = Z // 2
    u = X + Y + (row % 2) * 2
    r = hash3(u // 4, row, 0, seed)
    v = np.where(r < 0.3, -1, np.where(r > 0.8, 1, 0))
    return np.where((Z % 2 == 0) | (u % 4 == 0), v - 1, v)


PATTERNS = {"blocks": pat_blocks, "rows": pat_rows, "noise": pat_noise, "slate": pat_slate}


# ---------------------------------------------------------------- Modelle
class Model:
    def __init__(self, name, mats, pivot, static=True, sun_angle=0.0, patterns=None, dither=0.0, ao=True):
        self.name = name
        self.mats = mats                    # uint8 [F, Z, Y, X] Materialzeilen (0 = leer)
        self.pivot = pivot                  # (Spalte, Zeile, Schicht) des Ursprungs
        self.static = static                # fest in der Welt -> Eigenschatten einbacken
        self.sun_angle = sun_angle          # Drehung des Modells in der Welt (für den Eigenschatten), Grad
        self.patterns = patterns or {}      # Materialname -> Mustername
        self.dither = dither
        self.ao = ao


def from_npz(path, remap=None):
    d = np.load(path)
    names = [str(n) for n in d["names"]]
    lut = np.zeros(256, np.uint8)
    for i, n in enumerate(names):
        n2 = (remap or {}).get(n, n)
        lut[i + 1] = MID.get(n2, 0) if n2 else 0
    return lut[d["mat"]], tuple(float(v) for v in d["pivot"])


def ellipsoid(shape, c, r):
    Z, Y, X = np.indices(shape)
    return (((X + 0.5 - c[0]) / r[0]) ** 2 + ((Y + 0.5 - c[1]) / r[1]) ** 2 + ((Z + 0.5 - c[2]) / r[2]) ** 2) <= 1


def cylinder(shape, c, r, z0, z1):
    Z, Y, X = np.indices(shape)
    return (((X + 0.5 - c[0]) ** 2 + (Y + 0.5 - c[1]) ** 2) <= r * r) & (Z >= z0) & (Z < z1)


def model_bollard():
    s = (10, 9, 9)
    v = np.zeros(s, np.uint8)
    v[cylinder(s, (4.5, 4.5), 2.6, 0, 8)] = MID["Metal"]
    v[cylinder(s, (4.5, 4.5), 3.6, 6, 8)] = MID["Metal"]
    v[cylinder(s, (4.5, 4.5), 1.8, 8, 9)] = MID["Metal"]
    return Model("bollard", v[None], (4.5, 4.5, 0))


def model_parcel():
    s = (8, 9, 12)
    v = np.zeros(s, np.uint8)
    v[0:7, 1:8, 1:11] = MID["Parcel"]
    v[0:7, 4, 1:11] = MID["Shirt"]          # Schnur über Kreuz
    v[0:7, 1:8, 6] = MID["Shirt"]
    v[6, 1:8, 1:11] = np.where(v[6, 1:8, 1:11] == MID["Shirt"], MID["Shirt"], MID["Parcel"])
    return Model("parcel", v[None], (6, 4.5, 0))


def model_parcel_big():
    """Paket für das Ansichtsfenster der Oberfläche: Packpapier, Schnur über Kreuz, Adresszettel, Siegel."""
    s = (15, 18, 24)
    v = np.zeros(s, np.uint8)
    v[0:13, 2:16, 2:22] = MID["Parcel"]
    v[12, 3:15, 3:21] = MID["Parcel"]
    v[0:13, 8:10, 2:22] = MID["Shirt"]                 # Schnur längs
    v[0:13, 2:16, 11:13] = MID["Shirt"]                # Schnur quer
    v[13, 8:10, 10:14] = MID["Shirt"]                  # Knoten
    v[13, 7:11, 11:13] = MID["Shirt"]
    v[12, 3:7, 4:10] = MID["WhitePaint"]               # Adresszettel
    v[12, 4, 5:9] = MID["Metal"]
    v[12, 5, 5:8] = MID["Metal"]
    v[12, 11:14, 16:19] = MID["RedPaint"]              # Siegel
    v[0:12, 15, 15:19] = np.where(np.arange(12)[:, None] % 4 == 1, MID["RedPaint"], v[0:12, 15, 15:19])
    return Model("parcel_big", v[None], (12.0, 9.0, 0), static=False,
                 patterns={"Parcel": "noise"})


def model_gull():
    """Möwe nach Osten (+x), drei Flügelstellungen: oben, Mitte, unten."""
    frames = []
    for tip in (6, 1, -4):
        s = (14, 27, 19)
        v = np.zeros(s, np.uint8)
        Z, Y, X = np.indices(s)
        cy = 13.5
        body = ((X + 0.5 - 8.5) / 6.0) ** 2 + ((Y + 0.5 - cy) / 2.3) ** 2 + ((Z + 0.5 - 6.0) / 2.6) ** 2 <= 1
        head = ((X + 0.5 - 14.5) / 2.3) ** 2 + ((Y + 0.5 - cy) / 2.0) ** 2 + ((Z + 0.5 - 7.2) / 2.4) ** 2 <= 1
        beak = (X >= 16) & (X <= 18) & (np.abs(Y + 0.5 - cy) <= 0.6) & (Z >= 6) & (Z <= 7)
        tail = (X >= 1) & (X <= 3) & (np.abs(Y + 0.5 - cy) <= 1.6) & (Z >= 5) & (Z <= 6)
        v[body | head | tail] = MID["Gull"]
        v[beak] = MID["Beak"]
        for side in (-1, 1):                  # Flügel als gebogene Platten, Spitzen dunkel
            for k in range(1, 12):
                y = int(round(cy + side * (1.6 + k))) - (1 if side < 0 else 0)
                zt = 6 + int(round(tip * (k / 11.0) ** 1.4))
                xs = range(6, 12) if k < 7 else range(6, 11 - (k - 7) // 2)
                for x in xs:
                    if 0 <= y < s[1] and 0 <= zt < s[0]:
                        v[zt, y, x] = MID["GullWing"] if k < 9 else MID["Metal"]
        frames.append(v)
    return Model("gull", np.stack(frames), (8.5, 13.5, 6.0), static=False, ao=False)


def model_smoke():
    """Rauchballen in sechs Größen (Bilder 0-5)."""
    frames = []
    s = (12, 13, 13)
    for r in (1.6, 2.3, 3.0, 3.7, 4.4, 5.1):
        v = np.zeros(s, np.uint8)
        v[ellipsoid(s, (6.5, 6.5, 6.0), (r, r, r / LAYER_H * 0.95))] = MID["Smoke"]
        frames.append(v)
    return Model("smoke", np.stack(frames), (6.5, 6.5, 6.0), static=False, ao=False)


# ---------------------------------------------------------------- Szene (Weltmaß: 1 Rasterweite = 1 Bildpixel)
LAYOUT = {
    "view": [426, 240],
    "scene_h": 182,                 # darunter liegt die Textleiste
    "pivot": [213.0, 96.0],         # Weltpunkt in der Bildmitte der Szene
    "center": [213.0, 96.0],
    "quay_h": 9,                    # Kai: Schichten 0-8, Oberfläche in Schicht 8, Gegenstände ab Schicht 9
    "jetty": {"x0": 252, "x1": 276, "y0": 30, "y1": 120, "deck": 8},
    "walk": {"y": 158.0, "x0": 58.0, "x1": 184.0},
}
TERR = {"x0": -64, "y0": -184, "w": 576, "h": 576}


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def value_noise(X, Y, cell, seed):
    gx, gy = X / cell, Y / cell
    x0, y0 = np.floor(gx).astype(int), np.floor(gy).astype(int)
    fx, fy = gx - x0, gy - y0
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a = hash3(x0, y0, 0, seed); b = hash3(x0 + 1, y0, 0, seed)
    c = hash3(x0, y0 + 1, 0, seed); d = hash3(x0 + 1, y0 + 1, 0, seed)
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def terrain():
    """Höhenfeld in Schichten (0 = Wasser) mit Oberflächenmaterial, daraus ein Voxelvolumen."""
    W, H, x0, y0 = TERR["w"], TERR["h"], TERR["x0"], TERR["y0"]
    X, Y = np.meshgrid(np.arange(W) + x0 + 0.5, np.arange(H) + y0 + 0.5)
    n1 = value_noise(X, Y, 23, 11) - 0.5
    n2 = value_noise(X, Y, 9, 12) - 0.5
    qh = LAYOUT["quay_h"]
    h = np.zeros((H, W))
    # Kai (gerade Kante bei y = 120, Ostende bei x = 318) und Hof westlich davon
    quay = (Y >= 120) & (X <= 318)
    yard = (X <= 70 + 6 * n1) & (Y >= 94 + 8 * n2) & ~quay
    h[quay | yard] = qh
    # Westhügel: Terrassen (4 Schichten) bis etwa 25 Schichten, Felsküste nach Osten und Norden
    dh = np.hypot((X + 70) / 150.0, (Y - 6) / 118.0) + 0.14 * n1 + 0.05 * n2
    hill = np.where(dh < 1.0, 5 + 21 * smoothstep(1.0, 0.45, dh), 0)
    hill = np.where(hill > 0, np.floor(hill / 4.0) * 4.0 + 1.0, 0)
    hill = np.where((Y > 88) & (hill > 0), np.maximum(hill, qh), hill)
    h = np.maximum(h, np.where(~quay, hill, 0))
    # Felsnase: steile Kanten, Terrassen zu 3 Schichten, Plateau (19) für den Leuchtturm, Steilküste nach Süden
    dn = np.hypot((X - 392) / 64.0, (Y - 50) / 104.0) + 0.12 * n1 + 0.05 * n2
    head = np.where(dn < 0.97, 10 + 7 * smoothstep(0.97, 0.35, dn), 0)
    head = np.where(head > 0, np.floor(head / 3.0) * 3.0 + 1.0, 0)
    plate = np.hypot((X - 388) / 25.0, (Y - 114) / 20.0) + 0.06 * n2
    head = np.where(plate < 1.0, 19, np.where((plate < 1.6) & (head > 0), np.maximum(head, 16), head))
    h = np.maximum(h, head)
    # Felsiger Übergang vom Ostende des Kais zur Felsnase
    ledge = (X > 312) & (X < 350) & (Y > 112) & (Y < 136) & (np.hypot((X - 334) / 22.0, (Y - 124) / 13.0) + 0.3 * n2 < 1)
    h = np.where(ledge, np.maximum(h, np.floor(8 + 4 * (0.5 + n1))), h)
    # Felsbrocken im Wasser
    for cx, cy, r, hh in ((150, 40, 10, 5), (172, 22, 6, 3), (96, 66, 7, 4), (205, -30, 8, 4),
                          (348, 168, 8, 5), (370, 178, 5, 3), (318, 6, 9, 5)):
        d = np.hypot(X - cx, Y - cy) / r + 0.25 * n2
        h = np.maximum(h, np.where(d < 1, np.ceil(hh * (1 - d * d) + 0.5), 0))
    h = np.floor(h).astype(int)
    h[quay] = qh                                   # Kai bleibt eben
    nz = int(h.max()) + 1
    Z = np.arange(nz)[:, None, None]
    occ = Z < h[None]
    # Oberflächenmaterial je Säule
    hp = np.pad(h, 2, mode="edge")
    flat = np.ones(h.shape, bool)
    for dy in (-2, 0, 2):
        for dx in (-2, 0, 2):
            flat &= hp[2 + dy:2 + dy + h.shape[0], 2 + dx:2 + dx + h.shape[1]] >= h - 1
    top = np.full(h.shape, MID["Rock"], np.uint8)
    grassy = flat & (h >= 7) & ~quay
    top[grassy] = MID["Grass"]
    top[(h <= 3) & flat] = MID["Sand"]
    top[quay] = MID["Cobble"]
    kerb = quay & (((Y < 126) & (X > 70)) | (X > 312))
    top[kerb] = MID["Kerb"]
    mats = np.zeros(occ.shape, np.uint8)
    ZZ = np.broadcast_to(Z, occ.shape)
    is_top = ZZ == (h[None] - 1)
    side_mat = np.where(quay | (yard & (h <= qh)), MID["StoneDark"], MID["Rock"]).astype(np.uint8)
    mats[:] = np.where(is_top, top[None], side_mat[None])
    # Gras hängt eine Schicht über die Kante, darunter Moos an der Wasserlinie
    mats[(ZZ == h[None] - 2) & (top[None] == MID["Grass"])] = MID["Grass"]
    mats[(ZZ <= 1) & (side_mat[None] == MID["Rock"])] = MID["Moss"]
    mats[~occ] = 0
    return mats, h, quay, kerb


def decor_positions(h, top_grass, seed=5):
    """Büsche, Grasbüschel und Steine auf flachen Grasflächen im sichtbaren Bereich (fester Seed)."""
    rng = np.random.default_rng(seed)
    out, used = [], []
    plan = [("bush", 14, 11), ("tuft", 30, 6), ("stone", 8, 7)]
    for name, count, dist in plan:
        tries = 0
        while sum(1 for o in out if o[0] == name) < count and tries < 4000:
            tries += 1
            x = rng.uniform(-50, 470)
            y = rng.uniform(-110, 176)
            ix, iy = int(x - TERR["x0"]), int(y - TERR["y0"])
            if not top_grass[iy, ix]:
                continue
            hh = int(h[iy, ix])
            win = h[iy - 3:iy + 4, ix - 3:ix + 4]
            if win.min() != hh or win.max() != hh:
                continue
            if (x < 64 and 96 < y < 160) or np.hypot(x - 388, y - 114) < 16 or (x < 110 and y > 120):
                continue
            if any(np.hypot(x - u, y - v) < max(dist, d2) for u, v, d2 in used):
                continue
            used.append((x, y, dist))
            out.append((name, round(float(x), 1), round(float(y), 1), hh, round(float(rng.uniform(0, 360)), 1)))
    return out


def model_bush():
    s = (9, 13, 13)
    v = np.zeros(s, np.uint8)
    Z, Y, X = np.indices(s)
    blob = np.zeros(s, bool)
    for cx, cy, cz, r in ((6.5, 6.5, 3.0, 5.0), (4.5, 7.5, 3.5, 3.4), (8.5, 5.5, 4.0, 3.2), (6.5, 6.0, 5.6, 3.0)):
        blob |= ((X + 0.5 - cx) / r) ** 2 + ((Y + 0.5 - cy) / r) ** 2 + ((Z + 0.5 - cz) / (r * 0.95 / LAYER_H)) ** 2 <= 1
    leaf = hash3(X, Y, Z, 41)
    blob &= ~((leaf < 0.18) & (Z > 2))                 # lockere Ränder
    v[blob] = MID["Grass"]
    v[blob & (leaf > 0.82)] = MID["Moss"]
    return Model("bush", v[None], (6.5, 6.5, 0), patterns={"Grass": "noise"})


def model_tuft():
    s = (4, 5, 5)
    v = np.zeros(s, np.uint8)
    for (x, y, zt) in ((2, 2, 4), (1, 2, 3), (3, 1, 3), (2, 3, 2), (3, 3, 3), (1, 1, 2)):
        v[0:zt, y, x] = MID["Grass"]
    v[0, 1:4, 1:4] = MID["Moss"]
    return Model("tuft", v[None], (2.5, 2.5, 0), ao=False)


def model_stone():
    s = (5, 7, 8)
    v = np.zeros(s, np.uint8)
    v[ellipsoid(s, (4.0, 3.5, 0.6), (3.6, 2.8, 3.8))] = MID["Rock"]
    return Model("stone", v[None], (4.0, 3.5, 0), patterns={"Rock": "noise"})


def terrain_variation(mats, quay, kerb):
    nz, ny, nx = mats.shape
    Z, Y, X = np.indices(mats.shape)
    Xw, Yw = X + TERR["x0"], Y + TERR["y0"]
    var = np.zeros(mats.shape, np.int8)
    # Pflaster: versetzte Steine 6 x 4, Fugen dunkel, einzelne Steine heller/dunkler
    row = Yw // 4
    off = (row % 2) * 3
    joint = (Yw % 4 == 0) | ((Xw + off) % 6 == 0)
    stone = hash3((Xw + off) // 6, row, 0, 21)
    cob = np.where(joint, -2, np.where(stone < 0.22, -1, np.where(stone > 0.82, 1, 0)))
    m = mats == MID["Cobble"]
    var[m] = cob[m]
    # Kantensteine: Blöcke von 9 px
    kj = (Xw % 9 == 0) | (Yw == 125)
    m = mats == MID["Kerb"]
    var[m] = np.where(kj, -1, np.where(hash3(Xw // 9, 0, 0, 22) > 0.7, 1, 0))[m]
    # Kaimauer
    m = mats == MID["StoneDark"]
    var[m] = pat_blocks(Xw, Yw, Z, 6, 3, 23)[m]
    # Fels: grobe Flecken + feines Rauschen
    coarse = hash3(Xw // 3, Yw // 3, Z // 2, 24)
    fine = hash3(Xw, Yw, Z, 25)
    rock = np.where(coarse < 0.3, -1, np.where(coarse > 0.8, 1, 0)) + np.where(fine < 0.1, -1, 0)
    m = (mats == MID["Rock"]) | (mats == MID["Moss"])
    var[m] = np.clip(rock, -2, 1)[m]
    m = mats == MID["Grass"]
    g = hash3(Xw, Yw, 0, 26)
    tuft = hash3(Xw // 2, Yw // 3, 0, 27)
    var[m] = np.where(g < 0.16, -1, np.where((g > 0.9) | (tuft > 0.93), 1, 0))[m]
    m = mats == MID["Sand"]
    var[m] = np.where(hash3(Xw, Yw, Z, 28) < 0.2, -1, 0)[m]
    return var


def model_jetty():
    j = LAYOUT["jetty"]
    w, l = j["x1"] - j["x0"], j["y1"] - j["y0"]
    nz = 14
    v = np.zeros((nz, l, w), np.uint8)
    var = np.zeros(v.shape, np.int8)
    deck = j["deck"]                       # oberste Deckschicht
    Z, Y, X = np.indices(v.shape)
    # Planken quer, 3 px breit, 1 px Fuge; Längsträger darunter; Pfähle an den Ecken und in der Mitte
    plank = (Y % 4 != 3) & (Z >= deck - 1) & (Z <= deck) & (X >= 1) & (X < w - 1)
    v[plank] = MID["Plank"]
    var[plank] = np.where(hash3(Y // 4, 0, 0, 31) < 0.3, -1, np.where(hash3(Y // 4, 1, 0, 31) > 0.75, 1, 0))[plank]
    var[plank & ((X == 1) | (X == w - 2))] -= 1
    beam = ((X == 3) | (X == 4) | (X == w - 5) | (X == w - 4)) & (Z >= deck - 3) & (Z < deck - 1)
    v[beam] = MID["WoodDark"]
    for py in (2, 26, 50, l - 3):
        for px in (1, w - 2):
            post = (np.abs(X - px) <= 1) & (np.abs(Y - py) <= 1) & (Z <= (deck + 5 if py == 2 else deck - 1))
            v[post] = MID["WoodDark"]
    return Model("jetty", v[None], (0.0, 0.0, 0.0), patterns={}, dither=0.0), var


def pattern_var(model):
    F, Z, Y, X = np.indices(model.mats.shape)
    var = np.zeros(model.mats.shape, np.int8)
    for mname, pname in model.patterns.items():
        m = model.mats == MID[mname]
        if m.any():
            var[m] = PATTERNS[pname](X[m], Y[m], Z[m])
    return var


# ---------------------------------------------------------------- Ausgabe
def export(model, var=None, dither_override=None):
    mats = model.mats
    nf, nz, ny, nx = mats.shape
    occ = mats > 0
    var = pattern_var(model) if var is None else var.reshape(mats.shape)
    data = np.zeros(mats.shape + (4,), np.uint8)
    nrm = np.zeros(mats.shape + (4,), np.uint8)
    vis = np.zeros(mats.shape, bool)
    for f in range(nf):
        o = occ[f]
        n = normals(o, 1, 1)
        ao = occlusion(o) if model.ao else np.ones(o.shape, np.float32)
        sh = np.zeros(o.shape, bool)
        if model.static:
            a = math.radians(-model.sun_angle)       # Sonne in Modellkoordinaten
            S = SHADOW_SUN
            sl = (S[0] * math.cos(a) - S[1] * math.sin(a), S[0] * math.sin(a) + S[1] * math.cos(a), S[2])
            sh = self_shadow(o, sl, steps=int(2 * max(o.shape) + 10))
        vis[f] = exposed(o)
        data[f, ..., 0] = mats[f]
        data[f, ..., 1] = np.clip(ao * 255, 0, 255).astype(np.uint8)
        data[f, ..., 2] = (np.clip(var[f], -7, 7) + 8).astype(np.uint8) | (sh.astype(np.uint8) << 4)
        data[f, ..., 3] = np.where(vis[f], 255, 0)
        nrm[f, ..., :3] = np.clip(n * 127.5 + 127.5, 0, 255).astype(np.uint8)
        nrm[f, ..., 3] = data[f, ..., 3]
    # Zellen: je Bild und Schicht auf die belegten Voxel zuschneiden
    cells, sizes = [], []
    for f in range(nf):
        for z in range(nz):
            m = vis[f, z]
            if not m.any():
                cells.append(None)
                continue
            ys, xs = np.nonzero(m)
            cells.append((f, z, xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
            sizes.append((xs.max() + 1 - xs.min(), ys.max() + 1 - ys.min()))
    width = 4096 if max(nx, ny) > 200 else 1024
    pos, height = shelf_pack(sizes, width)
    atlas_w = min(width, max(p[0] + s[0] for p, s in zip(pos, sizes)))
    A = np.zeros((height, atlas_w, 4), np.uint8)
    N = np.zeros((height, atlas_w, 4), np.uint8)
    out_cells = []
    k = 0
    for c in cells:
        if c is None:
            out_cells.append(None)
            continue
        f, z, xa, ya, xb, yb = c
        px, py = pos[k]
        k += 1
        A[py:py + yb - ya, px:px + xb - xa] = data[f, z, ya:yb, xa:xb]
        N[py:py + yb - ya, px:px + xb - xa] = nrm[f, z, ya:yb, xa:xb]
        # Rechteck im Blatt und Lage der linken oberen Ecke relativ zum Drehpunkt
        out_cells.append([int(px), int(py), int(xb - xa), int(yb - ya),
                          round(xa - model.pivot[0], 3), round(ya - model.pivot[1], 3)])
    # Ankerpunkte relativ zum Drehpunkt (x, y in Rasterweiten, z in Schichten): leuchtende Teile, Spitze
    anchors = {}
    m0 = mats[0]
    glow = m0 >= GLOW_START
    if glow.any():
        z, y, x = np.nonzero(glow)
        anchors["glow"] = [float(x.mean() + 0.5 - model.pivot[0]), float(y.mean() + 0.5 - model.pivot[1]),
                           float(z.mean() + 0.5 - model.pivot[2])]
        south = y >= np.percentile(y, 70)
        anchors["glow_south"] = [float(x[south].mean() + 0.5 - model.pivot[0]),
                                 float(y[south].mean() + 0.5 - model.pivot[1]),
                                 float(z[south].mean() + 0.5 - model.pivot[2])]
    z, y, x = np.nonzero(m0)
    top = z >= z.max() - 2
    anchors["top"] = [float(x[top].mean() + 0.5 - model.pivot[0]), float(y[top].mean() + 0.5 - model.pivot[1]),
                      float(z.max() + 1 - model.pivot[2])]
    Image.fromarray(A).save(OUT / f"{model.name}.png", optimize=True)
    Image.fromarray(N).save(OUT / f"{model.name}_n.png", optimize=True)
    return {
        "frames": nf, "layers": nz, "size": [nx, ny], "pivot_z": model.pivot[2],
        "cells": out_cells,     # Index = Bild * layers + Schicht
        "dither": model.dither if dither_override is None else dither_override,
        "voxels": int(occ.sum()), "visible": int(vis.sum()), "atlas": [int(atlas_w), int(height)],
        "anchors": anchors,
    }


def walk_advance(path, cycle_px):
    """Vorschub je Laufbild aus dem Standfuß: Schwerpunkt der Sohle (Schichten 0-1) des Fußes, der in beiden
    Bildern am Boden steht; auf die Zykluslänge der Animation skaliert (Abrollen verschiebt den Schwerpunkt)."""
    m = np.load(path)["mat"]
    nf, nz, ny, nx = m.shape
    feet = []
    for f in range(nf):
        row = {}
        for name, ys in (("L", slice(0, ny // 2)), ("R", slice(ny // 2, ny))):
            sole = m[f, 0:2, ys, :] > 0
            z, y, x = np.nonzero(sole)
            row[name] = (float(x.mean()) if len(x) else None, int((m[f, 0, ys, :] > 0).sum()))
        feet.append(row)
    diffs = []
    for f in range(nf):
        a, b = feet[f], feet[(f + 1) % nf]
        best = max(("L", "R"), key=lambda n: min(a[n][1], b[n][1]))
        diffs.append(a[best][0] - b[best][0])
    k = cycle_px / sum(diffs)
    return [round(d * k, 4) for d in diffs], [round(d, 3) for d in diffs]


def water_map(h):
    """R = Ufernähe (1 an der Kante, 0 ab 14 px), G = Schatten des Geländes auf der Wasserfläche."""
    land = h > 0
    d = np.full(h.shape, 99.0)
    ys, xs = np.nonzero(land)
    # Abstand per wiederholter Erosion (genügt bis 14 px)
    cur = land.copy()
    for k in range(1, 15):
        grown = cur.copy()
        grown[1:] |= cur[:-1]; grown[:-1] |= cur[1:]; grown[:, 1:] |= cur[:, :-1]; grown[:, :-1] |= cur[:, 1:]
        d[grown & ~cur] = k
        cur = grown
    near = np.clip(1 - (d - 1) / 13.0, 0, 1)
    near[land] = 1
    # Geländeschatten: Strahl zur Sonne über das Höhenfeld
    sh = np.zeros(h.shape, bool)
    sx, sy, sz = SHADOW_SUN
    hor = math.hypot(sx, sy)
    Y, X = np.indices(h.shape)
    for t in np.arange(1.0, 60.0, 0.7):
        px = np.round(X + sx / hor * t).astype(int)
        py = np.round(Y + sy / hor * t).astype(int)
        ok = (px >= 0) & (px < h.shape[1]) & (py >= 0) & (py < h.shape[0])
        hh = np.zeros(h.shape)
        hh[ok] = h[py[ok], px[ok]]
        sh |= hh * LAYER_H > t * sz / hor
    img = np.zeros(h.shape + (4,), np.uint8)
    img[..., 0] = (near * 255).astype(np.uint8)
    img[..., 1] = np.where(sh & ~land, 255, 0)
    img[..., 2] = np.clip(h * 8, 0, 255).astype(np.uint8)   # Geländehöhe in Schichten * 8
    img[..., 3] = 255
    Image.fromarray(img).save(OUT / "water.png", optimize=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    PREV.mkdir(parents=True, exist_ok=True)
    ramps = build_ramps()
    Image.fromarray(ramps).save(OUT / "ramps.png")
    Image.fromarray(ramps).resize((8 * 16, ramps.shape[0] * 16), Image.NEAREST).save(PREV / "ramps.png")

    models = []
    # Aus shared/3d voxelisiert
    badger = {"Glass": "GlassWindow"}
    for n in ("badger_walk", "badger_idle", "badger_wave"):
        m, p = from_npz(VOX / f"{n}.npz", badger)
        models.append(Model(n, m, p, static=False))
    m, p = from_npz(VOX / "cottage.npz", {"Glass": "GlassWindow"})
    models.append(Model("cottage", m, p, patterns={"Stone": "blocks", "Roof": "slate", "Wood": "rows", "StoneDark": "noise"}))
    m, p = from_npz(VOX / "lighthouse.npz", {"Glass": "GlassLamp"})
    models.append(Model("lighthouse", m, p, patterns={"StoneDark": "blocks"}))
    for n, ang in (("boat_a", -90.0), ("boat_b", -90.0)):
        m, p = from_npz(VOX / f"{n}.npz", {"Glass": "GlassWindow"})
        models.append(Model(n, m, p, static=True, sun_angle=ang, patterns={"Wood": "rows", "WhitePaint": "rows"}))
    m, p = from_npz(VOX / "barrel.npz")
    models.append(Model("barrel", m, p, patterns={"Wood": "rows"}))
    m, p = from_npz(VOX / "crates.npz")
    models.append(Model("crates", m, p, patterns={"Wood": "rows"}))
    m, p = from_npz(VOX / "rope.npz")
    models.append(Model("rope", m, p, patterns={"Rope": "noise"}))
    m, p = from_npz(VOX / "lantern.npz", {"Glass": "GlassLantern"})
    models.append(Model("lantern", m, p))
    # Prozedural
    models += [model_bollard(), model_parcel(), model_parcel_big(), model_gull(), model_smoke(), model_bush(), model_tuft(), model_stone()]

    manifest = {"materials": [n for n, _, _ in MATERIALS], "glow_start": GLOW_START, "layer_h": LAYER_H,
                "sun": [round(float(v), 4) for v in SUN], "shadow_step": [round(float(v), 4) for v in SHADOW_STEP],
                "layout": LAYOUT, "terrain": TERR, "stacks": {}}
    for m in models:
        manifest["stacks"][m.name] = export(m)
        print(f"{m.name}: {manifest['stacks'][m.name]['visible']} sichtbare Voxel, Blatt {manifest['stacks'][m.name]['atlas']}")
    jm, jvar = model_jetty()
    manifest["stacks"]["jetty"] = export(jm, jvar)
    tm, h, quay, kerb = terrain()
    tvar = terrain_variation(tm, quay, kerb)
    terr = Model("terrain", tm[None], (-TERR["x0"], -TERR["y0"], 0.0), static=True, dither=0.6)
    manifest["stacks"]["terrain"] = export(terr, tvar[None])
    print("terrain:", manifest["stacks"]["terrain"]["atlas"])
    water_map(h)
    top_mat = np.take_along_axis(tm, np.clip(h - 1, 0, None)[None], axis=0)[0]
    manifest["decor"] = decor_positions(h, (top_mat == MID["Grass"]) & (h > 0))
    adv, raw = walk_advance(VOX / "badger_walk.npz", 0.367 / 0.04)
    manifest["walk_advance"] = adv
    print("Vorschub je Laufbild:", adv, "Sohlenschwerpunkt:", raw)
    print("Deko:", len(manifest["decor"]))
    (OUT / "stacks.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False, default=lambda o: o.item()))
    print("ok")


if __name__ == "__main__":
    main()
