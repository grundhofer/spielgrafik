# -*- coding: utf-8 -*-
"""Posen-Vorlage für das KI-Figurenblatt (HD-2D): der geriggte Dachs aus shared/3d.

Nach dem Muster von styles/hibit-pixel/blender/walk_layout.py, aber mit leichter Aufsicht (wie die
HD-2D-Kamera) und mit Vorderansichten:
  walk_00..07  Seitenansicht nach rechts, 8 Phasen des Laufzyklus (Walk, je 1/8 s)
  front_*      Vorderansicht: Idle (zwei Atemphasen) und Wave (Arm oben, zwei Winkstellungen)
Jedes Bild einzeln mit transparentem Hintergrund, orthografisch, Ursprung der Figur in der Bildmitte.
compose_layout.py setzt daraus das 1536×1024-Blatt für genimg.py.

Aufruf (aus dem Projektordner):
  blender -b --factory-startup -P styles/hd-2d/blender/pose_layout.py -- --out <ordner> [--elev 15]
Gibt je Bild die Lage beider Füße (tiefster Punkt, x-Bereich) in Metern aus.
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
ap.add_argument("--elev", type=float, default=15.0, help="Aufsicht in Grad")
ap.add_argument("--wave", default="12,22", help="Bilder (30 fps) der Wave-Animation")
ap.add_argument("--id", action="store_true",
                help="Kennungsbild statt Schattierung: nahes Bein grün, fernes Bein blau, Rest schwarz (nur Laufbilder)")
A = ap.parse_args(argv)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = 30
bpy.ops.import_scene.gltf(filepath=os.path.abspath(A.glb))
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 16
sc.render.resolution_x = sc.render.resolution_y = A.px
sc.render.film_transparent = True
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGBA"
sc.view_settings.view_transform = "Standard"
world = bpy.data.worlds.new("W")
sc.world = world
world.use_nodes = True
bgn = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
bgn.inputs["Color"].default_value = (0.8, 0.82, 0.86, 1)
bgn.inputs["Strength"].default_value = 0.9

cam = bpy.data.cameras.new("Cam")
cam.type = "ORTHO"
cam.ortho_scale = 1.30
cam_ob = bpy.data.objects.new("Cam", cam)
sc.collection.objects.link(cam_ob)
sc.camera = cam_ob
CENTER_Z = 0.55      # Bildmitte auf dieser Höhe über dem Ursprung
DIST = 4.0
e = math.radians(A.elev)


def view(kind):
    """Kamera so setzen, dass die Bildmitte auf (0, 0, CENTER_Z) zeigt."""
    if kind == "side":    # sieht die rechte Seite (Paket), Figur blickt nach rechts
        cam_ob.location = (0.0, -DIST * math.cos(e), CENTER_Z + DIST * math.sin(e))
        cam_ob.rotation_euler = (math.pi / 2 - e, 0.0, 0.0)
    else:                 # von vorn (+X)
        cam_ob.location = (DIST * math.cos(e), 0.0, CENTER_Z + DIST * math.sin(e))
        cam_ob.rotation_euler = (math.pi / 2 - e, 0.0, math.pi / 2)


key = bpy.data.lights.new("Key", "SUN")
key.energy = 3.0
key_ob = bpy.data.objects.new("Key", key)
sc.collection.objects.link(key_ob)
key_ob.rotation_euler = (math.radians(55), 0, math.radians(-30))

arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
meshes = [o for o in bpy.data.objects if o.type == "MESH" and any(m.type == "ARMATURE" for m in o.modifiers)]
for o in bpy.data.objects:   # Knochenform-Hilfsobjekte nicht rendern
    if o.type == "MESH" and o not in meshes:
        o.hide_render = True


def set_action(name):
    ad = arm.animation_data or arm.animation_data_create()
    act = next(a for a in bpy.data.actions
               if a.name == name or a.name.startswith(name + "_") or a.name.startswith(name + "."))
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
            pts = [mw @ v.co for v in me.vertices
                   if any(g.group == vg.index and g.weight > 0.5 for g in v.groups)]
            if pts:
                res[side] = (min(p.z for p in pts), min(p.x for p in pts), max(p.x for p in pts))
        ev.to_mesh_clear()
    return res


def id_materials():
    """Flächen nach Beinknochen einfärben (Emission, ohne Licht): nahes Bein (R, zur Kamera) grün,
    fernes Bein (L) blau, alles andere schwarz (verdeckt die Beine, wo der Körper davor liegt)."""
    sc.view_settings.view_transform = "Standard"
    sc.eevee.taa_render_samples = 1
    sc.render.filter_size = 0.0
    mats = {}
    for name, col in (("IdNear", (0, 1, 0, 1)), ("IdFar", (0, 0, 1, 1)), ("IdOther", (0, 0, 0, 1))):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = col
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(em.outputs[0], out.inputs[0])
        mats[name] = m
    for ob in meshes:
        me = ob.data
        me.materials.clear()
        for n in ("IdOther", "IdNear", "IdFar"):
            me.materials.append(mats[n])
        groups = {g.index: g.name for g in ob.vertex_groups}
        for poly in me.polygons:
            w = {"L": 0.0, "R": 0.0}
            for vi in poly.vertices:
                for g in me.vertices[vi].groups:
                    gn = groups.get(g.group, "")
                    if gn.split(".")[0] in ("thigh", "shin", "foot") and gn[-1] in "LR":
                        w[gn[-1]] += g.weight
            k = len(poly.vertices)
            side = max(w, key=w.get)
            poly.material_index = (1 if side == "R" else 2) if w[side] / k > 0.5 else 0


os.makedirs(A.out, exist_ok=True)
if A.id:
    id_materials()
jobs = [("walk_%02d" % k, "side", "Walk", 30.0 * k / 8.0) for k in range(8)]
jobs += [("front_idle_a", "front", "Idle", 0.0), ("front_idle_b", "front", "Idle", 30.0)]
for i, f in enumerate(int(x) for x in A.wave.split(",")):
    jobs.append(("front_wave_%d" % i, "front", "Wave", float(f)))
if A.id:
    jobs = [j for j in jobs if j[0].startswith("walk")]
    jobs = [("id_" + t, k, a, f) for t, k, a, f in jobs]
for tag, kind, action, f in jobs:
    view(kind)
    set_action(action)
    sc.frame_set(int(f), subframe=f - int(f))
    fi = foot_info()
    print("FOOT %-14s f=%5.2f " % (tag, f) + " ".join(
        "%s: z %.3f x %.3f..%.3f" % (s, *fi[s]) for s in sorted(fi)))
    sc.render.filepath = os.path.join(A.out, tag + ".png")
    bpy.ops.render.render(write_still=True)
print("ortho_scale", cam.ortho_scale, "px", A.px, "center_z", CENTER_Z, "elev", A.elev)
