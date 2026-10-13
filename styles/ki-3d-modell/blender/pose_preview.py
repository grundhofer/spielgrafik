# Posen einer geriggten glb rendern (Workbench, Textur): je Animation einige Bilder aus einer Richtung.
#
#   blender -b --factory-startup -P styles/ki-3d-modell/blender/pose_preview.py -- in.glb out_prefix \
#       --anim Walk --frames 0,4,8,12 --az 90 [--size 360] [--elev 5]
import bpy, math, os, sys
import mathutils

argv = sys.argv[sys.argv.index("--") + 1:]
src, prefix = argv[0], argv[1]
opt = lambda k, d: argv[argv.index(k) + 1] if k in argv else d
anim = opt("--anim", "Walk")
frames = [int(x) for x in opt("--frames", "0").split(",")]
az = math.radians(float(opt("--az", "90")))
size = int(opt("--size", "360"))
elev = math.radians(float(opt("--elev", "5")))

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=os.path.abspath(src))
arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
act = next(a for a in bpy.data.actions if a.name.startswith(anim))
arm.animation_data_create()
arm.animation_data.action = act
if hasattr(arm.animation_data, "action_suitable_slots") and len(act.slots):
    arm.animation_data.action_slot = act.slots[0]
for t in arm.animation_data.nla_tracks:
    t.mute = True
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.display.shading.light = "STUDIO"
sc.display.shading.color_type = "TEXTURE"
sc.render.resolution_x = sc.render.resolution_y = size
sc.view_settings.view_transform = "Standard"
sc.world = bpy.data.worlds.new("w")
cd = bpy.data.cameras.new("c"); cd.type = "ORTHO"; cd.ortho_scale = 1.25
cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
ctr = mathutils.Vector((0.0, 0.0, 0.52))
d = mathutils.Vector((math.cos(az) * math.cos(elev), math.sin(az) * math.cos(elev), math.sin(elev)))
cam.location = ctr + d * 4
cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
out = []
for f in frames:
    sc.frame_set(f)
    sc.render.filepath = f"{prefix}_{anim}_{f:02d}.png"
    bpy.ops.render.render(write_still=True)
    out.append(sc.render.filepath)
print("POSES", " ".join(out))
