# PS1-Fassung des Dachses: badger_low.glb (876 Dreiecke) mit Decimate (Collapse) auf das Budget der
# Konsole bringen (Figur 300–800 Dreiecke). Knochen, Gewichte, Animationen und Materialnamen bleiben.
#
#   blender -b --factory-startup -P styles/ps1-lowpoly/blender/decimate_badger.py -- \
#       shared/3d/badger_low.glb styles/ps1-lowpoly/demo/models/badger_ps1.glb 0.90
#
# Verhältnis 0,90 (864 -> 777 Dreiecke, mit Paket 789): Bei 0,80 (703) blieben Splitter an Mützenschirm und
# Ohren und eine dunkle Linie im Gesicht, die in der Nahaufnahme (ca. 70 px Figurenhöhe) sichtbar wären.
# Die Option Symmetrie (Achse Y) ergab bei 0,90 eine Kerbe im Gesicht und wird nicht genutzt.
#
# Hinweis aus shared/3d/README.md: Ein Durchlauf durch den Blender-Import verschiebt Knochen um bis zu 4 mm
# (auch in der Nahaufnahme unsichtbar) und legt ein Objekt "Icosphere" für die Knochenanzeige an, das nicht
# exportiert wird.
import sys

import bpy

src, out, ratio = sys.argv[sys.argv.index("--") + 1:][:3]
ratio = float(ratio)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)


def tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


ob = bpy.data.objects["Badger"]
before = tris(ob)
bpy.context.view_layer.objects.active = ob
for o in bpy.context.selected_objects:
    o.select_set(False)
ob.select_set(True)

mod = ob.modifiers.new("Decimate", "DECIMATE")
mod.decimate_type = "COLLAPSE"
mod.ratio = ratio
mod.use_collapse_triangulate = True
# vor den Armature-Modifier, damit auf der Ruhepose reduziert wird
bpy.ops.object.modifier_move_to_index(modifier="Decimate", index=0)
bpy.ops.object.modifier_apply(modifier="Decimate")
after = tris(ob)

parcel = bpy.data.objects.get("Parcel")
total = after + (tris(parcel) if parcel else 0)
actions = sorted(a.name for a in bpy.data.actions)
print(f"BADGER_TRIS before={before} after={after} total_with_parcel={total} actions={actions}")

bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_yup=True, export_apply=False,
                          export_cameras=False, export_lights=False, export_animations=True,
                          export_animation_mode="ACTIONS")
