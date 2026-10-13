# -*- coding: utf-8 -*-
"""Zwischenstufen des per Skript gebauten Dachses sichtbar machen (für den Katalog, nicht für die Demo).

Aufruf (aus dem Projektordner):
  blender -b --factory-startup -P styles/blender-rig/blender/stages.py -- --tmp <Temp-Ordner>
  .venv/bin/python styles/blender-rig/scripts/compose_stages.py --tmp <Temp-Ordner>

1. Baut den Dachs mit dem unveränderten shared/3d/blender/build_badger.py neu, aber in den Temp-Ordner
   (--out, --no-preview, --no-notes, --save-blend). shared/ wird nicht verändert. Vergleicht das neue
   badger.glb Byte für Byte mit shared/3d/badger.glb (Deterministik).
2. Öffnet die gespeicherte .blend und rendert mit Workbench (schnell, flach, transparenter Hintergrund):
   parts.png     Grundformen: Figur nach losen Teilen getrennt, jedes Teil eine Farbe (Ruhepose)
   body.png      Figur einfarbig grau (Ruhepose), Unterlage für die Knochen
   bones.png     21 Knochen als Oktaeder wie in Blender, Farben wie in der Godot-Demo (Ruhepose)
   weights.png   Gewichte: Punktfarbe = mit den Gewichten gemischte Farbe der Knochen
   walk.png      Walk an 6 Zeitpunkten (gesampelte Schlüssel 0, 5, …, 25) nebeneinander, Seitenansicht
   walk_bones.png  die Knochen dieser 6 Posen
   walk_curves.json  Höhe von Knöchel und Zehenspitze beider Füße in allen 31 Schlüsseln von Walk
   stages.json   Zahlen (Teile, Dreiecke, Knochen, Schlüssel je Animation, Byte-Vergleich)
Zusammensetzen und Beschriften: scripts/compose_stages.py.
"""
import json
import math
import os
import subprocess
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
TMP = os.path.abspath(argv[argv.index("--tmp") + 1]) if "--tmp" in argv else "/tmp/blender-rig-stages"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
BUILD = os.path.join(ROOT, "shared", "3d", "blender", "build_badger.py")
os.makedirs(TMP, exist_ok=True)

# --- 1. Neu bauen (in den Temp-Ordner) ---------------------------------------------------------------
blend = os.path.join(TMP, "badger.blend")
res = subprocess.run([bpy.app.binary_path, "-b", "--factory-startup", "-P", BUILD, "--", "--out", TMP,
                      "--no-preview", "--no-notes", "--save-blend", blend], capture_output=True, text=True)
build_log = [l for l in res.stdout.splitlines() if l.startswith("BADGER")]
print("\n".join(build_log))
if res.returncode or not os.path.exists(blend):
    print(res.stdout[-2000:], res.stderr[-2000:])
    raise SystemExit("build_badger.py fehlgeschlagen")
with open(os.path.join(TMP, "badger.glb"), "rb") as a, open(os.path.join(ROOT, "shared", "3d", "badger.glb"), "rb") as b:
    same = a.read() == b.read()
print("STAGES glb identisch mit shared/3d/badger.glb:", same)

# --- 2. Rendern ------------------------------------------------------------------------------------------
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene
arm = bpy.data.objects["Armature"]
body = bpy.data.objects["Badger_high"]
parcel = bpy.data.objects["Parcel_high"]
for o in list(sc.objects):
    if o not in (arm, body, parcel):
        o.hide_render = True
arm.hide_render = True
arm.animation_data.action = None
for tr in arm.animation_data.nla_tracks:
    tr.mute = True

sc.render.engine = "BLENDER_WORKBENCH"
sc.render.film_transparent = True
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGBA"
sc.display.render_aa = "16"
sh = sc.display.shading
sh.light = "STUDIO"
sh.show_shadows = False
sh.show_cavity = False
sh.show_object_outline = True
sh.object_outline_color = (0.08, 0.08, 0.1)
sh.show_specular_highlight = False
sc.view_settings.view_transform = "Standard"

