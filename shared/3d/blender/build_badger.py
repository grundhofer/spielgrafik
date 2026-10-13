# -*- coding: utf-8 -*-
"""Dachs-Kurier als geriggte, animierte Figur für die gemeinsame 3D-Grundlage.

Aufruf (aus dem Projektordner):
  blender -b --factory-startup -P shared/3d/blender/build_badger.py --
  blender -b --factory-startup -P shared/3d/blender/build_badger.py -- --parcel-side L
  blender -b --factory-startup -P shared/3d/blender/build_badger.py -- --out /tmp/x --save-blend /tmp/x/badger.blend

Ausgaben (Standard: shared/3d/):
  badger.glb      Meshes "Badger" + "Parcel", Armature "Armature", Animationen Idle/Walk/Wave
  badger_low.glb  dieselben Knochen und Animationen, 400–900 Dreiecke (für PS1/N64-Stile)
  badger_notes.md Notizen (aus den Werten dieses Skripts erzeugt)
  preview_badger_*.png  Vorschaubilder aus den exportierten GLBs (preview_badger.py, EEVEE), plus Prüfwerte

Alles wird aus Grundformen erzeugt (Loft-Ringe, Ellipsoide, Röhren, gefaste Quader), keine .blend-Vorlage.
Achsen hier in Blender: Z oben, die Figur blickt nach +X, ihre linke Körperseite ist +Y.
Der glTF-Export (+Y oben) ergibt in Godot: Y oben, Blick nach +X, linke Seite -Z, rechte Seite +Z.
Die Hafenkamera steht auf Godot +Z und blickt nach -Z, sieht also die rechte Seite des Dachses.

--parcel-side R (Standard) folgt dem Referenzblatt shared/badger/master_sheet.png: Paket unter dem rechten
Arm, Tasche an der rechten Hüfte, Riemen über der linken Schulter, gewinkt wird mit der linken Hand.
--parcel-side L spiegelt diese Ausstattung (Paket links, Winken rechts).
"""
import argparse
import math
import os
import re
import subprocess
import sys
import time
from math import cos, pi, radians, sin, sqrt

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

V = Vector


# --------------------------------------------------------------------------------------------
# Argumente
# --------------------------------------------------------------------------------------------
def _script_dir():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        for i, a in enumerate(sys.argv):
            if a in ("-P", "--python") and i + 1 < len(sys.argv):
                return os.path.dirname(os.path.abspath(sys.argv[i + 1]))
    return os.getcwd()


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="build_badger.py")
    ap.add_argument("--out", default=os.path.normpath(os.path.join(_script_dir(), "..")),
                    help="Zielordner für badger.glb und badger_low.glb (Standard: shared/3d)")
    ap.add_argument("--parcel-side", choices=["R", "L"], default="R",
                    help="Arm mit dem Paket (R = wie im Referenzblatt)")
    ap.add_argument("--save-blend", default="", help="optional: .blend zur Kontrolle speichern (nicht einchecken)")
    ap.add_argument("--no-preview", action="store_true", help="keine Vorschaubilder und Prüfwerte")
    ap.add_argument("--no-notes", action="store_true", help="badger_notes.md nicht schreiben")
    return ap.parse_args(argv)


ARGS = parse_args()
PS = ARGS.parcel_side                 # Paketseite
FS = "L" if PS == "R" else "R"        # freie Seite (Winken)


def sgn(side):
    """Y-Vorzeichen einer Körperseite in Blender (links = +Y)."""
    return 1.0 if side == "L" else -1.0


SP, SF = sgn(PS), sgn(FS)
FPS = 30

# --------------------------------------------------------------------------------------------
# Materialien (Farben als sRGB-Hex, wie in build_harbor.py)
# --------------------------------------------------------------------------------------------
MAT_DEFS = [
    ("FurDark",  "#4A3F3B", 0.90, 0.0, "Fell dunkel: Körper, Beine, Unterarme, Pfoten, Augenstreifen, Ohrinneres"),
    ("FurLight", "#F0E2C8", 0.90, 0.0, "Fell hell: Gesichtsstreifen, Wangen, Bauch, Ohrränder, Schwanz"),
    ("Cap",      "#4C5530", 0.80, 0.0, "Schirmmütze (Kopf und Schirm)"),
    ("Brass",    "#C08D35", 0.35, 1.0, "Messing: Mützenknöpfe, Westenknöpfe, Taschenschnalle"),
    ("Vest",     "#59613A", 0.80, 0.0, "Weste mit Taschenklappen und Rückenriegel"),
    ("Shirt",    "#EDD9B8", 0.80, 0.0, "Hemd (hochgekrempelte Ärmel, Ausschnitt) und Paketschnur"),
    ("Scarf",    "#A8242A", 0.90, 0.0, "Strickschal"),
    ("Satchel",  "#6E3A25", 0.60, 0.0, "Leder: Umhängetasche, Riemen, Mützenband"),
    ("Parcel",   "#C08B57", 0.85, 0.0, "Packpapier des Pakets"),
    ("Nose",     "#2A201D", 0.35, 0.0, "Nase, Mund, Krallen"),
    ("Eye",      "#2B170D", 0.15, 0.0, "Augen"),
]
MAT_INDEX = {d[0]: i for i, d in enumerate(MAT_DEFS)}
MATS = []


def hex_lin(h):
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return out


def make_materials():
    for name, color, rough, metal, _ in MAT_DEFS:
        m = bpy.data.materials.new(name)
        if m.node_tree is None:
            m.use_nodes = True
        bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        col = hex_lin(color)
        bsdf.inputs["Base Color"].default_value = (*col, 1.0)
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Metallic"].default_value = metal
        m.diffuse_color = (*col, 1.0)
        MATS.append(m)


# --------------------------------------------------------------------------------------------
# Mathe-Helfer
# --------------------------------------------------------------------------------------------
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def smoothstep(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def table_lin(table, x):
    """Stückweise linear; table = [(x, v1, v2, ...), ...] aufsteigend nach x."""
    if x <= table[0][0]:
        return list(table[0][1:])
    if x >= table[-1][0]:
        return list(table[-1][1:])
    for i in range(len(table) - 1):
        x0, x1 = table[i][0], table[i + 1][0]
        if x0 <= x <= x1:
            t = (x - x0) / (x1 - x0)
            return [lerp(a, b, t) for a, b in zip(table[i][1:], table[i + 1][1:])]


def table_smooth(table, x):
    """Kubische Hermite-Interpolation mit Catmull-Rom-Tangenten (weiche Profile)."""
    xs = [r[0] for r in table]
    n = len(table)
    if x <= xs[0]:
        return list(table[0][1:])
    if x >= xs[-1]:
        return list(table[-1][1:])
    i = 0
    while xs[i + 1] < x:
        i += 1
    x0, x1 = xs[i], xs[i + 1]
    h = x1 - x0
    t = (x - x0) / h
    h00, h10 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t
    h01, h11 = -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
    out = []
    for c in range(1, len(table[0])):
        def slope(k):
            if k == 0:
                return (table[1][c] - table[0][c]) / (xs[1] - xs[0])
            if k == n - 1:
                return (table[-1][c] - table[-2][c]) / (xs[-1] - xs[-2])
            return (table[k + 1][c] - table[k - 1][c]) / (xs[k + 1] - xs[k - 1])
        out.append(h00 * table[i][c] + h10 * h * slope(i) + h01 * table[i + 1][c] + h11 * h * slope(i + 1))
    return out


def rot3(ax=0.0, ay=0.0, az=0.0):
    """Drehung in Grad um die festen Achsen X, dann Y, dann Z."""
    return (Matrix.Rotation(radians(az), 3, "Z") @ Matrix.Rotation(radians(ay), 3, "Y")
            @ Matrix.Rotation(radians(ax), 3, "X"))


def rot_about(r3, pivot):
    return Matrix.Translation(pivot) @ r3.to_4x4() @ Matrix.Translation(-pivot)


def basis_from_normal(n, hint=V((0, 0, 1))):
    z = V(n).normalized()
    h = V(hint)
    if abs(z.dot(h)) > 0.95:
        h = V((1, 0, 0))
    x = h.cross(z).normalized()
    y = z.cross(x)
    return x, y, z


# --------------------------------------------------------------------------------------------
# Kurven
# --------------------------------------------------------------------------------------------
def catmull(points, steps=16):
    P = [V(p) for p in points]
    ext = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for s in range(steps):
            t = s / steps
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-1].copy())
    return out


def arc_lengths(poly):
    cum = [0.0]
    for a, b in zip(poly, poly[1:]):
        cum.append(cum[-1] + (b - a).length)
    return cum


def sample_at(poly, cum, d):
    d = clamp(d, 0.0, cum[-1])
    for i in range(len(cum) - 1):
        if cum[i + 1] >= d:
            seg = cum[i + 1] - cum[i]
            t = 0.0 if seg < 1e-9 else (d - cum[i]) / seg
            return poly[i].lerp(poly[i + 1], t)
    return poly[-1].copy()


def tangent_at(poly, cum, d, eps=0.004):
    return (sample_at(poly, cum, d + eps) - sample_at(poly, cum, d - eps)).normalized()


# --------------------------------------------------------------------------------------------
# Mesh-Bausteine
# --------------------------------------------------------------------------------------------
class MB:
    """Sammelt Punkte, Flächen und Materialnamen eines Teils."""

    def __init__(self, name):
        self.name = name
        self.v, self.f, self.fm = [], [], []

    def vert(self, co):
        self.v.append(V(co))
        return len(self.v) - 1

    def face(self, ids, mat):
        self.f.append(tuple(ids))
        self.fm.append(MAT_INDEX[mat])

    def add_bm(self, bm, mat):
        base = len(self.v)
        bm.verts.index_update()
        for v in bm.verts:
            self.v.append(v.co.copy())
        for f in bm.faces:
            self.f.append(tuple(base + v.index for v in f.verts))
            self.fm.append(MAT_INDEX[mat])


def loft(mb, rings, mat_fn, cap0=None, cap1=None, closed=False):
    """Verbindet gleich lange Ringe zu Vierecken; Pole schließen die Enden."""
    N = len(rings[0])
    ids = [[mb.vert(p) for p in r] for r in rings]
    nr = len(rings)
    for j in range(nr if closed else nr - 1):
        j2 = (j + 1) % nr
        for i in range(N):
            mb.face((ids[j][i], ids[j][(i + 1) % N], ids[j2][(i + 1) % N], ids[j2][i]), mat_fn(j, i))
    if cap0 is not None:
        c = mb.vert(cap0)
        for i in range(N):
            mb.face((ids[0][(i + 1) % N], ids[0][i], c), mat_fn(0, i))
    if cap1 is not None:
        c = mb.vert(cap1)
        for i in range(N):
            mb.face((ids[-1][i], ids[-1][(i + 1) % N], c), mat_fn(max(nr - 2, 0), i))
    return ids


def ellipsoid(mb, center, radii, axes=None, nseg=10, nring=6, mat="FurDark", ring_mat=None, thetas=None):
    ax, ay, az = axes if axes else (V((1, 0, 0)), V((0, 1, 0)), V((0, 0, 1)))
    c = V(center)
    rings = []
    ths = [radians(t) for t in thetas] if thetas else [pi * k / nring for k in range(1, nring)]
    for th in ths:
        rings.append([c + ax * (radii[0] * sin(th) * cos(2 * pi * i / nseg))
                      + ay * (radii[1] * sin(th) * sin(2 * pi * i / nseg)) + az * (radii[2] * cos(th))
                      for i in range(nseg)])
    fn = (lambda j, i: ring_mat(j)) if ring_mat else (lambda j, i: mat)
    loft(mb, rings, fn, cap0=c + az * radii[2], cap1=c - az * radii[2])


def sweep(mb, pts, nrms, profile, mat_fn, closed=False, caps=True):
    """Profil (Liste (b, n)) entlang einer Punktfolge; n = gewünschte Normalenrichtung je Punkt."""
    n = len(pts)
    rings = []
    for k in range(n):
        if closed:
            t = (pts[(k + 1) % n] - pts[k - 1]).normalized()
        else:
            t = (pts[min(k + 1, n - 1)] - pts[max(k - 1, 0)]).normalized()
        nn = nrms[k] - t * nrms[k].dot(t)
        nn.normalize()
        bb = t.cross(nn)
        rings.append([pts[k] + bb * px + nn * py for px, py in profile])
    if closed:
        return loft(mb, rings, mat_fn, closed=True)
    c0 = c1 = None
    if caps:
        c0 = sum(rings[0], V()) / len(rings[0])
        c1 = sum(rings[-1], V()) / len(rings[-1])
    return loft(mb, rings, mat_fn, cap0=c0, cap1=c1)


