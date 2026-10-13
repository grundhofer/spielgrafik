# -*- coding: utf-8 -*-
"""Posen-Vorlage für das gemalte Laufblatt: rendert den Dachs aus shared/3d/badger.glb in 8 Laufphasen
(Seitenansicht, nach rechts) plus Stehpose von der Seite und im Dreiviertelprofil, je als freigestelltes PNG.
Dazu je Phase die Fußpunkte (tiefste Vertices der Knochengruppen foot.L/foot.R) in Pixeln.

  blender -b --factory-startup -P styles/painterly-digital/blender/poses.py -- --out styles/painterly-digital/assets/raw/poses

Die Bilder sind nur Layout- und Posenvorlage für das KI-Übermalen (agy), nicht das Endbild.
"""
import argparse, json, math, os, sys

import bpy
from mathutils import Vector as V

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--glb", default="shared/3d/badger.glb")
ap.add_argument("--out", required=True)
ap.add_argument("--w", type=int, default=306)
ap.add_argument("--h", type=int, default=512)
ap.add_argument("--ortho", type=float, default=1.36)   # Bildhöhe in Metern
ap.add_argument("--base", type=float, default=0.12)    # Abstand Boden -> unterer Bildrand in Metern
A = ap.parse_args(argv)
os.makedirs(A.out, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = 24          # vor dem Import: Walk (1,0 s) liegt dann auf Bild 0..24, 8 Phasen = alle 3 Bilder
bpy.ops.import_scene.gltf(filepath=os.path.abspath(A.glb))
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 32
sc.render.resolution_x, sc.render.resolution_y = A.w, A.h
sc.render.resolution_percentage = 100
sc.render.film_transparent = True
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGBA"
sc.view_settings.view_transform = "Standard"
world = bpy.data.worlds.new("W")
sc.world = world
world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs["Color"].default_value = (0.55, 0.6, 0.7, 1)
bg.inputs["Strength"].default_value = 0.9

def sun(name, energy, d, shadow=True):
    l = bpy.data.lights.new(name, "SUN"); l.energy = energy; l.use_shadow = shadow
    ob = bpy.data.objects.new(name, l); sc.collection.objects.link(ob)
    ob.rotation_euler = V(d).normalized().to_track_quat("-Z", "Y").to_euler()
    return ob

# Licht von vorn links oben (warm, wie die Laterne), schwaches Fülllicht
sun("Key", 3.2, (0.45, 1.0, -0.8))
sun("Fill", 0.8, (-0.6, 0.8, -0.3), shadow=False)

cam = bpy.data.cameras.new("Cam"); cam.type = "ORTHO"; cam.ortho_scale = A.ortho
cam_ob = bpy.data.objects.new("Cam", cam); sc.collection.objects.link(cam_ob); sc.camera = cam_ob
zc = A.ortho / 2 - A.base

def place(view):
    if view == "side":
        pos, tgt = V((0.0, -3.0, zc)), V((0.0, 0.0, zc))
    else:  # Dreiviertel: von vorn rechts, Figur schaut nach rechts vorn
        pos, tgt = V((2.1, -2.1, zc)), V((0.0, 0.0, zc))
    cam_ob.location = pos
    cam_ob.rotation_euler = (tgt - pos).normalized().to_track_quat("-Z", "Y").to_euler()

arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
meshes = [o for o in bpy.data.objects if o.type == "MESH" and any(m.type == "ARMATURE" for m in o.modifiers)]
for o in bpy.data.objects:   # Knochenform-Hilfsobjekte ausblenden
    if o.type == "MESH" and o not in meshes:
        o.hide_render = True

def set_action(name):
    ad = arm.animation_data or arm.animation_data_create()
    act = next(a for a in bpy.data.actions if a.name == name or a.name.startswith(name + "_") or a.name.startswith(name + "."))
    ad.action = act
    if getattr(ad, "action_slot", None) is None and len(act.slots):
        ad.action_slot = act.slots[0]
    return act

def foot_sets():
    s = {}
    for ob in meshes:
        for side in "LR":
            vg = ob.vertex_groups.get("foot." + side)
            if vg is None:
                continue
            s[(ob.name, side)] = [v.index for v in ob.data.vertices if any(g.group == vg.index and g.weight > 0.5 for g in v.groups)]
    return s

FS = foot_sets()
ppm = A.h / A.ortho

def feet_px():
    dg = bpy.context.evaluated_depsgraph_get()
    res = {}
    for side in "LR":
        pts = []
        for ob in meshes:
            idx = FS.get((ob.name, side), [])
            if not idx:
                continue
            ev = ob.evaluated_get(dg); me = ev.to_mesh(); mw = ob.matrix_world
            pts += [mw @ me.vertices[i].co for i in idx]
            ev.to_mesh_clear()
        zmin = min(p.z for p in pts)
        sole = [p for p in pts if p.z < zmin + 0.01]
        xs = [p.x for p in sole]
        # Pixel: x relativ zur Bildmitte, y von oben
        res[side] = {"x0": round(A.w / 2 + min(xs) * ppm, 1), "x1": round(A.w / 2 + max(xs) * ppm, 1),
                     "lift_m": round(zmin - 0.003, 4), "y": round(A.h / 2 - (zmin - zc) * ppm, 1)}
    return res

info = {"ppm": round(ppm, 2), "size": [A.w, A.h], "baseline_y": round(A.h / 2 + zc * ppm, 1), "frames": []}
act = set_action("Walk")
print("INFO Walk range", tuple(act.frame_range))
place("side")
for k in range(8):
    f = 3 * k
    sc.frame_set(f)
    p = os.path.join(A.out, f"walk_{k}.png")
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    info["frames"].append({"name": f"walk_{k}", "frame": f, "feet": feet_px()})
act = set_action("Idle")
sc.frame_set(0)
for view in ("side", "threequarter"):
    place(view)
    p = os.path.join(A.out, f"stand_{view}.png")
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    info["frames"].append({"name": f"stand_{view}", "frame": 0, "feet": feet_px() if view == "side" else None})
with open(os.path.join(A.out, "poses.json"), "w") as fh:
    json.dump(info, fh, indent=1)
print("DONE", A.out)
