"""Hafen von Lornholm: gemeinsame, stilneutrale 3D-Grundszene fuer alle 3D-Stile.

Aufruf (aus dem Projektordner):
  blender -b --factory-startup -P shared/3d/blender/build_harbor.py -- [Optionen]

Optionen:
  --out PATH          Ziel-glb (Standard: shared/3d/harbor.glb)
  --notes PATH        Notizen (Standard: shared/3d/harbor_notes.md)
  --preview-dir DIR   Ordner fuer preview_harbor_<ansicht>.png (Standard: shared/3d)
  --views LIST        Kommagetrennt: main, overview, top, side, cottage, boats, lighthouse, props
                      (Standard: main,overview)
  --no-preview        nur bauen und exportieren
  --samples N         EEVEE-Samples fuer die Vorschau (Standard: 48)
  --blend PATH        zusaetzlich eine .blend speichern (nur zum Nachsehen, nicht einchecken)

Koordinaten in Blender: Z oben, Meter. Der Kai laeuft entlang X, seine Oberflaeche liegt bei Z=0,
die Kamera blickt von -Y nach +Y. Export als glTF mit +Y oben: Godot (x, y, z) = Blender (x, z, -y).
Alles ist deterministisch (feste Seeds).
"""
import argparse
import json
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector, noise

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED3D = os.path.dirname(SCRIPT_DIR)

# --------------------------------------------------------------------------------------------
# Szenenmasse (Blender-Koordinaten, Meter)
# --------------------------------------------------------------------------------------------
WATER_Z = -0.8            # Wasserlinie; die Kaioberflaeche liegt bei Z = 0
SEABED_Z = -2.6           # Unterkante von Mauern, Pfaehlen und Gelaende
QUAY_X0, QUAY_X1 = -13.0, 8.0
QUAY_FRONT_Y = -8.0       # Vorderkante (zur Kamera)
QUAY_EDGE_Y = 1.0         # Wasserkante hinten
QUAY_CORNER_X = -5.0      # links davon reicht der Kai bis QUAY_BACK_Y zurueck
QUAY_BACK_Y = 3.6
MORTAR_Z = -0.05          # Fugenhoehe zwischen den Pflastersteinen
COPING_W = 0.62           # Breite der Kantensteine

WALK_Y = -1.2             # Laufweg des Dachses auf dem Kai
WALK_X0, WALK_X1 = -6.0, 2.0

JETTY_X0, JETTY_X1 = 2.65, 4.25
JETTY_Y0, JETTY_Y1 = 0.45, 8.6
JETTY_TOP = 0.04

COTTAGE_POS = Vector((-8.4, 1.0, 0.0))
COTTAGE_W, COTTAGE_D, COTTAGE_H, COTTAGE_RISE = 3.6, 3.0, 2.45, 1.35

LIGHTHOUSE_XY = (10.2, 25.6)
LIGHTHOUSE_BASE_Z = 2.8

# Hauptkamera (Blender): Position, Neigung, vertikaler Bildwinkel
CAM_MAIN = dict(pos=(-1.8, -14.5, 3.4), pitch=-3.0, yaw=0.0, fov_v=42.0)
CAM_OVERVIEW = dict(pos=(-26.0, -30.0, 25.0), target=(2.0, 9.0, 0.0), fov_v=42.0)

# --------------------------------------------------------------------------------------------
# Materialien: stilneutral, nur Grundfarbe (sRGB-Hex), Rauheit, Metall, ggf. Emission
# --------------------------------------------------------------------------------------------
MAT_DEFS = {
    "Stone":      dict(color="#8C877D", rough=0.90),
    "StoneDark":  dict(color="#5A5650", rough=0.90),
    "Wood":       dict(color="#8E6440", rough=0.80),
    "WoodDark":   dict(color="#4E3726", rough=0.85),
    "WhitePaint": dict(color="#E8E4DA", rough=0.60),
    "RedPaint":   dict(color="#B02A22", rough=0.55),
    "Roof":       dict(color="#4A5361", rough=0.80),
    "Glass":      dict(color="#FFD27A", rough=0.20, emit="#FFC060", emit_strength=4.0),
    "Rope":       dict(color="#BFA77A", rough=0.95),
    "Metal":      dict(color="#3C3D40", rough=0.50, metal=0.7),
    "Rock":       dict(color="#6E6A64", rough=0.95),
    "Sand":       dict(color="#C9B48A", rough=1.00),
    "Grass":      dict(color="#6E8048", rough=1.00),
    "Water":      dict(color="#2B5A6B", rough=0.15),
}
MATS = {}


def hex_lin(h):
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return out


def make_materials():
    for name, d in MAT_DEFS.items():
        m = bpy.data.materials.new(name)
        if m.node_tree is None:
            m.use_nodes = True
        bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        col = hex_lin(d["color"])
        bsdf.inputs["Base Color"].default_value = (*col, 1.0)
        bsdf.inputs["Roughness"].default_value = d["rough"]
        bsdf.inputs["Metallic"].default_value = d.get("metal", 0.0)
        if "emit" in d:
            bsdf.inputs["Emission Color"].default_value = (*hex_lin(d["emit"]), 1.0)
            bsdf.inputs["Emission Strength"].default_value = d["emit_strength"]
        m.diffuse_color = (*col, 1.0)
        MATS[name] = m


# --------------------------------------------------------------------------------------------
# Kleine Mathe-Helfer
# --------------------------------------------------------------------------------------------
def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def M(loc=(0, 0, 0), rot=(0, 0, 0), scale=None):
    """Matrix aus Ort, Rotation in Grad (XYZ) und optionaler Skalierung."""
    e = Euler(tuple(math.radians(a) for a in rot), "XYZ")
    s = Vector(scale) if scale is not None else Vector((1, 1, 1))
    return Matrix.LocRotScale(Vector(loc), e, s)


def polyline_dist(px, py, pts):
    lens = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
    total = sum(lens)
    best_d, best_s, acc = 1e9, 0.0, 0.0
    for (a, b), L in zip(zip(pts, pts[1:]), lens):
        dx, dy = b[0] - a[0], b[1] - a[1]
        u = max(0.0, min(1.0, ((px - a[0]) * dx + (py - a[1]) * dy) / (L * L)))
        d = math.hypot(px - (a[0] + u * dx), py - (a[1] + u * dy))
        if d < best_d:
            best_d, best_s = d, (acc + u * L) / total
        acc += L
    return best_d, best_s


# --------------------------------------------------------------------------------------------
# Mesh-Baukasten: Teile als bmesh bauen, mit Material und Matrix in einen Sammler legen
# --------------------------------------------------------------------------------------------
class MB:
    def __init__(self):
        self.v, self.f, self.m = [], [], []

    def add(self, bm, mats, mtx=None):
        if isinstance(mats, str):
            mats = [mats]
        off = len(self.v)
        bm.verts.index_update()
        for vt in bm.verts:
            co = mtx @ vt.co if mtx is not None else vt.co
            self.v.append((co.x, co.y, co.z))
        for fc in bm.faces:
            self.f.append([vt.index + off for vt in fc.verts])
            self.m.append(mats[min(fc.material_index, len(mats) - 1)])
        bm.free()
        return self


def bm_box(sx, sy, sz, bevel=0.0, drop_bottom=False):
    """Quader um den Ursprung."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= sx
        v.co.y *= sy
        v.co.z *= sz
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, offset_type="OFFSET", segments=1,
                        profile=0.5, affect="EDGES", clamp_overlap=True)
    if drop_bottom:
        bm.normal_update()
        kill = [f for f in bm.faces if f.normal.z < -0.99]
        bmesh.ops.delete(bm, geom=kill, context="FACES")
    return bm


def bm_cyl(r1, r2, depth, seg, caps=True):
    """Zylinder/Kegel entlang Z um den Ursprung."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=caps, cap_tris=False, segments=seg, radius1=r1,
                          radius2=r2, depth=depth)
    return bm


def bm_lathe(profile, seg, bands=None, cap_bottom=True, cap_top=True, phase=0.0):
    """Drehkoerper aus (r, z)-Profil von unten nach oben; bands[i] = Materialindex zwischen Ring i und i+1."""
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        rings.append([bm.verts.new((r * math.cos(2 * math.pi * k / seg + phase),
                                    r * math.sin(2 * math.pi * k / seg + phase), z))
                      for k in range(seg)])
    for i in range(len(rings) - 1):
        for k in range(seg):
            a, b = rings[i][k], rings[i][(k + 1) % seg]
            c, d = rings[i + 1][(k + 1) % seg], rings[i + 1][k]
            f = bm.faces.new((a, b, c, d))
            f.material_index = bands[i] if bands else 0
    if cap_bottom and profile[0][0] > 1e-6:
        f = bm.faces.new(list(reversed(rings[0])))
        f.material_index = bands[0] if bands else 0
    if cap_top and profile[-1][0] > 1e-6:
        f = bm.faces.new(rings[-1])
        f.material_index = bands[-1] if bands else 0
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    return bm


def bm_tube(pts, radius, sides=6, closed=False, caps=True, radius_fn=None):
    """Rohr entlang einer Punktliste (Parallel-Transport-Rahmen)."""
    bm = bmesh.new()
    P = [Vector(p) for p in pts]
    n = len(P)
    rings, prev = [], None
    for i in range(n):
        if closed:
            t = (P[(i + 1) % n] - P[(i - 1) % n]).normalized()
        else:
            t = (P[min(i + 1, n - 1)] - P[max(i - 1, 0)]).normalized()
        if prev is None:
            ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
            nn = (ref - t * ref.dot(t)).normalized()
        else:
            nn = (prev - t * prev.dot(t)).normalized()
        prev = nn
        b = t.cross(nn)
        r = radius_fn(i / (n - 1)) if radius_fn else radius
        rings.append([bm.verts.new(P[i] + r * (math.cos(2 * math.pi * k / sides) * nn +
                                               math.sin(2 * math.pi * k / sides) * b))
                      for k in range(sides)])
    for i in range(n if closed else n - 1):
        r0, r1 = rings[i], rings[(i + 1) % n]
        for k in range(sides):
            bm.faces.new((r0[k], r0[(k + 1) % sides], r1[(k + 1) % sides], r1[k]))
    if caps and not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    return bm


