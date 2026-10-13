# Hafen als Diorama für den Eintrag diorama-tiltshift: aus shared/3d/harbor.glb ein Inselstück auf einem
# Holzsockel bauen.
#
#   blender -b --factory-startup -P styles/diorama-tiltshift/blender/build_diorama.py -- \
#       shared/3d/harbor.glb styles/diorama-tiltshift/demo/models/harbor_diorama.glb
#
# Objektnamen, Eltern, Empties, Lage und Materialnamen des gemeinsamen glb bleiben erhalten (shared/3d wird
# nicht verändert). Geändert bzw. ergänzt wird:
#  1. Ausschnitt: Gelände, Kai, Felsen und Meer werden an einem abgerundeten Rechteck (Godot x -12,5 bis 14,5,
#     z -30,5 bis 2,9, Eckradius 2,5 m) abgeschnitten (bmesh.bisect_plane je Kante, konvex). IslandsFar fällt
#     weg (liegt 170 m und mehr hinter dem Kai, außerhalb jedes Sockels).
#  2. Schnittwände (wie bei einem aufgeschnittenen Modell): entlang des Umrisses alle 5 cm von oben gemessen,
#     wie hoch Land oder Wasser steht. SectionLand reicht vom Meeresboden (-2,6 m) bis zur Geländeoberkante,
#     SectionWater vom Grund bis zur Wasserlinie (-0,8 m), wo Wasser oben liegt (Gießharz im Schnitt).
#     UV = (Umfangsmeter, Höhe), UV2 = (Oberkante der Säule, Art der Oberfläche: 0 Kai, 1 Gras, 2 Sand, 3 Fels).
#  3. Seabed: Grundplatte bei -2,6 m unter dem Wasser (durch das Harz sichtbar).
#  4. PlinthBase: Holzsockel (Nussbaum) 1,2 m hoch, 0,35 m breiter als das Inselstück, mit Fasen.
#     Plaque: Messingschild vorn am Sockel (die Schrift setzt Godot als Label3D davor).
#  5. Gull1, Gull2: zwei Spielzeugmöwen an Nylonfäden (GullWire), Ursprung am Aufhängepunkt oben, damit sie
#     in Godot als Pendel schwingen. Gull1 hängt (halb so groß) rechts neben dem Dachs über dem Kai, in der
#     Schärfeebene der Nahaufnahme; Gull2 hängt hinten vor dem Leuchtturm (in der Unschärfe).
# Deterministisch (keine Zufallswerte ohne festen Seed).
import json
import math
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = argv[0], argv[1]

# Umriss in Godot-Koordinaten (x, z); Blender: (x, -z)
GX0, GX1 = -12.5, 14.5
GZ0, GZ1 = -30.5, 2.9          # hinten, vorn
CORNER_R = 2.5
CORNER_SEG = 6
WATER_Z = -0.8
SEABED_Z = -2.6
BASE_BOTTOM = -3.8
BASE_MARGIN = 0.35
BASE_CHAMFER = 0.08
STEP = 0.05
CLIP = ["Quay", "WestHill", "Headland", "RocksSea", "Sea"]
LAND = ["Quay", "WestHill", "Headland", "RocksSea", "Jetty", "Cottage", "Lighthouse"]
SMOOTH_DEG = {"WestHill": 38.0, "Headland": 38.0, "Sea": 180.0}   # sonst flach (wie im gemeinsamen glb)
GULLS = {"Gull1": ((-1.6, 1.7, 2.4), -148.0, 0.65), "Gull2": ((6.2, 7.4, -15.5), -150.0, 1.0)}   # Godot-Lage, Drehung um Y, Größe
WIRE_TOP = 48.0


def g2b(x, y, z):
    return Vector((x, -z, y))


def outline(offset=0.0):
    """Abgerundetes Rechteck in Blender-XY, gegen den Uhrzeigersinn (von oben), mit Versatz nach außen."""
    x0, x1 = GX0 - offset, GX1 + offset
    y0, y1 = -GZ1 - offset, -GZ0 + offset       # Blender-y: vorn = -3,5, hinten = 30,5
    r = CORNER_R + offset
    pts = []
    corners = [((x1 - r, y0 + r), -90.0), ((x1 - r, y1 - r), 0.0), ((x0 + r, y1 - r), 90.0), ((x0 + r, y0 + r), 180.0)]
    for (cx, cy), a0 in corners:
        for i in range(CORNER_SEG + 1):
            a = math.radians(a0 + 90.0 * i / CORNER_SEG)
            pts.append(Vector((cx + r * math.cos(a), cy + r * math.sin(a))))
    return pts


