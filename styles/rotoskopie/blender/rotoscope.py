# -*- coding: utf-8 -*-
"""Rotoskopie-Vorlage: der geriggte Dachs aus shared/3d in der Seitenansicht, je Pose drei Datenpässe.

Aufruf (aus dem Projektordner):
  blender -b --factory-startup -P styles/rotoskopie/blender/rotoscope.py -- \
      --glb shared/3d/badger.glb --out <scratch>/rotoskopie/passes [--ppm 600] [--only walk,give] [--preview]

Posen (Seitenansicht, Blick nach +X = rechts, Paketseite zur Kamera):
  walk_0 … walk_7  Walk (1,0 s) bei t = k/8 s, auf der Stelle (die Figur rückt in Godot mit 0,367 m/s vor)
  give_0 … give_5  „Paket überreichen“: Idle t = 0, danach Knochen per Skript gedreht (GIVE unten)

Je Pose (in Renderauflösung, ohne Kantenglättung, Raw-Farbraum):
  <pose>_id.png     R = Materialnummer × 16, G = 128 auf der abgewandten Körperseite (Blender y > FAR_Y,
                    Bein, Arm und Fuß links), B = 128 an den Pfoten (Handgewicht > 0,5)
  <pose>_z.png      16-bit-Kameratiefe, linear auf Z_NEAR … Z_NEAR + Z_RANGE
  <pose>_light.png  Lambert-Licht max(N·L, 0) für die eine harte Schattenstufe des klassischen Wegs
Dazu passes.json: Maßstab, Ursprung (Fußpunkt der Figur) im Bild und je Pose die 3D-Messpunkte als Pixel:
Ferse/Zehe beider Füße (Knochen), tiefster Sohlenpunkt je Fuß (verformtes Mesh), Kopfknochen, Pfote rechts,
Paketmitte. Mit --preview statt der Pässe ein schattiertes Kontrollbild je Pose (Gestaltung der Geste).

Rundung der Konturen wie in styles/ligne-claire/blender/render_badger.py: Dreiecke zu Vierecken, Smooth
Shading, Subdivision Surface hinter dem Armature-Modifier.
"""
import argparse, json, math, pathlib, sys

import bmesh
import bpy
from mathutils import Matrix, Vector
from bpy_extras.object_utils import world_to_camera_view

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--glb", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--ppm", type=float, default=600.0, help="Pixel pro Meter im Render")
ap.add_argument("--only", default="walk,give")
ap.add_argument("--subsurf", type=int, default=1)
ap.add_argument("--preview", action="store_true")
a = ap.parse_args(argv)

out = pathlib.Path(a.out)
out.mkdir(parents=True, exist_ok=True)

MATS = ["FurDark", "FurLight", "Cap", "Brass", "Vest", "Shirt", "Scarf", "Satchel", "Parcel", "Nose", "Eye"]
FAR_Y = 0.07          # Blender +Y = linke Körperseite (Godot -Z), von der Kamera abgewandt
LIGHT = Vector((-0.45, -0.55, 0.70)).normalized()   # Licht von links oben vorn (zur Kamera hin)

# Geste „Paket überreichen“ (Seitenansicht). Drehungen um die Welt-Y-Achse (Blender), in Grad:
# negativ = Arm nach vorn/oben schwingen, positiv beim Rumpf = nach vorn neigen. Reihenfolge Eltern vor Kind.
GIVE = [
    [],                                                                     # 0 Stand (Idle t = 0)
    [("spine", -4), ("head", -4), ("upper_arm.R", -25), ("forearm.R", 0), ("hand.R", 15),
     ("upper_arm.L", -10)],                                                 # 1 Ausholen: Paket löst sich
    [("spine", 3), ("chest", 2), ("upper_arm.R", -58), ("forearm.R", 10), ("hand.R", 24),
     ("upper_arm.L", -22), ("forearm.L", -10)],                             # 2 Paket kommt nach vorn
    [("spine", 8), ("chest", 4), ("head", 3), ("upper_arm.R", -84), ("forearm.R", 18), ("hand.R", 44),
     ("upper_arm.L", -34), ("forearm.L", -18)],                             # 3 ausgestreckt
    [("spine", 13), ("chest", 6), ("head", 10), ("upper_arm.R", -88), ("forearm.R", 20), ("hand.R", 46),
     ("upper_arm.L", -38), ("forearm.L", -20)],                             # 4 Verbeugung beim Überreichen
    [("spine", 7), ("chest", 3), ("head", -6), ("upper_arm.R", -86), ("forearm.R", 19), ("hand.R", 45),
     ("upper_arm.L", -36), ("forearm.L", -19)],                             # 5 aufschauen, Paket hingehalten
]


def lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = 30                       # vor dem Import: Aktionen in 30 fps
bpy.ops.import_scene.gltf(filepath=str(pathlib.Path(a.glb).resolve()), merge_vertices=a.subsurf > 0)
for ob in list(bpy.data.objects):
    if ob.name.startswith("Icosphere"):
        bpy.data.objects.remove(ob)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
meshes = [o for o in bpy.data.objects if o.type == "MESH"]

# Pfotengewicht als Punktattribut (Linie am Handgelenk im klassischen Weg)
for ob in meshes:
    if "hand.L" not in ob.vertex_groups:
        continue
    gi = {ob.vertex_groups[n].index for n in ("hand.L", "hand.R") if n in ob.vertex_groups}
    w = [min(1.0, sum(g.weight for g in v.groups if g.group in gi)) for v in ob.data.vertices]
    at = ob.data.attributes.new("hand_w", "FLOAT", "POINT")
    at.data.foreach_set("value", w)

if a.subsurf > 0:
    for ob in meshes:
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bmesh.ops.join_triangles(bm, faces=bm.faces[:], cmp_materials=True, cmp_seam=False, cmp_sharp=False,
                                 cmp_uvs=False, cmp_vcols=False, angle_face_threshold=math.radians(40),
                                 angle_shape_threshold=math.radians(40))
        bm.to_mesh(ob.data)
        bm.free()
        ob.data.shade_smooth()
        sub = ob.modifiers.new("Subdivision", "SUBSURF")
        sub.levels = sub.render_levels = a.subsurf


def new_mat(name):
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    return m, nt, o


# ID-Material je Originalmaterial: R = Nummer, G = abgewandte Seite, B = Pfote
id_mats = {}
for i, name in enumerate(MATS):
    m, nt, o = new_mat("ID_" + name)
    em = nt.nodes.new("ShaderNodeEmission")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    far = nt.nodes.new("ShaderNodeMath"); far.operation = "GREATER_THAN"; far.inputs[1].default_value = FAR_Y
    farv = nt.nodes.new("ShaderNodeMath"); farv.operation = "MULTIPLY"; farv.inputs[1].default_value = 128 / 255
    attr = nt.nodes.new("ShaderNodeAttribute"); attr.attribute_name = "hand_w"
    paw = nt.nodes.new("ShaderNodeMath"); paw.operation = "GREATER_THAN"; paw.inputs[1].default_value = 0.5
    pawv = nt.nodes.new("ShaderNodeMath"); pawv.operation = "MULTIPLY"; pawv.inputs[1].default_value = 128 / 255
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    comb.inputs[0].default_value = (i + 1) * 16 / 255
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    nt.links.new(sep.outputs["Y"], far.inputs[0])
    nt.links.new(far.outputs[0], farv.inputs[0])
    nt.links.new(farv.outputs[0], comb.inputs[1])
    nt.links.new(attr.outputs["Fac"], paw.inputs[0])
    nt.links.new(paw.outputs[0], pawv.inputs[0])
    nt.links.new(pawv.outputs[0], comb.inputs[2])
    nt.links.new(comb.outputs[0], em.inputs["Color"])
    nt.links.new(em.outputs[0], o.inputs[0])
    id_mats[name] = m

# Tiefe (Kameraabstand) und Licht als Override-Materialien
D_CAM = 20.0
Z_NEAR, Z_RANGE = D_CAM - 1.0, 2.0
zmat, znt, zo = new_mat("DepthPass")
zem = znt.nodes.new("ShaderNodeEmission")
cd = znt.nodes.new("ShaderNodeCameraData")
mr = znt.nodes.new("ShaderNodeMapRange")
mr.inputs["From Min"].default_value = Z_NEAR
mr.inputs["From Max"].default_value = Z_NEAR + Z_RANGE
znt.links.new(cd.outputs["View Z Depth"], mr.inputs["Value"])
znt.links.new(mr.outputs["Result"], zem.inputs["Color"])
znt.links.new(zem.outputs[0], zo.inputs[0])