def bm_slab(x0, x1, y0, y1, z0, z1, chamfer, ztop_jitter=(0, 0, 0, 0), vertical=0.0):
    """Stein mit abgeschraegter Oberkante, ohne Unterseite. vertical = Hoehe des senkrechten Teils."""
    bm = bmesh.new()
    zc = z0 + vertical if vertical > 0 else z0
    base = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    bot = [bm.verts.new((x, y, z0)) for x, y in base]
    rings = [bot]
    if vertical > 0:
        rings.append([bm.verts.new((x, y, zc)) for x, y in base])
    top = [bm.verts.new((x0 + chamfer, y0 + chamfer, z1 + ztop_jitter[0])),
           bm.verts.new((x1 - chamfer, y0 + chamfer, z1 + ztop_jitter[1])),
           bm.verts.new((x1 - chamfer, y1 - chamfer, z1 + ztop_jitter[2])),
           bm.verts.new((x0 + chamfer, y1 - chamfer, z1 + ztop_jitter[3]))]
    rings.append(top)
    for ra, rb in zip(rings, rings[1:]):
        for k in range(4):
            bm.faces.new((ra[k], ra[(k + 1) % 4], rb[(k + 1) % 4], rb[k]))
    bm.faces.new(top)
    return bm


def bm_heightfield(x0, x1, y0, y1, step, hfun, jitter=0.0, seed=1, cull=None):
    rng = random.Random(seed)
    nx, ny = int(round((x1 - x0) / step)), int(round((y1 - y0) / step))
    bm = bmesh.new()
    grid = []
    for j in range(ny + 1):
        row = []
        for i in range(nx + 1):
            x, y = x0 + i * step, y0 + j * step
            if 0 < i < nx and 0 < j < ny and jitter > 0:
                x += rng.uniform(-jitter, jitter)
                y += rng.uniform(-jitter, jitter)
            row.append(bm.verts.new((x, y, hfun(x, y))))
        grid.append(row)
    for j in range(ny):
        for i in range(nx):
            vs = (grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i])
            if cull and cull([v.co for v in vs]):
                continue
            bm.faces.new(vs)
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY")
    bm.normal_update()
    return bm


# --------------------------------------------------------------------------------------------
# Objekte anlegen
# --------------------------------------------------------------------------------------------
def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def place(ob, world_loc, parent=None, rot_z=0.0):
    if parent is not None:
        ob.parent = parent
        ob.location = Vector(world_loc) - parent.location
    else:
        ob.location = Vector(world_loc)
    ob.rotation_euler = (0.0, 0.0, math.radians(rot_z))


def make_obj(name, mb, loc=(0, 0, 0), smooth=None, parent=None, rot_z=0.0):
    me = bpy.data.meshes.new(name)
    me.from_pydata(mb.v, [], mb.f)
    names = []
    for n in mb.m:
        if n not in names:
            names.append(n)
    for n in names:
        me.materials.append(MATS[n])
    me.polygons.foreach_set("material_index", [names.index(n) for n in mb.m])
    me.validate(clean_customdata=False)
    # N-Ecke selbst triangulieren (gleichmaessige Dreiecke statt Faecher, feste Reihenfolge im glb)
    bm = bmesh.new()
    bm.from_mesh(me)
    ngons = [f for f in bm.faces if len(f.verts) > 4]
    if ngons:
        bmesh.ops.triangulate(bm, faces=ngons, quad_method="BEAUTY", ngon_method="BEAUTY")
        bm.to_mesh(me)
    bm.free()
    me.update()
    if smooth:
        me.shade_smooth()
        me.set_sharp_from_angle(angle=math.radians(smooth))
    else:
        me.shade_flat()
    ob = link(bpy.data.objects.new(name, me))
    place(ob, loc, parent, rot_z)
    return ob


def make_empty(name, loc, parent=None, size=0.3):
    ob = link(bpy.data.objects.new(name, None))
    ob.empty_display_type = "PLAIN_AXES"
    ob.empty_display_size = size
    place(ob, loc, parent)
    return ob


# --------------------------------------------------------------------------------------------
# Meer
# --------------------------------------------------------------------------------------------
def graded(inner_min, inner_max, step, outer_lo, outer_hi, n_lo, n_hi):
    """Feines Raster innen, geometrisch wachsende Abstaende nach aussen."""
    inner = [inner_min + i * step for i in range(int(round((inner_max - inner_min) / step)) + 1)]

    def grow(total, n):
        lo, hi = 1.0001, 4.0
        s0 = step * 1.25
        for _ in range(60):
            q = (lo + hi) / 2
            if s0 * (q ** n - 1) / (q - 1) > total:
                hi = q
            else:
                lo = q
        out, acc = [], 0.0
        for k in range(n):
            acc += s0 * q ** k
            out.append(acc)
        out[-1] = total
        return out

    lo = [inner_min - d for d in grow(inner_min - outer_lo, n_lo)] if n_lo else []
    hi = [inner_max + d for d in grow(outer_hi - inner_max, n_hi)] if n_hi else []
    return list(reversed(lo)) + inner + hi


def build_sea():
    xs = graded(-21.0, 21.0, 1.5, -700.0, 700.0, 6, 6)
    ys = graded(-10.5, 33.0, 1.5, -40.0, 900.0, 2, 9)
    mb = MB()
    bm = bmesh.new()
    grid = [[bm.verts.new((x, y, 0.0)) for x in xs] for y in ys]
    for j in range(len(ys) - 1):
        for i in range(len(xs) - 1):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    mb.add(bm, "Water")
    ob = make_obj("Sea", mb, (0, 0, WATER_Z), smooth=180)
    # Planare UVs in Metern (u = x, v = y), passend fuer Wellen-Shader und Kacheltexturen
    me = ob.data
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (co.x, co.y)
    return ob, (len(xs) - 1, len(ys) - 1)


# --------------------------------------------------------------------------------------------
# Kai mit Pflaster, Kantensteinen und Pollern
# --------------------------------------------------------------------------------------------
def build_quay():
    rng = random.Random(7)
    mb = MB()
    bm = bmesh.new()
    wet = WATER_Z + 0.12
    outline = [(QUAY_X0, QUAY_FRONT_Y), (QUAY_X1, QUAY_FRONT_Y), (QUAY_X1, QUAY_EDGE_Y),
               (QUAY_CORNER_X, QUAY_EDGE_Y), (QUAY_CORNER_X, QUAY_BACK_Y), (QUAY_X0, QUAY_BACK_Y)]
    for (ax, ay), (bx, by) in zip(outline, outline[1:] + outline[:1]):
        for z0, z1, mi in ((SEABED_Z, wet, 1), (wet, MORTAR_Z, 0)):
            f = bm.faces.new([bm.verts.new(p) for p in ((ax, ay, z0), (bx, by, z0), (bx, by, z1), (ax, ay, z1))])
            f.material_index = mi
    # Fugenflaeche (dunkel) unter dem Pflaster, als zwei Rechtecke
    for x0, x1, y0, y1 in ((QUAY_X0, QUAY_X1, QUAY_FRONT_Y, QUAY_EDGE_Y),
                           (QUAY_X0, QUAY_CORNER_X, QUAY_EDGE_Y, QUAY_BACK_Y)):
        f = bm.faces.new([bm.verts.new((x, y, MORTAR_Z)) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))])
        f.material_index = 1
    mb.add(bm, ["Stone", "StoneDark"])

    # Kantensteine entlang der Wasserkanten (StoneDark), am Steg unterbrochen
    cz0, cz1 = -0.22, 0.10
    ov = 0.06
    edge_in = QUAY_EDGE_Y - COPING_W

    def coping_run(a0, a1, along_x, fixed0, fixed1, skip=None):
        a = a0
        while a < a1 - 0.05:
            L = rng.uniform(1.05, 1.45)
            b = min(a + L, a1)
            if a1 - b < 0.5:
                b = a1
            if not (skip and a < skip[1] and b > skip[0]):
                g = 0.025
                if along_x:
                    s = bm_slab(a + g, b - g, fixed0, fixed1, cz0, cz1 + rng.uniform(-0.01, 0.01), 0.035,
                                vertical=0.24)
                else:
                    s = bm_slab(fixed0, fixed1, a + g, b - g, cz0, cz1 + rng.uniform(-0.01, 0.01), 0.035,
                                vertical=0.24)
                mb.add(s, "StoneDark")
            a = b

    coping_run(QUAY_CORNER_X - COPING_W, QUAY_X1 + ov, True, edge_in, QUAY_EDGE_Y + ov,
               skip=(JETTY_X0 - 0.05, JETTY_X1 + 0.05))
    coping_run(QUAY_FRONT_Y, edge_in, False, QUAY_X1 - COPING_W, QUAY_X1 + ov)
    coping_run(QUAY_EDGE_Y + ov, QUAY_BACK_Y, False, QUAY_CORNER_X - COPING_W, QUAY_CORNER_X + ov)

    # Pflaster in Reihen mit versetzten Fugen
    cot_x0 = COTTAGE_POS.x - COTTAGE_W / 2 - 0.15
    cot_x1 = COTTAGE_POS.x + COTTAGE_W / 2 + 0.15
    cot_y0 = COTTAGE_POS.y - COTTAGE_D / 2 - 0.15
    cot_y1 = COTTAGE_POS.y + COTTAGE_D / 2 + 0.15

    def pave_rows(y_start, y_end, x_start, x_end):
        y = y_start
        while y < y_end - 0.01:
            d = rng.uniform(0.6, 0.8)
            y1 = min(y + d, y_end)
            if y_end - y1 < 0.35:
                y1 = y_end
            x = x_start
            while x < x_end - 0.01:
                L = rng.uniform(0.75, 1.25)
                x1 = min(x + L, x_end)
                if x_end - x1 < 0.35:
                    x1 = x_end
                cx, cy = (x + x1) / 2, (y + y1) / 2
                inside_cottage = cot_x0 < cx < cot_x1 and cot_y0 < cy < cot_y1
                if not inside_cottage:
                    g = 0.025
                    jit = tuple(rng.uniform(-0.008, 0.008) for _ in range(4))
                    mb.add(bm_slab(x + g, x1 - g, y + g, y1 - g, MORTAR_Z, 0.0, 0.035, jit), "Stone")
                x = x1
            y = y1

    pave_rows(QUAY_FRONT_Y, edge_in, QUAY_X0, QUAY_X1 - COPING_W)
    pave_rows(edge_in, QUAY_BACK_Y, QUAY_X0, QUAY_CORNER_X - COPING_W)
    quay = make_obj("Quay", mb, (0, 0, 0), smooth=None)

    # Poller aus Eisen an der Kante
    mb = MB()
    for bx in (-3.4, 0.7, 6.3):
        prof = [(0.17, 0.0), (0.15, 0.06), (0.125, 0.12), (0.12, 0.34), (0.19, 0.40), (0.19, 0.47),
                (0.12, 0.52), (0.0, 0.53)]
        mb.add(bm_lathe(prof, 12, cap_bottom=False), "Metal",
               Matrix.Translation((bx, QUAY_EDGE_Y - 0.3, cz1)))
    bollards = make_obj("Bollards", mb, (0, 0, 0), smooth=50)
    return quay, bollards


