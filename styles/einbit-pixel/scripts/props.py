#!/usr/bin/env python3
"""Von Hand gesetzte Gegenstände für die Tonkarte (Koordinaten im 400×240-Ausschnitt).

Das Bildmodell zeichnet Fässer, Kisten, Boote, Steg, Laterne, Leuchtturm sowie Tür und Fenster des Häuschens
feiner als das 400er-Raster; umgerechnet werden sie zu Pixelbrei. Diese Teile werden deshalb hier mit
einfachen Grundformen neu gesetzt – Lage und Größe nach dem KI-Bild, Tonstufen wie in einem 1-Bit-Spiel
(Kontur schwarz, Flächen 0/4/8/12/16, Lichtkante weiß). Alles bleibt Tonkarte; die Muster setzt der Shader.
"""
import math

import numpy as np

import onebit as ob

R = {"object": 0, "sky": 1, "water": 2, "ground": 3, "glass": 4, "star": 5, "lamp": 6, "window": 7}


class Canvas:
    """Zeichenfläche auf der Tonkarte. oy verschiebt alle y-Angaben (Koordinaten der Gegenstände sind für
    den Ausschnitt ab Zeile 22 des 400er-Rasters gemessen)."""

    def __init__(self, lev, fam, region, oy=0):
        self.lev, self.fam, self.reg = lev, fam, region
        self.h, self.w = lev.shape
        self.oy = oy

    def put(self, x, y, level, region=R["object"], family=ob.BAYER):
        x, y = int(x), int(y) + self.oy
        if 0 <= x < self.w and 0 <= y < self.h:
            self.lev[y, x] = level
            self.reg[y, x] = region
            self.fam[y, x] = family

    def rect(self, x0, y0, x1, y1, level, region=R["object"], family=ob.BAYER):
        y0, y1 = y0 + self.oy, y1 + self.oy
        x0, x1 = max(0, int(x0)), min(self.w - 1, int(x1))
        y0, y1 = max(0, int(y0)), min(self.h - 1, int(y1))
        if x1 < x0 or y1 < y0:
            return
        self.lev[y0:y1 + 1, x0:x1 + 1] = level
        self.reg[y0:y1 + 1, x0:x1 + 1] = region
        self.fam[y0:y1 + 1, x0:x1 + 1] = family

    def frame(self, x0, y0, x1, y1, level=0):
        self.rect(x0, y0, x1, y0, level)
        self.rect(x0, y1, x1, y1, level)
        self.rect(x0, y0, x0, y1, level)
        self.rect(x1, y0, x1, y1, level)

    def line(self, x0, y0, x1, y1, level, region=R["object"]):
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while True:
            self.put(x0, y0, level, region)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def ellipse(self, cx, cy, rx, ry, level, outline=None):
        for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
            for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
                v = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
                if v <= 1.0:
                    self.put(x, y, level)
        if outline is not None:
            self.ellipse_ring(cx, cy, rx, ry, outline)

    def ellipse_ring(self, cx, cy, rx, ry, level):
        inside = lambda x, y: ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0
        for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
            for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
                if inside(x, y) and not (inside(x - 1, y) and inside(x + 1, y) and inside(x, y - 1) and inside(x, y + 1)):
                    self.put(x, y, level)

    def clear(self, x0, y0, x1, y1, sky_lev, water_lev, ground_row, ground_lev):
        """Fläche auf Hintergrund zurücksetzen: Himmel/Wasser nach Zeile, ab ground_row Kai (Zeilen im
        Bild, also schon verschoben)."""
        for yy in range(max(0, y0 + self.oy), min(self.h, y1 + self.oy + 1)):
            for x in range(max(0, x0), min(self.w, x1 + 1)):
                if yy >= ground_row:
                    self.put(x, yy - self.oy, ground_lev[yy], R["ground"])
                elif water_lev[yy] is not None:
                    self.put(x, yy - self.oy, water_lev[yy], R["water"], ob.DASH)
                else:
                    self.put(x, yy - self.oy, sky_lev[yy], R["sky"], ob.LINES)