cam_data = bpy.data.cameras.new("StageCam")
cam_data.type = "ORTHO"
cam = bpy.data.objects.new("StageCam", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam


def aim(location, target, ortho, res):
    cam.location = Vector(location)
    d = Vector(target) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cam_data.ortho_scale = ortho
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100


def render(name):
    sc.render.filepath = os.path.join(TMP, name)
    bpy.ops.render.render(write_still=True)
    print("STAGES render", name)


SIDE_COL = {"mid": (1.0, 0.80, 0.28), "L": (0.30, 0.82, 1.0), "R": (1.0, 0.42, 0.72),
            "soft": (0.50, 0.95, 0.52), "root": (0.80, 0.80, 0.84)}


def bone_group(n):
    if n == "root":
        return "root"
    if n.startswith("scarf") or n == "tail":
        return "soft"
    if n.endswith(".L"):
        return "L"
    if n.endswith(".R"):
        return "R"
    return "mid"


def srgb_to_lin(c):
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def bone_objects(offset=Vector((0, 0, 0)), tag=""):
    """Oktaeder je Knochen aus der aktuellen Pose (Armature-Raum = Welt, das Objekt sitzt im Ursprung)."""
    objs = []
    for pb in arm.pose.bones:
        h, t = pb.head.copy(), pb.tail.copy()
        y = t - h
        ln = y.length
        x = pb.x_axis.normalized() * ln * 0.1
        z = pb.z_axis.normalized() * ln * 0.1
        c = h + y * 0.1
        verts = [h, c + x, c + z, c - x, c - z, t]
        verts = [v + offset for v in verts]
        faces = [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1), (5, 2, 1), (5, 3, 2), (5, 4, 3), (5, 1, 4)]
        me = bpy.data.meshes.new(f"bone_{tag}{pb.name}")
        me.from_pydata([tuple(v) for v in verts], [], faces)
        ob = bpy.data.objects.new(me.name, me)
        ob.color = (*srgb_to_lin(SIDE_COL[bone_group(pb.name)]), 1.0)
        sc.collection.objects.link(ob)
        objs.append(ob)
    return objs


def hide(objs, flag):
    for o in objs:
        o.hide_render = flag


VIEW = dict(location=(2.3, -2.9, 1.25), target=(0.02, 0.0, 0.52), ortho=1.32, res=(720, 900))
stats = {"glb_identical": same, "build_log": build_log}

# Ruhepose
arm.data.pose_position = "REST"
bpy.context.view_layer.update()
aim(**VIEW)

# a) Grundformen: nach losen Teilen trennen (Kopie), jedes Teil eine Farbe
parts = []
for src in (body, parcel):
    ob = src.copy()
    ob.data = src.data.copy()
    ob.modifiers.clear()
    ob.parent = None
    sc.collection.objects.link(ob)
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.separate(type="LOOSE")
    bpy.ops.object.mode_set(mode="OBJECT")
    parts += list(bpy.context.selected_objects)
parts.sort(key=lambda o: (round(-o.bound_box[0][2], 3), o.name))
golden = 0.61803398875
for i, o in enumerate(parts):
    hue = (0.08 + i * golden) % 1.0
    sat, val = (0.50, 0.95) if i % 2 == 0 else (0.62, 0.80)
    import colorsys
    o.color = (*srgb_to_lin(colorsys.hsv_to_rgb(hue, sat, val)), 1.0)
stats["loose_parts"] = len(parts)
hide([body, parcel], True)
sh.color_type = "OBJECT"
render("parts.png")
hide(parts, True)

# b) Figur grau + Knochen (Ruhepose)
hide([body, parcel], False)
sh.color_type = "SINGLE"
sh.single_color = (0.62, 0.63, 0.66)
render("body.png")
bones = bone_objects(tag="rest_")
hide([body, parcel], True)
sh.color_type = "OBJECT"
sh.show_object_outline = True
render("bones.png")
hide([body, parcel], False)