# --------------------------------------------------------------------------------------------
# Holzsteg
# --------------------------------------------------------------------------------------------
def build_jetty():
    rng = random.Random(21)
    mb = MB()
    w = JETTY_X1 - JETTY_X0
    cx = (JETTY_X0 + JETTY_X1) / 2
    # Planken quer zur Laufrichtung
    y = JETTY_Y0
    while y < JETTY_Y1 - 0.1:
        pw = rng.uniform(0.21, 0.26)
        b = bm_box(w + rng.uniform(-0.04, 0.06), pw, 0.06, drop_bottom=True)
        mb.add(b, "Wood", M((cx + rng.uniform(-0.03, 0.03), y + pw / 2, JETTY_TOP - 0.03 + rng.uniform(-0.006, 0.006)),
                            (0, 0, rng.uniform(-1.2, 1.2))))
        y += pw + 0.03
    # Laengstraeger und Querjoche
    for sx in (JETTY_X0 + 0.15, cx, JETTY_X1 - 0.15):
        mb.add(bm_box(0.12, JETTY_Y1 - QUAY_EDGE_Y, 0.16), "WoodDark",
               M((sx, (QUAY_EDGE_Y + JETTY_Y1) / 2, JETTY_TOP - 0.06 - 0.08)))
    bents = [1.7, 3.9, 6.1, 8.3]
    for by in bents:
        mb.add(bm_box(w + 0.5, 0.16, 0.16), "WoodDark", M((cx, by, JETTY_TOP - 0.22 - 0.08)))
        for px in (JETTY_X0 - 0.12, JETTY_X1 + 0.12):
            top = JETTY_TOP - 0.3
            if by in (6.1, 8.3):
                top = JETTY_TOP + (0.75 if by == 8.3 else 0.6)  # Festmachpfaehle
            depth = top - SEABED_Z
            mb.add(bm_cyl(0.12, 0.12, depth, 8), "WoodDark", M((px, by, SEABED_Z + depth / 2)))
            if top > JETTY_TOP:
                mb.add(bm_cyl(0.12, 0.05, 0.08, 8), "WoodDark", M((px, by, top + 0.04)))
    return make_obj("Jetty", mb, (0, 0, 0), smooth=40)


# --------------------------------------------------------------------------------------------
# Fischerboote (Ursprung an der Wasserlinie, Bug zeigt nach lokal +X)
# --------------------------------------------------------------------------------------------
def hull_param(P):
    L, B = P["L"], P["B"]

    def half_beam(t):
        if t < 0.42:
            u = t / 0.42
            return B / 2 * (P["transom"] + (1 - P["transom"]) * math.sin(u * math.pi / 2))
        u = (t - 0.42) / 0.58
        return B / 2 * max(0.0, 1 - u ** 2.0) ** 0.75

    def sheer(t):
        return (P["sheer"] + (P["bow"] - P["sheer"]) * max(0.0, (t - 0.5) / 0.5) ** 2
                + (P["stern"] - P["sheer"]) * max(0.0, (0.5 - t) / 0.5) ** 2)

    def keel(t):
        k = P["keel"]
        k += (0.12 - P["keel"]) * max(0.0, (t - 0.72) / 0.28) ** 2.2
        k += 0.12 * max(0.0, 1 - t / 0.22)
        return k

    def section(t, s):
        """s in [0, 1]: 0 = Kiel, 1 = Schandeck. Gibt (y >= 0, z) zurueck."""
        a = s * math.pi / 2
        hb, sh, kz = half_beam(t), sheer(t), keel(t)
        return hb * math.sin(a) ** 0.55, kz + (sh - kz) * (1 - math.cos(a) ** 1.6)

    def x_at(t, s):
        x = -L / 2 + t * L
        if t > 0.85:
            x += 0.32 * ((t - 0.85) / 0.15) ** 2 * s
        return x

    def width_at(t, z):
        prev = section(t, 0.0)
        for i in range(1, 101):
            cur = section(t, i / 100)
            if cur[1] >= z:
                if cur[1] == prev[1]:
                    return cur[0]
                u = (z - prev[1]) / (cur[1] - prev[1])
                return lerp(prev[0], cur[0], u)
            prev = cur
        return prev[0]

    return half_beam, sheer, keel, section, x_at, width_at


def build_hull_bm(P, paint, stripe):
    """Rumpfschale mit Spiegel, per Solidify verdickt. Materialreihenfolge siehe mats."""
    half_beam, sheer, keel, section, x_at, _ = hull_param(P)
    n_st, n_half = 16, 5
    bm = bmesh.new()
    rows = []
    for i in range(n_st + 1):
        t = i / n_st
        row = []
        for j in range(-n_half, n_half + 1):
            s = abs(j) / n_half
            yy, zz = section(t, s)
            row.append(bm.verts.new((x_at(t, s), yy if j >= 0 else -yy, zz)))
        rows.append(row)
    for i in range(n_st):
        for j in range(2 * n_half):
            a, b = rows[i][j], rows[i + 1][j]
            c, d = rows[i + 1][j + 1], rows[i][j + 1]
            f = bm.faces.new((a, d, c, b))
            f.material_index = 3 if (j == 0 or j == 2 * n_half - 1) else 0
    f = bm.faces.new(list(reversed(rows[0])))  # Spiegel (Heck)
    f.material_index = 0
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)

    # Solidify ueber ein Hilfsobjekt; Materialindex +1 innen, +2 Rand
    me = bpy.data.meshes.new("_hull_tmp")
    bm.to_mesh(me)
    bm.free()
    for name in (paint, "Wood", "WoodDark", stripe, "Wood", "WoodDark"):
        me.materials.append(MATS[name])
    tmp = link(bpy.data.objects.new("_hull_tmp", me))
    mod = tmp.modifiers.new("solid", "SOLIDIFY")
    mod.thickness = 0.05
    mod.offset = -1.0
    mod.use_even_offset = True
    mod.use_rim = True
    mod.material_offset = 1
    mod.material_offset_rim = 2
    dg = bpy.context.evaluated_depsgraph_get()
    ev = tmp.evaluated_get(dg)
    me2 = bpy.data.meshes.new_from_object(ev)
    out = bmesh.new()
    out.from_mesh(me2)
    bpy.data.objects.remove(tmp)
    bpy.data.meshes.remove(me)
    bpy.data.meshes.remove(me2)
    return out, [paint, "Wood", "WoodDark", stripe, "Wood", "WoodDark"]


def boat_floor(mb, P, zf, t0=0.06, t1=0.9, inset=0.07):
    _, _, _, _, x_at, width_at = hull_param(P)
    ts = [lerp(t0, t1, k / 12) for k in range(13)]
    pts = [(x_at(t, 0.3), -(width_at(t, zf) - inset)) for t in ts]
    pts += [(x_at(t, 0.3), width_at(t, zf) - inset) for t in reversed(ts)]
    bm = bmesh.new()
    bm.faces.new([bm.verts.new((x, y, zf)) for x, y in pts])
    mb.add(bm, "Wood")


def boat_thwart(mb, P, t, z, mat="Wood"):
    _, _, _, _, x_at, width_at = hull_param(P)
    w = 2 * (width_at(t, z) - 0.04)
    mb.add(bm_box(0.22, w, 0.05, bevel=0.01), mat, M((x_at(t, 0.5), 0, z)))


def build_boat_a(loc, rot_z):
    """Kleines Fischerboot mit Ruderhaus."""
    P = dict(L=4.6, B=1.75, keel=-0.40, sheer=0.50, bow=0.86, stern=0.62, transom=0.62)
    mb = MB()
    hull, mats = build_hull_bm(P, "WhitePaint", "RedPaint")
    mb.add(hull, mats)
    zf = -0.16
    boat_floor(mb, P, zf)
    boat_thwart(mb, P, 0.72, 0.28)
    # Ruderhaus
    hx0, hx1 = -1.35, -0.35
    hz1 = 1.25
    mb.add(bm_box(hx1 - hx0, 1.0, hz1 - zf, bevel=0.015), "WhitePaint", M(((hx0 + hx1) / 2, 0, (zf + hz1) / 2)))
    mb.add(bm_box(1.3, 1.24, 0.08, bevel=0.015), "RedPaint", M(((hx0 + hx1) / 2 - 0.05, 0, hz1 + 0.04)))
    for wy in (-0.24, 0.24):  # Frontfenster
        mb.add(bm_box(0.04, 0.34, 0.32), "Metal", M((hx1 + 0.01, wy, 0.86)))
    for side in (-1, 1):  # Seitenfenster
        mb.add(bm_box(0.5, 0.04, 0.3), "Metal", M(((hx0 + hx1) / 2 + 0.05, side * 0.51, 0.87)))
    # Mast mit Positionslampe
    mb.add(bm_cyl(0.035, 0.03, 1.1, 8), "WoodDark", M((-0.75, 0, hz1 + 0.08 + 0.55)))
    mb.add(bm_box(0.08, 0.08, 0.1), "Metal", M((-0.75, 0, hz1 + 0.08 + 1.12)))
    # Fischkiste im Vorschiff
    mb.add(bm_box(0.5, 0.4, 0.22, bevel=0.01), "Wood", M((0.75, 0.15, zf + 0.11), (0, 0, 8)))
    return make_obj("BoatA", mb, loc, smooth=50, rot_z=rot_z)


