# Vergleichsansichten für assets/compare_badger.png: rendert ein Modell (glb mit Textur oder PLY mit
# Eckpunktfarben) von vorn, rechts und hinten (Workbench, Studiolicht, orthografisch).
#
#   blender -b --factory-startup -P styles/ki-3d-modell/blender/compare_views.py -- in.(glb|ply) out_prefix [--size 320]
import bpy, math, os, sys
import mathutils

argv = sys.argv[sys.argv.index("--") + 1:]
src, prefix = argv[0], argv[1]
size = int(argv[argv.index("--size") + 1]) if "--size" in argv else 320
bpy.ops.wm.read_factory_settings(use_empty=True)
if src.endswith(".ply"):
    bpy.ops.wm.ply_import(filepath=os.path.abspath(src), import_colors="SRGB")
    color = "VERTEX"
else:
    bpy.ops.import_scene.gltf(filepath=os.path.abspath(src))
    color = "TEXTURE"
obs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
pts = [o.matrix_world @ mathutils.Vector(c) for o in obs for c in o.bound_box]
lo = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
ctr = (lo + hi) / 2
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.display.shading.light = "STUDIO"
sc.display.shading.color_type = color
sc.render.resolution_x = sc.render.resolution_y = size
sc.view_settings.view_transform = "Standard"
sc.world = bpy.data.worlds.new("w")
cd = bpy.data.cameras.new("c")
cd.type = "ORTHO"
cd.ortho_scale = (hi.z - lo.z) * 1.12
cam = bpy.data.objects.new("c", cd)
sc.collection.objects.link(cam)
sc.camera = cam
for name, az in (("front", 0.0), ("right", -90.0), ("back", 180.0)):
    a = math.radians(az)
    d = mathutils.Vector((math.cos(a), math.sin(a), 0.0))
    cam.location = ctr + d * 5.0
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = f"{prefix}_{name}.png"
    bpy.ops.render.render(write_still=True)