LEGEND = {"#": 0, ",": 2, "-": 4, "=": 6, "+": 8, "*": 10, ":": 12, ";": 14, ".": 16,
          "G": (16, "glass"), "L": (16, "lamp"), "W": (16, "window")}


def stamp(c, art, x0, y0):
    """ASCII-Bild setzen; Leerzeichen bleibt Hintergrund. Gibt die Pixel mit eigenem Bereich zurück."""
    special = {}
    for r, line in enumerate(art.strip("\n").split("\n")):
        for k, ch in enumerate(line):
            if ch == " ":
                continue
            v = LEGEND[ch]
            if isinstance(v, tuple):
                c.put(x0 + k, y0 + r, v[0], R[v[1]])
                special.setdefault(v[1], []).append((x0 + k, y0 + r))
            else:
                c.put(x0 + k, y0 + r, v)
    return special


ROPE = """
     ###########
   ##...........##
  #..###########..#
 #..#...........#..#
 #.#..#########..#.#
 #.#.#,,,,,,,,,#.#.#
 #.#..#########..#.#
 #..#...........#..#
  #..###########..#
   ##...........###
     ############..#
                ##..#
                  ##
"""

LIGHTHOUSE = """
        .
        .
       .-.
      .---.
     .-----.
     .......
     .#LLL#.
     .#LLL#.
     .#LLL#.
     .#LLL#.
     .......
  .............
  .#.#.#.#.#.#.
  #############
    .......:+
    .......:+
    ...##..:+
    ...##..:+
    .......:+
    .......:+
   ........::+
   ........::+
   ........::+
   ........::+
   .#########+.
   .##########.
   .##########.
   .##########.
   .##########.
   .#########+.
   ........::+
   ........::+
  .........::+
  .........::++
  ......##.::++
  ......##.::++
  .........::++
  .........::++
  .........::++
  .........::++
  .........::++
 ..........::++
 ..........::++
 ...####...::++
 ...####...::++
 ...####...::++
 ...####...::++
 ...####...::++
"""

PARCEL = """
  ##########
 #....#....##
#.....#....#.#
############..#
#.....#.....#.#
#..#.#.#....#.#
#.....#.....#.#
#.....#.....##
#############
"""

LANTERN_HEAD = """
    ###
     #
    ###
   #:::#
  #.....#
 #########
 #GGG#GGG#
 #GGG#GGG#
 #GGG#GGG#
 #GGG#GGG#
 #GGG#GGG#
 #GGG#GGG#
  #GG#GG#
  #######
    ###
     #
"""


def shade(u, ramp=((0.14, 4), (0.32, 8), (0.62, 12), (0.80, 16), (0.92, 12)), last=8):
    for lim, lv in ramp:
        if u < lim:
            return lv
    return last


def barrel(c, x0, y0, w=19, h=26):
    """Fass: Deckel als helle Ellipse, Körper mit festen Schattierungsbändern je Spalte, schwarze Reifen."""
    cx = x0 + (w - 1) / 2
    bands = [(-9, 0), (-8, 12), (-6, 16), (-3, 12), (2, 8), (5, 4), (7, 0)]   # (ab Spalte rel. Mitte, Stufe)
    def band(dx):
        lv = 0
        for lim, v in bands:
            if dx >= lim:
                lv = v
        return lv
    hoops = (8, 9, h - 7, h - 6)
    for r in range(h):
        y = y0 + r
        if r < 4:
            half = [5, 7, 8, 8][r]
        else:
            half = (w - 1) / 2 - 1 + 1.0 * math.sin(math.pi * (r - 3) / (h - 4))
        left, right = round(cx - half), round(cx + half)
        for x in range(left, right + 1):
            dx = x - cx
            if r == 0 or (r < 4 and x in (left, right)):
                lv = 0
            elif r < 3:
                lv = 16 if r == 1 or abs(dx) < 5 else 12
            elif r == 3:
                lv = 0
            elif x in (left, right) or r == h - 1:
                lv = 0
            elif r in hoops:
                lv = 16 if r in (hoops[0], hoops[2]) and -6 <= dx < -3 else 0
            else:
                lv = band(dx)
            c.put(x, y, lv)


