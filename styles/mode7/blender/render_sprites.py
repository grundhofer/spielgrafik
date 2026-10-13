# -*- coding: utf-8 -*-
"""Rendert die Rohbilder für die Sprite-Größenstufen (Mode 7 kann Sprites nicht skalieren).

Aufruf (aus dem Projektordner):
  blender -b --factory-startup -P styles/mode7/blender/render_sprites.py -- \
      --spec styles/mode7/blender/sprites_spec.json --out <tmp>/sprites [--only badger_walk]

Je Blatt, Größenstufe und Bild zwei Durchgänge mit EEVEE, ohne Kantenglättung und ohne Dithering:
  *_id.png   Materialnummer im Rotkanal (Wert = 8 × Nummer), Alpha = Abdeckung
  *_nrm.png  Normale im Kameraraum als Farbe (0,5 + 0,5·n), 16 Bit
Orthografische Kamera unter festem Höhen- und Seitenwinkel, Maßstab = Pixel je Meter × Überabtastung.
scripts/build_sprites.py verkleinert danach je Zielpixel nach Mehrheit des Materials und schattiert mit
der Palette. Die Lage des Bodenpunkts (Ursprung des Objekts) und weiterer Punkte (Schornstein, Laterne)
steht in index.json.
"""
import argparse
import json
import math
import os
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Euler, Vector


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="")
    return ap.parse_args(argv)


ARGS = parse_args()
SPEC = json.load(open(ARGS.spec))
MATS = SPEC["materials"]          # Name -> Nummer (1..31)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = 30
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = 1
    sc.render.filter_size = 0.0
    sc.render.film_transparent = True
    sc.render.dither_intensity = 0.0
    sc.view_settings.view_transform = "Raw" if "Raw" in [i.identifier for i in
        sc.view_settings.bl_rna.properties["view_transform"].enum_items] else "Standard"
    sc.view_settings.look = "None"
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.resolution_percentage = 100
    world = bpy.data.worlds.new("W")
    sc.world = world
    if world.node_tree is None:
        world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Strength"].default_value = 0.0
    return sc


def make_mats():
    """Je Material eine ID- und eine Normalen-Fassung (nur Emission)."""
    out = {}
    for name, num in MATS.items():
        mid = bpy.data.materials.new(f"ID_{name}")
        mid.use_nodes = True
        nt = mid.node_tree
        nt.nodes.clear()
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = (num * 8 / 255.0, 0, 0, 1)
        em.inputs["Strength"].default_value = 1.0
        o = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(em.outputs[0], o.inputs["Surface"])
        out[name] = mid
    mn = bpy.data.materials.new("NRM")
    mn.use_nodes = True
    nt = mn.node_tree
    nt.nodes.clear()
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    vt = nt.nodes.new("ShaderNodeVectorTransform")
    vt.vector_type = "NORMAL"
    vt.convert_from = "WORLD"
    vt.convert_to = "CAMERA"
    mul = nt.nodes.new("ShaderNodeVectorMath")
    mul.operation = "MULTIPLY_ADD"
    mul.inputs[1].default_value = (0.5, 0.5, -0.5)     # Kameraraum: −Z blickt nach vorn; z zur Kamera positiv
    mul.inputs[2].default_value = (0.5, 0.5, 0.5)
    em = nt.nodes.new("ShaderNodeEmission")
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(geo.outputs["Normal"], vt.inputs[0])
    nt.links.new(vt.outputs[0], mul.inputs[0])
    nt.links.new(mul.outputs[0], em.inputs["Color"])
    nt.links.new(em.outputs[0], o.inputs["Surface"])
    return out, mn


def base_name(matname):
    return matname.split(".")[0]


def set_pass(meshes, kind, idmats, nrm):
    for ob in meshes:
        if ob.name == "Holdout":
            continue
        for i, slot in enumerate(ob.material_slots):
            orig = ob.get("orig_mats")[i]
            if kind == "id":
                if orig not in idmats:
                    raise RuntimeError(f"Material {orig} fehlt in materials ({ob.name})")
                slot.material = idmats[orig]
            else:
                slot.material = nrm


def armature():
    return next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)


def set_action(arm, name):
    ad = arm.animation_data or arm.animation_data_create()
    for tr in list(ad.nla_tracks):
        ad.nla_tracks.remove(tr)
    act = next(a for a in bpy.data.actions if a.name == name or a.name.startswith(name + "_"))
    ad.action = act
    if getattr(ad, "action_slot", None) is None and len(act.slots):
        ad.action_slot = act.slots[0]


