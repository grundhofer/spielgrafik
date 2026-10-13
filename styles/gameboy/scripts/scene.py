"""Hafen von Lornholm als Hintergrund für den Handheld: 256x104 Pixel in 4 Tönen (Tonnummer 0 = hell, 3 = dunkel).

Sichtbar sind 160x104 (20x13 Kacheln); die Wolkenzeilen y 8-23 (Kachelzeilen 1-2) sind 256 px breit und werden per
Zeilen-Scroll verschoben. draw(state) zeichnet die Szene in einem Animationszustand; build_rom.py vergleicht die
Zustände und macht daraus Kachelanimationen. Flächen (Wasser, Pflaster, Planken, Mauer, Dach) sind kachelgenau
wiederholte Muster, damit die Szene in das Budget von 256 Hintergrundkacheln passt.
"""
import numpy as np

from pix import put, stamp

W, H = 256, 104
VIS = 160
CLOUD_Y0, CLOUD_Y1 = 8, 24          # Zeilen mit eigenem Scroll (Kachelzeilen 1-2)
QUAY_Y = 72                         # Oberkante des Kais
JETTY_X = 108                       # ab hier Holzsteg statt Steinkai
FEET_Y = 97                         # unterste Pixelzeile der Füße auf dem Kai
LAMP = (136, 28)                    # Mitte der Leuchtturmlampe
LANTERN = (64, 50)                  # linke obere Ecke des Laternenkopfs
CHIMNEY_TOP = (26, 31)              # Rauchaustritt (Mitte, Oberkante)
PARCEL = (91, 89)                   # Paket am Kai (linke obere Ecke), Unterkante auf FEET_Y, 4 px Kai bis zum Steg

# Animationskanäle: Name -> Anzahl Zustände
CHANNELS = {"water": 8, "beam": 8, "lantern": 3, "stars": 2}


def dither(c, y0, y1, a, b, level, x0=0, x1=W):
    """Ton a mit Anteil level/4 in Ton b, geordnetes 2x2-Muster."""
    m = [[0, 2], [3, 1]]
    for y in range(y0, y1):
        for x in range(x0, x1):
            c[y, x] = b if m[y & 1][x & 1] < level else a


# ---------------------------------------------------------------- Himmel

STARS = [(5, 2), (21, 5), (55, 4), (90, 6), (106, 1), (124, 3), (147, 5), (157, 1),
         (14, 26), (47, 25), (101, 25), (153, 27), (36, 30), (8, 33)]
BIG_STARS = [(41, 3), (117, 5), (78, 26)]           # Kreuzsterne, funkeln abwechselnd


def sky(c, st):
    c[:, :] = 3
    dither(c, 24, 28, 3, 2, 1)
    dither(c, 28, 32, 3, 2, 2)
    dither(c, 32, 36, 3, 2, 3)
    c[36:38, :] = 2
    dither(c, 38, 40, 2, 1, 2)
    c[40:43, :] = 1
    c[43, :] = 0
    c[44, :] = 1
    c[45, :] = 0
    for x, y in STARS:
        if c[y, x] == 3:
            c[y, x] = 0 if y < 24 else 1
    for i, (x, y) in enumerate(BIG_STARS):
        c[y, x] = 0
        if (st["stars"] + i) % 2 == 0:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                c[y + dy, x + dx] = 1


CLOUDS = [
    # Grundlinie y, Buckel (x, Radius x, Radius y); Zeilen 9-22, Breite 256 (Zeilen-Scroll)
    (20, [(5, 5, 3), (13, 6, 6), (23, 7, 7), (33, 6, 5), (41, 4, 3)]),
    (15, [(70, 4, 3), (78, 6, 5), (88, 5, 4), (95, 3, 2)]),
    (21, [(118, 5, 3), (127, 7, 6), (138, 8, 8), (149, 6, 5), (157, 4, 3)]),
    (17, [(186, 5, 4), (196, 7, 6), (206, 5, 4)]),
    (22, [(228, 4, 3), (237, 6, 5), (247, 6, 4), (254, 3, 2)]),
]


