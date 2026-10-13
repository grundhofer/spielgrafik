# -*- coding: utf-8 -*-
"""Rendert Posen des gemeinsamen Dachs-Modells als Layout-Referenzen für den Bleistift-Laufbogen durch das Bildmodell.
# Übernommen aus styles/kupferstich/blender/pose_layout.py (dort aus bilderbuch-gouache), unverändert bis auf Pfade im Kommentar.

Aufruf (aus dem Projektordner):
  blender -b --factory-startup -P styles/bleistift-skizze/blender/pose_layout.py -- \
      --glb shared/3d/badger.glb --set walk --out styles/bleistift-skizze/assets/ref/poses_walk
  blender -b --factory-startup -P styles/bleistift-skizze/blender/pose_layout.py -- \
      --glb shared/3d/badger.glb --set front --out styles/bleistift-skizze/assets/ref/poses_front

Gleiche Kamera und gleiches Licht wie walk_layout.py (orthografisch, 1,25 m Bildhöhe auf 512 px, also 409,6 px/m,
Licht von links oben vorn, weißes Umgebungslicht), damit beide Bögen denselben Maßstab haben.

Sätze:
  walk   307x512 je Bild: walk_0 … walk_7 (Walk bei t = 0, 1/8 … 7/8 s), stand (Idle 0, Seitenansicht),
         turn (Idle 0, um 40° zur Kamera gedreht)
  front  512x512 je Bild, um 75° zur Kamera gedreht: front (Idle 0), wave_raise (Wave, Arm seitlich),
         wave_out (Hand oben außen), wave_in (Hand oben innen), blink und talk (wie front; Augen bzw. Mund ändert erst
         das Bildmodell laut Prompt)
Ergebnis: <name>.png (RGBA, transparent) und poses.json mit den Sohlenpunkten je Bild in Pixeln.
"""
import argparse, json, math, os, sys

import bpy
from mathutils import Vector

V = Vector
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--glb", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--set", required=True, choices=["walk", "front"])
ap.add_argument("--ortho", type=float, default=1.25)
ap.add_argument("--cz", type=float, default=0.56)
A = ap.parse_args(argv)

TURN = -75.0
if A.set == "walk":
    W, H, CX = 307, 512, -0.012
    POSES = [(f"walk_{i}", "Walk", i / 8.0, 0.0) for i in range(8)]
    POSES += [("stand", "Idle", 0.0, 0.0), ("turn", "Idle", 0.0, -40.0)]
else:
    W, H, CX = 512, 512, 0.05
    # Wave (1,5 s = 45 Bilder): Bild 6 Arm seitlich, 12 Hand oben außen, 20 Hand oben innen
    POSES = [("front", "Idle", 0.0, TURN), ("wave_raise", "Wave", 6 / 30.0, TURN),
             ("wave_out", "Wave", 12 / 30.0, TURN), ("wave_in", "Wave", 20 / 30.0, TURN),
             ("blink", "Idle", 0.0, TURN), ("talk", "Idle", 0.0, TURN)]

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

os.makedirs(A.out, exist_ok=True)
info = {"set": A.set, "w": W, "h": H, "px_per_m": px_per_m, "ground_y": to_px(V((0, 0, 0)))[1], "frames": []}
for name, act_name, t, rot in POSES:
    act = use_action(act_name)
    f0, f1 = act.frame_range
    ft = f0 + t * 30.0
    sc.frame_set(int(math.floor(ft)), subframe=ft - math.floor(ft))
    top.rotation_mode = "XYZ"
    top.rotation_euler = (top.rotation_euler.x, top.rotation_euler.y, math.radians(rot))
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    feet = {}
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
        xs = [to_px(p)[0] for p in low]
        feet[side] = {"z_m": round(zmin, 4), "x0_px": round(min(xs), 1), "x1_px": round(max(xs), 1),
                      "lift_px": round(zmin * px_per_m, 1)}
    sc.render.filepath = os.path.join(os.path.abspath(A.out), f"{name}.png")
    bpy.ops.render.render(write_still=True)
    info["frames"].append({"name": name, "action": act_name, "frame": ft, "rot": rot, "feet": feet})
    print("FRAME", name, act_name, ft, rot, feet, flush=True)

with open(os.path.join(A.out, "poses.json"), "w") as f:
    json.dump(info, f, indent=1)
print("OK", A.out)