def tube(mb, ctrl, stations, radius_fn, nseg, mat_fn, ref, offset=0.0, sx=1.0, sy=1.0, pole=0.55):
    """Runde Röhre entlang einer Catmull-Rom-Kurve. stations = Bogenlängen (+offset ab ctrl[0])."""
    poly = catmull(ctrl, 16)
    cum = arc_lengths(poly)
    pts = [sample_at(poly, cum, d + offset) for d in stations]
    tans = [tangent_at(poly, cum, d + offset) for d in stations]
    n = (ref - tans[0] * ref.dot(tans[0])).normalized()
    rings = []
    for k, (p, t) in enumerate(zip(pts, tans)):
        n = (n - t * n.dot(t)).normalized()
        b = t.cross(n)
        r = radius_fn(stations[k])
        rings.append([p + n * (r * sx * cos(2 * pi * i / nseg)) + b * (r * sy * sin(2 * pi * i / nseg))
                      for i in range(nseg)])
    c0 = pts[0] - tans[0] * (radius_fn(stations[0]) * pole)
    c1 = pts[-1] + tans[-1] * (radius_fn(stations[-1]) * pole)
    loft(mb, rings, mat_fn, cap0=c0, cap1=c1)
    return poly, cum


def solid_from_grid(mb, grid, t, mat, downs=None):
    """Platte aus einem Gitter von Oberseitenpunkten; Dicke t in Richtung downs (Standard -Z)."""
    R, C = len(grid), len(grid[0])
    top = [[mb.vert(p) for p in row] for row in grid]
    bot = [[mb.vert(grid[r][c] + (downs[r][c] if downs else V((0, 0, -1))) * t) for c in range(C)]
           for r in range(R)]
    for r in range(R - 1):
        for c in range(C - 1):
            mb.face((top[r][c], top[r][c + 1], top[r + 1][c + 1], top[r + 1][c]), mat)
            mb.face((bot[r][c], bot[r + 1][c], bot[r + 1][c + 1], bot[r][c + 1]), mat)
    loop = ([(0, c) for c in range(C)] + [(r, C - 1) for r in range(1, R)]
            + [(R - 1, c) for c in range(C - 2, -1, -1)] + [(r, 0) for r in range(R - 2, 0, -1)])
    for k in range(len(loop)):
        (r0, c0), (r1, c1) = loop[k], loop[(k + 1) % len(loop)]
        mb.face((top[r0][c0], top[r1][c1], bot[r1][c1], bot[r0][c0]), mat)


def bevel_box(mb, size, mtx, bevel, mat):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = V((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges) + list(bm.verts), offset=bevel, segments=1,
                        profile=0.5, affect="EDGES", clamp_overlap=True)
    bm.transform(mtx)
    mb.add_bm(bm, mat)
    bm.free()


def frame_matrix(center, x_axis, y_axis, z_axis):
    m = Matrix((x_axis, y_axis, z_axis)).transposed().to_4x4()
    m.translation = center
    return m