def clouds(c):
    for yb, lumps in CLOUDS:
        x0 = min(cx - rx for cx, rx, _ in lumps)
        x1 = max(cx + rx for cx, rx, _ in lumps)
        cells = set()
        for x in range(x0, x1 + 1):
            for y in range(CLOUD_Y0, yb + 1):
                for cx, rx, ry in lumps:
                    if ((x - cx) / (rx + 0.5)) ** 2 + ((y - yb) / (ry + 0.5)) ** 2 <= 1.0:
                        cells.add((x % W, y))
                        break
        for x, y in cells:
            c[y, x] = 2
        for x, y in cells:
            if (x, y + 1) not in cells:
                c[y, x] = 1 if x % 4 != 1 else 0                 # Unterkante vom Abendlicht
            elif (x, y + 2) not in cells and x % 2 == 0:
                c[y, x] = 1
            elif (x, y - 1) not in cells:
                c[y, x] = 2                                       # Oberkante dunkel, Körper heller gedithert
            elif (x + y) % 2 == 0 and (x, y + 3) not in cells:
                c[y, x] = 1


# ---------------------------------------------------------------- Meer

# y: Muster über 8 px (Ton je Pixel) und Richtung; je Zustand um 1 px verschoben (Kachelanimation)
WATER_ROWS = {
    46: ("11011101", 1),
    47: ("22112222", -1),
    48: ("12222211", 1),
    49: ("22222222", 1),
    50: ("22221122", -1),
    51: ("22222222", 1),
    52: ("11222222", 1),
    53: ("22222222", 1),
    54: ("22222122", -1),
    55: ("22222222", 1),
    56: ("22112222", 1),
    57: ("22222222", 1),
    58: ("22222332", -1),
    59: ("22222222", 1),
    60: ("21222222", 1),
    61: ("22222222", 1),
    62: ("33222222", -1),
    63: ("22222222", 1),
    64: ("22223322", 1),
    65: ("22222222", 1),
    66: ("32222233", -1),
    67: ("22222222", 1),
    68: ("22333332", 1),
    69: ("33333333", 1),
    70: ("33332333", -1),
    71: ("33333333", 1),
}
# Wasser unter dem Steg (y 94-103): dunkel, einzelne Lichtreflexe
UNDER_ROWS = {
    94: ("33333333", 1), 95: ("33333333", 1), 96: ("33233333", -1), 97: ("33333333", 1),
    98: ("33333322", 1), 99: ("33333333", 1), 100: ("32333333", -1), 101: ("33333333", 1),
    102: ("33332233", 1), 103: ("33333333", 1),
}


PROBE = {"fill": None}           # build_rom.py: Wasser einfarbig zeichnen, um sichtbare Wasserpixel zu finden


def water_rows(c, rows, w, x0=0, x1=W):
    for y, (pat, d) in rows.items():
        p = [int(ch) for ch in pat] if PROBE["fill"] is None else [PROBE["fill"]] * 8
        for x in range(x0, x1):
            c[y, x] = p[(x - d * w) % 8]


def sea(c, st):
    water_rows(c, WATER_ROWS, st["water"])


# ---------------------------------------------------------------- Landzunge und Leuchtturm

