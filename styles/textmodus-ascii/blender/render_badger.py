"""Rendert den Dachs aus shared/3d/badger.glb als Material-ID-Bilder (Vorlage für das Zeichen-Sprite).

    blender -b --factory-startup -P styles/textmodus-ascii/blender/render_badger.py -- <ausgabeordner>

Jedes Material bekommt eine eindeutige, flache Farbe (Workbench, flaches Licht, ohne Kantenglättung), damit
scripts/sprite_from_render.py je Zielpixel das häufigste Material auszählen kann. Ausgabe:
  side_walk_00.png … (Laufzyklus von der Seite, Figur nach +X = im Bild nach rechts)
  side_idle.png, front_idle.png
Orthografische Kamera, 1,4 m Bildhöhe, 700×700 Pixel.
"""
import math, pathlib, sys

import bpy

ROOT = pathlib.Path(__file__).resolve().parents[3]
OUT = pathlib.Path(sys.argv[sys.argv.index("--") + 1]) if "--" in sys.argv else pathlib.Path("/tmp/badger_ids")
OUT.mkdir(parents=True, exist_ok=True)

ID = {  # Material -> ID-Farbe (sRGB 0..1)
    "FurDark": (0.2, 0.2, 0.2), "FurLight": (1.0, 1.0, 1.0), "Cap": (0.0, 0.5, 0.0), "Brass": (1.0, 1.0, 0.0),
    "Vest": (0.0, 1.0, 0.0), "Shirt": (0.8, 0.8, 0.6), "Scarf": (1.0, 0.0, 0.0), "Satchel": (0.5, 0.25, 0.0),
    "Parcel": (1.0, 0.6, 0.2), "Nose": (0.0, 0.0, 0.0), "Eye": (0.0, 0.0, 1.0),
}

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(ROOT / "shared" / "3d" / "badger.glb"))
sc = bpy.context.scene
for m in bpy.data.materials:
    base = m.name.split(".")[0]
    if base in ID:
        c = ID[base]
        m.diffuse_color = (c[0] ** 2.2, c[1] ** 2.2, c[2] ** 2.2, 1.0)
    else:
        print("unbekanntes Material", m.name)

sc.render.engine = "BLENDER_WORKBENCH"
sc.display.shading.light = "FLAT"
sc.display.shading.color_type = "MATERIAL"
sc.display.render_aa = "OFF"
sc.display.shading.show_object_outline = False
sc.render.film_transparent = True
sc.view_settings.view_transform = "Standard"
sc.render.resolution_x = 700
sc.render.resolution_y = 700
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGBA"

cam_data = bpy.data.cameras.new("cam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = 1.4
cam = bpy.data.objects.new("cam", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam

arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
actions = {a.name: a for a in bpy.data.actions}
print("Aktionen:", list(actions))


def set_action(name):
    act = next(a for n, a in actions.items() if n.startswith(name))
    arm.animation_data_create()
    arm.animation_data.action = act
    try:  # Blender 4.4+: Aktionen mit Slots
        if act.slots:
            arm.animation_data.action_slot = act.slots[0]
    except AttributeError:
        pass
    return act


def side():
    cam.location = (0.0, -5.0, 0.62)          # vor der Figur (Blender -Y = Godot +Z), Blick nach +Y
    cam.rotation_euler = (math.radians(90), 0.0, 0.0)


def front():
    cam.location = (5.0, 0.0, 0.62)           # Figur blickt nach +X
    cam.rotation_euler = (math.radians(90), 0.0, math.radians(90))


def shoot(name):
    sc.render.filepath = str(OUT / name)
    bpy.ops.render.render(write_still=True)


fps = sc.render.fps
act = set_action("Walk")
f0, f1 = act.frame_range
n = int(sys.argv[sys.argv.index("--") + 2]) if len(sys.argv) > sys.argv.index("--") + 2 else 5
side()
for k in range(n):
    fr = f0 + (f1 - f0) * k / n
    sc.frame_set(int(math.floor(fr)), subframe=fr - math.floor(fr))
    shoot(f"side_walk_{k:02d}.png")
set_action("Idle")
sc.frame_set(int(act.frame_range[0]))
shoot("side_idle.png")
front()
shoot("front_idle.png")
print("Walk-Bereich", f0, f1, "fps", fps)
