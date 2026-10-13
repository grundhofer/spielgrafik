# Dachs für den Eintrag handpainted-3d: gebackene Umgebungsverdeckung als Vertexfarbe COLOR_0.
#
# Nicht über glTF-Import/Export (verschiebt Knochen um bis zu 4 mm, siehe shared/3d/README.md), sondern aus der
# .blend, die shared/3d/blender/build_badger.py mit --save-blend schreibt. Zwei Schritte:
#
#   blender -b --factory-startup -P shared/3d/blender/build_badger.py -- \
#       --out <tmp>/badger_build --no-preview --no-notes --save-blend <tmp>/badger_build/badger.blend
#   blender -b --factory-startup -P styles/handpainted-3d/blender/bake_badger_ao.py -- \
#       <tmp>/badger_build/badger.blend styles/handpainted-3d/demo/models/badger_hp.glb [--no-ao]
#
# Mit --no-ao entsteht dasselbe glb wie shared/3d/badger.glb (Prüfung, dass der Weg nichts anderes verändert).
# Gebacken wird in der Ruhepose (= Bindepose), Figur und Paket verdecken sich gegenseitig:
#   R = Nahverdeckung (Strahlen bis 6 cm): Falten, Schal am Hals, Achseln, unter Mützenschirm und Tasche
#   G = Fernverdeckung (Strahlen bis 22 cm): zwischen Arm und Körper, unter dem Schal, Beine unter der Weste
#   B = 1, A = 1
# Gleiches Verfahren wie bake() in build_harbor_hp.py (feste Strahlrichtungen, BVH-Baum, deterministisch).
import json
import math
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND, OUT = argv[0], argv[1]
NO_AO = "--no-ao" in argv
NEAR_DIST, FAR_DIST, RAYS, LIFT = 0.06, 0.22, 64, 0.004


def fib_dirs(n):
    out = []
    for i in range(n):
        u = (i + 0.5) / n
        r, phi = math.sqrt(u), i * 2.399963229728653
        out.append(Vector((r * math.cos(phi), r * math.sin(phi), math.sqrt(1.0 - u))))
    return out


def bake(objs):
    verts, polys = [], []
    for ob in objs:
        off = len(verts)
        verts += [ob.matrix_world @ v.co for v in ob.data.vertices]
        polys += [[off + i for i in p.vertices] for p in ob.data.polygons]
    bvh = BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)
    hemi = fib_dirs(RAYS)
    stats = {}
    for ob in objs:
        me, mw = ob.data, ob.matrix_world
        nm = mw.to_3x3().inverted().transposed()
        for a in list(me.color_attributes):
            me.color_attributes.remove(a)
        ca = me.color_attributes.new(name="Color", type="FLOAT_COLOR", domain="CORNER")
        me.color_attributes.active_color = ca
        me.color_attributes.render_color_index = 0
        cn = me.corner_normals
        acc, n_l, dark = [0.0, 0.0], 0, 0
        for p in me.polygons:
            c = mw @ p.center
            for li in p.loop_indices:
                v = mw @ me.vertices[me.loops[li].vertex_index].co
                n = (nm @ cn[li].vector).normalized()
                o = v.lerp(c, 0.15) + n * LIFT
                rot = n.to_track_quat("Z", "Y").to_matrix()
                hn = hf = 0
                for d in hemi:
                    hit = bvh.ray_cast(o, rot @ d, FAR_DIST)
                    if hit[0] is not None:
                        hf += 1
                        if hit[3] < NEAR_DIST:
                            hn += 1
                near, far = 1.0 - hn / RAYS, 1.0 - hf / RAYS
                ca.data[li].color = (near, far, 1.0, 1.0)
                acc[0] += near
                acc[1] += far
                dark += far < 0.6
                n_l += 1
        stats[ob.name] = {"mean_near_far": [round(x / max(n_l, 1), 3) for x in acc],
                          "share_far_below_0.6": round(dark / max(n_l, 1), 3)}
    print("BADGER_AO " + json.dumps(stats))


bpy.ops.wm.open_mainfile(filepath=BLEND)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
body, parcel = bpy.data.objects["Badger_high"], bpy.data.objects["Parcel_high"]
others = [o for o in bpy.data.objects if o.type == "MESH" and o not in (body, parcel)]
for pb in arm.pose.bones:                      # Ruhepose wie beim Export in build_badger.py
    pb.location = (0, 0, 0)
    pb.rotation_quaternion = (1, 0, 0, 0)
    pb.scale = (1, 1, 1)
bpy.context.scene.frame_set(0)
if not NO_AO:
    bake([body, parcel])
for o in others:                               # Namen frei machen wie build_badger.py
    o.name = o.name + "_x"
    o.data.name = o.data.name + "_x"
body.name = body.data.name = "Badger"
parcel.name = parcel.data.name = "Parcel"

bpy.ops.object.select_all(action="DESELECT")
arm.select_set(True)
body.select_set(True)
parcel.select_set(True)
bpy.context.view_layer.objects.active = arm
# Exporteinstellungen wie export_glb() in shared/3d/blender/build_badger.py, dazu die aktive Vertexfarbe
extra = {} if NO_AO else {"export_vertex_color": "ACTIVE", "export_all_vertex_colors": False}
bpy.ops.export_scene.gltf(
    filepath=OUT, export_format="GLB", use_selection=True, export_yup=True, export_apply=False,
    export_texcoords=True, export_normals=True, export_materials="EXPORT", export_image_format="NONE",
    export_skins=True, export_influence_nb=4, export_def_bones=False, export_morph=False,
    export_animations=True, export_animation_mode="ACTIONS", export_nla_strips=True,
    export_force_sampling=True, export_optimize_animation_size=False, export_reset_pose_bones=True,
    export_rest_position_armature=True, export_anim_slide_to_zero=False, export_frame_range=False,
    export_extras=False, export_cameras=False, export_lights=False, **extra)
print("BADGER_HP " + OUT)