def headland(c):
    pts = [(104, 63), (108, 60), (112, 57), (116, 55), (121, 53), (126, 52), (131, 52), (142, 52),
           (147, 51), (152, 49), (156, 49), (160, 48)]
    top = {}
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        for x in range(xa, xb + 1):
            top[x] = int(round(ya + (yb - ya) * (x - xa) / max(1, xb - xa)))
    for x, yt in top.items():
        for y in range(yt, 64):
            c[y, x] = 3
        c[yt, x] = 1                                          # Kante gegen den hellen Horizont
    # einige Felsblöcke mit heller Oberkante
    for x, yt in top.items():
        if yt + 1 < 64 and x % 5 != 0:
            c[yt + 1, x] = 2                                  # zweite, dunklere Lichtkante
    for x, yt in top.items():                                 # Rundung: gedithertes Band unter der Lichtkante
        for y in (yt + 3, yt + 4):
            if y < 62 and (x + y) % 2 == 0:
                c[y, x] = 2
    # Gischt am Fuß
    for x in range(102, 160):
        if x % 4 != 2:
            c[64, x] = 1 if x % 3 else 0


LAMP_ROOM = stamp("""
....3....
...313...
..33133..
.3311133.
.3.....3.
.3.....3.
.3.....3.
333333333
.3.3.3.3.
""")


def lighthouse(c, st):
    lx, ly = LAMP
    # Turm y 32-52: oben 7 px, unten 11 px breit; rechts Schattenseite, rotes Band dunkel
    for y in range(32, 53):
        t = (y - 32) / 20.0
        half = 3 + t * 2.0
        x0 = int(round(lx - half))
        x1 = int(round(lx + half))
        for x in range(x0, x1 + 1):
            rel = (x - x0) / max(1, x1 - x0)
            v = 0 if rel < 0.6 else 1
            if 39 <= y <= 42:
                v = 2 if rel < 0.6 else 3
            c[y, x] = v
        c[y, x0] = 3
        c[y, x1] = 3
    c[38, lx - 3:lx + 5] = 3
    c[43, lx - 4:lx + 5] = 3
    c[35:37, lx] = 3                                          # Fensterchen
    c[47:52, lx - 2:lx + 1] = 3                               # Tür
    c[46, lx - 1] = 3
    c[52, lx - 6:lx + 7] = 3
    put(c, LAMP_ROOM, lx - 4, ly - 5)                         # Dach y 23-26, Glas y 27-29, Galerie y 30-31
    beam(c, st)


def beam(c, st):
    lx, ly = LAMP
    b = st["beam"]
    # 8 Zustände einer Umdrehung: 0 zur Kamera (Blitz), 1-3 Strahl links, 4 abgewandt, 5-7 Strahl rechts
    proj = [0.0, 0.55, 1.0, 0.55, 0.0, 0.55, 1.0, 0.55][b]
    side = [0, -1, -1, -1, 0, 1, 1, 1][b]
    for i in range(5):
        for j in range(3):
            x, y = lx - 2 + i, ly - 1 + j
            c[y, x] = (1 if (x + y) & 1 else 2) if b == 4 else 0
    if b == 0:                                                # Blitz: Lichtkranz
        for dx, dy, v in ((-5, 0, 0), (-6, 0, 1), (5, 0, 0), (6, 0, 1), (0, -7, 1), (-4, -3, 1), (4, -3, 1),
                          (-7, 0, 1), (7, 0, 1), (-4, 3, 1), (4, 3, 1), (-6, -2, 1), (6, -2, 1)):
            x, y = lx + dx, ly + dy
            if c[y, x] in (2, 3):
                c[y, x] = v
    if not side:
        return
    length = int(round(proj * (72 if side < 0 else 24)))
    for i in range(5, length + 5):
        x = lx + side * i
        if not (0 <= x < VIS):
            break
        half = (i - 5) // 14                                  # Kegel öffnet sich: 1, 3, 5 ... Zeilen
        fade = (i - 5) / max(1, length)
        for dy in range(-half, half + 1):
            y = ly + dy
            if not (24 <= y < 40):
                continue
            edge = abs(dy) == half and half > 0
            chk = (x + y) & 1
            if fade < 0.4 and not edge:
                v = 0
            elif fade < 0.75 and not edge:
                v = 0 if chk else 1
            elif not edge:
                v = 1 if chk else None
            else:
                v = 1 if (chk and fade < 0.7) else None
            if v is not None and c[y, x] != 0:
                c[y, x] = v


