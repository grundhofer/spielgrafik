# Hafen für den Eintrag handpainted-3d: aus shared/3d/harbor.glb eine Variante mit flachem Kaiboden für
# gemalte Pflastertextur, stilisierten Formen, eigenen Koordinaten je Steinfläche und gebackener
# Umgebungsverdeckung als Vertexfarbe bauen.
#
#   blender -b --factory-startup -P styles/handpainted-3d/blender/build_harbor_hp.py -- \
#       shared/3d/harbor.glb styles/handpainted-3d/demo/models/harbor_hp.glb [--no-stylize]
#
# --no-stylize lässt Schritt 2 weg (nur zum Vergleich: Anteil der Pixel, den die Formen ändern).
#
# Objektnamen, Eltern, Empties, Lage und Materialnamen bleiben wie im gemeinsamen glb (shared/3d wird nicht
# verändert). Geändert wird:
#  1. Kaiboden: Die modellierten Pflasterplatten und die Fugenfläche fallen weg; an ihrer Stelle liegt bei
#     y = 0 ein Gitter aus 0,5-m-Vierecken (neues Material "Paving", UV in Metern). Die Steine und Fugen
#     kommen aus der gemalten Textur, wie in Spielen mit handbemalten Texturen üblich (einfache Geometrie,
#     Detail in der Farbe). Vorgehen wie styles/n64/blender/build_harbor_n64.py (rebuild_quay_floor).
#  2. Stilisierte, leicht übertriebene Formen (jedes Objekt im eigenen Raum, Ursprung und Lage bleiben):
#     Häuschen: Wände unten um 0,13 m ausgestellt (3° Neigung, oben schmaler als unten), Dachplatten an der
#     Traufe 15 % und am Ortgang 20 % länger, First in der Mitte 6 cm durchgesackt (Giebelspitzen sinken mit,
#     damit zwischen Giebel und Dach keine Lücke entsteht); Fässer in der Mitte 10 % bauchiger; Steg- und
#     Festmachpfähle 1,4-fach, Laternenpfahl 1,5-fach dicker; Leuchtturm unten 14 % breiter (stärkere
#     Verjüngung). Das Fensterglas (eigenes Objekt) folgt der Wand.
#  3. Eckquader, Sockel, Gewände, Simse und Kantensteine (StoneDark auf Häuschen, Kai, Laternenpfahl) bekommen
#     je Fläche eigene Koordinaten in Metern (UV) und die Flächengröße (UV2): Der Shader malt daraus einen
#     Stein je Fläche mit gemalter Kante, statt die Mauertextur quer über die Kanten zu projizieren.
#  4. Große Flächen (Wände des Häuschens, Kaimauern) werden unterteilt, damit die Verdeckung Verläufe zeigt.
#  5. Gebackene Umgebungsverdeckung je Ecke als Vertexfarbe COLOR_0 (Kanäle getrennt, gemischt im Shader):
#       R = Nahverdeckung (Strahlen bis 0,7 m): dunkle Fugen und Kontaktschatten unter Fässern und Kisten
#       G = Fernverdeckung (Strahlen bis 4 m): großflächige Abdunklung neben Häuschen, unter Steg und Booten
#       B = 1 (frei)
#     Das Meer bekommt keine Vertexfarben (eigener Shader), Glas wird weiß.
# Deterministisch (feste Strahlrichtungen, kein Zufall).
import json
import math
import sys

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = argv[0], argv[1]
STYLIZE = "--no-stylize" not in argv

# Maße aus shared/3d/blender/build_harbor.py (Blender-Koordinaten: Z oben, Kamera blickt nach +Y)
QUAY_X0, QUAY_X1 = -13.0, 8.0
QUAY_FRONT_Y, QUAY_EDGE_Y = -8.0, 1.0
QUAY_CORNER_X, QUAY_BACK_Y = -5.0, 3.6
MORTAR_Z = -0.05
FLOOR_CELL = 0.5
NEAR_DIST, FAR_DIST, RAYS = 0.7, 4.0, 64
SUBDIV = {"Cottage": (0.6, {"Stone", "StoneDark"}), "Quay": (1.0, {"Stone", "StoneDark"})}


def tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def material(name, like):
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials[like].copy()
    m.name = name
    return m


def edit(ob, fn):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    fn(bm, ob.matrix_world)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