def render_sheet(sh, idmats, nrm, out_dir, index):
    sc = bpy.context.scene
    names = sh["objects"]
    root_names = sh["roots"]
    if "origin" in sh:
        root_pos = Vector(sh["origin"])
    else:
        ps = [bpy.data.objects[n].matrix_world.translation for n in root_names]
        root_pos = sum(ps, Vector()) / len(ps)
    meshes = []
    for ob in bpy.data.objects:
        keep = ob.name in names or (ob.parent and ob.parent.name in names and ob.type == "MESH")
        if ob.type == "MESH":
            ob.hide_render = not keep
            if keep:
                meshes.append(ob)
    for ob in meshes:
        if ob.get("orig_mats") is None:
            ob["orig_mats"] = [base_name(s.material.name) for s in ob.material_slots]
    # Objekte um die Hochachse durch den Ursprung drehen (Blickrichtung der Figur / Lage des Objekts)
    yaw = math.radians(sh.get("yaw", 0.0))
    roll_list = sh.get("rolls", [0.0])
    roots = [bpy.data.objects[n] for n in root_names]
    hold = bpy.data.objects.get("Holdout")
    if hold:
        hold.hide_render = "holdout_z" not in sh
        if "holdout_z" in sh:
            hold.location = (root_pos.x, root_pos.y, sh["holdout_z"])
    saved = {ob.name: (ob.matrix_world.copy()) for ob in roots}
    arm = armature() if sh.get("action") else None
    if arm:
        set_action(arm, sh["action"])
    cam_data = bpy.data.cameras.get("SprCam") or bpy.data.cameras.new("SprCam")
    cam_data.type = "ORTHO"
    cam = bpy.data.objects.get("SprCam") or bpy.data.objects.new("SprCam", cam_data)
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    sc.camera = cam
    el = math.radians(sh["elevation"])
    az = math.radians(sh.get("azimuth", 0.0))
    view_dir = Vector((-math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), -math.sin(el)))  # Blick
    bw, bh = sh["box"]
    ax, ay = sh["anchor"]          # Anteil im Bild, wo der Bodenpunkt liegen soll (x von links, y von oben)
    marks = sh.get("marks", {})    # Name -> Objektname eines Empties/Objekts, dessen Lage mitgeschrieben wird
    for si, ppm in enumerate(sh["ppm"]):
        ss = sh.get("ss", 4)
        w = max(1, int(math.ceil(bw * ppm))) * ss
        h = max(1, int(math.ceil(bh * ppm))) * ss
        sc.render.resolution_x, sc.render.resolution_y = w, h
        cam_data.ortho_scale = max(w, h) / (ppm * ss)
        cam_data.sensor_fit = "AUTO"
        # Kamera so verschieben, dass der Bodenpunkt bei (ax, ay) liegt
        right = view_dir.cross(Vector((0, 0, 1))).normalized()
        up = right.cross(view_dir).normalized()
        cam.rotation_euler = view_dir.to_track_quat("-Z", "Y").to_euler()
        span_x = w / (ppm * ss)
        span_y = h / (ppm * ss)
        off = right * ((0.5 - ax) * span_x) + up * ((ay - 0.5) * span_y)
        cam.location = root_pos - view_dir * 50.0 + off
        for fi, fr in enumerate(sh.get("frames", [0])):
            for ri, roll in enumerate(roll_list):
                for ob in roots:
                    m = saved[ob.name]
                    rot = Euler((roll_x(roll, sh), 0, yaw), "XYZ").to_matrix().to_4x4()
                    piv = root_pos
                    from mathutils import Matrix
                    ob.matrix_world = Matrix.Translation(piv) @ rot @ Matrix.Translation(-piv) @ m
                if arm:
                    f = float(fr)
                    sc.frame_set(int(math.floor(f)), subframe=f - math.floor(f))
                else:
                    sc.frame_set(0)
                bpy.context.view_layer.update()
                tag = f"{sh['name']}_s{si}_f{fi}" + (f"_r{ri}" if len(roll_list) > 1 else "")
                for kind in ("id", "nrm"):
                    set_pass(meshes, kind, idmats, nrm)
                    sc.render.image_settings.color_depth = "8" if kind == "id" else "16"
                    sc.render.filepath = os.path.join(out_dir, f"{tag}_{kind}.png")
                    bpy.ops.render.render(write_still=True)
                gp = world_to_camera_view(sc, cam, root_pos)
                rec = {"sheet": sh["name"], "step": si, "frame": fi, "roll": ri, "ppm": ppm, "ss": ss,
                       "size": [w, h], "ground": [gp.x * w, (1 - gp.y) * h], "marks": {}}
                for mk, obn in marks.items():
                    ob = bpy.data.objects[obn]
                    p = world_to_camera_view(sc, cam, ob.matrix_world.translation)
                    rec["marks"][mk] = [p.x * w, (1 - p.y) * h]
                index.append(rec)
        for ob in roots:
            ob.matrix_world = saved[ob.name]


def make_holdout():
    """Wasserfläche als Holdout: schneidet den Rumpf unter der Wasserlinie weg (Alpha 0)."""
    me = bpy.data.meshes.new("Holdout")
    s = 40.0
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    m = bpy.data.materials.new("HoldoutMat")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    hn = nt.nodes.new("ShaderNodeHoldout")
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(hn.outputs[0], o.inputs["Surface"])
    me.materials.append(m)
    ob = bpy.data.objects.new("Holdout", me)
    ob["orig_mats"] = ["__holdout__"]
    bpy.context.scene.collection.objects.link(ob)
    ob.hide_render = True


def roll_x(roll, sh):
    return math.radians(roll)


def main():
    os.makedirs(ARGS.out, exist_ok=True)
    index = []
    glb_loaded = None
    for sh in SPEC["sheets"]:
        if ARGS.only and sh["name"] not in ARGS.only.split(","):
            continue
        if sh["glb"] != glb_loaded:
            reset()
            bpy.ops.import_scene.gltf(filepath=os.path.abspath(sh["glb"]))
            for ob in list(bpy.data.objects):
                if ob.name == "Icosphere":
                    bpy.data.objects.remove(ob)
            idmats, nrm = make_mats()
            make_holdout()
            glb_loaded = sh["glb"]
        render_sheet(sh, idmats, nrm, ARGS.out, index)
        print("SHEET", sh["name"])
    old = []
    ip = os.path.join(ARGS.out, "index.json")
    if os.path.exists(ip) and ARGS.only:
        old = [r for r in json.load(open(ip)) if r["sheet"] not in ARGS.only.split(",")]
    json.dump(old + index, open(ip, "w"), indent=1)


main()
