# Low-Poly-Fassung des gemeinsamen Hafens (Katalogeintrag lowpoly-flat).
#
#   blender -b --factory-startup -P styles/lowpoly-flat/blender/build_lowpoly.py -- \
#       shared/3d/harbor.glb styles/lowpoly-flat/demo/models/harbor_lowpoly.glb \
#       --report styles/lowpoly-flat/assets/harbor_lowpoly.json
#
# Liest harbor.glb aus shared/3d, ändert nur Geometrie und Flächendaten und exportiert eine eigene
# glb mit denselben Objekt-, Empty- und Materialnamen:
#   1. Gelände und Felsen grob reduzieren (Decimate „Collapse“), damit große Facetten entstehen;
#      danach Rock/Sand/Grass nach derselben Regel wie build_harbor.py neu zuweisen (pro Facette).
#   2. Alle Flächen flach schattieren (eigene Normalen gelöscht): Jede Facette hat genau eine Normale.
#   3. Je Facette eine Farbabweichung als Vertexfarbe (COLOR_0): R = Helligkeit, G = Farbton,
#      Zufall mit festem Seed je Objekt. Der Shader in Godot macht daraus ±wenige Prozent.
# Deterministisch: feste Seeds, feste Reihenfolge.
import json
import math
import random
import sys
import zlib

import bmesh
import bpy

WATER_Z = -0.8          # Blender-z der Wasserlinie (Godot-y)

# Objekt -> Anteil der Dreiecke, der bleibt (Decimate Collapse). Nicht genannte Objekte bleiben gleich.
DECIMATE = {
    "WestHill": 0.22,
    "Headland": 0.30,
    "RocksSea": 0.45,
    "IslandsFar": 0.6,
}
TERRAIN = {"WestHill", "Headland", "IslandsFar"}
# Objekte ohne Farbabweichung (Glas leuchtet gleichmäßig, Meer wird in Godot ersetzt)
NO_JITTER = {"CottageWindow", "LanternGlass", "LighthouseLamp", "Sea"}


def args():
    a = sys.argv[sys.argv.index("--") + 1:]
    src, out = a[0], a[1]
    report = a[a.index("--report") + 1] if "--report" in a else None
    return src, out, report


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def decimate(ob, ratio):
    mod = ob.modifiers.new("Decimate", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = ratio
    mod.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = ob
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.ops.object.modifier_apply(modifier=mod.name)


def terrain_materials(ob):
    """Wie terrain_mats() in shared/3d/blender/build_harbor.py, aber auf die neuen Facetten."""
    names = [m.name for m in ob.data.materials]
    idx = {n: names.index(n) for n in ("Rock", "Sand", "Grass") if n in names}
    me = ob.data
    mw = ob.matrix_world
    for p in me.polygons:
        n = (mw.to_3x3() @ p.normal).normalized()
        cz = (mw @ p.center).z
        if n.z < 0.8:
            name = "Rock"
        elif cz < WATER_Z + 0.5:
            name = "Sand"
        else:
            name = "Grass"
        p.material_index = idx.get(name, idx.get("Rock", 0))


def flat_shade(ob):
    me = ob.data
    if me.has_custom_normals:
        bpy.context.view_layer.objects.active = ob
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    me.shade_flat()


def face_jitter(ob):
    me = ob.data
    rng = random.Random(zlib.crc32(ob.name.encode()))
    for a in list(me.color_attributes):
        me.color_attributes.remove(a)
    col = me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
    data = [0.0] * (len(me.loops) * 4)
    for p in me.polygons:
        r, g = (0.5, 0.5) if ob.name in NO_JITTER else (rng.random(), rng.random())
        for li in p.loop_indices:
            data[li * 4:li * 4 + 4] = (r, g, 1.0, 1.0)
    col.data.foreach_set("color", data)
    me.color_attributes.active_color = col
    me.color_attributes.render_color_index = 0


def main():
    src, out, report = args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # merge_vertices: sonst ist jedes Mesh an UV-Nähten und harten Kanten aufgetrennt, und Decimate
    # reißt Löcher entlang dieser Nähte.
    bpy.ops.import_scene.gltf(filepath=src, merge_vertices=True)
    info = {}
    for ob in sorted((o for o in bpy.data.objects if o.type == "MESH"), key=lambda o: o.name):
        before = tri_count(ob)
        if ob.name in DECIMATE:
            decimate(ob, DECIMATE[ob.name])
        if ob.name in TERRAIN:
            terrain_materials(ob)
        flat_shade(ob)
        face_jitter(ob)
        info[ob.name] = {"before": before, "after": tri_count(ob)}
        print(f"{ob.name:16s} {before:6d} -> {info[ob.name]['after']:6d} Dreiecke")
    tot_b = sum(v["before"] for v in info.values())
    tot_a = sum(v["after"] for v in info.values())
    print(f"Summe {tot_b} -> {tot_a}")
    bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_yup=True, export_apply=True,
                              export_cameras=False, export_lights=False, export_normals=True,
                              export_vertex_color="ACTIVE", export_all_vertex_colors=False)
    if report:
        with open(report, "w") as f:
            json.dump({"source": src, "objects": info, "total_before": tot_b, "total_after": tot_a,
                       "decimate": DECIMATE}, f, indent=1)


main()