def crate(c, x0, y0, w, h, top=3, side=3, kind="brace"):
    """Vorderseite w×h ab (x0, y0+top), Deckel top Zeilen hoch, rechte Seite side Spalten breit."""
    fy0, fy1 = y0 + top, y0 + top + h - 1
    fx0, fx1 = x0, x0 + w - 1
    # Deckel (hell), Seite (dunkel)
    for r in range(top):
        y = y0 + r
        sh = top - r
        for x in range(fx0 + sh, fx1 + sh + 1):
            c.put(x, y, 0 if r == 0 or x in (fx0 + sh, fx1 + sh) else 16)
    for k in range(1, side + 1):
        for y in range(fy0 - k, fy1 - k + 1):
            c.put(fx1 + k, y, 0 if k == side or y in (fy0 - k, fy1 - k) else 4)
    c.rect(fx0, fy0, fx1, fy1, 12)
    c.frame(fx0, fy0, fx1, fy1, 0)
    c.frame(fx0 + 2, fy0 + 2, fx1 - 2, fy1 - 2, 0)
    c.rect(fx0 + 1, fy0 + 1, fx1 - 1, fy0 + 1, 16)          # Lichtkante oben
    ix0, iy0, ix1, iy1 = fx0 + 3, fy0 + 3, fx1 - 3, fy1 - 3
    if kind == "slats_v":
        for x in range(ix0 + 2, ix1, 3):
            c.rect(x, iy0, x, iy1, 0)
    elif kind == "slats_h":
        for y in range(iy0 + 2, iy1, 3):
            c.rect(ix0, y, ix1, y, 0)
    else:
        c.line(ix0, iy1, ix1, iy0, 0)
        c.line(ix0 + 1, iy1, ix1, iy0 + 1, 16)


def rope_coil(c, x0, y0):
    stamp(c, ROPE, x0, y0)


def boat(c, x0, x1, yw, hside=6, bow_right=True):
    """Ruderboot im Profil, leicht von oben: Bordwand als helle Fläche (weißes Dollbord, eine schwarze
    Plankennaht, darunter Bayer 12) mit schwarzer Kontur und durchgehender schwarzer Wasserlinie, dunkles
    Inneres, Bänke. Die erste Fassung (Bordwand in Streifen 0/16/12) ging im Strichraster des Wassers unter."""
    L = x1 - x0
    xc = (x0 + x1) / 2
    for x in range(x0, x1 + 1):
        t = (x - xc) / (L / 2)
        sheer = 3.0 * t * t + (1.2 * max(0, t) if bow_right else 1.2 * max(0, -t))
        ytop = round(yw - hside - sheer)
        end = max(0.0, (abs(t) - 0.7) / 0.3)
        ybot = round(yw - end * (hside + sheer - 1))
        far = round(ytop - 3 + 1.5 * t * t)                # ferne Bordkante
        for y in range(far, ytop):
            c.put(x, y, 16 if y == far else 0)              # Inneres dunkel, ferne Kante hell
        for y in range(ytop, ybot + 1):
            rr = y - ytop
            if x in (x0, x1) or y == ybot:
                lv = 0
            elif rr <= 1:
                lv = 16                                     # Dollbord (nahe Bordkante)
            elif rr == 3:
                lv = 0                                      # Plankennaht
            else:
                lv = 16 if rr == 2 else 12
            c.put(x, y, lv)
        if x in (x0, x1):
            for y in range(far, ybot + 1):
                c.put(x, y, 0)
        else:
            c.put(x, far - 1, 0)
        if ybot >= yw - 1:                                  # Wasserlinie unter dem Rumpf
            c.put(x, yw + 1, 0, R["water"], ob.DASH)
    # Bänke
    for tb in (-0.35, 0.3):
        xb = round(xc + tb * L / 2)
        ytop = round(yw - hside - 3.0 * tb * tb)
        for y in range(ytop - 2, ytop):
            c.put(xb, y, 16)
            c.put(xb + 1, y, 16)