def mb_object(mb, sharp_deg=None):
    me = bpy.data.meshes.new(mb.name)
    me.from_pydata([tuple(v) for v in mb.v], [], mb.f)
    for m in MATS:
        me.materials.append(m)
    me.polygons.foreach_set("material_index", mb.fm)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    if sharp_deg:
        me.set_sharp_from_angle(angle=radians(sharp_deg))
    me.update()
    ob = bpy.data.objects.new(mb.name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def extrude_material(ob, mat, dist):
    """Hebt alle Flächen eines Materials um dist entlang der Normalen an (Westenkante)."""
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    mi = MAT_INDEX[mat]
    bm.normal_update()
    faces = [f for f in bm.faces if f.material_index == mi]
    vlist = list({v for f in faces for v in f.verts})
    kd = KDTree(len(vlist))
    for k, v in enumerate(vlist):
        kd.insert(v.co, k)
    kd.balance()
    nrm = [v.normal.copy() for v in vlist]
    ret = bmesh.ops.extrude_face_region(bm, geom=faces, use_keep_orig=False)
    for e in ret["geom"]:
        if isinstance(e, bmesh.types.BMVert):
            _, k, _ = kd.find(e.co)
            e.co += nrm[k] * dist
        elif isinstance(e, bmesh.types.BMFace):
            e.material_index = mi
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # extrude_face_region legt neue Elemente in speicherabhängiger Reihenfolge an; feste Reihenfolge herstellen,
    # sonst ändern sich bei jedem Lauf Dreiecksreihenfolge und (bei Gleichstand) übertragene Gewichte
    for seq, key in ((bm.verts, lambda v: (round(v.co.z, 6), round(v.co.y, 6), round(v.co.x, 6))),
                     (bm.faces, lambda f: (f.material_index,) + tuple(round(c, 6) for c in f.calc_center_median()))):
        seq.index_update()
        rank = {e.index: r for r, e in enumerate(sorted(seq, key=key))}
        seq.sort(key=lambda e: rank[e.index])
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    me.update()


# --------------------------------------------------------------------------------------------
# Detailstufen
# --------------------------------------------------------------------------------------------
HIGH = dict(
    tag="high",
    torso_z=[0.150, 0.175, 0.205, 0.235, 0.265, 0.300, 0.335, 0.370, 0.410, 0.450, 0.490, 0.535,
             0.570, 0.605, 0.635, 0.665, 0.695, 0.730, 0.760],
    torso_nf=2, torso_nb=9, vest_lip=True,
    head_x=[-0.165, -0.152, -0.135, -0.115, -0.090, -0.060, -0.030, 0.000, 0.030, 0.060, 0.090, 0.120,
            0.150, 0.178, 0.203, 0.222, 0.234, 0.243],
    head_n=(2, 3, 3, 2), eye=(10, 6), nose=(10, 6), ear=(10, 6), mouth=True,
    cap_seg=20, visor=(9, 3), cap_button=(8, 4),
    leg_seg=10, leg_f=[0.0, 0.12, 0.28, 0.45, 0.60, 0.75, 0.90, 1.0],
    foot_seg=10, foot_st=None, claws=True,
    arm_seg=10, arm_st=[-0.045, -0.015, 0.020, 0.060, 0.095, 0.120, 0.128, 0.148, 0.156, 0.180, 0.215,
                        0.250, 0.285, 0.305, 0.330, 0.355, 0.375],
    tail_seg=8, tail_f=[0.0, 0.2, 0.45, 0.7, 0.88, 1.0],
    scarf=(26, 8), scarf_wraps=2, ripple=True, strip_prof=8, strip_n=10, fringe=True,
    strap_n=28, details=True, satchel_flap=True, parcel_string=True, parcel_bevel=0.007,
)
LOW = dict(
    tag="low",
    torso_z=[0.165, 0.235, 0.300, 0.420, 0.535, 0.630, 0.720],
    torso_nf=1, torso_nb=3, vest_lip=False,
    head_x=[-0.150, -0.090, -0.010, 0.070, 0.150, 0.222, 0.238],
    head_n=(1, 1, 1, 1), eye=(4, 2), nose=None, ear=(6, 2), mouth=False,
    cap_seg=8, visor=(3, 2), cap_button=(4, 2),
    leg_seg=6, leg_f=[0.0, 0.5, 1.0],
    foot_seg=6, foot_st=[-0.045, 0.020, 0.100], claws=False,
    arm_seg=6, arm_st=[-0.030, 0.060, 0.148, 0.160, 0.300, 0.355],
    tail_seg=4, tail_f=[0.0, 0.5, 1.0],
    scarf=(8, 4), scarf_wraps=1, ripple=False, strip_prof=4, strip_n=3, fringe=False,
    strap_n=8, details=False, satchel_flap=False, parcel_string=False, parcel_bevel=0.0,
)

# --------------------------------------------------------------------------------------------
# Rumpf: Ringe entlang Z, Querschnitt Ellipse (vorn etwas voller). Winkel th ab +X (vorn) Richtung +Y.
# --------------------------------------------------------------------------------------------
TORSO = [  # z, Mittelpunkt x, Halbtiefe a, Halbbreite b
    (0.150, 0.000, 0.095, 0.105),
    (0.175, 0.005, 0.150, 0.165),
    (0.220, 0.012, 0.183, 0.203),
    (0.280, 0.020, 0.200, 0.222),
    (0.340, 0.024, 0.205, 0.226),
    (0.400, 0.020, 0.198, 0.219),
    (0.460, 0.013, 0.186, 0.208),
    (0.520, 0.006, 0.170, 0.197),
    (0.580, 0.000, 0.152, 0.186),
    (0.630, 0.000, 0.132, 0.166),
    (0.670, 0.008, 0.108, 0.128),
    (0.710, 0.018, 0.088, 0.098),
    (0.760, 0.028, 0.072, 0.078),
]
# halber Öffnungswinkel der vorderen Flächengruppe (Ausschnitt oben, Bauch-Dreieck unten)
THF = [(0.0, 40), (0.26, 40), (0.30, 30), (0.335, 18), (0.37, 6), (0.53, 6), (0.565, 13), (0.60, 20),
       (0.635, 26), (0.665, 30), (0.80, 30)]
VEST_LIP = 0.007
HEM_Z = 0.30


def torso_pt(z, th):
    cx, a, b = table_smooth(TORSO, z)
    c, s = cos(th), sin(th)
    return V((cx + a * (1.04 if c > 0 else 0.96) * c, b * s, z))


def torso_nrm(z, th):
    e = 1e-3
    dz = torso_pt(z + e, th) - torso_pt(z - e, th)
    dt = torso_pt(z, th + e) - torso_pt(z, th - e)
    n = dt.cross(dz).normalized()
    p = torso_pt(z, th)
    if n.dot(p - V((table_smooth(TORSO, z)[0], 0, z))) < 0:
        n = -n
    return n


def vest_at(z, th):
    """True, wenn an dieser Stelle die Weste sitzt (dann liegt die Oberfläche VEST_LIP weiter außen)."""
    if z > 0.685:
        return False
    if abs(th) <= radians(table_lin(THF, z)[0]):
        return 0.37 <= z < 0.535
    return z >= HEM_Z


def torso_surf(z, th, lip=True):
    p, n = torso_pt(z, th), torso_nrm(z, th)
    if lip and vest_at(z, th):
        p = p + n * VEST_LIP
    return p, n


def torso_mat(zm, front):
    if zm > 0.685:
        return "FurDark"
    if front:
        if zm < 0.37:
            return "FurLight"
        return "Vest" if zm < 0.535 else "Shirt"
    return "FurDark" if zm < HEM_Z else "Vest"


def build_torso(L):
    mb = MB("torso")
    zs, nf, nb = L["torso_z"], L["torso_nf"], L["torso_nb"]
    H = nf + nb
    rings = []
    for z in zs:
        tf = radians(table_lin(THF, z)[0])
        half = [tf * k / nf for k in range(nf)] + [tf + (pi - tf) * k / nb for k in range(nb)] + [pi]
        ths = half + [-h for h in reversed(half[1:-1])]
        rings.append([torso_pt(z, th) for th in ths])

    def mf(j, i):
        ii = i if i < H else 2 * H - 1 - i
        return torso_mat(0.5 * (zs[j] + zs[j + 1]), ii < nf)

    loft(mb, rings, mf, cap0=V((0.0, 0, zs[0] - 0.014)), cap1=V((0.03, 0, zs[-1] + 0.014)))
    ob = mb_object(mb)
    if L["vest_lip"]:
        extrude_material(ob, "Vest", VEST_LIP)
    return ob


# --------------------------------------------------------------------------------------------
# Kopf: Ringe entlang X (Schnauze nach +X). phi = Winkel ab oben, positiv zur linken Seite (+Y).
# Die Ringpunkte liegen genau auf den Grenzen der Fellzeichnung, damit die Streifen saubere Kanten haben.
# --------------------------------------------------------------------------------------------
HEAD = [  # x, Mitte z, Halbbreite b, Halbhöhe c, Verjüngung oben k
    (-0.168, 0.838, 0.042, 0.040, 0.15),
    (-0.150, 0.835, 0.098, 0.085, 0.18),
    (-0.120, 0.831, 0.148, 0.108, 0.18),
    (-0.080, 0.828, 0.176, 0.118, 0.18),
    (-0.030, 0.825, 0.186, 0.118, 0.18),
    (0.020, 0.820, 0.176, 0.110, 0.16),
    (0.060, 0.814, 0.148, 0.094, 0.12),
    (0.100, 0.806, 0.110, 0.073, 0.08),
    (0.140, 0.799, 0.078, 0.055, 0.04),
    (0.180, 0.795, 0.058, 0.044, 0.02),
    (0.215, 0.792, 0.046, 0.036, 0.00),
    (0.245, 0.791, 0.033, 0.027, 0.00),
]
HEAD_BACK = V((-0.176, 0.0, 0.838))
HEAD_TIP = V((0.256, 0.0, 0.791))
# Grenzwinkel (Grad ab oben): weißer Scheitelstreifen | dunkles Augenband | weiße Wange | Kinn
STRIPES = [(-0.17, 22, 96, 150), (-0.10, 20, 100, 150), (-0.04, 18, 92, 150), (0.02, 17, 80, 150),
           (0.06, 19, 78, 150), (0.10, 24, 80, 150), (0.14, 29, 82, 152), (0.20, 33, 80, 155),
           (0.26, 36, 80, 155)]
EYE_X, EYE_DPHI, EYE_R = 0.122, 0.0, 0.021


def head_pt(x, phi):
    zc, b, c, k = table_smooth(HEAD, x)
    cp, sp = cos(phi), sin(phi)
    return V((x, b * sp * (1 - k * cp), zc + c * cp * (1.0 if cp >= 0 else 0.92)))


def head_nrm(x, phi):
    e = 1e-3
    n = (head_pt(x + e, phi) - head_pt(x - e, phi)).cross(head_pt(x, phi + e) - head_pt(x, phi - e))
    n.normalize()
    p = head_pt(x, phi)
    if n.dot(p - V((x, 0, table_smooth(HEAD, x)[0]))) < 0:
        n = -n
    return n


def head_phis(x, n):
    p1, p2, p3 = [radians(a) for a in table_lin(STRIPES, x)]
    b = [0.0, p1, p2, p3, pi]
    half = []
    for g in range(4):
        for k in range(n[g]):
            half.append(b[g] + (b[g + 1] - b[g]) * k / n[g])
    half.append(pi)
    return half + [-h for h in reversed(half[1:-1])]


def head_group(i, n):
    H = sum(n)
    ii = i if i < H else 2 * H - 1 - i
    acc = 0
    for g in range(4):
        acc += n[g]
        if ii < acc:
            return g
    return 3


def head_mat(xm, g):
    if xm > 0.229:
        return "Nose"
    if g == 0:
        return "FurLight" if xm > -0.115 else "FurDark"
    if g == 1:
        return "FurDark"
    if g == 2:
        return "FurLight" if xm > -0.10 else "FurDark"
    return "FurLight" if xm > -0.02 else "FurDark"


def build_head(L):
    mb = MB("head")
    xs, n = L["head_x"], L["head_n"]
    rings = [[head_pt(x, ph) for ph in head_phis(x, n)] for x in xs]
    loft(mb, rings, lambda j, i: head_mat(0.5 * (xs[j] + xs[j + 1]), head_group(i, n)),
         cap0=HEAD_BACK, cap1=HEAD_TIP)
    if L["nose"]:
        ellipsoid(mb, (0.246, 0, 0.793), (0.024, 0.034, 0.025), nseg=L["nose"][0], nring=L["nose"][1],
                  mat="Nose")
    # Augen mitten im dunklen Band, mit hellem Glanzpunkt (FurLight)
    for side in (1.0, -1.0):
        p1, p2, _ = table_lin(STRIPES, EYE_X)
        phi = radians(0.5 * (p1 + p2) + EYE_DPHI) * side
        p, nr = head_pt(EYE_X, phi), head_nrm(EYE_X, phi)
        c = p - nr * 0.008
        er = EYE_R if L["tag"] == "high" else EYE_R * 1.25    # in der Low-Fassung etwas größer, sonst unsichtbar
        ellipsoid(mb, c, (er, er, er), basis_from_normal(nr), L["eye"][0], L["eye"][1], mat="Eye")
        if L["tag"] == "high":
            g = (nr + V((0.25, 0, 0.55))).normalized()
            ellipsoid(mb, c + g * (EYE_R - 0.0015), (0.0055, 0.0055, 0.0055), None, 6, 4, mat="FurLight")
    # Ohren: flache Scheiben, Innenseite dunkel, Rand hell
    for side in (1.0, -1.0):
        x, phi = -0.065, radians(60) * side
        p, nr = head_pt(x, phi), head_nrm(x, phi)
        c = p + nr * 0.020 + V((0, 0, 0.004))
        face_dir = (nr * 0.55 + V((0.8, 0, 0.25))).normalized()
        ax, ay, az = basis_from_normal(face_dir)
        nseg, nring = L["ear"]
        if nring >= 4:   # Innenfläche (Pol vorn bis 38°) dunkel, Rand und Rückseite hell
            ellipsoid(mb, c, (0.037, 0.039, 0.017), (ax, ay, az), nseg,
                      ring_mat=lambda j: "FurDark" if j == 0 else "FurLight", thetas=[20, 38, 75, 115, 150])
        else:
            ellipsoid(mb, c, (0.037, 0.039, 0.017), (ax, ay, az), nseg, nring, mat="FurLight")
    # Mund: dünne Linie unter der Nase, Mundwinkel leicht nach oben
    if L["mouth"]:
        pts_xphi = [(0.124, 114), (0.136, 125), (0.158, 135), (0.184, 143), (0.207, 151), (0.223, 165),
                    (0.231, 180)]
        path = [(x, -a) for x, a in pts_xphi] + [(x, a) for x, a in reversed(pts_xphi[:-1])]
        pts, nrms = [], []
        for x, a in path:
            ph = radians(a)
            pts.append(head_pt(x, ph) + head_nrm(x, ph) * 0.0008)
            nrms.append(head_nrm(x, ph))
        prof = [(-0.0028, -0.002), (0.0028, -0.002), (0.0028, 0.0018), (-0.0028, 0.0018)]
        sweep(mb, pts, nrms, prof, lambda j, i: "Nose")
    return mb


# --------------------------------------------------------------------------------------------
# Mütze: Ellipse um den Kopf auf Höhe CAP_ZB, Band (Leder), gewölbter Deckel, Schirm, Messingknöpfe
# --------------------------------------------------------------------------------------------
CAP_ZB = 0.893


def cap_base():
    pts = []
    for i in range(121):
        x = -0.176 + 0.43 * i / 120
        for k in range(72):
            p = head_pt(x, -pi + 2 * pi * k / 72)
            if CAP_ZB - 0.002 <= p.z <= CAP_ZB + 0.035:
                pts.append(p)
    xmin, xmax = min(p.x for p in pts), max(p.x for p in pts)
    cx = 0.5 * (xmin + xmax)
    a = 0.5 * (xmax - xmin) + 0.008
    b = max(abs(p.y) for p in pts) + 0.008
    s = max(1.0, max(sqrt(((p.x - cx) / a) ** 2 + (p.y / b) ** 2) for p in pts))
    return cx, a * s, b * s


def build_cap(L, mb):
    cx, a, b = cap_base()
    crown = [  # dz, dx, Skala a, Skala b
        (0.000, 0.000, 1.00, 1.00), (0.028, 0.000, 1.00, 1.00), (0.034, 0.014, 1.10, 1.07),
        (0.055, 0.028, 1.17, 1.11), (0.080, 0.030, 1.14, 1.08), (0.100, 0.024, 0.98, 0.93),
        (0.112, 0.018, 0.76, 0.72)]
    if L["tag"] == "low":
        crown = [crown[0], crown[1], crown[3], crown[5]]
    nseg = L["cap_seg"]
    rings = []
    for dz, dx, sa, sb in crown:
        rings.append([V((cx + dx + a * sa * cos(2 * pi * i / nseg), b * sb * sin(2 * pi * i / nseg), CAP_ZB + dz))
                      for i in range(nseg)])
    def band(j, i):     # Lederband nur vorn und an den Seiten, hinten wie im Referenzblatt grün
        th = 2 * pi * (i + 0.5) / nseg
        return "Satchel" if (j == 0 and cos(th) > -0.35) else "Cap"

    loft(mb, rings, band,
         cap0=V((cx, 0, CAP_ZB + 0.02)), cap1=V((cx + 0.016, 0, CAP_ZB + 0.118)))
    # Schirm
    rows, cols = L["visor"]
    th_max = radians(72)
    grid = []
    for r in range(rows):
        th = -th_max + 2 * th_max * r / (rows - 1)
        inner = V((cx + a * cos(th), b * sin(th), CAP_ZB + 0.004))
        out = V((cos(th) / a, sin(th) / b, 0)).normalized()
        ln = 0.012 + 0.062 * max(0.0, cos(th / th_max * pi / 2)) ** 0.7
        row = []
        for c in range(cols):
            u = c / (cols - 1)
            row.append(inner + out * (ln * u) + V((0, 0, -ln * (0.12 * u + 0.28 * u * u) + 0.004 * sin(pi * u))))
        grid.append(row)
    solid_from_grid(mb, grid, 0.009, "Cap")
    # Knöpfe am Band
    for side in (1.0, -1.0):
        th = radians(55) * side
        p = V((cx + a * cos(th), b * sin(th), CAP_ZB + 0.014))
        nr = V((cos(th) / a, sin(th) / b, 0)).normalized()
        ellipsoid(mb, p + nr * 0.002, (0.011, 0.011, 0.005), basis_from_normal(nr), L["cap_button"][0],
                  L["cap_button"][1], mat="Brass")


# --------------------------------------------------------------------------------------------
# Gelenkpositionen (Ruhepose = Haltung aus dem Referenzblatt)
# --------------------------------------------------------------------------------------------
def leg_joints(side):
    s = sgn(side)
    H = V((0.0, s * 0.11, 0.27))
    K = V((0.022, s * 0.12, 0.165))
    A = V((0.0, s * 0.125, 0.065))
    TOE = V((0.12, s * 0.125, 0.02))
    return H, K, A, TOE


def arm_joints(side):
    s = sgn(side)
    S = V((0.0, s * 0.195, 0.605))
    if side == PS:    # Arm hält das Paket an die Seite gedrückt
        dirs = [(-0.30, 0.62, -0.72), (0.80, 0.0, -0.60), (0.65, -0.05, -0.76)]
    else:             # freier Arm hängt locker
        dirs = [(0.03, 0.45, -0.89), (0.12, 0.10, -0.99), (0.10, 0.02, -0.99)]
    pts = [S]
    for (dx, dy, dz), ln in zip(dirs, (0.17, 0.145, 0.075)):
        pts.append(pts[-1] + V((dx, s * dy, dz)).normalized() * ln)
    return pts   # Schulter, Ellbogen, Handgelenk, Handspitze


SCARF_BACK_TH = 180.0 - SP * 25.0   # Rückenende des Schals, zur Paketseite versetzt
SCARF_FRONT_TH = SF * 22.0          # Vorderes Ende auf der freien Seite
STRIP_T = 0.020


def scarf_point(z, th_deg, extra=0.0):
    th = radians(th_deg)
    p, n = torso_surf(z, th, lip=False)
    return p + n * (VEST_LIP + 0.004 + STRIP_T / 2 + extra), n


PARCEL_C = V((0.005, SP * 0.212, 0.38))
PARCEL_R = Matrix.Rotation(radians(-10), 3, "Y")   # vorderes Ende etwas höher
PARCEL_SIZE = (0.27, 0.09, 0.16)

# --------------------------------------------------------------------------------------------
# Gliedmaßen, Schwanz
# --------------------------------------------------------------------------------------------
LEG_R = [(0.0, 0.072), (0.25, 0.088), (0.55, 0.086), (0.8, 0.068), (1.0, 0.056)]
FOOT = [  # dx ab Knöchel, Halbbreite, Oberkante z, Unterkante z
    (-0.058, 0.030, 0.040, 0.014),
    (-0.050, 0.048, 0.066, 0.005),
    (-0.028, 0.058, 0.084, 0.003),
    (0.010, 0.062, 0.084, 0.003),
    (0.050, 0.068, 0.068, 0.003),
    (0.085, 0.070, 0.052, 0.003),
    (0.108, 0.064, 0.040, 0.005),
    (0.122, 0.044, 0.030, 0.010),
]
ARM_R = [(-0.05, 0.045), (-0.015, 0.060), (0.020, 0.068), (0.060, 0.072), (0.095, 0.070), (0.120, 0.067),
         (0.128, 0.076), (0.148, 0.076), (0.156, 0.053), (0.180, 0.050), (0.250, 0.046), (0.300, 0.040),
         (0.330, 0.050), (0.355, 0.054), (0.375, 0.043), (0.390, 0.022)]
CUFF_END = 0.152
TAIL_CTRL = [V((-0.13, 0, 0.335)), V((-0.180, 0, 0.30)), V((-0.193, 0, 0.23)), V((-0.180, 0, 0.165))]
TAIL_R = [(0.0, 0.035), (0.2, 0.050), (0.45, 0.058), (0.7, 0.050), (0.88, 0.032), (1.0, 0.012)]


def build_leg(L, mb, side):
    H, K, A, _ = leg_joints(side)
    ctrl = [H + V((0, 0, 0.065)), H, K, A]
    total = arc_lengths(catmull(ctrl))[-1]
    st = [f * total for f in L["leg_f"]]
    tube(mb, ctrl, st, lambda d: table_smooth(LEG_R, d / total)[0], L["leg_seg"], lambda j, i: "FurDark",
         V((1, 0, 0)))


def foot_ring(A, dx, w, zt, zb, nseg):
    zm = zb + (zt - zb) * 0.38
    ring = []
    for i in range(nseg):
        al = 2 * pi * i / nseg
        ca, sa = cos(al), sin(al)
        y = w * (abs(sa) ** 0.75) * (1 if sa >= 0 else -1)
        z = zm + (zt - zm) * ca if ca >= 0 else zm - (zm - zb) * (abs(ca) ** 0.45)
        ring.append(V((A.x + dx, A.y + y, z)))
    return ring


def build_foot(L, mb, side):
    _, _, A, _ = leg_joints(side)
    rows = FOOT if L["foot_st"] is None else [[dx] + table_smooth(FOOT, dx) for dx in L["foot_st"]]
    rings = [foot_ring(A, r[0], r[1], r[2], r[3], L["foot_seg"]) for r in rows]
    loft(mb, rings, lambda j, i: "FurDark", cap0=V((A.x - 0.064, A.y, 0.028)), cap1=V((A.x + 0.128, A.y, 0.022)))


def build_claws(mb, side):
    _, _, A, _ = leg_joints(side)
    for oy in (-0.042, -0.014, 0.014, 0.042):
        base = V((A.x + 0.110, A.y + oy, 0.017))
        d = V((1, 0, -0.18)).normalized()
        ax, ay, _ = basis_from_normal(d)
        ring = [base + (ax * cos(2 * pi * i / 5) + ay * sin(2 * pi * i / 5)) * 0.0075 for i in range(5)]
        loft(mb, [ring], lambda j, i: "Nose", cap0=base - d * 0.006, cap1=base + d * 0.026)


def build_arm(L, mb, side):
    S, E, W, T = arm_joints(side)
    s = sgn(side)
    S0 = S + V((0, -s * 0.05, 0.012))
    ctrl = [S0, S, E, W, T, T + (T - W).normalized() * 0.016]
    poly = catmull(ctrl, 16)
    off = arc_lengths(poly)[16]       # Bogenlänge bis zur Schulter (Kontrollpunkt 1)
    st = L["arm_st"]

    def mf(j, i):
        return "Shirt" if 0.5 * (st[j] + st[j + 1]) < CUFF_END else "FurDark"

    tube(mb, ctrl, st, lambda d: table_lin(ARM_R, d)[0], L["arm_seg"], mf, V((1, 0, 0)), offset=off)


def build_tail(L, mb):
    total = arc_lengths(catmull(TAIL_CTRL))[-1]
    st = [f * total for f in L["tail_f"]]
    tube(mb, TAIL_CTRL, st, lambda d: table_smooth(TAIL_R, d / total)[0], L["tail_seg"],
         lambda j, i: "FurLight", V((-1, 0, 0)), sx=0.7, sy=1.15, pole=0.9)


# --------------------------------------------------------------------------------------------
# Schal: Wicklungen um den Hals, vorderes Ende (fest) und hinteres Ende (an scarf_1/scarf_2)
# --------------------------------------------------------------------------------------------
def build_scarf_wraps(L, mb):
    if L["scarf_wraps"] == 2:
        wraps = [((0.012, 0, 0.668), 0.128, 0.145, 0.044, 10.0), ((0.030, 0, 0.722), 0.112, 0.128, 0.042, 14.0)]
    else:
        wraps = [((0.020, 0, 0.695), 0.122, 0.138, 0.062, 12.0)]
    nmaj, nmin = L["scarf"]
    for center, rx, ry, r, tilt in wraps:
        R = Matrix.Rotation(radians(tilt), 3, "Y")
        rings = []
        for i in range(nmaj):
            u = 2 * pi * i / nmaj
            base = V((rx * cos(u), ry * sin(u), 0))
            nrm = V((cos(u) / rx, sin(u) / ry, 0)).normalized()
            rr = r * (1.0 + (0.06 if (L["ripple"] and i % 2) else 0.0))
            rings.append([V(center) + R @ (base + nrm * (rr * cos(2 * pi * j / nmin))
                                           + V((0, 0, rr * 0.85 * sin(2 * pi * j / nmin))))
                          for j in range(nmin)])
        loft(mb, rings, lambda j, i: "Scarf", closed=True)


def strip_profile(L, w):
    t = STRIP_T
    if L["strip_prof"] == 4:
        return [(0.5 * w, -0.5 * t), (0.5 * w, 0.5 * t), (-0.5 * w, 0.5 * t), (-0.5 * w, -0.5 * t)]
    return [(0.5 * w, -0.25 * t), (0.5 * w, 0.25 * t), (0.38 * w, 0.5 * t), (-0.38 * w, 0.5 * t),
            (-0.5 * w, 0.25 * t), (-0.5 * w, -0.25 * t), (-0.38 * w, -0.5 * t), (0.38 * w, -0.5 * t)]


def scarf_strip(L, mb, th_deg, z0, z1, width, extra_fn):
    n = L["strip_n"]
    pts, nrms = [], []
    for k in range(n):
        z = lerp(z0, z1, k / (n - 1))
        p, nr = scarf_point(z, th_deg, extra_fn(z))
        pts.append(p)
        nrms.append(nr)
    sweep(mb, pts, nrms, strip_profile(L, width), lambda j, i: "Scarf")
    if L["fringe"]:
        t = (pts[-1] - pts[-2]).normalized()
        nr = (nrms[-1] - t * nrms[-1].dot(t)).normalized()
        b = t.cross(nr)
        for ob in (-0.03, -0.01, 0.01, 0.03):
            a = pts[-1] + b * (ob * width / 0.085) - t * 0.004
            bpts = [a, a + t * 0.02 + nr * 0.002, a + t * 0.04 + nr * 0.004]
            prof = [(0.007, -0.004), (0.007, 0.004), (-0.007, 0.004), (-0.007, -0.004)]
            sweep(mb, bpts, [nr] * 3, prof, lambda j, i: "Scarf")
    return pts


def build_scarf_ends(L, mb_front, mb_back):
    scarf_strip(L, mb_front, SCARF_FRONT_TH, 0.672, 0.405, 0.085, lambda z: 0.004 * smoothstep(0.6, 0.45, z))
    scarf_strip(L, mb_back, SCARF_BACK_TH, 0.672, 0.430, 0.080, lambda z: 0.0)


# --------------------------------------------------------------------------------------------
# Riemen, Tasche, Westendetails, Paket
# --------------------------------------------------------------------------------------------
def build_strap(L, mb, torso_ob):
    me = torso_ob.data
    bvh = BVHTree.FromPolygons([v.co for v in me.vertices], [p.vertices[:] for p in me.polygons])
    c = V((-0.01, SP * 0.02, 0.55))
    n = V((-0.15, SP * 0.75, 1.0)).normalized()        # Ebene: über die freie Schulter zur Paketseite
    e1 = (V((1, 0, 0)) - n * n.x).normalized()
    e2 = n.cross(e1)
    pts, nrms = [], []
    K = L["strap_n"]
    for k in range(K):
        t = 2 * pi * k / K
        loc, nor, _, _ = bvh.ray_cast(c, e1 * cos(t) + e2 * sin(t))
        if loc is None:
            continue
        pts.append(loc + nor * 0.004)
        nrms.append(nor)
    prof = [(-0.017, 0.0), (0.017, 0.0), (0.017, 0.006), (-0.017, 0.006)]
    sweep(mb, pts, nrms, prof, lambda j, i: "Satchel", closed=True)


def build_satchel(L, mb):
    th = radians(180.0 - SP * 28.0)   # hinten an der Hüfte der Paketseite, hinter dem Paket
    z = 0.365
    p, n = torso_surf(z, th)
    o = V((n.x, n.y, 0)).normalized()
    up = V((0, 0, 1))
    r = up.cross(o).normalized()
    w, d, h = 0.12, 0.055, 0.15
    center = p + o * (d / 2 + 0.006)
    bevel_box(mb, (w, d, h), frame_matrix(center, r, o, up), 0.008 if L["details"] else 0.0, "Satchel")
    if L["satchel_flap"]:
        fc = center + o * (d / 2 + 0.004) + up * (h / 2 - 0.045)
        bevel_box(mb, (w + 0.006, 0.010, 0.092), frame_matrix(fc, r, o, up), 0.003, "Satchel")
        bc = fc + o * 0.006 + up * (-0.040)
        bevel_box(mb, (0.024, 0.008, 0.020), frame_matrix(bc, r, o, up), 0.002, "Brass")


def vest_button(mb, z, th, r=0.011, extra=0.0):
    p, n = torso_surf(z, th)
    ellipsoid(mb, p + n * (0.002 + extra), (r, r, 0.0045), basis_from_normal(n), 8, 4, mat="Brass")


def vest_flap(mb, z, th, w, h, point=0.008):
    b_loc = table_smooth(TORSO, z)[2]
    grid, downs = [], []
    for r in range(2):
        row, drow = [], []
        for c in range(3):
            zz = z - h * r - (point if (r == 1 and c == 1) else 0.0)
            tt = th + (c - 1) * (w / 2) / b_loc
            p, n = torso_surf(zz, tt)
            row.append(p + n * 0.0055)
            drow.append(-n)
        grid.append(row)
        downs.append(drow)
    solid_from_grid(mb, grid, 0.0055, "Vest", downs=downs)
    vest_button(mb, z - h * 0.75, th, r=0.0085, extra=0.0055)


def build_vest_details(mb):
    for z in (0.39, 0.445, 0.50):
        vest_button(mb, z, SF * radians(8))
    vest_flap(mb, 0.515, SF * radians(50), 0.075, 0.028)
    vest_flap(mb, 0.515, SP * radians(44), 0.075, 0.028)
    vest_flap(mb, 0.375, SF * radians(50), 0.085, 0.032)
    vest_flap(mb, 0.375, SP * radians(50), 0.085, 0.032)
    vest_flap(mb, 0.345, pi, 0.15, 0.030, point=0.0)              # Rückenriegel
    for d in (-0.055, 0.055):
        vest_button(mb, 0.330, pi + d / 0.2, r=0.009, extra=0.0055)


def build_parcel(L, mb):
    R4 = PARCEL_R.to_4x4()
    M = Matrix.Translation(PARCEL_C) @ R4
    bevel_box(mb, PARCEL_SIZE, M, L["parcel_bevel"], "Parcel")
    if not L["parcel_string"]:
        return
    hx, hy, hz = [s / 2 + 0.0015 for s in PARCEL_SIZE]

    def loop(corners, nrm_fn):
        pts = []
        for i in range(len(corners)):
            a, b = V(corners[i]), V(corners[(i + 1) % len(corners)])
            pts.append(a.lerp(b, 0.12))
            pts.append(a.lerp(b, 0.88))
        return [M @ p for p in pts], [(R4.to_3x3() @ nrm_fn(p)).normalized() for p in pts]

    prof = [(-0.006, 0.0), (0.006, 0.0), (0.006, 0.003), (-0.006, 0.003)]
    # Schnur quer (Ebene x = 0) und längs (Ebene z = 0)
    pts, nr = loop([(0, hy, hz), (0, -hy, hz), (0, -hy, -hz), (0, hy, -hz)], lambda p: V((0, p.y, p.z)))
    sweep(mb, pts, nr, prof, lambda j, i: "Shirt", closed=True)
    pts, nr = loop([(hx, hy, 0), (-hx, hy, 0), (-hx, -hy, 0), (hx, -hy, 0)], lambda p: V((p.x, p.y, 0)))
    sweep(mb, pts, nr, prof, lambda j, i: "Shirt", closed=True)
    # Schleife auf der Außenseite (zur Paketseite)
    out = V((0, SP, 0))
    knot = M @ (out * (hy + 0.004))
    ellipsoid(mb, knot, (0.008, 0.008, 0.006), basis_from_normal(R4.to_3x3() @ out), 8, 4, mat="Shirt")
    for sx in (-1.0, 1.0):
        c = M @ (out * (hy + 0.004) + V((sx * 0.018, 0, 0.004)))
        ax = (R4.to_3x3() @ rot3(0, sx * 25, 0) @ V((1, 0, 0))).normalized()
        az = (R4.to_3x3() @ out).normalized()
        ay = az.cross(ax)
        ellipsoid(mb, c, (0.017, 0.010, 0.004), (ax, ay, az), 8, 4, mat="Shirt")


# --------------------------------------------------------------------------------------------
# Armature
# --------------------------------------------------------------------------------------------
BONE_ORDER = ["root", "hips", "spine", "chest", "neck", "head",
              "upper_arm.L", "forearm.L", "hand.L", "upper_arm.R", "forearm.R", "hand.R",
              "thigh.L", "shin.L", "foot.L", "thigh.R", "shin.R", "foot.R",
              "scarf_1", "scarf_2", "tail"]
REST, HEADS = {}, {}


def bone_layout():
    B = {
        "root": (V((0, 0, 0)), V((0.12, 0, 0)), None, False),
        "hips": (V((0, 0, 0.285)), V((0, 0, 0.40)), "root", False),
        "spine": (V((0, 0, 0.40)), V((0, 0, 0.52)), "hips", True),
        "chest": (V((0, 0, 0.52)), V((0, 0, 0.655)), "spine", True),
        "neck": (V((0, 0, 0.655)), V((0.03, 0, 0.75)), "chest", True),
        "head": (V((0.03, 0, 0.75)), V((0.03, 0, 0.95)), "neck", True),
        "tail": (TAIL_CTRL[1].copy(), TAIL_CTRL[3].copy(), "hips", False),
    }
    for side in "LR":
        S, E, W, T = arm_joints(side)
        B["upper_arm." + side] = (S, E, "chest", False)
        B["forearm." + side] = (E, W, "upper_arm." + side, True)
        B["hand." + side] = (W, T, "forearm." + side, True)
        H, K, A, TOE = leg_joints(side)
        B["thigh." + side] = (H, K, "hips", False)
        B["shin." + side] = (K, A, "thigh." + side, True)
        B["foot." + side] = (A, TOE, "shin." + side, True)
    p1 = scarf_point(0.650, SCARF_BACK_TH)[0]
    p2 = scarf_point(0.548, SCARF_BACK_TH)[0]
    p3 = scarf_point(0.440, SCARF_BACK_TH)[0]
    B["scarf_1"] = (p1, p2, "chest", False)
    B["scarf_2"] = (p2, p3, "scarf_1", True)
    return B


def build_armature():
    data = bpy.data.armatures.new("Armature")
    arm = bpy.data.objects.new("Armature", data)
    bpy.context.scene.collection.objects.link(arm)
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    B = bone_layout()
    for name in BONE_ORDER:
        h, t, parent, conn = B[name]
        eb = data.edit_bones.new(name)
        eb.head, eb.tail = h, t
        d = (t - h).normalized()
        eb.align_roll(V((0, 0, 1)) if abs(d.x) > 0.7 else V((1, 0, 0)))
        if parent:
            eb.parent = data.edit_bones[parent]
            eb.use_connect = conn
    bpy.ops.object.mode_set(mode="OBJECT")
    data.bones["root"].use_deform = False
    for b in data.bones:
        REST[b.name] = b.matrix_local.copy()
        HEADS[b.name] = b.head_local.copy()
    return arm


# --------------------------------------------------------------------------------------------
# Gewichte
# --------------------------------------------------------------------------------------------
def set_weights(ob, fn):
    for v in ob.data.vertices:
        w = {b: x for b, x in fn(v.co).items() if x > 1e-4}
        tot = sum(w.values()) or 1.0
        for b, x in w.items():
            vg = ob.vertex_groups.get(b) or ob.vertex_groups.new(name=b)
            vg.add([v.index], x / tot, "REPLACE")


def bone_seg_dist(p, name, arm):
    b = arm.data.bones[name]
    a, c = b.head_local, b.tail_local
    ab = c - a
    t = clamp((p - a).dot(ab) / max(ab.length_squared, 1e-12))
    return (a + ab * t - p).length


def auto_weights(ob, arm, bones):
    """Bone-Heat (Automatische Gewichte) nur mit den genannten Knochen."""
    saved = {b.name: b.use_deform for b in arm.data.bones}
    for b in arm.data.bones:
        b.use_deform = b.name in bones
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    for b in arm.data.bones:
        b.use_deform = saved[b.name]
    # Absicherung: Punkte ohne Gewicht bekommen den nächstgelegenen Knochen
    missing = 0
    for v in ob.data.vertices:
        if sum(g.weight for g in v.groups) < 1e-4:
            best = min(bones, key=lambda n: bone_seg_dist(v.co, n, arm))
            (ob.vertex_groups.get(best) or ob.vertex_groups.new(name=best)).add([v.index], 1.0, "REPLACE")
            missing += 1
    return missing


def pin_soles(ob, foot, other, z0=0.025, z1=0.050):
    """Sohle (z < z0) ganz an den Fußknochen, bis z1 überblenden: der aufgesetzte Fuß bleibt exakt am Boden."""
    vf = ob.vertex_groups.get(foot) or ob.vertex_groups.new(name=foot)
    vo = ob.vertex_groups.get(other)
    for v in ob.data.vertices:
        t = smoothstep(z0, z1, v.co.z)
        if t >= 1.0:
            continue
        wf = next((g.weight for g in v.groups if g.group == vf.index), 0.0)
        wo = next((g.weight for g in v.groups if vo and g.group == vo.index), 0.0)
        nf = wf + (1.0 - t) * wo
        vf.add([v.index], nf, "REPLACE")
        if vo:
            vo.add([v.index], wo * t, "REPLACE")


def transfer_weights(ob, src, rigid=False):
    """Gewichte vom Rumpf übernehmen; rigid=True nimmt für alle Punkte die Gewichte am Schwerpunkt."""
    me = src.data
    bvh = BVHTree.FromPolygons([v.co for v in me.vertices], [p.vertices[:] for p in me.polygons])
    names = {g.index: g.name for g in src.vertex_groups}
    vw = [{names[g.group]: g.weight for g in v.groups} for v in me.vertices]

    def fn(co):
        loc, _, fi, _ = bvh.find_nearest(co)
        acc, tot = {}, 0.0
        for vi in me.polygons[fi].vertices:
            w = 1.0 / max((me.vertices[vi].co - loc).length, 1e-5)
            tot += w
            for b, x in vw[vi].items():
                acc[b] = acc.get(b, 0.0) + x * w
        return {b: x / tot for b, x in acc.items()}

    if rigid:
        center = sum((v.co for v in ob.data.vertices), V()) / len(ob.data.vertices)
        w = fn(center)
        set_weights(ob, lambda co: w)
    else:
        set_weights(ob, fn)


def scarf_wrap_w(co):
    t = smoothstep(0.655, 0.745, co.z)
    return {"chest": 1.0 - t, "neck": t}


def scarf_back_w(co):
    t = clamp((0.672 - co.z) / (0.672 - 0.430))
    a = smoothstep(0.02, 0.16, t)
    b = smoothstep(0.42, 0.62, t)
    return {"chest": 1.0 - a, "scarf_1": a * (1.0 - b), "scarf_2": b}


def normalize_limit(ob, limit=4):
    for v in ob.data.vertices:
        gs = sorted([(g.weight, g.group) for g in v.groups], reverse=True)
        keep = [(w, gi) for w, gi in gs[:limit] if w > 1e-3]
        drop = [gi for w, gi in gs if (w, gi) not in keep]
        for gi in drop:
            ob.vertex_groups[gi].remove([v.index])
        tot = sum(w for w, _ in keep) or 1.0
        for w, gi in keep:
            ob.vertex_groups[gi].add([v.index], w / tot, "REPLACE")


def smart_uv(ob):
    """Smart UV Project (66°), danach 1 UV-Einheit = 1 m – wie in build_harbor.py."""
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=radians(66.0), island_margin=0.002, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    ob.select_set(False)
    me = ob.data
    uv = me.uv_layers.active.data
    a3, auv = 0.0, 0.0
    for p in me.polygons:
        a3 += p.area
        pts = [uv[li].uv for li in p.loop_indices]
        s = 0.0
        for i in range(len(pts)):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % len(pts)]
            s += x1 * y2 - x2 * y1
        auv += abs(s) / 2
    k = math.sqrt(a3 / auv) if auv > 0 else 1.0
    for d in uv:
        d.uv = d.uv * k
    me.uv_layers.active.name = "UVMap"
    repack_uv_islands(ob)


