# -*- coding: utf-8 -*-
"""Posen-Vorlage für das KI-Figurenblatt und Ersatzweg für die Figur: der geriggte Dachs aus shared/3d
in der Seitenansicht, jedes Material als flacher Grauwert (Tonplatte) mit schwarzer Freestyle-Kontur.

Rendert 8 Phasen des Laufzyklus (Walk, 1,0 s, je 1/8) und 4 Stehbilder (Idle) einzeln mit transparentem
Hintergrund (mit --color in den Originalfarben mit weichem Licht). scripts/compose_layout.py setzt daraus das 1536×1024-Blatt, das genimg.py als erste Referenz
bekommt (Layout, Beinstellungen, Tonwerte), das Kostüm-Referenzblatt als zweite.

Aufruf (aus dem Projektordner):
  blender -b --factory-startup -P styles/einbit-pixel/blender/pose_layout.py -- --out <ordner> [--px 480]
Gibt je Bild die Lage beider Füße (tiefster Punkt, x vorn/hinten) in Metern aus.
"""
import argparse
import math
import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--glb", default="shared/3d/badger.glb")
ap.add_argument("--out", required=True)
ap.add_argument("--px", type=int, default=480, help="Kantenlänge eines Einzelbildes")
ap.add_argument("--line", type=float, default=3.0, help="Freestyle-Linienbreite in Pixeln")
ap.add_argument("--color", action="store_true", help="Originalmaterialien mit weichem Licht statt Tonplatte (Vorlage fürs Bildmodell)")
A = ap.parse_args(argv)

# Tonwerte je Material (0 = schwarz, 1 = weiß): so soll die Figur in 1 Bit gelesen werden.
TONES = {
    "FurDark": 0.02, "Nose": 0.0, "Eye": 0.0,
    "FurLight": 1.0, "Shirt": 1.0, "Brass": 1.0,
    "Cap": 0.30, "Vest": 0.30, "Satchel": 0.55,
    "Scarf": 0.55, "Parcel": 0.80,
}

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = 30
bpy.ops.import_scene.gltf(filepath=os.path.abspath(A.glb))
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 8
sc.render.resolution_x = sc.render.resolution_y = A.px
sc.render.film_transparent = True
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGBA"
sc.view_settings.view_transform = "Standard"
sc.render.use_freestyle = True
sc.render.line_thickness_mode = "ABSOLUTE"
sc.render.line_thickness = A.line
vl = sc.view_layers[0]
vl.use_freestyle = True
fs = vl.freestyle_settings
ls = fs.linesets[0] if len(fs.linesets) else fs.linesets.new("Lines")
ls.select_by_visibility = True
ls.select_by_edge_types = True
ls.select_silhouette = True
ls.select_border = True
ls.select_crease = False
ls.select_material_boundary = True
if ls.linestyle is None:
    ls.linestyle = bpy.data.linestyles.new("Ink")
ls.linestyle.color = (0, 0, 0)
ls.linestyle.thickness = A.line

world = bpy.data.worlds.new("W")
sc.world = world

cam = bpy.data.cameras.new("Cam")
cam.type = "ORTHO"
cam.ortho_scale = 1.30
cam_ob = bpy.data.objects.new("Cam", cam)
sc.collection.objects.link(cam_ob)
sc.camera = cam_ob
cam_ob.location = (0.0, -4.0, 0.60)
cam_ob.rotation_euler = (math.radians(90), 0, 0)

arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
meshes = [o for o in bpy.data.objects if o.type == "MESH" and any(m.type == "ARMATURE" for m in o.modifiers)]
for o in bpy.data.objects:   # Knochenform-Hilfsobjekte nicht rendern
    if o.type == "MESH" and o not in meshes:
        o.hide_render = True

# Materialien durch flache Grauwerte (Emission) ersetzen
if A.color:
    sc.render.use_freestyle = False
    world.use_nodes = True
    bgn = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bgn.inputs["Color"].default_value = (0.8, 0.82, 0.86, 1)
    bgn.inputs["Strength"].default_value = 0.9
    key = bpy.data.lights.new("Key", "SUN")
    key.energy = 3.0
    key_ob = bpy.data.objects.new("Key", key)
    sc.collection.objects.link(key_ob)
    key_ob.rotation_euler = (math.radians(55), 0, math.radians(-30))
    TONES = {}
flat = {}
for name, v in TONES.items():
    m = bpy.data.materials.new("flat_" + name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (v ** 2.2, v ** 2.2, v ** 2.2, 1)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], out.inputs[0])
    flat[name] = m
for ob in meshes:
    for slot in ob.material_slots:
        if slot.material is None:
            continue
        base = slot.material.name.split(".")[0]
        if base in flat:
            slot.material = flat[base]
        elif not A.color:
            print("WARN unbekanntes Material", slot.material.name)


def set_action(name):
    ad = arm.animation_data or arm.animation_data_create()
    act = next(a for a in bpy.data.actions if a.name == name or a.name.startswith(name + "_") or a.name.startswith(name + "."))
    ad.action = act
    if getattr(ad, "action_slot", None) is None and len(act.slots):
        ad.action_slot = act.slots[0]
    return act


def foot_info():
    dg = bpy.context.evaluated_depsgraph_get()
    res = {}
    for ob in meshes:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ob.matrix_world
        for side in "LR":
            vg = ob.vertex_groups.get("foot." + side)
            if vg is None:
                continue
            pts = [mw @ v.co for v in me.vertices if any(g.group == vg.index and g.weight > 0.5 for g in v.groups)]
            if pts:
                res[side] = (min(p.z for p in pts), min(p.x for p in pts), max(p.x for p in pts))
        ev.to_mesh_clear()
    return res


os.makedirs(A.out, exist_ok=True)
jobs = [("walk", "Walk", 30.0 * k / 8.0) for k in range(8)] + [("idle", "Idle", f) for f in (0, 15, 30, 45)]
for i, (tag, action, f) in enumerate(jobs):
    set_action(action)
    sc.frame_set(int(f), subframe=f - int(f))
    fi = foot_info()
    print("FOOT %s %02d f=%.2f " % (tag, i, f) + " ".join(
        "%s: z %.3f x %.3f..%.3f" % (s, *fi[s]) for s in sorted(fi)))
    sc.render.filepath = os.path.join(A.out, "%s_%02d.png" % (tag, i))
    bpy.ops.render.render(write_still=True)
print("ortho_scale", cam.ortho_scale, "px", A.px, "cam_z", cam_ob.location.z)