# ---------------------------------------------------------------- Boote

BOAT_A = stamp("""
.............3..............
............333.............
.............3..............
.............3..............
.............3..............
.............3..............
.............3..............
.............3..............
.............3..............
.............3............3.
..33333......3...........33.
..30003......3..........303.
..30303......3.........3003.
3333333333333333333333330033
3000000000000000000000000003
.31111111111111111111111113.
..311111111111111111111113..
...3222222222222222222223...
....33333333333333333333....
""")

BOAT_B = stamp("""
.........3............
........333...........
.........3............
.........3............
.........3............
.........3............
.........3............
.3.......3............
.33......3.....3333...
.303.....3.....3003...
.3003....3.....3033...
3300333333333333333333
3111111111111111111113
.30000000000000000003.
..311111111111111113..
...3222222222222222...
....33333333333333....
""")


def boats(c):
    put(c, BOAT_A, 42, 43)          # Rumpf y 56-61, Mast x 55
    put(c, BOAT_B, 79, 45)          # Rumpf y 55-61, Mast x 88
    for x0, x1 in ((47, 66), (83, 98)):
        for x in range(x0, x1):
            c[62, x] = 3
            if x % 2 == 0:
                c[63, x] = 3
    # Festmacher: Boot A am Kai, Boot B am Steganfang (Poller in props)
    for (xa, ya), (xb, yb) in MOORING:
        for y in range(ya, yb + 1):
            x = int(round(xa + (xb - xa) * (y - ya) / (yb - ya)))
            c[y, x] = 1                                       # Tau im Abendlicht, hell auf dunklem Wasser


MOORING = [((44, 59), (41, 71)), ((99, 58), (105, 71))]
BOLLARD = stamp("""
313
303
333
""")


# ---------------------------------------------------------------- Kai und Steg

def quay(c):
    # Kaikante (über die ganze Breite): dunkle Kante gegen das Wasser, helle Oberkante, Kantensteine
    c[QUAY_Y:H, :] = 1
    c[QUAY_Y, :] = 3
    c[QUAY_Y + 1, :] = 0
    for y in range(QUAY_Y + 2, QUAY_Y + 5):
        for x in range(W):
            c[y, x] = 2 if x % 16 == 15 else 1
    c[QUAY_Y + 5, :] = 2
    # Pflaster: ruhige helle Fläche, Platten nur mit dunklen Fugenstrichen angedeutet (Figuren davor gut lesbar)
    rows = [(78, 86, 0), (86, 95, 9), (95, 104, 4)]
    for y0, y1, off in rows:
        for y in range(y0, y1):
            for x in range(W):
                j = (x + off) % 16
                v = 1
                if y == y1 - 1 and j not in (6, 7, 8):
                    v = 2
                elif j == 15 and y0 + 1 < y < y1 - 2:
                    v = 2
                elif y == y0 and j < 12:
                    v = 0
                elif (j, y - y0) in ((4, 3), (11, 5), (12, 5)):
                    v = 2
                c[y, x] = v
    # Lichtschein der Laterne: helle Fugen (Ton 0 statt 2) im Umkreis
    lx = LANTERN[0] + 3
    for y in range(QUAY_Y + 6, H):
        for x in range(max(0, lx - 26), lx + 27):
            r = ((x - lx) / 26.0) ** 2 + ((y - 86) / 16.0) ** 2
            if r < 1.0 and c[y, x] == 1 and (x + y) % 2 == 0 and r > 0.15:
                c[y, x] = 0


