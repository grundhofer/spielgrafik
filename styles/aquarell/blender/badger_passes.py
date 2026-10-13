# -*- coding: utf-8 -*-
"""Rendert die Animationsclips des gemeinsamen Dachs-Modells als Hilfsbilder für den Aquarell-Maler.

Aufruf (aus dem Projektordner):
  blender -b --factory-startup -P styles/aquarell/blender/badger_passes.py -- \
      --glb shared/3d/badger.glb --out styles/aquarell/assets/raw/badger_passes

Je Bild drei PNGs (gleiche Kamera, orthografisch, Wurzel der Figur fest im Ursprung):
  id_<clip>_<n>.png     Workbench, flach, ohne Kantenglättung: Materialkennung als Farbe (Tabelle in passes.json)
  shade_<clip>_<n>.png  EEVEE, alle Flächen weiß-diffus: Licht von links oben vorn + Himmelslicht; Alpha = Deckung
  nrm_<clip>_<n>.png    EEVEE, Emission der Kamera-Normalen (0..1), für Falten- und Überdeckungskanten

Clips (15 Bilder/s Wiedergabe):
  walk   10 Bilder, Walk bei 0, 3, 6 … 27 (Animation mit 1,5-facher Geschwindigkeit), Seitenansicht
  stop    6 Bilder, Pose gleitet von Walk (weiter ab Bild 30) in Idle (Anfang), Seitenansicht
  turn    5 Bilder, Idle, Drehung von 0° auf TURN° zur Kamera
  wave   23 Bilder, Wave (1,5 s), zur Kamera gedreht
  idle   30 Bilder, Idle (2 s), zur Kamera gedreht
passes.json enthält zu jedem Bild die Fußpunkte (Pixel) für die Messung des Standfußes.
"""
import argparse, json, math, os, sys

import bpy
from mathutils import Vector, Quaternion

V = Vector
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--glb", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--px", type=int, default=630, help="Kantenlänge des quadratischen Bildes")
ap.add_argument("--ortho", type=float, default=1.25)
ap.add_argument("--cz", type=float, default=0.6)
ap.add_argument("--turn", type=float, default=-75.0)
ap.add_argument("--clips", default="walk,stop,turn,wave,idle")
ap.add_argument("--only-first", action="store_true")
A = ap.parse_args(argv)

# Kennfarben der Materialien (sRGB, Workbench zeigt diffuse_color unverändert bei Standard-Transformation)
IDS = {"FurDark": (1, 0, 0), "FurLight": (0, 1, 0), "Cap": (0, 0, 1), "Brass": (1, 1, 0), "Vest": (1, 0, 1),
       "Shirt": (0, 1, 1), "Scarf": (1, 0.5, 0), "Satchel": (0.5, 0, 1), "Parcel": (0, 0.5, 0),
       "Nose": (0.5, 0.5, 0.5), "Eye": (1, 1, 1)}

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = 30
bpy.ops.import_scene.gltf(filepath=os.path.abspath(A.glb))
sc.render.resolution_x = sc.render.resolution_y = A.px
sc.render.resolution_percentage = 100
sc.render.film_transparent = True
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGBA"
sc.view_settings.view_transform = "Standard"
sc.eevee.taa_render_samples = 32

world = bpy.data.worlds.new("W")
sc.world = world
if world.node_tree is None:
    world.use_nodes = True
bgn = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
bgn.inputs["Color"].default_value = (0.62, 0.66, 0.78, 1)   # kühles Himmelslicht
bgn.inputs["Strength"].default_value = 0.32

key = bpy.data.lights.new("Key", "SUN")
key.energy = 2.0
key.angle = math.radians(5)
key_ob = bpy.data.objects.new("Key", key)
sc.collection.objects.link(key_ob)
# von rechts oben vorn (Gesicht der nach rechts laufenden Figur im Licht): Licht kommt aus +X, -Y (Kameraseite), +Z
key_ob.rotation_euler = V((-0.6, 0.65, -0.9)).normalized().to_track_quat("-Z", "Y").to_euler()

