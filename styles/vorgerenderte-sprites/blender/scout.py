"""Schnelle Ausschnittsprüfung: ganze Szene mit Dachs an mehreren Stellen, EEVEE oder Cycles.
blender -b --factory-startup -P blender/scout.py -- OUT.png [eevee|cycles] [x1,x2,...]
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import vs_scene as S

args = S.arg_list()
out = args[0]
engine = args[1] if len(args) > 1 else "eevee"
xs = [float(v) for v in args[2].split(",")] if len(args) > 2 else [-8.0, -6.0]
S.reset()
S.load_harbor()
S.apply_materials()
S.world_sky()
S.scene_lights()
S.bg_camera()
for i, x in enumerate(xs):
    arm, objs = S.load_badger()
    arm.location = (x, S.WALK_Y, 0.0)
    if i == len(xs) - 1:
        arm.rotation_euler.z = -1.5708   # zur Kamera
S.apply_materials()
S.render_setup("CYCLES" if engine == "cycles" else "BLENDER_EEVEE", samples=32 if engine == "cycles" else 16)
bpy.context.scene.render.filepath = out
bpy.ops.render.render(write_still=True)