def planes():
    pts = outline()
    out = []
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        if (b - a).length < 1e-6:
            continue
        d = (b - a).normalized()
        nrm = Vector((d.y, -d.x, 0.0))      # nach außen (Umlauf gegen den Uhrzeigersinn)
        out.append((Vector((a.x, a.y, 0.0)), nrm))
    return out


def tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def new_material(name, rgb, rough=0.8, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    return m


def clip_object(ob, pls):
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.transform(ob.matrix_world)
    for co, no in pls:
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=co, plane_no=no, clear_outer=True)
    bm.transform(ob.matrix_world.inverted())
    bm.to_mesh(me)
    bm.free()
    me.update()


def reset_normals(ob, angle_deg):
    """Eigene Normalen aus dem glTF verwerfen (bisect zerschneidet sie) und neu glätten wie im gemeinsamen glb."""
    me = ob.data
    with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
        if me.has_custom_normals:
            bpy.ops.mesh.customdata_custom_splitnormals_clear()
    if angle_deg is None:
        me.shade_flat()
    else:
        me.shade_smooth()
        me.set_sharp_from_angle(angle=math.radians(angle_deg))


def make_object(name, bm, mats, parent=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if parent:
        ob.parent = parent
    return ob


# --- Ablauf --------------------------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
bpy.data.objects.remove(bpy.data.objects["IslandsFar"])
before = {o.name: tris(o) for o in bpy.data.objects if o.type == "MESH"}

PL = planes()
for name in CLIP:
    ob = bpy.data.objects[name]
    clip_object(ob, PL)
    reset_normals(ob, SMOOTH_DEG.get(name))

# Alles Übrige muss im Umriss liegen
poly = outline()


def inside(p, pad=0.0):
    for co, no in PL:
        if (Vector((p.x, p.y, 0.0)) - co).dot(no) > -pad:
            return False
    return True


for ob in bpy.data.objects:
    if ob.type == "MESH" and ob.name not in CLIP:
        for v in ob.data.vertices:
            assert inside(ob.matrix_world @ v.co), f"{ob.name} ragt über den Sockel"

# Materialklasse je Fläche für die Schnittwand
CLASS = {"Stone": 0, "StoneDark": 0, "Grass": 1, "Sand": 2, "Rock": 3, "Wood": 0, "WoodDark": 0, "WhitePaint": 0}
verts, polys, pclass = [], [], []
for name in LAND:
    ob = bpy.data.objects[name]
    off = len(verts)
    verts += [ob.matrix_world @ v.co for v in ob.data.vertices]
    for p in ob.data.polygons:
        polys.append([off + i for i in p.vertices])
        mname = ob.data.materials[p.material_index].name
        pclass.append(CLASS.get(mname, 3))
bvh = BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)

M = {
    "SectionLand": new_material("SectionLand", (0.32, 0.22, 0.14), 0.95),
    "SectionWater": new_material("SectionWater", (0.10, 0.35, 0.40), 0.05),
    "Seabed": new_material("Seabed", (0.55, 0.48, 0.36), 1.0),
    "PlinthWood": new_material("PlinthWood", (0.22, 0.12, 0.06), 0.35),
    "PlaqueBrass": new_material("PlaqueBrass", (0.80, 0.62, 0.30), 0.3, 1.0),
    "GullWhite": new_material("GullWhite", (0.92, 0.92, 0.90), 0.4),
    "GullGrey": new_material("GullGrey", (0.45, 0.48, 0.52), 0.4),
    "GullBeak": new_material("GullBeak", (0.95, 0.65, 0.15), 0.4),
    "GullWire": new_material("GullWire", (0.85, 0.85, 0.85), 0.2),
}

# --- Schnittwände --------------------------------------------------------------------------------------
pts = outline()
samples = []          # (Punkt, Normale nach außen, Umfangsmeter)
dist = 0.0
for i in range(len(pts)):
    a, b = pts[i], pts[(i + 1) % len(pts)]
    L = (b - a).length
    if L < 1e-6:
        continue
    d = (b - a).normalized()
    nrm = Vector((d.y, -d.x))
    k = max(1, math.ceil(L / STEP))
    for j in range(k):
        samples.append((a + (b - a) * (j / k), nrm, dist + L * j / k))
    dist += L
samples.append((samples[0][0], samples[0][1], dist))
PERIM = dist

cols = []
for p, nrm, s in samples:
    q = p - nrm * 0.004          # knapp innerhalb, damit der Strahl die abgeschnittene Fläche noch trifft
    hit = bvh.ray_cast(Vector((q.x, q.y, 60.0)), Vector((0, 0, -1)), 200.0)
    if hit[0] is not None and hit[0].z > SEABED_Z:
        top, cls = hit[0].z, pclass[hit[2]]
    else:
        top, cls = SEABED_Z, 2
    cols.append((p, nrm, s, top, cls))

