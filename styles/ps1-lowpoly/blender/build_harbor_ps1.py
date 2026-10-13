# PS1-Fassung des Hafens: aus shared/3d/harbor.glb eine Variante mit Konsolen-Geometrie bauen.
#
#   blender -b --factory-startup -P styles/ps1-lowpoly/blender/build_harbor_ps1.py -- \
#       shared/3d/harbor.glb styles/ps1-lowpoly/demo/models/harbor_ps1.glb [--no-ao]
#
# Objektnamen, Eltern, Empties und Lage bleiben wie im gemeinsamen glb (shared/3d wird nicht verändert).
# Geändert wird nur Geometrie, dazu kommen Vertexfarben:
#  1. Fässer, Poller, Leuchtturm und Lampenglas neu als Drehkörper mit wenigen Seiten
#     (Fass 8 Seiten, Poller 8, Leuchtturm 10). Fassdauben und Reifen stehen in einer eigenen Textur
#     (Material "BarrelSide", UV 0..1 einmal herum), das Geländer der Galerie ist ein Band mit
#     Ausschnitt-Textur (Material "Railing") statt 16 Stäben und zwei Ringen. Die Kisten sind Würfel mit
#     gemalten Brettern und Rahmen (Material "CrateSide") statt Körper plus 12 Leisten.
#  2. Kaiboden: die modellierten Pflasterplatten und die Fugenfläche fallen weg; an ihrer Stelle liegt bei
#     y = 0 ein Boden aus wenigen großen Vierecken (2,2–2,7 m, Material "Paving", UV in Metern), auf dem das
#     affine Verziehen sichtbar wird (bisher baute main.gd diesen Boden zur Laufzeit 12 mm über dem Pflaster).
#  3. Ohne Z-Puffer (die Demo sortiert nach Polygonen) gibt es kein "unter Wasser" und kein "unter dem
#     Boden": Was das Wasser oder der Kaiboden verdecken soll, würde sonst darüber gezeichnet. Deshalb wird
#     alles unter der Wasserlinie abgeschnitten (Mauern, Pfähle, Gelände, Felsen, Inseln, die Außenhaut der
#     Boote) und alles unter dem Kaiboden innerhalb des Kais entfernt (Gelände, Innenseiten der Kantensteine).
#     So bauten Entwickler der Zeit ihre Level.
#  4. Vertexfarben: Umgebungsverdeckung je Ecke (eigene Strahlen über einen BVH-Baum, feste Richtungen),
#     im Shader als vorberechnete Helligkeit je Eckpunkt auf Grundlicht und Sonne gerechnet (wie
#     vorbeleuchtete Level der Zeit).
#
# Masse und Positionen aus shared/3d/blender/build_harbor.py (nur gelesen).
import json
import math
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = argv[0], argv[1]
DO_AO = "--no-ao" not in argv

# --- Maße aus build_harbor.py (Blender-Koordinaten: Z oben, Kamera blickt nach +Y) ------------------
WATER_Z = -0.8
QUAY_X0, QUAY_X1 = -13.0, 8.0
QUAY_FRONT_Y, QUAY_EDGE_Y = -8.0, 1.0
QUAY_CORNER_X, QUAY_BACK_Y = -5.0, 3.6
MORTAR_Z = -0.05
COPING_W = 0.62
LIGHTHOUSE_XY = (10.2, 25.6)
CAM_MAIN_XY = (-1.8, -14.5)

LIGHTHOUSE_SIDES = 10
BOLLARD_SIDES = 8
BARREL_SIDES = 8
FLOOR_CELLS = [((QUAY_X0, QUAY_X1, QUAY_FRONT_Y, QUAY_EDGE_Y), (8, 4)),          # 2,63 × 2,25 m
               ((QUAY_X0, QUAY_CORNER_X, QUAY_EDGE_Y, QUAY_BACK_Y), (3, 1))]   # 2,67 × 2,60 m


def tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


