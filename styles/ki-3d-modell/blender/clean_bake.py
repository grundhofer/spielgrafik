# TripoSR-Mesh säubern, aufrichten, dezimieren, Textur backen, als glb exportieren.
#
#   blender -b --factory-startup -P styles/ki-3d-modell/blender/clean_bake.py -- \
#       --dir styles/ki-3d-modell/work/tsr/barrel --name Barrel --height 0.9 --tris 4000 \
#       --tilt foot --out styles/ki-3d-modell/demo/models/barrel_tsr.glb --tex-out styles/ki-3d-modell/assets/barrel_tex.png
#
# Eingaben aus --dir (von scripts/tsr_run.py und scripts/fit_projection.py):
#   mesh.ply        Marching-Cubes-Mesh von TripoSR mit Eckpunktfarben (Kamerarahmen: vorn +X, oben +Z)
#   input_rgba.png  das Bild, das TripoSR gesehen hat (quadratisch, Vordergrund 85 %)
#   proj.json       Projektion dieses Bildes auf das Mesh (D, k, cx, cy)
#
# Schritte: Schwebeteile entfernen -> Projektion der Vorderansicht als UV "proj" + Gewicht "projw"
# (zugewandt und sichtbar) -> aufrichten (TripoSR rekonstruiert im Blickwinkel des Bildes, Aufsicht = schief)
# -> auf echte Höhe skalieren, Ursprung unten Mitte -> Kopie glätten und dezimieren, Normalen, Smart-UV
# -> Cycles-Bake EMIT (selected to active): Farbe = Mischung aus Eckpunktfarbe und projiziertem Bild
# -> glb mit eingebetteter Textur. Bericht als <out>.json (bzw. --report).
import bpy, bmesh, json, math, os, sys, time
import numpy as np
import mathutils
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
import argparse
ap = argparse.ArgumentParser(prog="clean_bake.py")
ap.add_argument("--dir", required=True)
ap.add_argument("--name", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--tex-out", required=True)
ap.add_argument("--report", default="")
ap.add_argument("--height", type=float, default=0.0, help="Höhe in m nach dem Aufrichten")
ap.add_argument("--length", type=float, default=0.0, help="statt --height: Länge in x (m) nach dem Drehen")
ap.add_argument("--tris", type=int, default=5000)
ap.add_argument("--tex", type=int, default=1024)
ap.add_argument("--tilt", default="foot", help="foot | flat | <Grad>")
ap.add_argument("--tilt-range", type=float, default=45.0)
ap.add_argument("--yaw", default="0", help="auto (lange Achse nach X) | <Grad> um Z nach dem Aufrichten")
ap.add_argument("--min-part", type=float, default=0.004, help="Teile unter diesem Anteil der Flächen weg")
ap.add_argument("--no-project", action="store_true", help="nur Eckpunktfarben backen")
ap.add_argument("--vc-tex-out", default="", help="zusätzlich nur Eckpunktfarben backen (Vergleich)")
ap.add_argument("--smooth", type=int, default=2, help="Glättungsschritte vor dem Dezimieren")
ap.add_argument("--sharp", type=float, default=50.0, help="Kantenwinkel für harte Kanten (Grad)")
ap.add_argument("--origin", default="bottom", help="bottom (Mitte der Grundfläche) | feet (Mitte der unteren 8 %)")
ap.add_argument("--roughness", type=float, default=0.8)
ap.add_argument("--bridge", action="store_true", help="lose Teile (z. B. Laterne ohne Kette) mit einem "
                "dunklen Stab nach oben an das Hauptteil hängen")
ap.add_argument("--squash-back", default="", help="x0,zmax,f: hinter x0 (m, nach Aufrichten) und unter zmax "
                "Abstand nach hinten mit f multiplizieren (geratenen Schwanz zurückdrücken)")
A = ap.parse_args(argv)

T0 = time.time()
R = {"name": A.name, "dir": A.dir}


def log(*a):
    print("[clean_bake]", *a, flush=True)


def np_verts(me):
    v = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get("co", v)
    return v.reshape(-1, 3)


def np_tris(me):
    me.calc_loop_triangles()
    t = np.empty(len(me.loop_triangles) * 3, np.int64)
    me.loop_triangles.foreach_get("vertices", t)
    return t.reshape(-1, 3)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ Import
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.ply_import(filepath=os.path.join(A.dir, "mesh.ply"), import_colors="SRGB")
hi = bpy.context.selected_objects[0]
hi.name = A.name + "_hi"
me = hi.data
R["input_faces"] = len(me.polygons)
R["input_vertices"] = len(me.vertices)
col_name = me.color_attributes[0].name if len(me.color_attributes) else None
assert col_name, "PLY ohne Eckpunktfarben"

# ------------------------------------------------------------------ Schwebeteile entfernen
bm = bmesh.new()
bm.from_mesh(me)
bm.verts.ensure_lookup_table()
seen = set()
parts = []
for f in bm.faces:
    if f.index in seen:
        continue
    stack, comp = [f], []
    seen.add(f.index)
    while stack:
        g = stack.pop()
        comp.append(g)
        for e in g.edges:
            for h in e.link_faces:
                if h.index not in seen:
                    seen.add(h.index)
                    stack.append(h)
    parts.append(comp)
parts.sort(key=len, reverse=True)
big = len(parts[0])
drop = [p for p in parts if len(p) < A.min_part * big]
R["components"] = [len(p) for p in parts[:12]]
R["components_removed"] = len(drop)
R["faces_removed"] = sum(len(p) for p in drop)
dverts = set()
for p in drop:
    for f in p:
        dverts.update(v.index for v in f.verts)
bmesh.ops.delete(bm, geom=[bm.verts[i] for i in dverts], context="VERTS")
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(me)
bm.free()
me.update()

# ------------------------------------------------------------------ Projektion der Vorderansicht (Rohkoordinaten)
img_path = os.path.join(A.dir, "input_rgba.png")
src_img = bpy.data.images.load(img_path)
src_img.colorspace_settings.name = "sRGB"
P = json.load(open(os.path.join(A.dir, "proj.json")))
D, k, cx, cy = P["D"], P["k_norm"], P["cx_norm"], P["cy_norm"]
V = np_verts(me)
N = np.empty(len(me.vertices) * 3)
me.vertex_normals.foreach_get("vector", N)
N = N.reshape(-1, 3)
depth = D - V[:, 0]
u = cx + k * V[:, 1] / depth
vimg = cy - k * V[:, 2] / depth
C = np.array([D, 0.0, 0.0])
to_c = C - V
dist = np.linalg.norm(to_c, axis=1)
to_c /= dist[:, None]
facing = (N * to_c).sum(1)
# Sichtbarkeit: Strahl vom Punkt zur Kamera
bvh = BVHTree.FromPolygons([tuple(v) for v in V], [tuple(p.vertices) for p in me.polygons], all_triangles=True)
vis = np.zeros(len(V))
eps = 0.004
for i in np.where(facing > 0.05)[0]:
    o = mathutils.Vector(V[i] + to_c[i] * eps)
    hit = bvh.ray_cast(o, mathutils.Vector(to_c[i]), dist[i])
    vis[i] = 0.0 if hit[0] is not None else 1.0
# Alpha des Eingabebilds an der Stelle (Ränder und Löcher nicht projizieren)
w_img, h_img = src_img.size
px = np.empty(w_img * h_img * 4, np.float32)
src_img.pixels.foreach_get(px)
px = px.reshape(h_img, w_img, 4)[::-1]          # Blender: Zeile 0 unten -> umdrehen
xi = np.clip((u * w_img).astype(int), 0, w_img - 1)
yi = np.clip((vimg * h_img).astype(int), 0, h_img - 1)
alpha = px[yi, xi, 3]
w = vis * smoothstep(0.15, 0.5, facing) * smoothstep(0.6, 0.95, alpha)
if A.no_project:
    w[:] = 0.0
R["projected_share"] = round(float((w > 0.5).mean()), 3)
R["projection"] = {k_: P[k_] for k_ in ("D", "iou", "iou_default_1.9m_40deg")}
at = me.attributes.new("projw", "FLOAT", "POINT")
at.data.foreach_set("value", w.astype(np.float32))
uvl = me.uv_layers.new(name="proj")
lv = np.empty(len(me.loops), np.int64)
me.loops.foreach_get("vertex_index", lv)
uv = np.stack([u[lv], 1.0 - vimg[lv]], 1).astype(np.float32)
uvl.data.foreach_set("uv", uv.ravel())

# ------------------------------------------------------------------ Aufrichten, Maßstab, Ursprung
V = np_verts(me)
F = np_tris(me)
tri = V[F]
nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
area = 0.5 * np.linalg.norm(nrm, axis=1)
nrm /= (2 * area[:, None] + 1e-12)
cen = tri.mean(1)


def rot_z(a, X):   # z-Koordinate nach Drehung um Y (Blender-Konvention: x' = c x + s z, z' = -s x + c z)
    return -math.sin(a) * X[:, 0] + math.cos(a) * X[:, 2]


if A.tilt in ("foot", "flat"):
    best = None
    for deg in np.arange(-A.tilt_range, A.tilt_range + 0.01, 0.5):
        a = math.radians(deg)
        z = rot_z(a, V)
        if A.tilt == "foot":           # größte ebene Standfläche unten
            nz, cz = rot_z(a, nrm), rot_z(a, cen)
            H = z.max() - z.min()
            score = area[(nz < -0.97) & (cz < z.min() + 0.02 * H)].sum()
        else:                          # flachste Lage (robuste Höhe 1.–99. Perzentil)
            score = -(np.percentile(z, 99) - np.percentile(z, 1))
        if best is None or score > best[0]:
            best = (score, deg)
    tilt = best[1]
else:
    tilt = float(A.tilt)
R["tilt_deg"] = tilt
M = mathutils.Matrix.Rotation(math.radians(tilt), 4, "Y")
me.transform(M)
V = np_verts(me)
if A.yaw == "sym":
    # Figur im Halbprofil: Drehung um Z, bei der die Figur am besten spiegelsymmetrisch zur XZ-Ebene ist
    from mathutils.kdtree import KDTree
    rng = np.random.default_rng(1)
    sub = V[rng.choice(len(V), min(6000, len(V)), replace=False)]
    best = None
    for deg in np.arange(-70, 70.1, 1.0):
        a = math.radians(deg)
        c_, s_ = math.cos(a), math.sin(a)
        Q = np.stack([c_ * sub[:, 0] - s_ * sub[:, 1], s_ * sub[:, 0] + c_ * sub[:, 1], sub[:, 2]], 1)
        Q[:, 1] -= 0.5 * (Q[:, 1].min() + Q[:, 1].max())
        kd = KDTree(len(Q))
        for i_, q in enumerate(Q):
            kd.insert(q, i_)
        kd.balance()
        err = np.mean([kd.find((q[0], -q[1], q[2]))[2] for q in Q])
        if best is None or err < best[0]:
            best = (err, deg)
    yaw = best[1]
    R["yaw_sym_err"] = round(float(best[0]), 5)
elif A.yaw == "auto":
    xy = V[:, :2] - V[:, :2].mean(0)
    ev, evec = np.linalg.eigh(np.cov(xy.T))
    ax = evec[:, np.argmax(ev)]
    yaw = -math.degrees(math.atan2(ax[1], ax[0]))
else:
    yaw = float(A.yaw)
R["yaw_deg"] = round(yaw, 2)
me.transform(mathutils.Matrix.Rotation(math.radians(yaw), 4, "Z"))
V = np_verts(me)
s = A.height / (V[:, 2].max() - V[:, 2].min()) if A.height else A.length / (V[:, 0].max() - V[:, 0].min())
if A.origin == "feet":
    low = V[V[:, 2] < V[:, 2].min() + 0.08 * (V[:, 2].max() - V[:, 2].min())]
    c_xy = 0.5 * (low[:, :2].min(0) + low[:, :2].max(0))
else:
    c_xy = 0.5 * (V[:, :2].min(0) + V[:, :2].max(0))
me.transform(mathutils.Matrix.Scale(s, 4) @ mathutils.Matrix.Translation((-c_xy[0], -c_xy[1], -V[:, 2].min())))
me.update()
R["scale"] = round(s, 4)
if A.squash_back:
    x0, zmax, fac = map(float, A.squash_back.split(","))
    V = np_verts(me)
    sel = V[:, 0] < x0
    wz = smoothstep(zmax, zmax - 0.08, V[:, 2])          # nach oben weich auslaufen
    nx = np.where(sel, x0 + (V[:, 0] - x0) * (1 - (1 - fac) * wz), V[:, 0])
    R["squash_back"] = {"x0": x0, "zmax": zmax, "f": fac, "vertices": int(sel.sum()),
                        "x_min_before": round(float(V[:, 0].min()), 3), "x_min_after": round(float(nx.min()), 3)}
    V[:, 0] = nx
    me.vertices.foreach_set("co", V.ravel())
    me.update()
V = np_verts(me)
R["size_m"] = [round(float(x), 3) for x in (V.max(0) - V.min(0))]

# ------------------------------------------------------------------ Lose Teile anhängen (--bridge)
# TripoSR verliert dünne Teile (Kettenglieder werden Splitter und fallen oben weg). Ein loses Teil, das unter
# dem Hauptteil hängt (Laterne unter dem Ausleger), wird waagerecht unter den Ausleger geschoben und bekommt
# später in der niedrigen Fassung einen senkrechten Stab bis zur Unterkante des Auslegers.
rods = []
if A.bridge:
    bmb = bmesh.new()
    bmb.from_mesh(me)
    bmb.faces.ensure_lookup_table()
    seen, comps = set(), []
    for f in bmb.faces:
        if f.index in seen:
            continue
        stack, cv = [f], set()
        seen.add(f.index)
        while stack:
            g = stack.pop()
            cv.update(v.index for v in g.verts)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index)
                        stack.append(h)
        comps.append(sorted(cv))
    bmb.free()
    comps.sort(key=len, reverse=True)
    V = np_verts(me)
    M_ = V[comps[0]]
    R["bridges"] = []
    for cv in comps[1:]:
        if len(cv) < 0.02 * len(comps[0]):
            continue
        P_ = V[cv]
        top = P_[P_[:, 2] > P_[:, 2].max() - 0.01 * A.height].mean(0)
        top[2] = P_[:, 2].max()
        band = M_[(M_[:, 2] > top[2] + 0.03) & (M_[:, 2] < top[2] + 0.6)]
        slab = band[np.abs(band[:, 1] - top[1]) < 0.05]
        if len(slab) < 5:
            continue
        hang = np.array([0.5 * (slab[:, 0].min() + slab[:, 0].max()), top[1], slab[:, 2].min()])
        shift = np.array([hang[0] - top[0], 0.0, 0.0])
        V[cv] += shift
        rods.append((mathutils.Vector(top + shift - [0, 0, 0.03]), mathutils.Vector(hang + [0, 0, 0.03])))
        R["bridges"].append({"part_vertices": len(cv), "shift_m": [round(float(x), 3) for x in shift],
                             "rod_m": round(float(hang[2] - top[2]), 3)})
    me.vertices.foreach_set("co", V.ravel())
    me.update()

