# -*- coding: utf-8 -*-
"""Rendert Posen des gemeinsamen Dachs-Modells als Layout-Referenz für den Cel-Bogen des Bildmodells.

Grundlage: styles/bilderbuch-gouache/blender/pose_layout.py (Kamera, Licht, Fußmessung übernommen).
Neu für den Zeichentrick-Look: Der Laufzyklus des Modells ist für einen Zeichentrickfilm zu steif. Das Skript
liest die Pose je Bild aus der Aktion, verstärkt die Drehung der Bein-, Arm- und Beckenknochen (Winkel × Faktor)
und setzt die Figur danach so tief, dass der unterste Fußpunkt auf dem Boden steht. So entsteht das Auf und Ab
eines gezeichneten Laufzyklus (tief im Kontakt, hoch im Durchgang) aus der Geometrie, ohne geschätzte Werte.

Aufruf (aus dem Projektordner):
  blender -b --factory-startup -P styles/zeichentrick-cel/blender/pose_layout.py -- \
      --glb shared/3d/badger.glb --out styles/zeichentrick-cel/assets/ref/poses

Ergebnis: <name>.png (RGBA, transparent, 307x512, 409,6 px/m) und poses.json (Sohlenpunkte, Anhebung je Bild).
Posen: walk_0 … walk_7 (Walk bei t = 0 … 7/8 s, verstärkt), stand (Idle 0, Seitenansicht),
       front (Idle 0, um 60° zur Kamera gedreht, Kopf weitere 15° zur Kamera).
"""
import argparse, json, math, os, sys

import bpy
from mathutils import Quaternion, Vector

V = Vector
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--glb", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--ortho", type=float, default=1.25)
ap.add_argument("--cz", type=float, default=0.56)
ap.add_argument("--leg", type=float, default=1.7, help="Verstärkung der Beinwinkel im Laufen")
ap.add_argument("--arm", type=float, default=1.6, help="Verstärkung des freien Arms im Laufen")
ap.add_argument("--body", type=float, default=1.5, help="Verstärkung von Becken, Rücken, Kopf im Laufen")
A = ap.parse_args(argv)

W, H, CX = 307, 512, -0.012
POSES = [(f"walk_{i}", "Walk", i / 8.0, 0.0, True) for i in range(8)]
POSES += [("stand", "Idle", 0.0, 0.0, False), ("front", "Idle", 0.0, -60.0, False)]
GAIN = {"thigh.L": "leg", "thigh.R": "leg", "shin.L": "leg", "shin.R": "leg", "foot.L": "leg", "foot.R": "leg",
        "upper_arm.L": "arm", "forearm.L": "arm", "hips": "body", "spine": "body", "chest": "body",
        "neck": "body", "head": "body", "scarf_1": "arm", "scarf_2": "arm", "tail": "arm"}

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = 30
bpy.ops.import_scene.gltf(filepath=os.path.abspath(A.glb))
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 32
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.render.resolution_percentage = 100
sc.render.film_transparent = True
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGBA"
sc.view_settings.view_transform = "Standard"

world = bpy.data.worlds.new("W")
sc.world = world
if world.node_tree is None:
    world.use_nodes = True
bgn = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
bgn.inputs["Color"].default_value = (1, 1, 1, 1)
bgn.inputs["Strength"].default_value = 0.9

key = bpy.data.lights.new("Key", "SUN")
key.energy = 2.2
key.angle = math.radians(8)
key_ob = bpy.data.objects.new("Key", key)
sc.collection.objects.link(key_ob)
key_ob.rotation_euler = (V((0.8, 0.6, -1.0))).normalized().to_track_quat("-Z", "Y").to_euler()

cam = bpy.data.cameras.new("Cam")
cam.type = "ORTHO"
cam.ortho_scale = A.ortho
cam_ob = bpy.data.objects.new("Cam", cam)
sc.collection.objects.link(cam_ob)
sc.camera = cam_ob
cam_ob.location = V((CX, -3.0, A.cz))
cam_ob.rotation_euler = V((0, 1, 0)).to_track_quat("-Z", "Z").to_euler()
px_per_m = max(W, H) / A.ortho

arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
top = arm
while top.parent:
    top = top.parent
ad = arm.animation_data or arm.animation_data_create()
for tr in list(ad.nla_tracks):
    ad.nla_tracks.remove(tr)


def use_action(name):
    act = next(a for a in bpy.data.actions if a.name == name or a.name.startswith(name + "_")
               or a.name.startswith(name + "."))
    ad.action = act
    if len(act.slots):
        ad.action_slot = act.slots[0]
    return act


def to_px(p):
    return ((p.x - CX) * px_per_m + W / 2, (A.cz - p.z) * px_per_m + H / 2)


fsets = {}
for ob in meshes:
    for side in "LR":
        vg = ob.vertex_groups.get("foot." + side)
        if vg is not None:
            fsets[(ob.name, side)] = [v.index for v in ob.data.vertices
                                      for g in v.groups if g.group == vg.index and g.weight > 0.5]


def foot_points(dg):
    out = {}
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
        out[side] = pts
    return out


def amplify(q, k):
    axis, ang = q.to_axis_angle()
    if ang > math.pi:
        ang -= 2 * math.pi
    return Quaternion(axis, ang * k)


os.makedirs(A.out, exist_ok=True)
info = {"w": W, "h": H, "px_per_m": px_per_m, "ground_y": to_px(V((0, 0, 0)))[1],
        "gain": {"leg": A.leg, "arm": A.arm, "body": A.body}, "frames": []}
base_z = top.location.z
for name, act_name, t, rot, boost in POSES:
    act = use_action(act_name)
    f0, f1 = act.frame_range
    ft = f0 + t * 30.0
    sc.frame_set(int(math.floor(ft)), subframe=ft - math.floor(ft))
    bpy.context.view_layer.update()
    # Pose aus der Aktion übernehmen, Aktion lösen, dann verstärken (sonst überschreibt das Rendern die Änderung).
    pose = {pb.name: (pb.location.copy(), pb.rotation_quaternion.copy(), pb.scale.copy()) for pb in arm.pose.bones}
    ad.action = None
    for pb in arm.pose.bones:
        loc, q, s = pose[pb.name]
        pb.rotation_mode = "QUATERNION"
        pb.location, pb.scale = loc, s
        g = GAIN.get(pb.name)
        k = {"leg": A.leg, "arm": A.arm, "body": A.body}[g] if (boost and g) else 1.0
        pb.rotation_quaternion = amplify(q, k) if k != 1.0 else q
        if boost and pb.name == "hips":
            pb.location = loc * A.body
    top.rotation_mode = "XYZ"
    top.rotation_euler = (top.rotation_euler.x, top.rotation_euler.y, math.radians(rot))
    top.location.z = base_z
    if name == "front":
        hb = arm.pose.bones.get("head")
        hb.rotation_quaternion = Quaternion((0, 1, 0), math.radians(-15)) @ hb.rotation_quaternion
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    fp = foot_points(dg)
    zmin = min(p.z for side in "LR" for p in fp[side])
    top.location.z = base_z - zmin + 0.003  # unterster Fußpunkt auf den Boden (Sohlen sonst bei 3 mm)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    fp = foot_points(dg)
    feet = {}
    for side in "LR":
        pts = fp[side]
        zm = min(p.z for p in pts)
        low = [p for p in pts if p.z < zm + 0.01]
        xs = [to_px(p)[0] for p in low]
        feet[side] = {"z_m": round(zm, 4), "x0_px": round(min(xs), 1), "x1_px": round(max(xs), 1),
                      "lift_px": round(zm * px_per_m, 1)}
    sc.render.filepath = os.path.join(os.path.abspath(A.out), f"{name}.png")
    bpy.ops.render.render(write_still=True)
    info["frames"].append({"name": name, "action": act_name, "frame": ft, "rot": rot, "boost": boost,
                           "body_shift_m": round(-zmin + 0.003, 4), "feet": feet})
    print("FRAME", name, round(-zmin, 4), feet, flush=True)

with open(os.path.join(A.out, "poses.json"), "w") as f:
    json.dump(info, f, indent=1)
print("OK", A.out)