def jetty(c, near_y, far_y, near_x, far_x):
    """Steg in Aufsicht von schräg vorn: Planken werden zum Ende hin schmaler."""
    rows = list(range(far_y, near_y + 1))
    n = len(rows)
    seams, y, hgt = [], far_y, 2.0
    while y < near_y:
        seams.append(int(y))
        y += hgt
        hgt = min(4.0, hgt + 0.25)
    for i, y in enumerate(rows):
        f = i / max(1, n - 1)
        xl = round(far_x[0] + (near_x[0] - far_x[0]) * f)
        xr = round(far_x[1] + (near_x[1] - far_x[1]) * f)
        for x in range(xl, xr + 1):
            if x in (xl, xr) or y in seams:
                lv = 0
            else:
                lv = 16
            c.put(x, y, lv)
        # Balken unter der Plankenkante
        c.put(xl - 1, y, 0)
        c.put(xr + 1, y, 4)
        c.put(xr + 2, y, 0)
    # Pfähle: oben an den Ecken, unten am fernen Ende ins Wasser
    for (px, top, bot) in ((far_x[0] - 1, far_y - 5, far_y + 2), (far_x[1], far_y - 5, far_y + 2),
                           (near_x[0] + 6, near_y - 13, near_y - 6), (near_x[1] - 7, near_y - 13, near_y - 6)):
        c.rect(px, top, px + 1, bot, 0)
        c.put(px + 1, top + 1, 16)
    for px in (far_x[0] + 2, far_x[1] - 2):
        c.rect(px, far_y + 1, px, far_y + 4, 0, R["water"])


def lighthouse(c, x0, y0):
    """Leuchtturm als Stempel: helle Gegenkontur vor dem dunklen Himmel, schwarzes Band mit Lichtkante."""
    return stamp(c, LIGHTHOUSE, x0, y0).get("lamp", [])