# --- kleiner Baukasten mit UVs je Ecke ------------------------------------------------------------------
class MB:
    """Sammelt Flächen: Eckpunkte (lokal), Material, UV je Ecke."""

    def __init__(self):
        self.v, self.f = [], []          # f: (indices, material, uvs)

    def vert(self, co):
        self.v.append(tuple(co))
        return len(self.v) - 1

    def face(self, cos, mat, uvs):
        self.f.append(([self.vert(c) for c in cos], mat, uvs))

    def tris(self):
        return sum(len(i) - 2 for i, _, _ in self.f)


def lathe(mb, prof, seg, mats, mtx=Matrix(), bands=None, cap_bottom=True, cap_top=True, phase=0.0,
          uv="meters", r_ref=None):
    """Drehkörper aus (r, z)-Profil. uv="meters": u = Bogen bei r_ref, v = Profillänge (Meter);
    uv="unit": u = 0..1 einmal herum, v = 0..1 von unten nach oben (eigene Textur je Objekt)."""
    if r_ref is None:
        r_ref = max(r for r, _ in prof)
    s = [0.0]
    for (r0, z0), (r1, z1) in zip(prof, prof[1:]):
        s.append(s[-1] + math.hypot(r1 - r0, z1 - z0))
    z_lo, z_hi = prof[0][1], prof[-1][1]

    def P(r, z, k):
        a = 2 * math.pi * k / seg + phase
        return mtx @ Vector((r * math.cos(a), r * math.sin(a), z))

    for i in range(len(prof) - 1):
        (r0, z0), (r1, z1) = prof[i], prof[i + 1]
        mat = mats[bands[i]] if bands else mats[0]
        for k in range(seg):
            if uv == "unit":
                u0, u1 = k / seg, (k + 1) / seg
                v0, v1 = (z0 - z_lo) / (z_hi - z_lo), (z1 - z_lo) / (z_hi - z_lo)
            else:
                u0, u1 = 2 * math.pi * r_ref * k / seg, 2 * math.pi * r_ref * (k + 1) / seg
                v0, v1 = s[i], s[i + 1]
            if r1 < 1e-6:      # Spitze: Dreieck
                mb.face([P(r0, z0, k), P(r0, z0, k + 1), P(0, z1, 0)], mat,
                        [(u0, v0), (u1, v0), ((u0 + u1) / 2, v1)])
            elif r0 < 1e-6:
                mb.face([P(0, z0, 0), P(r1, z1, k + 1), P(r1, z1, k)], mat,
                        [((u0 + u1) / 2, v0), (u1, v1), (u0, v1)])
            else:
                mb.face([P(r0, z0, k), P(r0, z0, k + 1), P(r1, z1, k + 1), P(r1, z1, k)], mat,
                        [(u0, v0), (u1, v0), (u1, v1), (u0, v1)])

    def cap(r, z, mat, up):
        ks = range(seg) if up else range(seg - 1, -1, -1)
        cos = [P(r, z, k) for k in ks]
        uvs = [(r * math.cos(2 * math.pi * k / seg + phase), r * math.sin(2 * math.pi * k / seg + phase)) for k in ks]
        mb.face(cos, mat, uvs)

    if cap_bottom and prof[0][0] > 1e-6:
        cap(prof[0][0], prof[0][1], mats[bands[0]] if bands else mats[0], False)
    if cap_top and prof[-1][0] > 1e-6:
        cap(prof[-1][0], prof[-1][1], mats[bands[-1]] if bands else mats[0], True)


