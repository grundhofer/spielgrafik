#!/usr/bin/env python3
"""Sektorkarte "Hafen von Lornholm" für den Raycaster-Eintrag.

Eine Karte wie bei den 2,5D-Sektor-Engines: Jeder Sektor ist ein Polygon im Grundriss mit einer
Bodenhöhe, einer Bodentextur, einer Lichtstufe (0–255) und ggf. einem Lichteffekt. Wände entstehen nur an
Sektorgrenzen und sind immer senkrecht; Böden sind waagrecht (einzige Ausnahme: das Dach des Häuschens als
Schräge wie in der Build-Engine 1996). Decken gibt es keine: alles ist Außenbereich mit Himmel.

Regeln, die der Bau einhält:
  * Zweiseitige Kante (zwei Sektoren teilen sie): Stufenwand vom niedrigeren zum höheren Boden; Textur des
    höheren Sektors, Licht des niedrigeren (die Wand gehört zur Seite, von der aus man sie sieht).
  * Einseitige Kante: Wand vom Boden bis wall_base hinunter (Kaimauer, Felswand, Bootsrumpf), Licht aus
    drop_light (Standard: das Meer davor).
  * Wände längs der Ost-West-Achse eine Lichtstufe dunkler, längs Nord-Süd eine heller ("fake contrast").
  * Texturen 32 Texel je Meter (eine 64er-Kachel = 2 m), Böden an einem festen 2-m-Raster ausgerichtet,
    Wände fortlaufend entlang der Kantenzüge.

Achsen wie shared/3d: x nach Osten, y nach oben, z nach Süden (zur Startkamera), Kai bei y = 0,
Wasserlinie y = -0,8. Ausgabe: demo/map/lornholm.json (Dreiecke je Textur) und assets/automap.png.

    python3 scripts/build_map.py
"""
import json
import math
import pathlib

import numpy as np
from PIL import Image, ImageDraw

ENTRY = pathlib.Path(__file__).resolve().parent.parent
OUT = ENTRY / "demo" / "map" / "lornholm.json"
TPM = 32.0           # Texel je Meter
WATER = -0.8
BASE = -1.4          # Unterkante einseitiger Wände (unter der Wasserlinie)

TEX_SIZE = {}
for p in (ENTRY / "assets" / "textures").glob("*.png"):
    with Image.open(p) as im:
        TEX_SIZE[p.stem] = im.size


# ---------------------------------------------------------------------------------------------
# Geometrie-Helfer

def area(loop):
    s = 0.0
    for (x0, z0), (x1, z1) in zip(loop, loop[1:] + loop[:1]):
        s += x0 * z1 - x1 * z0
    return s / 2


def orient(loop, positive=True):
    return list(loop) if (area(loop) > 0) == positive else list(reversed(loop))


def ngon(cx, cz, r, n=8, rot=22.5):
    return [(round(cx + r * math.cos(math.radians(rot + 360 * i / n)), 3),
             round(cz + r * math.sin(math.radians(rot + 360 * i / n)), 3)) for i in range(n)]


def rect(x0, z0, x1, z1):
    return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]


def boat_outline(cx, cz, length, width, bow_len=1.1):
    """Bug nach +x; Heck mit abgeschrägten Ecken."""
    hl, hw = length / 2, width / 2
    return [(cx - hl, cz - hw + 0.18), (cx - hl + 0.25, cz - hw), (cx + hl - bow_len, cz - hw),
            (cx + hl - 0.35, cz - hw * 0.55), (cx + hl, cz), (cx + hl - 0.35, cz + hw * 0.55),
            (cx + hl - bow_len, cz + hw), (cx - hl + 0.25, cz + hw), (cx - hl, cz + hw - 0.18)]


def inset(loop, d):
    """Polygon (konvex genug) um d nach innen versetzen (Schnitt der verschobenen Kanten)."""
    loop = orient(loop, True)
    n = len(loop)
    lines = []
    for i in range(n):
        (x0, z0), (x1, z1) = loop[i], loop[(i + 1) % n]
        dx, dz = x1 - x0, z1 - z0
        L = math.hypot(dx, dz)
        nx, nz = -dz / L, dx / L      # bei positiver Fläche zeigt diese Normale nach innen
        lines.append(((x0 + nx * d, z0 + nz * d), (dx, dz)))
    out = []
    for i in range(n):
        (p, r), (q, s) = lines[i - 1], lines[i]
        cr = r[0] * s[1] - r[1] * s[0]
        t = ((q[0] - p[0]) * s[1] - (q[1] - p[1]) * s[0]) / cr
        out.append((round(p[0] + t * r[0], 3), round(p[1] + t * r[1], 3)))
    return out