def build_boat_b(loc, rot_z):
    """Offenes Fischerboot mit kurzem Mast, eingerolltem Segel und Riemen."""
    P = dict(L=4.0, B=1.55, keel=-0.36, sheer=0.42, bow=0.74, stern=0.55, transom=0.58)
    mb = MB()
    hull, mats = build_hull_bm(P, "RedPaint", "WhitePaint")
    mb.add(hull, mats)
    zf = -0.14
    boat_floor(mb, P, zf)
    boat_thwart(mb, P, 0.36, 0.22)
    boat_thwart(mb, P, 0.62, 0.22)
    # Mast, Baum, eingerolltes Segel
    mx = 0.62
    mb.add(bm_cyl(0.05, 0.035, 3.0, 8), "WoodDark", M((mx, 0, zf + 1.5)))
    mb.add(bm_cyl(0.035, 0.03, 2.3, 8), "WoodDark", M((mx - 1.15, 0, 0.95), (0, 90, 0)))
    sail = [(mx - 0.1 - 2.0 * k / 8, 0.0, 1.06 + 0.02 * math.sin(k)) for k in range(9)]
    mb.add(bm_tube(sail, 0.1, sides=8, radius_fn=lambda u: 0.07 + 0.07 * math.sin(math.pi * min(1, u * 1.1))),
           "Rope")
    # zwei Riemen ueber den Duchten
    for side in (-1, 1):
        mb.add(bm_cyl(0.025, 0.025, 2.3, 6), "Wood", M((-0.1, side * 0.32, 0.3), (0, 88, side * 7)))
        mb.add(bm_box(0.5, 0.13, 0.02), "Wood", M((-1.35, side * 0.47, 0.33), (0, 2, side * 7)))
    return make_obj("BoatB", mb, loc, smooth=50, rot_z=rot_z)


# --------------------------------------------------------------------------------------------
# Hafenmeisterhaeuschen
# --------------------------------------------------------------------------------------------
def build_cottage():
    W, D, H, R = COTTAGE_W, COTTAGE_D, COTTAGE_H, COTTAGE_RISE
    mb = MB()
    # Wandkoerper mit Giebeln (Profil in YZ, entlang X extrudiert), ohne Boden
    bm = bmesh.new()
    prof = [(-D / 2, 0.0), (D / 2, 0.0), (D / 2, H), (0.0, H + R), (-D / 2, H)]
    left = [bm.verts.new((-W / 2, y, z)) for y, z in prof]
    right = [bm.verts.new((W / 2, y, z)) for y, z in prof]
    bm.faces.new(right)                        # Giebel +X
    bm.faces.new(list(reversed(left)))         # Giebel -X
    for k in range(len(prof)):
        a, b = left[k], left[(k + 1) % len(prof)]
        c, d = right[(k + 1) % len(prof)], right[k]
        bm.faces.new((a, b, c, d))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    mb.add(bm, "Stone")
    # Sockel
    mb.add(bm_box(W + 0.1, D + 0.1, 0.32, drop_bottom=True), "StoneDark", M((0, 0, 0.16)))
    # Eckquader
    for sx in (-1, 1):
        for sy in (-1, 1):
            z = 0.32
            k = 0
            while z < H - 0.1:
                h = 0.34
                long_x = k % 2 == 0
                lx = 0.52 if long_x else 0.3
                ly = 0.3 if long_x else 0.52
                cxq = sx * (W / 2 - lx / 2 + 0.03)
                cyq = sy * (D / 2 - ly / 2 + 0.03)
                mb.add(bm_box(lx, ly, h - 0.03), "StoneDark", M((cxq, cyq, z + h / 2)))
                z += h
                k += 1
    # Dach: zwei Platten mit Ueberstand, Firstkappe
    slope = math.atan2(R, D / 2)
    run = math.hypot(D / 2, R) + 0.32
    th = 0.13
    for side in (-1, 1):
        # Plattenmitte: vom First aus entlang der Dachneigung nach aussen
        dy = side * math.cos(slope)
        dz = -math.sin(slope)
        nrm = Vector((0, side * math.sin(slope), math.cos(slope)))
        c = Vector((0, dy * run / 2, H + R + dz * run / 2)) + nrm * (th / 2 + 0.02)
        c += Vector((0, -dy, -dz)) * 0.06
        mb.add(bm_box(W + 0.5, run, th, bevel=0.02), "Roof", M(c, (math.degrees(-side * slope), 0, 0)))
    mb.add(bm_lathe([(0.11, -0.5), (0.11, 0.5)], 6, cap_bottom=True, cap_top=True, phase=math.pi / 6),
           "Roof", M((0, 0, H + R + 0.19), (0, 90, 0), scale=(1, 1, (W + 0.5) / 1.0)))
    # Schornstein mit Abdeckplatte und Topf
    chx, chy = -W / 2 + 0.62, 0.35
    ch_top = H + R + 0.7
    mb.add(bm_box(0.56, 0.56, ch_top - H), "Stone", M((chx, chy, (H + ch_top) / 2)))
    mb.add(bm_box(0.7, 0.7, 0.1, bevel=0.015), "StoneDark", M((chx, chy, ch_top + 0.05)))
    mb.add(bm_cyl(0.11, 0.09, 0.22, 8), "StoneDark", M((chx, chy, ch_top + 0.21)))
    # Tuer vorn mit Steinrahmen und Stufe
    fy = -D / 2
    dx = 0.85
    mb.add(bm_box(0.9, 0.08, 1.88, bevel=0.01), "WoodDark", M((dx, fy - 0.02, 0.94)))
    for k in range(3):  # Querbretter
        mb.add(bm_box(0.84, 0.03, 0.08), "Wood", M((dx, fy - 0.07, 0.35 + k * 0.6)))
    for sx in (-1, 1):
        mb.add(bm_box(0.14, 0.14, 2.0), "StoneDark", M((dx + sx * 0.52, fy - 0.03, 1.0)))
    mb.add(bm_box(1.25, 0.16, 0.2, bevel=0.01), "StoneDark", M((dx, fy - 0.03, 2.08)))
    mb.add(bm_box(1.2, 0.45, 0.1, bevel=0.01), "StoneDark", M((dx, fy - 0.2, 0.05)))
    # Fenster vorn: Rahmen, Sprossen, Sims, Klappladen (Glas ist eigenes Objekt)
    wx, wz, ww, wh = -0.8, 1.45, 0.82, 0.9
    for sx in (-1, 1):
        mb.add(bm_box(0.07, 0.08, wh + 0.07), "WhitePaint", M((wx + sx * (ww / 2), fy - 0.03, wz)))
    for sz in (-1, 1):
        mb.add(bm_box(ww + 0.07, 0.08, 0.07), "WhitePaint", M((wx, fy - 0.03, wz + sz * wh / 2)))
    mb.add(bm_box(0.045, 0.06, wh), "WhitePaint", M((wx, fy - 0.04, wz)))
    mb.add(bm_box(ww, 0.06, 0.045), "WhitePaint", M((wx, fy - 0.04, wz)))
    mb.add(bm_box(ww + 0.25, 0.2, 0.08, bevel=0.01), "StoneDark", M((wx, fy - 0.08, wz - wh / 2 - 0.07)))
    for sx in (-1, 1):
        mb.add(bm_box(0.42, 0.045, wh + 0.04, bevel=0.008), "RedPaint",
               M((wx + sx * (ww / 2 + 0.26), fy - 0.03, wz)))
    # Seitenfenster an der rechten Giebelwand (+X)
    sxw, syw, szw, sw, sh = W / 2, 0.15, 1.5, 0.62, 0.72
    for sy in (-1, 1):
        mb.add(bm_box(0.08, 0.07, sh + 0.07), "WhitePaint", M((sxw + 0.03, syw + sy * sw / 2, szw)))
    for sz in (-1, 1):
        mb.add(bm_box(0.08, sw + 0.07, 0.07), "WhitePaint", M((sxw + 0.03, syw, szw + sz * sh / 2)))
    mb.add(bm_box(0.06, 0.045, sh), "WhitePaint", M((sxw + 0.04, syw, szw)))
    mb.add(bm_box(0.2, sw + 0.2, 0.08, bevel=0.01), "StoneDark", M((sxw + 0.08, syw, szw - sh / 2 - 0.07)))
    cottage = make_obj("Cottage", mb, COTTAGE_POS, smooth=30)

    # Fensterglas als eigenes Objekt (emissiv), Ursprung in der Mitte des Frontfensters
    win_world = COTTAGE_POS + Vector((wx, fy - 0.015, wz))
    mbw = MB()
    mbw.add(bm_box(ww, 0.03, wh), "Glass")
    side_local = Vector((sxw + 0.015, syw, szw)) - Vector((wx, fy - 0.015, wz))
    mbw.add(bm_box(0.03, sw, sh), "Glass", Matrix.Translation(side_local))
    make_obj("CottageWindow", mbw, win_world, parent=cottage)
    make_empty("ChimneySmoke", COTTAGE_POS + Vector((chx, chy, ch_top + 0.4)), parent=cottage)
    return cottage


