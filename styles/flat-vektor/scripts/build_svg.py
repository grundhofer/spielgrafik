#!/usr/bin/env python3
"""Zeichnet den Hafen von Lornholm und den Dachs-Kurier als SVG (Weg A: Vektorgrafik aus Code).

    .venv/bin/python styles/flat-vektor/scripts/build_svg.py

Schreibt assets/harbor.svg und assets/badger.svg. Beide Dateien lassen sich in jedem Vektorprogramm öffnen und
weiterbearbeiten; scripts/svg2godot.py macht daraus Polygon2D-Szenen für die Demo. Gruppen mit id sind die
animierten Teile: ihr transform="translate(…)" ist der Drehpunkt in Godot.

Formensprache: weiche Kurven (Catmull-Rom -> Bézier), flache Füllungen, höchstens ein sanfter Verlauf je Fläche,
keine Konturen. Tiefe über Luftperspektive: Je weiter hinten eine Ebene liegt, desto näher ist ihre Farbe am
Horizontlicht.
"""
import math, pathlib, random

HERE = pathlib.Path(__file__).resolve().parent.parent
W, H = 1280, 720
HORIZON = 372
QUAY_BACK = 548     # hintere Kante der Kaifläche (Wasser endet hier)
GROUND = 574        # Fußlinie des Dachses
QUAY_FRONT = 600

# Palette (Abenddämmerung): Rollen statt freier Farbwahl
P = {
    "sky0": "#17183f", "sky1": "#33296a", "sky2": "#6f3f82", "sky3": "#c35c7e", "sky4": "#f08c62", "sky5": "#ffc979",
    "haze": "#e48a83", "far": "#b8668a", "mid": "#8a4c84", "near": "#4a3873", "deep": "#2a2350",
    "rim": "#7a5a96", "sea0": "#f3a27c", "sea1": "#c86a86", "sea2": "#7a4682", "sea3": "#3a2f6c",
    "light": "#ffd88f", "lamp": "#ffe3a6", "cream": "#f6ecdc", "shade": "#d6c2cc", "red": "#e0483f", "red2": "#b8363e",
    "wall": "#b494b2", "wall2": "#94739a", "side": "#6a4c7c", "roof": "#3b2b5c", "door": "#47305a",
    "wood": "#8d5a58", "wood2": "#6b4150", "quay": "#6c5586", "quay2": "#56426f", "quayf": "#382b56", "stone": "#7b6394",
    "rope": "#c9a07a", "crate": "#a8705c", "crate2": "#84505a", "paper": "#d9a066", "string": "#fbe6c4",
}


def f(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def catmull(pts, closed=True, t=0.5):
    """Glatte Kurve durch die Punkte (Catmull-Rom als kubische Bézier-Segmente)."""
    n = len(pts)
    d = [f"M{f(pts[0][0])},{f(pts[0][1])}"]
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        p0 = pts[(i - 1) % n] if (closed or i > 0) else pts[i]
        p1, p2 = pts[i], pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if (closed or i + 2 < n) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) * t / 3, p1[1] + (p2[1] - p0[1]) * t / 3)
        c2 = (p2[0] - (p3[0] - p1[0]) * t / 3, p2[1] - (p3[1] - p1[1]) * t / 3)
        d.append(f"C{f(c1[0])},{f(c1[1])} {f(c2[0])},{f(c2[1])} {f(p2[0])},{f(p2[1])}")
    return " ".join(d) + (" Z" if closed else "")


def ridge(pts, base_y, x0, x1):
    """Silhouette: glatte Oberkante durch pts, unten gerade auf base_y geschlossen. Enden im Bild laufen weich auf
    base_y aus (keine senkrechte Stufe); Enden außerhalb des Bildes bleiben flach auf der Höhe des Randpunkts."""
    left = (x0, base_y) if x0 >= 0 else (x0, pts[0][1])
    right = (x1, base_y) if x1 <= W else (x1, pts[-1][1])
    d = catmull([left] + pts + [right], closed=False)
    return d + f" L{f(x1)},{f(base_y)} L{f(x0)},{f(base_y)} Z"


