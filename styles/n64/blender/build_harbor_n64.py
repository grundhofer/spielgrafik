# N64-Fassung des Hafens: aus shared/3d/harbor.glb eine Variante mit Konsolen-Geometrie und gebackenem
# Vertexlicht bauen.
#
#   blender -b --factory-startup -P styles/n64/blender/build_harbor_n64.py -- \
#       shared/3d/harbor.glb styles/n64/demo/models/harbor_n64.glb
#
# Objektnamen, Eltern, Empties und Lage bleiben wie im gemeinsamen glb (shared/3d wird nicht verändert).
# Geändert wird:
#  1. Kaiboden: Die modellierten Pflasterplatten und die Fugenfläche fallen weg. An ihrer Stelle liegt bei
#     y = 0 ein Gitter aus 0,5-m-Vierecken (Material "Paving", UV in Metern), auf dem eine kleine, weich
#     gefilterte Pflastertextur kachelt, wie in Spielen der Zeit. Das feine Gitter trägt das Vertexlicht
#     (Schatten von Häuschen und Fässern, Lichtschein des Fensters).
#  2. Fässer (10 Seiten, Dauben und Reifen als Textur "BarrelSide") und Kisten (ein Würfel je Kiste mit
#     Kistentextur "CrateSide") statt modellierter Leisten, Dauben und Reifen.
#  3. Große Flächen (Wände und Giebel des Häuschens, Kaimauern) werden unterteilt, damit Licht je Eckpunkt
#     dort Verläufe zeigen kann (so bauten Entwickler der Zeit vorbeleuchtete Level).
#  4. Gebackenes Vertexlicht als Vertexfarbe COLOR_0 je Ecke (Kanäle getrennt, gemischt wird im Shader):
#       R = Umgebungsverdeckung (Himmelslicht), 32 feste Strahlen, 1,5 m
#       G = Abendsonne: max(0, N·L) mal Sichtbarkeit (5 Strahlen um die Sonnenrichtung, 120 m)
#       B = Fensterlicht des Häuschens (zwei Punktlichter vor Front- und Seitenfenster, mit Sichtprüfung)
#     Das Meer bekommt keine Vertexfarben (eigener Shader), Glas wird weiß.
# Deterministisch (feste Strahlrichtungen, kein Zufall).
import json
import math
import sys

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = argv[0], argv[1]

# --- Maße aus shared/3d/blender/build_harbor.py (Blender-Koordinaten: Z oben, Kamera blickt nach +Y) -----
QUAY_X0, QUAY_X1 = -13.0, 8.0
QUAY_FRONT_Y, QUAY_EDGE_Y = -8.0, 1.0
QUAY_CORNER_X, QUAY_BACK_Y = -5.0, 3.6
MORTAR_Z = -0.05
FLOOR_CELL = 0.5

# Sonne wie in shared/3d/demo/main.tscn: Lichtrichtung Godot (0.86, -0.24, -0.46) = Blender (0.86, 0.46, -0.24)
TO_SUN = -Vector((0.86, 0.46, -0.24)).normalized()
# Fensterlichter: 0,35 m vor dem Frontfenster (Blender (-9.2, -0.515, 1.45)) und vor dem Seitenfenster
WINDOW_LIGHTS = [(Vector((-9.2, -0.87, 1.45)), 1.0, 5.5), (Vector((-6.25, 1.15, 1.5)), 0.7, 4.0)]
AO_DIST, AO_RAYS = 1.5, 32
SUBDIV = {"Cottage": (0.7, {"Stone"}), "Quay": (1.6, {"Stone", "StoneDark"})}


def tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def material(name, like):
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials[like].copy()
    m.name = name
    return m


class MB:
    """Sammelt Flächen: Eckpunkte (lokal), Material, UV je Ecke."""

    def __init__(self):
        self.v, self.f = [], []

    def face(self, cos, mat, uvs):
        idx = []
        for c in cos:
            self.v.append(tuple(c))
            idx.append(len(self.v) - 1)
        self.f.append((idx, mat, uvs))


