# -*- coding: utf-8 -*-
"""Layout-Vorlage für den Hintergrund: harbor.glb aus der Szenenkamera dieses Eintrags, flache Farben mit einer
harten Lichtstufe und Freestyle-Kontur (Tonplatte). Das Bildmodell übermalt diese Vorlage („as if traced …“),
die 3D-Daten liefern dazu die genaue Lage von Laterne, Fenster, Schornstein, Leuchtfeuer und Laufweg.

Aufruf (aus dem Projektordner):
  blender -b --factory-startup -P styles/rotoskopie/blender/harbor_layout.py -- \
      --glb shared/3d/harbor.glb --out styles/rotoskopie/assets/ref/harbor_layout.png

Kamera (Godot): Position CAM, Blick entlang -Z, waagerecht, 16:9-Bild mit fov 42° vertikal (Keep Height).
Das Renderbild ist 1536×1024 (3:2, das Format des Bildmodells) mit demselben horizontalen Bildwinkel; das
16:9-Spielbild sind die Zeilen 160–1024 (unten bündig, oben 160 Zeilen zusätzlicher Himmel).
Schreibt neben das Bild <name>.json mit den Bildpunkten der Empties im 1280×720-Spielbild.
"""
import argparse, json, math, pathlib, sys

import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--glb", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--line", type=float, default=1.6)
ap.add_argument("--cam", default="-2.5,1.9,9.4", help="Kameraposition in Godot-Koordinaten")
ap.add_argument("--pitch", type=float, default=-1.0, help="Neigung in Grad (negativ = nach unten)")
a = ap.parse_args(argv)

CAM = tuple(float(v) for v in a.cam.split(","))          # Godot
W, H, TOP = 1536, 1024, 160       # Renderbild; 16:9-Ausschnitt = Zeilen TOP … H
TAN_H = math.tan(math.radians(21)) * 16 / 9
LIGHT = Vector((-0.55, -0.45, 0.70)).normalized()   # Blender: von links vorn oben

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=str(pathlib.Path(a.glb).resolve()))

# Flache Farben: Grundfarbe × (1 im Licht, 0,62 im Schatten), Glas leuchtet
for m in list(bpy.data.materials):
    nt = m.node_tree
    if nt is None:
        continue
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        continue
    base = list(bsdf.inputs["Base Color"].default_value)
    name = m.name.split(".")[0]
    nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(em.outputs[0], o.inputs[0])
    if name == "Glass":
        em.inputs["Color"].default_value = (1.0, 0.72, 0.30, 1)
        em.inputs["Strength"].default_value = 1.0
        continue
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    dot = nt.nodes.new("ShaderNodeVectorMath"); dot.operation = "DOT_PRODUCT"
    dot.inputs[1].default_value = LIGHT
    gt = nt.nodes.new("ShaderNodeMath"); gt.operation = "GREATER_THAN"; gt.inputs[1].default_value = 0.12
    mp = nt.nodes.new("ShaderNodeMapRange")
    mp.inputs["To Min"].default_value = 0.62
    mp.inputs["To Max"].default_value = 1.0
    mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    mul.inputs["A"].default_value = base
    nt.links.new(geo.outputs["Normal"], dot.inputs[0])
    nt.links.new(dot.outputs["Value"], gt.inputs[0])
    nt.links.new(gt.outputs[0], mp.inputs["Value"])
    nt.links.new(mp.outputs["Result"], mul.inputs["B"])
    nt.links.new(mul.outputs["Result"], em.inputs["Color"])

world = bpy.data.worlds.new("Sky")
sc.world = world
world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs["Color"].default_value = (0.42, 0.36, 0.45, 1)
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 16
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.render.resolution_percentage = 100
sc.render.film_transparent = False
sc.view_settings.view_transform = "Standard"
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGB"
sc.render.use_freestyle = True
sc.render.line_thickness_mode = "ABSOLUTE"
sc.render.line_thickness = a.line
vl = sc.view_layers[0]
vl.use_freestyle = True
fs = vl.freestyle_settings
fs.crease_angle = math.radians(140)
ls = fs.linesets[0] if len(fs.linesets) else fs.linesets.new("Ink")
ls.select_by_visibility = True
ls.select_by_edge_types = True
ls.select_silhouette = True
ls.select_border = True
ls.select_crease = True
ls.select_material_boundary = True
if ls.linestyle is None:
    ls.linestyle = bpy.data.linestyles.new("Ink")
ls.linestyle.color = (0.06, 0.04, 0.05)
ls.linestyle.thickness = a.line

cd = bpy.data.cameras.new("Cam")
cd.sensor_fit = "HORIZONTAL"
cd.sensor_width = 36.0
cd.lens = 18.0 / TAN_H
cd.shift_y = (H / 2 - (TOP + (H - TOP) / 2)) / W * -1     # Bildmitte des 16:9-Ausschnitts auf die Achse
cd.clip_start, cd.clip_end = 0.1, 3000.0
cam = bpy.data.objects.new("Cam", cd)
sc.collection.objects.link(cam)
sc.camera = cam
cam.location = Vector((CAM[0], -CAM[2], CAM[1]))
cam.rotation_euler = (math.pi / 2 + math.radians(a.pitch), 0, 0)
bpy.context.view_layer.update()


def game_px(p):
    """Blender-Weltpunkt -> Pixel im 1280×720-Spielbild."""
    v = world_to_camera_view(sc, cam, p)
    x, y = v.x * W, (1 - v.y) * H
    return [round(x * 1280 / W, 1), round((y - TOP) * 720 / (H - TOP), 1)]


marks = {}
for n in ["LanternLight", "LighthouseLight", "ChimneySmoke", "CottageWindow", "BoatA", "BoatB", "WalkStart",
          "WalkEnd"]:
    ob = bpy.data.objects.get(n)
    if ob is not None:
        marks[n] = game_px(ob.matrix_world.translation)
sc.render.filepath = str(pathlib.Path(a.out).resolve())
bpy.ops.render.render(write_still=True)
info = {"cam_godot": CAM, "pitch_deg": a.pitch, "fov_v_16_9": 42.0, "render": [W, H], "crop_rows": [TOP, H], "game": [1280, 720],
        "marks_game_px": marks}
pathlib.Path(a.out).with_suffix(".json").write_text(json.dumps(info, indent=1))
print("MARKS", json.dumps(marks))
