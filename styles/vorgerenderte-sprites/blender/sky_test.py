"""Nur Himmel durch die Szenenkamera (schnelle Abstimmung der Wolken)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import vs_scene as S
a = S.arg_list()
S.reset()
S.world_sky()
S.bg_camera()
sc = S.render_setup("CYCLES", samples=16)
sc.render.resolution_x, sc.render.resolution_y = S.W * 2, S.H * 2
sc.render.filepath = a[0]
bpy.ops.render.render(write_still=True)