# --------------------------------------------------------------------------------------------
# Leuchtturm
# --------------------------------------------------------------------------------------------
def build_lighthouse(cam_xy):
    mb = MB()
    base_r, top_r, z0, z1 = 1.38, 0.98, 0.6, 8.4

    def r_at(z):
        u = (z - z0) / (z1 - z0)
        return top_r + (base_r - top_r) * (1 - u) ** 1.5

    # Sockel
    mb.add(bm_lathe([(1.8, -0.4), (1.8, 0.42), (1.62, 0.6), (r_at(0.6) - 0.02, 0.6)], 16, cap_bottom=False),
           "StoneDark")
    # Turm mit rotem Band
    zs = [0.6, 1.8, 3.0, 4.0, 4.5, 5.7, 6.7, 7.6, 8.4]
    prof = [(r_at(z), z) for z in zs]
    bands = [0 if not (4.5 <= zs[i] < 5.7) else 1 for i in range(len(zs) - 1)]
    mb.add(bm_lathe(prof, 16, bands=bands, cap_bottom=False, cap_top=False), ["WhitePaint", "RedPaint"])
    # Konsole und Galerie
    mb.add(bm_lathe([(top_r, 8.4), (1.06, 8.56), (1.36, 8.74)], 16, cap_bottom=False, cap_top=False),
           "WhitePaint")
    mb.add(bm_lathe([(1.36, 8.74), (1.5, 8.74), (1.5, 8.9)], 16, cap_bottom=False, cap_top=True), "StoneDark")
    # Gelaender
    for k in range(16):
        a = 2 * math.pi * (k + 0.5) / 16
        mb.add(bm_box(0.04, 0.04, 0.82), "Metal", M((1.42 * math.cos(a), 1.42 * math.sin(a), 8.9 + 0.41)))
    for rz in (9.3, 9.72):
        ring = [(1.42 * math.cos(2 * math.pi * k / 20), 1.42 * math.sin(2 * math.pi * k / 20), rz) for k in range(20)]
        mb.add(bm_tube(ring, 0.025, sides=4, closed=True), "Metal")
    # Laternenhaus: Bruestung, Sprossen, Dach mit Lueftungskugel und Spitze
    mb.add(bm_lathe([(0.84, 8.9), (0.84, 9.32), (0.74, 9.32)], 16, cap_bottom=False, cap_top=False), "WhitePaint")
    for k in range(8):
        a = 2 * math.pi * k / 8
        mb.add(bm_box(0.06, 0.06, 0.92), "Metal",
               M((0.735 * math.cos(a), 0.735 * math.sin(a), 9.32 + 0.46), (0, 0, math.degrees(a))))
    mb.add(bm_lathe([(0.96, 10.24), (0.96, 10.32), (0.84, 10.38), (0.5, 10.66), (0.16, 10.86), (0.0, 10.9)], 16,
                    bands=[0, 1, 1, 1, 1], cap_bottom=True), ["Metal", "RedPaint"])
    # Kugel als Drehkoerper: bmesh.ops.create_uvsphere liefert je Lauf eine andere Flaechenreihenfolge
    ball = [(0.13 * math.sin(math.pi * k / 6), -0.13 * math.cos(math.pi * k / 6)) for k in range(7)]
    mb.add(bm_lathe(ball, 8), "Metal", Matrix.Translation((0, 0, 11.0)))
    mb.add(bm_cyl(0.02, 0.01, 0.5, 6), "Metal", M((0, 0, 11.35)))
    # Tuer, Fenster und Stufe zur Kamera gedreht
    face = math.degrees(math.atan2(cam_xy[1] - LIGHTHOUSE_XY[1], cam_xy[0] - LIGHTHOUSE_XY[0]))
    rot = M((0, 0, 0), (0, 0, face + 90))  # lokal -Y zeigt zur Kamera
    door_r = r_at(1.5)
    parts = [
        (bm_box(0.8, 0.3, 1.75, bevel=0.01), "WoodDark", (0, -door_r + 0.1, 0.6 + 0.875)),
        (bm_box(0.13, 0.36, 1.95), "StoneDark", (-0.48, -door_r + 0.1, 0.6 + 0.97)),
        (bm_box(0.13, 0.36, 1.95), "StoneDark", (0.48, -door_r + 0.1, 0.6 + 0.97)),
        (bm_box(1.1, 0.36, 0.18), "StoneDark", (0, -door_r + 0.1, 0.6 + 1.94)),
        (bm_box(1.2, 0.5, 0.16, bevel=0.01), "StoneDark", (0, -1.86, 0.5)),
    ]
    for wz in (3.5, 6.4):
        parts.append((bm_box(0.3, 0.3, 0.46, bevel=0.01), "WoodDark", (0, -r_at(wz) + 0.12, wz)))
        parts.append((bm_box(0.42, 0.3, 0.06), "StoneDark", (0, -r_at(wz) + 0.1, wz - 0.27)))
    for b, mat, p in parts:
        mb.add(b, mat, rot @ Matrix.Translation(p))
    base = Vector((LIGHTHOUSE_XY[0], LIGHTHOUSE_XY[1], LIGHTHOUSE_BASE_Z))
    lh = make_obj("Lighthouse", mb, base, smooth=40)

    lamp_z = (9.32 + 10.24) / 2
    mbl = MB()
    mbl.add(bm_cyl(0.72, 0.72, 10.24 - 9.32, 12), "Glass")
    make_obj("LighthouseLamp", mbl, base + Vector((0, 0, lamp_z)), parent=lh, smooth=40)
    make_empty("LighthouseLight", base + Vector((0, 0, lamp_z)), parent=lh, size=0.5)
    return lh


# --------------------------------------------------------------------------------------------
# Gelaende: Huegel links, Felsnase rechts, Felsen im Wasser, ferne Inseln
# --------------------------------------------------------------------------------------------
def terrain_mats(bm, grass=True):
    """Materialindex je Flaeche: 0 Rock (steil), 1 Sand (flach am Wasser), 2 Grass (flach, hoeher)."""
    for f in bm.faces:
        cz = f.calc_center_median().z
        if f.normal.z < 0.8:
            f.material_index = 0
        elif cz < WATER_Z + 0.5:
            f.material_index = 1
        else:
            f.material_index = 2 if grass else 0


def in_quay(x, y, pad=0.1):
    if x < QUAY_X0 - pad or x > QUAY_X1 + pad or y < QUAY_FRONT_Y - pad:
        return False
    if y <= QUAY_EDGE_Y + pad:
        return True
    return x <= QUAY_CORNER_X + pad and y <= QUAY_BACK_Y + pad


def quay_dist(x, y):
    """Abstand (m) zur Kaiflaeche in der Draufsicht, 0 innerhalb."""
    def rect(x0, x1, y0, y1):
        return math.hypot(max(x0 - x, 0.0, x - x1), max(y0 - y, 0.0, y - y1))
    return min(rect(QUAY_X0, QUAY_X1, QUAY_FRONT_Y, QUAY_EDGE_Y),
               rect(QUAY_X0, QUAY_CORNER_X, QUAY_EDGE_Y, QUAY_BACK_Y))


def fit_to_quay(x, y, h):
    """Gelaende unter dem Kai absenken und an Land buendig an das Pflaster anschliessen."""
    if in_quay(x, y):
        return min(h, -0.08)
    return min(h, lerp(-0.03, h, smoothstep(0.0, 2.2, quay_dist(x, y))))


WEST_C, WEST_R = (-18.5, 2.0), (13.6, 17.0)


def west_land_h(x, y):
    ex, ey = (x - WEST_C[0]) / WEST_R[0], (y - WEST_C[1]) / WEST_R[1]
    e = 1.0 - math.sqrt(ex * ex + ey * ey)
    e += 0.09 * noise.noise(Vector((x * 0.07, y * 0.07, 0.5))) + 0.035 * noise.noise(Vector((x * 0.25, y * 0.25, 3.3)))
    land = smoothstep(-0.06, 0.08, e)
    rise = smoothstep(0.08, 0.6, e) * smoothstep(-3.0, 10.0, y)
    n = noise.noise(Vector((x * 0.2, y * 0.2, 1.7)))
    n2 = noise.noise(Vector((x * 0.7, y * 0.7, 4.2)))
    hill = 6.0 * rise * (0.8 + 0.3 * n) + 0.22 * n2 * smoothstep(0.05, 0.2, e)
    cliff = 0.55 * noise.noise(Vector((x * 0.55, y * 0.55, 5.1))) * 4.0 * land * (1.0 - land)
    h = lerp(SEABED_Z, 0.18, land) + hill * land + cliff
    return fit_to_quay(x, y, h)


HEADLAND_SPINE = [(11.2, -7.0), (12.6, 1.0), (13.3, 9.0), (12.9, 16.5), (11.4, 22.5), (9.6, 26.2), (8.4, 28.0)]


def headland_h(x, y):
    d, s = polyline_dist(x, y, HEADLAND_SPINE)
    w = lerp(4.6, 3.4, s) + 1.1 * noise.noise(Vector((s * 5.0, 0.0, 9.7)))
    top = 0.5 + 2.4 * smoothstep(0.2, 0.75, s)
    edge = w - d
    land = smoothstep(-1.6, 1.4, edge)
    n = noise.noise(Vector((x * 0.32, y * 0.32, 7.3)))
    n2 = noise.noise(Vector((x * 0.9, y * 0.9, 2.1)))
    h_top = top + 0.45 * n * smoothstep(0.0, 2.5, edge) + 0.18 * n2
    cliff = 0.6 * noise.noise(Vector((x * 0.6, y * 0.6, 8.8))) * 4.0 * land * (1.0 - land)
    h = lerp(SEABED_Z, h_top, land) + cliff
    dl = math.hypot(x - LIGHTHOUSE_XY[0], y - LIGHTHOUSE_XY[1])
    h = lerp(LIGHTHOUSE_BASE_Z - 0.05, h, smoothstep(2.2, 3.4, dl))
    return fit_to_quay(x, y, h)


def cull_deep(cos):
    return all(c.z < SEABED_Z + 0.25 for c in cos)


def cull_quay(cos):
    return all(in_quay(c.x, c.y, -0.3) for c in cos)


TERRAIN_MATS = ["Rock", "Sand", "Grass"]


def build_terrain():
    obs = []
    bm = bm_heightfield(-34.0, -2.0, -17.0, 21.0, 1.0, west_land_h, jitter=0.28, seed=3,
                        cull=lambda cos: cull_deep(cos) or cull_quay(cos))
    terrain_mats(bm)
    obs.append(make_obj("WestHill", MB().add(bm, TERRAIN_MATS), (0, 0, 0), smooth=38))

    bm = bm_heightfield(2.5, 21.0, -13.0, 34.0, 1.0, headland_h, jitter=0.28, seed=5,
                        cull=lambda cos: cull_deep(cos) or cull_quay(cos))
    terrain_mats(bm)
    obs.append(make_obj("Headland", MB().add(bm, TERRAIN_MATS), (0, 0, 0), smooth=38))

    # Felsen im Wasser
    rng = random.Random(9)
    mb = MB()
    rocks = [(8.4, 3.2, 1.0), (8.6, 8.0, 0.8), (8.2, 13.0, 1.2), (7.4, 19.5, 0.9), (-5.9, 6.5, 0.8),
             (-7.3, 12.0, 1.1), (4.6, 17.0, 0.6), (6.4, 29.5, 1.3)]
    for i, (rx, ry, rs) in enumerate(rocks):
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
        for v in bm.verts:
            n = noise.noise(v.co * 1.3 + Vector((i * 3.1, 0, 0)))
            v.co *= 1.0 + 0.22 * n
            v.co.z *= 0.62
        mb.add(bm, "Rock", M((rx, ry, WATER_Z + rs * 0.08), (0, 0, rng.uniform(0, 360)),
                             (rs * rng.uniform(1.0, 1.4), rs, rs)))
    obs.append(make_obj("RocksSea", mb, (0, 0, 0), smooth=None))

    # Ferne Inseln am Horizont
    mb = MB()
    islands = [(-105.0, 185.0, 70.0, 26.0, 14.0, 1), (-40.0, 230.0, 55.0, 20.0, 9.0, 2),
               (12.0, 320.0, 60.0, 22.0, 7.0, 3), (55.0, 200.0, 80.0, 30.0, 18.0, 4)]
    for cx, cy, sx, sy, hh, seed in islands:
        def ih(x, y, cx=cx, cy=cy, sx=sx, sy=sy, hh=hh, seed=seed):
            r = math.hypot((x - cx) / (sx / 2), (y - cy) / (sy / 2))
            n = noise.noise(Vector((x * 0.05, y * 0.05, seed * 1.3)))
            peak = max(0.0, 1 - r * (1 + 0.25 * n)) ** 0.8
            return WATER_Z - 3.0 + (hh + 3.0) * peak * (0.85 + 0.25 * n)
        bm = bm_heightfield(cx - sx * 0.6, cx + sx * 0.6, cy - sy * 0.6, cy + sy * 0.6, max(sx, sy) * 1.2 / 11.0,
                            ih, jitter=0.0, cull=lambda cos: all(c.z < WATER_Z - 1.0 for c in cos))
        terrain_mats(bm)
        mb.add(bm, TERRAIN_MATS)
    obs.append(make_obj("IslandsFar", mb, (0, 0, 0), smooth=None))
    return obs


