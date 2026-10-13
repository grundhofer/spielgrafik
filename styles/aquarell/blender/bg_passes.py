# -*- coding: utf-8 -*-
"""Rendert den gemeinsamen Hafen (shared/3d/harbor.glb) aus der Kamera des Aquarell-Eintrags als Hilfsbilder für den
Hintergrund-Maler (tools/paint_bg.py). Die Geometrie bleibt unverändert; nur Kamera und Licht sind eigene.

Aufruf (aus dem Projektordner):
  blender -b --factory-startup -P styles/aquarell/blender/bg_passes.py -- \
      --glb shared/3d/harbor.glb --out styles/aquarell/assets/raw/bg_passes [--scale 2]

Kamera (Godot-Koordinaten): Position (CX, CH, CZ), Neigung PITCH Grad, fov 42 vertikal, 1280x720 (x scale).
Der Dachs läuft vorn auf z = WALK_Z; dort sind 167 px je Meter (Figur ca. 167 px hoch).
Ausgaben: color.png (EEVEE, Abendlicht, Himmel transparent), id.png (Workbench, je Objekt und Material eine
Kennfarbe, ohne Kantenglättung), depth.png (16 bit, Kameraabstand / 400 m), cam.json (Kennfarben-Tabelle und
die Bildpositionen der Lichtquellen, Rauchaustritt, Laufweg und Horizont, in 1280x720-Pixeln).
"""
import argparse, colorsys, json, math, os, sys

import bpy
from mathutils import Vector, Euler
from bpy_extras.object_utils import world_to_camera_view

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--glb", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--scale", type=int, default=2)
ap.add_argument("--cx", type=float, default=-2.6)
ap.add_argument("--ch", type=float, default=1.25)
ap.add_argument("--cz", type=float, default=11.2)
ap.add_argument("--pitch", type=float, default=1.0)
ap.add_argument("--walk-z", type=float, default=5.0)
ap.add_argument("--passes", default="color,depth,id")
A = ap.parse_args(argv)
W, H = 1280 * A.scale, 720 * A.scale


def g2b(x, y, z):          # Godot -> Blender
    return Vector((x, -z, y))


bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=os.path.abspath(A.glb))
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.render.resolution_percentage = 100
sc.render.film_transparent = True
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGBA"
sc.view_settings.view_transform = "Standard"
sc.eevee.taa_render_samples = 32

cam = bpy.data.cameras.new("Cam")
cam.sensor_fit = "VERTICAL"
cam.angle = math.radians(42.0)
cam.clip_start, cam.clip_end = 0.1, 3000
cam_ob = bpy.data.objects.new("Cam", cam)
sc.collection.objects.link(cam_ob)
sc.camera = cam_ob
cam_ob.location = g2b(A.cx, A.ch, A.cz)
cam_ob.rotation_euler = Euler((math.radians(90 + A.pitch), 0, 0), "XYZ")

# Abendlicht: tiefe Sonne hinten links am Horizont, violettes Himmelslicht, schwache Aufhellung von vorn links
world = bpy.data.worlds.new("W")
sc.world = world
if world.node_tree is None:
    world.use_nodes = True
bgn = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
bgn.inputs["Color"].default_value = (0.42, 0.40, 0.62, 1)
bgn.inputs["Strength"].default_value = 0.55


def sun(name, energy, color, direction, angle=3.0, shadow=True):
    l = bpy.data.lights.new(name, "SUN")
    l.energy, l.color, l.angle = energy, color, math.radians(angle)
    l.use_shadow = shadow
    o = bpy.data.objects.new(name, l)
    sc.collection.objects.link(o)
    o.rotation_euler = Vector(direction).normalized().to_track_quat("-Z", "Y").to_euler()
    return o


# Richtungen in Blender-Koordinaten (Strahlrichtung): Sonne steht hinten (+Y) links (-X), 9° hoch
sun("Sun", 2.2, (1.0, 0.62, 0.36), (0.45, -1.0, -0.16), angle=2.0)
sun("Fill", 0.55, (0.80, 0.82, 1.0), (0.5, 1.0, -0.8), angle=10.0, shadow=False)


def point(name, energy, color, pos, radius=0.1):
    l = bpy.data.lights.new(name, "POINT")
    l.energy, l.color, l.shadow_soft_size = energy, color, radius
    o = bpy.data.objects.new(name, l)
    sc.collection.objects.link(o)
    o.location = pos
    return o


objs = {o.name: o for o in bpy.data.objects}