def set_mesh(ob, mb, smooth_angle):
    """Mesh-Daten eines vorhandenen Objekts ersetzen (Name, Lage, Eltern und Kinder bleiben)."""
    me = bpy.data.meshes.new(ob.name + "_n64")
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
    # doppelte Punkte (je Fläche eigene Ecken) zusammenführen, damit Glättung und Vertexlicht durchlaufen
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    me.set_sharp_from_angle(angle=math.radians(smooth_angle))
    old = ob.data
    ob.data = me
    bpy.data.meshes.remove(old)
    me.name = ob.name


def M(loc=(0, 0, 0), rot_deg=(0, 0, 0)):
    return Matrix.LocRotScale(Vector(loc), Euler(tuple(math.radians(a) for a in rot_deg), "XYZ"), None)


# --- 2. Fässer und Kisten ------------------------------------------------------------------------------
def barrel():
    """Fass 0,9 m hoch, 10 Seiten, Bauch aus 4 Ringen; Dauben und Reifen in barrel.png (u: 2 Kacheln
    einmal herum, v: 0..1 von unten nach oben), Deckel mit Brettern (Material Wood, UV in Metern).
    Ohne Boden: 4 × 20 + 8 = 88 Dreiecke."""
    seg, H = 10, 0.9
    prof = [(0.255, 0.0), (0.305, 0.2), (0.322, 0.45), (0.305, 0.7), (0.255, H)]
    mb = MB()

    def P(r, z, k):
        a = 2 * math.pi * k / seg + math.pi / seg
        return Vector((r * math.cos(a), r * math.sin(a), z))

    for i in range(len(prof) - 1):
        (r0, z0), (r1, z1) = prof[i], prof[i + 1]
        for k in range(seg):
            u0, u1 = 2.0 * k / seg, 2.0 * (k + 1) / seg
            mb.face([P(r0, z0, k), P(r0, z0, k + 1), P(r1, z1, k + 1), P(r1, z1, k)], "BarrelSide",
                    [(u0, z0 / H), (u1, z0 / H), (u1, z1 / H), (u0, z1 / H)])
    r = prof[-1][0]
    cos = [P(r, H, k) for k in range(seg)]
    mb.face(cos, "Wood", [(c.x, c.y) for c in cos])
    return mb


def crates():
    """Kistenstapel wie build_crates() in shared/3d (gleiche Größen, Lage und Drehung), jede Kiste ein Würfel
    ohne Boden mit der Kistentextur auf jeder Seite (UV 0..1 je Fläche): 10 Dreiecke je Kiste."""
    mb = MB()
    for s, loc, rot in ((0.62, (-0.34, 0.0, 0.31), 4), (0.62, (0.33, 0.06, 0.31), -7),
                        (0.58, (0.0, 0.03, 0.91), 14), (0.44, (0.95, -0.25, 0.22), 23)):
        mtx = M(loc, (0, 0, rot))
        h = s / 2
        c = [Vector((x, y, z)) for x in (-h, h) for y in (-h, h) for z in (-h, h)]   # Index x*4 + y*2 + z
        # Umlaufsinn so, dass die Normale nach außen zeigt; UV aus den lokalen Koordinaten (v = oben)
        faces = {"-x": ([0, 1, 3, 2], lambda p: (p.y, p.z)), "+x": ([4, 6, 7, 5], lambda p: (p.y, p.z)),
                 "-y": ([0, 4, 5, 1], lambda p: (p.x, p.z)), "+y": ([2, 3, 7, 6], lambda p: (p.x, p.z)),
                 "top": ([1, 5, 7, 3], lambda p: (p.x, p.y))}
        for name, (idx, f) in faces.items():
            uvs = [(f(c[i])[0] / s + 0.5, f(c[i])[1] / s + 0.5) for i in idx]
            mb.face([mtx @ c[i] for i in idx], "CrateSide", uvs)
    return mb


