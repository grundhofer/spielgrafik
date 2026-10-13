"""Erkundung: Hafen aus shared/3d in Iso-Ansicht (orthografisch, 30° Neigung, ±45° Drehung) mit EEVEE.

  blender -b --factory-startup -P styles/iso-vorgerendert/blender/scout.py -- --out <dir> [--yaw 45] [--scale 40]
          [--center x,y,z (Godot)] [--heights]

Nur zum Festlegen von Ausschnitt und Blickrichtung; keine Ausgaben im Eintrag.
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Euler, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--yaw", type=float, default=45.0)
ap.add_argument("--scale", type=float, default=40.0)
ap.add_argument("--center", default="0,0,-3")
ap.add_argument("--res", default="960x720")
ap.add_argument("--heights", action="store_true")
ap.add_argument("--lh", default="", help="Leuchtturm versetzen: x,z,scale (Godot); Fuß auf das Gelände")
ap.add_argument("--tag", default="")
ap.add_argument("--badgers", default="", help="x,z,blick_grad;... (Godot; Blick 0 = +x)")
ap.add_argument("--window", default="", help="s,X0,Ytop: px/m, linker Rand und Oberkante (Iso-Bildkoordinaten) für 640x360")
A = ap.parse_args(argv)
os.makedirs(A.out, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=os.path.join(ROOT, "shared", "3d", "harbor.glb"))
sc = bpy.context.scene

if A.heights:
    dg = bpy.context.evaluated_depsgraph_get()
    print("HEIGHTS (Godot x across, z down; value = ground y in dm, '.' = water)")
    for gz in range(-30, 9, 1):
        row = []
        for gx in range(-14, 17, 1):
            hit, loc, nrm, idx, ob, mw = sc.ray_cast(dg, Vector((gx, -gz, 50)), Vector((0, 0, -1)))
            if hit and ob.name != "Sea":
                row.append("%4d" % round(loc.z * 10))
            else:
                row.append("   .")
        print("z=%4d " % gz + "".join(row))
    print("x:     " + "".join("%4d" % gx for gx in range(-14, 17)))

if A.lh:
    lx, lz, ls = map(float, A.lh.split(","))
    lh = bpy.data.objects["Lighthouse"]
    dg = bpy.context.evaluated_depsgraph_get()
    lh.hide_set(True)
    hit, loc, *_ = sc.ray_cast(dg, Vector((lx, -lz, 60)), Vector((0, 0, -1)))
    base = loc.z if hit and loc.z > -0.79 else -0.5
    print("LH base", base)
    lh.hide_set(False)
    lh.location = (lx, -lz, base)
    lh.scale = (ls, ls, ls)

if A.badgers:
    for spec in A.badgers.split(";"):
        bx, bz, byaw = map(float, spec.split(","))
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=os.path.join(ROOT, "shared", "3d", "badger.glb"))
        root = next(o for o in bpy.data.objects if o not in before and o.parent is None)
        root.rotation_mode = "XYZ"
        root.location = (bx, -bz, 0.0)
        root.rotation_euler = (0, 0, math.radians(byaw))

w = bpy.data.worlds.new("W")
sc.world = w
w.use_nodes = True
bgn = w.node_tree.nodes["Background"]
bgn.inputs["Color"].default_value = (0.05, 0.07, 0.12, 1)
bgn.inputs["Strength"].default_value = 1.0
sun = bpy.data.lights.new("Sun", "SUN")
sun.energy = 3.0
sun.angle = math.radians(0.5)
so = bpy.data.objects.new("Sun", sun)
sc.collection.objects.link(so)
so.rotation_euler = Euler((math.radians(65), 0, math.radians(-60)))

cam = bpy.data.cameras.new("Cam")
cam.type = "ORTHO"
cam.ortho_scale = A.scale
co = bpy.data.objects.new("Cam", cam)
sc.collection.objects.link(co)
sc.camera = co
eul = Euler((math.radians(60), 0, math.radians(A.yaw)), "XYZ")
co.rotation_euler = eul
D = eul.to_matrix() @ Vector((0, 0, -1))
R = eul.to_matrix() @ Vector((1, 0, 0))
U = eul.to_matrix() @ Vector((0, 1, 0))
if A.window:
    ws, X0, Yt = map(float, A.window.split(","))
    Xc, Yc = X0 + 320.0 / ws, Yt - 180.0 / ws
    cam.ortho_scale = 640.0 / ws
    co.location = Xc * R + Yc * U - 60 * D
else:
    gx, gy, gz = map(float, A.center.split(","))
    c = Vector((gx, -gz, gy))
    co.location = c - 60 * D
cam.clip_start, cam.clip_end = 0.1, 500
W, H = map(int, A.res.split("x"))
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 16
bpy.context.view_layer.update()
sc.render.filepath = os.path.join(A.out, "scout_yaw%+d_s%d%s.png" % (A.yaw, A.scale, A.tag))
bpy.ops.render.render(write_still=True)
print("SCOUT OK", sc.render.filepath)