# c) Gewichte: Farbe = Summe Gewicht x Knochenfarbe (Farbattribut, Workbench "Attribute")
names = [b.name for b in arm.data.bones]
bone_rgb = {}
for i, n in enumerate(names):
    hue = (i * golden) % 1.0
    bone_rgb[n] = colorsys.hsv_to_rgb(hue, 0.75, 0.95)
for ob in (body, parcel):
    me = ob.data
    attr = me.color_attributes.new("BoneColor", "FLOAT_COLOR", "POINT")
    gname = {g.index: g.name for g in ob.vertex_groups}
    for v in me.vertices:
        acc = [0.0, 0.0, 0.0]
        tot = 0.0
        for g in v.groups:
            n = gname[g.group]
            if n in bone_rgb and g.weight > 0:
                for k in range(3):
                    acc[k] += bone_rgb[n][k] * g.weight
                tot += g.weight
        col = [a / tot for a in acc] if tot > 0 else [0.2, 0.2, 0.2]
        attr.data[v.index].color = (*srgb_to_lin(col), 1.0)
    me.color_attributes.active_color = attr
sh.color_type = "VERTEX"
render("weights.png")
stats["bone_colors"] = {n: [round(c, 3) for c in bone_rgb[n]] for n in names}

# d) Walk: 6 gesampelte Schlüssel nebeneinander, Seitenansicht (rechte Seite, wie die Hafenkamera)
hide(bones, True)
arm.data.pose_position = "POSE"
walk = bpy.data.actions["Walk"]
arm.animation_data.action = walk
if hasattr(arm.animation_data, "action_slot") and walk.slots:
    arm.animation_data.action_slot = walk.slots[0]
keys = [0, 5, 10, 15, 20, 25]
SP = 0.62
poses, pbones = [], []
for i, f in enumerate(keys):
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    off = Vector((i * SP, 0, 0))
    for src in (body, parcel):
        me = bpy.data.meshes.new_from_object(src.evaluated_get(dg))
        me.transform(src.matrix_world)
        ob = bpy.data.objects.new(f"walk{f}_{src.name}", me)
        ob.location = off
        sc.collection.objects.link(ob)
        poses.append(ob)
    pbones += bone_objects(offset=off, tag=f"w{f}_")
curves = {"frames": [], "L_ankle": [], "R_ankle": [], "L_toe": [], "R_toe": []}
for f in range(0, 31):
    sc.frame_set(f)
    curves["frames"].append(f)
    for s in "LR":
        pb = arm.pose.bones["foot." + s]
        curves[f"{s}_ankle"].append(round(pb.head.z, 4))
        curves[f"{s}_toe"].append(round(pb.tail.z, 4))
with open(os.path.join(TMP, "walk_curves.json"), "w") as fh:
    json.dump(curves, fh)
hide([body, parcel], True)
hide(pbones, True)
sh.color_type = "MATERIAL"
mid = (len(keys) - 1) * SP / 2
aim(location=(mid, -6.0, 0.55), target=(mid, 0.0, 0.55), ortho=len(keys) * SP + 0.1, res=(1800, 560))
render("walk.png")
hide(poses, True)
hide(pbones, False)
sh.color_type = "OBJECT"
render("walk_bones.png")

# Zahlen
for a in bpy.data.actions:
    if a.name in ("Idle", "Walk", "Wave"):
        stats.setdefault("actions", {})[a.name] = [int(a.frame_range[0]), int(a.frame_range[1])]
stats["bones"] = len(arm.data.bones)
stats["deform_bones"] = sum(1 for b in arm.data.bones if b.use_deform)
stats["walk_keys"] = keys
with open(os.path.join(TMP, "stages.json"), "w") as fh:
    json.dump(stats, fh, indent=1, ensure_ascii=False)
print("STAGES fertig:", TMP)