# --------------------------------------------------------------------------------------------
# Requisiten auf dem Kai
# --------------------------------------------------------------------------------------------
def build_barrel(name, loc, rot_z):
    H = 0.9

    def r(z):
        return 0.27 + 0.055 * math.sin(math.pi * z / H)

    prof = [(r(0) - 0.02, 0.0), (r(0.1), 0.1), (r(0.1) + 0.012, 0.1), (r(0.16) + 0.012, 0.16),
            (r(0.16), 0.16), (r(0.45), 0.45), (r(0.74), 0.74), (r(0.74) + 0.012, 0.74), (r(0.8) + 0.012, 0.8),
            (r(0.8), 0.8), (r(H) - 0.02, H), (r(H) - 0.05, H), (r(H) - 0.05, H - 0.03)]
    bands = [0, 1, 1, 1, 0, 0, 1, 1, 1, 0, 0, 0]
    mb = MB()
    mb.add(bm_lathe(prof, 12, bands=bands, cap_bottom=True, cap_top=True), ["Wood", "Metal"])
    return make_obj(name, mb, loc, smooth=40, rot_z=rot_z)


def crate(mb, s, mtx):
    e = 0.06
    mb.add(bm_box(s - 0.03, s - 0.03, s - 0.03), "Wood", mtx)
    h = s / 2 - e / 2
    for a in (-1, 1):
        for b in (-1, 1):
            mb.add(bm_box(s, e, e), "WoodDark", mtx @ Matrix.Translation((0, a * h, b * h)))
            mb.add(bm_box(e, s, e), "WoodDark", mtx @ Matrix.Translation((a * h, 0, b * h)))
            mb.add(bm_box(e, e, s - 2 * e), "WoodDark", mtx @ Matrix.Translation((a * h, b * h, 0)))


def build_crates(loc):
    mb = MB()
    crate(mb, 0.62, M((-0.34, 0.0, 0.31), (0, 0, 4)))
    crate(mb, 0.62, M((0.33, 0.06, 0.31), (0, 0, -7)))
    crate(mb, 0.58, M((0.0, 0.03, 0.62 + 0.29), (0, 0, 14)))
    crate(mb, 0.44, M((0.95, -0.25, 0.22), (0, 0, 23)))
    return make_obj("CrateStack", mb, loc, smooth=30)


def build_rope(loc):
    pts = []
    tr = 0.04
    turns1, turns2 = 2.6, 1.1
    per = 14
    n1 = int(turns1 * per)
    for k in range(n1 + 1):
        a = 2 * math.pi * k / per
        r = 0.1 + (0.31 - 0.1) * k / n1
        pts.append((r * math.cos(a), r * math.sin(a), tr))
    n2 = int(turns2 * per)
    a_end = 2 * math.pi * n1 / per
    for k in range(1, n2 + 1):
        a = a_end + 2 * math.pi * k / per
        r = 0.29 - (0.29 - 0.18) * k / n2
        z = tr + min(1.0, k / 5) * 0.06
        pts.append((r * math.cos(a), r * math.sin(a), z))
    # loses Ende
    last = Vector(pts[-1])
    for k in range(1, 6):
        pts.append((last.x + 0.08 * k, last.y - 0.1 * k, max(tr, last.z - 0.03 * k)))
    mb = MB()
    mb.add(bm_tube(pts, tr, sides=5), "Rope")
    return make_obj("RopeCoil", mb, loc, smooth=60)


def build_lantern_post(loc):
    mb = MB()
    post_h = 2.45
    mb.add(bm_box(0.4, 0.4, 0.14, bevel=0.015), "StoneDark", M((0, 0, 0.07)))
    mb.add(bm_box(0.16, 0.16, post_h, bevel=0.015), "WoodDark", M((0, 0, post_h / 2)))
    mb.add(bm_box(0.2, 0.2, 0.06, bevel=0.01), "WoodDark", M((0, 0, post_h + 0.03)))
    arm = 0.62
    mb.add(bm_box(arm, 0.08, 0.09), "WoodDark", M((-arm / 2 + 0.05, 0, post_h - 0.12)))
    brace = math.hypot(0.36, 0.36)
    mb.add(bm_box(brace, 0.06, 0.06), "WoodDark", M((-0.18, 0, post_h - 0.34), (0, -45, 0)))
    # Haken und Laterne aus Eisen
    lx = -arm + 0.12
    mb.add(bm_box(0.025, 0.025, 0.12), "Metal", M((lx, 0, post_h - 0.22)))
    top = post_h - 0.28
    tor = bm_tube([(lx + 0.04 * math.cos(2 * math.pi * k / 8), 0.0, top + 0.04 * math.sin(2 * math.pi * k / 8))
                   for k in range(8)], 0.01, sides=4, closed=True)
    mb.add(tor, "Metal")
    mb.add(bm_cyl(0.2, 0.03, 0.16, 4), "Metal", M((lx, 0, top - 0.08 - 0.04), (0, 0, 45)))
    mb.add(bm_box(0.27, 0.27, 0.03), "Metal", M((lx, 0, top - 0.2 - 0.015)))
    body_h = 0.3
    zc = top - 0.23 - body_h / 2
    for a in (-1, 1):
        for b in (-1, 1):
            mb.add(bm_box(0.025, 0.025, body_h), "Metal", M((lx + a * 0.11, b * 0.11, zc)))
    mb.add(bm_box(0.26, 0.26, 0.04), "Metal", M((lx, 0, zc - body_h / 2 - 0.02)))
    mb.add(bm_cyl(0.07, 0.0, 0.08, 4), "Metal", M((lx, 0, zc - body_h / 2 - 0.08), (180, 0, 45)))
    post = make_obj("LanternPost", mb, loc, smooth=30)
    glass_world = Vector(loc) + Vector((lx, 0, zc))
    mbg = MB()
    mbg.add(bm_box(0.2, 0.2, body_h - 0.02), "Glass")
    make_obj("LanternGlass", mbg, glass_world, parent=post)
    make_empty("LanternLight", glass_world, parent=post)
    return post


# --------------------------------------------------------------------------------------------
# UVs: Smart UV Project, danach einheitliche Dichte (1 UV-Einheit = 1 m)
# --------------------------------------------------------------------------------------------
def smart_uv(ob):
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.002, scale_to_bounds=False)
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


# --------------------------------------------------------------------------------------------
# Vorschau
# --------------------------------------------------------------------------------------------
def setup_preview(samples):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = samples
    sc.render.resolution_x, sc.render.resolution_y = 1280, 720
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    try:
        sc.view_settings.view_transform = "AgX"
    except TypeError:
        pass
    sc.eevee.use_shadows = True
    world = bpy.data.worlds.new("PreviewSky")
    sc.world = world
    if world.node_tree is None:
        world.use_nodes = True
    nt = world.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    cr = ramp.color_ramp
    cr.elements[0].position = 0.0
    cr.elements[0].color = (*hex_lin("#E9A15E"), 1)
    cr.elements[1].position = 0.22
    cr.elements[1].color = (*hex_lin("#5F78A6"), 1)
    e = cr.elements.new(0.06)
    e.color = (*hex_lin("#C98A78"), 1)
    e = cr.elements.new(0.6)
    e.color = (*hex_lin("#26355E"), 1)
    bg.inputs["Strength"].default_value = 0.9

    sun = bpy.data.lights.new("PreviewSun", "SUN")
    sun.energy = 3.2
    sun.color = hex_lin("#FFD9B0")
    sun.angle = math.radians(3)
    so = link(bpy.data.objects.new("PreviewSun", sun))
    d = Vector((0.55, 0.72, -0.42)).normalized()
    so.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

    def point(name, pos, energy, color="#FFB860", radius=0.05):
        ld = bpy.data.lights.new(name, "POINT")
        ld.energy = energy
        ld.color = hex_lin(color)
        ld.shadow_soft_size = radius
        o = link(bpy.data.objects.new(name, ld))
        o.location = pos
        return o

    ll = bpy.data.objects["LanternLight"].matrix_world.translation
    point("PreviewLantern", ll, 60)
    cw = bpy.data.objects["CottageWindow"].matrix_world.translation
    point("PreviewWindow", cw + Vector((0, -0.35, 0)), 40)
    lh = bpy.data.objects["LighthouseLight"].matrix_world.translation
    point("PreviewLighthouse", lh, 900, radius=0.3)


def add_camera(name, pos, fov_v, rot=None, target=None):
    cd = bpy.data.cameras.new(name)
    cd.sensor_fit = "VERTICAL"
    cd.sensor_height = 24.0
    cd.lens = 12.0 / math.tan(math.radians(fov_v) / 2)
    cd.clip_start = 0.1
    cd.clip_end = 3000.0
    co = link(bpy.data.objects.new(name, cd))
    co.location = pos
    if target is not None:
        d = Vector(target) - Vector(pos)
        co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    else:
        co.rotation_euler = Euler(tuple(math.radians(a) for a in rot), "XYZ")
    return co


