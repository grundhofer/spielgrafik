# -*- coding: utf-8 -*-
"""Dachs-Kurier als vorgerenderte BOB-Einzelbilder (Amiga: Blitter-Objekte aus Einzelbildern).

Aufruf (aus dem Projektordner):
  blender -b --factory-startup -P styles/amiga-illustration/blender/render_badger.py -- \
      --out styles/amiga-illustration/assets/raw/badger3d [--ppm 40.87] [--ss 4]

Rendert aus shared/3d/badger.glb (unverändert) die ganze Vorführung der Demo mit 15 Bildern/s in einer
festen Seitenansicht (orthografisch, Kamera blickt auf die rechte Körperseite wie die Hafenkamera):
  Laufen (Walk, speed_scale 1,5), Abbremsen bis zu einer Beinstellung mit geschlossenen Füßen, Idle,
  Drehung zur Kamera, Winken (Wave), Idle.
Je Bild zwei Renderings in SS-facher Auflösung:
  shaded_NNN.png  EEVEE, Abendlicht (warmes Führungslicht, kühles Himmelslicht, oranges Gegenlicht)
  id_NNN.png      Workbench, flache Materialfarben ohne Kantenglättung (Material-ID je Pixel)
Die Figur wird mit Wurzelbewegung gerendert; die Kamera rückt nur in ganzen Zielpixeln nach. Dadurch liegt das
Zielraster fest in der Welt: Der Standfuß steht in allen Bildern auf denselben Zielpixeln (kein Rutschen).
frames.json: je Bild Zeit, Zustand, linke Kante (Zielpixel, relativ zum Haltepunkt der Wurzel) und Zellgröße.
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Quaternion, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--glb", default=os.path.join(ROOT, "shared/3d/badger.glb"))
    ap.add_argument("--ppm", type=float, default=15 / 0.367)    # Zielpixel je Meter: 15 px Schrittlänge je Zyklus
    ap.add_argument("--ss", type=int, default=4)                 # Überabtastung
    ap.add_argument("--fps", type=int, default=15)
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--only", default="")                        # z. B. "0,10,44" für Probebilder
    return ap.parse_args(argv)


A = parse_args()
WALK_SPEED = 0.367           # m/s bei speed_scale 1 (README shared/3d)
RATE = 2.0                   # speed_scale beim Laufen (0,73 m/s wie in der Probeszene)
FOOT_MARGIN = 2              # Zielpixel unter der Fußsohle
CELL_W = int(math.ceil(1.06 * A.ppm)) // 2 * 2       # Zielpixel je Bild (Platz für Arm und Paket)
CELL_H = int(math.ceil(1.30 * A.ppm)) + FOOT_MARGIN

# Ablauf (Sekunden): Laufen bis T_BRAKE, Abbremsen bis T_STOP, Idle, Drehen, Winken, Idle
T_BRAKE, T_STOP = 2.80, 3.20
T_TURN0, T_TURN1 = 3.40, 3.80
T_WAVE0 = 3.80
WAVE_LEN = 1.5
T_END = 6.0
BLEND = 0.2                  # Überblendung zwischen Animationen


def hex_lin(h):
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return out


ID_COLORS = {  # Material -> flache Kennfarbe für den ID-Pass (weit auseinander)
    "FurDark": "#202020", "FurLight": "#F0F0F0", "Cap": "#00A000", "Brass": "#FFFF00", "Vest": "#006060",
    "Shirt": "#C0C080", "Scarf": "#FF0000", "Satchel": "#804000", "Parcel": "#FF8000", "Nose": "#000080",
    "Eye": "#8000FF",
}


def setup():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = 30
    bpy.ops.import_scene.gltf(filepath=A.glb)
    sc = bpy.context.scene
    for o in bpy.data.objects:
        if o.name.startswith("Icosphere"):
            o.hide_render = True
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"
    sc.render.resolution_x = CELL_W * A.ss
    sc.render.resolution_y = CELL_H * A.ss
    sc.render.resolution_percentage = 100
    world = bpy.data.worlds.new("Dusk")
    sc.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (*hex_lin("#3A3F66"), 1)
    bg.inputs["Strength"].default_value = 0.7
    cam = bpy.data.cameras.new("Cam")
    cam.type = "ORTHO"
    cam.sensor_fit = "VERTICAL"
    cam.ortho_scale = CELL_H / A.ppm
    cam_ob = bpy.data.objects.new("Cam", cam)
    sc.collection.objects.link(cam_ob)
    cam_ob.rotation_euler = (math.radians(90), 0, 0)     # blickt nach +Y (Godot -Z), also auf die rechte Seite
    sc.camera = cam_ob

    def sun(name, col, energy, direction):
        L = bpy.data.lights.new(name, "SUN")
        L.color = hex_lin(col)
        L.energy = energy
        L.angle = math.radians(6)
        ob = bpy.data.objects.new(name, L)
        sc.collection.objects.link(ob)
        ob.rotation_euler = Vector(direction).normalized().to_track_quat("-Z", "Y").to_euler()
        return ob

    # Richtungen = Lichtrichtung (vom Licht zur Figur), Blender-Achsen: +Y = vom Betrachter weg, +Z oben
    sun("Key", "#FFFFFF", 3.4, (0.55, 0.7, -0.55))      # neutrales Führungslicht von vorn links oben
    sun("Fill", "#C8D0FF", 1.4, (-0.6, 0.8, -0.25))     # kühles Himmelslicht von vorn rechts
    sun("Rim", "#FFB070", 1.2, (0.35, -0.9, -0.15))     # Abendrot von hinten
    return sc, cam_ob


def armature():
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    ad = arm.animation_data or arm.animation_data_create()
    for tr in list(ad.nla_tracks):      # der glTF-Import legt die Animationen auch als NLA-Spuren ab
        ad.nla_tracks.remove(tr)
    return arm


ACTIONS = {}


def sample_pose(arm, name, seconds):
    """Pose (je Knochen loc, quat, scale) der Animation name zur Zeit seconds (30 fps im glTF)."""
    ad = arm.animation_data or arm.animation_data_create()
    act = ACTIONS[name]
    ad.action = act
    if getattr(ad, "action_slot", None) is None and len(act.slots):
        ad.action_slot = act.slots[0]
    f = seconds * 30.0
    fi = int(math.floor(f))
    bpy.context.scene.frame_set(fi, subframe=f - fi)
    pose = {}
    for pb in arm.pose.bones:
        q = pb.rotation_quaternion.copy() if pb.rotation_mode == "QUATERNION" else pb.rotation_euler.to_quaternion()
        pose[pb.name] = (pb.location.copy(), q, pb.scale.copy())
    return pose


def blend(p1, p2, w):
    out = {}
    for k in p1:
        l1, q1, s1 = p1[k]
        l2, q2, s2 = p2[k]
        out[k] = (l1.lerp(l2, w), q1.slerp(q2, w), s1.lerp(s2, w))
    return out


def apply_pose(arm, pose):
    ad = arm.animation_data
    ad.action = None
    for pb in arm.pose.bones:
        l, q, s = pose[pb.name]
        pb.location = l
        if pb.rotation_mode == "QUATERNION":
            pb.rotation_quaternion = q
        else:
            pb.rotation_euler = q.to_euler(pb.rotation_mode)
        pb.scale = s
    bpy.context.view_layer.update()


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def foot_gap(arm, tau):
    """Waagrechter Abstand der Fußknochen (m) in der Walk-Animation zur Zeit tau."""
    sample_pose(arm, "Walk", tau)
    bpy.context.view_layer.update()
    xs = [(arm.matrix_world @ arm.pose.bones[n].head).x for n in ("foot.L", "foot.R") if n in arm.pose.bones]
    return abs(xs[0] - xs[1]) if len(xs) == 2 else 0.0


def timeline(arm):
    """Animationszeit tau(t) der Walk-Animation: Laufen mit RATE, Abbremsen linear auf 0. Das Ende liegt auf der
    Phase mit dem kleinsten Fußabstand (Füße beisammen), dann kann ohne Sprung auf Idle überblendet werden."""
    gaps = [(foot_gap(arm, i / 60.0), i / 60.0) for i in range(60)]
    best = min(gaps)[1]
    walk_tau = RATE * T_BRAKE + RATE * (T_STOP - T_BRAKE) / 2.0
    tau0 = (best - walk_tau) % 1.0
    return tau0, walk_tau, best, min(gaps)[0]


def tau_at(t, tau0):
    if t <= T_BRAKE:
        return tau0 + RATE * t
    if t <= T_STOP:
        d = t - T_BRAKE
        D = T_STOP - T_BRAKE
        return tau0 + RATE * T_BRAKE + RATE * (d - d * d / (2 * D))
    return tau0 + RATE * T_BRAKE + RATE * (T_STOP - T_BRAKE) / 2.0


def state_at(arm, t, tau0):
    """Pose, Wurzel-x (m, relativ zum Haltepunkt), Drehung um die Hochachse (Grad) und Zustandsname."""
    tau_end = tau_at(T_END, tau0)
    x = WALK_SPEED * (tau_at(t, tau0) - tau_end)
    yaw = 0.0
    if t < T_STOP:
        pose = sample_pose(arm, "Walk", tau_at(t, tau0) % 1.0)
        st = "walk" if t < T_BRAKE else "brake"
    else:
        idle = sample_pose(arm, "Idle", (t - T_STOP) % 2.0)
        st = "idle"
        if t < T_STOP + BLEND:
            w = smooth((t - T_STOP) / BLEND)
            pose = blend(sample_pose(arm, "Walk", tau_end % 1.0), idle, w)
        else:
            pose = idle
        if t >= T_TURN0:
            yaw = -90.0 * smooth((t - T_TURN0) / (T_TURN1 - T_TURN0))
            st = "turn" if t < T_TURN1 else "front"
        if T_WAVE0 <= t < T_WAVE0 + WAVE_LEN + BLEND:
            wt = t - T_WAVE0
            wave = sample_pose(arm, "Wave", min(wt, WAVE_LEN - 1e-3))
            w = smooth(wt / BLEND) * (1.0 - smooth((wt - WAVE_LEN) / BLEND))
            pose = blend(pose, wave, w)
            st = "wave"
    return pose, x, yaw, st


def set_id_materials(on, saved):
    for m in bpy.data.materials:
        if m.name in ID_COLORS:
            if on:
                saved.setdefault(m.name, tuple(m.diffuse_color))
                m.diffuse_color = (*hex_lin(ID_COLORS[m.name]), 1)
            elif m.name in saved:
                m.diffuse_color = saved[m.name]


def main():
    sc, cam_ob = setup()
    arm = armature()
    for a in bpy.data.actions:
        for n in ("Idle", "Walk", "Wave"):
            if a.name == n or a.name.startswith(n + "_") or a.name.startswith(n + "."):
                ACTIONS[n] = a
    tau0, walk_tau, phase, gap = timeline(arm)
    print(f"INFO tau0={tau0:.3f} walk_tau={walk_tau:.3f} Endphase={phase:.3f} Fußabstand={gap:.3f} m")
    os.makedirs(A.out, exist_ok=True)
    n = int(round(T_END * A.fps))
    only = {int(v) for v in A.only.split(",") if v}
    frames = []
    saved = {}
    ppm = A.ppm
    for i in range(n):
        t = i / A.fps
        pose, x, yaw, st = state_at(arm, t, tau0)
        apply_pose(arm, pose)
        arm.location = (x, 0, 0)
        arm.rotation_mode = "XYZ"
        arm.rotation_euler = (0, 0, math.radians(yaw))
        bpy.context.view_layer.update()
        # Zielraster fest in der Welt: linke Kante in ganzen Zielpixeln
        left = int(math.floor(x * ppm)) - CELL_W // 2
        cam_ob.location = ((left + CELL_W / 2) / ppm, -10.0, (CELL_H / 2 - FOOT_MARGIN) / ppm)
        frames.append({"i": i, "t": round(t, 4), "state": st, "left": left, "root_x_px": round(x * ppm, 3),
                       "yaw": round(yaw, 2)})
        if only and i not in only:
            continue
        sc.render.engine = "BLENDER_EEVEE"
        sc.eevee.taa_render_samples = A.samples
        set_id_materials(False, saved)
        sc.render.filepath = os.path.join(A.out, f"shaded_{i:03d}.png")
        bpy.ops.render.render(write_still=True)
        sc.render.engine = "BLENDER_WORKBENCH"
        sc.display.shading.light = "FLAT"
        sc.display.shading.color_type = "MATERIAL"
        sc.display.render_aa = "OFF"
        set_id_materials(True, saved)
        sc.render.filepath = os.path.join(A.out, f"id_{i:03d}.png")
        bpy.ops.render.render(write_still=True)
        set_id_materials(False, saved)
    meta = {"fps": A.fps, "ppm": ppm, "ss": A.ss, "cell": [CELL_W, CELL_H], "foot_margin": FOOT_MARGIN,
            "id_colors": ID_COLORS, "times": {"brake": T_BRAKE, "stop": T_STOP, "turn": [T_TURN0, T_TURN1],
                                              "wave": [T_WAVE0, T_WAVE0 + WAVE_LEN]},
            "walk": {"rate": RATE, "speed_mps": WALK_SPEED * RATE, "tau0": tau0, "end_phase": phase},
            "frames": frames}
    with open(os.path.join(A.out, "frames.json"), "w") as f:
        json.dump(meta, f, indent=1)
    print("DONE", len(frames))


main()
