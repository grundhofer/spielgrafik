# -*- coding: utf-8 -*-
"""Hafenbild aus shared/3d/harbor.glb als Vorlage für die 32-Farben-Illustration (Ausweichweg ohne Bildmodell).

Aufruf (aus dem Projektordner):
  blender -b --factory-startup -P styles/amiga-illustration/blender/render_bg.py -- \
      --out styles/amiga-illustration/assets/raw/bg3d [--ss 4]

Kamera näher und tiefer als die Hauptkamera, damit der Dachs im 320x144-Bild etwa 41 px hoch ist:
Godot-Position (-2.5, 1.2, 9.0), 3° nach oben geneigt, vertikaler Bildwinkel 38,9° (f = 204 Zielpixel);
Laufweg des Dachses auf z = 4.0 (vorderes Pflaster), dort 40,8 px je Meter.
Ausgaben: shaded.png (EEVEE, Abendlicht), id.png (Workbench, flache Kennfarben je Material ohne
Kantenglättung, für Masken), camera.json (Projektion des Laufwegs in Zielpixel).
"""
import argparse
import json
import math
import os
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--glb", default=os.path.join(ROOT, "shared/3d/harbor.glb"))
    ap.add_argument("--ss", type=int, default=4)
    ap.add_argument("--samples", type=int, default=64)
    return ap.parse_args(argv)


A = parse_args()
W, H = 320, 144
F_PX = 204.0
CAM_G = (-2.5, 1.2, 9.0)        # Godot-Koordinaten
PITCH = 3.0
WALK_Z = 4.0


def hex_lin(h):
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return out


def g2b(p):
    return Vector((p[0], -p[2], p[1]))


ID_COLORS = {"Water": "#0000FF", "Glass": "#FFFF00", "Stone": "#808080", "StoneDark": "#404040",
             "Wood": "#A06030", "WoodDark": "#503018", "WhitePaint": "#FFFFFF", "RedPaint": "#FF0000",
             "Roof": "#304060", "Rope": "#C0A060", "Metal": "#202020", "Rock": "#706050", "Sand": "#E0C080",
             "Grass": "#40A040"}