def point_in(loop, x, z):
    c = False
    n = len(loop)
    for i in range(n):
        (x0, z0), (x1, z1) = loop[i], loop[(i + 1) % n]
        if (z0 > z) != (z1 > z) and x < x0 + (z - z0) * (x1 - x0) / (z1 - z0):
            c = not c
    return c


# ---------------------------------------------------------------------------------------------
# Dreiecke: Ohrenschneiden mit Löchern (Brücke zum äußeren Rand)

def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _in_tri(p, a, b, c):
    d1, d2, d3 = _cross(a, b, p), _cross(b, c, p), _cross(c, a, p)
    return d1 >= -1e-12 and d2 >= -1e-12 and d3 >= -1e-12


def bridge_holes(outer, holes):
    poly = orient(outer, True)
    for hole in sorted((orient(h, False) for h in holes), key=lambda h: -max(p[0] for p in h)):
        mi = max(range(len(hole)), key=lambda i: hole[i][0])
        M = hole[mi]
        best, bi = None, None
        for i in range(len(poly)):
            a, b = poly[i], poly[(i + 1) % len(poly)]
            if (a[1] - M[1]) * (b[1] - M[1]) > 0 or a[1] == b[1]:
                continue
            t = (M[1] - a[1]) / (b[1] - a[1])
            x = a[0] + t * (b[0] - a[0])
            if x >= M[0] and (best is None or x < best):
                best = x
                bi = i if a[0] > b[0] else (i + 1) % len(poly)
        if bi is None:
            raise ValueError("Loch ohne sichtbaren Randpunkt")
        I = (best, M[1])
        P = poly[bi]
        # Spiegelpunkte im Dreieck M-I-P bevorzugen (kleinster Winkel)
        cand = bi
        bestang = None
        tri = (M, I, P) if _cross(M, I, P) > 0 else (M, P, I)
        for i, q in enumerate(poly):
            if q == P:
                continue
            prev, nxt = poly[i - 1], poly[(i + 1) % len(poly)]
            if _cross(prev, q, nxt) < 0 and _in_tri(q, *tri):
                ang = abs(math.atan2(q[1] - M[1], q[0] - M[0]))
                if bestang is None or ang < bestang:
                    bestang, cand = ang, i
        bi = cand
        ring = hole[mi:] + hole[:mi]
        poly = poly[:bi + 1] + ring + [ring[0], poly[bi]] + poly[bi + 1:]
    return poly


def triangulate(outer, holes=()):
    poly = bridge_holes(outer, list(holes)) if holes else orient(outer, True)
    idx = list(range(len(poly)))
    tris = []
    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        n = len(idx)
        for k in range(n):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % n]
            a, b, c = poly[i0], poly[i1], poly[i2]
            if _cross(a, b, c) <= 1e-12:
                continue
            ok = True
            for j in idx:
                if j in (i0, i1, i2) or poly[j] in (a, b, c):
                    continue
                if _in_tri(poly[j], a, b, c):
                    ok = False
                    break
            if ok:
                tris.append((a, b, c))
                idx.pop(k)
                break
        else:
            raise ValueError("Triangulierung hängt fest")
    tris.append(tuple(poly[i] for i in idx))
    return tris


# ---------------------------------------------------------------------------------------------
# Sektoren

SECTORS = []