# --- 1. Kaiboden ----------------------------------------------------------------------------------------
def edit(ob, fn):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    fn(bm, ob.matrix_world)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def rebuild_quay_floor(bm, mw):
    """Pflasterplatten (Stone zwischen Fugenhöhe und 2 cm) und Fugenfläche löschen, Mauerkrone von der
    Fugenhöhe auf 0 heben, Bodengitter (Paving) einsetzen."""
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
    bpy.data.objects["Quay"].data.materials.append(material("Paving", "Stone"))
    pi = len(bpy.data.objects["Quay"].data.materials) - 1
    uv = bm.loops.layers.uv.active
    for x0, x1, y0, y1 in ((QUAY_X0, QUAY_X1, QUAY_FRONT_Y, QUAY_EDGE_Y),
                           (QUAY_X0, QUAY_CORNER_X, QUAY_EDGE_Y, QUAY_BACK_Y)):
        nx = max(1, round((x1 - x0) / FLOOR_CELL))
        ny = max(1, round((y1 - y0) / FLOOR_CELL))
        grid = [[bm.verts.new((x0 + (x1 - x0) * i / nx, y0 + (y1 - y0) * j / ny, 0.0)) for i in range(nx + 1)]
                for j in range(ny + 1)]
        for j in range(ny):
            for i in range(nx):
                f = bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
                f.material_index = pi
                f.smooth = True
                for lp in f.loops:
                    lp[uv].uv = (lp.vert.co.x, lp.vert.co.y)
    # Nähte zwischen den beiden Bodenflächen schließen (gleiche Punkte bei y = QUAY_EDGE_Y)
    bmesh.ops.remove_doubles(bm, verts=[v for v in bm.verts if abs(v.co.z) < 1e-6], dist=1e-4)


# --- 3. Große Flächen unterteilen -----------------------------------------------------------------------
def subdivide_long(ob, max_len, mat_names):
    me = ob.data
    mats = [m.name for m in me.materials]

    def fn(bm, mw):
        for _ in range(6):
            faces = [f for f in bm.faces if mats[f.material_index] in mat_names]
            bmesh.ops.triangulate(bm, faces=[f for f in faces if len(f.verts) > 4])
            faces = [f for f in bm.faces if mats[f.material_index] in mat_names]
            edges = {e for f in faces for e in f.edges if e.calc_length() > max_len}
            if not edges:
                break
            bmesh.ops.subdivide_edges(bm, edges=list(edges), cuts=1, use_grid_fill=True)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    edit(ob, fn)


# --- 4. Vertexlicht backen ------------------------------------------------------------------------------
def fib_dirs(n):
    """Kosinusgewichtete Halbkugel (Fibonacci-Spirale), z = Normale."""
    out = []
    for i in range(n):
        u = (i + 0.5) / n
        r, phi = math.sqrt(u), i * 2.399963229728653
        out.append(Vector((r * math.cos(phi), r * math.sin(phi), math.sqrt(1.0 - u))))
    return out


def sun_dirs():
    base = TO_SUN
    side = base.cross(Vector((0, 0, 1))).normalized()
    up = side.cross(base).normalized()
    s = math.radians(1.2)
    return [base] + [(base + side * math.tan(s) * a + up * math.tan(s) * b).normalized()
                     for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))]