class Doc:
    def __init__(self, w, h, ident):
        self.w, self.h, self.id = w, h, ident
        self.defs, self.body, self.depth = [], [], 1

    def lin(self, gid, x1, y1, x2, y2, stops, units="userSpaceOnUse"):
        """Linearer Verlauf. userSpaceOnUse: Koordinaten im System der Form, also LOKAL in ihrer Gruppe (nach deren
        translate). objectBoundingBox: 0…1 über den Umriss jeder Form; für Formen, die einen Verlauf teilen."""
        s = "".join(f'<stop offset="{f(o)}" stop-color="{c}"' + (f' stop-opacity="{f(a)}"' if a < 1 else "") + "/>"
                    for o, c, a in [(st + (1,))[:3] for st in stops])
        self.defs.append(f'<linearGradient id="{gid}" gradientUnits="{units}" x1="{f(x1)}" y1="{f(y1)}" x2="{f(x2)}" y2="{f(y2)}">{s}</linearGradient>')
        return f"url(#{gid})"

    def rad(self, gid, cx, cy, r, stops, sy=1.0):
        s = "".join(f'<stop offset="{f(o)}" stop-color="{c}"' + (f' stop-opacity="{f(a)}"' if a < 1 else "") + "/>"
                    for o, c, a in [(st + (1,))[:3] for st in stops])
        tr = f' gradientTransform="translate({f(cx)},{f(cy)}) scale(1,{f(sy)}) translate({f(-cx)},{f(-cy)})"' if sy != 1 else ""
        self.defs.append(f'<radialGradient id="{gid}" gradientUnits="userSpaceOnUse" cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}"{tr}>{s}</radialGradient>')
        return f"url(#{gid})"

    def add(self, s):
        self.body.append("  " * self.depth + s)

    def g(self, gid=None, x=0, y=0, extra=""):
        a = (f' id="{gid}"' if gid else "") + (f' transform="translate({f(x)},{f(y)})"' if (x or y) else "") + extra
        self.add(f"<g{a}>")
        self.depth += 1
        return self

    def end(self):
        self.depth -= 1
        self.add("</g>")

    def path(self, d, fill, ident=None, op=1.0, extra=""):
        self.add(f'<path{f" id=\"{ident}\"" if ident else ""} d="{d}" fill="{fill}"' + (f' opacity="{f(op)}"' if op < 1 else "") + f"{extra}/>")

    def rect(self, x, y, w, h, fill, rx=0, ident=None, op=1.0, extra=""):
        self.add(f'<rect{f" id=\"{ident}\"" if ident else ""} x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}"' + (f' rx="{f(rx)}"' if rx else "")
                 + f' fill="{fill}"' + (f' opacity="{f(op)}"' if op < 1 else "") + f"{extra}/>")

    def circle(self, cx, cy, r, fill, ident=None, op=1.0, extra=""):
        self.add(f'<circle{f" id=\"{ident}\"" if ident else ""} cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" fill="{fill}"' + (f' opacity="{f(op)}"' if op < 1 else "") + f"{extra}/>")

    def ellipse(self, cx, cy, rx, ry, fill, ident=None, op=1.0, extra=""):
        self.add(f'<ellipse{f" id=\"{ident}\"" if ident else ""} cx="{f(cx)}" cy="{f(cy)}" rx="{f(rx)}" ry="{f(ry)}" fill="{fill}"' + (f' opacity="{f(op)}"' if op < 1 else "") + f"{extra}/>")

    def poly(self, pts, fill, ident=None, op=1.0, extra=""):
        self.path("M" + " L".join(f"{f(x)},{f(y)}" for x, y in pts) + " Z", fill, ident, op, extra)

    def write(self, path):
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" id="{self.id}" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">',
               "<defs>", *["  " + d for d in self.defs], "</defs>", *self.body, "</svg>", ""]
        pathlib.Path(path).write_text("\n".join(out))


ADD = ' data-blend="add"'


def cloud(d, gid, x, y, w, bumps, fill, base_h=12):
    """Wolke als eine Form: Umriss = Vereinigung aus Grundbalken (Kapsel) und Halbkreisen, flache Unterkante."""
    pts = []
    r0 = base_h / 2
    step = 3.0
    xs = [0.0]
    while xs[-1] < w:
        xs.append(min(w, xs[-1] + step))
    for px in xs:
        top = 0.0 - base_h if r0 <= px <= w - r0 else -r0 - math.sqrt(max(0.0, r0 * r0 - (min(px, w - px) - r0) ** 2))
        for bx, r in bumps:
            cy = -base_h * 0.5 - r * 0.35
            if abs(px - bx) < r:
                top = min(top, cy - math.sqrt(r * r - (px - bx) ** 2))
        pts.append((px, top))
    # Unterkante mit gerundeten Enden
    bottom = []
    for k in range(9):
        a = math.pi / 2 + k * math.pi / 16
        bottom.append((r0 + r0 * math.cos(a), -r0 + r0 * math.sin(a)))
    right = [(w - px, py) for px, py in reversed(bottom)]     # von rechts Mitte nach unten
    outline = pts + right[1:] + bottom[:-1]
    d.g(gid, x, y)
    d.poly(outline, fill)
    d.end()