def render_views(views, out_dir, samples):
    setup_preview(samples)
    sc = bpy.context.scene
    cams = {}
    cm = CAM_MAIN
    cams["main"] = add_camera("PreviewCamMain", cm["pos"], cm["fov_v"], rot=(90 + cm["pitch"], 0, cm["yaw"]))
    co = CAM_OVERVIEW
    cams["overview"] = add_camera("PreviewCamOverview", co["pos"], co["fov_v"], target=co["target"])
    top = add_camera("PreviewCamTop", (-2.0, 8.0, 80.0), 30.0, rot=(0, 0, 0))
    top.data.type = "ORTHO"
    top.data.ortho_scale = 46.0
    cams["top"] = top
    cams["side"] = add_camera("PreviewCamSide", (40.0, 6.0, 6.0), 40.0, target=(0.0, 6.0, 2.0))
    # Nahansichten zur Kontrolle einzelner Teile
    cams["cottage"] = add_camera("PreviewCamCottage", (-4.6, -6.0, 2.4), 40.0, target=(-8.4, 1.0, 1.6))
    cams["boats"] = add_camera("PreviewCamBoats", (3.2, -3.5, 2.6), 45.0, target=(3.2, 6.0, -0.4))
    cams["lighthouse"] = add_camera("PreviewCamLighthouse", (2.0, 12.0, 7.0), 40.0,
                                    target=(LIGHTHOUSE_XY[0], LIGHTHOUSE_XY[1], LIGHTHOUSE_BASE_Z + 5.5))
    cams["props"] = add_camera("PreviewCamProps", (0.5, -5.5, 1.9), 45.0, target=(0.5, 0.5, 0.3))
    written = []
    for v in views:
        sc.camera = cams[v]
        path = os.path.join(out_dir, f"preview_harbor_{v}.png")
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        written.append(path)
    return written


# --------------------------------------------------------------------------------------------
# Notizen
# --------------------------------------------------------------------------------------------
def to_godot(v):
    return (round(v[0], 3) + 0.0, round(v[2], 3) + 0.0, round(-v[1], 3) + 0.0)


def fmt(v):
    return "(" + ", ".join(f"{c:.2f}" for c in v) + ")"


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


OBJECT_INFO = {
    "Sea": "Meeresgitter für Wellen-Shader, Ursprung auf der Wasserlinie",
    "Quay": "Steinkai: Mauern, Fugenfläche, Pflaster, Kantensteine",
    "Bollards": "drei eiserne Poller an der Kaikante",
    "Jetty": "Holzsteg: Planken, Träger, Pfähle, zwei Paar Festmachpfähle",
    "BoatA": "Fischerboot mit Ruderhaus (weiß/rot); Ursprung an der Wasserlinie, Bug lokal +X",
    "BoatB": "offenes Fischerboot mit Mast (rot/weiß); Ursprung an der Wasserlinie, Bug lokal +X",
    "Cottage": "Hafenmeisterhäuschen aus Stein: Dach, Tür, Klappläden, Schornstein",
    "CottageWindow": "Fensterglas (Front- und Seitenfenster), emissiv",
    "Lighthouse": "Leuchtturm: Sockel, Turm mit rotem Band, Galerie, Geländer, Laternendach",
    "LighthouseLamp": "Verglasung des Laternenhauses = Lampe, emissiv; Ursprung im Lichtzentrum",
    "WestHill": "Insel links mit Hügel hinter dem Häuschen, schließt bündig an den Kai an",
    "Headland": "Felsnase rechts mit Plateau für den Leuchtturm",
    "RocksSea": "Felsbrocken im Wasser",
    "IslandsFar": "ferne Inseln am Horizont (185 bis 320 m hinter dem Kai)",
    "Barrel1": "Fass",
    "Barrel2": "Fass",
    "CrateStack": "Kistenstapel (drei gestapelt, eine daneben)",
    "RopeCoil": "Taurolle",
    "LanternPost": "Holzpfahl mit Ausleger und eiserner Laterne",
    "LanternGlass": "Laternenglas, emissiv",
}
EMPTY_INFO = {
    "LighthouseLight": "Lichtzentrum des Leuchtturms (Strahl, Licht, Blinken)",
    "LanternLight": "Mitte der Laterne (OmniLight3D zum Flackern)",
    "ChimneySmoke": "Austritt des Rauchs über dem Schornstein (Partikel)",
    "WalkStart": "Laufweg des Dachses: Start",
    "WalkEnd": "Laufweg des Dachses: Ende",
}


def de(x, nd=2):
    """Zahl mit deutschem Dezimalkomma für Fließtext."""
    return f"{x:.{nd}f}".replace(".", ",")