# ------------------------------------------------------------------ Niedrige Fassung
lo = hi.copy()
lo.data = hi.data.copy()
lo.name = lo.data.name = A.name
bpy.context.collection.objects.link(lo)
for ob in (hi, lo):
    ob.select_set(False)
bpy.context.view_layer.objects.active = lo
lo.select_set(True)
if A.smooth:
    m = lo.modifiers.new("Smooth", "SMOOTH")
    m.factor, m.iterations = 0.5, A.smooth
    bpy.ops.object.modifier_apply(modifier=m.name)
m = lo.modifiers.new("Decimate", "DECIMATE")
m.decimate_type = "COLLAPSE"
m.ratio = min(1.0, A.tris / max(len(lo.data.polygons), 1))
m.use_collapse_triangulate = True
bpy.ops.object.modifier_apply(modifier=m.name)
ld = lo.data
if A.bridge:
    bmb = bmesh.new()
    bmb.from_mesh(ld)
    for a_, b_ in rods:
        bmesh.ops.create_cone(bmb, cap_ends=True, segments=8, radius1=0.011 * A.height, radius2=0.011 * A.height,
                              depth=(b_ - a_).length, matrix=mathutils.Matrix.Translation((a_ + b_) / 2))
    bmb.to_mesh(ld)
    bmb.free()
    ld.update()