lmat, lnt, lo = new_mat("LightPass")
lem = lnt.nodes.new("ShaderNodeEmission")
lgeo = lnt.nodes.new("ShaderNodeNewGeometry")
dot = lnt.nodes.new("ShaderNodeVectorMath"); dot.operation = "DOT_PRODUCT"
dot.inputs[1].default_value = LIGHT
mx = lnt.nodes.new("ShaderNodeMath"); mx.operation = "MAXIMUM"; mx.inputs[1].default_value = 0.0
lnt.links.new(lgeo.outputs["Normal"], dot.inputs[0])
lnt.links.new(dot.outputs["Value"], mx.inputs[0])
lnt.links.new(mx.outputs[0], lem.inputs["Color"])
lnt.links.new(lem.outputs[0], lo.inputs[0])

orig = {}
for ob in meshes:
    orig[ob.name] = [s.material for s in ob.material_slots]


def use_materials(kind):
    for ob in meshes:
        for s, m0 in zip(ob.material_slots, orig[ob.name]):
            base = m0.name.split(".")[0]
            s.material = id_mats[base] if kind == "id" else m0


scene.world = bpy.data.worlds.new("W")
scene.world.color = (0, 0, 0)
scene.render.engine = "BLENDER_EEVEE"
scene.render.film_transparent = True
scene.render.image_settings.file_format = "PNG"

# Kamera: orthografisch, Blick von -Y nach +Y (Godot: von +Z), waagerecht (reine Seitenansicht)
X0, X1, Z0, Z1 = -0.50, 0.80, -0.06, 1.12     # Bildfeld in Metern (alle Posen passen hinein)
res_x, res_y = round((X1 - X0) * a.ppm), round((Z1 - Z0) * a.ppm)
scene.render.resolution_x, scene.render.resolution_y = res_x, res_y
scene.render.resolution_percentage = 100
cam_data = bpy.data.cameras.new("Cam")
cam_data.type = "ORTHO"
cam_data.sensor_fit = "HORIZONTAL"
cam_data.ortho_scale = X1 - X0
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
cam.location = Vector(((X0 + X1) / 2, -D_CAM, (Z0 + Z1) / 2))
cam.rotation_euler = (math.pi / 2, 0, 0)
cam_data.clip_start, cam_data.clip_end = 0.1, 100.0
bpy.context.view_layer.update()


def project(p):
    v = world_to_camera_view(scene, cam, p)
    return [round(v.x * res_x, 2), round((1 - v.y) * res_y, 2)]


acts = {x.name.split(".")[0]: x for x in bpy.data.actions}
ad = arm.animation_data or arm.animation_data_create()


def set_action(name, sec):
    act = next(x for n, x in acts.items() if n == name or n.startswith(name + "_"))
    ad.action = act
    if len(act.slots):
        ad.action_slot = act.slots[0]
    f0 = act.frame_range[0]
    f = f0 + sec * scene.render.fps
    scene.frame_set(int(math.floor(f)), subframe=f - math.floor(f))
    bpy.context.view_layer.update()


def rot_bone(name, deg):
    """Knochen um die Welt-Y-Achse durch seinen Kopf drehen (Kinder folgen)."""
    pb = arm.pose.bones[name]
    axis = (arm.matrix_world.inverted().to_3x3() @ Vector((0, 1, 0))).normalized()
    piv = pb.matrix.translation.copy()
    R = Matrix.Translation(piv) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-piv)
    pb.matrix = R @ pb.matrix
    bpy.context.view_layer.update()


def set_give(k):
    set_action("Idle", 0.0)
    basis = {pb.name: pb.matrix_basis.copy() for pb in arm.pose.bones}
    ad.action = None
    for pb in arm.pose.bones:
        pb.matrix_basis = basis[pb.name]
    bpy.context.view_layer.update()
    for name, deg in GIVE[k]:
        rot_bone(name, deg)


foot_vs = {}
for ob in meshes:
    for side in "LR":
        vg = ob.vertex_groups.get("foot." + side)
        if vg is not None:
            foot_vs[(ob.name, side)] = [v.index for v in ob.data.vertices
                                        for g in v.groups if g.group == vg.index and g.weight > 0.5]