def build_harbor():
    d = Doc(W, H, "harbor")
    rng = random.Random(20261013)

    # ---------------------------------------------------------------- Himmel
    sky = d.lin("g_sky", 0, 0, 0, HORIZON, [(0, P["sky0"]), (0.33, P["sky1"]), (0.6, P["sky2"]), (0.8, P["sky3"]), (0.93, P["sky4"]), (1, P["sky5"])])
    d.rect(-40, -40, W + 80, HORIZON + 60, sky, ident="sky")
    d.g("stars")
    k = 0
    while k < 22:
        x, y = rng.uniform(20, W - 20), rng.uniform(12, 190)
        if (x < 340 and y < 80) or (1040 < x < 1230 and y > 60):   # nicht hinter Ortsschild und Leuchtturm
            continue
        d.circle(x, y, rng.choice([1.1, 1.3, 1.5, 1.8]), "#fff3dc", ident=f"star{k}", op=0.85)
        k += 1
    for i, (x, y, s) in enumerate([(392, 58, 5), (742, 34, 6), (960, 92, 4.5)]):
        d.g(f"sparkle{i}", x, y)
        d.poly([(0, -s), (s * 0.22, -s * 0.22), (s, 0), (s * 0.22, s * 0.22), (0, s), (-s * 0.22, s * 0.22), (-s, 0), (-s * 0.22, -s * 0.22)], "#fff6e2")
        d.end()
    d.end()

    # Sonne sinkt: Mittelpunkt 10 px unter dem Horizont, das Meer deckt den unteren Teil der Scheibe (24 von 68 px sichtbar)
    SUN = (540, HORIZON + 10)
    d.g("sun")
    glow = d.rad("g_sunglow", SUN[0], SUN[1], 340, [(0, "#ffb070", 0.6), (0.4, "#ff9a6a", 0.24), (1, "#ff8a6a", 0)], sy=0.42)
    d.ellipse(SUN[0], SUN[1], 340, 143, glow, extra=ADD)
    d.circle(SUN[0], SUN[1], 34, "#fff0c4")
    d.end()

    # Wolken: Unterseite vom Abendlicht angestrahlt (heller), Oberseite kühl. Die Wolken liegen in verschobenen
    # Gruppen und teilen sich je Höhe einen Verlauf: daher objectBoundingBox (oben 0 bis unten 1 je Wolke).
    BB = "objectBoundingBox"
    c_hi = d.lin("g_cloud_hi", 0, 0, 0, 1, [(0, "#4a3678"), (1, "#a1508a")], BB)
    c_mid = d.lin("g_cloud_mid", 0, 0, 0, 1, [(0, "#7c4684"), (1, "#e07a8c")], BB)
    c_lo = d.lin("g_cloud_lo", 0, 0, 0, 1, [(0, "#c0607f"), (1, "#f6a07c")], BB)
    d.g("clouds")
    cloud(d, "cloud_a", 40, 150, 300, [(60, 24), (112, 36), (170, 30), (215, 22)], c_hi)
    cloud(d, "cloud_d", 650, 124, 180, [(48, 18), (90, 26), (132, 17)], c_hi)
    cloud(d, "cloud_b", 780, 240, 360, [(56, 20), (104, 30), (166, 40), (236, 32), (286, 22)], c_mid)
    cloud(d, "cloud_c", 290, 328, 150, [(40, 15), (76, 21), (112, 14)], c_lo, base_h=10)
    d.end()

    # Möwen (Flügel als eigene Knoten, schlagen im Code)
    d.g("gulls")
    for i, (x, y, s) in enumerate([(420, 196, 1.0), (470, 176, 0.75)]):
        d.g(f"gull{i}", x, y)
        d.g(f"gull{i}_wl")
        d.path(f"M0,0 C{f(-5*s)},{f(-9*s)} {f(-11*s)},{f(-9*s)} {f(-17*s)},{f(-3*s)} C{f(-11*s)},{f(-5*s)} {f(-6*s)},{f(-4*s)} 0,{f(2*s)} Z", "#e9dccd")
        d.end()
        d.g(f"gull{i}_wr")
        d.path(f"M0,0 C{f(5*s)},{f(-9*s)} {f(11*s)},{f(-9*s)} {f(17*s)},{f(-3*s)} C{f(11*s)},{f(-5*s)} {f(6*s)},{f(-4*s)} 0,{f(2*s)} Z", "#f6ecdc")
        d.end()
        d.ellipse(0, 0, 6 * s, 2.4 * s, "#f6ecdc")
        d.end()
    d.end()

    # ---------------------------------------------------------------- Ferne Ebenen (Luftperspektive)
    far = d.lin("g_far", 0, 340, 0, HORIZON, [(0, P["far"]), (1, P["haze"])])
    d.path(ridge([(150, 362), (230, 350), (300, 343), (360, 348), (430, 360), (470, 366)], HORIZON + 2, 120, 520), far, ident="island_far")
    d.path(ridge([(700, 366), (760, 357), (820, 353), (870, 360)], HORIZON + 2, 660, 900), far, ident="island_far2")
    mid = d.lin("g_mid", 0, 270, 0, HORIZON, [(0, P["mid"]), (1, "#b3627f")])
    d.path(ridge([(-40, 292), (40, 280), (120, 292), (200, 314), (280, 334), (340, 354), (380, 366)], HORIZON + 2, -40, 400), mid, ident="hills_mid")

    # ---------------------------------------------------------------- Meer
    sea = d.lin("g_sea", 0, HORIZON, 0, QUAY_BACK, [(0, P["sea0"]), (0.16, P["sea1"]), (0.55, P["sea2"]), (1, P["sea3"])])
    d.rect(-40, HORIZON, W + 80, QUAY_BACK - HORIZON + 30, sea, ident="sea")
    d.rect(-40, HORIZON - 1, W + 80, 2.2, "#ffdca0", ident="horizon_line", op=0.85)
    # Sonnenpfad: Glanzstriche unter der Sonne (einzeln animiert)
    d.g("sunpath", SUN[0], 0)
    for i, (y, w) in enumerate([(380, 130), (388, 104), (397, 118), (408, 80), (420, 92), (434, 58), (450, 66), (468, 40), (488, 46), (510, 28)]):
        d.g(f"sp{i}", 0, y)
        d.rect(-w / 2, -1.5, w, 3, "#ffd99a", rx=1.5, op=0.78 - i * 0.05)
        d.end()
    d.end()
    d.g("shimmer")
    k = 0
    while k < 16:
        x = rng.uniform(30, W - 50)
        y = rng.uniform(HORIZON + 12, QUAY_BACK - 8)
        if 430 < x < 650 or (690 < x < 1000 and 470 < y < 545):    # nicht im Sonnenpfad und nicht hinter den Booten
            continue
        w = rng.uniform(14, 30) * (0.6 + (y - HORIZON) / 170)
        d.g(f"sh{k}", x, y)
        d.rect(-w / 2, -1, w, 2, "#f9c3b0", rx=1, op=0.45)
        d.end()
        k += 1
    d.end()

    # ---------------------------------------------------------------- Felsnase rechts mit Spiegelung
    near = d.lin("g_near", 0, 270, 0, HORIZON + 24, [(0, "#5a4282"), (1, P["deep"])])
    rim = d.lin("g_rim", 0, 280, 0, 360, [(0, "#9068a6"), (1, "#634884")])
    low = d.lin("g_near2", 0, 340, 0, HORIZON + 22, [(0, "#3f3069"), (1, "#261e48")])
    refl = d.lin("g_refl", 0, HORIZON + 22, 0, HORIZON + 80, [(0, P["deep"], 0.6), (1, P["deep"], 0)])
    d.path(catmull([(866, HORIZON + 22), (900, HORIZON + 40), (1000, HORIZON + 58), (1120, HORIZON + 52), (1220, HORIZON + 62),
                    (1330, HORIZON + 58), (1330, HORIZON + 22)], closed=False) + " Z", refl, ident="headland_refl")
    d.path(ridge([(878, HORIZON + 6), (900, 358), (940, 342), (990, 322), (1040, 302), (1090, 291), (1132, 288), (1180, 287), (1230, 279), (1300, 268)],
                 HORIZON + 22, 862, 1320), near, ident="headland")
    d.path(catmull([(896, 360), (940, 342), (990, 322), (1040, 302), (1090, 291), (1132, 288), (1110, 296), (1066, 304), (1020, 318), (972, 336), (928, 354)]),
           rim, ident="headland_rim")
    d.path(ridge([(934, 376), (980, 364), (1050, 356), (1120, 360), (1200, 350), (1300, 354)], HORIZON + 22, 912, 1320), low, ident="headland_low")
    # Zwei Felsen vor der Spitze und eine helle Brandungslinie an der Wasserlinie
    d.rect(862, HORIZON + 21, 480, 2.4, "#c58aa8", rx=1.2, op=0.7, ident="surf")

    # ---------------------------------------------------------------- Leuchtturm (Ursprung: Fuß, Mitte)
    LX, LY = 1132, 290
    d.g("lighthouse", LX, LY)
    # Strahl (zeigt nach +x; im Code über scale.x als Projektion gedreht), hinter dem Turm
    d.g("beam", 0, -171)
    beam = d.lin("g_beam", 0, 0, 820, 0, [(0, "#ffe9b4", 0.62), (0.35, "#ffd9a0", 0.28), (1, "#ffc890", 0)])
    d.path("M0,-5 L820,-58 C826,-20 826,20 820,58 L0,5 Z", beam, extra=ADD)
    d.end()
    tower = d.lin("g_tower", -26, 0, 26, 0, [(0, "#fff7ea"), (0.55, P["cream"]), (1, P["shade"])])
    band = d.lin("g_band", -26, 0, 26, 0, [(0, "#ec5a4c"), (0.55, P["red"]), (1, P["red2"])])
    hw = lambda y: 26 - 8 * (-y / 150)
    d.poly([(-26, 0), (-hw(-150), -150), (hw(-150), -150), (26, 0)], tower)
    d.poly([(-hw(-72), -72), (-hw(-98), -98), (hw(-98), -98), (hw(-72), -72)], band)
    d.path("M-7,0 L-7,-14 C-7,-20 7,-20 7,-14 L7,0 Z", P["door"])
    d.rect(-3.5, -128, 7, 11, P["door"], rx=3)
    d.rect(-3.5, -50, 7, 11, P["door"], rx=3)
    d.rect(-27, -157, 54, 7, P["deep"], rx=2)                 # Galerie
    d.rect(-23, -164, 46, 7, P["deep"], op=0.55, rx=1)        # Geländer (halbtransparent)
    d.rect(-14, -186, 28, 30, P["lamp"], rx=3, ident="lamp_room")
    d.rect(-2, -186, 4, 30, P["deep"], op=0.8)
    d.path("M-18,-185 C-18,-200 18,-200 18,-185 Z", P["deep"])   # Kuppel
    d.rect(-1.5, -205, 3, 9, P["deep"], rx=1.5)
    d.g("lamp_glow", 0, -171)
    lg = d.rad("g_lampglow", 0, 0, 64, [(0, "#fff0c0", 0.9), (0.22, "#ffd890", 0.42), (1, "#ffb070", 0)])
    d.circle(0, 0, 64, lg, extra=ADD)
    d.end()
    d.end()

    # ---------------------------------------------------------------- Boote und Steg
    def boat(gid, x, y, s, hull, stripe, cabin, mast):
        d.g(gid, x, y)   # Ursprung: Wasserlinie Mitte (Drehpunkt fürs Schaukeln)
        d.ellipse(0, 4 * s, 78 * s, 5 * s, P["deep"], op=0.35)                # Schatten im Wasser
        if mast:
            d.rect(-14 * s, -96 * s, 3.2 * s, 86 * s, P["wood2"])
            d.path(f"M{f(-11*s)},{f(-90*s)} L{f(32*s)},{f(-22*s)} L{f(-11*s)},{f(-22*s)} Z", "#efdcd2", op=0.95)
        if cabin:
            d.rect(-38 * s, -40 * s, 34 * s, 26 * s, P["cream"], rx=3 * s)
            d.rect(-32 * s, -34 * s, 10 * s, 9 * s, P["door"], rx=2 * s)
            d.rect(-17 * s, -34 * s, 8 * s, 9 * s, P["door"], rx=2 * s)
            d.rect(-42 * s, -45 * s, 42 * s, 6 * s, P["roof"], rx=2 * s)
        d.path(f"M{f(-74*s)},{f(-18*s)} L{f(78*s)},{f(-24*s)} C{f(70*s)},{f(-2*s)} {f(52*s)},{f(6*s)} {f(30*s)},{f(7*s)} "
               f"L{f(-50*s)},{f(7*s)} C{f(-64*s)},{f(5*s)} {f(-72*s)},{f(-6*s)} {f(-74*s)},{f(-18*s)} Z", hull)
        d.path(f"M{f(-74*s)},{f(-18*s)} L{f(78*s)},{f(-24*s)} L{f(76.5*s)},{f(-17*s)} L{f(-72.5*s)},{f(-11*s)} Z", stripe)
        d.end()

    # Steg: Längssteg parallel zum Kai, Querbrücke zum Kai
    d.g("jetty")
    for x in (712, 760, 808, 856, 904, 952):
        d.rect(x - 3.5, 500, 7, 30, P["wood2"])
    d.rect(700, 496, 268, 8, P["wood"], rx=2)
    d.rect(700, 503, 268, 3, P["wood2"])
    d.poly([(862, 504), (900, 504), (912, QUAY_BACK + 1), (858, QUAY_BACK + 1)], P["wood"])
    for k in range(6):
        y0 = 504 + k * 7.5
        d.rect(860 + k * 0.1, y0 + 5.2, 50 + k * 1.8, 1.6, P["wood2"], op=0.7)
    for x in (712, 966):
        d.rect(x - 4, 484, 8, 16, P["wood2"], rx=2)
    d.end()
    # Fischerboot längsseits am Kai (Wasserlinie hinter der Kaikante), Ruderboot am Ende des Stegs
    hull_b = d.lin("g_hull_b", 0, -24, 0, 8, [(0, "#f4e8de"), (1, "#c9b2bf")])
    boat("boat_b", 790, 546, 0.82, hull_b, P["red"], True, True)
    hull_a = d.lin("g_hull_a", 0, -24, 0, 8, [(0, "#a8686a"), (1, "#6e3f55")])
    boat("boat_a", 1010, 534, 0.62, hull_a, "#e8c9a8", False, False)

    # ---------------------------------------------------------------- Häuschen links (Giebel zur Kamera)
    d.g("cottage")
    base = QUAY_BACK + 6
    d.poly([(-40, base), (-40, 430), (14, 382), (24, 382), (24, base)], P["side"])        # Seitenwand im Schatten
    d.poly([(-48, 432), (16, 374), (26, 384), (-40, 444)], P["roof"])                      # Dachkante links
    wall = d.lin("g_wall", 24, 0, 214, 0, [(0, "#c7a8c0"), (1, P["wall2"])])
    d.poly([(24, base), (24, 430), (119, 344), (214, 430), (214, base)], wall)
    for x, y, w in [(36, 520, 26), (176, 506, 24), (40, 452, 20), (184, 448, 18), (150, 534, 30), (100, 410, 22)]:
        d.rect(x, y, w, 10, "#a184a2", rx=5, op=0.8)
    d.poly([(12, 434), (119, 336), (226, 434), (226, 443), (119, 346), (12, 443)], P["roof"])   # Giebelkante
    d.rect(105, 318, 26, 44, "#8a6a92")                                                    # Schornstein
    d.rect(101, 312, 34, 8, P["roof"], rx=2)
    d.rect(54, 478, 42, base - 478, P["door"])
    d.path("M54,480 C54,462 96,462 96,480 Z", P["door"])
    d.circle(88, 518, 2.5, P["light"])
    d.g("window_glow", 160, 472)
    wg = d.rad("g_winglow", 0, 0, 80, [(0, "#ffc56e", 0.55), (0.4, "#ffb060", 0.18), (1, "#ff9a60", 0)])
    d.circle(0, 0, 80, wg, extra=ADD)
    d.end()
    win = d.lin("g_win", 0, 452, 0, 494, [(0, "#ffe6a2"), (1, "#ffb75c")])
    d.rect(138, 452, 44, 42, win, rx=3, ident="window")
    d.rect(158.5, 452, 3, 42, P["door"])
    d.rect(138, 471.5, 44, 3, P["door"])
    d.rect(134, 494, 52, 5, P["roof"], rx=2)
    d.g("smoke_origin", 118, 308)
    d.end()
    d.end()

    # ---------------------------------------------------------------- Kai
    quay = d.lin("g_quay", 0, QUAY_BACK, 0, QUAY_FRONT, [(0, P["quay"]), (1, P["quay2"])])
    d.rect(-40, QUAY_BACK, W + 80, QUAY_FRONT - QUAY_BACK, quay, ident="quay_top")
    d.rect(-40, QUAY_BACK - 1, W + 80, 4, "#9479ac", ident="quay_edge")
    for row, (y, h) in enumerate([(556, 9), (571, 11), (588, 9)]):
        x = -20 + row * 37
        while x < W:
            w = 58 + (int(x * 7 + row * 13) % 5) * 9
            d.rect(x, y, w - 8, h, P["stone"], rx=h / 2, op=0.38)
            x += w + 6
    d.rect(-40, QUAY_FRONT, W + 80, H - QUAY_FRONT + 20, P["quayf"], ident="quay_front")
    d.rect(-40, QUAY_FRONT, W + 80, 3, "#4d3c70")

    # Fässer neben dem Häuschen
    barrel = d.lin("g_barrel", 0, 0, 34, 0, [(0, "#a06560"), (1, "#6d4052")])
    for i, (x, y) in enumerate([(232, 556), (270, 560)]):
        d.g(f"barrel{i}", x, y)
        d.ellipse(17, 1, 20, 3.5, P["deep"], op=0.35)
        d.path("M2,0 C-2,-14 -2,-30 2,-44 L32,-44 C36,-30 36,-14 32,0 Z", barrel)
        d.rect(-0.5, -36, 35, 3, P["wood2"], rx=1.5)
        d.rect(-0.5, -11, 35, 3, P["wood2"], rx=1.5)
        d.ellipse(17, -44, 15, 3.6, "#b97a6c")
        d.end()

    # Laterne am Pfahl (Ausleger nach rechts)
    d.g("lantern_post")
    d.ellipse(694, QUAY_BACK + 18, 18, 3, P["deep"], op=0.35)
    d.rect(689, 426, 9, QUAY_BACK + 18 - 426, P["wood2"], rx=2)
    d.rect(686, 426, 46, 6, P["wood2"], rx=2)
    d.poly([(697, 448), (697, 441), (718, 432), (722, 432)], P["wood2"])
    d.rect(725, 431, 2, 9, P["deep"])
    d.end()
    LAN = (726, 456)
    d.g("lantern_glow", LAN[0], LAN[1])
    lgl = d.rad("g_lanternglow", 0, 0, 110, [(0, "#ffe6a8", 1), (0.16, "#ffcf80", 0.62), (0.45, "#ffaa68", 0.2), (1, "#ff9a60", 0)])
    d.circle(0, 0, 110, lgl, extra=ADD)
    d.end()
    d.g("lantern", LAN[0], 440)   # Ursprung am Haken: die Laterne pendelt im Wind
    d.path("M-9,4 L9,4 L5,-1 L-5,-1 Z", P["deep"])
    d.rect(-8, 4, 16, 22, P["lamp"], rx=2)
    d.rect(-1, 4, 2, 22, P["deep"], op=0.7)
    d.rect(-10, 25, 20, 4, P["deep"], rx=1.5)
    d.end()

    # Paket am Kai mit Hinweisring (Ring als radialer Verlauf, kein Loch nötig)
    PK = (628, GROUND)
    d.g("hotspot", PK[0] + 15, PK[1] - 10)
    hs = d.rad("g_hotspot", 0, 0, 30, [(0, "#ffd88f", 0), (0.62, "#ffd88f", 0), (0.78, "#ffe2a8", 0.85), (0.92, "#ffd88f", 0), (1, "#ffd88f", 0)])
    d.circle(0, 0, 30, hs, extra=ADD)
    d.end()
    d.g("parcel", PK[0], PK[1])
    d.ellipse(15, 0, 19, 3, P["deep"], op=0.4)
    d.rect(0, -20, 30, 20, P["paper"], rx=2.5)
    d.rect(0, -20, 30, 6, "#e9b47a", rx=2.5)
    d.rect(13.5, -20, 3, 20, P["string"])
    d.rect(0, -11.5, 30, 2.6, P["string"])
    d.path("M15,-21 C10,-28 6,-24 12,-20 Z", P["string"])
    d.path("M15,-21 C20,-28 24,-24 18,-20 Z", P["string"])
    d.end()

    # Tau und Kisten rechts vorn
    d.g("rope", 1040, 570)
    d.ellipse(0, 2, 30, 6, P["deep"], op=0.35)
    for k, (rx_, ry_, c) in enumerate([(28, 9, P["rope"]), (21, 6.6, "#a77f62"), (17, 5.2, P["rope"]), (10, 3.2, "#a77f62"), (6, 1.9, P["rope"])]):
        d.ellipse(0, -2 - k * 0.3, rx_, ry_, c)
    d.end()
    crate = d.lin("g_crate", 0, 0, 0, 1, [(0, "#bb8068"), (1, P["crate2"])], "objectBoundingBox")   # je Kiste oben -> unten
    d.g("crates", 1110, 566)
    d.ellipse(60, 2, 70, 4, P["deep"], op=0.35)
    for (x, y, s) in [(0, -46, 46), (50, -46, 46), (24, -86, 40)]:
        d.rect(x, y, s, s, crate, rx=3)
        d.rect(x + 4, y + 4, s - 8, 3, "#cf977a", rx=1.5)
        d.poly([(x + 6, y + s - 6), (x + 10, y + s - 6), (x + s - 6, y + 10), (x + s - 6, y + 6), (x + s - 10, y + 6), (x + 6, y + s - 10)], P["crate2"], op=0.7)
    d.end()

    d.write(HERE / "assets" / "harbor.svg")