def box(mb, sx, sy, sz, mat, mtx=Matrix(), skip=(), unit_uv=False):
    """Quader um den Ursprung, UV je Seite planar in Metern (lokal), mit unit_uv je Seite 0..1 (eine Textur
    je Fläche, z. B. Kiste). skip: "top", "bottom"."""
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    c = [Vector((x, y, z)) for x in (-hx, hx) for y in (-hy, hy) for z in (-hz, hz)]
    # Indizes: x*4 + y*2 + z
    faces = {
        "-x": ([0, 1, 3, 2], lambda p: (p.y, p.z)), "+x": ([4, 6, 7, 5], lambda p: (p.y, p.z)),
        "-y": ([0, 4, 5, 1], lambda p: (p.x, p.z)), "+y": ([2, 3, 7, 6], lambda p: (p.x, p.z)),
        "bottom": ([0, 2, 6, 4], lambda p: (p.x, p.y)), "top": ([1, 5, 7, 3], lambda p: (p.x, p.y)),
    }
    def unit(uv, name):
        size = {"-x": (sy, sz), "+x": (sy, sz), "-y": (sx, sz), "+y": (sx, sz), "bottom": (sx, sy), "top": (sx, sy)}[name]
        return (uv[0] / size[0] + 0.5, uv[1] / size[1] + 0.5)

    for name, (idx, f) in faces.items():
        if name in skip:
            continue
        uvs = [f(c[i]) for i in idx]
        if unit_uv:
            uvs = [unit(uv, name) for uv in uvs]
        mb.face([mtx @ c[i] for i in idx], mat, uvs)


def M(loc=(0, 0, 0), rot_deg=(0, 0, 0)):
    from mathutils import Euler
    return Matrix.LocRotScale(Vector(loc), Euler(tuple(math.radians(a) for a in rot_deg), "XYZ"), None)


def material(name, like=None):
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials[like].copy()
    m.name = name
    return m


def set_mesh(ob, mb, smooth_angle=50.0):
    """Mesh-Daten eines vorhandenen Objekts ersetzen (Name, Lage, Eltern und Kinder bleiben)."""
    me = bpy.data.meshes.new(ob.name + "_ps1")
    me.from_pydata(mb.v, [], [i for i, _, _ in mb.f])
    names = []
    for _, m, _ in mb.f:
        if m not in names:
            names.append(m)
    for n in names:
        me.materials.append(bpy.data.materials[n])
    me.polygons.foreach_set("material_index", [names.index(m) for _, m, _ in mb.f])
    uvl = me.uv_layers.new(name="UVMap")
    li = 0
    for _, _, uvs in mb.f:
        for uv in uvs:
            uvl.data[li].uv = uv
            li += 1
    me.validate(clean_customdata=False)
    me.update()
    me.shade_smooth()
    me.set_sharp_from_angle(angle=math.radians(smooth_angle))
    old = ob.data
    ob.data = me
    bpy.data.meshes.remove(old)
    me.name = ob.name


# --- 1. Neue Low-Poly-Teile --------------------------------------------------------------------------
def barrel():
    """Fass 0,9 m: 8 Seiten, drei Bänder (Bauch dazwischen gerade), Deckel; Dauben und Reifen in barrel.png.
    Ohne Boden (steht auf dem Kai): 3 × 16 + 6 = 54 Dreiecke."""
    H = 0.9
    mb = MB()
    lathe(mb, [(0.255, 0.0), (0.315, 0.2), (0.315, 0.7), (0.255, H)], BARREL_SIDES, ["BarrelSide"], cap_bottom=False,
          cap_top=False, uv="unit", phase=math.pi / BARREL_SIDES)
    lathe(mb, [(0.255, H)], BARREL_SIDES, ["Wood"], cap_bottom=False, cap_top=True, phase=math.pi / BARREL_SIDES)
    return mb


def bollards():
    mb = MB()
    prof = [(0.17, 0.0), (0.12, 0.13), (0.12, 0.35), (0.19, 0.41), (0.17, 0.50), (0.0, 0.53)]
    for bx in (-3.4, 0.7, 6.3):
        lathe(mb, prof, BOLLARD_SIDES, ["Metal"], mtx=Matrix.Translation((bx, QUAY_EDGE_Y - 0.3, 0.10)),
              cap_bottom=False, phase=math.pi / BOLLARD_SIDES, r_ref=0.15)
    return mb


def crates():
    """Kistenstapel wie build_crates() in shared/3d, aber jede Kiste ein einziger Würfel ohne Boden (10 Dreiecke)
    mit einer Kistentextur je Seite (Material "CrateSide": Bretter, Rahmen und Fugen gemalt statt modelliert)."""
    mb = MB()
    for s, loc, rot in ((0.62, (-0.34, 0.0, 0.31), 4), (0.62, (0.33, 0.06, 0.31), -7), (0.58, (0.0, 0.03, 0.91), 14),
                        (0.44, (0.95, -0.25, 0.22), 23)):
        box(mb, s, s, s, "CrateSide", M(loc, (0, 0, rot)), skip=("bottom",), unit_uv=True)
    return mb


