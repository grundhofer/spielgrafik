"""Kandidaten für feste Kameraeinstellungen schnell mit EEVEE ansehen (nur zur Auswahl, kein Endbild).

blender -b --factory-startup -P styles/vorgerendert-fixkamera/blender/scout.py -- OUT_DIR [shots.json]

Kameras in Godot-Koordinaten (x, y, z) mit Ziel und vertikalem Bildwinkel; Dachs-Platzhalter
(badger_low.glb, zur Kamera gedreht) an einigen Stellen, damit die Figurengröße sichtbar wird.
Mit shots.json als zweitem Argument kommen Kameras und Dachs-Punkte aus dieser Datei (z. B. demo/shots.json).
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


CAMS = {
    "s1_a": ((-13.0, 6.5, 8.0), (-2.0, -0.5, -4.0), 46),
    "s1_b": ((-14.0, 5.0, 6.0), (-3.0, 0.0, -3.0), 44),
    "s1_c": ((-12.5, 4.0, 7.5), (-3.0, 0.3, -2.0), 44),
    "s1_d": ((-15.0, 7.5, 5.0), (-2.0, -1.0, -5.0), 42),
    "s2_a": ((-3.6, 0.85, 5.6), (4.0, 2.6, -14.0), 52),
    "s2_b": ((-2.8, 1.0, 5.0), (5.0, 3.0, -14.0), 55),
    "s2_c": ((-4.5, 1.2, 6.0), (3.0, 2.0, -12.0), 50),
    "s2_d": ((-1.5, 0.7, 4.6), (6.0, 3.4, -14.0), 56),
}
BADGERS = [(-5.95, -1.4), (-5.95, -0.2), (-5.95, 1.0), (-3.0, 1.2), (-1.0, 1.2)]
if len(args) > 1:  # Einstellungen und Dachs-Punkte aus einer shots.json
    import json
    data = json.load(open(args[1]))
    CAMS = {s["name"]: (tuple(s["pos"]), tuple(s["target"]), s["fov"]) for s in data["shots"]}
    BADGERS = [(p["x"], p["z"]) for p in data["path"]]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=os.path.join(ROOT, "shared/3d/harbor.glb"))
for (x, z) in BADGERS:
    bpy.ops.import_scene.gltf(filepath=os.path.join(ROOT, "shared/3d/badger_low.glb"))
    roots = [o for o in bpy.context.selected_objects if o.parent is None]
    for r in roots:
        r.location = gb((x, 0.0, z))
        r.rotation_mode = "XYZ"
        r.rotation_euler[2] = math.radians(-90)  # Blick zur Kamera (+Z in Godot)

sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 8
sc.render.resolution_x, sc.render.resolution_y = 480, 360
sc.view_settings.view_transform = "AgX"
world = bpy.data.worlds.new("W")
sc.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.25, 0.3, 0.5, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.6
sun = bpy.data.lights.new("Sun", "SUN")
sun.energy = 3.0
sun.color = (1.0, 0.6, 0.35)
so = bpy.data.objects.new("Sun", sun)
sc.collection.objects.link(so)
d = gb((0.55, -0.12, 0.83)).normalized()  # Licht läuft nach rechts, unten, zur Kamera (Sonne hinten links)
so.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
for name, e in (("LanternLight", 80), ("LighthouseLight", 900)):
    ld = bpy.data.lights.new(name + "L", "POINT")
    ld.energy = e
    ld.color = (1.0, 0.7, 0.4)
    o = bpy.data.objects.new(name + "L", ld)
    sc.collection.objects.link(o)
    o.location = bpy.data.objects[name].matrix_world.translation

for name, (pos, tgt, fov) in CAMS.items():
    cd = bpy.data.cameras.new(name)
    cd.sensor_fit = "VERTICAL"
    cd.sensor_height = 24.0
    cd.lens = 12.0 / math.tan(math.radians(fov) / 2)
    cd.clip_start, cd.clip_end = 0.1, 3000
    co = bpy.data.objects.new(name, cd)
    sc.collection.objects.link(co)
    co.location = gb(pos)
    co.rotation_euler = (gb(tgt) - gb(pos)).to_track_quat("-Z", "Y").to_euler()
    sc.camera = co
    sc.render.filepath = os.path.join(out_dir, f"scout_{name}.png")
    bpy.ops.render.render(write_still=True)
print("SCOUT OK")