def jetty(c, st):
    x0 = JETTY_X
    # Deck: Planken parallel zur Kante, nach vorn höher
    planks = [(73, 2), (75, 2), (77, 3), (80, 3), (83, 3), (86, 4)]
    for i, (y0, h) in enumerate(planks):
        for y in range(y0, y0 + h):
            for x in range(x0, W):
                j = (x + i * 11) % 32
                if y == y0 + h - 1:
                    v = 3
                elif j == 31:
                    v = 3
                elif y == y0:
                    v = 1
                else:
                    v = 2
                    if (j, y - y0) in ((7, 1), (20, 2), (21, 2)):
                        v = 3                                 # Astloch, Maserung
                c[y, x] = v
    c[QUAY_Y, x0:W] = 3
    # Stirnbalken
    c[90, x0:W] = 3
    c[91, x0:W] = 1
    c[92, x0:W] = 2
    c[93, x0:W] = 3
    # Wasser unter dem Steg und Pfähle
    water_rows(c, UNDER_ROWS, st["water"], x0, W)
    for px in range(x0 + 6, W, 16):
        for y in range(94, H):
            c[y, px] = 3
            c[y, px + 1] = 2
            c[y, px + 2] = 2
            c[y, px + 3] = 3
        c[94, px:px + 4] = 3
    # Seitenwand des Steinkais unter dem Steganfang
    for y in range(90, H):
        for x in range(x0 - 4, x0):
            c[y, x] = 3 if (x == x0 - 1 or (y - 90) % 5 == 4) else 2
    c[QUAY_Y:90, x0 - 1] = 3


# ---------------------------------------------------------------- Häuschen links