def bake(objs, occluders):
    verts, polys = [], []
    for ob in occluders:
        off = len(verts)
        verts += [ob.matrix_world @ v.co for v in ob.data.vertices]
        polys += [[off + i for i in p.vertices] for p in ob.data.polygons]
    bvh = BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)
    hemi = fib_dirs(AO_RAYS)
    suns = sun_dirs()
    stats = {}
    for ob in objs:
        me, mw = ob.data, ob.matrix_world
        nm = mw.to_3x3().inverted().transposed()
        for a in list(me.color_attributes):
            me.color_attributes.remove(a)
        ca = me.color_attributes.new(name="Color", type="FLOAT_COLOR", domain="CORNER")
        me.color_attributes.active_color = ca
        me.color_attributes.render_color_index = 0
        cn = me.corner_normals
        glass = all(m.name == "Glass" for m in me.materials)
        acc = [0.0, 0.0, 0.0]
        n_l = 0
        for p in me.polygons:
            c = mw @ p.center
            for li in p.loop_indices:
                if glass:
                    col = (1.0, 1.0, 1.0)
                else:
                    v = mw @ me.vertices[me.loops[li].vertex_index].co
                    n = (nm @ cn[li].vector).normalized()
                    # 15 % zur Flächenmitte versetzt: Ecken, die in anderer Geometrie stecken, würden sonst schwarz
                    o = v.lerp(c, 0.15) + n * 0.012
                    rot = n.to_track_quat("Z", "Y").to_matrix()
                    hits = sum(1 for d in hemi if bvh.ray_cast(o, rot @ d, AO_DIST)[0] is not None)
                    ao = 1.0 - hits / AO_RAYS
                    ndl = n.dot(TO_SUN)
                    sun = 0.0
                    if ndl > 0.0:
                        vis = sum(1 for d in suns if bvh.ray_cast(o, d, 120.0)[0] is None) / len(suns)
                        sun = ndl * vis
                    win = 0.0
                    for lp, strength, rad in WINDOW_LIGHTS:
                        dv = lp - o
                        d = dv.length
                        if d >= rad:
                            continue
                        ldir = dv / d
                        ndl_w = n.dot(ldir)
                        if ndl_w <= 0.0:
                            continue
                        if bvh.ray_cast(o, ldir, d - 0.05)[0] is not None:
                            continue
                        fall = (1.0 - (d / rad) ** 2) ** 2 / (1.0 + 0.6 * d * d)
                        win += strength * (0.35 + 0.65 * ndl_w) * fall
                    col = (ao, sun, min(win, 1.0))
                ca.data[li].color = (col[0], col[1], col[2], 1.0)
                for k in range(3):
                    acc[k] += col[k]
                n_l += 1
        stats[ob.name] = [round(x / max(n_l, 1), 3) for x in acc]
    print("BAKE_MEAN_AO_SUN_WIN " + json.dumps(stats))


# --- Ablauf ----------------------------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in [o for o in bpy.data.objects if o.name.startswith("Icosphere")]:
    bpy.data.objects.remove(o)

before = {o.name: tris(o) for o in bpy.data.objects if o.type == "MESH"}
material("BarrelSide", "Wood")
material("CrateSide", "Wood")

for name in ("Barrel1", "Barrel2"):
    set_mesh(bpy.data.objects[name], barrel(), smooth_angle=50.0)
set_mesh(bpy.data.objects["CrateStack"], crates(), smooth_angle=30.0)
edit(bpy.data.objects["Quay"], rebuild_quay_floor)
for name, (max_len, mats) in SUBDIV.items():
    subdivide_long(bpy.data.objects[name], max_len, mats)

meshes = [o for o in bpy.data.objects if o.type == "MESH"]
solid = [o for o in meshes if o.name != "Sea"]
occ = [o for o in solid if not all(m.name == "Glass" for m in o.data.materials)]
bake(solid, occ)

bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", export_yup=True, export_apply=True,
                          export_cameras=False, export_lights=False, export_texcoords=True, export_normals=True,
                          export_extras=False, export_vertex_color="ACTIVE", export_all_vertex_colors=False,
                          export_animations=False, use_selection=False)

after = {o.name: tris(o) for o in meshes}
print("HARBOR_N64 " + json.dumps({"total_before": sum(before.values()), "total_after": sum(after.values()),
                                  "objects": {k: [before.get(k), after[k]] for k in sorted(after)},
                                  "materials": sorted(m.name for m in bpy.data.materials if m.users)}))