stats = {"columns": len(cols), "perimeter_m": round(PERIM, 2), "water_columns": 0, "max_land": -9.0}
for kind in ("SectionLand", "SectionWater"):
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    uv2 = bm.loops.layers.uv.new("UV2")
    prev = None
    for p, nrm, s, top, cls in cols:
        if kind == "SectionLand":
            z0, z1, ttop, off = SEABED_Z, max(top, SEABED_Z), max(top, SEABED_Z), 0.0
            stats["max_land"] = max(stats["max_land"], top)
        else:
            z0, z1, ttop, off = min(max(top, SEABED_Z), WATER_Z), WATER_Z, WATER_Z, 0.003
            if top < WATER_Z:
                stats["water_columns"] += 1
        o = Vector((p.x + nrm.x * off, p.y + nrm.y * off))
        vb = bm.verts.new((o.x, o.y, z0))
        vt = bm.verts.new((o.x, o.y, z1))
        cur = (vb, vt, s, z0, z1, ttop, cls)
        if prev is not None:
            pb, pt_, ps, pz0, pz1, ptop, pcls = prev
            if (pz1 - pz0) > 1e-4 or (z1 - z0) > 1e-4:
                f = bm.faces.new((pb, vb, vt, pt_))
                f.smooth = False
                data = [(pb, ps, pz0, ptop, pcls), (vb, s, z0, ttop, cls), (vt, s, z1, ttop, cls), (pt_, ps, pz1, ptop, pcls)]
                for lp, (v, ss, zz, tt, cc) in zip(f.loops, data):
                    lp[uv].uv = (ss, zz)
                    lp[uv2].uv = (tt, float(cc))
        prev = cur
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    make_object(kind, bm, [M[kind]])

# --- Meeresboden -----------------------------------------------------------------------------------------
bm = bmesh.new()
uv = bm.loops.layers.uv.new("UVMap")
f = bm.faces.new([bm.verts.new((p.x, p.y, SEABED_Z)) for p in pts])
for lp in f.loops:
    lp[uv].uv = (lp.vert.co.x, lp.vert.co.y)
bmesh.ops.triangulate(bm, faces=[f])
make_object("Seabed", bm, [M["Seabed"]])

# --- Holzsockel ----------------------------------------------------------------------------------------
bm = bmesh.new()
uv = bm.loops.layers.uv.new("UVMap")
rings = [
    (BASE_MARGIN - BASE_CHAMFER, SEABED_Z),
    (BASE_MARGIN, SEABED_Z - BASE_CHAMFER),
    (BASE_MARGIN, BASE_BOTTOM + BASE_CHAMFER),
    (BASE_MARGIN - BASE_CHAMFER, BASE_BOTTOM),
]
ring_pts = [outline(off) for off, _ in rings]
ring_verts = [[bm.verts.new((p.x, p.y, z)) for p in rp] for rp, (_, z) in zip(ring_pts, rings)]
n = len(ring_pts[0])
for r in range(len(rings) - 1):
    acc = 0.0
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new((ring_verts[r][i], ring_verts[r][j], ring_verts[r + 1][j], ring_verts[r + 1][i]))
        L = (ring_pts[r][j] - ring_pts[r][i]).length
        for lp, (u, v) in zip(f.loops, ((acc, rings[r][1]), (acc + L, rings[r][1]), (acc + L, rings[r + 1][1]), (acc, rings[r + 1][1]))):
            lp[uv].uv = (u, v)
        acc += L
for r, flip in ((0, False), (len(rings) - 1, True)):
    vs = ring_verts[r][::-1] if flip else ring_verts[r]
    f = bm.faces.new(vs)
    for lp in f.loops:
        lp[uv].uv = (lp.vert.co.x, lp.vert.co.y)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
make_object("PlinthBase", bm, [M["PlinthWood"]])

# Messingschild vorn am Sockel (Godot: Mitte x = 1, y = -3,2, Vorderseite z = 2,9 + 0,35 + 0,04)
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
bmesh.ops.scale(bm, vec=(5.2, 0.04, 0.66), verts=bm.verts)
bmesh.ops.translate(bm, vec=g2b(1.0, (SEABED_Z + BASE_BOTTOM) / 2, GZ1 + BASE_MARGIN + 0.02), verts=bm.verts)
bmesh.ops.bevel(bm, geom=[e for e in bm.edges], offset=0.015, segments=1, affect="EDGES")
uv = bm.loops.layers.uv.new("UVMap")
for f in bm.faces:
    for lp in f.loops:
        lp[uv].uv = (lp.vert.co.x, lp.vert.co.z)