def measure():
    dg = bpy.context.evaluated_depsgraph_get()
    pts = {"L": [], "R": []}
    allp = []
    parcel = []
    for ob in meshes:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ob.matrix_world
        co = [mw @ v.co for v in me.vertices]
        allp += co
        if ob.name.startswith("Parcel"):
            parcel += co
        ev.to_mesh_clear()
    # Fußpunkte über die Punktnummern der Basisgeometrie: Subsurf ändert die Punktzahl, deshalb kurz aus
    mods ={ob.name: [m for m in ob.modifiers if m.type == "SUBSURF"] for ob in meshes}
    for ob in meshes:
        for m in mods[ob.name]:
            m.show_viewport = False
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    for ob in meshes:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        for side in "LR":
            idx = foot_vs.get((ob.name, side))
            if idx:
                pts[side] += [ob.matrix_world @ me.vertices[j].co for j in idx]
        ev.to_mesh_clear()
    for ob in meshes:
        for m in mods[ob.name]:
            m.show_viewport = True
    bpy.context.view_layer.update()
    feet = {}
    for side in "LR":
        p = pts[side]
        zmin = min(q.z for q in p)
        low = [q for q in p if q.z < zmin + 0.006]
        pb = arm.pose.bones["foot." + side]
        h, t = arm.matrix_world @ pb.head, arm.matrix_world @ pb.tail
        feet[side] = {"sole_z_m": round(zmin, 4), "sole_x0_m": round(min(q.x for q in low), 4),
                      "sole_x1_m": round(max(q.x for q in low), 4),
                      "sole_px": [project(Vector((min(q.x for q in low), 0, zmin)))[0],
                                  project(Vector((max(q.x for q in low), 0, zmin)))[0],
                                  project(Vector((0, 0, zmin)))[1]],
                      "heel_px": project(h), "toe_px": project(t)}
    hb = arm.pose.bones["head"]
    hr = arm.pose.bones["hand.R"]
    bb = [min(q.x for q in allp), max(q.x for q in allp), min(q.z for q in allp), max(q.z for q in allp)]
    pc = sum(parcel, Vector()) / max(1, len(parcel))
    return {"feet": feet,
            "head_px": [project(arm.matrix_world @ hb.head), project(arm.matrix_world @ hb.tail)],
            "hand_r_px": project(arm.matrix_world @ hr.tail),
            "parcel_px": project(pc),
            "bbox_m": [round(x, 4) for x in bb]}


def render(path, kind):
    vl = scene.view_layers[0]
    s = scene.render.image_settings
    if kind == "preview":
        use_materials("orig")
        vl.material_override = None
        scene.view_settings.view_transform = "Standard"
        scene.eevee.taa_render_samples = 16
        scene.render.filter_size = 1.5
        s.color_mode, s.color_depth = "RGBA", "8"
    else:
        scene.view_settings.view_transform = "Raw"
        scene.view_settings.look = "None"
        scene.eevee.taa_render_samples = 1
        scene.render.filter_size = 0.0
        if kind == "id":
            use_materials("id")
            vl.material_override = None
            s.color_mode, s.color_depth = "RGBA", "8"
        elif kind == "z":
            vl.material_override = zmat
            s.color_mode, s.color_depth = "BW", "16"
        elif kind == "light":
            vl.material_override = lmat
            s.color_mode, s.color_depth = "BW", "8"
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


if a.preview:
    sun = bpy.data.lights.new("Sun", "SUN")
    sun.energy = 3.0
    so = bpy.data.objects.new("Sun", sun)
    scene.collection.objects.link(so)
    so.rotation_euler = LIGHT.to_track_quat("Z", "Y").to_euler()
    scene.world.color = (0.35, 0.35, 0.38)

poses = []
if "walk" in a.only:
    poses += [(f"walk_{k}", ("walk", k)) for k in range(8)]
if "give" in a.only:
    poses += [(f"give_{k}", ("give", k)) for k in range(len(GIVE))]

info = {"ppm": a.ppm, "size": [res_x, res_y], "field_m": [X0, X1, Z0, Z1], "origin_px": project(Vector((0, 0, 0))),
        "depth": {"near": Z_NEAR, "range": Z_RANGE}, "mats": MATS, "far_y": FAR_Y, "light": list(LIGHT),
        "give": GIVE, "subsurf": a.subsurf, "poses": {}}
for name, (kind, k) in poses:
    if kind == "walk":
        set_action("Walk", k / 8.0)
    else:
        set_give(k)
    info["poses"][name] = measure()
    print("POSE", name, info["poses"][name]["bbox_m"], {s: info["poses"][name]["feet"][s]["sole_z_m"] for s in "LR"},
          flush=True)
    if a.preview:
        render(out / f"{name}_prev.png", "preview")
    else:
        render(out / f"{name}_id.png", "id")
        render(out / f"{name}_z.png", "z")
        render(out / f"{name}_light.png", "light")

(out / "passes.json").write_text(json.dumps(info, indent=1))
print("fertig:", out, res_x, res_y)
