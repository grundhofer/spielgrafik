# Kontrollansichten einer glb (Workbench, Textur, Studiolicht) aus mehreren Richtungen in ein Blatt.
#
#   blender -b --factory-startup -P styles/ki-3d-modell/blender/preview.py -- in.glb out.png [--views 6] [--size 320]
#       [--elev 12] [--wire]
import bpy, math, os, sys
import mathutils

argv = sys.argv[sys.argv.index("--") + 1:]
src, out = argv[0], argv[1]
views = int(argv[argv.index("--views") + 1]) if "--views" in argv else 6
size = int(argv[argv.index("--size") + 1]) if "--size" in argv else 320
elev = float(argv[argv.index("--elev") + 1]) if "--elev" in argv else 12.0
wire = "--wire" in argv

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=os.path.abspath(src))
obs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
pts = [o.matrix_world @ mathutils.Vector(c) for o in obs for c in o.bound_box]
lo = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
ctr = (lo + hi) / 2
rad = (hi - lo).length / 2

sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.display.shading.light = "STUDIO"
sc.display.shading.color_type = "TEXTURE"
sc.display.shading.show_cavity = False
sc.display.shading.show_object_outline = False
if wire:
    sc.display.shading.show_wireframes = True if hasattr(sc.display.shading, "show_wireframes") else False
sc.render.resolution_x = sc.render.resolution_y = size
sc.render.film_transparent = False
sc.world = bpy.data.worlds.new("w")
sc.view_settings.view_transform = "Standard"
cam_data = bpy.data.cameras.new("cam")
cam_data.lens = 50
cam = bpy.data.objects.new("cam", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam
dist = rad / math.sin(math.radians(19)) * 0.8
frames = []
base, ext = os.path.splitext(out)
for i in range(views):
    az = math.radians(360.0 * i / views)
    e = math.radians(elev)
    d = mathutils.Vector((math.cos(az) * math.cos(e), math.sin(az) * math.cos(e), math.sin(e)))
    cam.location = ctr + d * dist
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    p = f"{base}_{i}{ext}"
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    frames.append(p)
print("PREVIEW", " ".join(frames))
