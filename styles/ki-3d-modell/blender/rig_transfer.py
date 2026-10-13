# KI-Mesh (TripoSR, gesäubert und gebacken) auf das vorhandene Dachs-Rig aus shared/3d setzen.
#
#   # 1. Rig-Quelle neu bauen (schreibt nur in den eigenen Ordner, bytegleich zu shared/3d/badger.glb):
#   blender -b --factory-startup -P shared/3d/blender/build_badger.py -- --out styles/ki-3d-modell/work/rigsrc \
#       --no-preview --no-notes --save-blend styles/ki-3d-modell/work/rigsrc/badger.blend
#   # 2. Gewichte übertragen und exportieren:
#   blender -b --factory-startup styles/ki-3d-modell/work/rigsrc/badger.blend \
#       -P styles/ki-3d-modell/blender/rig_transfer.py -- --mesh styles/ki-3d-modell/work/badger_static.glb \
#       --out styles/ki-3d-modell/demo/models/badger_tsr.glb [--report r.json]
#
# Gewichte von der handgebauten Figur (Badger_high + Parcel_high) per Data-Transfer-Modifier (nächste Fläche,
# interpoliert) auf das KI-Mesh; Kopf, Paket und Krallen bleiben dadurch fast starr. (Blenders automatische
# Gewichte direkt auf dem KI-Mesh wurden versucht: "Bone Heat Weighting: failed to find solution for one or
# more bones", der Export hatte danach keinen Skin. Nicht weiter verfolgt.)
# Danach: höchstens 4 Einflüsse je Eckpunkt, normalisiert; Export mit denselben glTF-Einstellungen wie
# build_badger.py (Aktionen Idle, Walk, Wave als NLA-Spuren, gesampelt).
import bpy, json, os, sys, time
import numpy as np
import mathutils