# --- 1. Kaiboden ----------------------------------------------------------------------------------------
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
    bmesh.ops.remove_doubles(bm, verts=[v for v in bm.verts if abs(v.co.z) < 1e-6], dist=1e-4)


# --- 2. Stilisierte Formen --------------------------------------------------------------------------------
# Maße aus shared/3d/blender/build_harbor.py (lokale Koordinaten der Objekte, Z oben)
COT_W, COT_D, COT_H, COT_R = 3.6, 3.0, 2.45, 1.35
WALL_FLARE = 0.128            # m: Wandfuß nach außen = tan(3°) * Traufhöhe
EAVE_EXT, VERGE_EXT = 0.15, 0.20
RIDGE_SAG = 0.06
CHIMNEY_XY = ((-COT_W / 2 + 0.62 - 0.36, -COT_W / 2 + 0.62 + 0.36), (0.35 - 0.36, 0.35 + 0.36))
BARREL_H, BARREL_BULGE = 0.9, 0.10
JETTY_PILES = [(x, y) for x in (2.53, 4.37) for y in (1.7, 3.9, 6.1, 8.3)]
PILE_SCALE, POST_SCALE, POST_BASE_SCALE = 1.4, 1.5, 1.25
LH_Z0, LH_Z1, LH_FLARE = 0.6, 8.4, 0.14
SHAPE_LOG = {}


def mats_of(ob):
    return [m.name for m in ob.data.materials]


def vert_mats(ob):
    """Materialnamen je Vertex (aus den Flächen, an denen er hängt)."""
    mats = mats_of(ob)
    out = [set() for _ in ob.data.vertices]
    for p in ob.data.polygons:
        for vi in p.vertices:
            out[vi].add(mats[p.material_index])
    return out


def flare(x, y, z):
    """Wandneigung des Häuschens: unterhalb der Traufe nach außen, oberhalb unverändert."""
    k = max(0.0, COT_H - z) / COT_H
    return x * (1.0 + WALL_FLARE / (COT_W / 2) * k), y * (1.0 + WALL_FLARE / (COT_D / 2) * k)


def sag(x):
    half = (COT_W + 0.5) / 2 * (1.0 + VERGE_EXT)
    return RIDGE_SAG * max(0.0, 1.0 - (x / half) ** 2)


def stylize_cottage(ob, win):
    me = ob.data
    vm = vert_mats(ob)
    slope = math.atan2(COT_R, COT_D / 2)
    ridge = Vector((0.0, 0.0, COT_H + COT_R))
    cap_axis_z = COT_H + COT_R + 0.19
    mats = mats_of(ob)
    cap = set()
    for p in me.polygons:
        if mats[p.material_index] != "Roof":
            continue
        if all(abs(math.hypot(me.vertices[i].co.y, me.vertices[i].co.z - cap_axis_z) - 0.11) < 0.004 for i in p.vertices):
            cap.update(p.vertices)
    eave_before = min(v.co.z for v, m in zip(me.vertices, vm) if "Roof" in m)
    for v, m in zip(me.vertices, vm):
        c = v.co
        if "Roof" in m:
            if v.index not in cap:
                # entlang der Dachneigung vom First nach außen verlängern (Traufe)
                best = None
                for side in (-1.0, 1.0):
                    d = Vector((0.0, side * math.cos(slope), -math.sin(slope)))
                    s = (c - ridge).dot(d)
                    if best is None or s > best[0]:
                        best = (s, d)
                if best[0] > 0.0:
                    c += best[1] * best[0] * EAVE_EXT
            c.x *= 1.0 + VERGE_EXT                      # Ortgang
            c.z -= sag(c.x)
        else:
            in_chimney = (CHIMNEY_XY[0][0] < c.x < CHIMNEY_XY[0][1] and CHIMNEY_XY[1][0] < c.y < CHIMNEY_XY[1][1])
            if c.z > COT_H - 0.01:
                if not in_chimney:
                    c.z -= sag(c.x)                     # Giebelspitzen sinken mit dem First
            else:
                c.x, c.y = flare(c.x, c.y, c.z)
    # Fensterglas folgt der Wand (im Raum des Häuschens rechnen, Ursprung bleibt)
    to_cot = ob.matrix_world.inverted() @ win.matrix_world
    back = to_cot.inverted()
    for v in win.data.vertices:
        p = to_cot @ v.co
        p.x, p.y = flare(p.x, p.y, p.z)
        v.co = back @ p
    me.update()
    win.data.update()
    roof = [v.co for v, m in zip(me.vertices, vm) if "Roof" in m]
    SHAPE_LOG["Cottage"] = {"roof_x": [round(min(c.x for c in roof), 3), round(max(c.x for c in roof), 3)],
                            "roof_y": [round(min(c.y for c in roof), 3), round(max(c.y for c in roof), 3)],
                            "eave_z": [round(eave_before, 3), round(min(c.z for c in roof), 3)],
                            "wall_foot_x": round(max(v.co.x for v, m in zip(me.vertices, vm)
                                                     if "Stone" in m and v.co.z < 0.01), 3)}


