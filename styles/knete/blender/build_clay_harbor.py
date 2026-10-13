# Knete: den gemeinsamen Hafen in ein Knetmodell umformen.
#
#   blender -b --factory-startup -P styles/knete/blender/build_clay_harbor.py -- \
#       shared/3d/harbor.glb styles/knete/demo/models/harbor_knete.glb [--preview OUT.png] [--only Name,Name]
#
# Schreibt zusätzlich <out>_path.json: Höhe der Knet-Pflasteroberfläche entlang des Laufwegs
# (Strahltests von oben), damit main.gd die Figur auf die tatsächliche, unebene Oberfläche stellt.
#
# Je Objekt (Tabelle CLAY unten):
#   remesh  Voxel-Remesh (verschmilzt Teile wie gedrückte Knete), glätten (runde Kanten),
#           Beulen per Rauschen entlang der Normale, Ausdünnen, Materialien vom nächsten
#           Originalpolygon zurückholen (Remesh behält nur ein Material), Box-UVs in Metern.
#   soft    Gelände (offene Höhenfelder, nicht remeshbar) und Taurolle: Catmull-Clark unterteilen (rundet
#           die Kanten der Low-Poly-Facetten), glätten, Beulen.
#   keep    unverändert (Glas: leuchtet nur).
#   drop    entfernen (IslandsFar liegt hinter dem Himmelsprospekt, das Meer baut Godot neu).
# Namen, Eltern, Empties und Lage bleiben erhalten. Deterministisch (Rauschen ohne Zufall).
import sys, math, bpy, bmesh
from mathutils import Vector, noise
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = argv[0], argv[1]
PREVIEW = argv[argv.index("--preview") + 1] if "--preview" in argv else None
ONLY = set(argv[argv.index("--only") + 1].split(",")) if "--only" in argv else None

# voxel: Kantenlänge der Voxel (m); smooth: Glättungsdurchgänge (Rundung etwa sqrt(n)*voxel);
# lump: Beulenhöhe (m) und Wellenlänge (m); keep_ratio: Anteil der Dreiecke nach dem Ausdünnen.
CLAY = {
    "Quay":       dict(mode="remesh", voxel=0.025, smooth=5, lump=(0.008, 0.45), keep_ratio=0.1),
    "Cottage":    dict(mode="remesh", voxel=0.03, smooth=5, lump=(0.012, 0.5), keep_ratio=0.15),
    "CrateStack": dict(mode="remesh", voxel=0.018, smooth=5, lump=(0.006, 0.25), keep_ratio=0.35),
    "Barrel1":    dict(mode="remesh", voxel=0.018, smooth=4, lump=(0.006, 0.25), keep_ratio=0.35),
    "Barrel2":    dict(mode="remesh", voxel=0.018, smooth=4, lump=(0.006, 0.25), keep_ratio=0.35),
    "BoatA":      dict(mode="remesh", voxel=0.022, smooth=4, lump=(0.008, 0.35), keep_ratio=0.2),
    "BoatB":      dict(mode="remesh", voxel=0.022, smooth=4, lump=(0.008, 0.35), keep_ratio=0.2),
    "Bollards":   dict(mode="remesh", voxel=0.012, smooth=4, lump=(0.004, 0.15), keep_ratio=0.4),
    "LanternPost": dict(mode="remesh", voxel=0.011, smooth=3, lump=(0.004, 0.18), keep_ratio=0.4),
    "Jetty":      dict(mode="remesh", voxel=0.02, smooth=4, lump=(0.006, 0.3), keep_ratio=0.15),
    "Lighthouse": dict(mode="remesh", voxel=0.04, smooth=4, lump=(0.02, 0.8), keep_ratio=0.2),
    "RocksSea":   dict(mode="remesh", voxel=0.05, smooth=6, lump=(0.05, 0.9), keep_ratio=0.2),
    "RopeCoil":   dict(mode="soft", subdiv=2, catmull=True, smooth=0, lump=(0.003, 0.12)),
    "Headland":   dict(mode="soft", subdiv=2, catmull=True, smooth=3, lump=(0.16, 2.0)),
    "WestHill":   dict(mode="soft", subdiv=2, catmull=True, smooth=3, lump=(0.16, 2.0)),
    "CottageWindow": dict(mode="keep"),
    "LanternGlass": dict(mode="keep"),
    "LighthouseLamp": dict(mode="keep"),
    "IslandsFar": dict(mode="drop"),
    "Sea":        dict(mode="drop"),
}