def wpos(name):
    return objs[name].matrix_world.translation.copy()


point("LanternPt", 60.0, (1.0, 0.62, 0.30), wpos("LanternLight"))
point("WindowPt", 40.0, (1.0, 0.60, 0.30), wpos("CottageWindow") + Vector((0, -0.6, 0)))

# Spiegelungen auf dem Wasser: ebene Lichtsonde auf der Wasserlinie
try:
    pr = bpy.data.lightprobes.new("Mirror", "PLANE")
    po = bpy.data.objects.new("Mirror", pr)
    sc.collection.objects.link(po)
    po.location = Vector((0, 15, -0.8))
    po.scale = (60, 40, 1)
except Exception as e:      # ältere Namen
    print("WARN probe", e)
for m in bpy.data.materials:
    if m.name == "Water" and m.node_tree:
        b = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if b:
            b.inputs["Roughness"].default_value = 0.08

os.makedirs(A.out, exist_ok=True)


def render(name):
    sc.render.filepath = os.path.join(os.path.abspath(A.out), name)
    bpy.ops.render.render(write_still=True)


# --- Bildpositionen ---------------------------------------------------------------------------------------
bpy.context.view_layer.update()


def to_px(p):
    v = world_to_camera_view(sc, cam_ob, p)
    return [round(v.x * 1280, 1), round((1 - v.y) * 720, 1)]


info = {"camera_godot": {"pos": [A.cx, A.ch, A.cz], "pitch_deg_up": A.pitch, "fov": 42.0}, "walk_z": A.walk_z}
pts = {k: to_px(wpos(k)) for k in ("LanternLight", "LighthouseLight", "ChimneySmoke", "CottageWindow")}
pts["walk_left"] = to_px(g2b(-8, 0.012, A.walk_z))
pts["walk_right"] = to_px(g2b(4, 0.012, A.walk_z))
pts["horizon_far"] = to_px(g2b(A.cx, 0, -2000))
for b in ("BoatA", "BoatB"):
    pts[b] = to_px(wpos(b))
d = (cam_ob.location - g2b(0, 0, A.walk_z)).length
info["px_per_m_walk"] = round(720 / (2 * abs(A.cz - A.walk_z) * math.tan(math.radians(21))), 2)
info["points"] = pts
print("POINTS", pts, info["px_per_m_walk"])

passes = A.passes.split(",")
if "color" in passes:
    sc.render.engine = "BLENDER_EEVEE"
    render("color.png")

if "depth" in passes:
    m = bpy.data.materials.new("PassDepth")
    if m.node_tree is None:
        m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    camd = nt.nodes.new("ShaderNodeCameraData")
    div = nt.nodes.new("ShaderNodeMath")
    div.operation = "DIVIDE"
    div.inputs[1].default_value = 400.0
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(camd.outputs["View Distance"], div.inputs[0])
    nt.links.new(div.outputs[0], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    bpy.context.view_layer.material_override = m
    sc.render.image_settings.color_depth = "16"
    sc.view_settings.view_transform = "Raw" if "Raw" in [i.identifier for i in
                                                         sc.view_settings.bl_rna.properties["view_transform"].enum_items] else "Standard"
    sc.eevee.taa_render_samples = 1
    render("depth.png")
    bpy.context.view_layer.material_override = None
    sc.render.image_settings.color_depth = "8"
    sc.view_settings.view_transform = "Standard"

if "id" in passes:
    # je (Objekt, Materialplatz) eine eigene Materialkopie mit Kennfarbe
    table = {}
    k = 0
    for ob in sorted([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: o.name):
        for slot in ob.material_slots:
            if slot.material is None:
                continue
            k += 1
            h = (k * 0.61803398875) % 1.0
            s = 0.55 + 0.45 * ((k * 7) % 5) / 4
            v = 0.45 + 0.55 * ((k * 3) % 4) / 3
            col = colorsys.hsv_to_rgb(h, s, v)
            orig = slot.material.name
            mc = slot.material.copy()
            mc.diffuse_color = (*col, 1)
            slot.link = "OBJECT"
            slot.material = mc
            table[f"{ob.name}/{orig}"] = [round(c, 5) for c in col]
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "FLAT"
    sc.display.shading.color_type = "MATERIAL"
    sc.display.render_aa = "OFF"
    render("id.png")
    info["ids"] = table

with open(os.path.join(A.out, "cam.json"), "w") as f:
    json.dump(info, f, indent=1)
print("OK")