def sector(name, loop, floor, ftex, light, side=None, peg=("top", None), holes=(), special=None,
           drop_light="sea", base=BASE, hole_side=None, edges=None, no_drop=False, ceil=None, ceil_tex="tarboard",
           upper=None, upper_peg=("top", None), ceil_top=None):
    """floor: Höhe oder (h0, gx, gz) für eine Schräge h = h0 + gx·x + gz·z.
    ceil: Deckenhöhe (None = Himmel). Wo ein Sektor mit Decke an Himmel grenzt, entsteht eine obere Wand
    (upper) von der Decke bis ceil_top, wie die "upper textures" der Sektor-Engines."""
    s = {"name": name, "loop": orient(loop, True), "holes": [orient(h, False) for h in holes],
         "floor": floor, "ftex": ftex, "light": light, "side": side or ftex, "peg": peg, "special": special,
         "drop_light": drop_light, "base": base, "hole_side": hole_side, "edges": edges or {},
         "no_drop": no_drop, "ceil": ceil, "ceil_tex": ceil_tex, "upper": upper or side or ftex,
         "upper_peg": upper_peg, "ceil_top": ceil_top}
    # Kantenvorgaben beziehen sich auf die Punktreihenfolge der Eingabe; nach dem Umdrehen anpassen
    if s["loop"] != list(loop) and edges:
        n = len(loop)
        s["edges"] = {(n - 2 - k) % n: v for k, v in edges.items()}
    SECTORS.append(s)
    return s


def floor_at(s, x, z):
    f = s["floor"]
    if isinstance(f, tuple):
        return f[0] + f[1] * x + f[2] * z
    return f


# Meer -------------------------------------------------------------------------------------
sector("sea", rect(-520, -760, 520, 60), WATER, "water0", 160, no_drop=True)

# Kai: Westteil reicht weiter nach Norden (Häuschen), Ostteil endet an der Hafenkante z = -1
QUAY = [(-22, 16), (11, 16), (11, -1.0), (4.25, -1.0), (2.65, -1.0), (-3.2, -1.0), (-3.2, -5.6), (-22, -5.6)]
LANTERN_POOL = [(3.0, -0.65), (5.9, -0.65), (6.7, 0.5), (5.8, 1.9), (3.6, 2.1), (2.5, 0.8)]
WINDOW_POOL = [(-4.48, -1.45), (-3.45, -1.15), (-3.45, -4.05), (-4.48, -3.75)]
sector("quay", QUAY, 0.0, "pave", 160, side="quaywall", holes=[LANTERN_POOL, WINDOW_POOL])
sector("lanternpool", LANTERN_POOL, 0.0, "pave", 240, special="fireflicker")
sector("windowpool", WINDOW_POOL, 0.0, "pave", 232)

# Steg mit zwei Paar Festmachpfählen (eine Stufe tiefer als der Kai)
sector("jetty", [(2.65, -1.0), (4.25, -1.0), (4.25, -8.6), (2.65, -8.6)], -0.18, "deck", 192, side="tarboard")
for i, (px, pz) in enumerate([(2.65, -8.6), (4.05, -8.6), (2.65, -4.6), (4.05, -4.6)]):
    sector(f"post{i}", rect(px, pz, px + 0.2, pz + 0.2), 0.62 if i < 2 else 0.48, "tarboard", 192,
           side="tarboard", drop_light="jetty")

# Häuschen: Block bis zur Traufe (2,5 m), Satteldach als zwei Schrägen (First 3,9 m, längs z)
CX0, CX1, CZ0, CZ1 = -8.5, -4.5, -4.6, -0.6
RIDGE_X, EAVE, RIDGE = -6.5, 2.5, 3.9
# Kanten: Süd (Tür), Ost (Fenster) in 2-m-Abschnitte geteilt, damit Fenster und Tür eigene Texturen tragen
# Süd: Türnische 1,2 x 0,4 m (eigener Sektor mit niedriger Decke), Ost: Fensterabschnitt mit eigenem Licht
DX0, DX1, DZ = -7.1, -5.9, CZ1 - 0.4
cottage_loop = [(CX0, CZ1), (DX0, CZ1), (DX0, DZ), (DX1, DZ), (DX1, CZ1), (CX1, CZ1), (CX1, -1.6), (CX1, -3.6),
                (CX1, CZ0), (CX0, CZ0)]
sector("cottage", cottage_loop, EAVE, "slate", 176, side="cottage", peg=("bottom", 0.0), drop_light="quay",
       edges={2: {"tex": "door", "u0": 0.0, "peg": ("bottom", 0.04)},
              6: {"tex": "cottage_win", "u0": 0.0, "light": "windowpool"}})