def lump_height(p, amp, wave):
    """Beulen aus zwei Oktaven Perlin-Rauschen im Objektraum (deterministisch)."""
    q = p / wave
    h = noise.noise(q) + 0.45 * noise.noise(q * 2.3 + Vector((17.1, 3.7, 9.2)))
    return amp * h


def box_uvs(bm):
    """UV in Metern aus der Hauptachse der Flächennormale (Godot braucht eine UV-Map)."""
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for l in f.loops:
            c = l.vert.co
            l[uv].uv = (c.y, c.z) if ax == 0 else ((c.x, c.z) if ax == 1 else (c.x, c.y))


def transfer_materials(ob, src_mesh):
    """Je neues Polygon das Material des nächstgelegenen Originalpolygons (gleicher Objektraum)."""
    verts = [v.co.copy() for v in src_mesh.vertices]
    polys = [tuple(p.vertices) for p in src_mesh.polygons]
    mats = [p.material_index for p in src_mesh.polygons]
    tree = BVHTree.FromPolygons(verts, polys)
    me = ob.data
    for p in me.polygons:
        loc, nor, idx, dist = tree.find_nearest(p.center)
        p.material_index = mats[idx] if idx is not None else 0


CUT_Z = -1.05   # Blender-z (= Godot-y): darunter liegt alles im undurchsichtigen Knetmeer