def stylize_barrel(ob):
    for v in ob.data.vertices:
        u = min(max(v.co.z / BARREL_H, 0.0), 1.0)
        g = 1.0 + BARREL_BULGE * math.sin(math.pi * u)
        v.co.x *= g
        v.co.y *= g
    ob.data.update()
    SHAPE_LOG[ob.name] = {"r_max": round(max(math.hypot(v.co.x, v.co.y) for v in ob.data.vertices), 3)}


def stylize_jetty(ob):
    vm = vert_mats(ob)
    n = 0
    for v, m in zip(ob.data.vertices, vm):
        if "WoodDark" not in m:
            continue
        for px, py in JETTY_PILES:
            dx, dy = v.co.x - px, v.co.y - py
            if math.hypot(dx, dy) < 0.13:
                v.co.x = px + dx * PILE_SCALE
                v.co.y = py + dy * PILE_SCALE
                n += 1
                break
    ob.data.update()
    SHAPE_LOG["Jetty"] = {"pile_verts": n}


def stylize_post(ob):
    vm = vert_mats(ob)
    for v, m in zip(ob.data.vertices, vm):
        if "WoodDark" in m and abs(v.co.x) <= 0.101 and abs(v.co.y) <= 0.101:
            v.co.x *= POST_SCALE
            v.co.y *= POST_SCALE
        elif "StoneDark" in m:
            v.co.x *= POST_BASE_SCALE
            v.co.y *= POST_BASE_SCALE
    ob.data.update()


def stylize_lighthouse(ob):
    vm = vert_mats(ob)
    for v, m in zip(ob.data.vertices, vm):
        c = v.co
        if c.z < LH_Z0 - 0.01 or c.z > LH_Z1 + 0.001:
            continue
        if "StoneDark" in m and math.hypot(c.x, c.y) > 1.58:
            continue                                   # Sockelkante bleibt
        u = min(max((c.z - LH_Z0) / (LH_Z1 - LH_Z0), 0.0), 1.0)
        g = 1.0 + LH_FLARE * (1.0 - u) ** 1.3
        c.x *= g
        c.y *= g
    ob.data.update()


# --- 3. Eigene Koordinaten je Steinfläche ------------------------------------------------------------------
BLOCK_OBJECTS = ("Cottage", "Quay", "LanternPost")
BLOCK_MAX = 4.0     # größere Flächen (Kaimauer unter Wasser) behalten die Projektion


def block_uvs(ob):
    """StoneDark-Flächen: UV = Meter ab der unteren linken Ecke der Fläche (Tangente waagrecht, Bitangente
    aufwärts bzw. bei liegenden Flächen x/y), UV2 = Breite und Höhe der Fläche. Andere Flächen: UV2 = 0.
    glTF dreht V um (v -> 1 - v); deshalb hier 1 - v speichern, in Godot kommt v an."""
    me = ob.data
    mats = mats_of(ob)
    uv0 = me.uv_layers[0]
    uv1 = me.uv_layers.new(name="Block")
    up = Vector((0.0, 0.0, 1.0))
    n_block = 0
    sizes = []
    for p in me.polygons:
        if mats[p.material_index] != "StoneDark":
            for li in p.loop_indices:
                uv1.data[li].uv = (0.0, 1.0)
            continue
        n = p.normal
        if abs(n.z) > 0.9:
            t, b = Vector((1.0, 0.0, 0.0)), Vector((0.0, 1.0, 0.0))
        else:
            t = up.cross(n).normalized()
            b = n.cross(t).normalized()
            if b.z < 0:
                b, t = -b, -t
        pts = [(me.vertices[me.loops[li].vertex_index].co.dot(t), me.vertices[me.loops[li].vertex_index].co.dot(b))
               for li in p.loop_indices]
        u0, u1 = min(q[0] for q in pts), max(q[0] for q in pts)
        v0, v1 = min(q[1] for q in pts), max(q[1] for q in pts)
        w, h = u1 - u0, v1 - v0
        if max(w, h) > BLOCK_MAX:
            for li in p.loop_indices:
                uv1.data[li].uv = (0.0, 1.0)
            continue
        n_block += 1
        sizes.append(max(w, h))
        for li, (qu, qv) in zip(p.loop_indices, pts):
            uv0.data[li].uv = (qu - u0, 1.0 - (qv - v0))
            uv1.data[li].uv = (max(w, 1e-3), 1.0 - max(h, 1e-3))
    me.uv_layers.active = uv0
    SHAPE_LOG.setdefault("block_faces", {})[ob.name] = n_block