sector("doorway", rect(DX0, DZ, DX1, CZ1), 0.04, "quaywall_dry", 152, side="quaywall_dry", drop_light="quay",
       ceil=2.0, ceil_tex="tarboard", upper="cottage", upper_peg=("bottom", 0.0), ceil_top=EAVE)
g = (RIDGE - EAVE) / (RIDGE_X - CX0)      # Steigung je Meter (beide Dachseiten gleich)
sector("roof_e", rect(RIDGE_X, CZ0, CX1, CZ1), (EAVE + g * CX1, -g, 0.0), "slate", 176,
       side="cottage", peg=("bottom", 0.0), base=EAVE, drop_light="quay")
sector("roof_w", rect(CX0, CZ0, RIDGE_X, CZ1), (EAVE - g * CX0, g, 0.0), "slate", 176, side="cottage",
       peg=("bottom", 0.0), base=EAVE, drop_light="quay")
sector("chimney", rect(-6.85, -3.9, -6.15, -3.2), 4.9, "iron", 176, side="brick", base=3.0, drop_light="quay")

# Kisten (Sektoren wie in den Shootern der Zeit), Poller als Sprites
sector("crate1", rect(6.2, -0.75, 7.2, 0.25), 1.0, "deck", 176, side="crate", drop_light="quay", base=0.0)
sector("crate2", rect(7.2, -0.55, 8.2, 0.45), 1.0, "deck", 176, side="crate", drop_light="quay", base=0.0)
sector("crate3", rect(6.7, -0.65, 7.7, 0.35), 2.0, "deck", 176, side="crate", drop_light="quay", base=1.0)

# Boote: Rumpf als Ring (Bordwand), Innenraum tiefer; Boot A mit Ruderhaus, Boot B mit Mast
for name, (cx, cz, L, W, tex, light) in {"boat_a": (0.05, -6.1, 4.6, 1.75, "boat_a", 200),
                                         "boat_b": (6.75, -6.4, 4.0, 1.55, "boat_b", 200)}.items():
    hull = boat_outline(cx, cz, L, W)
    inner = inset(hull, 0.14)
    sector(name, hull, -0.22, "tarboard", light, side=tex, holes=[inner], hole_side="tarboard", drop_light=name)
    sector(name + "_in", inner, -0.52, "deck", light - 16, side="tarboard")
    if name == "boat_a":
        sector("wheelhouse", rect(cx - 1.2, cz - 0.55, cx - 0.1, cz + 0.55), 0.62, "plasterred", light,
               side="boatwhite", drop_light="boat_a_in", base=-0.6)
    else:
        sector("mast", rect(cx + 0.35, cz - 0.07, cx + 0.49, cz + 0.07), 2.3, "tarboard", light,
               side="tarboard", drop_light="boat_b_in", base=-0.6)

# Westhügel hinter dem Häuschen (Terrassen)
sector("hill_a", [(-30, -5.6), (-3.2, -5.6), (-2.6, -8.0), (-5.0, -13.0), (-11, -19.5), (-22, -23), (-34, -21)],
       1.0, "grass", 176, side="cliff")
sector("hill_b", [(-30, -8.6), (-7.0, -8.6), (-8.2, -13.0), (-13.0, -17.5), (-24, -19.5), (-32, -18)],
       2.6, "grass", 176, side="cliff", drop_light="hill_a")
sector("hill_c", [(-28, -10.5), (-12.5, -10.5), (-15.5, -15.0), (-25, -16.5)], 4.4, "grass", 168, side="cliff",
       drop_light="hill_b")

# Felsnase mit Leuchtturm (rechts hinten), drei Felsstufen
sector("rock_a", [(7.5, -11.0), (13.5, -10.0), (22, -13.5), (29, -22), (27, -34), (16, -39), (8, -34), (5.0, -22)],
       0.5, "cliff", 192, side="cliff")
sector("rock_b", [(8.4, -14.0), (15.0, -13.5), (21.5, -17.5), (24.5, -24), (21.5, -33), (13.5, -35), (8.6, -31),
                  (6.8, -22.5)], 1.7, "grass", 200, side="cliff", drop_light="rock_a")
