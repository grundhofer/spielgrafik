# -*- coding: utf-8 -*-
"""Kontrollbilder und Messwerte für badger.glb / badger_low.glb (EEVEE, aus der exportierten GLB).

Aufruf (aus dem Projektordner):
  blender -b --factory-startup -P shared/3d/blender/preview_badger.py -- --glb shared/3d/badger.glb
  blender -b --factory-startup -P shared/3d/blender/preview_badger.py -- --glb shared/3d/badger_low.glb \
      --prefix preview_badger_low --views front,side,walk
  ... -- --glb shared/3d/badger.glb --check --views none      (nur Messwerte: Bodenkontakt, Fußhub)

Ansichten: front, side, back, threequarter, walk (drei Phasen, Seitenansicht), wave, idle.
Die Seitenansicht schaut wie die Hafenkamera auf die rechte Körperseite (Blender -Y, Godot +Z).
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

V = Vector


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="preview_badger.py")
    ap.add_argument("--glb", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--prefix", default="preview_badger")
    ap.add_argument("--views", default="front,side,back,threequarter,walk,wave")
    ap.add_argument("--walk-frames", default="0,9,15")
    ap.add_argument("--size", default="720x900")
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--check", action="store_true")
    return ap.parse_args(argv)


ARGS = parse_args()


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
    sc.render.fps = 30          # vor dem Import setzen, sonst rechnet der Importer mit 24 fps
    bpy.ops.import_scene.gltf(filepath=os.path.abspath(ARGS.glb))
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = ARGS.samples
    w, h = [int(v) for v in ARGS.size.split("x")]
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "Standard"
    world = bpy.data.worlds.new("PreviewWorld")
    sc.world = world
    if world.node_tree is None:
        world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (*hex_lin("#C9D2DA"), 1)
    bg.inputs["Strength"].default_value = 0.85
    # Boden
    me = bpy.data.meshes.new("Ground")
    s = 30.0
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    mat = bpy.data.materials.new("GroundMat")
    if mat.node_tree is None:
        mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*hex_lin("#B9B2A6"), 1)
    bsdf.inputs["Roughness"].default_value = 0.95
    me.materials.append(mat)
    link(bpy.data.objects.new("Ground", me))
    # Lichter (werden je Ansicht zur Kamera ausgerichtet)
    key = bpy.data.lights.new("Key", "SUN")
    key.energy = 3.0
    key.angle = math.radians(4)
    fill = bpy.data.lights.new("Fill", "SUN")
    fill.energy = 0.9
    fill.use_shadow = False
    cam = bpy.data.cameras.new("Cam")
    cam.type = "ORTHO"
    cam.ortho_scale = 1.25
    cam_ob = link(bpy.data.objects.new("Cam", cam))
    sc.camera = cam_ob
    return sc, cam_ob, link(bpy.data.objects.new("Key", key)), link(bpy.data.objects.new("Fill", fill))


def aim(ob, direction):
    ob.rotation_euler = direction.normalized().to_track_quat("-Z", "Y").to_euler()


VIEWS = {   # Kameraposition, Ziel
    "front": (V((3.0, 0.0, 0.52)), V((0, 0, 0.52))),
    "side": (V((0.0, -3.0, 0.52)), V((0, 0, 0.52))),
    "back": (V((-3.0, 0.0, 0.52)), V((0, 0, 0.52))),
    "threequarter": (V((2.3, -2.0, 1.15)), V((0.02, 0, 0.48))),
}


def place_view(name, cam_ob, key_ob, fill_ob):
    pos, tgt = VIEWS[name]
    cam_ob.location = pos
    fwd = (tgt - pos).normalized()
    aim(cam_ob, fwd)
    right = fwd.cross(V((0, 0, 1))).normalized()
    aim(key_ob, fwd + V((0, 0, -0.75)) + right * 0.55)
    aim(fill_ob, fwd + V((0, 0, -0.2)) - right * 0.8)


def armature():
    return next(o for o in bpy.data.objects if o.type == "ARMATURE")


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
    act = next((a for a in bpy.data.actions if a.name == name or a.name.startswith(name + "_")
                or a.name.startswith(name + ".")), None)
    if act is None:
        raise RuntimeError(f"Animation {name} fehlt; vorhanden: {[a.name for a in bpy.data.actions]}")
    ad.action = act
    if getattr(ad, "action_slot", None) is None and len(act.slots):
        ad.action_slot = act.slots[0]
    return act


def render(sc, path):
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("PREVIEW", path)


def foot_vertex_sets(meshes):
    sets = {}
    for ob in meshes:
        for side in "LR":
            vg = ob.vertex_groups.get("foot." + side)
            if vg is None:
                continue
            idx = []
            for v in ob.data.vertices:
                for g in v.groups:
                    if g.group == vg.index and g.weight > 0.5:
                        idx.append(v.index)
            sets[(ob.name, side)] = idx
    return sets


def check(sc, arm, meshes):
    dg = bpy.context.evaluated_depsgraph_get()
    fsets = foot_vertex_sets(meshes)
    for name in ("Idle", "Walk", "Wave"):
        act = set_action(arm, name)
        f0, f1 = [int(round(x)) for x in act.frame_range]
        lowest, rows = 1e9, []
        for f in range(f0, f1 + 1):
            sc.frame_set(f)
            dg.update()
            mins = {"L": 1e9, "R": 1e9}
            allmin = 1e9
            for ob in meshes:
                ev = ob.evaluated_get(dg)
                me = ev.to_mesh()
                mw = ob.matrix_world
                zs = [(mw @ v.co).z for v in me.vertices]
                allmin = min(allmin, min(zs))
                for side in "LR":
                    for i in fsets.get((ob.name, side), []):
                        mins[side] = min(mins[side], zs[i])
                ev.to_mesh_clear()
            lowest = min(lowest, allmin)
            rows.append((f, round(allmin, 4), round(mins["L"], 4), round(mins["R"], 4)))
        print(f"CHECK {name}: frames {f0}-{f1}, tiefster Punkt {lowest:.4f} m")
        if name == "Walk":
            for r in rows:
                print("CHECK   frame %2d  min %.4f  footL %.4f  footR %.4f" % r)
            print("CHECK   Fußhub max L %.3f R %.3f" % (max(r[2] for r in rows), max(r[3] for r in rows)))


def main():
    sc, cam_ob, key_ob, fill_ob = setup()
    arm = armature()
    # nur gehäutete Meshes (der Importer legt zusätzlich eine "Icosphere" als Knochenform an)
    meshes = [o for o in bpy.data.objects if o.type == "MESH" and any(m.type == "ARMATURE" for m in o.modifiers)]
    tris = {o.name: sum(len(p.vertices) - 2 for p in o.data.polygons) for o in meshes}
    print("INFO meshes", tris, "summe", sum(tris.values()))
    print("INFO bones", [b.name for b in arm.data.bones])
    print("INFO actions", [(a.name, tuple(a.frame_range)) for a in bpy.data.actions])
    if ARGS.check:
        check(sc, arm, meshes)
    out = ARGS.out or os.path.dirname(os.path.abspath(ARGS.glb))
    views = [v for v in ARGS.views.split(",") if v and v != "none"]
    for v in views:
        if v in VIEWS:
            set_action(arm, None)
            sc.frame_set(0)
            place_view(v, cam_ob, key_ob, fill_ob)
            render(sc, os.path.join(out, f"{ARGS.prefix}_{v}.png"))
        elif v == "walk":
            set_action(arm, "Walk")
            place_view("side", cam_ob, key_ob, fill_ob)
            for k, f in enumerate(int(x) for x in ARGS.walk_frames.split(",")):
                sc.frame_set(f)
                render(sc, os.path.join(out, f"{ARGS.prefix}_walk_{k + 1}.png"))
        elif v in ("wave", "idle"):
            set_action(arm, v.capitalize())
            place_view("threequarter" if v == "wave" else "front", cam_ob, key_ob, fill_ob)
            sc.frame_set(22 if v == "wave" else 15)
            render(sc, os.path.join(out, f"{ARGS.prefix}_{v}.png"))


main()
