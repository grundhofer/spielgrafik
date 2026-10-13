"""Kandidaten für die drei Knotenansichten schnell mit EEVEE ansehen (nur zur Auswahl, kein Endbild).

blender -b --factory-startup -P styles/vorgerendert-diashow/blender/scout.py -- OUT_DIR

Kameras in Godot-Koordinaten (x, y, z): Position, Ziel, horizontaler Bildwinkel; Bild 544×332 wie die Knoten.
Dachs-Platzhalter (badger_low.glb, zur Kamera gedreht) an einigen Stellen, damit die Figurengröße sichtbar wird.
"""
import math
import os
import sys

import bpy
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
args = sys.argv[sys.argv.index("--") + 1:]
out_dir = args[0]
os.makedirs(out_dir, exist_ok=True)


def gb(v):
    """Godot (x, y, z) -> Blender (x, -z, y)."""
    return Vector((v[0], -v[2], v[1]))


EYE = 1.62
CAMS = {
    "kai_a": ((-1.0, EYE, 3.0), (-9.0, 1.9, -4.0), 64),
    "kai_b": ((0.5, EYE, 2.0), (-9.0, 2.0, -6.0), 64),
    "kai_c": ((-2.0, EYE, 4.5), (-9.5, 2.0, -3.0), 70),
    "steg_a": ((2.2, EYE, 3.0), (6.0, 2.6, -20.0), 64),
    "steg_b": ((2.4, EYE, 1.5), (6.0, 3.1, -20.0), 70),
    "steg_c": ((2.0, EYE, 2.0), (5.0, 2.9, -20.0), 70),
    "tuer_a": ((7.0, 2.8 + EYE, -17.5), (10.2, 6.0, -25.6), 64),
    "tuer_b": ((12.5, 2.8 + EYE, -18.5), (10.2, 6.0, -25.6), 64),
    "tuer_c": ((9.0, 2.8 + EYE, -16.5), (10.2, 6.5, -25.6), 70),
}
BADGERS = [(3.45, -6.0), (3.45, -3.8)]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=os.path.join(ROOT, "shared/3d/harbor.glb"))
for (x, z) in BADGERS:
    bpy.ops.import_scene.gltf(filepath=os.path.join(ROOT, "shared/3d/badger_low.glb"))
    roots = [o for o in bpy.context.selected_objects if o.parent is None]
    for r in roots:
        r.location = gb((x, 0.0, z))
        r.rotation_mode = "XYZ"
        r.rotation_euler[2] = math.radians(-90)

sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 8
sc.render.resolution_x, sc.render.resolution_y = 544, 332
sc.view_settings.view_transform = "AgX"
world = bpy.data.worlds.new("W")
sc.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.25, 0.3, 0.45, 1)
sun = bpy.data.lights.new("S", "SUN")
sun.energy = 3.0
so = bpy.data.objects.new("S", sun)
sc.collection.objects.link(so)
so.rotation_euler = Vector((0.55, 0.72, -0.42)).normalized().to_track_quat("-Z", "Y").to_euler()

for name, (pos, tgt, hfov) in CAMS.items():
    cd = bpy.data.cameras.new(name)
    cd.sensor_fit = "HORIZONTAL"
    cd.sensor_width = 36.0
    cd.lens = 18.0 / math.tan(math.radians(hfov) / 2)
    cd.clip_start, cd.clip_end = 0.1, 3000
    co = bpy.data.objects.new(name, cd)
    sc.collection.objects.link(co)
    co.location = gb(pos)
    co.rotation_euler = (gb(tgt) - gb(pos)).to_track_quat("-Z", "Y").to_euler()
    sc.camera = co
    sc.render.filepath = os.path.join(out_dir, name + ".png")
    bpy.ops.render.render(write_still=True)