cam = bpy.data.cameras.new("Cam")
cam.type = "ORTHO"
cam.ortho_scale = A.ortho
cam_ob = bpy.data.objects.new("Cam", cam)
sc.collection.objects.link(cam_ob)
sc.camera = cam_ob
cam_ob.location = V((0.0, -4.0, A.cz))
cam_ob.rotation_euler = V((0, 1, 0)).to_track_quat("-Z", "Z").to_euler()
px_per_m = A.px / A.ortho

arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
top = arm
while top.parent:
    top = top.parent

# --- Materialvarianten ------------------------------------------------------------------------------
mats = {m.name: m for m in bpy.data.materials}
orig_trees = {}


def node_mat(name, build):
    m = bpy.data.materials.new(name)
    if m.node_tree is None:
        m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    build(nt, out)
    return m


def build_white(nt, out):
    d = nt.nodes.new("ShaderNodeBsdfDiffuse")
    d.inputs["Color"].default_value = (0.8, 0.8, 0.8, 1)
    nt.links.new(d.outputs[0], out.inputs["Surface"])


def build_normal(nt, out):
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    vt = nt.nodes.new("ShaderNodeVectorTransform")
    vt.vector_type = "NORMAL"
    vt.convert_from = "WORLD"
    vt.convert_to = "CAMERA"
    mul = nt.nodes.new("ShaderNodeVectorMath")
    mul.operation = "MULTIPLY_ADD"
    mul.inputs[1].default_value = (0.5, 0.5, 0.5)
    mul.inputs[2].default_value = (0.5, 0.5, 0.5)
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(geo.outputs["Normal"], vt.inputs[0])
    nt.links.new(vt.outputs[0], mul.inputs[0])
    nt.links.new(mul.outputs[0], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])


WHITE = node_mat("PassWhite", build_white)
NORMAL = node_mat("PassNormal", build_normal)
for name, col in IDS.items():
    if name in mats:
        mats[name].diffuse_color = (*col, 1)


def set_mode(mode):
    vl = bpy.context.view_layer
    if mode == "id":
        sc.render.engine = "BLENDER_WORKBENCH"
        sc.display.shading.light = "FLAT"
        sc.display.shading.color_type = "MATERIAL"
        sc.display.render_aa = "OFF"
        vl.material_override = None
    else:
        sc.render.engine = "BLENDER_EEVEE"
        vl.material_override = WHITE if mode == "shade" else NORMAL


# --- Posen --------------------------------------------------------------------------------------------
ad = arm.animation_data or arm.animation_data_create()
for tr in list(ad.nla_tracks):
    ad.nla_tracks.remove(tr)


def action(name):
    return next(a for a in bpy.data.actions if a.name == name or a.name.startswith(name + "_")
                or a.name.startswith(name + "."))


def use_action(name):
    act = action(name)
    ad.action = act
    if len(act.slots):
        ad.action_slot = act.slots[0]
    return act


def pose_at(name, frame):
    """Werte aller Knochen bei Bild frame der Animation name (aus der Auswertung, nicht aus den Kurven)."""
    use_action(name)
    sc.frame_set(int(math.floor(frame)), subframe=frame - math.floor(frame))
    return {pb.name: (pb.location.copy(), pb.rotation_quaternion.copy(), pb.scale.copy()) for pb in arm.pose.bones}


def apply_pose(p):
    ad.action = None
    for pb in arm.pose.bones:
        loc, rot, scl = p[pb.name]
        pb.location, pb.rotation_quaternion, pb.scale = loc, rot, scl
    bpy.context.view_layer.update()


def blend(pa, pb_, k):
    out = {}
    for n in pa:
        la, ra, sa = pa[n]
        lb, rb, sb = pb_[n]
        out[n] = (la.lerp(lb, k), ra.slerp(rb, k), sa.lerp(sb, k))
    return out


