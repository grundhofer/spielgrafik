#!/usr/bin/env python3
"""Baut die Manuskriptseite (alles außer Miniatur, Figur und Text) aus Code: Pergament, Rahmen der Miniatur aus
Gold- und Farbleiste, Dornblattranken (Efeuranken) mit goldenen und farbigen Blättern und Goldpollen in allen
Rändern, Fleuronnée-Feld für die rote Initiale.

    .venv/bin/python styles/buchmalerei/scripts/build_page.py

Ausgabe (assets/):
  page.png       1280x720 RGB, die Seite
  page_gold.png  1280x720 RGB-Maske (nie Alpha): R = Blattgold-Deckung, G = Phase je Goldelement (für das
                 Aufblitzen), B = Relief (Punzierung und Knitter des Blattgolds)
  page.json      Lage von Miniaturfenster, Textspalte, Initialfeld (liest main.gd)

Gezeichnet wird doppelt groß (2560x1440) und mit Lanczos verkleinert. Zufall nur aus numpy RandomState(seed).
Farben aus der KI-Miniatur abgeleitet (Ultramarin, Zinnober, Rosa, Malachit, Bleiweiß, Gold).
"""
import json, math, pathlib

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "assets"
W, H = 1280, 720
K = 2                                    # Überabtastung
SEED = 20261013

WIN = (64, 48, 792, 524)                 # Miniaturfenster x, y, w, h
TEXT = (902, 40, 324, 548)               # Textspalte
INIT = (902, 92, 100, 100)               # Feld der Initiale (Fleuronnée), Buchstabe setzt Godot
DROLL_CLEAR = (972, 1130)                # x-Bereich ohne Ranken am unteren Stiel (dort steht die Drolerie)

INK = (52, 34, 24)
BLUE = (38, 62, 158)
BLUE_D = (24, 38, 110)
ROSE = (196, 98, 112)
ROSE_D = (150, 60, 74)
GREEN = (58, 112, 70)
GREEN_D = (34, 74, 46)
RED = (178, 44, 30)
WHITE = (246, 240, 224)
PARCH = (234, 219, 184)
PEN_BLUE = (44, 70, 160)

rs = np.random.RandomState(SEED)