def lighthouse():
    """Wie build_lighthouse() in shared/3d, aber 10 Seiten, Turm aus 4 Ringabschnitten, Geländer als
    Ausschnitt-Textur, 5 statt 8 Sprossen, Dach aus 3 Ringen, ohne Fasen an den Kästen."""
    n = LIGHTHOUSE_SIDES
    ph = math.pi / n
    base_r, top_r, z0, z1 = 1.38, 0.98, 0.6, 8.4

    def r_at(z):
        u = (z - z0) / (z1 - z0)
        return top_r + (base_r - top_r) * (1 - u) ** 1.5

    mb = MB()
    lathe(mb, [(1.8, -0.4), (1.8, 0.42), (1.62, 0.6), (r_at(0.6) - 0.02, 0.6)], n, ["StoneDark"],
          cap_bottom=False, phase=ph)
    zs = [0.6, 2.6, 4.5, 5.7, 8.4]
    bands = [1 if 4.5 <= zs[i] < 5.7 else 0 for i in range(len(zs) - 1)]
    lathe(mb, [(r_at(z), z) for z in zs], n, ["WhitePaint", "RedPaint"], bands=bands, cap_bottom=False,
          cap_top=False, phase=ph, r_ref=1.2)
    lathe(mb, [(top_r, 8.4), (1.36, 8.74)], n, ["WhitePaint"], cap_bottom=False, cap_top=False, phase=ph)
    lathe(mb, [(1.36, 8.74), (1.5, 8.74), (1.5, 8.9)], n, ["StoneDark"], cap_bottom=False, cap_top=True, phase=ph)
    # Geländer: ein Band (je Seite eine Kachel der Ausschnitt-Textur), beidseitig sichtbar
    rr, zr0, zr1 = 1.42, 8.9, 9.72
    for k in range(n):
        a0, a1 = 2 * math.pi * k / n + ph, 2 * math.pi * (k + 1) / n + ph
        p = [Vector((rr * math.cos(a0), rr * math.sin(a0), zr0)), Vector((rr * math.cos(a1), rr * math.sin(a1), zr0)),
             Vector((rr * math.cos(a1), rr * math.sin(a1), zr1)), Vector((rr * math.cos(a0), rr * math.sin(a0), zr1))]
        mb.face(p, "Railing", [(0, 0), (1, 0), (1, 1), (0, 1)])
        mb.face(p[::-1], "Railing", [(0, 1), (1, 1), (1, 0), (0, 0)])     # Rückseite (innen)
    # Laternenhaus: Brüstung, 5 Sprossen, Dach, Kugel, Spitze
    lathe(mb, [(0.84, 8.9), (0.84, 9.32), (0.74, 9.32)], n, ["WhitePaint"], cap_bottom=False, cap_top=False,
          phase=ph)
    for k in range(5):
        a = 2 * math.pi * k / 5 + 0.3
        box(mb, 0.07, 0.07, 0.92, "Metal", M((0.74 * math.cos(a), 0.74 * math.sin(a), 9.32 + 0.46),
                                             (0, 0, math.degrees(a))), skip=("top", "bottom"))
    lathe(mb, [(0.96, 10.24), (0.96, 10.32), (0.5, 10.66), (0.0, 10.9)], n, ["Metal", "RedPaint"],
          bands=[0, 1, 1], cap_bottom=True, phase=ph)
    lathe(mb, [(0.0, 10.87), (0.13, 11.0), (0.0, 11.13)], 4, ["Metal"])
    lathe(mb, [(0.025, 11.1), (0.0, 11.6)], 4, ["Metal"], cap_bottom=False)
    # Tür, Rahmen, Stufe und zwei Fenster zur Hauptkamera gedreht (wie im Original)
    face = math.degrees(math.atan2(CAM_MAIN_XY[1] - LIGHTHOUSE_XY[1], CAM_MAIN_XY[0] - LIGHTHOUSE_XY[0]))
    rot = M((0, 0, 0), (0, 0, face + 90))
    door_r = r_at(1.5)
    parts = [((0.8, 0.3, 1.75), "WoodDark", (0, -door_r + 0.1, 0.6 + 0.875)),
             ((0.13, 0.36, 1.95), "StoneDark", (-0.48, -door_r + 0.1, 0.6 + 0.97)),
             ((0.13, 0.36, 1.95), "StoneDark", (0.48, -door_r + 0.1, 0.6 + 0.97)),
             ((1.1, 0.36, 0.18), "StoneDark", (0, -door_r + 0.1, 0.6 + 1.94)),
             ((1.2, 0.5, 0.16), "StoneDark", (0, -1.86, 0.5))]
    for wz in (3.5, 6.4):
        parts.append(((0.3, 0.3, 0.46), "WoodDark", (0, -r_at(wz) + 0.12, wz)))
        parts.append(((0.42, 0.3, 0.06), "StoneDark", (0, -r_at(wz) + 0.1, wz - 0.27)))
    for size, mat, p in parts:
        box(mb, *size, mat, rot @ Matrix.Translation(p))
    return mb