def smooth(k):
    return k * k * (3 - 2 * k)


CLIPS = {}
walk = action("Walk")
w0, w1 = walk.frame_range
CLIPS["walk"] = [("Walk", w0 + 3 * i, 0.0, None) for i in range(10)]
# Anhalten: Walk läuft weiter (Bild 30 = 0 …), Pose gleitet in 6 Bildern in Idle(0)
CLIPS["stop"] = [("blend", w0 + (3 * i) % 30, 0.0, smooth((i + 1) / 6.0)) for i in range(6)]
CLIPS["turn"] = [("Idle", 2.0 * i, A.turn * smooth((i + 1) / 5.0), None) for i in range(5)]
wave = action("Wave")
CLIPS["wave"] = [("Wave", wave.frame_range[0] + 2.0 * i, A.turn, None) for i in range(23)]
CLIPS["idle"] = [("Idle", 10.0 + 2.0 * i, A.turn, None) for i in range(30)]


def to_px(p):
    return ((p.x - cam_ob.location.x) * px_per_m + A.px / 2, (A.cz - p.z) * px_per_m + A.px / 2)


fsets = {}
for ob in meshes:
    for side in "LR":
        vg = ob.vertex_groups.get("foot." + side)
        if vg is not None:
            fsets[(ob.name, side)] = [v.index for v in ob.data.vertices
                                      for g in v.groups if g.group == vg.index and g.weight > 0.5]


def feet():
    dg = bpy.context.evaluated_depsgraph_get()
    res = {}
    for side in "LR":
        pts = []
        for ob in meshes:
            idx = fsets.get((ob.name, side))
            if not idx:
                continue
            ev = ob.evaluated_get(dg)
            me = ev.to_mesh()
            pts += [ob.matrix_world @ me.vertices[j].co for j in idx]
            ev.to_mesh_clear()
        zmin = min(p.z for p in pts)
        low = [p for p in pts if p.z < zmin + 0.01]
        pb = arm.pose.bones["foot." + side]
        ank = arm.matrix_world @ pb.head
        res[side] = {"z_px": round(zmin * px_per_m, 2), "heel_px": round(to_px(V((min(p.x for p in low), 0, 0)))[0], 2),
                     "toe_px": round(to_px(V((max(p.x for p in low), 0, 0)))[0], 2),
                     "ankle_x": round(to_px(ank)[0], 2), "ankle_y": round(to_px(ank)[1], 2)}
    return res


os.makedirs(A.out, exist_ok=True)
info = {"px": A.px, "px_per_m": px_per_m, "ground_y": to_px(V((0, 0, 0)))[1], "ids": IDS, "clips": {}}
idle0 = pose_at("Idle", 0.0)
for clip in A.clips.split(","):
    rows = []
    for n, (src, fr, rot, k) in enumerate(CLIPS[clip]):
        if A.only_first and n > 0:
            break
        if src == "blend":
            apply_pose(blend(pose_at("Walk", fr), idle0, k))
        else:
            apply_pose(pose_at(src, fr))
        top.rotation_mode = "XYZ"
        top.rotation_euler = (top.rotation_euler.x, top.rotation_euler.y, math.radians(rot))
        bpy.context.view_layer.update()
        ft = feet()
        for mode in ("id", "shade", "nrm"):
            set_mode(mode)
            sc.render.filepath = os.path.join(os.path.abspath(A.out), f"{mode}_{clip}_{n:02d}.png")
            bpy.ops.render.render(write_still=True)
        rows.append({"n": n, "src": src, "frame": fr, "rot": rot, "blend": k, "feet": ft})
        print("FRAME", clip, n, src, fr, rot, k, ft, flush=True)
    info["clips"][clip] = rows
with open(os.path.join(A.out, "passes.json"), "w") as f:
    json.dump(info, f, indent=1)
print("OK")