def noise(h, w, cell, rs):
    g = rs.rand(h // cell + 3, w // cell + 3).astype(np.float32)
    im = Image.fromarray(g).resize(((w // cell + 3) * cell, (h // cell + 3) * cell), Image.BICUBIC)
    return np.array(im)[cell:cell + h, cell:cell + w]


# ---------------------------------------------------------------- Zeichenebenen (doppelt groß)
paint = Image.new("RGBA", (W * K, H * K), (0, 0, 0, 0))
gold = Image.new("L", (W * K, H * K), 0)
phase = Image.new("L", (W * K, H * K), 0)
white = Image.new("L", (W * K, H * K), 0)
ink = Image.new("L", (W * K, H * K), 0)
pen = Image.new("L", (W * K, H * K), 0)        # blaue Federzeichnung (Fleuronnée)
dp, dg, dph, dw, di, dpen = (ImageDraw.Draw(x) for x in (paint, gold, phase, white, ink, pen))


def S(p):
    return (p[0] * K, p[1] * K)


def line(d, pts, w, fill=255):
    pts = [S(p) for p in pts]
    d.line(pts, fill=fill, width=max(1, round(w * K)), joint="curve")
    r = w * K / 2
    for p in (pts[0], pts[-1]):
        d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=fill)


def poly(d, pts, fill):
    d.polygon([S(p) for p in pts], fill=fill)


def circle(d, c, r, fill=None, outline=None, width=1):
    x, y = c[0] * K, c[1] * K
    d.ellipse((x - r * K, y - r * K, x + r * K, y + r * K), fill=fill, outline=outline,
              width=max(1, round(width * K)) if outline is not None else 0)


def outline_poly(pts, w=1.1):
    line(di, list(pts) + [pts[0]], w)


# ---------------------------------------------------------------- Formen
def ivy_leaf(c, ang, L):
    """Stilisiertes Efeublatt (Dornblatt): Spitze in Richtung ang, zwei Seitenlappen, Kerbe am Stiel."""
    spec = [(0, 1.0), (28, 0.52), (62, 0.78), (105, 0.44), (150, 0.36), (180, 0.16),
            (210, 0.36), (255, 0.44), (298, 0.78), (332, 0.52)]
    pts = []
    for a, r in spec:
        t = math.radians(a) + ang
        pts.append((c[0] + math.cos(t) * r * L, c[1] + math.sin(t) * r * L))
    return pts


def spiral(p0, ang, length, curl, steps=40):
    """Ranke: läuft von p0 in Richtung ang los und rollt sich ein (curl > 0: rechtsherum)."""
    pts = [p0]
    x, y = p0
    a = ang
    ds = length / steps
    for i in range(steps):
        s = i / steps
        a += curl * (0.2 + 2.6 * s ** 1.6) / steps * 3.0
        x += math.cos(a) * ds
        y += math.sin(a) * ds
        pts.append((x, y))
    return pts, a


def tendril(p0, ang, length, curl, steps=50):
    """Offene Ranke: erst fast gerade aus dem Stiel hinaus, am Ende eng eingerollt."""
    pts = [p0]
    x, y = p0
    a = ang
    ds = length / steps
    for i in range(steps):
        s = i / steps
        a += curl * (0.35 + 7.0 * s ** 3.2) / steps
        x += math.cos(a) * ds
        y += math.sin(a) * ds
        pts.append((x, y))
    return pts


def bezant(c, r=2.4):
    """Goldpollen: Goldpunkt mit Tuschekontur."""
    circle(dg, c, r, fill=255)
    circle(dph, c, r + 0.5, fill=int(rs.randint(1, 255)))
    circle(di, c, r, outline=255, width=0.9)


def hair_spray(p, ang, L, n=3):
    """Haarranken mit Goldpollen am Ende."""
    for k in range(n):
        a = ang + (k - (n - 1) / 2) * 0.55
        pts, a2 = spiral(p, a, L * (0.8 + 0.3 * rs.rand()), 0.9 * (1 if k % 2 else -1), steps=14)
        line(di, pts, 0.7)
        bezant(pts[-1], 2.0)


def leaf(c, ang, L, kind):
    pts = ivy_leaf(c, ang, L)
    if kind == "gold":
        poly(dg, pts, 255)
        poly(dph, pts, int(rs.randint(1, 255)))
    else:
        col, dark = {"blue": (BLUE, BLUE_D), "rose": (ROSE, ROSE_D), "green": (GREEN, GREEN_D)}[kind]
        poly(dp, pts, col + (255,))
        # dunklere Hälfte (Modellierung) und weiße Mittelrippe
        half = [pts[0]] + pts[5:] + [pts[0]]
        poly(dp, half, dark + (255,))
        tip = pts[0]
        base = pts[5]
        line(dw, [base, ((base[0] * 0.3 + tip[0] * 0.7), (base[1] * 0.3 + tip[1] * 0.7))], 0.8)
    outline_poly(pts, 1.0)


def flower(c, r):
    """Vierpass-Blüte in Blau und Rosa mit Goldmitte (Knotenpunkte der Ranke)."""
    for k in range(4):
        a = k * math.pi / 2 + math.pi / 4
        pc = (c[0] + math.cos(a) * r * 0.62, c[1] + math.sin(a) * r * 0.62)
        circle(dp, pc, r * 0.55, fill=(BLUE if k % 2 else ROSE) + (255,))
        circle(di, pc, r * 0.55, outline=255, width=1.0)
        circle(dw, (pc[0] - r * 0.15, pc[1] - r * 0.15), r * 0.14, fill=255)
    circle(dg, c, r * 0.42, fill=255)
    circle(dph, c, r * 0.45, fill=int(rs.randint(1, 255)))
    circle(di, c, r * 0.42, outline=255, width=1.0)


def point_at(path, seg, pos):
    i, acc = 0, 0.0
    while i < len(seg) - 1 and acc + seg[i] < pos:
        acc += seg[i]
        i += 1
    f = min(1.0, (pos - acc) / seg[i])
    p = (path[i][0] + (path[i + 1][0] - path[i][0]) * f, path[i][1] + (path[i + 1][1] - path[i][1]) * f)
    return p, math.atan2(path[i + 1][1] - path[i][1], path[i + 1][0] - path[i][0])


def leaf_on(pts, frac, side, L, kind, spread=1.2):
    """Blatt mit kurzem Stiel an der Stelle frac einer Ranke, nach außen (side) gedreht."""
    j = min(len(pts) - 2, max(0, int(frac * (len(pts) - 1))))
    m = pts[j]
    ma = math.atan2(pts[j + 1][1] - m[1], pts[j + 1][0] - m[0])
    la = ma + side * spread
    stalk = (m[0] + math.cos(la) * L * 0.32, m[1] + math.sin(la) * L * 0.32)
    line(di, [m, stalk], 0.9)
    leaf((stalk[0] + math.cos(la) * L * 0.15, stalk[1] + math.sin(la) * L * 0.15), la, L, kind)


def vine(path, every, L_tendril, L_leaf, kinds, curl=2.2, stem_w=1.9, skip=None):
    """Hauptstiel entlang path; im Abstand every abwechselnd nach beiden Seiten eine eingerollte Ranke mit zwei
    Blättern und Goldpollen am Ende, dazwischen Haarranken mit Goldpollen."""
    line(di, path, stem_w)
    seg = [math.dist(path[i], path[i + 1]) for i in range(len(path) - 1)]
    total = sum(seg)
    pos, n, k = every * 0.5, 0, 0
    while pos < total - every * 0.3:
        p, tang = point_at(path, seg, pos)
        side = 1 if n % 2 == 0 else -1
        if skip and skip[0] <= p[0] <= skip[1]:
            pos += every
            n += 1
            continue
        Lt = L_tendril * (0.85 + 0.3 * rs.rand())
        pts = tendril(p, tang + side * 1.05, Lt, side * curl)
        line(di, pts, 1.15)
        leaf_on(pts, 0.42, -side, L_leaf * (0.95 + 0.15 * rs.rand()), kinds[k % len(kinds)])
        k += 1
        leaf_on(pts, 0.74, -side, L_leaf * (0.75 + 0.15 * rs.rand()), kinds[k % len(kinds)], spread=1.0)
        k += 1
        bezant(pts[-1], 2.4 if L_leaf > 12 else 2.0)
        # Haarranke zwischen den Knoten, zur Gegenseite
        q, tq = point_at(path, seg, min(total - 1, pos + every * 0.5))
        hair_spray(q, tq - side * 1.25, L_tendril * 0.42, n=3)
        pos += every
        n += 1


def wavy(p0, p1, amp, wl, n=200):
    pts = []
    L = math.dist(p0, p1)
    ux, uy = (p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L
    for i in range(n + 1):
        s = i / n
        o = amp * math.sin(s * L / wl * 2 * math.pi)
        pts.append((p0[0] + ux * s * L - uy * o, p0[1] + uy * s * L + ux * o))
    return pts


# ---------------------------------------------------------------- Miniaturrahmen
x, y, w, h = WIN
# von innen nach außen: Tusche 1.4, Farbleiste 6, Tusche 1.4, Gold 7, Tusche 1.4
def rect(off):
    return (x - off, y - off, x + w + off, y + h + off)

# Farbleiste (abwechselnd Blau und Rosa, Segmente ~64 px) mit weißen Perlen
band_in, band_out = 1.4, 7.4
bx0, by0, bx1, by1 = rect(band_out)
ix0, iy0, ix1, iy1 = rect(band_in)
segs = []
def band_segments(a, b, fixed, horizontal):
    n = max(1, round((b - a) / 64))
    st = (b - a) / n
    for k in range(n):
        segs.append((a + k * st, a + (k + 1) * st, fixed, horizontal, k))
band_segments(bx0, bx1, (by0, iy0), True)
band_segments(bx0, bx1, (iy1, by1), True)
band_segments(iy0, iy1, (bx0, ix0), False)
band_segments(iy0, iy1, (ix1, bx1), False)
for a, b, (f0, f1), hor, k in segs:
    col = BLUE if k % 2 == 0 else ROSE
    if hor:
        dp.rectangle((a * K, f0 * K, b * K, f1 * K), fill=col + (255,))
        for xx in np.arange(a + 4, b - 2, 7.0):
            circle(dw, (xx, (f0 + f1) / 2), 1.0, fill=255)
    else:
        dp.rectangle((f0 * K, a * K, f1 * K, b * K), fill=col + (255,))
        for yy in np.arange(a + 4, b - 2, 7.0):
            circle(dw, ((f0 + f1) / 2, yy), 1.0, fill=255)
# Goldleiste
gx0, gy0, gx1, gy1 = rect(15.8)
dg.rectangle((gx0 * K, gy0 * K, gx1 * K, gy1 * K), fill=255)
dg.rectangle((bx0 * K, by0 * K, bx1 * K, by1 * K), fill=0)
# Phasen der Goldleiste in Abschnitten (jeder Abschnitt blitzt für sich)
for k, xx in enumerate(np.arange(gx0, gx1, 40)):
    dph.rectangle((xx * K, gy0 * K, (xx + 40) * K, gy1 * K), fill=int(rs.randint(1, 255)))
dph.rectangle((bx0 * K, by0 * K, bx1 * K, by1 * K), fill=0)
for yy in np.arange(gy0, gy1, 40):
    v = int(rs.randint(1, 255))
    dph.rectangle((gx0 * K, yy * K, bx0 * K, (yy + 40) * K), fill=v)
    dph.rectangle((bx1 * K, yy * K, gx1 * K, (yy + 40) * K), fill=int(rs.randint(1, 255)))
# Tuschelinien
for off in (0.7, 8.1, 16.5):
    a0, b0, a1, b1 = rect(off)
    line(di, [(a0, b0), (a1, b0), (a1, b1), (a0, b1), (a0, b0)], 1.4)
FRAME_OUT = rect(16.5)

# ---------------------------------------------------------------- Ranken in den Rändern
fx0, fy0, fx1, fy1 = FRAME_OUT
# links: vom oberen Rahmeneck bis in den unteren Rand
left = wavy((25, 24), (25, 656), 5, 120)
vine(left, 50, 27, 11.5, ["gold", "blue", "gold", "rose", "gold", "green", "gold", "blue", "rose"])
# oben: schmal, kleine Ranken
top = wavy((44, 15), (1258, 15), 3, 100)
vine(top, 46, 20, 8.0, ["gold", "rose", "gold", "blue", "gold", "green"], curl=2.0, stem_w=1.6)
# rechts
right = wavy((1262, 24), (1262, 656), 4, 112)
vine(right, 52, 23, 10.0, ["gold", "rose", "gold", "blue", "gold", "green", "rose"])
# unten (bas-de-page): breite Ranke mit großen Blättern
bottom = wavy((25, 658), (1262, 658), 15, 236, n=400)
# über dem Stück Stiel, auf dem die Drolerie steht (main.gd: DROLL_FOOT x = 1080), keine Ranken
vine(bottom, 64, 64, 17, ["gold", "blue", "rose", "gold", "green", "gold", "rose", "blue", "gold"], curl=2.2,
     stem_w=2.2, skip=DROLL_CLEAR)
for c, r in [((25, 24), 11), ((1262, 24), 11), ((25, 658), 13), ((1262, 658), 13)]:
    flower(c, r)

# ---------------------------------------------------------------- Initialfeld: Fleuronnée in blauer Feder
# Die rote Initiale setzt Godot (Texturina) mittig in dieses Feld; das Federwerk füllt Binnenraum und Umgebung.
ix, iy, iw, ih = INIT
cx, cy = ix + iw / 2, iy + ih / 2


def pline(pts, w=0.85):
    line(dpen, pts, w)


# Rahmen: doppelte Linie, außen eine Reihe kleiner Halbkreisbögen (Perlstab)
for off, wdt in ((3, 0.9), (7, 0.7)):
    pline([(ix + off, iy + off), (ix + iw - off, iy + off), (ix + iw - off, iy + ih - off), (ix + off, iy + ih - off),
           (ix + off, iy + off)], wdt)
for k in range(13):
    t0 = (k + 0.5) / 13
    for (px, py, a) in ((ix + 3 + t0 * (iw - 6), iy + 3, -math.pi / 2), (ix + 3 + t0 * (iw - 6), iy + ih - 3, math.pi / 2),
                        (ix + 3, iy + 3 + t0 * (ih - 6), math.pi), (ix + iw - 3, iy + 3 + t0 * (ih - 6), 0)):
        arc = [(px + math.cos(a + u) * 3.0, py + math.sin(a + u) * 3.0) for u in np.linspace(-1.5, 1.5, 9)]
        pline(arc, 0.6)
# Ecken: Spiralen nach außen
for (qx, qy, a) in ((ix, iy, -2.36), (ix + iw, iy, -0.78), (ix + iw, iy + ih, 0.78), (ix, iy + ih, 2.36)):
    for s_ in (-1, 1):
        pts, _ = spiral((qx, qy), a + s_ * 0.35, 16, s_ * 2.2, steps=24)
        pline(pts, 0.75)
        circle(dpen, pts[-1], 1.0, fill=255)
# Binnenfeld: dichtes Federwerk aus kleinen Spiralen im Raster und Perlen (die Initiale verdeckt die Mitte)
gstep = 11.0
for gy_ in np.arange(iy + 14, iy + ih - 12, gstep):
    for gx_ in np.arange(ix + 14, ix + iw - 12, gstep):
        j = int((gx_ - ix) / gstep) + int((gy_ - iy) / gstep)
        s_ = 1 if j % 2 else -1
        pts, _ = spiral((gx_, gy_), j * 0.9, 9.5, s_ * 2.4, steps=16)
        pline(pts, 0.6)
        circle(dpen, (gx_ + gstep / 2, gy_ + gstep / 2), 0.7, fill=255)
# Ausläufer: Federstrich den Spaltenrand hinab, Fäden und Spiralen, endet in Goldpollen
tail_x = ix - 13
tail = wavy((tail_x, iy + 4), (tail_x, iy + 360), 2.5, 40)
pline(tail, 0.9)
pline([(tail_x + 4, iy + 10), (tail_x + 4, iy + 300)], 0.55)
for k in range(1, 16):
    py = iy + 6 + k * 22
    s_ = 1 if k % 2 else -1
    pts, _ = spiral((tail_x, py), math.pi / 2 + s_ * 1.35, 12, -s_ * 2.0, steps=18)
    pline(pts, 0.7)
    circle(dpen, pts[-1], 1.0, fill=255)
    circle(dpen, (tail_x - s_ * 3.5, py + 9), 0.8, fill=255)
bezant((tail_x, iy + 366), 2.8)
# nach oben über den Rubrikzeilen
up = wavy((tail_x, iy + 4), (tail_x, iy - 50), 2, 30)
pline(up, 0.8)
for k in range(1, 3):
    py = iy + 4 - k * 18
    s_ = 1 if k % 2 else -1
    pts, _ = spiral((tail_x, py), -math.pi / 2 + s_ * 1.35, 11, s_ * 2.0, steps=16)
    pline(pts, 0.7)
    circle(dpen, pts[-1], 1.0, fill=255)
bezant((tail_x, iy - 54), 2.4)
pline([(tail_x, iy + 4), (ix + 3, iy + 3)], 0.8)
pline([(ix + iw - 3, iy + ih - 3), (ix + iw + 10, iy + ih + 12)], 0.7)
bezant((ix + iw + 12, iy + ih + 14), 2.2)

# ---------------------------------------------------------------- Pergament (1x, numpy)
hh, ww = H, W
base = np.array(PARCH, np.float32)[None, None, :] * np.ones((hh, ww, 1), np.float32)
n1 = noise(hh, ww, 180, rs) - 0.5
n2 = noise(hh, ww, 40, rs) - 0.5
n3 = noise(hh, ww, 8, rs) - 0.5
n4 = rs.rand(hh, ww).astype(np.float32) - 0.5
tone = n1 * 16 + n2 * 7 + n3 * 3.5 + n4 * 3.0
base += tone[..., None] * np.array([1.0, 0.95, 0.85])[None, None, :]
# warmer, etwas dunklerer Rand (Griffspuren, Alterung)
yy, xx = np.mgrid[0:hh, 0:ww].astype(np.float32)
edge = np.minimum.reduce([xx, yy, ww - 1 - xx, hh - 1 - yy])
age = np.clip(1 - edge / 60.0, 0, 1) ** 2
base -= age[..., None] * np.array([18, 22, 30])[None, None, :]
# Haarporen des Pergaments: wenige feine dunkle Punkte
ys = rs.randint(0, hh, 900)
xs = rs.randint(0, ww, 900)
for y0, x0 in zip(ys, xs):
    base[y0, x0] -= np.array([14, 16, 18]) * rs.rand()
parch = np.clip(base, 0, 255)

# ---------------------------------------------------------------- Zusammensetzen
def down(im):
    return im.resize((W, H), Image.LANCZOS)

paint1 = np.array(down(paint)).astype(np.float32) / 255.0
gold1 = np.array(down(gold)).astype(np.float32) / 255.0
white1 = np.array(down(white)).astype(np.float32) / 255.0
ink1 = np.array(down(ink)).astype(np.float32) / 255.0
pen1 = np.array(down(pen)).astype(np.float32) / 255.0
phase1 = np.array(phase.resize((W, H), Image.NEAREST))

img = parch.copy()
a = paint1[..., 3:4]
# Temperafarbe mit leichter Pinselstruktur
tex = 1.0 + (noise(hh, ww, 3, rs) - 0.5)[..., None] * 0.10
img = img * (1 - a) + paint1[..., :3] * 255 * tex * a

# Blattgold: Relief aus Knitter (feines Rauschen) und Punzierung (Punktraster in der Goldleiste)
crinkle = noise(hh, ww, 2, rs) * 0.6 + noise(hh, ww, 6, rs) * 0.4
punch = np.zeros((hh, ww), np.float32)
# Punzen nur in der Goldleiste des Rahmens (Blätter und Pollen sind glatt poliert)
in_bar = ((xx >= gx0) & (xx <= gx1) & (yy >= gy0) & (yy <= gy1)) & ~((xx > bx0) & (xx < bx1) & (yy > by0) & (yy < by1))
gx = (xx % 5 == 2) & (yy % 5 == 2) & in_bar
punch[gx] = 255.0
punch = np.array(Image.fromarray(punch.astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))).astype(np.float32) / 255.0
relief = np.clip(0.2 + 0.7 * crinkle - 2.0 * punch, 0, 1)
G_DARK = np.array([118, 84, 32], np.float32)
G_MID = np.array([204, 162, 74], np.float32)
G_LIGHT = np.array([246, 218, 134], np.float32)
r = relief[..., None]
gcol = np.where(r < 0.5, G_DARK + (G_MID - G_DARK) * (r / 0.5), G_MID + (G_LIGHT - G_MID) * ((r - 0.5) / 0.5))
gcol = gcol * 0.88 + G_MID * 0.12
g = gold1[..., None]
img = img * (1 - g) + gcol * g
w_ = white1[..., None]
img = img * (1 - w_) + np.array(WHITE, np.float32) * w_
p_ = pen1[..., None] * 0.95
img = img * (1 - p_) + np.array(PEN_BLUE, np.float32) * p_
i_ = ink1[..., None]
img = img * (1 - i_) + np.array(INK, np.float32) * i_

Image.fromarray(np.clip(img, 0, 255).round().astype(np.uint8)).save(OUT / "page.png")
gm = np.dstack([(gold1 * (1 - ink1) * 255).round().astype(np.uint8), phase1,
                (relief * 255).round().astype(np.uint8)])
Image.fromarray(gm).save(OUT / "page_gold.png")
info = {"size": [W, H], "window": list(WIN), "frame_outer": [round(v, 1) for v in FRAME_OUT],
        "text": list(TEXT), "initial": list(INIT), "seed": SEED}
(OUT / "page.json").write_text(json.dumps(info, indent=1))
print(json.dumps(info))
