# -*- coding: utf-8 -*-
"""Posen-Vorlage für das KI-Figurenblatt: der geriggte Dachs aus shared/3d in der Seitenansicht.

Rendert 8 Phasen des Laufzyklus (Walk, 1,0 s) und 4 Stehbilder (Idle) einzeln mit transparentem
Hintergrund. compose_layout.py setzt daraus ein 1536×1024-Blatt, das genimg.py als erste Referenz bekommt
(Layout und Beinstellungen), das Referenzblatt des Kostüms als zweite.

Aufruf (aus dem Projektordner):
  blender -b --factory-startup -P styles/hibit-pixel/blender/walk_layout.py -- --out <ordner>
Gibt je Bild die Lage beider Füße (tiefster Punkt, x vorn) in Metern aus, für die spätere Prüfung.
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--glb", default="shared/3d/badger.glb")
ap.add_argument("--out", required=True)
ap.add_argument("--px", type=int, default=480, help="Kantenlänge eines Einzelbildes")
A = ap.parse_args(argv)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = 30
bpy.ops.import_scene.gltf(filepath=os.path.abspath(A.glb))
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 16
sc.render.resolution_x = sc.render.resolution_y = A.px
sc.render.film_transparent = True
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGBA"
sc.view_settings.view_transform = "Standard"
world = bpy.data.worlds.new("W")
sc.world = world
world.use_nodes = True
bgn = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
bgn.inputs["Color"].default_value = (0.8, 0.82, 0.86, 1)
bgn.inputs["Strength"].default_value = 0.9

cam = bpy.data.cameras.new("Cam")
cam.type = "ORTHO"
cam.ortho_scale = 1.30
cam_ob = bpy.data.objects.new("Cam", cam)
sc.collection.objects.link(cam_ob)
sc.camera = cam_ob
cam_ob.location = (0.0, -4.0, 0.60)
cam_ob.rotation_euler = (math.radians(90), 0, 0)

key = bpy.data.lights.new("Key", "SUN")
key.energy = 3.0
key_ob = bpy.data.objects.new("Key", key)
sc.collection.objects.link(key_ob)
key_ob.rotation_euler = (math.radians(55), 0, math.radians(-30))

arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
meshes = [o for o in bpy.data.objects if o.type == "MESH" and any(m.type == "ARMATURE" for m in o.modifiers)]
for o in bpy.data.objects:   # Knochenform-Hilfsobjekte nicht rendern
    if o.type == "MESH" and o not in meshes:
        o.hide_render = True


def set_action(name):
    ad = arm.animation_data or arm.animation_data_create()
    act = next(a for a in bpy.data.actions if a.name == name or a.name.startswith(name + "_") or a.name.startswith(name + "."))
    ad.action = act
    if getattr(ad, "action_slot", None) is None and len(act.slots):
        ad.action_slot = act.slots[0]
    return act


def foot_info():
    dg = bpy.context.evaluated_depsgraph_get()
    res = {}
    for ob in meshes:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ob.matrix_world
        for side in "LR":
            vg = ob.vertex_groups.get("foot." + side)
            if vg is None:
                continue
            pts = [mw @ v.co for v in me.vertices if any(g.group == vg.index and g.weight > 0.5 for g in v.groups)]
            if pts:
                res[side] = (min(p.z for p in pts), min(p.x for p in pts), max(p.x for p in pts))
        ev.to_mesh_clear()
    return res


os.makedirs(A.out, exist_ok=True)
jobs = [("walk", "Walk", 30.0 * k / 8.0) for k in range(8)] + [("idle", "Idle", f) for f in (0, 15, 30, 45)]
for i, (tag, action, f) in enumerate(jobs):
    set_action(action)
    sc.frame_set(int(f), subframe=f - int(f))
    fi = foot_info()
    print("FOOT %s %02d f=%.2f " % (tag, i, f) + " ".join(
        "%s: z %.3f x %.3f..%.3f" % (s, *fi[s]) for s in sorted(fi)))
    sc.render.filepath = os.path.join(A.out, "%s_%02d.png" % (tag, i))
    bpy.ops.render.render(write_still=True)
print("ortho_scale", cam.ortho_scale, "px", A.px, "cam_z", cam_ob.location.z)
