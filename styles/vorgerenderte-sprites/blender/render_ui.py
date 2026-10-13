"""Oberfläche vorrendern: Holzrahmen der Textbox, Messingschild für den Ort, drehendes Paket als Zeiger.

blender -b --factory-startup -P blender/render_ui.py -- OUTDIR [--frame 418x60] [--plaque 146x15] [--samples 64]

Alles orthografisch von oben, 1 Zielpixel = 1 cm, 4× überabgetastet; der Rahmen wird in genau der
Zielgröße gebaut (Leisten, Messingecken, Nägel), damit nichts gestreckt werden muss. Für andere Größen
das Skript mit anderen Maßen laufen lassen.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

import vs_scene as S  # noqa: E402

PX = 0.01   # 1 Zielpixel = 1 cm


def parse():
    a = S.arg_list()
    o = {"out": a[0], "frame": "418x60", "plaque": "146x15", "samples": 64, "border": 7}
    i = 1
    while i < len(a):
        k = a[i].lstrip("-")
        o[k] = type(o[k])(a[i + 1])
        i += 2
    return o


def box(name, x0, y0, x1, y1, z0, z1, mat, bevel=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = x0 + (v.co.x + 0.5) * (x1 - x0)
        v.co.y = y0 + (v.co.y + 0.5) * (y1 - y0)
        v.co.z = z0 + (v.co.z + 0.5) * (z1 - z0)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    ob = bpy.data.objects.new(name, me)
    S._link(ob)
    if bevel:
        m = ob.modifiers.new("Fase", "BEVEL")
        m.width = bevel
        m.segments = 3
    ob.data.materials.append(mat)
    return ob


def sphere(name, loc, r, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=16, ring_count=8)
    ob = bpy.context.active_object
    ob.name = name
    ob.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    return ob


def mats():
    out = {}
    for name in ("Wood", "WoodDark", "Brass", "Parcel", "Shirt"):
        m = bpy.data.materials.new(name)
        c, r, met, d = S.MATS[name]
        S.build_material(m, c, r, met, d)
        out[name] = m
    # Messing für die Oberfläche: weniger metallisch, sonst spiegelt es nur den dunklen Himmel
    S.build_material(out["Brass"], "#D9A845", 0.3, 0.45, None)
    # Holz der Leisten: Maserung in Weltkoordinaten statt UV (Würfel ohne passende UVs)
    for name in ("Wood", "WoodDark"):
        nt = out[name].node_tree
        tc = [n for n in nt.nodes if n.bl_idname == "ShaderNodeTexCoord"][0]
        mp = [n for n in nt.nodes if n.bl_idname == "ShaderNodeMapping"][0]
        nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
        mp.inputs["Scale"].default_value = (2.0, 30.0, 1.0)
    return out


def ui_scene(o, w_px, h_px):
    S.reset()
    S.world_sky(strength=0.6, clouds=False)
    S.sun("Key", (0.5, -0.6, -0.7), 3.2, "#FFF1DC", angle=8)     # von oben links
    S.sun("Rim", (-0.6, 0.5, -0.4), 0.8, "#9AA8FF", angle=10)
    cd = bpy.data.cameras.new("UICam")
    cd.type = "ORTHO"
    cd.sensor_fit = "HORIZONTAL" if w_px >= h_px else "VERTICAL"
    cd.ortho_scale = max(w_px, h_px) * PX
    co = S._link(bpy.data.objects.new("UICam", cd))
    co.location = (w_px * PX / 2, h_px * PX / 2, 5.0)
    bpy.context.scene.camera = co
    sc = S.render_setup("CYCLES", samples=o["samples"], transparent=True, w=w_px, h=h_px)
    return sc


def do_frame(o, out):
    w, h = map(int, o["frame"].split("x"))
    b = o["border"]
    sc = ui_scene(o, w, h)
    M = mats()
    W, H, B = w * PX, h * PX, b * PX
    t = 0.04
    # zwei lange Leisten oben und unten, zwei kurze links und rechts, leicht gefast
    box("Top", 0, H - B, W, H, 0, t, M["Wood"], bevel=0.012)
    box("Bottom", 0, 0, W, B, 0, t, M["Wood"], bevel=0.012)
    box("Left", 0, B, B, H - B, 0, t * 0.9, M["Wood"], bevel=0.012)
    box("Right", W - B, B, W, H - B, 0, t * 0.9, M["Wood"], bevel=0.012)
    # innere Zierleiste (heller), 1 px
    box("InTop", B, H - B - PX * 1.2, W - B, H - B, 0, t * 0.5, M["WoodDark"])
    box("InBot", B, B, W - B, B + PX * 1.2, 0, t * 0.5, M["WoodDark"])
    box("InL", B, B, B + PX * 1.2, H - B, 0, t * 0.5, M["WoodDark"])
    box("InR", W - B - PX * 1.2, B, W - B, H - B, 0, t * 0.5, M["WoodDark"])
    # Messingecken mit Nagel
    cs = (b + 3) * PX
    for i, (x, y) in enumerate(((0, 0), (W - cs, 0), (0, H - cs), (W - cs, H - cs))):
        box(f"Corner{i}", x, y, x + cs, y + cs, t, t + 0.01, M["Brass"], bevel=0.004)
        sphere(f"Nail{i}", (x + cs / 2, y + cs / 2, t + 0.012), PX * 1.4, M["Brass"])
    # Nägel entlang der langen Leisten
    n = int((w - 40) // 52)
    for k in range(1, n + 1):
        x = W * k / (n + 1)
        sphere(f"NT{k}", (x, H - B / 2, t + 0.004), PX * 1.1, M["Brass"])
        sphere(f"NB{k}", (x, B / 2, t + 0.004), PX * 1.1, M["Brass"])
    sc.render.filepath = os.path.join(out, "frame_00.png")
    bpy.ops.render.render(write_still=True)
    return {"size": [w, h], "border": b}


def do_plaque(o, out):
    w, h = map(int, o["plaque"].split("x"))
    sc = ui_scene(o, w, h)
    M = mats()
    W, H = w * PX, h * PX
    box("Plate", 0, 0, W, H, 0, 0.02, M["Brass"], bevel=0.012)
    for i, x in enumerate((PX * 4, W - PX * 4)):
        sphere(f"Rivet{i}", (x, H / 2, 0.022), PX * 1.2, M["WoodDark"])
    sc.render.filepath = os.path.join(out, "plaque_00.png")
    bpy.ops.render.render(write_still=True)
    return {"size": [w, h]}


def do_cursor(o, out):
    w, h = 14, 12
    sc = ui_scene(o, w, h)
    M = mats()
    # Paket: Quader mit Schnur, dreht sich um die senkrechte Bildachse
    piv = bpy.data.objects.new("Piv", None)
    S._link(piv)
    piv.location = (w * PX / 2, h * PX / 2, 0.0)
    parts = [box("Parcel", -0.04, -0.03, 0.04, 0.03, -0.025, 0.025, M["Parcel"], bevel=0.004),
             box("StrX", -0.0405, -0.004, 0.0405, 0.004, -0.0255, 0.0255, M["Shirt"]),
             box("StrY", -0.004, -0.0305, 0.004, 0.0305, -0.0255, 0.0255, M["Shirt"])]
    for p in parts:
        p.parent = piv
    n = 8
    for k in range(n):
        piv.rotation_euler = (math.radians(-25), 2 * math.pi * k / n, math.radians(8))
        sc.render.filepath = os.path.join(out, f"cursor_{k:02d}.png")
        bpy.ops.render.render(write_still=True)
    return {"size": [w, h], "frames": n, "fps": 10}


def main():
    o = parse()
    out = os.path.join(o["out"], "ui")
    os.makedirs(out, exist_ok=True)
    meta = {"frame": do_frame(o, out), "plaque": do_plaque(o, out), "cursor": do_cursor(o, out)}
    with open(os.path.join(out, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    print("fertig ui")


main()
