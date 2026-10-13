# -*- coding: utf-8 -*-
"""Rendert Posen des gemeinsamen Dachs-Modells als Layout-Referenz für die Buchmalerei-Figur (Dreiviertelansicht
mit Redegestus). Nach styles/holzschnitt/blender/pose_layout.py (dort aus kupferstich/bilderbuch-gouache), hier mit
frei wählbaren Drehungen und Wave-Bildern.

Aufruf (aus dem Projektordner):
  blender -b --factory-startup -P styles/buchmalerei/blender/pose_layout.py -- \
      --glb shared/3d/badger.glb --out <ordner> --pose wave:12:-40 --pose idle:0:-40

  --pose name:frame:rot   name = idle|wave, frame = Bild der Aktion bei 30 Bildern/s, rot = Drehung um die
                          Hochachse in Grad (0 = Seitenansicht nach rechts, -90 = Vorderansicht)
Ergebnis: <name>_<frame>_<rot>.png (RGBA, transparent, 512x768, orthografisch 1,25 m Bildhöhe) und poses.json.
"""
import argparse, json, math, os, sys

import bpy
from mathutils import Vector

V = Vector
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--glb", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--pose", action="append", required=True)
ap.add_argument("--ortho", type=float, default=1.25)
ap.add_argument("--cz", type=float, default=0.56)
A = ap.parse_args(argv)

W, H, CX = 512, 768, 0.0

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
top = arm
while top.parent:
    top = top.parent
ad = arm.animation_data or arm.animation_data_create()
for tr in list(ad.nla_tracks):
    ad.nla_tracks.remove(tr)


def use_action(name):
    act = next(a for a in bpy.data.actions if a.name.lower() == name or a.name.lower().startswith(name + "_")
               or a.name.lower().startswith(name + "."))
    ad.action = act
    if len(act.slots):
        ad.action_slot = act.slots[0]
    return act


os.makedirs(A.out, exist_ok=True)
info = {"w": W, "h": H, "px_per_m": px_per_m, "ground_y": (A.cz - 0.0) * px_per_m + H / 2, "frames": []}
for spec in A.pose:
    name, frame, rot = spec.split(":")
    act = use_action(name)
    f0, _ = act.frame_range
    sc.frame_set(int(f0 + float(frame)))
    top.rotation_mode = "XYZ"
    top.rotation_euler = (top.rotation_euler.x, top.rotation_euler.y, math.radians(float(rot)))
    bpy.context.view_layer.update()
    out = f"{name}_{frame}_{rot}.png"
    sc.render.filepath = os.path.join(os.path.abspath(A.out), out)
    bpy.ops.render.render(write_still=True)
    info["frames"].append({"file": out, "action": name, "frame": float(frame), "rot": float(rot)})
    print("FRAME", out, flush=True)

with open(os.path.join(A.out, "poses.json"), "w") as f:
    json.dump(info, f, indent=1)
print("OK", A.out)