def lighthouse_lamp():
    mb = MB()
    h = 10.24 - 9.32
    lathe(mb, [(0.72, -h / 2), (0.72, h / 2)], LIGHTHOUSE_SIDES, ["Glass"], phase=math.pi / LIGHTHOUSE_SIDES)
    return mb


# --- 2./3. Schneiden ----------------------------------------------------------------------------------
def in_quay(x, y, pad=0.0):
    if x < QUAY_X0 - pad or x > QUAY_X1 + pad or y < QUAY_FRONT_Y - pad:
        return False
    if y <= QUAY_EDGE_Y + pad:
        return True
    return x <= QUAY_CORNER_X + pad and y <= QUAY_BACK_Y + pad


def edit(ob, fn):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    fn(bm, ob.matrix_world)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def crossing(bm, mw, axis, value, region=None):
    """Flächen, die die Ebene (Weltachse axis = value) schneiden, optional nur in region(x0, x1, y0, y1)."""
    out = []
    for f in bm.faces:
        cs = [mw @ v.co for v in f.verts]
        vals = [c[axis] for c in cs]
        if not (min(vals) < value - 1e-5 and max(vals) > value + 1e-5):
            continue
        if region:
            x0, x1, y0, y1 = region
            if max(c.x for c in cs) < x0 or min(c.x for c in cs) > x1 or max(c.y for c in cs) < y0 or min(c.y for c in cs) > y1:
                continue
        out.append(f)
    return out


def bisect(bm, mw, faces, co_world, no_world):
    if not faces:
        return
    inv = mw.inverted()
    co = inv @ Vector(co_world)
    no = (mw.to_3x3().transposed() @ Vector(no_world)).normalized()
    edges = {e for f in faces for e in f.edges}
    verts = {v for f in faces for v in f.verts}
    bmesh.ops.bisect_plane(bm, geom=list(verts) + list(edges) + faces, plane_co=co, plane_no=no)


def cut_below(z_world, outward_only=False, inside=None):
    """Alles unter z_world (Welt) abschneiden. outward_only: nur nach außen zeigende Flächen löschen
    (Boote: Boden und Innenwände bleiben). inside(x, y): nur Flächen über dieser Grundfläche.
    Geschnitten werden nur Flächen, die die Ebene kreuzen (und in der Grundfläche liegen)."""
    def fn(bm, mw):
        faces = crossing(bm, mw, 2, z_world)
        if inside:
            faces = [f for f in faces if inside(*(mw @ f.calc_center_median()).xy)]
        bisect(bm, mw, faces, (0, 0, z_world), (0, 0, 1))
        kill = []
        for f in bm.faces:
            c = mw @ f.calc_center_median()
            if c.z >= z_world - 1e-4:
                continue
            if inside and not inside(c.x, c.y):
                continue
            if outward_only:
                n = (mw.to_3x3() @ f.normal).normalized()
                ref = mw @ Vector((0, 0, 0.3))
                if n.dot(c - ref) <= 0:
                    continue
            kill.append(f)
        bmesh.ops.delete(bm, geom=kill, context="FACES")
        loose = [v for v in bm.verts if not v.link_faces]
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    return fn