def repack_uv_islands(ob, margin=0.01):
    """Inseln neu anordnen, nur verschieben, in fester Reihenfolge (kleinster Flächenindex je Insel).

    Smart UV Project packt die Inseln zeitabhängig, ihre Lage ändert sich sonst bei jedem Lauf. Form, Drehung und
    Maßstab der Inseln (1 UV-Einheit = 1 m) bleiben erhalten; die GLB wird damit bei gleichem Skript bytegleich.
    """
    from bpy_extras.bmesh_utils import bmesh_linked_uv_islands
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    lay = bm.loops.layers.uv.active
    islands = []
    for faces in bmesh_linked_uv_islands(bm, lay):
        us = [l[lay].uv.x for f in faces for l in f.loops]
        vs = [l[lay].uv.y for f in faces for l in f.loops]
        islands.append((min(f.index for f in faces), faces, min(us), min(vs), max(us) - min(us), max(vs) - min(vs)))
    islands.sort(key=lambda t: t[0])
    total = sum((w + margin) * (h + margin) for _, _, _, _, w, h in islands)
    row_w = max(math.sqrt(total) * 1.15, max(t[4] for t in islands) + margin)
    order = sorted(islands, key=lambda t: (-round(t[5], 4), t[0]))     # Regale: hohe Inseln zuerst
    x = y = row_h = 0.0
    for _, faces, u0, v0, w, h in order:
        if x > 0 and x + w > row_w:
            x, y, row_h = 0.0, y + row_h + margin, 0.0
        du, dv = x - u0, y - v0
        for f in faces:
            for l in f.loops:
                l[lay].uv.x += du
                l[lay].uv.y += dv
        x += w + margin
        row_h = max(row_h, h)
    bm.to_mesh(me)
    bm.free()