def cottage(c):
    top, base = 58, 86                       # Mauer: Bruchstein, Muster 8x8; dunkel, damit das Fenster leuchtet
    for y in range(top, base):
        for x in range(0, 40):
            r = (y - top) % 8
            off = 0 if ((y - top) // 4) % 2 == 0 else 4
            jy = r in (3, 7)
            jx = ((x + off) % 8) == 7
            v = 3 if (jy or jx) else 2
            if not jy and not jx and r in (0, 4) and (x + off) % 8 < 3:
                v = 1                                         # Abendlicht auf der Steinkante
            c[y, x] = v
        c[y, 39] = 3
        c[y, 38] = 2
    for y in range(40, 58):                  # Dach: Schiefer 8x4, rechte Kante schräg
        xr = 33 + (y - 40) // 2
        for x in range(0, xr + 1):
            r = (y - 40) % 4
            off = 0 if ((y - 40) // 4) % 2 == 0 else 4
            v = 2
            if r == 3:
                v = 3
            elif (x + off) % 8 == 0:
                v = 3
            elif r == 0 and (x + off) % 8 in (2, 3, 4):
                v = 1
            c[y, x] = v
        c[y, xr] = 3
        c[y, xr + 1] = 3
    c[39, 0:34] = 3
    c[40, 0:33] = 1
    c[58, 0:43] = 3
    c[57, 0:43] = 3
    for y in range(33, 40):                  # Schornstein x 22-30
        for x in range(22, 31):
            r = (y - 33) % 4
            v = 2 if r == 3 or (x + (4 if (y - 33) // 4 else 0)) % 8 == 7 else 1
            c[y, x] = v
        c[y, 22] = 3
        c[y, 30] = 3
    c[31, 21:32] = 3
    c[32, 21:32] = 3
    c[32, 23:30] = 2
    win = stamp("""
333333333333
300000300003
300000300003
300000300003
333333333333
300000300003
300000300003
300000300003
333333333333
.1111111111.
""")
    # Lichtschein des Fensters auf der dunklen Mauer: Ton 1 im Schachbrett, 2 px um den Rahmen
    for y in range(61, 75):
        for x in range(21, 37):
            inside = 23 <= x <= 34 and 63 <= y <= 72
            if not inside and (x + y) % 2 == 0 and c[y, x] == 2:
                c[y, x] = 1
    put(c, win, 23, 63)
    # Tür 24 px hoch (so hoch wie der Dachs), Bretter dunkel, Laibung hell vom Abendlicht
    door = stamp("""
11111111111
13333333331
13232323231
13232323231
13232323231
13232323231
13232323231
13232323231
13232323231
13232323231
13232323231
13202323231
13232323231
13232323231
13232323231
13232323231
13232323231
13232323231
13232323231
13232323231
13232323231
13232323231
13232323231
13333333331
""")
    put(c, door, 0, 61)
    c[85, 0:13] = 3
    c[84, 0:12] = 1


# ---------------------------------------------------------------- Requisiten

LANTERN_HEAD = stamp("""
...333...
..33133..
.3333333.
.3.....3.
.3.....3.
.3.....3.
.3.....3.
.3333333.
..33333..
...333...
""")

LANTERN_GLASS = [   # 5x4 Glas, drei Flackerzustände: hell, fast aus, halb (Wechsel hell/dunkel, nicht 0/1)
    stamp("""
00000
00000
00000
00000
"""),
    stamp("""
22222
22222
22022
21012
"""),
    stamp("""
22122
21012
00000
00000
"""),
]
LANTERN_HALO = {0: (4.6, 6.6), 2: (4.6, 5.6)}       # Zustand -> Ring (Radius innen, außen) aus Ton 1


def lantern(c, st):
    x, y = LANTERN
    s = st["lantern"]
    if s in LANTERN_HALO:                    # Lichtschein: Schachbrett aus Ton 1 auf dunklem Grund
        r0, r1 = LANTERN_HALO[s]
        cx, cy = x + 3, y + 2.5
        for yy in range(48, 62):
            for xx in range(56, 76):
                d = ((xx - cx) ** 2 + (yy - cy) ** 2) ** 0.5
                if r0 <= d < r1 and (xx + yy) % 2 == 0 and c[yy, xx] in (2, 3):
                    c[yy, xx] = 1
    put(c, LANTERN_HEAD, x - 1, y - 2)
    put(c, LANTERN_GLASS[s], x + 1, y + 1)
    for yy in range(y + 8, 88):              # Pfahl
        c[yy, x + 2] = 3
        c[yy, x + 3] = 2
        c[yy, x + 4] = 3
    c[86:88, x + 1:x + 6] = 3
    c[88, x:x + 7] = 3


BARREL = stamp("""
..33333333..
.3221110223.
333333333333
322211102223
322211102223
322211102223
333333333333
322211102223
322211102223
322211102223
333333333333
.3222111223.
..33333333..
""")

CRATE = stamp("""
3333333333333
3111111111113
3133333333313
3131111111313
3131311111313
3131131111313
3131113111313
3131111311313
3131111131313
3133333333313
3111111111113
3333333333333
""")

ROPE = stamp("""
..3333333333..
.311111111113.
31133333333113
31322222222313
31321111112313
.313333333313.
..3111111113..
...33333333...
""")

PARCEL_ART = stamp("""
..33...33..
...3.2.3...
.333323333.
.300020003.
.300020003.
.322222223.
.300020003.
.311121113.
..3333333..
""")                                         # Schleife oben, Schnurkreuz mittig in Ton 2 (Schnur, nicht Kante)


def props(c):
    put(c, BARREL, 42, 75)
    put(c, BARREL, 52, 77)
    put(c, ROPE, 113, 79)
    put(c, CRATE, 132, 64)
    put(c, CRATE, 145, 64)
    put(c, CRATE, 138, 76)
    put(c, PARCEL_ART, *PARCEL)
    for _, (xb, yb) in MOORING:
        put(c, BOLLARD, xb - 1, yb - 1)


def draw(state=None):
    st = {k: 0 for k in CHANNELS}
    if state:
        st.update(state)
    c = np.zeros((H, W), np.int8)
    sky(c, st)
    clouds(c)
    sea(c, st)
    headland(c)
    lighthouse(c, st)
    boats(c)
    quay(c)
    jetty(c, st)
    cottage(c)
    lantern(c, st)
    props(c)
    return c