sector("plateau", [(7.4, -19.8), (13.0, -19.3), (16.5, -23.0), (15.5, -29.5), (11.0, -31.5), (7.6, -29.0)],
       2.8, "grass", 208, side="cliff", drop_light="rock_b")
LX, LZ = 10.2, -25.6
sector("lh_base", ngon(LX, LZ, 2.0), 3.4, "quaywall_dry", 216, side="quaywall_dry", drop_light="plateau", base=2.0)
tower = ngon(LX, LZ, 1.25)
# Tür und Fenster auf den Seiten, die zum Hafen (Süden, +z) zeigen; Kanten 1 und 2 liegen südlich
sector("lh_tower", tower, 11.2, "iron", 208, side="lh_tower", peg=("bottom", 3.4), drop_light="lh_base", base=3.0,
       special="lighthouse",
       edges={1: {"tex": "lh_door", "peg": ("bottom", 3.4)}, 2: {"tex": "lh_tower_win", "peg": ("bottom", 3.4)},
              0: {"tex": "lh_tower_win", "peg": ("bottom", 3.4)}})
sector("lh_lamp", ngon(LX, LZ, 0.85), 12.9, "iron", 176, side="lamp", drop_light="lh_tower", base=11.0)
sector("lh_cap", ngon(LX, LZ, 0.62), 13.5, "iron", 176, side="plasterred", drop_light="lh_lamp", base=12.6)
sector("lh_cap2", ngon(LX, LZ, 0.32), 14.0, "iron", 176, side="plasterred", drop_light="lh_cap", base=13.2)
sector("lh_tip", ngon(LX, LZ, 0.08, 4, 45), 14.45, "iron", 176, side="iron", drop_light="lh_cap2", base=13.8)

# Felsen im Wasser und ferne Inseln
for i, (rx, rz, r, h) in enumerate([(5.2, -14.5, 1.1, -0.2), (-1.2, -15.8, 0.8, -0.35), (15.5, -8.2, 0.9, -0.25)]):
    sector(f"searock{i}", ngon(rx, rz, r, 6, 10 + 17 * i), h, "cliff", 176, side="cliff")
for i, (ix, iz, w, d, h) in enumerate([(-120, -230, 70, 26, 9.0), (-40, -260, 38, 14, 5.0), (60, -205, 52, 20, 7.5),
                                       (170, -300, 90, 30, 14.0), (-250, -320, 80, 28, 11.0)]):
    loop = [(ix - w / 2, iz), (ix - w / 4, iz - d / 2), (ix + w / 5, iz - d / 2.2), (ix + w / 2, iz - d / 8),
            (ix + w / 3, iz + d / 2), (ix - w / 3, iz + d / 2.2)]
    sector(f"island{i}", loop, h, "grass", 128, side="cliff")


# ---------------------------------------------------------------------------------------------
# Bau