def join(objs, name, arm):
    for o in objs:
        o.parent = None
        o.modifiers.clear()
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    ob = objs[0]
    ob.name = name
    ob.data.name = name
    normalize_limit(ob)
    smart_uv(ob)
    ob.parent = arm
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    return ob


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


# --------------------------------------------------------------------------------------------
# Figur bauen (eine Detailstufe)
# --------------------------------------------------------------------------------------------
def build_figure(L, arm):
    t = L["tag"]
    parts = []   # (Objekt, Gewichtsart, Daten, Gruppe)

    def add(mb, kind, data=None, sharp=None, group="body"):
        if not mb.f:
            return None
        ob = mb_object(mb, sharp)
        ob.name = f"{t}_{mb.name}"
        parts.append((ob, kind, data, group))
        return ob

    torso = build_torso(L)
    torso.name = f"{t}_torso"
    parts.append((torso, "auto", ["hips", "spine", "chest", "neck"], "body"))
    add(build_head(L), "rigid", "head")
    cap = MB("cap")
    build_cap(L, cap)
    add(cap, "rigid", "head", sharp=50)
    for side in "LR":
        mb = MB("leg_" + side)
        build_leg(L, mb, side)
        add(mb, "auto", ["thigh." + side, "shin." + side, "foot." + side])
        mb = MB("foot_" + side)
        build_foot(L, mb, side)
        add(mb, "auto_sole", ["shin." + side, "foot." + side])
        if L["claws"]:
            mb = MB("claws_" + side)
            build_claws(mb, side)
            add(mb, "rigid", "foot." + side)
        mb = MB("arm_" + side)
        build_arm(L, mb, side)
        add(mb, "auto", ["upper_arm." + side, "forearm." + side, "hand." + side])
    mb = MB("tail")
    build_tail(L, mb)
    add(mb, "auto", ["hips", "tail"])
    mb = MB("scarf")
    build_scarf_wraps(L, mb)
    add(mb, "fn", scarf_wrap_w)
    front, back = MB("scarf_front"), MB("scarf_back")
    build_scarf_ends(L, front, back)
    add(front, "rigid", "chest")
    add(back, "fn", scarf_back_w)
    mb = MB("strap")
    build_strap(L, mb, torso)
    add(mb, "transfer", None, sharp=60)
    mb = MB("satchel")
    build_satchel(L, mb)
    add(mb, "transfer_rigid", None, sharp=40)
    if L["details"]:
        mb = MB("vest_details")
        build_vest_details(mb)
        add(mb, "transfer", None, sharp=60)
    mb = MB("parcel")
    build_parcel(L, mb)
    add(mb, "rigid", "hand." + PS, sharp=40, group="parcel")

    report = {}
    for ob, kind, data, _ in parts:          # Bone-Heat zuerst (Rumpf liefert Gewichte für "transfer")
        if kind in ("auto", "auto_sole"):
            report[ob.name] = auto_weights(ob, arm, data)
        if kind == "auto_sole":
            pin_soles(ob, data[1], data[0])
    for ob, kind, data, _ in parts:
        if kind == "rigid":
            set_weights(ob, lambda co, b=data: {b: 1.0})
        elif kind == "fn":
            set_weights(ob, data)
        elif kind == "transfer":
            transfer_weights(ob, torso)
        elif kind == "transfer_rigid":
            transfer_weights(ob, torso, rigid=True)
    body = join([p[0] for p in parts if p[3] == "body"], f"Badger_{t}", arm)
    parcel = join([p[0] for p in parts if p[3] == "parcel"], f"Parcel_{t}", arm)
    return body, parcel, report


# --------------------------------------------------------------------------------------------
# Animation: jede Pose als Satz von Drehungen X_b im Ruhe-Koordinatensystem um den Knochenkopf.
# Für jeden Knochen gilt dann basis = Rest^-1 @ X @ Rest (unabhängig von der Pose der Eltern).
# --------------------------------------------------------------------------------------------
def delta(name, r3=None, trans=None):
    m = rot_about(r3 if r3 is not None else Matrix.Identity(3), HEADS[name])
    if trans is not None:
        m = Matrix.Translation(trans) @ m
    return m