make_object("Plaque", bm, [M["PlaqueBrass"]])


# --- Möwen an Fäden ------------------------------------------------------------------------------------
def gull_bm():
    """Spielzeugmöwe, Kopf nach +X (Blender), Flügel ausgebreitet und leicht angehoben. Ursprung = Körpermitte."""
    bm = bmesh.new()

    def add(geom_fn, mi, mtx):
        tmp = bmesh.new()
        geom_fn(tmp)
        tmp.transform(mtx)
        for f in tmp.faces:
            f.material_index = mi
        me = bpy.data.meshes.new("tmp")
        tmp.to_mesh(me)
        tmp.free()
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)

    def sphere(b):
        bmesh.ops.create_uvsphere(b, u_segments=14, v_segments=9, radius=1.0)
        for f in b.faces:
            f.smooth = True

    def cone(b):
        bmesh.ops.create_cone(b, cap_ends=True, segments=8, radius1=1.0, radius2=0.0, depth=1.0)
        for f in b.faces:
            f.smooth = True

    def wing(b):
        bmesh.ops.create_cube(b, size=1.0)
        for f in b.faces:
            f.smooth = False

    S = Matrix.Diagonal
    add(sphere, 0, Matrix.Translation((0, 0, 0)) @ S((0.36, 0.16, 0.15, 1)))                      # Körper
    add(sphere, 0, Matrix.Translation((0.30, 0, 0.09)) @ S((0.11, 0.095, 0.095, 1)))              # Kopf
    add(cone, 2, Matrix.Translation((0.44, 0, 0.08)) @ Matrix.Rotation(math.radians(90), 4, "Y") @ S((0.03, 0.025, 0.12, 1)))
    add(cone, 0, Matrix.Translation((-0.38, 0, 0.0)) @ Matrix.Rotation(math.radians(-90), 4, "Y") @ S((0.09, 0.05, 0.2, 1)))  # Schwanz
    for side in (1, -1):
        for seg, (y0, y1, mi) in enumerate(((0.08, 0.42, 0), (0.42, 0.72, 1))):      # innen weiß, Spitze grau
            yc = (y0 + y1) / 2
            m = (Matrix.Rotation(math.radians(side * 16.0), 4, "X") @ Matrix.Translation((0.0, side * yc, 0.03 + (0.06 if seg else 0)))
                 @ S((0.20 - 0.05 * seg, (y1 - y0), 0.025, 1)))
            add(wing, mi, m)
    return bm


for name, (gpos, yaw, size) in GULLS.items():
    b = gull_bm()
    bmesh.ops.scale(b, vec=(size, size, size), verts=b.verts)
    pos = g2b(*gpos)
    top = g2b(gpos[0], WIRE_TOP, gpos[2])
    # Ursprung oben am Faden: Geometrie relativ dazu
    bmesh.ops.rotate(b, verts=b.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(yaw), 3, "Z"))
    bmesh.ops.translate(b, vec=pos - top, verts=b.verts)
    uv = b.loops.layers.uv.new("UVMap")
    for f in b.faces:
        for lp in f.loops:
            lp[uv].uv = (lp.vert.co.x, lp.vert.co.y)
    # selbst dreiecken: sonst wählt der Export bei den Polkappen der Kugeln je Lauf eine andere Reihenfolge
    bmesh.ops.triangulate(b, faces=b.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
    ob = make_object(name, b, [M["GullWhite"], M["GullGrey"], M["GullBeak"]])
    ob.location = top
    w = bmesh.new()
    bmesh.ops.create_cone(w, cap_ends=False, segments=5, radius1=0.006, radius2=0.006, depth=1.0)
    bmesh.ops.scale(w, vec=(1, 1, (top - pos).length - 0.12), verts=w.verts)
    bmesh.ops.translate(w, vec=(0, 0, -((top - pos).length - 0.12) / 2), verts=w.verts)
    w.loops.layers.uv.new("UVMap")
    wo = make_object(name + "Wire", w, [M["GullWire"]], parent=ob)
    wo.location = (0, 0, 0)

for o in bpy.data.objects:
    if o.type == "MESH" and o.name not in before:
        o.data.validate()

after = {o.name: tris(o) for o in bpy.data.objects if o.type == "MESH"}
bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", export_yup=True, export_apply=True,
                          export_cameras=False, export_lights=False, export_texcoords=True, export_normals=True,
                          export_extras=False, export_animations=False, use_selection=False)
print("DIORAMA " + json.dumps({"stats": {k: round(v, 3) if isinstance(v, float) else v for k, v in stats.items()},
                               "tris_total": sum(after.values()),
                               "objects": {k: [before.get(k), after[k]] for k in sorted(after)}}))