argv = sys.argv[sys.argv.index("--") + 1:]
import argparse
ap = argparse.ArgumentParser(prog="rig_transfer.py")
ap.add_argument("--mesh", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--report", default="")
ap.add_argument("--keep-blend", default="", help="optional .blend zur Kontrolle (nicht einchecken)")
A = ap.parse_args(argv)
T0 = time.time()
R = {"method": "data_transfer POLYINTERP_NEAREST", "mesh": A.mesh}

arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
src_body = bpy.data.objects["Badger_high"]
src_parcel = bpy.data.objects["Parcel_high"]

bpy.ops.object.select_all(action="DESELECT")
bpy.ops.import_scene.gltf(filepath=os.path.abspath(A.mesh))
tsr = next(o for o in bpy.context.selected_objects if o.type == "MESH")
# glTF-Import legt die Figur ggf. unter ein Empty: lösen, Transformation übernehmen
mw = tsr.matrix_world.copy()
tsr.parent = None
tsr.matrix_world = mw
bpy.ops.object.select_all(action="DESELECT")
tsr.select_set(True)
bpy.context.view_layer.objects.active = tsr
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def verts_world(ob):
    me = ob.data
    v = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", v)
    v = v.reshape(-1, 3)
    M = np.array(ob.matrix_world)
    return v @ M[:3, :3].T + M[:3, 3]


# Ausrichten: Fußsohlen beider Figuren in x/y zur Deckung bringen (Eckpunkte unter 3 cm Höhe, seitlich der
# Mitte, damit ein geratener Schwanz am Boden nicht mitzählt). Die Füße müssen auf den Fußknochen sitzen.
Vt = verts_world(tsr)
Vs = np.concatenate([verts_world(src_body)])
soles = lambda V: V[(V[:, 2] < V[:, 2].min() + 0.03) & (np.abs(V[:, 1]) > 0.06)]
ct = 0.5 * (soles(Vt)[:, :2].min(0) + soles(Vt)[:, :2].max(0))
cs = 0.5 * (soles(Vs)[:, :2].min(0) + soles(Vs)[:, :2].max(0))
d = cs - ct
tsr.data.transform(mathutils.Matrix.Translation((d[0], d[1], 0.0)))
R["align_offset_m"] = [round(float(x), 4) for x in d]
Vt = verts_world(tsr)
R["tsr_bbox"] = [[round(float(x), 3) for x in Vt.min(0)], [round(float(x), 3) for x in Vt.max(0)]]
R["src_bbox"] = [[round(float(x), 3) for x in Vs.min(0)], [round(float(x), 3) for x in Vs.max(0)]]

deform = [b.name for b in arm.data.bones if b.use_deform]
R["deform_bones"] = len(deform)

# Quelle: Kopie von Figur + Paket, zu einem Objekt vereint (Gruppen nach Knochennamen)
bpy.ops.object.select_all(action="DESELECT")
tmp = []
for o in (src_body, src_parcel):
    c = o.copy()
    c.data = o.data.copy()
    c.modifiers.clear()
    bpy.context.collection.objects.link(c)
    tmp.append(c)
for c in tmp:
    c.select_set(True)
bpy.context.view_layer.objects.active = tmp[0]
bpy.ops.object.join()
src = tmp[0]
for name in deform:
    if name not in tsr.vertex_groups:
        tsr.vertex_groups.new(name=name)
m = tsr.modifiers.new("Weights", "DATA_TRANSFER")
m.object = src
m.use_object_transform = True
m.use_vert_data = True
m.data_types_verts = {"VGROUP_WEIGHTS"}
m.vert_mapping = "POLYINTERP_NEAREST"
m.layers_vgroup_select_src = "ALL"
m.layers_vgroup_select_dst = "NAME"
bpy.ops.object.select_all(action="DESELECT")
tsr.select_set(True)
bpy.context.view_layer.objects.active = tsr
bpy.ops.object.modifier_apply(modifier=m.name)
bpy.data.objects.remove(src, do_unlink=True)
tsr.parent = arm
tsr.matrix_parent_inverse = arm.matrix_world.inverted()
am = tsr.modifiers.new("Armature", "ARMATURE")
am.object = arm

# Umhängetasche an der linken Hüfte: Data Transfer gibt ihr die Gewichte der nahen linken Hand, beim Winken
# zog sie sich dann lang (Winken wird in der Demo trotzdem nicht gezeigt, siehe style.json). Braune Eckpunkte (Farbe aus der gebackenen Textur) links am Körper, die vom linken
# Arm bewegt würden, hängen deshalb ganz an den Hüften.
import colorsys
img = next(n.image for n in tsr.active_material.node_tree.nodes if n.type == "TEX_IMAGE" and n.image)
W_, H_ = img.size
px = np.empty(W_ * H_ * 4, np.float32)
img.pixels.foreach_get(px)
px = px.reshape(H_, W_, 4)
uvd = tsr.data.uv_layers.active.data
vuv = {}
for lp in tsr.data.loops:
    vuv.setdefault(lp.vertex_index, uvd[lp.index].uv)
arm_l = {"hand.L", "forearm.L", "upper_arm.L"}
names_ = {g.index: g.name for g in tsr.vertex_groups}
hips = tsr.vertex_groups["hips"]
moved = 0
for v in tsr.data.vertices:
    co = tsr.matrix_world @ v.co
    if not (co.y > 0.10 and 0.22 < co.z < 0.62) or not v.groups:
        continue
    g = max(v.groups, key=lambda x: x.weight)
    if names_[g.group] not in arm_l:
        continue
    uv = vuv[v.index]
    r_, g_, b_ = px[min(int(uv.y * H_), H_ - 1), min(int(uv.x * W_), W_ - 1), :3]
    h, s_, val = colorsys.rgb_to_hsv(r_ ** (1 / 2.2), g_ ** (1 / 2.2), b_ ** (1 / 2.2))
    if 0.02 < h < 0.12 and s_ > 0.35 and 0.15 < val < 0.75:
        for gg in list(v.groups):
            tsr.vertex_groups[gg.group].remove([v.index])
        hips.add([v.index], 1.0, "REPLACE")
        moved += 1
R["satchel_vertices_to_hips"] = moved

# höchstens 4 Einflüsse, normalisiert
bpy.ops.object.select_all(action="DESELECT")
tsr.select_set(True)
bpy.context.view_layer.objects.active = tsr
bpy.ops.object.mode_set(mode="WEIGHT_PAINT")
bpy.ops.object.vertex_group_limit_total(group_select_mode="ALL", limit=4)
bpy.ops.object.vertex_group_normalize_all(group_select_mode="ALL", lock_active=False)
bpy.ops.object.mode_set(mode="OBJECT")

# Statistik: dominanter Knochen je Eckpunkt
names = [g.name for g in tsr.vertex_groups]
dom = {}
unweighted = 0
for v in tsr.data.vertices:
    if not v.groups:
        unweighted += 1
        continue
    g = max(v.groups, key=lambda x: x.weight)
    dom[names[g.group]] = dom.get(names[g.group], 0) + 1
R["dominant_bone_vertices"] = dict(sorted(dom.items(), key=lambda x: -x[1]))
R["unweighted_vertices"] = unweighted

# Export: nur Armature + KI-Figur; Namen wie in shared/3d (Mesh "Badger")
for o in list(bpy.data.objects):
    if o.type == "MESH" and o is not tsr:
        o.name = o.name + "_old"
tsr.name = "Badger"
tsr.data.name = "Badger"
bpy.ops.object.select_all(action="DESELECT")
arm.select_set(True)
tsr.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.context.scene.frame_set(0)
bpy.ops.export_scene.gltf(
    filepath=os.path.abspath(A.out), export_format="GLB", use_selection=True, export_yup=True, export_apply=False,
    export_texcoords=True, export_normals=True, export_materials="EXPORT", export_image_format="AUTO",
    export_skins=True, export_influence_nb=4, export_def_bones=False, export_morph=False,
    export_animations=True, export_animation_mode="ACTIONS", export_nla_strips=True,
    export_force_sampling=True, export_optimize_animation_size=False, export_reset_pose_bones=True,
    export_rest_position_armature=True, export_anim_slide_to_zero=False, export_frame_range=False,
    export_extras=False, export_cameras=False, export_lights=False)
R["glb_bytes"] = os.path.getsize(A.out)
R["tris"] = sum(len(p.vertices) - 2 for p in tsr.data.polygons)
R["t_total"] = round(time.time() - T0, 2)
if A.keep_blend:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(A.keep_blend))
rep = A.report or os.path.splitext(A.out)[0] + "_rig.json"
with open(rep, "w") as fh:
    json.dump(R, fh, indent=1)
print("[rig_transfer]", json.dumps(R))