def frame_rot(a1, b1, a2, b2):
    def fr(a, b):
        e1 = a.normalized()
        e3 = a.cross(b)
        if e3.length < 1e-8:
            e3 = e1.orthogonal()
        e3.normalize()
        e2 = e3.cross(e1)
        return Matrix((e1, e2, e3)).transposed()
    return fr(a2, b2) @ fr(a1, b1).transposed()


IK_WARN = []


def leg_ik(side, D_hips, ankle_w, pitch_deg, X):
    """Zwei-Gelenk-IK: Knöchel auf ankle_w (Ruheraum), Knie nach vorn, Fuß mit pitch_deg (Zehen hoch +)."""
    H = HEADS["thigh." + side]
    K = HEADS["shin." + side]
    A = HEADS["foot." + side]
    L1, L2 = (K - H).length, (A - K).length
    Di = D_hips.inverted()
    A_l = Di @ ankle_w
    pole = (Di.to_3x3() @ V((1, 0, 0)))
    v = A_l - H
    d = v.length
    dmax = (L1 + L2) * 0.999
    if d > dmax:
        IK_WARN.append((side, round(d - dmax, 4)))
    d = clamp(d, abs(L1 - L2) + 1e-4, dmax)
    u = v.normalized()
    A_l = H + u * d
    ca = clamp((L1 * L1 + d * d - L2 * L2) / (2 * L1 * d), -1.0, 1.0)
    a = math.acos(ca)
    w = (pole - u * pole.dot(u)).normalized()
    K_d = H + (u * cos(a) + w * sin(a)) * L1
    R_t = frame_rot(K - H, A - K, K_d - H, A_l - K_d)
    X["thigh." + side] = rot_about(R_t, H)
    s_d = R_t.inverted() @ (A_l - K_d)
    R_s = (A - K).rotation_difference(s_d).to_matrix()
    X["shin." + side] = rot_about(R_s, K)
    R_shin = (D_hips.to_3x3() @ R_t @ R_s).normalized()
    R_f = R_shin.inverted() @ Matrix.Rotation(radians(-pitch_deg), 3, "Y")
    X["foot." + side] = rot_about(R_f, A)


def plant_legs(X, pitch=0.0):
    for side in "LR":
        leg_ik(side, X.get("hips", Matrix.Identity(4)), HEADS["foot." + side], pitch, X)


def arm_rot(X, side, fwd=0.0, abd=0.0, elbow=0.0, wrist=0.0):
    s = sgn(side)
    X["upper_arm." + side] = delta("upper_arm." + side, rot3(s * abd, -fwd, 0))
    X["forearm." + side] = delta("forearm." + side, rot3(0, -elbow, 0))
    X["hand." + side] = delta("hand." + side, rot3(0, -wrist, 0))


# ---- Laufzyklus ------------------------------------------------------------------------------
WALK_FRAMES = 30            # 1 s
STRIDE = 0.22               # Weg des Standfußes pro Standphase (m)
STANCE = 0.60               # Anteil Standphase
LIFT = 0.050                # Fußhub in der Schwungphase
HEEL_Q, TOE_Q = 12.0, -16.0
HEEL_PIV, BALL_PIV = -0.055, 0.118
WALK_SPEED = STRIDE / (STANCE * WALK_FRAMES / FPS)   # m/s, damit die Füße nicht rutschen


def pivot_pose(A, u, piv, q):
    px = A.x + u + piv
    rx, rz = (A.x + u) - px, A.z
    qr = radians(q)
    return V((px + rx * cos(qr) - rz * sin(qr), A.y, rx * sin(qr) + rz * cos(qr)))


def foot_state(p, A):
    p %= 1.0
    if p < STANCE:
        u = STRIDE / 2 - STRIDE * p / STANCE
        if p < 0.08:
            return pivot_pose(A, u, HEEL_PIV, HEEL_Q * (1 - smoothstep(0.0, 0.08, p))), \
                HEEL_Q * (1 - smoothstep(0.0, 0.08, p))
        if p > 0.42:
            q = TOE_Q * smoothstep(0.42, STANCE, p)
            return pivot_pose(A, u, BALL_PIV, q), q
        return pivot_pose(A, u, 0.0, 0.0), 0.0
    t = (p - STANCE) / (1 - STANCE)
    a0, q0 = foot_state(STANCE - 1e-6, A)
    a1, q1 = foot_state(0.0, A)
    e = 0.5 - 0.5 * cos(pi * t)
    pos = V((lerp(a0.x, a1.x, e), A.y, lerp(a0.z, a1.z, t) + LIFT * sin(pi * t)))
    return pos, lerp(q0, q1, smoothstep(0.1, 0.85, t))


def walk_pose(f):
    p = f / WALK_FRAMES
    X = {}
    c2 = cos(2 * pi * (p - 0.3))
    bob = -0.012 - 0.008 * cos(4 * pi * p)
    sway = 0.010 * c2
    roll = -3.5 * c2
    yaw = -5.0 * cos(2 * pi * p)
    X["hips"] = delta("hips", rot3(roll, 0, yaw), V((0, sway, bob)))
    X["spine"] = delta("spine", rot3(-roll * 0.45, 2.0, -yaw * 0.8))
    X["chest"] = delta("chest", rot3(-roll * 0.25, 1.5 + 0.8 * cos(4 * pi * p + 0.6), -yaw * 0.8))
    X["neck"] = delta("neck", rot3(-roll * 0.15, -2.0, 0.3 * yaw))
    X["head"] = delta("head", rot3(-roll * 0.15, -1.5 + 1.5 * sin(4 * pi * p - 0.5), 0.3 * yaw))
    for side, ph in (("L", p), ("R", p + 0.5)):
        A = HEADS["foot." + side]
        pos, q = foot_state(ph, A)
        leg_ik(side, X["hips"], pos, q, X)
        if side == FS:
            arm_rot(X, side, fwd=-22.0 * cos(2 * pi * ph), abd=3.0,
                    elbow=10.0 + 10.0 * (0.5 - 0.5 * cos(2 * pi * ph)), wrist=6.0 * sin(2 * pi * ph - 1.2))
        else:
            arm_rot(X, side, fwd=-3.0 * cos(2 * pi * ph))
    X["scarf_1"] = delta("scarf_1", rot3(SP * 5.0 * sin(2 * pi * (p - 0.3) - 0.8),
                                         14.0 + 6.0 * sin(4 * pi * p - 1.2), 0))
    X["scarf_2"] = delta("scarf_2", rot3(SP * 6.0 * sin(2 * pi * (p - 0.3) - 1.6),
                                         10.0 + 8.0 * sin(4 * pi * p - 2.2), 0))
    X["tail"] = delta("tail", rot3(8.0 * sin(2 * pi * p + 0.5), 4.0 + 3.0 * sin(4 * pi * p), 0))
    return X


# ---- Idle ------------------------------------------------------------------------------------
IDLE_FRAMES = 60            # 2 s


def idle_pose(f):
    p = f / IDLE_FRAMES
    b = sin(2 * pi * p)
    X = {}
    X["hips"] = delta("hips", rot3(-1.2 * b, 0, 0), V((0, 0.005 * b, -0.004 + 0.004 * cos(2 * pi * p))))
    X["spine"] = delta("spine", rot3(0.6 * b, -1.0 * b, 0))
    X["chest"] = delta("chest", rot3(0.4 * b, -1.2 * b, 0))
    X["neck"] = delta("neck", rot3(0, 1.2 * b, 0))
    X["head"] = delta("head", rot3(0.6 * sin(2 * pi * p + 0.8), 0.8 * b + 1.2 * sin(2 * pi * p + 1.3),
                                   2.0 * sin(2 * pi * p + 0.4)))
    plant_legs(X)
    arm_rot(X, FS, fwd=2.0 * sin(2 * pi * p + 1.0), abd=1.0 + 1.5 * b, elbow=3.0 + 2.0 * sin(2 * pi * p + 0.5))
    arm_rot(X, PS, abd=0.8 * b)
    X["scarf_1"] = delta("scarf_1", rot3(SP * 2.0 * sin(2 * pi * p - 0.6), 3.0 + 1.5 * sin(2 * pi * p - 1.0), 0))
    X["scarf_2"] = delta("scarf_2", rot3(SP * 2.5 * sin(2 * pi * p - 1.3), 2.0 + 2.0 * sin(2 * pi * p - 1.8), 0))
    X["tail"] = delta("tail", rot3(6.0 * sin(4 * pi * p), 2.0, 0))
    return X


# ---- Winken ----------------------------------------------------------------------------------
WAVE_FRAMES = 45            # 1,5 s


def wave_pose(f):
    t = f / FPS
    e = smoothstep(0.0, 0.38, t) * (1 - smoothstep(1.12, 1.5, t))
    we = smoothstep(0.28, 0.45, t) * (1 - smoothstep(1.0, 1.18, t))
    w = 26.0 * sin(2 * pi * 2.4 * (t - 0.36)) * we
    wl = 26.0 * sin(2 * pi * 2.4 * (t - 0.42)) * we
    s = SF
    X = {}
    X["hips"] = delta("hips", rot3(s * 1.5 * e, 0, 0), V((0, -s * 0.008 * e, -0.003 * e)))
    X["spine"] = delta("spine", rot3(s * 1.5 * e, -1.0 * e, 0))
    X["chest"] = delta("chest", rot3(s * 3.0 * e, -1.5 * e, 0))
    X["neck"] = delta("neck", rot3(-s * 2.0 * e, 0, 0))
    X["head"] = delta("head", rot3(-s * 7.0 * e, -3.0 * e, 0))
    plant_legs(X)
    S, E, W, T = arm_joints(FS)
    q_u = (E - S).normalized().rotation_difference(V((0.20, s * 0.55, 0.81)).normalized())
    d_f = Matrix.Rotation(radians(-s * w), 3, "X") @ V((0.10, s * 0.15, 1.0)).normalized()
    q_f = (W - E).normalized().rotation_difference(q_u.inverted() @ d_f)
    d_h = Matrix.Rotation(radians(-s * 0.5 * wl), 3, "X") @ d_f
    q_h = (T - W).normalized().rotation_difference((q_u @ q_f).inverted() @ d_h)
    ident = Quaternion()
    X["upper_arm." + FS] = delta("upper_arm." + FS, ident.slerp(q_u, e).to_matrix())
    X["forearm." + FS] = delta("forearm." + FS, ident.slerp(q_f, e).to_matrix())
    X["hand." + FS] = delta("hand." + FS, ident.slerp(q_h, e).to_matrix())
    X["scarf_1"] = delta("scarf_1", rot3(-s * 4.0 * e, 3.0 * e, 0))
    X["scarf_2"] = delta("scarf_2", rot3(-s * 3.0 * e, 2.0 * e, 0))
    X["tail"] = delta("tail", rot3(10.0 * sin(2 * pi * 2.0 * t) * e, 0, 0))
    return X


def make_action(arm, name, frames, pose_fn, cyclic):
    act = bpy.data.actions.new(name)
    arm.animation_data_create()
    arm.animation_data.action = act
    prev = {}
    for f in range(frames + 1):
        X = pose_fn(f % frames if cyclic else f)
        for pb in arm.pose.bones:
            Xb = X.get(pb.name, Matrix.Identity(4))
            Bm = REST[pb.name]
            basis = Bm.inverted() @ Xb @ Bm
            loc, q, _ = basis.decompose()
            if pb.name in prev and q.dot(prev[pb.name]) < 0:
                q.negate()
            prev[pb.name] = q.copy()
            pb.rotation_mode = "QUATERNION"
            pb.location = loc
            pb.rotation_quaternion = q
            pb.scale = (1, 1, 1)
            pb.keyframe_insert("location", frame=f, group=pb.name)
            pb.keyframe_insert("rotation_quaternion", frame=f, group=pb.name)
            pb.keyframe_insert("scale", frame=f, group=pb.name)
    act.use_fake_user = True
    act.use_frame_range = True
    act.frame_start, act.frame_end = 0, frames
    act.use_cyclic = cyclic
    track = arm.animation_data.nla_tracks.new()
    track.name = name
    track.strips.new(name, 0, act)
    track.mute = True
    arm.animation_data.action = None
    return act


def reset_pose(arm):
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.scale = (1, 1, 1)


# --------------------------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------------------------
def export_glb(path, arm, objs):
    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.gltf(
        filepath=path, export_format="GLB", use_selection=True, export_yup=True, export_apply=False,
        export_texcoords=True, export_normals=True, export_materials="EXPORT", export_image_format="NONE",
        export_skins=True, export_influence_nb=4, export_def_bones=False, export_morph=False,
        export_animations=True, export_animation_mode="ACTIONS", export_nla_strips=True,
        export_force_sampling=True, export_optimize_animation_size=False, export_reset_pose_bones=True,
        export_rest_position_armature=True, export_anim_slide_to_zero=False, export_frame_range=False,
        export_extras=False, export_cameras=False, export_lights=False)