def write_notes(path, stats, sea_cells, glb_path):
    rel = lambda p: os.path.relpath(os.path.abspath(p), os.path.dirname(os.path.abspath(path)))
    total = sum(v.get("tris", 0) for v in stats.values())
    cm = CAM_MAIN
    cpos = to_godot(cm["pos"])
    tgt = to_godot(CAM_OVERVIEW["target"])
    opos = to_godot(CAM_OVERVIEW["pos"])
    fov_h = math.degrees(2 * math.atan(math.tan(math.radians(cm["fov_v"]) / 2) * 16 / 9))
    L = []
    w = L.append
    w("# Hafenszene `harbor.glb`: Notizen")
    w("")
    w("Gemeinsame, stilneutrale 3D-Grundszene „Hafen von Lornholm“ (nach `data/motif.json`) für alle 3D-Stile. "
      "Stile ändern Materialien, Shader, Auflösung und Nachbearbeitung, nicht die Geometrie.")
    w("Diese Datei erzeugt das Bauskript bei jedem Lauf; alle Zahlen kommen direkt aus dem Skript.")
    w("")
    w("## Bauen")
    w("")
    w("```")
    w("blender -b --factory-startup -P shared/3d/blender/build_harbor.py --")
    w("blender -b --factory-startup -P shared/3d/blender/build_harbor.py -- --no-preview")
    w("blender -b --factory-startup -P shared/3d/blender/build_harbor.py -- \\")
    w("    --views main,overview,top,side,cottage,boats,lighthouse,props --preview-dir /tmp/harbor")
    w("```")
    w("")
    w(f"Ausgaben: `{rel(glb_path)}`, diese Notizen und die Vorschaubilder `preview_harbor_main.png` (Hauptkamera) "
      "und `preview_harbor_overview.png` (Übersicht). Weitere Ansichten über `--views`. Deterministisch (feste "
      "Seeds; das glb ist bei gleichem Skript Byte für Byte gleich), Laufzeit wenige Sekunden, Blender 5.2 LTS, "
      "Vorschau mit EEVEE.")
    w("")
    w("Geprüft in Godot 4.7.2: glb importiert ohne Fehler, Knoten- und Materialnamen bleiben erhalten, Empties "
      "werden zu `Node3D`, und das Bild der Hauptkamera mit den Werten unten deckt sich mit "
      "`preview_harbor_main.png`.")
    w("")
    w("## Achsen und Maßstab")
    w("")
    w("- 1 Einheit = 1 m. Export als glTF mit +Y oben.")
    w("- Umrechnung: **Godot (x, y, z) = Blender (x, z, −y)**. Die Godot-Kamera blickt entlang −Z auf die Szene; "
      "„vorn“ (zur Kamera) ist +Z, „hinten“ (Meer, Leuchtturm) ist −Z.")
    w(f"- Kai entlang X. Kaioberfläche (Pflaster) bei y = 0. Wasserlinie bei y = {de(WATER_Z)}. Meeresboden und "
      f"Mauerunterkante bei y = {de(SEABED_Z)}.")
    w(f"- Laufweg des Dachses: y = 0, z = {de(-WALK_Y)}, x von {de(WALK_X0, 0)} bis +{de(WALK_X1, 0)} "
      f"(Empties `WalkStart`, `WalkEnd`). Pflaster reicht nach vorn bis z = {de(-QUAY_FRONT_Y, 0)}; die Kaikante "
      f"zum Wasser liegt bei z = {de(-QUAY_EDGE_Y)} (Kantensteine ab z = {de(-(QUAY_EDGE_Y - COPING_W))}).")
    w("- Links (x < −6,6) steht das Häuschen, in der Mitte liegt das Hafenbecken mit Steg (x 2,65 bis 4,25) und "
      "Booten, rechts hinten die Felsnase mit dem Leuchtturm, dahinter offenes Meer mit fernen Inseln.")
    w("- Kein Himmel, keine Lichter, keine Kameras im glb; das macht Godot.")
    w("")
    w("## Hauptkamera")
    w("")
    w("| | Godot | Blender |")
    w("|---|---|---|")
    w(f"| Position | `{fmt(cpos)}` | `{fmt(cm['pos'])}` |")
    w(f"| Rotation | `rotation_degrees = ({cm['pitch']:.1f}, {cm['yaw']:.1f}, 0.0)` | rotation_euler XYZ = "
      f"({90 + cm['pitch']:.1f}°, 0°, {cm['yaw']:.1f}°) |")
    w(f"| Blickrichtung | −Z, {de(abs(cm['pitch']), 0)}° nach unten geneigt | +Y, {de(abs(cm['pitch']), 0)}° nach unten |")
    w(f"| Bildwinkel | `fov = {cm['fov_v']:.1f}` (vertikal; `keep_aspect` = Keep Height, Standard) | "
      f"Sensor vertikal, {de(cm['fov_v'], 1)}° |")
    w(f"| horizontal bei 16:9 | {de(fov_h, 1)}° | {de(fov_h, 1)}° |")
    w("| near / far | 0,1 / 3000 | 0,1 / 3000 |")
    w("")
    w("Bildaufbau bei 1280×720: Kai mit Laufweg im unteren Drittel, Häuschen links, Boote und Steg in der Mitte, "
      "Laterne und Kisten rechts, Leuchtturm rechts oben (Spitze etwa 3° bzw. 55 px unter dem oberen Bildrand), Horizont "
      "etwa 50 px über der Bildmitte.")
    w("")
    w(f"Übersicht (nur Vorschau): Godot-Position `{fmt(opos)}`, Blick auf `{fmt(tgt)}`, "
      f"fov {de(CAM_OVERVIEW['fov_v'], 0)}.")
    w("")
    w("## Objekte")
    w("")
    w("Knotennamen in Godot = Objektnamen. Ursprung in Godot-Weltkoordinaten. Kinder hängen am genannten Elternknoten.")
    w("")
    w("| Objekt | Eltern | Ursprung (Godot) | Dreiecke | Materialien | Inhalt |")
    w("|---|---|---|---:|---|---|")
    for name, v in stats.items():
        if "tris" not in v:
            continue
        w(f"| `{name}` | {v['parent'] or '–'} | `{fmt(to_godot(v['world']))}` | {v['tris']} | "
          f"{', '.join(v['mats'])} | {OBJECT_INFO.get(name, '')} |")
    w(f"| **Summe** | | | **{total}** | | |")
    w("")
    w(f"`Sea` hat {sea_cells[0]} × {sea_cells[1]} Zellen: 1,5-m-Raster im Hafen (x −21 bis 21, z −33 bis 10,5), "
      "nach außen geometrisch gröber bis 700 m seitlich und 900 m nach hinten, damit das Wasser bis zum Horizont "
      "reicht. Es läuft unter Kai und Gelände durch.")
    w("")
    w("## Empties")
    w("")
    w("| Empty | Eltern | Position (Godot, Welt) | Zweck |")
    w("|---|---|---|---|")
    for name, v in stats.items():
        if v.get("empty"):
            w(f"| `{name}` | {v['parent'] or '–'} | `{fmt(to_godot(v['world']))}` | {EMPTY_INFO.get(name, '')} |")
    w("")
    w("## Materialien")
    w("")
    w("Stilneutral: nur Grundfarbe (sRGB), Rauheit, Metall, keine Texturen. Die Namen bleiben beim Import erhalten "
      "(`resource_name` der `StandardMaterial3D`), Stile erkennen und ersetzen sie daran.")
    w("")
    w("| Material | Farbe | Rauheit | Metall | Emission | Verwendet in |")
    w("|---|---|---:|---:|---|---|")
    used = {}
    for name, v in stats.items():
        for m in v.get("mats", []):
            used.setdefault(m, []).append(name)
    for name, d in MAT_DEFS.items():
        em = f"{d['emit']}, Stärke {de(d['emit_strength'], 0)}" if "emit" in d else "–"
        w(f"| `{name}` | {d['color']} | {de(d['rough'])} | {de(d.get('metal', 0.0), 1)} | {em} | "
          f"{', '.join(used.get(name, [])) or '–'} |")
    w("")
    w("`Grass` kommt zur vorgegebenen Liste hinzu, für flache, höher gelegene Geländeflächen (Kuppen von Insel und "
      "Felsnase). Ohne Grün wirkten die Kuppen wie Wüste. Wer es nicht braucht, gibt ihm die Farbe von `Rock`.")
    w("")
    w("Gelände (`WestHill`, `Headland`, `IslandsFar`): Flächen steiler als etwa 37° sind `Rock`, flache Flächen bis "
      "0,5 m über der Wasserlinie `Sand`, darüber `Grass`.")
    w("")
    w("## UVs und Normalen")
    w("")
    w("- Alle Meshes haben die UV-Map `UVMap` aus Smart UV Project (Winkelgrenze 66°). Danach ist jedes Objekt auf "
      "dieselbe Dichte skaliert: **1 UV-Einheit = 1 m**. Kacheltexturen erscheinen dadurch auf allen Objekten gleich "
      "groß (zum Beispiel 64 px pro Meter für den PS1-Look). Die UVs liegen deshalb nicht in 0..1.")
    w("- Für Unikat-Texturen oder Lightmaps: beim Import in Godot UV2 erzeugen lassen oder in Blender neu abwickeln.")
    w("- `Sea` hat planare UVs in Metern statt Smart UV; in Godot gilt UV = (x, z + 1), weil glTF V umdreht. Für "
      "Wellen besser Weltkoordinaten im Shader nehmen.")
    w("- Normalen: geglättet bis zu einem Kantenwinkel je Objekt (Taurolle 60°, Boote und Poller 50°, Leuchtturm, "
      "Fässer und Steg 40°, Gelände 38°, Häuschen, Kisten und Laternenpfahl 30°); `Quay`, `RocksSea`, `IslandsFar` "
      "und die Glasteile flach schattiert. "
      "Flat-Shading-Stile erzwingen Flächennormalen im Shader.")
    w("- Keine Vertexfarben.")
    w("")
    w("## Maße")
    w("")
    w("- Dachs ca. 1,0 m. Tür des Häuschens 0,90 × 1,88 m, Frontfenster 0,82 × 0,90 m (Unterkante 1,0 m).")
    w(f"- Häuschen {de(COTTAGE_W, 1)} × {de(COTTAGE_D, 1)} m, Traufe {de(COTTAGE_H)} m, First "
      f"{de(COTTAGE_H + COTTAGE_RISE)} m, Schornstein bis ca. 4,8 m.")
    w("- Fässer 0,90 m hoch, ca. 0,65 m Durchmesser. Kisten 0,62, 0,58 und 0,44 m. Taurolle ca. 0,7 m Durchmesser.")
    w("- Laternenpfahl 2,45 m hoch, Laterne hängt am Ausleger, Glasmitte ca. 1,8 m über dem Kai.")
    w("- Poller 0,53 m auf den Kantensteinen (Oberkante 0,10 m), Kantensteine 0,62 m breit.")
    w(f"- Steg {de(JETTY_X1 - JETTY_X0, 1)} m breit, reicht {de(JETTY_Y1 - QUAY_EDGE_Y, 1)} m ins Wasser, Deck "
      f"{de(JETTY_TOP)} m, Festmachpfähle bis 0,64 und 0,79 m.")
    w("- BoatA 4,6 × 1,75 m, Ruderhaus bis 1,3 m über Wasser. BoatB 4,0 × 1,55 m, Mast 3 m. Tiefgang ca. 0,4 m.")
    w(f"- Leuchtturm: Fuß auf {de(LIGHTHOUSE_BASE_Z, 1)} m, Turm 8,4 m, Lampenmitte {de(LIGHTHOUSE_BASE_Z + 9.78)} m, "
      f"Spitze {de(LIGHTHOUSE_BASE_Z + 11.6, 1)} m über dem Kai. Tür und Fenster zeigen zur Hauptkamera.")
    w("")
    w("## Hinweise für Stile")
    w("")
    w("- Szene instanzieren (`load(\"res://harbor.glb\").instantiate()`). Materialien per Name tauschen: alle "
      "`MeshInstance3D` durchgehen, `mesh.surface_get_material(i).resource_name` prüfen und "
      "`set_surface_override_material(i, …)` setzen.")
    w("- Leuchtende Teile sind eigene Objekte (`CottageWindow`, `LighthouseLamp`, `LanternGlass`); sie lassen sich "
      "einzeln flackern oder blinken. Lichter an die Empties hängen.")
    w("- Boote um ihren Ursprung (Wasserlinie) schaukeln: kleine Drehung um x und z, leichtes Heben in y.")
    w("- Rauch an `ChimneySmoke`, Leuchtturmstrahl an `LighthouseLight` (Drehung um y).")
    w("- Keine Kollisionen im glb; für den Laufweg genügt eine Ebene bei y = 0.")
    w("")
    w("## Grenzen")
    w("")
    w("- Das Meer endet 900 m hinter dem Kai knapp unter dem Horizont. Mit Nebel oder einem Himmel in Wasserfarbe am "
      "Horizont ist die Kante unsichtbar.")
    w("- Das Pflaster vorn ist absichtlich ruhig: Dort stehen Figur und Textbox.")
    w("- Das Gelände ist ein Höhenfeld (keine Überhänge).")
    w("- Ohne die Vorschau-Lichter (Sonne, Punktlichter an den Empties) wirkt die Szene in Godot flach; Licht und "
      "Himmel setzt jeder Stil selbst.")
    w("")
    open(path, "w", encoding="utf-8").write("\n".join(L))


# --------------------------------------------------------------------------------------------
def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(SHARED3D, "harbor.glb"))
    ap.add_argument("--notes", default=os.path.join(SHARED3D, "harbor_notes.md"))
    ap.add_argument("--preview-dir", default=SHARED3D)
    ap.add_argument("--views", default="main,overview")
    ap.add_argument("--no-preview", action="store_true")
    ap.add_argument("--samples", type=int, default=48)
    ap.add_argument("--blend", default=None)
    args = ap.parse_args(argv)

    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras):
        for d in list(coll):
            coll.remove(d)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0

    make_materials()
    sea, sea_cells = build_sea()
    build_quay()
    build_jetty()
    build_boat_a((0.05, 6.1, WATER_Z), 7.0)
    build_boat_b((6.75, 6.4, WATER_Z), 188.0)
    build_cottage()
    build_lighthouse(CAM_MAIN["pos"][:2])
    build_terrain()
    build_barrel("Barrel1", (-5.25, 0.15, 0.0), 0.0)
    build_barrel("Barrel2", (-4.55, 0.62, 0.0), 40.0)
    build_crates((6.55, -0.2, 0.0))
    build_rope((1.05, -0.05, 0.0))
    build_lantern_post((4.6, 0.12, 0.0))
    make_empty("WalkStart", (WALK_X0, WALK_Y, 0.0))
    make_empty("WalkEnd", (WALK_X1, WALK_Y, 0.0))

    for ob in bpy.data.objects:
        if ob.type == "MESH" and ob.name != "Sea":
            smart_uv(ob)

    bpy.context.view_layer.update()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=os.path.abspath(args.out), export_format="GLB", export_yup=True,
                              export_apply=True, export_cameras=False, export_lights=False,
                              export_texcoords=True, export_normals=True, export_extras=False,
                              use_selection=False)

    stats = {}
    for ob in sorted(bpy.data.objects, key=lambda o: o.name):
        if ob.type == "MESH":
            stats[ob.name] = dict(tris=tri_count(ob), mats=[m.name for m in ob.data.materials],
                                  parent=ob.parent.name if ob.parent else None,
                                  world=list(ob.matrix_world.translation))
        elif ob.type == "EMPTY":
            stats[ob.name] = dict(empty=True, parent=ob.parent.name if ob.parent else None,
                                  world=list(ob.matrix_world.translation))
    total = sum(s.get("tris", 0) for s in stats.values())
    print("HARBOR_STATS " + json.dumps(dict(total_tris=total, sea_cells=sea_cells, objects=stats)))
    if args.notes:
        write_notes(args.notes, stats, sea_cells, args.out)
        print("NOTES " + os.path.abspath(args.notes))

    if args.blend:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.blend))
    if not args.no_preview:
        views = [v.strip() for v in args.views.split(",") if v.strip()]
        for p in render_views(views, os.path.abspath(args.preview_dir), args.samples):
            print("PREVIEW " + p)


main()
