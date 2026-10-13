# -*- coding: utf-8 -*-
"""Rendert den gemeinsamen Dachs (shared/3d/badger_low.glb) als Materialkarte für die Handheld-Sprites.

Seitenansicht (Kamera auf Blender -Y, Blick +Y, rechte Körperseite mit Paket zur Kamera), orthografisch,
Workbench ohne Licht und ohne Kantenglättung: jedes Material bekommt eine eigene Farbe, damit build_badger.py
je Zielpixel das Material per Mehrheit bestimmen kann (statt Farben zu mitteln).

  blender -b --factory-startup -P styles/gameboy/blender/render_badger_ids.py -- \
      --glb shared/3d/badger_low.glb --out styles/gameboy/assets/raw/ids --px 0.045 --ss 10

Ausgabe: walk_00.png ... walk_29.png (Walk, 30 Bilder), idle_00.png, rest.png; Bildgröße 24x32 Zielpixel × ss.
Boden (z = 0) liegt auf der Unterkante der Rahmenzeile 28 (wie TOP 6 + 22 in badger.py).
"""
import argparse
import math
import os
import sys

import bpy

IDS = {   # Material -> ID-Farbe (linear, mit Raw-Ausgabe 1:1 im PNG)
    "FurDark": (0.0, 0.0, 1.0), "FurLight": (1.0, 1.0, 1.0), "Cap": (0.0, 1.0, 0.0), "Brass": (1.0, 1.0, 0.0),
    "Vest": (0.0, 0.5, 0.0), "Shirt": (1.0, 0.5, 0.0), "Scarf": (1.0, 0.0, 0.0), "Satchel": (0.5, 0.0, 0.0),
    "Parcel": (1.0, 0.0, 1.0), "Nose": (0.0, 1.0, 1.0), "Eye": (0.5, 0.0, 1.0),
}


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--px", type=float, default=0.045, help="Meter je Zielpixel")
    ap.add_argument("--ss", type=int, default=10, help="Unterabtastung je Zielpixel")
    ap.add_argument("--head-scale", type=float, default=1.0, help="Kopf größer (Knochen head), Kindchenschema")
    ap.add_argument("--stretch-x", type=float, default=1.0, help="Figur in Laufrichtung breiter")
    return ap.parse_args(argv)


A = args()


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


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = 30
    bpy.ops.import_scene.gltf(filepath=os.path.abspath(A.glb))
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "FLAT"
    sh.color_type = "MATERIAL"
    sh.show_object_outline = False
    sh.show_cavity = False
    sh.show_specular_highlight = False
    sh.show_shadows = False
    sc.display.render_aa = "OFF"
    sc.view_settings.view_transform = "Raw"
    sc.view_settings.look = "None"
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    W, H = 24, 32
    sc.render.resolution_x, sc.render.resolution_y = W * A.ss, H * A.ss
    sc.render.resolution_percentage = 100
    for m in bpy.data.materials:
        base = m.name.split(".")[0]
        if base in IDS:
            m.diffuse_color = (*IDS[base], 1.0)
        else:
            print("WARN unbekanntes Material", m.name)
    for o in bpy.data.objects:
        if o.type == "MESH" and not any(md.type == "ARMATURE" for md in o.modifiers):
            o.hide_render = True                          # Knochenform "Icosphere" des Importers
    cam = bpy.data.cameras.new("Cam")
    cam.type = "ORTHO"
    cam.sensor_fit = "VERTICAL"
    cam.ortho_scale = H * A.px
    ob = bpy.data.objects.new("Cam", cam)
    sc.collection.objects.link(ob)
    sc.camera = ob
    # Boden auf Unterkante Zeile 28 -> 3 Zeilen darunter; Bildmitte senkrecht bei z = (16 - 3) * px
    ob.location = (0.0, -5.0, (H / 2 - 3) * A.px)
    ob.rotation_euler = (math.radians(90), 0, 0)
    os.makedirs(A.out, exist_ok=True)
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    print("INFO actions", [(a.name, tuple(a.frame_range)) for a in bpy.data.actions])
    # Kopfgröße: die Aktionen tragen Skalierungskurven je Knochen (glTF), deshalb die Kurven selbst ändern
    n = 0
    for act in bpy.data.actions:
        for layer in getattr(act, "layers", []):
            for strip in layer.strips:
                for cb in strip.channelbags:
                    for fc in cb.fcurves:
                        if fc.data_path == 'pose.bones["head"].scale':
                            for kp in fc.keyframe_points:
                                kp.co[1] *= A.head_scale
                                kp.handle_left[1] *= A.head_scale
                                kp.handle_right[1] *= A.head_scale
                            n += 1
    print("INFO head scale curves", n)

    arm.scale = (A.stretch_x, 1.0, 1.0)

    def shot(name):
        pb = arm.pose.bones.get("head")
        pb.scale = (A.head_scale, A.head_scale, A.head_scale)
        bpy.context.view_layer.update()
        sc.render.filepath = os.path.join(A.out, name)
        bpy.ops.render.render(write_still=True)

    set_action(arm, None)
    sc.frame_set(0)
    shot("rest.png")
    act = set_action(arm, "Walk")
    f0, f1 = [int(round(x)) for x in act.frame_range]
    for f in range(f0, f1):
        sc.frame_set(f)
        shot("walk_%02d.png" % (f - f0))
    act = set_action(arm, "Idle")
    f0, f1 = [int(round(x)) for x in act.frame_range]
    for k, f in enumerate(range(f0, f1, 15)):
        sc.frame_set(f)
        shot("idle_%02d.png" % k)
    print("DONE")


main()