# ---------------------------------------------------------------- Dachs (Gliederpuppe, schaut nach rechts)
LEG = 30   # Hüfte bis Pfotenmitte (muss zu demo/main.gd passen)


def build_badger():
    """Ursprung jeder Gruppe = Drehpunkt. Körper: Ursprung an der Hüfte. Beine zeigen nach unten (+y), Länge LEG
    bis zur Pfotenmitte; Pfoten sind eigene Knoten und werden im Code auf den Boden gesetzt."""
    d = Doc(200, 200, "badger")
    fur, fur2, fur_hi = "#3e3848", "#2b2633", "#57506a"
    cream, green, green2, brass = "#f3e7d3", "#2f6650", "#234c3d", "#e8b54e"
    red, red2, brown, brown2 = "#e0443d", "#b8323a", "#7a4632", "#5c3326"

    d.g("shadow")
    d.ellipse(0, 0, 36, 4.5, "#1d1838", op=0.45)
    d.end()
    for side, col in (("far", fur2), ("near", fur)):
        d.g(f"leg_{side}")
        d.rect(-11, -6, 22, LEG + 8, col, rx=11)
        d.end()
        d.g(f"paw_{side}")
        d.path("M-12,5 C-13,-3 -6,-7 2,-7 C10,-7 16,-2 16,5 Z", col)
        d.end()

    d.g("body")
    # ferner Arm (hinter dem Rumpf)
    d.g("arm_far", -2, -70)
    d.rect(-8, -4, 16, 46, fur2, rx=8)
    d.end()
    # Tasche am Rücken
    sat = d.lin("g_satchel", -46, 0, -14, 0, [(0, "#8d5238"), (1, brown2)])
    d.rect(-46, -40, 32, 32, sat, rx=5)
    d.path("M-46,-35 C-46,-42 -14,-42 -14,-35 L-14,-23 L-46,-23 Z", brown)
    d.circle(-30, -25, 2.3, brass)
    # Rumpf (Birne), Bauch, Weste
    torso = d.lin("g_torso", -38, 0, 40, 0, [(0, fur2), (1, fur_hi)])
    d.path("M-34,-2 C-42,-40 -30,-82 -2,-88 C26,-92 42,-64 41,-32 C40,-10 28,2 8,4 C-10,6 -28,10 -34,-2 Z", torso)
    d.path("M6,3 C26,0 39,-14 39,-36 C37,-46 27,-48 19,-42 C12,-30 4,-12 6,3 Z", cream)
    vest = d.lin("g_vest", -34, 0, 38, 0, [(0, green2), (1, green)])
    d.path("M-33,-22 C-36,-54 -27,-82 -2,-86 C20,-89 36,-74 37,-52 L36,-30 C27,-22 4,-18 -33,-22 Z", vest)
    d.path("M37,-52 C34,-62 27,-68 22,-72 L18,-36 L36,-30 Z", "#f0e2cc")          # Hemd vorn
    d.rect(4, -44, 15, 10, green2, rx=2)                                              # Tasche
    d.circle(29, -46, 2.2, brass)
    d.circle(29, -34, 2.2, brass)
    # Gurt der Tasche quer über die Weste
    d.poly([(-28, -38), (-23, -42), (26, -84), (21, -80)], brown)
    # Schal: Wickel um den Hals, hinteres Ende als eigener Knoten (weht)
    d.g("scarf_tail", -14, -82)
    d.path("M-4,-4 L6,-2 C2,14 0,30 -2,46 L-12,44 C-10,26 -8,10 -4,-4 Z", red2)
    for k in range(4):
        d.rect(-12.5 + k * 2.6, 43, 1.8, 7, red2)
    d.end()
    d.path("M-26,-86 C-22,-96 28,-98 32,-88 C34,-80 26,-74 4,-73 C-14,-72 -28,-76 -26,-86 Z", red)
    d.path("M15,-78 C21,-76 25,-68 23,-52 L15,-52 C15,-62 13,-70 15,-78 Z", red)    # vorderes Ende
    for k in range(3):
        d.rect(15.5 + k * 2.6, -53, 1.8, 6, red)
    # Kopf (Drehpunkt am Hals)
    d.g("head", 4, -90)
    d.path("M-24,-10 C-26,-30 -10,-42 6,-40 L2,2 C-10,4 -22,2 -24,-10 Z", fur, ident="head_back")
    d.circle(-14, -27, 8.5, fur, ident="ear")
    d.circle(-14, -27, 4.2, cream)
    d.path("M-12,-8 C-14,-30 2,-44 18,-40 C32,-36 42,-26 52,-14 C56,-10 52,-4 46,-4 C32,-2 12,4 -2,4 C-10,4 -12,-2 -12,-8 Z", cream, ident="face")
    d.path("M-8,-24 C2,-31 18,-31 31,-23 C39,-19 45,-15 49,-13 C41,-13 31,-12 23,-10 C13,-8 2,-8 -6,-11 C-12,-14 -12,-20 -8,-24 Z", fur, ident="eye_stripe")
    d.g("eye", 24, -20)
    d.circle(0, 0, 3.4, "#fff6e6")
    d.circle(0.9, 0, 2.1, "#1a1622")
    d.end()
    d.circle(52, -12, 4.4, "#1a1622", ident="nose")
    # Mütze
    d.path("M-24,-30 C-26,-47 -5,-58 16,-54 C31,-52 36,-43 34,-32 Z", green, ident="cap")
    d.rect(-24, -35, 58, 6, brown, rx=2)
    d.path("M26,-33 C36,-35 48,-33 52,-29 C46,-27 36,-27 24,-28 Z", green2, ident="cap_peak")
    d.circle(24, -32, 2.8, brass)
    d.end()
    # vorderer Arm, Paket unter dem Arm (Drehpunkt an der Schulter)
    d.g("arm_near", 10, -68)
    pk = d.lin("g_parcel_b", 0, 14, 0, 40, [(0, "#e2ad73"), (1, "#c48852")])
    d.rect(-6, 14, 34, 24, pk, rx=2.5)
    d.rect(9.5, 14, 3, 24, "#fbe6c4")
    d.rect(-6, 24.5, 34, 2.6, "#fbe6c4")
    d.rect(-9, -6, 18, 22, "#f0e2cc", rx=8)                       # Ärmel
    d.path("M-7,10 C-8,20 -2,30 12,34 C20,36 26,34 28,30 C26,24 18,22 10,20 C6,18 6,14 7,10 Z", fur)   # Unterarm über dem Paket
    d.circle(27, 28, 6.5, fur)                                     # Pfote an der Vorderkante
    d.end()
    d.end()
    d.write(HERE / "assets" / "badger.svg")


if __name__ == "__main__":
    build_harbor()
    build_badger()
    print("assets/harbor.svg, assets/badger.svg geschrieben")