for ca in list(ld.color_attributes):
    ld.color_attributes.remove(ca)
for name in ("projw",):
    if name in ld.attributes:
        ld.attributes.remove(ld.attributes[name])
while len(ld.uv_layers):
    ld.uv_layers.remove(ld.uv_layers[0])
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.shade_smooth_by_angle(angle=math.radians(A.sharp))
ld.uv_layers.new(name="UVMap")
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.004, area_weight=0.0)
bpy.ops.object.mode_set(mode="OBJECT")
R["tris"] = sum(len(p.vertices) - 2 for p in ld.polygons)
R["vertices"] = len(ld.vertices)

# ------------------------------------------------------------------ Bake
sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = 4
sc.render.bake.margin = 16
sc.render.bake.margin_type = "EXTEND"

hm = bpy.data.materials.new(A.name + "_src")
hm.use_nodes = True
nt = hm.node_tree
nt.nodes.clear()
n_vc = nt.nodes.new("ShaderNodeVertexColor"); n_vc.layer_name = col_name
n_uv = nt.nodes.new("ShaderNodeUVMap"); n_uv.uv_map = "proj"
n_im = nt.nodes.new("ShaderNodeTexImage"); n_im.image = src_img; n_im.extension = "EXTEND"
n_w = nt.nodes.new("ShaderNodeAttribute"); n_w.attribute_name = "projw"; n_w.attribute_type = "GEOMETRY"
n_mix = nt.nodes.new("ShaderNodeMix"); n_mix.data_type = "RGBA"
n_em = nt.nodes.new("ShaderNodeEmission")
n_out = nt.nodes.new("ShaderNodeOutputMaterial")
sock = lambda node, ident, out=False: [s_ for s_ in (node.outputs if out else node.inputs) if s_.identifier == ident][0]
nt.links.new(n_uv.outputs["UV"], n_im.inputs["Vector"])
nt.links.new(n_w.outputs["Fac"], sock(n_mix, "Factor_Float"))
nt.links.new(n_vc.outputs["Color"], sock(n_mix, "A_Color"))
nt.links.new(n_im.outputs["Color"], sock(n_mix, "B_Color"))
nt.links.new(sock(n_mix, "Result_Color", True), n_em.inputs["Color"])
nt.links.new(n_em.outputs["Emission"], n_out.inputs["Surface"])
hi.data.materials.clear()
hi.data.materials.append(hm)