def cut_quay_footprint(bm, mw):
    """Gelände entlang der Kaigrenzen schneiden (nur in Kainähe) und innerhalb des Kais löschen."""
    region = (QUAY_X0 - 0.5, QUAY_X1 + 0.5, QUAY_FRONT_Y - 0.5, QUAY_BACK_Y + 0.5)
    for axis, value in ((0, QUAY_X0), (0, QUAY_X1), (1, QUAY_FRONT_Y), (1, QUAY_EDGE_Y), (0, QUAY_CORNER_X),
                        (1, QUAY_BACK_Y)):
        co = [0.0, 0.0, 0.0]
        co[axis] = value
        no = [0.0, 0.0, 0.0]
        no[axis] = 1.0
        bisect(bm, mw, crossing(bm, mw, axis, value, region), co, no)
    kill = [f for f in bm.faces if in_quay(*(mw @ f.calc_center_median()).xy, pad=-0.01)]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")


def rebuild_quay_floor(bm, mw):
    """Pflasterplatten (Stone, zwischen Fugenhöhe und 0) und Fugenfläche löschen, Mauerkrone auf 0 heben,
    großen Boden (Paving) einsetzen."""
    mats = [m.name for m in bpy.data.objects["Quay"].data.materials]
    kill = []
    for f in bm.faces:
        zs = [v.co.z for v in f.verts]
        name = mats[f.material_index]
        if name == "Stone" and min(zs) >= MORTAR_Z - 1e-4 and max(zs) <= 0.02:
            kill.append(f)
        elif name == "StoneDark" and max(abs(z - MORTAR_Z) for z in zs) < 1e-4:
            kill.append(f)
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    for v in bm.verts:
        if abs(v.co.z - MORTAR_Z) < 1e-4:
            v.co.z = 0.0
    if "Paving" not in mats:
        bpy.data.objects["Quay"].data.materials.append(material("Paving", "Stone"))
        mats.append("Paving")
    pi = mats.index("Paving")
    uv = bm.loops.layers.uv.active
    for (x0, x1, y0, y1), (nx, ny) in FLOOR_CELLS:
        grid = [[bm.verts.new((x0 + (x1 - x0) * i / nx, y0 + (y1 - y0) * j / ny, 0.0)) for i in range(nx + 1)]
                for j in range(ny + 1)]
        for j in range(ny):
            for i in range(nx):
                f = bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
                f.material_index = pi
                f.smooth = False
                for lp in f.loops:
                    lp[uv].uv = (lp.vert.co.x, lp.vert.co.y)