def build():
    names = [s["name"] for s in SECTORS]
    sid = {n: i for i, n in enumerate(names)}
    surf = {}

    def add(tex, tri_pts, uvs, sec, contrast):
        d = surf.setdefault(tex, {"v": [], "uv": [], "uv2": []})
        for (x, y, z), (u, v) in zip(tri_pts, uvs):
            d["v"] += [round(x, 4), round(y, 4), round(z, 4)]
            d["uv"] += [round(u, 5), round(v, 5)]
            d["uv2"] += [sec, contrast]

    # Böden
    for i, s in enumerate(SECTORS):
        tw, th = TEX_SIZE[s["ftex"]]
        for tri in triangulate(s["loop"], s["holes"]):
            pts = [(x, floor_at(s, x, z), z) for x, z in tri]
            uvs = [(x * TPM / tw, z * TPM / th) for x, z in tri]
            add(s["ftex"], pts, uvs, i, 8)          # 8 = Boden (Lichttabelle nach Entfernung)
        if s["ceil"] is not None:
            cw, chh = TEX_SIZE[s["ceil_tex"]]
            for tri in triangulate(s["loop"], s["holes"]):
                pts = [(x, s["ceil"], z) for x, z in tri]
                uvs = [(x * TPM / cw, z * TPM / chh) for x, z in tri]
                add(s["ceil_tex"], pts, uvs, i, 8)  # Decke: wie Boden nach Entfernung

    # Kanten sammeln
    def key(p):
        return (round(p[0], 3), round(p[1], 3))

    edges = {}
    for i, s in enumerate(SECTORS):
        loops = [(s["loop"], False)] + [(h, True) for h in s["holes"]]
        for li, (loop, is_hole) in enumerate(loops):
            cum = 0.0
            n = len(loop)
            for e in range(n):
                a, b = loop[e], loop[(e + 1) % n]
                L = math.hypot(b[0] - a[0], b[1] - a[1])
                rec = {"sec": i, "a": a, "b": b, "hole": is_hole, "edge": e if li == 0 else None, "cum": cum}
                edges.setdefault(frozenset((key(a), key(b))), []).append(rec)
                cum += L
    stats = {"two_sided": 0, "one_sided": 0, "steps": 0}

    def wall(rec_hi, front_sec, bottom_fn, top_fn, tex_peg=None):
        s = SECTORS[rec_hi["sec"]]
        ov = s["edges"].get(rec_hi["edge"], {}) if rec_hi["edge"] is not None else {}
        tex = ov.get("tex") or (s["hole_side"] if rec_hi["hole"] and s["hole_side"] else s["side"])
        peg = ov.get("peg", s["peg"])
        if tex_peg:
            tex, peg = tex_peg
        front = sid[ov["light"]] if "light" in ov else front_sec
        tw, th = TEX_SIZE[tex]
        a, b = rec_hi["a"], rec_hi["b"]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        u0 = ov.get("u0", rec_hi["cum"])
        ya0, yb0 = bottom_fn(a), bottom_fn(b)
        ya1, yb1 = top_fn(a), top_fn(b)
        if max(ya1 - ya0, yb1 - yb0) < 1e-4:
            return
        if peg[0] == "top":
            ref = peg[1] if peg[1] is not None else max(ya1, yb1)
            vf = lambda y: (ref - y) * TPM / th
        else:
            ref = peg[1] if peg[1] is not None else min(ya0, yb0)
            vf = lambda y: 1.0 - (y - ref) * TPM / th
        ua, ub = u0 * TPM / tw, (u0 + L) * TPM / tw
        dx, dz = b[0] - a[0], b[1] - a[1]
        contrast = -1 if abs(dz) < 1e-6 else (1 if abs(dx) < 1e-6 else 0)
        A0, B0 = (a[0], ya0, a[1]), (b[0], yb0, b[1])
        A1, B1 = (a[0], ya1, a[1]), (b[0], yb1, b[1])
        add(tex, [A0, B0, B1], [(ua, vf(ya0)), (ub, vf(yb0)), (ub, vf(yb1))], front, contrast)
        add(tex, [A0, B1, A1], [(ua, vf(ya0)), (ub, vf(yb1)), (ua, vf(ya1))], front, contrast)

    for k, recs in edges.items():
        if len(recs) > 2:
            raise ValueError("Kante mit mehr als zwei Sektoren: %s %s" % (k, [SECTORS[r["sec"]]["name"] for r in recs]))
        if len(recs) == 2:
            stats["two_sided"] += 1
            r1, r2 = recs
            s1, s2 = SECTORS[r1["sec"]], SECTORS[r2["sec"]]
            f1 = lambda p, s=s1: floor_at(s, *p)
            f2 = lambda p, s=s2: floor_at(s, *p)
            if f1(r1["a"]) + f1(r1["b"]) > f2(r1["a"]) + f2(r1["b"]):
                r1, r2, s1, s2, f1, f2 = r2, r1, s2, s1, f2, f1
            # r2/s2 ist der höhere Sektor, die Wand blickt in s1
            if f2(r2["a"]) + f2(r2["b"]) - f1(r2["a"]) - f1(r2["b"]) > 1e-4:
                stats["steps"] += 1
                wall(r2, r1["sec"], f1, f2)
            # obere Wand, wo ein Sektor mit Decke an einen Sektor unter freiem Himmel grenzt
            for rc, ro in ((r1, r2), (r2, r1)):
                sc_, so_ = SECTORS[rc["sec"]], SECTORS[ro["sec"]]
                if sc_["ceil"] is not None and so_["ceil"] is None and floor_at(so_, *rc["a"]) < sc_["ceil"]:
                    stats["uppers"] = stats.get("uppers", 0) + 1
                    wall(rc, ro["sec"], lambda p, c=sc_["ceil"]: c, lambda p, t=sc_["ceil_top"]: t,
                         (sc_["upper"], sc_["upper_peg"]))
        else:
            stats["one_sided"] += 1
            r = recs[0]
            s = SECTORS[r["sec"]]
            if s["ceil"] is not None:
                stats["uppers"] = stats.get("uppers", 0) + 1
                wall(r, sid[s["drop_light"]], lambda p, c=s["ceil"]: c, lambda p, t=s["ceil_top"]: t,
                     (s["upper"], s["upper_peg"]))
            if s["no_drop"]:
                continue
            wall(r, sid[s["drop_light"]], lambda p, s=s: s["base"], lambda p, s=s: floor_at(s, *p))

    return names, surf, stats


