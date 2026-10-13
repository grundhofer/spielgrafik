# -*- coding: utf-8 -*-
"""Isometrische Renderpässe (2:1) aus shared/3d für den Eintrag iso-pixel.

Kamera: orthografisch, 30° Neigung, 45° Drehung. Damit bildet eine Weltachse in der Bodenebene exakt auf
2 px waagrecht zu 1 px senkrecht ab (die Pixel-Iso-Linie). Je Bild entstehen zwei Pässe in k-facher
Überabtastung (Cycles, 1 Abtastung je Pixel in der Pixelmitte, kein Kantenglätten):
  <name>_id.png   Material-ID als Farbe (0/0,5/1 je Kanal, Raw), Alpha = Deckung
  <name>_nrm.png  Weltnormale als Farbe (N * 0,5 + 0,5)
scripts/pixelize3d.py macht daraus Pixel-Sprites (Mehrheit je Zielpixel, Stufenlicht, Kontur).

Aufruf (aus dem Projektordner):
  blender -b --factory-startup -P styles/iso-pixel/blender/iso_render.py -- --job badger --out <ordner>
  blender -b --factory-startup -P styles/iso-pixel/blender/iso_render.py -- --job props --out <ordner>
Schreibt zusätzlich <out>/<job>.json mit Maßstab, Ankerpunkt und Materialtabelle je Bild.
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Euler, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--job", choices=["badger", "props", "portrait"], required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--k", type=int, default=8, help="Überabtastung je Zielpixel")
ap.add_argument("--only", default="", help="nur diese Bildnamen (Komma)")
ap.add_argument("--head-tilt", type=float, default=-30.0, help="Kopf nach hinten kippen (Grad, Gesicht nach oben)")
ap.add_argument("--head-scale", type=float, default=1.4)
A = ap.parse_args(argv)
os.makedirs(A.out, exist_ok=True)

# Kamera-Achsen (Blender, Z oben): rechts R, oben U, Blickrichtung D
EUL = Euler((math.radians(60), 0.0, math.radians(45)), "XYZ")
R = EUL.to_matrix() @ Vector((1, 0, 0))
U = EUL.to_matrix() @ Vector((0, 1, 0))
D = EUL.to_matrix() @ Vector((0, 0, -1))

# Material-IDs: Farben aus {0, 0.5, 1}^3 ohne Schwarz
ID_LEVELS = [0.0, 0.5, 1.0]
ID_COLORS = [(r, g, b) for r in ID_LEVELS for g in ID_LEVELS for b in ID_LEVELS if (r, g, b) != (0, 0, 0)]

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = 1
sc.cycles.use_denoising = False
sc.cycles.seed = 0
sc.cycles.pixel_filter_type = "BOX"
sc.cycles.filter_width = 0.01
sc.cycles.max_bounces = 0
sc.render.film_transparent = True
sc.render.dither_intensity = 0.0
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGBA"
sc.render.image_settings.color_depth = "8"
sc.view_settings.view_transform = "Raw"
sc.view_settings.look = "None"
sc.view_settings.exposure = 0
sc.view_settings.gamma = 1
sc.render.fps = 30
world = bpy.data.worlds.new("W")
sc.world = world
world.use_nodes = True
for n in world.node_tree.nodes:
    if n.type == "BACKGROUND":
        n.inputs["Strength"].default_value = 0.0

cam = bpy.data.cameras.new("Cam")
cam.type = "ORTHO"
cam_ob = bpy.data.objects.new("Cam", cam)
sc.collection.objects.link(cam_ob)
sc.camera = cam_ob
cam_ob.rotation_euler = EUL


def emission_mat(name, color=None, normal=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.0
    if normal:
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        mul = nt.nodes.new("ShaderNodeVectorMath")
        mul.operation = "MULTIPLY_ADD"
        mul.inputs[1].default_value = (0.5, 0.5, 0.5)
        mul.inputs[2].default_value = (0.5, 0.5, 0.5)
        nt.links.new(geo.outputs["Normal"], mul.inputs[0])
        nt.links.new(mul.outputs["Vector"], em.inputs["Color"])
    else:
        em.inputs["Color"].default_value = (*color, 1.0)
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return m


NRM_MAT = emission_mat("__normal", normal=True)
ID_MATS = {}


def id_mat(orig_name, table):
    if orig_name not in table:
        table[orig_name] = len(table)
    i = table[orig_name]
    key = (orig_name, i)
    if key not in ID_MATS:
        ID_MATS[key] = emission_mat("__id_%s" % orig_name, ID_COLORS[i])
    return ID_MATS[key], ID_COLORS[i]


def render_passes(name, objs, scale_px, k, size, anchor_world, anchor_px, table, extra_meta=None):
    """objs: Mesh-Objekte, die sichtbar sein sollen; scale_px: Zielpixel je Meter; size: Zielgröße (w, h);
    anchor_world (Blender-Weltpunkt) landet auf dem Zielpixel-Eckpunkt anchor_px."""
    if A.only and name not in A.only.split(","):
        return None
    w, h = size
    sc.render.resolution_x = w * k
    sc.render.resolution_y = h * k
    sc.render.resolution_percentage = 100
    cam.ortho_scale = max(w, h) / scale_px
    cam.sensor_fit = "AUTO"
    # Kamerazentrum C so, dass anchor_world auf anchor_px abbildet (Bildmitte = (w/2, h/2))
    ax = (anchor_px[0] - w / 2.0) / scale_px
    ay = (anchor_px[1] - h / 2.0) / scale_px
    C = Vector(anchor_world) - ax * R + ay * U - 40.0 * D
    cam_ob.location = C
    cam.clip_start = 0.1
    cam.clip_end = 200.0
    vis = set(o.name for o in objs)
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = o.name not in vis
    # Materialtabelle je Objekt sichern und Pässe rendern
    saved = {o.name: [s.material for s in o.material_slots] for o in objs}
    mats = {}
    for o in objs:
        for s in o.material_slots:
            if s.material and not s.material.name.startswith("__"):
                _, col = id_mat(s.material.name, table)
                mats[s.material.name] = [round(c * 255) for c in col]
    for pas in ("id", "nrm"):
        for o in objs:
            for i, s in enumerate(o.material_slots):
                orig = saved[o.name][i]
                if orig is None:
                    continue
                s.link = "OBJECT"
                s.material = NRM_MAT if pas == "nrm" else id_mat(orig.name, table)[0]
        sc.render.filepath = os.path.join(A.out, "%s_%s.png" % (name, pas))
        bpy.ops.render.render(write_still=True)
    for o in objs:
        for i, s in enumerate(o.material_slots):
            s.material = saved[o.name][i]
            s.link = "DATA"
    meta = {"name": name, "scale_px": scale_px, "k": k, "size": [w, h], "anchor_px": list(anchor_px),
            "anchor_world": list(anchor_world), "materials": mats}
    if extra_meta:
        meta.update(extra_meta)
    return meta


def foot_info(arm_meshes):
    dg = bpy.context.evaluated_depsgraph_get()
    res = {}
    for ob in arm_meshes:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ob.matrix_world
        for side in "LR":
            vg = ob.vertex_groups.get("foot." + side)
            if vg is None:
                continue
            pts = [mw @ v.co for v in me.vertices if any(g.group == vg.index and g.weight > 0.5 for g in v.groups)]
            if pts:
                zmin = min(p.z for p in pts)
                sole = [p for p in pts if p.z < zmin + 0.01]
                res[side] = {"zmin": zmin, "x": sum(p.x for p in sole) / len(sole), "y": sum(p.y for p in sole) / len(sole)}
        ev.to_mesh_clear()
    return res


def job_badger():
    bpy.ops.import_scene.gltf(filepath=os.path.abspath("shared/3d/badger.glb"))
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    meshes = [o for o in bpy.data.objects if o.type == "MESH" and any(m.type == "ARMATURE" for m in o.modifiers)]
    for o in bpy.data.objects:
        if o.type == "MESH" and o not in meshes:
            o.hide_render = True

    # Kopf für die hohe Sicht anpassen: größer und nach hinten gekippt, sonst verdeckt die Mütze das Gesicht.
    # Constraints wirken nach der Animation, die Bewegung des Kopfes bleibt erhalten.
    ctl = bpy.data.objects.new("HeadCtl", None)
    sc.collection.objects.link(ctl)
    ctl.location = (1, 0, 0)
    pb = arm.pose.bones["head"]
    c = pb.constraints.new("TRANSFORM")
    c.target = ctl
    c.target_space = "WORLD"
    c.owner_space = "LOCAL"
    c.map_from = "LOCATION"
    c.from_min_x, c.from_max_x = 0.0, 1.0
    c.map_to = "ROTATION"
    c.map_to_x_from = "X"
    c.to_min_x_rot, c.to_max_x_rot = 0.0, math.radians(A.head_tilt)
    c.mix_mode_rot = "AFTER"
    c2 = pb.constraints.new("TRANSFORM")
    c2.target = ctl
    c2.target_space = "WORLD"
    c2.owner_space = "LOCAL"
    c2.map_from = "LOCATION"
    c2.from_min_x, c2.from_max_x = 0.0, 1.0
    c2.map_to = "SCALE"
    c2.map_to_x_from = c2.map_to_y_from = c2.map_to_z_from = "X"
    c2.to_min_x_scale = c2.to_min_y_scale = c2.to_min_z_scale = 1.0
    c2.to_max_x_scale = c2.to_max_y_scale = c2.to_max_z_scale = A.head_scale
    c2.mix_mode_scale = "MULTIPLY"

    def set_action(nm):
        ad = arm.animation_data or arm.animation_data_create()
        act = next(a for a in bpy.data.actions if a.name == nm or a.name.startswith(nm + "_") or a.name.startswith(nm + "."))
        ad.action = act
        if getattr(ad, "action_slot", None) is None and len(act.slots):
            ad.action_slot = act.slots[0]

    # Schrittweite messen: Standfuß wandert in der Walk-Schleife mit konstanter Geschwindigkeit zurück
    set_action("Walk")
    feet = []
    for f in range(31):
        sc.frame_set(f)
        feet.append(foot_info(meshes))
    # Geschwindigkeit des Standfußes: Steigung von x über die Bilder, in denen der Fuß am Boden ist
    speeds = []
    for side in "LR":
        seq = [(f, feet[f][side]["x"]) for f in range(31) if feet[f][side]["zmin"] < 0.006]
        for (f0, x0), (f1, x1) in zip(seq, seq[1:]):
            if f1 == f0 + 1:
                speeds.append((x0 - x1) * 30.0)
    speeds.sort()
    v = speeds[len(speeds) // 2]
    stride = v * 1.0
    print("STRIDE m/cycle %.4f (median foot speed %.4f m/s, n=%d)" % (stride, v, len(speeds)))

    k = A.k
    cyc_px = 10                      # Vorschub je Laufzyklus: (10, 5) Zielpixel
    s = cyc_px / (stride * math.cos(math.radians(45)))
    size = (64, 64)
    anchor = (26, 52)                # Ursprung (Bodenpunkt) in Bild 0
    table = {}
    metas = []
    n_walk = 10
    arm.rotation_mode = "XYZ"          # glTF-Import setzt Quaternionen; rotation_euler wirkt sonst nicht
    arm.rotation_euler = (0, 0, 0)
    for i in range(n_walk):
        set_action("Walk")
        f = 30.0 * i / n_walk
        sc.frame_set(int(f), subframe=f - int(f))
        arm.location = (stride * i / n_walk, 0, 0)
        fi = foot_info(meshes)
        m = render_passes("walk_se_%02d" % i, meshes, s, k, size, (0, 0, 0), anchor, table,
                          {"feet": fi, "anim": "Walk", "frame": f, "root": list(arm.location), "facing": "se"})
        if m:
            metas.append(m)
    arm.location = (0, 0, 0)
    # Stehen nach SO und nach S (zur Kamera): Idle 2,0 s in 12 Bildern (6 Bilder/s)
    for facing, rz in (("se", 0.0), ("s", -45.0)):
        arm.rotation_euler = (0, 0, math.radians(rz))
        for i in range(12):
            set_action("Idle")
            f = 60.0 * i / 12
            sc.frame_set(int(f))
            m = render_passes("idle_%s_%02d" % (facing, i), meshes, s, k, size, (0, 0, 0), anchor, table,
                              {"feet": foot_info(meshes), "anim": "Idle", "frame": f, "facing": facing})
            if m:
                metas.append(m)
    # Winken nach S: Wave 1,5 s in 15 Bildern (10 Bilder/s)
    arm.rotation_euler = (0, 0, math.radians(-45.0))
    for i in range(16):
        set_action("Wave")
        f = min(45.0, 3.0 * i)
        sc.frame_set(int(f))
        m = render_passes("wave_s_%02d" % i, meshes, s, k, size, (0, 0, 0), anchor, table,
                          {"feet": foot_info(meshes), "anim": "Wave", "frame": f, "facing": "s"})
        if m:
            metas.append(m)
    json.dump({"job": "badger", "stride_m": stride, "scale_px": s, "cycle_px": [cyc_px, cyc_px // 2],
               "ids": {n: [round(c * 255) for c in ID_COLORS[i]] for n, i in table.items()}, "frames": metas},
              open(os.path.join(A.out, "badger.json"), "w"), indent=1)


def job_props():
    bpy.ops.import_scene.gltf(filepath=os.path.abspath("shared/3d/harbor.glb"))
    k = A.k
    table = {}
    metas = []
    # name, Objekte, px/m, Zielgröße, Drehung um Z (Grad), Ankerpunkt (Ursprung) in Zielpixeln
    jobs = [
        ("cottage", ["Cottage", "CottageWindow"], 14.0, (80, 96), 0.0, (40, 78)),
        ("lighthouse", ["Lighthouse", "LighthouseLamp"], 8.5, (48, 112), 0.0, (24, 100)),
        ("boat_a", ["BoatA"], 12.0, (64, 56), 90.0, (32, 36)),
        ("boat_b", ["BoatB"], 12.0, (64, 64), 90.0, (32, 44)),
        ("barrel", ["Barrel1"], 22.0, (24, 32), 0.0, (12, 26)),
        ("crates", ["CrateStack"], 18.0, (48, 40), 0.0, (24, 30)),
        ("rope", ["RopeCoil"], 20.0, (24, 16), 0.0, (12, 10)),
        ("lantern", ["LanternPost", "LanternGlass"], 18.0, (32, 56), 0.0, (18, 50)),
    ]
    for name, obnames, s, size, rz, anchor in jobs:
        objs = [bpy.data.objects[n] for n in obnames]
        root = objs[0]
        # Objekt in den Ursprung holen (Kinder folgen), drehen
        root.rotation_mode = "XYZ"
        saved = (root.location.copy(), root.rotation_euler.copy())
        root.location = (0, 0, 0)
        root.rotation_euler = (0, 0, math.radians(rz))
        bpy.context.view_layer.update()
        m = render_passes(name, objs, s, k, size, (0, 0, 0), anchor, table, {"objects": obnames, "rot_z": rz})
        if m:
            metas.append(m)
        root.location, root.rotation_euler = saved
        bpy.context.view_layer.update()
    json.dump({"job": "props", "ids": {n: [round(c * 255) for c in ID_COLORS[i]] for n, i in table.items()},
               "frames": metas}, open(os.path.join(A.out, "props.json"), "w"), indent=1)


def job_portrait():
    """Brustbild als Vorlage für das KI-Porträt: Blick schräg nach links vorn, Kamera fast auf Augenhöhe."""
    bpy.ops.import_scene.gltf(filepath=os.path.abspath("shared/3d/badger.glb"))
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    meshes = [o for o in bpy.data.objects if o.type == "MESH" and any(m.type == "ARMATURE" for m in o.modifiers)]
    for o in bpy.data.objects:
        if o.type == "MESH" and o not in meshes:
            o.hide_render = True
    ad = arm.animation_data or arm.animation_data_create()
    act = next(a for a in bpy.data.actions if a.name.startswith("Idle"))
    ad.action = act
    if getattr(ad, "action_slot", None) is None and len(act.slots):
        ad.action_slot = act.slots[0]
    sc.frame_set(0)
    arm.rotation_mode = "XYZ"
    arm.rotation_euler = (0, 0, math.radians(-125.0))
    global R, U, D
    eul = Euler((math.radians(88), 0.0, 0.0), "XYZ")
    cam_ob.rotation_euler = eul
    R = eul.to_matrix() @ Vector((1, 0, 0))
    U = eul.to_matrix() @ Vector((0, 1, 0))
    D = eul.to_matrix() @ Vector((0, 0, -1))
    k = A.k
    size = (64, 64)
    s = 64 / 0.62
    m = render_passes("portrait", meshes, s, k, size, (0.0, 0.0, 0.70), (32, 40), {}, {"facing": "left-front"})
    json.dump({"job": "portrait", "ids": {n: v for n, v in m["materials"].items()}, "frames": [m]},
              open(os.path.join(A.out, "portrait.json"), "w"), indent=1)


if A.job == "badger":
    job_badger()
elif A.job == "portrait":
    job_portrait()
else:
    job_props()
print("DONE", A.job)