def lantern(c, post_x, post_top, post_bot, arm_x1, arm_y):
    """Galgenlaterne: Pfosten, Arm, Strebe, hängende Laterne (Glas als eigener Bereich)."""
    # Pfosten (5 px: Kontur, Licht links, Holz)
    for y in range(post_top, post_bot + 1):
        for i, lv in enumerate((0, 16, 12, 8, 0)):
            c.put(post_x + i, y, lv)
    c.rect(post_x, post_top, post_x + 4, post_top, 0)
    # Sockel auf der Kaifläche (7×4: Kontur, helle Oberkante, Stein)
    c.rect(post_x - 1, post_bot - 3, post_x + 5, post_bot, 12)
    c.frame(post_x - 1, post_bot - 3, post_x + 5, post_bot, 0)
    c.rect(post_x, post_bot - 2, post_x + 4, post_bot - 2, 16)
    # Arm
    for x in range(post_x + 4, arm_x1 + 1):
        for i, lv in enumerate((0, 16, 8, 0)):
            c.put(x, arm_y + i, lv)
    c.rect(arm_x1, arm_y, arm_x1, arm_y + 3, 0)
    # Strebe
    for k in range(10):
        c.put(post_x + 5 + k, arm_y + 14 - k, 0)
        c.put(post_x + 5 + k, arm_y + 13 - k, 12)
        c.put(post_x + 6 + k, arm_y + 14 - k, 0)
    # Laterne am Armende
    lx = arm_x1 - 6
    sp = stamp(c, LANTERN_HEAD, lx - 5, arm_y + 4)
    glass = sp.get("glass", [])
    gy = [p[1] for p in glass]
    return glass, (lx, (min(gy) + max(gy)) // 2)


def stone_wall(c, x0, y0, x1, y1, rng, skip=()):
    """Bruchsteinmauer: Lagen 5–6 px, Steine 6–12 px, Fugen schwarz, Steine hell (16/12, wenige 8)."""
    y = y0
    row = 0
    while y <= y1:
        hgt = 5 if row % 2 == 0 else 6
        x = x0 - (row % 2) * 4
        while x <= x1:
            sw = int(rng.integers(6, 13))
            lv = int(rng.choice([16, 16, 12, 12, 12, 8]))
            for yy in range(y, min(y + hgt, y1 + 1)):
                for xx in range(max(x, x0), min(x + sw, x1 + 1)):
                    if any(a <= xx <= b and cc <= yy <= d for (a, cc, b, d) in skip):
                        continue
                    joint = yy == y or xx == x
                    light = (yy == y + 1 and not joint)
                    c.put(xx, yy, 0 if joint else (16 if light and lv >= 12 else lv))
            x += sw
        y += hgt
        row += 1


def cottage_front(c, rng):
    """Mauer, Tür, erleuchtetes Fenster und Schornstein des Hafenmeisterhäuschens. Tür 81 px hoch (Sturz direkt
    unter der Traufe), etwa 1,3-mal so hoch wie der Dachs (62 px), damit das Häuschen nicht zur Puppenstube wird."""
    door = (4, 88, 30, 168)
    win = (39, 92, 59, 132)
    stone_wall(c, 0, 84, 64, 168, rng, skip=(door, win))
    c.rect(65, 84, 66, 168, 0)                                     # Hauskante
    for y in range(86, 168, 6):                                    # Eckquader
        c.rect(61, y, 64, y + 4, 16 if (y // 6) % 2 else 12)
        c.rect(60, y + 5, 64, y + 5, 0)
        c.rect(60, y, 60, y + 5, 0)
    # Tür: Sturz, Rahmen, Bretter
    x0, y0, x1, y1 = door
    c.rect(x0 - 2, y0 - 4, x1 + 2, y0 - 1, 16)
    c.frame(x0 - 2, y0 - 4, x1 + 2, y0 - 1, 0)
    c.rect(x0, y0, x1, y1, 4)
    c.frame(x0, y0, x1, y1, 0)
    for x in range(x0 + 4, x1 - 1, 5):
        c.rect(x, y0 + 1, x, y1 - 1, 0)
        c.rect(x + 1, y0 + 1, x + 1, y1 - 1, 8)
    c.rect(x0 + 1, y0 + 1, x0 + 1, y1 - 1, 12)
    c.rect(x1 - 4, y1 - 37, x1 - 3, y1 - 36, 16)                    # Klinke
    # Fenster: Rahmen, sechs Scheiben (Bereich window), Sprossen, Bank
    x0, y0, x1, y1 = win
    c.rect(x0 - 1, y0 - 1, x1 + 1, y1 + 1, 0)
    glass = []
    bars = (y0 + (y1 - y0) // 3, y0 + 2 * (y1 - y0) // 3)
    for y in range(y0 + 1, y1):
        for x in range(x0 + 1, x1):
            if x in (x0 + 1, x1 - 1) or y in (y0 + 1, y1 - 1) or x == (x0 + x1) // 2 or y in bars:
                c.put(x, y, 0)
            else:
                c.put(x, y, 16, R["window"])
                glass.append((x, y))
    c.rect(x0 - 3, y1 + 2, x1 + 3, y1 + 3, 16)
    c.frame(x0 - 3, y1 + 2, x1 + 3, y1 + 4, 0)
    return glass


def chimney(c, rng):
    stone_wall(c, 12, 12, 33, 40, rng)
    c.frame(11, 11, 34, 41, 0)
    c.rect(9, 8, 36, 11, 16)
    c.frame(9, 8, 36, 11, 0)
    c.rect(19, 0, 26, 7, 12)
    c.rect(20, 0, 21, 7, 16)
    c.frame(19, -1, 26, 8, 0)
    return (22.5, 0)


def parcel(c, x0, y0):
    """Das wartende Paket auf dem Kai: Packpapier hell, Schnur schwarz, Schleife."""
    stamp(c, PARCEL, x0, y0)