lm = bpy.data.materials.new(A.name)
lm.use_nodes = True
lt = lm.node_tree
bsdf = lt.nodes.get("Principled BSDF")
tex_img = bpy.data.images.new(A.name + "_tex", A.tex, A.tex, alpha=False)
tex_img.generated_color = (0.045, 0.04, 0.038, 1.0)   # ungebackene Stellen (Stab) = dunkles Eisen
tex_img.colorspace_settings.name = "sRGB"
n_t = lt.nodes.new("ShaderNodeTexImage")
n_t.image = tex_img
lt.links.new(n_t.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = A.roughness
bsdf.inputs["Specular IOR Level"].default_value = 0.25
lt.nodes.active = n_t
ld.materials.clear()
ld.materials.append(lm)

size = max(R["size_m"])


def bake(path):
    bpy.ops.object.select_all(action="DESELECT")
    hi.select_set(True)
    lo.select_set(True)
    bpy.context.view_layer.objects.active = lo
    t = time.time()
    bpy.ops.object.bake(type="EMIT", use_selected_to_active=True, cage_extrusion=0.02 * size,
                        max_ray_distance=0.06 * size, margin=16)
    tex_img.filepath_raw = os.path.abspath(path)
    tex_img.file_format = "PNG"
    tex_img.save()
    return round(time.time() - t, 2)


if A.vc_tex_out:
    n_w.attribute_name = "projw_none"      # fehlendes Attribut = 0 -> nur Eckpunktfarben
    R["t_bake_vc"] = bake(A.vc_tex_out)
    n_w.attribute_name = "projw"
R["t_bake"] = bake(A.tex_out)
tex_img.filepath_raw = os.path.abspath(A.tex_out)
tex_img.reload()

# ------------------------------------------------------------------ Export
bpy.ops.object.select_all(action="DESELECT")
lo.select_set(True)
bpy.context.view_layer.objects.active = lo
os.makedirs(os.path.dirname(os.path.abspath(A.out)), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=os.path.abspath(A.out), export_format="GLB", use_selection=True,
                          export_yup=True, export_apply=True, export_texcoords=True, export_normals=True,
                          export_materials="EXPORT", export_image_format="AUTO", export_cameras=False,
                          export_lights=False, export_extras=False, export_animations=False)
R["glb_bytes"] = os.path.getsize(A.out)
R["t_total"] = round(time.time() - T0, 2)
rep = A.report or os.path.splitext(A.out)[0] + ".json"
with open(rep, "w") as fh:
    json.dump(R, fh, indent=1)
log(json.dumps(R))