def texture_materials():
    """Feine Unruhe in Farbe und Relief (Rauschen) für Stein, Holz, Fels, Dach: sonst sind die Flächen des
    Modells einfarbig und das Dithering hat nichts zu zeichnen."""
    amount = {"Stone": 0.35, "StoneDark": 0.35, "Rock": 0.45, "Wood": 0.3, "WoodDark": 0.3, "Roof": 0.25,
              "Sand": 0.25, "Grass": 0.35}
    for m in bpy.data.materials:
        if m.name not in amount or not m.use_nodes:
            continue
        nt = m.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            continue
        base = tuple(bsdf.inputs["Base Color"].default_value)
        noise = nt.nodes.new("ShaderNodeTexNoise")
        tc = nt.nodes.new("ShaderNodeTexCoord")
        nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
        noise.inputs["Scale"].default_value = 1.2 if m.name in ("Rock", "Grass", "Sand") else 2.5
        noise.inputs["Detail"].default_value = 6.0
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        k = amount[m.name]
        ramp.color_ramp.elements[0].color = (1 - k, 1 - k, 1 - k, 1)
        ramp.color_ramp.elements[1].color = (1 + k * 0.6, 1 + k * 0.6, 1 + k * 0.6, 1)
        ramp.color_ramp.elements[0].position = 0.3
        ramp.color_ramp.elements[1].position = 0.7
        nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        mix.inputs[6].default_value = base
        nt.links.new(ramp.outputs["Color"], mix.inputs[7])
        nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.35
        nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def setup():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=A.glb)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = W * A.ss, H * A.ss
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "Standard"
    world = bpy.data.worlds.new("Dusk")
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    cr = ramp.color_ramp
    cr.elements[0].position = 0.0
    cr.elements[0].color = (*hex_lin("#F08A3C"), 1)
    cr.elements[1].position = 0.32
    cr.elements[1].color = (*hex_lin("#1C1F4A"), 1)
    for pos, col in ((0.03, "#E07850"), (0.08, "#9A5A7A"), (0.16, "#4A3F78")):
        e = cr.elements.new(pos)
        e.color = (*hex_lin(col), 1)
    bg.inputs["Strength"].default_value = 1.0

    sun = bpy.data.lights.new("Sun", "SUN")
    sun.energy = 2.2
    sun.color = hex_lin("#FF9A60")
    sun.angle = math.radians(2)
    so = bpy.data.objects.new("Sun", sun)
    sc.collection.objects.link(so)
    so.rotation_euler = Vector((-0.45, 0.85, -0.18)).normalized().to_track_quat("-Z", "Y").to_euler()
    sky = bpy.data.lights.new("SkyFill", "SUN")
    sky.energy = 0.7
    sky.color = hex_lin("#7A86D8")
    sky.use_shadow = False
    ko = bpy.data.objects.new("SkyFill", sky)
    sc.collection.objects.link(ko)
    ko.rotation_euler = Vector((0.3, 0.4, -1.0)).normalized().to_track_quat("-Z", "Y").to_euler()

    def point(name, pos, energy, color="#FFB860", radius=0.05):
        ld = bpy.data.lights.new(name, "POINT")
        ld.energy = energy
        ld.color = hex_lin(color)
        ld.shadow_soft_size = radius
        o = bpy.data.objects.new(name, ld)
        sc.collection.objects.link(o)
        o.location = pos
        return o

    point("Lantern", bpy.data.objects["LanternLight"].matrix_world.translation, 80)
    point("Window", bpy.data.objects["CottageWindow"].matrix_world.translation + Vector((0, -0.4, 0)), 60)
    point("Lighthouse", bpy.data.objects["LighthouseLight"].matrix_world.translation, 900, radius=0.3)
    cd = bpy.data.cameras.new("Cam")
    cd.sensor_fit = "VERTICAL"
    cd.sensor_height = 24.0
    fov = 2 * math.atan((H / 2) / F_PX)
    cd.lens = 12.0 / math.tan(fov / 2)
    cd.clip_start = 0.1
    cd.clip_end = 3000.0
    co = bpy.data.objects.new("Cam", cd)
    sc.collection.objects.link(co)
    co.location = g2b(CAM_G)
    co.rotation_euler = (math.radians(90 + PITCH), 0, 0)
    sc.camera = co
    return sc, co


def main():
    sc, cam = setup()
    texture_materials()
    os.makedirs(A.out, exist_ok=True)
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = A.samples
    sc.render.filepath = os.path.join(A.out, "shaded.png")
    bpy.ops.render.render(write_still=True)
    # ID-Pass
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "FLAT"
    sc.display.shading.color_type = "MATERIAL"
    sc.display.render_aa = "OFF"
    for m in bpy.data.materials:
        if m.name in ID_COLORS:
            m.diffuse_color = (*hex_lin(ID_COLORS[m.name]), 1)
    sc.world.color = (0, 0, 0)
    sc.render.filepath = os.path.join(A.out, "id.png")
    bpy.ops.render.render(write_still=True)
    # Projektion: Laufweg, Lampen
    def proj(p):
        v = world_to_camera_view(sc, cam, g2b(p))
        return [round(v.x * W, 2), round((1 - v.y) * H, 2), round(v.z, 3)]
    info = {"camera_godot": CAM_G, "pitch_deg": PITCH, "f_px": F_PX, "size": [W, H], "walk_z": WALK_Z,
            "walk_points": {str(x): proj((x, 0, WALK_Z)) for x in (-8, -6, -4, -2, 0, 2, 4)},
            "badger_top": proj((-2.5, 1.011, WALK_Z)),
            "lamps": {n: proj(tuple(bpy.data.objects[n].matrix_world.translation[i] for i in (0, 2, 1)) and
                                (bpy.data.objects[n].matrix_world.translation.x,
                                 bpy.data.objects[n].matrix_world.translation.z,
                                 -bpy.data.objects[n].matrix_world.translation.y))
                      for n in ("LanternLight", "LighthouseLight", "CottageWindow", "ChimneySmoke")}}
    with open(os.path.join(A.out, "camera.json"), "w") as f:
        json.dump(info, f, indent=1)
    print("INFO", json.dumps(info))


main()