def things():
    """Statische Sprites (Dekorationen wie die Fässer und Lampen der Shooter); Höhe und Sektor aus der Karte."""
    items = [
        ("barrel", -3.95, 0.35), ("barrel", -4.15, 1.15), ("rope", 0.9, -0.35),
        ("bollard", -1.6, -0.72), ("bollard", 1.7, -0.72), ("bollard", 8.6, -0.72), ("bollard", -3.55, -3.0),
        ("lanternpost", 4.6, -0.12), ("parcel", -1.45, 2.05),
    ]
    out = []
    for kind, x, z in items:
        s = find_sector(x, z)
        out.append({"kind": kind, "x": x, "z": z, "y": round(floor_at(SECTORS[s], x, z), 4), "sector": s})
    return out


def find_sector(x, z):
    best, bh = None, -1e9
    for i, s in enumerate(SECTORS):
        if point_in(s["loop"], x, z) and not any(point_in(h, x, z) for h in s["holes"]):
            h = floor_at(s, x, z)
            if h > bh:
                best, bh = i, h
    return best


def automap(names, path):
    """Grundriss wie die Kartenansicht der Shooter: Wände als Linien, Stufen heller."""
    S = 14.0
    x0, z0, x1, z1 = -24, -40, 31, 17
    W, H = int((x1 - x0) * S), int((z1 - z0) * S)
    im = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(im)
    tr = lambda p: ((p[0] - x0) * S, (p[1] - z0) * S)
    for s in SECTORS:
        col = (200, 60, 50) if s["name"] in ("sea",) else (170, 140, 90)
        if s["special"]:
            col = (230, 210, 60)
        for loop in [s["loop"]] + s["holes"]:
            d.line([tr(p) for p in loop + loop[:1]], fill=col, width=1)
    for gx in range(x0, x1 + 1, 2):
        d.line([tr((gx, z0)), tr((gx, z1))], fill=(18, 18, 30))
    for gz in range(z0, z1 + 1, 2):
        d.line([tr((x0, gz)), tr((x1, gz))], fill=(18, 18, 30))
    for s in SECTORS:
        for loop in [s["loop"]] + s["holes"]:
            d.line([tr(p) for p in loop + loop[:1]], fill=(230, 200, 140), width=1)
    for t in things():
        x, y = tr((t["x"], t["z"]))
        d.rectangle([x - 2, y - 2, x + 2, y + 2], outline=(80, 220, 80))
    im.save(path)


def main():
    names, surf, stats = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "texel_per_m": TPM,
        "sectors": [{"name": s["name"], "light": s["light"], "special": s["special"],
                     "loop": s["loop"], "holes": s["holes"],
                     "floor": list(s["floor"]) if isinstance(s["floor"], tuple) else [s["floor"], 0.0, 0.0]}
                    for s in SECTORS],
        "surfaces": surf,
        "things": things(),
    }
    OUT.write_text(json.dumps(data, separators=(",", ":")))
    automap(names, ENTRY / "assets" / "automap.png")
    ntri = sum(len(v["v"]) // 9 for v in surf.values())
    print(f"{len(SECTORS)} Sektoren, {ntri} Dreiecke, {len(surf)} Texturen; Kanten: {stats}")
    print("Dinge:", [(t['kind'], SECTORS[t['sector']]['name'], t['y']) for t in data["things"]])


if __name__ == "__main__":
    main()
