"""Brustbild des Dachses aus shared/3d/badger.glb als Bildvorlage (Ausschnitt, Pose, Licht) für das gemalte
Porträt der Bedienleiste (iso-vorgerendert).

  blender -b --factory-startup -P styles/iso-vorgerendert/blender/render_portrait.py -- --out <png>

Dreiviertelansicht nach links vorn, Kamera knapp über Augenhöhe, warmes Führungslicht von links,
kühles Kantenlicht von rechts hinten, dunkler Hintergrund. 768×1152 (2:3), Cycles.
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import isocam as ic  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
a = ap.parse_args(argv)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=os.path.join(ic.ROOT, "shared", "3d", "badger.glb"))
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
root = arm
while root.parent is not None:
    root = root.parent
root.rotation_mode = "XYZ"
root.rotation_euler = (0, 0, math.radians(-125.0))
ad = arm.animation_data or arm.animation_data_create()
act = next(x for x in bpy.data.actions if x.name.startswith("Idle"))
ad.action = act
if getattr(ad, "action_slot", None) is None and len(act.slots):
    ad.action_slot = act.slots[0]
sc.frame_set(0)

w = bpy.data.worlds.new("Dark")
sc.world = w
w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.02, 0.02, 0.035, 1)
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
ic.add_light("Key", "AREA", Vector((-1.6, -1.6, 1.6)), 120.0, "#FFD2A0", (1.0, 1.0),
             rot=(Vector((0, 0, 0.75)) - Vector((-1.6, -1.6, 1.6))).to_track_quat("-Z", "Y").to_euler())
ic.add_light("Rim", "AREA", Vector((1.2, 1.4, 1.4)), 80.0, "#9DB4FF", (0.6, 0.6),
             rot=(Vector((0, 0, 0.75)) - Vector((1.2, 1.4, 1.4))).to_track_quat("-Z", "Y").to_euler())

cd = bpy.data.cameras.new("PCam")
cd.lens = 85
cd.sensor_fit = "VERTICAL"
cd.sensor_height = 24
cam = ic.link_obj(bpy.data.objects.new("PCam", cd))
target = Vector((0.0, 0.0, 0.72))
cam.location = Vector((0.0, -3.1, 0.86))
cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
sc.camera = cam
ic.cycles_setup(sc, 96)
sc.view_settings.view_transform = "AgX"
sc.render.resolution_x, sc.render.resolution_y = 768, 1152
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGB"
sc.render.filepath = a.out
bpy.ops.render.render(write_still=True)
print("PORTRAIT OK", a.out)
