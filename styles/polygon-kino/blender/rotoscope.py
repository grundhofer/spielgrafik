# -*- coding: utf-8 -*-
"""Rotoskopie-Vorlagen für polygon-kino: rendert Hafen und Dachs aus shared/3d als Kennbilder.

Aufruf (aus dem Projektordner):
  blender -b --factory-startup -P styles/polygon-kino/blender/rotoscope.py -- --mode layout --out <tmp>
  blender -b --factory-startup -P styles/polygon-kino/blender/rotoscope.py -- --mode passes --out <tmp>

layout: EEVEE-Probebilder je Einstellung (Kamera aus shots.json, Dachs an den Probepositionen).
passes: je Ebene und je Dachs-Phase zwei Bilder in ss-facher Auflösung des Szenenbands (320x148):
  <name>_id.png     Workbench, flache Kennfarbe je (Objekt, Material), ohne Kantenglättung.
                    R = Kennnummer, G = 255 - Kennnummer, A = 0 für leer. Kennnummern in ids.json.
  <name>_lit.png    EEVEE, nur Emission: R = max(N·L_key, 0), G = max(N·L_rim, 0), B = N·oben (0..1 auf 0..255),
                    Lichtrichtungen je Einstellung (shots.json -> lights).
Das Meer (Sea) wird in jeder Ebene mitgerendert und bekommt die Kennnummer 1 (= Maske, verdeckt Rümpfe, Mauern und
Felsen unter der Wasserlinie). Leere Pixel haben Alpha 0.
frames.json: je Einstellung Bildpunkte des Laufwegs (Projektion), Phasen des Dachses mit Animationszeit.
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["layout", "passes"], required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--shots", default=os.path.join(HERE, "shots.json"))
    ap.add_argument("--ss", type=int, default=6, help="Überabtastung je Zielpixel (passes)")
    ap.add_argument("--scale", type=int, default=3, help="Vergrößerung der Probebilder (layout)")
    ap.add_argument("--only", default="", help="nur diese Einträge (Kommaliste), z. B. A_far,B_walk")
    return ap.parse_args(argv)


A = parse_args()
SHOTS = json.load(open(A.shots))
SW, SH = SHOTS["scene_px"]


def g2b(v):
    """Godot (x, y, z) -> Blender (x, -z, y)."""
    return Vector((v[0], -v[2], v[1]))


def hex_lin(h):
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return out


def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def setup():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = 30          # vor dem Import, sonst rechnet der Importer mit 24 fps
    bpy.ops.import_scene.gltf(filepath=os.path.join(ROOT, "shared/3d/harbor.glb"))
    harbor = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(ROOT, "shared/3d/badger.glb"))
    sc = bpy.context.scene
    badger = [o for o in bpy.data.objects if o not in harbor]
    for o in badger:
        if o.type == "MESH" and not any(m.type == "ARMATURE" for m in o.modifiers) and o.parent is None:
            o.hide_render = True                       # Knochenform des Importers
    arm = next(o for o in badger if o.type == "ARMATURE")
    root = arm
    while root.parent is not None:
        root = root.parent
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.resolution_percentage = 100
    return sc, harbor, badger, arm, root


def add_camera(sc, shot):
    cd = bpy.data.cameras.new("Cam")
    cd.sensor_fit = "HORIZONTAL"
    cd.sensor_width = 36.0
    cd.lens = 18.0 / math.tan(math.radians(shot["hfov"]) / 2)
    cd.clip_start = 0.1
    cd.clip_end = 3000.0
    cd.shift_x, cd.shift_y = shot.get("shift", (0.0, 0.0))
    co = link(bpy.data.objects.new("Cam", cd))
    co.location = g2b(shot["cam"])
    co.rotation_mode = "XYZ"
    co.rotation_euler = (math.radians(90.0), 0.0, math.radians(-shot.get("yaw", 0.0)))
    sc.camera = co
    return co


def project(sc, cam, p, w, h):
    from bpy_extras.object_utils import world_to_camera_view
    v = world_to_camera_view(sc, cam, p)
    return [v.x * w, (1.0 - v.y) * h, v.z]


def set_action(arm, name):
    ad = arm.animation_data or arm.animation_data_create()
    for tr in list(ad.nla_tracks):
        ad.nla_tracks.remove(tr)
    if name is None:
        ad.action = None
        for pb in arm.pose.bones:
            pb.location = (0, 0, 0)
            pb.rotation_quaternion = (1, 0, 0, 0)
            pb.rotation_euler = (0, 0, 0)
            pb.scale = (1, 1, 1)
        return None
    act = next(a for a in bpy.data.actions if a.name == name or a.name.startswith(name + "_")
               or a.name.startswith(name + "."))
    ad.action = act
    if getattr(ad, "action_slot", None) is None and len(act.slots):
        ad.action_slot = act.slots[0]
    return act


def place_badger(root, x, y, z, rot_deg):
    root.location = g2b((x, y, z))
    root.rotation_mode = "XYZ"
    root.rotation_euler = (0, 0, math.radians(rot_deg))


# ---------------------------------------------------------------------------------------------
def layout(sc, harbor, badger, arm, root):
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = 8
    sc.view_settings.view_transform = "Standard"
    world = bpy.data.worlds.new("W")
    sc.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (*hex_lin("#7F86B8"), 1)
    bg.inputs["Strength"].default_value = 0.8
    sun = link(bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN")))
    sun.data.energy = 3.0
    sun.rotation_euler = Vector((0.4, 0.8, -0.45)).to_track_quat("-Z", "Y").to_euler()
    sc.render.resolution_x, sc.render.resolution_y = SW * A.scale, SH * A.scale
    set_action(arm, "Walk")
    sc.frame_set(5)
    os.makedirs(A.out, exist_ok=True)
    for key, shot in SHOTS["shots"].items():
        cam = add_camera(sc, shot)
        for i, b in enumerate(shot.get("badger", [])):
            place_badger(root, *b[:4])
            if len(b) > 4:                     # [x, y, z, rot, Aktion, Zeit in s]
                act = set_action(arm, b[4])
                sc.frame_set(int(act.frame_range[0] + b[5] * 30))
            bpy.context.view_layer.update()
            sc.render.filepath = os.path.join(A.out, f"layout_{key}_{i}.png")
            bpy.ops.render.render(write_still=True)
            foot = project(sc, cam, g2b(b[:3]), SW, SH)
            set_action(arm, "Walk")
            sc.frame_set(5)
            head = project(sc, cam, g2b((b[0], 1.01, b[2])), SW, SH)
            print(f"LAYOUT {key}{i}: Fuß {foot[0]:.1f},{foot[1]:.1f}  Kopf {head[1]:.1f}  Höhe {foot[1]-head[1]:.1f} px")
        bpy.data.objects.remove(cam)


# ---------------------------------------------------------------------------------------------
def make_pass_materials(objs):
    """Je (Objekt, Materialplatz) ein eigenes Material: diffuse_color = Kennfarbe (Workbench),
    Knoten = Emission aus N·L (EEVEE). Gibt Kennliste und die Licht-Knoten zum Umstellen zurück."""
    ids = {1: {"object": "Sea", "material": "Water"}}
    light_nodes = []
    nxt = 2
    for ob in objs:
        if ob.type != "MESH":
            continue
        for slot in ob.material_slots:
            src = slot.material
            mname = src.name.split(".")[0] if src else "None"
            if ob.name == "Sea":
                i = 1
            else:
                i = nxt
                nxt += 1
                ids[i] = {"object": ob.name, "material": mname}
            m = bpy.data.materials.new(f"ID_{i:03d}")
            m.diffuse_color = (i / 255.0, (255 - i) / 255.0, 0.0, 1.0)
            m.use_nodes = True
            nt = m.node_tree
            for n in list(nt.nodes):
                nt.nodes.remove(n)
            out = nt.nodes.new("ShaderNodeOutputMaterial")
            em = nt.nodes.new("ShaderNodeEmission")
            em.inputs["Strength"].default_value = 1.0
            geo = nt.nodes.new("ShaderNodeNewGeometry")
            comb = nt.nodes.new("ShaderNodeCombineColor")
            chans = []
            for k in range(3):
                dot = nt.nodes.new("ShaderNodeVectorMath")
                dot.operation = "DOT_PRODUCT"
                nt.links.new(geo.outputs["Normal"], dot.inputs[0])
                mx = nt.nodes.new("ShaderNodeMath")
                if k < 2:
                    mx.operation = "MAXIMUM"
                    mx.inputs[1].default_value = 0.0
                else:                                   # N·oben auf 0..1
                    mx.operation = "MULTIPLY_ADD"
                    mx.inputs[1].default_value = 0.5
                    mx.inputs[2].default_value = 0.5
                nt.links.new(dot.outputs["Value"], mx.inputs[0])
                nt.links.new(mx.outputs["Value"], comb.inputs[k])
                chans.append(dot)
            chans[2].inputs[1].default_value = (0.0, 0.0, 1.0)
            nt.links.new(comb.outputs["Color"], em.inputs["Color"])
            nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
            light_nodes.append(chans)
            slot.link = "OBJECT"
            slot.material = m
    return ids, light_nodes


def set_lights(light_nodes, shot):
    key = g2b(shot["lights"]["key"]).normalized()
    rim = g2b(shot["lights"]["rim"]).normalized()
    for chans in light_nodes:
        chans[0].inputs[1].default_value = key
        chans[1].inputs[1].default_value = rim


def render_pair(sc, base):
    """Kennbild (Workbench, ohne Glättung) und Lichtbild (EEVEE, 1 Abtastung)."""
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "FLAT"
    sh.color_type = "MATERIAL"
    sh.show_object_outline = False
    sh.show_cavity = False
    sh.show_specular_highlight = False
    sh.show_shadows = False
    sc.display.render_aa = "OFF"
    sc.render.filepath = base + "_id.png"
    bpy.ops.render.render(write_still=True)
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = 1
    sc.render.filepath = base + "_lit.png"
    bpy.ops.render.render(write_still=True)


LIMBS = ("thigh", "shin", "foot", "upper_arm", "forearm", "hand")


def setup_feet(badger_meshes):
    """Farbattribute "feet" (linker Fuß rot, rechter Fuß grün; für die Fußmessung) und "side" (Gliedmaßen der
    linken Körperseite rot, der rechten grün; für ferne/nahe Gliedmaßen in der Seitenansicht)."""
    for ob in badger_meshes:
        me = ob.data
        side = me.color_attributes.new("side", "BYTE_COLOR", "POINT")
        gidx = {g.index: g.name for g in ob.vertex_groups}
        for v in me.vertices:
            c = [0.0, 0.0, 0.0, 1.0]
            for g in v.groups:
                name = gidx.get(g.group, "")
                if g.weight > 0.5 and name.split(".")[0] in LIMBS:
                    if name.endswith(".L"):
                        c[0] = 1.0
                    elif name.endswith(".R"):
                        c[1] = 1.0
            side.data[v.index].color = c
        attr = me.color_attributes.new("feet", "BYTE_COLOR", "POINT")
        gl, gr = ob.vertex_groups.get("foot.L"), ob.vertex_groups.get("foot.R")
        for v in me.vertices:
            c = (0.0, 0.0, 0.0, 1.0)
            for g in v.groups:
                if gl is not None and g.group == gl.index and g.weight > 0.5:
                    c = (1.0, 0.0, 0.0, 1.0)
                if gr is not None and g.group == gr.index and g.weight > 0.5:
                    c = (0.0, 1.0, 0.0, 1.0)
            attr.data[v.index].color = c
        me.color_attributes.active_color = attr


def foot_contact(badger_meshes):
    """Je Fuß: tiefster Punkt (m über Boden) und mittleres x (Godot) der Ecken bis 5 mm darüber."""
    dg = bpy.context.evaluated_depsgraph_get()
    out = {}
    for side in "LR":
        pts = []
        for ob in badger_meshes:
            vg = ob.vertex_groups.get("foot." + side)
            if vg is None:
                continue
            idx = {v.index for v in ob.data.vertices for g in v.groups if g.group == vg.index and g.weight > 0.5}
            ev = ob.evaluated_get(dg)
            me = ev.to_mesh()
            mw = ob.matrix_world
            pts += [mw @ me.vertices[i].co for i in idx]
            ev.to_mesh_clear()
        zmin = min(p.z for p in pts)
        low = [p for p in pts if p.z < zmin + 0.005]
        out[side] = [round(zmin, 4), round(sum(p.x for p in low) / len(low), 4)]
    return out


def render_feet(sc, base, badger_meshes):
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.color_type = "VERTEX"
    for name in ("feet", "side"):
        for ob in badger_meshes:
            ob.data.color_attributes.active_color = ob.data.color_attributes[name]
        sc.render.filepath = base + f"_{name}.png"
        bpy.ops.render.render(write_still=True)
    sc.display.shading.color_type = "MATERIAL"


def passes(sc, harbor, badger, arm, root):
    world = bpy.data.worlds.new("Black")
    sc.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0, 0, 0, 1)
    bg.inputs["Strength"].default_value = 0.0
    sc.view_settings.view_transform = "Raw"
    sc.view_settings.look = "None"
    sc.render.film_transparent = True
    sc.render.filter_size = 0.0
    sc.render.dither_intensity = 0.0           # sonst Rauschen beim Umrechnen auf 8 bit (Kennfarben ±1)
    sc.render.resolution_x, sc.render.resolution_y = SW * A.ss, SH * A.ss
    meshes = [o for o in bpy.data.objects if o.type == "MESH" and not o.hide_render]
    ids, light_nodes = make_pass_materials(meshes)
    os.makedirs(A.out, exist_ok=True)
    json.dump(ids, open(os.path.join(A.out, "ids.json"), "w"), indent=1)
    only = set(x for x in A.only.split(",") if x)
    by_name = {o.name: o for o in bpy.data.objects}
    sea = by_name["Sea"]
    harbor_meshes = [o for o in harbor if o.type == "MESH"]
    badger_meshes = [o for o in badger if o.type == "MESH" and not o.hide_render]
    setup_feet(badger_meshes)
    info = {"ss": A.ss, "scene_px": [SW, SH], "shots": {}}
    for key, shot in SHOTS["shots"].items():
        cam = add_camera(sc, shot)
        set_lights(light_nodes, shot)
        bpy.context.view_layer.update()
        si = {"anchors": {}, "clips": {}}
        for an in SHOTS["anchors"]:
            o = by_name[an]
            si["anchors"][an] = project(sc, cam, o.matrix_world.translation, SW, SH)
        c = shot["cam"]
        si["anchors"]["Horizon"] = project(sc, cam, g2b((c[0], -0.8, c[2] - 3000.0)), SW, SH)
        # Laufweg: Bildpunkte je Meter entlang x auf Höhe des Clips
        for cname, clip in shot.get("clips", {}).items():
            x, y, z, rot = clip["at"]
            p0 = project(sc, cam, g2b((x, y, z)), SW, SH)
            p1 = project(sc, cam, g2b((x + 1.0, y, z)), SW, SH)
            ph = project(sc, cam, g2b((x, y + 1.0, z)), SW, SH)
            si["clips"][cname] = {"action": clip["action"], "times": clip["times"], "at": clip["at"],
                                  "foot_px": p0, "px_per_m_x": [p1[0] - p0[0], p1[1] - p0[1]],
                                  "px_per_m_up": p0[1] - ph[1]}
        info["shots"][key] = si
        # Ebenen des Hintergrunds (Dachs aus)
        for o in badger_meshes:
            o.hide_render = True
        for lname, names in SHOTS["layers"].items():
            tag = f"{key}_{lname}"
            if only and tag not in only:
                continue
            for o in harbor_meshes:
                o.hide_render = not (o.name in names or o is sea)
            render_pair(sc, os.path.join(A.out, tag))
            print("PASS", tag)
        # Dachs (Hafen aus)
        for o in harbor_meshes:
            o.hide_render = True
        for o in badger_meshes:
            o.hide_render = False
        for cname, clip in shot.get("clips", {}).items():
            place_badger(root, *clip["at"])
            act = set_action(arm, clip["action"])
            f0 = act.frame_range[0]
            for i, t in enumerate(clip["times"]):
                tag = f"{key}_{cname}_{i:02d}"
                if only and tag not in only and f"{key}_{cname}" not in only:
                    continue
                fr = f0 + t * 30.0
                sc.frame_set(int(math.floor(fr)), subframe=fr - math.floor(fr))
                bpy.context.view_layer.update()
                render_pair(sc, os.path.join(A.out, tag))
                render_feet(sc, os.path.join(A.out, tag), badger_meshes)
                si["clips"][cname].setdefault("feet", []).append(foot_contact(badger_meshes))
                print("PASS", tag)
        bpy.data.objects.remove(cam)
    json.dump(info, open(os.path.join(A.out, "frames.json"), "w"), indent=1)


def main():
    sc, harbor, badger, arm, root = setup()
    if A.mode == "layout":
        layout(sc, harbor, badger, arm, root)
    else:
        passes(sc, harbor, badger, arm, root)
    print("DONE")


main()