# --- 4. Vertexfarben: Umgebungsverdeckung ----------------------------------------------------------------
def bake_ao(objs, occluders, dist=0.9, nrays=48):
    """Umgebungsverdeckung je Ecke mit festen Strahlrichtungen (deterministisch, ohne Cycles).
    Startpunkt 20 % von der Ecke zur Flächenmitte versetzt: Ecken, die in anderer Geometrie stecken
    (Glas im Rahmen, Kistenkörper in den Leisten, Fassfuß auf dem Boden), würden sonst ganz schwarz.
    Gespeichert wird der rohe Wert (1 = frei); wie stark er wirkt, regelt der Shader (ps1_vc_strength)."""
    from mathutils.bvhtree import BVHTree
    verts, polys = [], []
    for ob in occluders:
        off = len(verts)
        verts += [ob.matrix_world @ v.co for v in ob.data.vertices]
        polys += [[off + i for i in p.vertices] for p in ob.data.polygons]
    bvh = BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)
    dirs = []                                   # kosinusgewichtete Halbkugel (Fibonacci), z = Normale
    for i in range(nrays):
        u = (i + 0.5) / nrays
        r, phi = math.sqrt(u), i * 2.399963229728653
        dirs.append(Vector((r * math.cos(phi), r * math.sin(phi), math.sqrt(1.0 - u))))
    stats = {}
    for ob in objs:
        me, mw = ob.data, ob.matrix_world
        nm = mw.to_3x3().inverted().transposed()
        ca = me.color_attributes.new(name="Color", type="BYTE_COLOR", domain="CORNER")
        me.color_attributes.active_color = ca
        cn = me.corner_normals
        glass = all(m.name == "Glass" for m in me.materials)
        vals = []
        for p in me.polygons:
            c = mw @ p.center
            for li in p.loop_indices:
                if glass:
                    ao = 1.0
                else:
                    v = mw @ me.vertices[me.loops[li].vertex_index].co
                    n = (nm @ cn[li].vector).normalized()
                    o = v.lerp(c, 0.2) + n * 0.01
                    rot = n.to_track_quat("Z", "Y").to_matrix()
                    hits = sum(1 for d in dirs if bvh.ray_cast(o, rot @ d, dist)[0] is not None)
                    ao = 1.0 - hits / nrays
                ca.data[li].color = (ao, ao, ao, 1.0)
                vals.append(ao)
        stats[ob.name] = [round(min(vals), 2), round(sum(vals) / len(vals), 2)]
    print("AO_MIN_MEAN " + json.dumps(stats))


# --- Ablauf ----------------------------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in [o for o in bpy.data.objects if o.name.startswith("Icosphere")]:
    bpy.data.objects.remove(o)

before = {o.name: tris(o) for o in bpy.data.objects if o.type == "MESH"}
material("BarrelSide", "Wood")
material("Railing", "Metal")
material("CrateSide", "Wood")

for name in ("Barrel1", "Barrel2"):
    set_mesh(bpy.data.objects[name], barrel())
set_mesh(bpy.data.objects["Bollards"], bollards())
set_mesh(bpy.data.objects["CrateStack"], crates(), smooth_angle=30.0)
set_mesh(bpy.data.objects["Lighthouse"], lighthouse(), smooth_angle=40.0)
set_mesh(bpy.data.objects["LighthouseLamp"], lighthouse_lamp(), smooth_angle=40.0)

edit(bpy.data.objects["Quay"], rebuild_quay_floor)
for name in ("WestHill", "Headland"):
    edit(bpy.data.objects[name], cut_quay_footprint)
for name in ("Quay", "Jetty", "WestHill", "Headland", "RocksSea", "IslandsFar"):
    edit(bpy.data.objects[name], cut_below(WATER_Z))
for name in ("BoatA", "BoatB"):
    ob = bpy.data.objects[name]
    edit(ob, cut_below((ob.matrix_world @ Vector((0, 0, -0.02))).z, outward_only=True))
# unter dem Kaiboden innerhalb des Kais (Innenseiten der Kantensteine, Steg-Anfang, Sockel)
for name in ("Quay", "Jetty", "Cottage", "LanternPost", "CrateStack", "RopeCoil"):
    edit(bpy.data.objects[name], cut_below(0.0, inside=lambda x, y: in_quay(x, y, pad=-0.02)))

meshes = [o for o in bpy.data.objects if o.type == "MESH"]
if DO_AO:
    solid = [o for o in meshes if o.name != "Sea"]
    bake_ao(solid, solid)

bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", export_yup=True, export_apply=True,
                          export_cameras=False, export_lights=False, export_texcoords=True, export_normals=True,
                          export_extras=False, export_vertex_color="ACTIVE", export_all_vertex_colors=False,
                          export_animations=False, use_selection=False)

after = {o.name: tris(o) for o in meshes}

print("HARBOR_PS1 " + json.dumps({"total_before": sum(before.values()), "total_after": sum(after.values()),
                                  "objects": {k: [before.get(k), after[k]] for k in sorted(after)},
                                  "materials": sorted(m.name for m in bpy.data.materials if m.users)}))