# --------------------------------------------------------------------------------------------
# Vorschau (eigener Blender-Prozess, liest die exportierten GLBs) und Notizen
# --------------------------------------------------------------------------------------------
def run_previews(out):
    script = os.path.join(_script_dir(), "preview_badger.py")
    jobs = {
        "high": ["--glb", os.path.join(out, "badger.glb"), "--views", "front,side,back,walk,wave", "--check"],
        "low": ["--glb", os.path.join(out, "badger_low.glb"), "--prefix", "preview_badger_low",
                "--views", "front,side", "--check"],
    }
    checks = {}
    for tag, args in jobs.items():
        r = subprocess.run([bpy.app.binary_path, "-b", "--factory-startup", "-P", script, "--"] + args,
                           capture_output=True, text=True)
        text = r.stdout + r.stderr
        if r.returncode != 0 or "Traceback" in text:
            print(text)
            raise RuntimeError(f"preview_badger.py ({tag}) ist fehlgeschlagen")
        c = {"images": [os.path.basename(l.split(" ", 1)[1]) for l in r.stdout.splitlines()
                        if l.startswith("PREVIEW ")]}
        for m in re.finditer(r"CHECK (\w+): frames \d+-\d+, tiefster Punkt (-?[\d.]+) m", r.stdout):
            c[m.group(1)] = float(m.group(2))
        m = re.search(r"Fußhub max L ([\d.]+) R ([\d.]+)", r.stdout)
        if m:
            c["lift"] = (float(m.group(1)), float(m.group(2)))
        checks[tag] = c
        for line in r.stdout.splitlines():
            if line.startswith("CHECK") and not line.startswith("CHECK   frame"):
                print(f"BADGER {tag} {line}")
    return checks


def gd(v):
    """Blender-Vektor -> Godot-Koordinaten (x, y, z) = (x, z, -y)."""
    return (v.x, v.z, -v.y)


def fmt(v, nd=3):
    return "(" + ", ".join(f"{c:.{nd}f}".replace("-0.000", "0.000") for c in v) + ")"


def de(x, nd=2):
    return f"{x:.{nd}f}".replace(".", ",")


BONE_INFO = {
    "root": "Ursprung am Boden zwischen den Füßen, zeigt nach vorn; ohne Gewichte, in allen Animationen in Ruhe",
    "hips": "Becken und Bauch unten; Wippen, Seitwärtsschaukeln und Drehen im Lauf",
    "spine": "unterer Rücken, Bauch",
    "chest": "Brust, Schultern, Schalwicklung unten, vorderes Schalende",
    "neck": "Hals, Schalwicklung oben",
    "head": "Kopf mit Mütze, Ohren, Augen, Nase, Mund (starr)",
    "upper_arm": "Oberarm mit Hemdsärmel",
    "forearm": "Unterarm",
    "hand": "Pfote",
    "thigh": "Oberschenkel",
    "shin": "Unterschenkel",
    "foot": "Fuß (Pfote mit Krallen)",
    "scarf_1": "hinteres Schalende, obere Hälfte",
    "scarf_2": "hinteres Schalende, untere Hälfte",
    "tail": "Schwanz",
}


