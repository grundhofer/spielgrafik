# -*- coding: utf-8 -*-
"""Rendert den Laufzyklus des gemeinsamen 3D-Dachses (shared/3d/badger.glb, Animation Walk) als Lagevorlage
für ein gemaltes Laufblatt: 8 gleichmäßig verteilte Phasen, Seitenansicht (rechte Körperseite zur Kamera),
orthografisch, transparenter Hintergrund. Zusätzlich die Fußpunkte je Phase (Meter), damit der Vorschub je Bild
aus dem echten Standfuß kommt.

  blender -b --factory-startup -P styles/textoberflaeche/blender/walk_layout.py -- \
      --glb shared/3d/badger.glb --out styles/textoberflaeche/assets/raw/walk3d
"""
import argparse, json, math, os, sys
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--glb", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--phases", type=int, default=8)
ap.add_argument("--size", default="480x560")
ap.add_argument("--ortho", type=float, default=1.30)
A = ap.parse_args(argv)
os.makedirs(A.out, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = 30
bpy.ops.import_scene.gltf(filepath=os.path.abspath(A.glb))
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 16
w, h = [int(v) for v in A.size.split("x")]
sc.render.resolution_x, sc.render.resolution_y = w, h
sc.render.film_transparent = True
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGBA"
sc.view_settings.view_transform = "Standard"
world = bpy.data.worlds.new("W"); sc.world = world
world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs["Color"].default_value = (0.6, 0.62, 0.66, 1); bg.inputs["Strength"].default_value = 1.0

def aim(ob, d):
    ob.rotation_euler = d.normalized().to_track_quat("-Z", "Y").to_euler()

key = bpy.data.lights.new("Key", "SUN"); key.energy = 2.6
kob = bpy.data.objects.new("Key", key); sc.collection.objects.link(kob)
aim(kob, Vector((0.5, 1.0, -0.8)))
cam = bpy.data.cameras.new("Cam"); cam.type = "ORTHO"; cam.ortho_scale = A.ortho
cob = bpy.data.objects.new("Cam", cam); sc.collection.objects.link(cob); sc.camera = cob
# Kamera auf -Y, Blick nach +Y: die Figur blickt nach +X (rechts im Bild), ihre rechte Seite (Paket) zur Kamera.
# Bildmitte: x = 0, z = 0.50; Boden (z = 0) liegt damit bei 0.5 - 0.5/ortho*... (unten rechnet das Skript nach)
cob.location = Vector((0.0, -4.0, 0.50))
aim(cob, Vector((0, 1, 0)))

arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
act = next(a for a in bpy.data.actions if a.name == "Walk" or a.name.startswith("Walk"))
ad = arm.animation_data or arm.animation_data_create()
ad.action = act
if getattr(ad, "action_slot", None) is None and len(act.slots):
    ad.action_slot = act.slots[0]
f0, f1 = act.frame_range
meshes = [o for o in bpy.data.objects if o.type == "MESH" and any(m.type == "ARMATURE" for m in o.modifiers)]

def foot_sets():
    out = {}
    for ob in meshes:
        for side in "LR":
            vg = ob.vertex_groups.get("foot." + side)
            if vg is None:
                continue
            out[(ob.name, side)] = [v.index for v in ob.data.vertices
                                     if any(g.group == vg.index and g.weight > 0.5 for g in v.groups)]
    return out

FS = foot_sets()
px_per_m = h / A.ortho if h >= w else w / A.ortho   # ortho_scale gilt für die längere Bildseite
info = {"phases": A.phases, "cycle_s": (f1 - f0) / 30.0, "speed_m_s": 0.367, "px_per_m": px_per_m,
        "size": [w, h], "cam_center_m": [0.0, 0.50], "frames": []}
dg = bpy.context.evaluated_depsgraph_get()
for k in range(A.phases):
    t = f0 + (f1 - f0) * k / A.phases
    fi = int(math.floor(t)); sub = t - fi
    sc.frame_set(fi, subframe=sub)
    dg.update()
    feet = {}
    for side in "LR":
        pts = []
        for ob in meshes:
            ev = ob.evaluated_get(dg); me = ev.to_mesh(); mw = ob.matrix_world
            for i in FS.get((ob.name, side), []):
                pts.append(mw @ me.vertices[i].co)
            ev.to_mesh_clear()
        zmin = min(p.z for p in pts)
        low = [p for p in pts if p.z < zmin + 0.01]
        feet[side] = {"zmin": round(zmin, 4), "xmin": round(min(p.x for p in pts), 4),
                      "xmax": round(max(p.x for p in pts), 4),
                      "x_contact": round(sum(p.x for p in low) / len(low), 4)}
    sc.render.filepath = os.path.join(A.out, f"walk_{k}.png")
    bpy.ops.render.render(write_still=True)
    info["frames"].append({"k": k, "frame": round(t, 3), "feet": feet})
with open(os.path.join(A.out, "walk3d.json"), "w") as f:
    json.dump(info, f, indent=1)
print("DONE", A.out)