# --- 4. Große Flächen unterteilen -----------------------------------------------------------------------
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


# --- 5. Verdeckung backen -------------------------------------------------------------------------------
def fib_dirs(n):
    """Kosinusgewichtete Halbkugel (Fibonacci-Spirale), z = Normale."""
    out = []
    for i in range(n):
        u = (i + 0.5) / n
        r, phi = math.sqrt(u), i * 2.399963229728653
        out.append(Vector((r * math.cos(phi), r * math.sin(phi), math.sqrt(1.0 - u))))
    return out


def bake(objs, occluders):
    verts, polys = [], []
    for ob in occluders:
        off = len(verts)
        verts += [ob.matrix_world @ v.co for v in ob.data.vertices]
        polys += [[off + i for i in p.vertices] for p in ob.data.polygons]
    bvh = BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)
    hemi = fib_dirs(RAYS)
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
        acc = [0.0, 0.0]
        n_l = 0
        for p in me.polygons:
            c = mw @ p.center
            for li in p.loop_indices:
                if glass:
                    near = far = 1.0
                else:
                    v = mw @ me.vertices[me.loops[li].vertex_index].co
                    n = (nm @ cn[li].vector).normalized()
                    # 15 % zur Flächenmitte versetzt: Ecken, die in anderer Geometrie stecken, würden sonst schwarz
                    o = v.lerp(c, 0.15) + n * 0.012
                    rot = n.to_track_quat("Z", "Y").to_matrix()
                    hn = hf = 0
                    for d in hemi:
                        hit = bvh.ray_cast(o, rot @ d, FAR_DIST)
                        if hit[0] is not None:
                            hf += 1
                            if hit[3] < NEAR_DIST:
                                hn += 1
                    near = 1.0 - hn / RAYS
                    far = 1.0 - hf / RAYS
                ca.data[li].color = (near, far, 1.0, 1.0)
                acc[0] += near
                acc[1] += far
                n_l += 1
        stats[ob.name] = [round(x / max(n_l, 1), 3) for x in acc]
    print("BAKE_MEAN_NEAR_FAR " + json.dumps(stats))


# --- Ablauf ----------------------------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in [o for o in bpy.data.objects if o.name.startswith("Icosphere")]:
    bpy.data.objects.remove(o)

before = {o.name: tris(o) for o in bpy.data.objects if o.type == "MESH"}
edit(bpy.data.objects["Quay"], rebuild_quay_floor)
if STYLIZE:
    stylize_cottage(bpy.data.objects["Cottage"], bpy.data.objects["CottageWindow"])
    for name in ("Barrel1", "Barrel2"):
        stylize_barrel(bpy.data.objects[name])
    stylize_jetty(bpy.data.objects["Jetty"])
    stylize_post(bpy.data.objects["LanternPost"])
    stylize_lighthouse(bpy.data.objects["Lighthouse"])
for name in BLOCK_OBJECTS:
    block_uvs(bpy.data.objects[name])
print("SHAPES " + json.dumps(SHAPE_LOG))
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
print("HARBOR_HP " + json.dumps({"total_before": sum(before.values()), "total_after": sum(after.values()),
                                 "objects": {k: [before.get(k), after[k]] for k in sorted(after)},
                                 "materials": sorted(m.name for m in bpy.data.materials if m.users)}))