def close_open_parts(ob, thickness):
    """Unter dem Meer abschneiden, dann offene Teile schließen, damit das Voxel-Remesh sie als Körper
    erkennt (sonst verschwinden sie): große Teile (Kaiblock, Turmsockel) Löcher füllen, dünne Teile
    (Planken ohne Unterseite, Bodenbretter, Poller ohne Boden) nach innen aufdicken."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    if min(v.co.z for v in bm.verts) < CUT_Z:
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, CUT_Z), plane_no=(0, 0, 1),
                               clear_inner=True)
    bm.faces.ensure_lookup_table()
    seen, parts = set(), []
    for f0 in list(bm.faces):
        if f0.index in seen:
            continue
        stack, part = [f0], []
        seen.add(f0.index)
        while stack:
            f = stack.pop()
            part.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index not in seen:
                        seen.add(g.index)
                        stack.append(g)
        parts.append(part)
    n_fill = n_solid = 0
    for part in parts:
        bnd = list({e for f in part for e in f.edges if e.is_boundary})
        if not bnd:
            continue
        vs = [v.co for f in part for v in f.verts]
        dims = [max(v[i] for v in vs) - min(v[i] for v in vs) for i in range(3)]
        if min(dims) > 6 * thickness:
            res = bmesh.ops.holes_fill(bm, edges=bnd, sides=0)
            bmesh.ops.triangulate(bm, faces=res["faces"])
            n_fill += 1
        else:
            bmesh.ops.solidify(bm, geom=part, thickness=thickness)
            n_solid += 1
    bm.to_mesh(ob.data)
    bm.free()
    return n_fill, n_solid


def clayify(ob, cfg):
    src_mesh = ob.data.copy()
    bpy.context.view_layer.objects.active = ob
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    n0 = len(ob.data.polygons)
    if cfg["mode"] == "remesh":
        n_fill, n_solid = close_open_parts(ob, 2.5 * cfg["voxel"])
        if n_fill or n_solid:
            print(f"CLAY {ob.name:14s} offene Teile: {n_fill} gefüllt, {n_solid} aufgedickt")
        m = ob.modifiers.new("Remesh", "REMESH")
        m.mode = "VOXEL"
        m.voxel_size = cfg["voxel"]
        m.adaptivity = 0.0
        m.use_smooth_shade = True
        bpy.ops.object.modifier_apply(modifier=m.name)
    else:
        m = ob.modifiers.new("Subdiv", "SUBSURF")
        m.subdivision_type = "CATMULL_CLARK" if cfg.get("catmull") else "SIMPLE"
        m.levels = cfg["subdiv"]
        m.render_levels = cfg["subdiv"]
        bpy.ops.object.modifier_apply(modifier=m.name)
    if cfg.get("smooth"):
        m = ob.modifiers.new("Smooth", "LAPLACIANSMOOTH")
        m.iterations = cfg["smooth"]
        m.lambda_factor = 0.8
        m.lambda_border = 0.0          # Ränder offener Gelände-Flächen festhalten
        m.use_volume_preserve = True
        m.use_normalized = True
        bpy.ops.object.modifier_apply(modifier=m.name)
    # Beulen entlang der (geglätteten) Vertexnormalen
    amp, wave = cfg["lump"]
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.normal_update()
    offs = [lump_height(v.co, amp, wave) for v in bm.verts]
    for v, d in zip(bm.verts, offs):
        if cfg["mode"] == "soft" and v.is_boundary:
            continue
        v.co += v.normal * d
    bm.to_mesh(ob.data)
    bm.free()
    if cfg["mode"] == "remesh" and cfg.get("keep_ratio", 1.0) < 1.0:
        m = ob.modifiers.new("Decimate", "DECIMATE")
        m.decimate_type = "COLLAPSE"
        m.ratio = cfg["keep_ratio"]
        bpy.ops.object.modifier_apply(modifier=m.name)
    # Materialien zurück (Remesh behält nur das erste)
    ob.data.materials.clear()
    for mat in src_mesh.materials:
        ob.data.materials.append(mat)
    transfer_materials(ob, src_mesh)
    for p in ob.data.polygons:
        p.use_smooth = True
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    for l in list(bm.loops.layers.uv):
        bm.loops.layers.uv.remove(l)
    box_uvs(bm)
    bm.to_mesh(ob.data)
    bm.free()
    bpy.data.meshes.remove(src_mesh)
    n1 = len(ob.data.polygons)
    print(f"CLAY {ob.name:14s} {cfg['mode']:6s} Polygone {n0:6d} -> {n1:6d}")


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=SRC)
    for ob in list(bpy.data.objects):
        if ob.type != "MESH":
            continue
        cfg = CLAY.get(ob.name)
        if cfg is None:
            raise SystemExit(f"Objekt {ob.name} fehlt in CLAY")
        if cfg["mode"] == "drop":
            bpy.data.objects.remove(ob, do_unlink=True)
            continue
        if cfg["mode"] == "keep" or (ONLY and ob.name not in ONLY):
            continue
        clayify(ob, cfg)
    # Hilfsobjekt der Knochenanzeige o. Ä. nicht exportieren
    for ob in list(bpy.data.objects):
        if ob.name.startswith("Icosphere"):
            bpy.data.objects.remove(ob, do_unlink=True)
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in bpy.data.objects if o.type == "MESH")
    print(f"CLAY Summe Dreiecke: {tris}")
    bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", export_yup=True, export_apply=True,
                              export_cameras=False, export_lights=False, export_normals=True,
                              export_tangents=False, export_texcoords=True, export_materials="EXPORT")
    write_path_heights(OUT.replace(".glb", "_path.json"))
    if PREVIEW:
        render_preview(PREVIEW)


def write_path_heights(path):
    """Oberkante des Pflasters unter beiden Fußlinien (Godot z = 0,95 ± 0,125) für x = -4..1 m."""
    import json
    dg = bpy.context.evaluated_depsgraph_get()
    sc = bpy.context.scene
    xs = [round(-4.0 + i * 0.02, 3) for i in range(251)]
    rows = {}
    for zg in (0.825, 0.95, 1.075):
        hs = []
        for x in xs:
            hit, loc, n, idx, ob, m = sc.ray_cast(dg, Vector((x, -zg, 2.0)), Vector((0, 0, -1)))
            hs.append(round(loc.z, 4) if hit else None)
        rows[str(zg)] = hs
    with open(path, "w") as f:
        json.dump({"x": xs, "z_lines": rows, "note": "Godot-y der Oberkante, Strahltest von oben"}, f)
    print(f"CLAY Laufweg-Höhen: {path}")


def render_preview(path):
    """Schnelle EEVEE-Vorschau aus der Demo-Kamera (Godot (-0.6, 0.9, 5.15), rot (6, -10, 0), fov 42)."""
    sc = bpy.context.scene
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.sensor_fit = "VERTICAL"
    cam_data.sensor_height = 24.0
    cam_data.lens = 12.0 / math.tan(math.radians(21.0))
    cam_data.clip_start, cam_data.clip_end = 0.1, 500.0
    cam = bpy.data.objects.new("Cam", cam_data)
    sc.collection.objects.link(cam)
    cam.location = (-0.6, -5.15, 0.9)
    cam.rotation_euler = (math.radians(96.0), 0.0, math.radians(-10.0))
    sc.camera = cam
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 3.0
    sun.data.angle = math.radians(12.0)
    sun.rotation_euler = (math.radians(55), 0, math.radians(-40))
    sc.collection.objects.link(sun)
    world = bpy.data.worlds.new("W")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.35, 0.4, 0.55, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.6
    sc.world = world
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = 1280, 720
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


main()