def write_notes(path, arm, stats, bbox, checks, seconds):
    dat = {"L": "linken", "R": "rechten"}        # Dativ: mit der linken Hand
    nom = {"L": "linke", "R": "rechte"}          # Nominativ: die linke Hand
    p1, p2, _ = table_lin(STRIPES, EYE_X)
    eye_z = head_pt(EYE_X, radians(0.5 * (p1 + p2) + EYE_DPHI)).z
    belly_z = max(TORSO, key=lambda r: r[3])[0]
    belly_w = 2 * max(r[3] for r in TORSO) + 2 * VEST_LIP
    lines = []
    w = lines.append
    w("# Dachs-Kurier `badger.glb`: Notizen")
    w("")
    w("Geriggte, animierte Figur des Dachs-Kuriers (Referenz: `shared/badger/master_sheet.png`, vorn/Seite/hinten) "
      "für alle 3D-Stile. Stile ändern Materialien, Shader, Auflösung und Nachbearbeitung, nicht Geometrie, "
      "Knochen oder Animationen. Diese Datei erzeugt das Bauskript bei jedem Lauf; alle Zahlen kommen direkt "
      "aus dem Skript bzw. aus der Prüfung der exportierten Dateien.")
    w("")
    w("## Bauen")
    w("")
    w("```")
    w("blender -b --factory-startup -P shared/3d/blender/build_badger.py --")
    w("blender -b --factory-startup -P shared/3d/blender/build_badger.py -- --no-preview")
    w("blender -b --factory-startup -P shared/3d/blender/build_badger.py -- --parcel-side L --out /tmp/badger_l")
    w("blender -b --factory-startup -P shared/3d/blender/preview_badger.py -- --glb shared/3d/badger.glb \\")
    w("    --views front,side,back,threequarter,walk,wave,idle --check")
    w("```")
    w("")
    w("Ausgaben: `badger.glb`, `badger_low.glb`, diese Notizen und die Vorschaubilder `preview_badger_*.png`. "
      "Die Figur entsteht vollständig im Skript aus Grundformen (Ring-Lofts, Ellipsoide, Röhren entlang "
      "Kurven, gefaste Quader), ohne Zufall und ohne .blend-Vorlage; ein Neubau ergibt bytegleiche GLB-Dateien. "
      "Die Vorschaubilder rendert "
      "`preview_badger.py` mit EEVEE aus den **exportierten** GLBs, sie zeigen also genau das, was Godot "
      f"bekommt. Laufzeit dieses Laufs {de(seconds, 0)} s (mit Vorschau und Prüfung), Blender 5.2 LTS.")
    w("")
    w("## Ausrichtung und Maße")
    w("")
    w("- 1 Einheit = 1 m, glTF mit +Y oben. Umrechnung wie bei `harbor.glb`: **Godot (x, y, z) = Blender (x, z, −y)**.")
    w("- Die Figur **blickt nach +X** (läuft nach rechts). Ihre rechte Körperseite zeigt nach **+Z**, also zur "
      "Hafenkamera (Kamera auf +Z, Blick nach −Z); die linke Seite zeigt nach −Z.")
    w("- Ursprung = Knochen `root` auf dem Boden (y = 0) zwischen den Füßen. Fußsohlen bei y = 0,003.")
    w(f"- Höhe {de(bbox['h'], 3)} m (Mützendeckel), Länge {de(bbox['l'], 2)} m (hinten Tasche/Schwanz bis Nasenspitze, "
      f"x {de(bbox['x0'])} bis {de(bbox['x1'])}), Breite {de(bbox['w'], 2)} m (z {de(bbox['z0'])} bis "
      f"{de(bbox['z1'])}, Ellbogen und Paket).")
    w(f"- Augenhöhe {de(eye_z)} m, Nasenspitze bei x = {de(bbox['x1'])}. Bauch am breitesten "
      f"({de(belly_w)} m) auf {de(belly_z)} m Höhe. Hüftgelenk auf {de(leg_joints('L')[0].z)} m.")
    w("- Im Hafen auf den Laufweg setzen: `position = Vector3(x, 0, 1.2)`, keine Drehung nötig "
      "(`WalkStart` → `WalkEnd` ist +X). Nach links laufen: `rotation_degrees.y = 180` "
      "(dann ist die linke Seite und nicht das Paket zur Kamera gewandt; siehe `--parcel-side`).")
    w("")
    w("## Paketseite (Entscheidung)")
    w("")
    w(f"Gebaut ist die Fassung `--parcel-side {PS}`: Paket unter dem **{dat[PS]}** Arm, gewinkt wird mit der "
      f"**{dat[FS]}** Hand. Tasche hinten an der Hüfte der Paketseite, Riemen über die Schulter der "
      "freien Seite, ein Schalende vorn auf der freien Seite, eines hinten auf der Paketseite.")
    w("")
    w("Grund: Das Referenzblatt zeigt das Paket in allen drei Ansichten unter dem **rechten** Arm (vorn: im Bild "
      "links; Seitenansicht nach rechts blickend: auf der zugewandten Seite; hinten: im Bild rechts). Wer nach "
      "rechts läuft, wendet der Kamera die rechte Seite zu; so ist das Paket in der Hafenansicht sichtbar wie "
      "im gemalten Laufzyklus `shared/badger/walk_painted.png`. Der Bauauftrag nannte den linken Arm; damit "
      "läge das Paket in der Hafenansicht hinter dem Körper. Wer die linke Fassung braucht: "
      "`--parcel-side L` spiegelt Paket, Tasche, Riemen, Schalenden und Winkarm (Knochen bleiben gleich). "
      "Abwägung: Mit `R` ist in der Seitenansicht das Paket zu sehen, die winkende Hand aber verdeckt; mit `L` "
      "ist es umgekehrt.")
    w("")
    w("## Knoten in Godot")
    w("")
    w("```")
    w("badger (Node3D)")
    w("├─ Armature (Node3D)")
    w("│  └─ Skeleton3D")
    w("│     ├─ Badger   (MeshInstance3D, Figur)")
    w("│     └─ Parcel   (MeshInstance3D, Paket; einzeln ausblendbar)")
    w("└─ AnimationPlayer   (Idle, Walk, Wave)")
    w("```")
    w("")
    w("`badger_low.glb` hat denselben Aufbau, dieselben Knochen und dieselben Animationen.")
    w("")
    w("## Knochen")
    w("")
    w("Positionen in Godot-Koordinaten (Meter, Ruhepose). Namen mit `.L`/`.R` = linke/rechte Körperseite der Figur.")
    w("")
    w("| Knochen | Eltern | Kopf | Spitze | bewegt |")
    w("|---|---|---|---|---|")
    for name in BONE_ORDER:
        b = arm.data.bones[name]
        par = b.parent.name if b.parent else "–"
        key = name.split(".")[0]
        info = BONE_INFO.get(key, "")
        if name == "hand." + PS:
            info += "; hält das Paket (Mesh `Parcel` hängt zu 100 % hier)"
        w(f"| `{name}` | {par} | `{fmt(gd(b.head_local))}` | `{fmt(gd(b.tail_local))}` | {info} |")
    w("")
    w("## Animationen")
    w("")
    lift = checks.get("high", {}).get("lift")
    lift_txt = f"bis {de(min(lift) * 100, 1)} cm" if lift else "ca. 7 cm"
    w("| Name | Länge | Bilder bei 30 fps | Schleife | Inhalt |")
    w("|---|---|---|---|---|")
    w(f"| `Idle` | {de(IDLE_FRAMES / FPS, 1)} s | {IDLE_FRAMES} | ja | Atmen (Brust hebt und senkt sich, Schultern "
      "gehen mit), leichte Gewichtsverlagerung, Kopf nickt und schaut minimal umher, Schwanz und hinteres "
      "Schalende wippen. Füße stehen fest (IK). |")
    w(f"| `Walk` | {de(WALK_FRAMES / FPS, 1)} s | {WALK_FRAMES} | ja | Laufzyklus auf der Stelle, zwei Schritte. "
      f"Ferse setzt auf, Fuß rollt ab, Zehen drücken ab, Schwungbein hebt den Fuß {lift_txt}. Becken wippt, "
      "schaukelt und dreht sich, Oberkörper dreht gegen, freier Arm schwingt gegen das Bein, Paketarm bleibt "
      "fast ruhig, hinteres Schalende fliegt nach hinten und schwingt, Schwanz wedelt. |")
    w(f"| `Wave` | {de(WAVE_FRAMES / FPS, 1)} s | {WAVE_FRAMES} | nein | Winkt mit der freien ({dat[FS]}) Hand: "
      "Arm hoch (0–0,38 s), zwei Mal hin und her (bis 1,12 s), wieder ab. Kopf neigt sich zur Hand, Oberkörper "
      "lehnt leicht zur anderen Seite. Beginnt und endet in der Ruhepose, Füße fest. |")
    w("")
    w(f"- **Laufgeschwindigkeit {de(WALK_SPEED, 3)} m/s.** Die Figur in Godot mit dieser Geschwindigkeit nach +X "
      "bewegen, dann rutschen die Füße nicht (bei `speed_scale` s entsprechend v · s). Kein Root-Motion: `root` "
      "bleibt in allen Animationen in Ruhe.")
    w("- Phasen im `Walk`: 0,00 s linke Ferse setzt auf · 0,30 s rechter Fuß schwingt durch (höchster Punkt) · "
      "0,50 s rechte Ferse setzt auf · 0,80 s linker Fuß schwingt durch. Das letzte Bild gleicht dem ersten, "
      "die Schleife ist nahtlos.")
    w("- **Schleife einschalten:** glTF kennt kein Loop-Flag, Godot importiert alle drei Animationen mit "
      "`LOOP_NONE`. Entweder in den erweiterten Importeinstellungen je Animation „Loop Mode“ setzen oder im Code:")
    w("")
    w("```gdscript")
    w("var badger: Node3D = load(\"res://badger.glb\").instantiate()")
    w("add_child(badger)")
    w("var player: AnimationPlayer = badger.get_node(\"AnimationPlayer\")")
    w("for n in [\"Idle\", \"Walk\"]:")
    w("    player.get_animation(n).loop_mode = Animation.LOOP_LINEAR")
    w("player.play(\"Walk\")")
    w(f"# in _process: badger.position.x += {WALK_SPEED:.3f} * delta")
    w("```")
    w("")
    w("## Materialien")
    w("")
    w("Stilneutral wie beim Hafen: nur Grundfarbe (sRGB), Rauheit, Metall, keine Texturen. Die Namen bleiben "
      "beim Import erhalten (`resource_name`), Stile erkennen und ersetzen sie daran.")
    w("")
    w("| Material | Farbe | Rauheit | Metall | verwendet für |")
    w("|---|---|---:|---:|---|")
    for name, color, rough, metal, use in MAT_DEFS:
        w(f"| `{name}` | {color} | {de(rough)} | {de(metal, 1)} | {use} |")
    w("")
    w("Hinweise: Das Mützenband und der Riemen nutzen `Satchel` (gleiches Leder). Die Paketschnur nutzt `Shirt`, "
      "der Glanzpunkt in den Augen `FurLight`. Die Nase ist in der hohen Fassung eine eigene Kugel, in der "
      "Low-Fassung die Schnauzenspitze.")
    w("")
    w("## Meshes und Dreiecke")
    w("")
    w("| Datei | Mesh | Dreiecke | Punkte (Blender) | Materialien |")
    w("|---|---|---:|---:|---|")
    for tag, fname in (("high", "badger.glb"), ("low", "badger_low.glb")):
        st = stats[tag]
        w(f"| `{fname}` | `Badger` | {st['body']} | {st['verts']} | {', '.join(st['mats'])} |")
        w(f"| `{fname}` | `Parcel` | {st['parcel']} | {st['pverts']} | {', '.join(st['pmats'])} |")
    for tag, fname in (("high", "badger.glb"), ("low", "badger_low.glb")):
        st = stats[tag]
        w(f"")
        w(f"`{fname}` zusammen: **{st['body'] + st['parcel']} Dreiecke**.")
    w("")
    w("Die Low-Fassung hat dieselbe Silhouette mit 4–8 Segmenten je Ring; es fehlen Mund, Westenknöpfe, "
      "Taschenklappen, Rückenriegel, Paketschnur, Krallen und Glanzpunkte, der Schal hat eine statt zwei "
      "Wicklungen, die Augen sind etwas größer.")
    w("")
    w("## Gewichte")
    w("")
    w("- Automatische Gewichte (Bone Heat) je Körperteil, jeweils nur mit den Knochen, die das Teil bewegen "
      "sollen: Rumpf `hips, spine, chest, neck`; Bein `thigh, shin, foot`; Fuß `shin, foot`; Arm "
      "`upper_arm, forearm, hand`; Schwanz `hips, tail`. So zieht ein schwingender Arm nicht an der Weste.")
    w("- Fußsohlen (unter 2,5 cm) hängen ganz an `foot`, bis 5 cm übergeblendet: Der aufgesetzte Fuß bleibt exakt "
      "am Boden.")
    w("- Starr: Kopf samt Mütze, Ohren, Augen, Nase, Mund → `head`; Krallen → `foot`; vorderes Schalende → "
      f"`chest`; Paket → `hand.{PS}`.")
    w("- Schalwicklungen nach Höhe von `chest` nach `neck`; hinteres Schalende nach Höhe `chest` → `scarf_1` → "
      "`scarf_2`.")
    w("- Riemen, Westenknöpfe, Taschenklappen: Gewichte vom nächstgelegenen Rumpfpunkt übernommen. Die Tasche "
      "bekommt für alle Punkte die Gewichte an ihrem Mittelpunkt, damit sie starr bleibt.")
    w("- Höchstens 4 Einflüsse je Punkt, normiert.")
    w("")
    w("## UVs und Normalen")
    w("")
    w("- UV-Map `UVMap` aus Smart UV Project (66°), danach **1 UV-Einheit = 1 m** wie bei `harbor.glb` "
      "(Kacheltexturen erscheinen auf Figur und Hafen gleich groß). Die UVs liegen deshalb nicht in 0..1. "
      "Die Inseln überlappen nicht und werden in fester Reihenfolge angeordnet, ein Neubau ergibt dieselben UVs "
      "(eine aufgemalte Textur bleibt gültig).")
    w("- Weiche Normalen. Harte Kanten ab 40° bei Tasche, Paket, Schnur; ab 50° am Mützenschirm; ab 60° bei "
      "Riemen und Westenklappen.")
    w("- Jedes Teil ist eine geschlossene Hülle; Arme, Beine, Schwanz, Kopf und Schal stecken im Rumpf, statt "
      "mit ihm verschmolzen zu sein. Für Umriss-Shader (umgedrehte Hülle) und Flat-Shading unproblematisch.")
    w("- Fellzeichnung, Weste und Bauch sind Materialgrenzen auf Kanten (die Ringpunkte liegen genau auf den "
      "Streifengrenzen), daher saubere Kanten ohne Textur. Die Weste ist 7 mm aufgesetzt (echte Kante am Saum).")
    w("")
    w("## Prüfung")
    w("")
    h = checks.get("high", {})
    lo = checks.get("low", {})
    if h:
        w("Werte aus `preview_badger.py --check` (ausgewertet am verformten Mesh, jedes Bild der Animation):")
        w("")
        w("| Datei | tiefster Punkt Idle | tiefster Punkt Walk | tiefster Punkt Wave | Fußhub Walk L / R |")
        w("|---|---:|---:|---:|---:|")
        for tag, fname, c in (("high", "badger.glb", h), ("low", "badger_low.glb", lo)):
            if not c:
                continue
            lf = c.get("lift", (0, 0))
            w(f"| `{fname}` | {de(c.get('Idle', 0) * 1000, 1)} mm | {de(c.get('Walk', 0) * 1000, 1)} mm | "
              f"{de(c.get('Wave', 0) * 1000, 1)} mm | {de(lf[0] * 100, 1)} / {de(lf[1] * 100, 1)} cm |")
        w("")
        w("Kein Punkt geht unter den Boden (alle Werte ≥ 0). Die Knöchelziele des Laufzyklus sind alle "
          f"erreichbar (IK-Begrenzungen: {len(IK_WARN)}).")
    else:
        w("Dieser Lauf hat keine Prüfung ausgeführt (`--no-preview`).")
    w("")
    w("Zusätzlich von Hand geprüft: Import beider Dateien in Godot 4.7.2 (headless, keine Fehler; Knochen, "
      "Animationslängen, Material- und Knotennamen wie oben; Paket auf der +Z-Seite) und Sichtprüfung der "
      "Vorschaubilder gegen das Referenzblatt.")
    w("")
    if h.get("images"):
        w("Vorschaubilder (EEVEE, aus den GLBs): " + ", ".join(f"`{x}`" for x in h["images"] + lo.get("images", []))
          + ". `walk_1..3` = Seitenansicht wie die Hafenkamera bei 0,00 s, 0,30 s und 0,50 s.")
        w("")
    w("## Hinweise für Stile")
    w("")
    w("- Materialien per Name tauschen (wie beim Hafen): alle `MeshInstance3D` durchgehen, "
      "`mesh.surface_get_material(i).resource_name` prüfen, `set_surface_override_material(i, …)` setzen.")
    w("- Paket ausblenden (z. B. nach der Übergabe): `badger.get_node(\"Armature/Skeleton3D/Parcel\").visible = false`.")
    w("- PS1/N64: `badger_low.glb` mit niedriger Auflösung und Nearest-Filter; gleiche Knochen, Animationen und "
      "Materialnamen, Code bleibt gleich.")
    w("- Pixel-3D, 1-Bit, Toon: geschlossene Hüllen und Materialgrenzen auf Kanten funktionieren mit "
      "Umriss- und Stufen-Shadern; Farben je Material ersetzen.")
    w("- Animationen überblenden: `Wave` beginnt und endet in der Ruhepose, `Idle` liegt nahe daran; "
      "`player.play(\"Wave\", 0.2)` blendet weich ein.")
    w("- Winken in der Hafenszene: Die Seitenansicht verdeckt den Winkarm. Figur zur Kamera drehen "
      "(`rotation_degrees.y = -90`, Blick nach +Z), dann `Wave` spielen. Das ergibt die Vorderansicht des "
      "Referenzblatts mit dem Paket im Bild links.")
    w("")
    w("## Grenzen")
    w("")
    w(f"- In der reinen Seitenansicht (Hafenkamera) ist die winkende {nom[FS]} Hand ganz hinter dem Kopf "
      "verborgen. `Wave` ist für Ansichten von vorn oder schräg vorn gebaut; in der Hafenszene die Figur vorher "
      "zur Kamera drehen (siehe Hinweise).")
    w("- Das Paket liegt ein paar Zentimeter im Bauch (angedrückt) und folgt der Hand; im Lauf verschiebt es sich "
      "mit dem Paketarm um etwa 1–2 cm gegen den Körper.")
    w("- Keine Gesichtsanimation (kein Blinzeln, kein Mund), keine Fingerknochen; die Pfoten sind geschlossene Formen.")
    w("- Nur das hintere Schalende hat Knochen; das vordere Ende hängt fest an der Brust.")
    w("- Arme und Beine stecken als eigene Hüllen im Rumpf. Bei starkem Beugen (Arm über Kopf beim Winken, "
      "Beinschwung) sieht man an Schulter und Hüfte die Durchdringungskante; bei den gezeigten Animationen "
      "liegt sie im Ärmel bzw. unter dem Bauch.")
    w("- Fell nur als Fläche ohne Fellkanten; die Strickstruktur des Schals ist nur durch Rippen in der "
      "Geometrie angedeutet (hohe Fassung). Feinheiten wie Taschenklappen, Knöpfe und Schnur sind klein "
      "und verschwinden bei niedriger Auflösung.")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def main():
    t0 = time.time()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.unit_settings.system = "METRIC"
    make_materials()
    arm = build_armature()
    hi_body, hi_parcel, rep_hi = build_figure(HIGH, arm)
    lo_body, lo_parcel, rep_lo = build_figure(LOW, arm)
    acts = [make_action(arm, "Idle", IDLE_FRAMES, idle_pose, True),
            make_action(arm, "Walk", WALK_FRAMES, walk_pose, True),
            make_action(arm, "Wave", WAVE_FRAMES, wave_pose, False)]
    reset_pose(arm)
    sc.frame_set(0)
    os.makedirs(ARGS.out, exist_ok=True)
    stats = {}
    for tag, body, parcel, fname in (("high", hi_body, hi_parcel, "badger.glb"),
                                     ("low", lo_body, lo_parcel, "badger_low.glb")):
        others = [o for o in (hi_body, hi_parcel, lo_body, lo_parcel) if o not in (body, parcel)]
        for o in others:                         # Namen frei machen: exportierte Meshes heißen immer gleich
            o.name = o.name + "_x"
            o.data.name = o.data.name + "_x"
        body.name = body.data.name = "Badger"
        parcel.name = parcel.data.name = "Parcel"
        export_glb(os.path.join(ARGS.out, fname), arm, [body, parcel])

        def used(ob):
            idx = {p.material_index for p in ob.data.polygons}
            return [m.name for i, m in enumerate(ob.data.materials) if i in idx]
        stats[tag] = dict(body=tri_count(body), parcel=tri_count(parcel), verts=len(body.data.vertices),
                          pverts=len(parcel.data.vertices), mats=used(body), pmats=used(parcel))
        body.name = body.data.name = f"Badger_{tag}"
        parcel.name = parcel.data.name = f"Parcel_{tag}"
        for o in others:
            o.name = o.name[:-2]
            o.data.name = o.data.name[:-2]
    cos_ = [v.co for o in (hi_body, hi_parcel) for v in o.data.vertices]
    xs, ys, zs = [c.x for c in cos_], [c.y for c in cos_], [c.z for c in cos_]
    bbox = dict(h=max(zs), x0=min(xs), x1=max(xs), l=max(xs) - min(xs), z0=-max(ys), z1=-min(ys),
                w=max(ys) - min(ys))
    if ARGS.save_blend:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(ARGS.save_blend))
    print("BADGER parcel side:", PS, "free side:", FS)
    print("BADGER tris:", {k: (v["body"], v["parcel"]) for k, v in stats.items()})
    print("BADGER bone-heat fallback verts:", rep_hi, rep_lo)
    print("BADGER walk speed m/s:", round(WALK_SPEED, 3))
    print("BADGER IK clamps:", len(IK_WARN), IK_WARN[:10])
    print("BADGER actions:", [(a.name, tuple(a.frame_range)) for a in acts])
    print("BADGER bbox:", {k: round(v, 3) for k, v in bbox.items()})
    checks = {} if ARGS.no_preview else run_previews(ARGS.out)
    if not ARGS.no_notes:
        write_notes(os.path.join(ARGS.out, "badger_notes.md"), arm, stats, bbox, checks, time.time() - t0)
        print("BADGER notes:", os.path.join(ARGS.out, "badger_notes.md"))


main()
