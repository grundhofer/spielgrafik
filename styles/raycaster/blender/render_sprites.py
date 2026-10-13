# -*- coding: utf-8 -*-
"""Rendert die Sprite-Vorlagen für den Raycaster-Eintrag aus den gemeinsamen 3D-Modellen.

Wie die Monster der Sektor-Shooter (Modelle fotografiert und digitalisiert): Das Modell steht fest, wird
in 45°-Schritten gedreht, Kamera und Licht bleiben stehen. Je Bild zwei Durchgänge:
  <name>_shade.png  EEVEE mit Licht (für die Helligkeit innerhalb eines Materials)
  <name>_id.png     jedes Material als flache Emissionsfarbe, ohne Kantenglättung (Material je Pixel)
Die Bilder sind SUPER-fach größer als das Ziel; scripts/build_sprites.py verkleinert sie per
Mehrheitsentscheid auf das Texelraster und rastet sie in die 256er-Palette ein.

Aufruf (aus dem Projektordner):
  blender -b --factory-startup -P styles/raycaster/blender/render_sprites.py -- --out <ordner>
      [--only badger|props] [--scale 32] [--super 8]
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="render_sprites.py")
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="badger,props")
    ap.add_argument("--scale", type=float, default=32.0, help="Texel je Meter im Ziel")
    ap.add_argument("--super", type=int, default=8, help="Überabtastung je Texel")
    ap.add_argument("--elev", type=float, default=8.0, help="Kamerahöhe in Grad über der Waagrechten")
    ap.add_argument("--samples", type=int, default=16)
    return ap.parse_args(argv)


ARGS = parse_args()
OUT = os.path.abspath(ARGS.out)
os.makedirs(OUT, exist_ok=True)

# Material -> ID-Farbe (sRGB); build_sprites.py ordnet die Farben wieder den Namen zu.
ID_COLORS = {
    "FurDark": (40, 40, 40), "FurLight": (255, 255, 255), "Cap": (0, 160, 0), "Brass": (255, 200, 0),
    "Vest": (0, 90, 40), "Shirt": (255, 230, 170), "Scarf": (230, 0, 0), "Satchel": (140, 70, 0),
    "Parcel": (220, 150, 80), "Nose": (0, 0, 0), "Eye": (0, 0, 255),
    "Wood": (160, 100, 50), "WoodDark": (90, 50, 20), "Metal": (60, 60, 90), "Rope": (200, 180, 120),
    "StoneDark": (100, 100, 100), "Glass": (255, 255, 0), "String": (250, 240, 200),
}


def lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def aim(ob, direction):
    ob.rotation_euler = direction.normalized().to_track_quat("-Z", "Y").to_euler()


def base_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = 30
    return sc


def setup_render(sc, w, h, cam_center_z, ortho_h):
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    world = bpy.data.worlds.get("SpriteWorld") or bpy.data.worlds.new("SpriteWorld")
    sc.world = world
    if world.node_tree is None:
        world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (lin(150), lin(150), lin(160), 1)
    bg.inputs["Strength"].default_value = 0.55
    cam = bpy.data.cameras.new("SpriteCam")
    cam.type = "ORTHO"
    cam.sensor_fit = "VERTICAL"
    cam.ortho_scale = ortho_h
    cam_ob = link(bpy.data.objects.new("SpriteCam", cam))
    e = math.radians(ARGS.elev)
    # Kamera blickt von -Y nach +Y, leicht von oben; das Ziel liegt auf der Mittelachse
    tgt = Vector((0, 0, cam_center_z))
    pos = tgt + Vector((0, -20 * math.cos(e), 20 * math.sin(e)))
    cam_ob.location = pos
    aim(cam_ob, tgt - pos)
    sc.camera = cam_ob
    # Licht fest zur Kamera: Hauptlicht von links oben vorn, schwaches Gegenlicht rechts
    fwd = (tgt - pos).normalized()
    right = fwd.cross(Vector((0, 0, 1))).normalized()
    key = bpy.data.lights.new("Key", "SUN")
    key.energy = 3.2
    key.angle = math.radians(3)
    key_ob = link(bpy.data.objects.new("Key", key))
    aim(key_ob, fwd + Vector((0, 0, -0.9)) + right * 0.75)
    fill = bpy.data.lights.new("Fill", "SUN")
    fill.energy = 0.8
    fill.use_shadow = False
    fill_ob = link(bpy.data.objects.new("Fill", fill))
    aim(fill_ob, fwd + Vector((0, 0, -0.1)) - right * 0.9)
    return cam_ob


def projected_origin(sc, cam_ob, point=Vector((0, 0, 0))):
    """Pixelposition (x, y von oben) eines Weltpunkts im Ortho-Bild."""
    from bpy_extras.object_utils import world_to_camera_view
    co = world_to_camera_view(sc, cam_ob, point)
    return co.x * sc.render.resolution_x, (1 - co.y) * sc.render.resolution_y


def id_material(name, rgb):
    m = bpy.data.materials.new("ID_" + name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (lin(rgb[0]), lin(rgb[1]), lin(rgb[2]), 1)
    em.inputs["Strength"].default_value = 1.0
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], out.inputs[0])
    return m


def base_name(mat_name):
    for k in ID_COLORS:
        if mat_name == k or mat_name.startswith(k + "."):
            return k
    return None


class MatSwap:
    """Tauscht alle Materialien der Meshes gegen ID-Emission und zurück."""

    def __init__(self, meshes):
        self.meshes = meshes
        self.orig = {ob.name: [s.material for s in ob.material_slots] for ob in meshes}
        self.ids = {}
        missing = set()
        for ob in meshes:
            for s in ob.material_slots:
                if s.material is None:
                    continue
                b = base_name(s.material.name)
                if b is None:
                    missing.add(s.material.name)
                    continue
                if b not in self.ids:
                    self.ids[b] = id_material(b, ID_COLORS[b])
        if missing:
            raise RuntimeError("Materialien ohne ID-Farbe: %s" % sorted(missing))

    def to_id(self):
        for ob in self.meshes:
            for s in ob.material_slots:
                if s.material is not None:
                    s.material = self.ids[base_name(s.material.name)]

    def restore(self):
        for ob in self.meshes:
            for s, m in zip(ob.material_slots, self.orig[ob.name]):
                s.material = m


def render(sc, path, samples):
    sc.eevee.taa_render_samples = samples
    sc.render.filter_size = 1.5 if samples > 1 else 0.01
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def set_action(arm, name):
    ad = arm.animation_data or arm.animation_data_create()
    for tr in list(ad.nla_tracks):
        ad.nla_tracks.remove(tr)
    act = next((a for a in bpy.data.actions if a.name == name or a.name.startswith(name + "_")
                or a.name.startswith(name + ".")), None)
    if act is None:
        raise RuntimeError(f"Animation {name} fehlt: {[a.name for a in bpy.data.actions]}")
    ad.action = act
    if getattr(ad, "action_slot", None) is None and len(act.slots):
        ad.action_slot = act.slots[0]
    return act


def bone_world(arm, bone):
    pb = arm.pose.bones[bone]
    return arm.matrix_world @ pb.tail


# ---------------------------------------------------------------------------------------------
# Dachs: 8 Blickwinkel x (4 Lauf + 1 Stand + 2 Winken)

def badger():
    sc = base_scene()
    bpy.ops.import_scene.gltf(filepath=os.path.join(ROOT, "shared/3d/badger.glb"))
    sc = bpy.context.scene
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    top = arm  # Wurzelobjekt drehen (Import legt evtl. ein Eltern-Empty an)
    while top.parent is not None:
        top = top.parent

    # Leinwand im Ziel: 40 x 46 Texel, Fußpunkt bei (20, 43)
    S, K = ARGS.scale, ARGS.super
    cw, ch, ox, oy = 40, 46, 20, 43
    w, h = cw * K, ch * K
    ortho_h = ch / S                      # Meter, die die Bildhöhe abdeckt
    # Kamera so legen, dass der Fußpunkt auf (ox, oy) fällt: Mitte der Leinwand in Metern über dem Boden
    e = math.radians(ARGS.elev)
    center_z = (oy - ch / 2) / S / math.cos(e)
    cam_ob = setup_render(sc, w, h, center_z, ortho_h)
    px, py = projected_origin(sc, cam_ob)
    swap = MatSwap(meshes)

    # Schlüsselposen
    poses = []
    walk = set_action(arm, "Walk")
    f0 = walk.frame_range[0]
    for i, ph in enumerate((0.0, 0.25, 0.5, 0.75)):   # A: linke Ferse setzt auf, C: rechte
        poses.append(("walk%d" % i, "Walk", f0 + ph * 30.0))
    poses.append(("idle0", "Idle", 0.0))
    # Winken: Extrempunkte der Hand zwischen 0,4 und 1,1 s suchen (linke Hand, quer zur Blickrichtung)
    wave = set_action(arm, "Wave")
    wf0 = wave.frame_range[0]
    xs = []
    for f in range(int(wf0 + 12), int(wf0 + 34)):
        sc.frame_set(f)
        p = bone_world(arm, "hand.L")
        xs.append((f, p.x, p.z))
    fa = min(xs, key=lambda r: r[1])[0]
    fb = max(xs, key=lambda r: r[1])[0]
    poses.append(("wave0", "Wave", float(min(fa, fb))))
    poses.append(("wave1", "Wave", float(max(fa, fb))))
    meta = {"canvas": [cw, ch], "origin": [ox, oy], "scale": S, "super": K, "elev": ARGS.elev,
            "origin_px_render": [px, py], "poses": [], "wave_hand_x": xs}

    for name, action, frame in poses:
        set_action(arm, action)
        fi = int(math.floor(frame))
        sc.frame_set(fi, subframe=frame - fi)
        for rot in range(8):
            # Blickwinkel rot: Richtung zur Kamera = Blickrichtung der Figur um rot*45° gedreht (gegen den
            # Uhrzeigersinn von oben). Kamera liegt bei -Y; Figur blickt in Ruhe nach +X.
            a = rot * 45.0
            top.rotation_mode = "XYZ"
            top.rotation_euler = (top.rotation_euler.x, top.rotation_euler.y, math.radians(-90.0 - a))
            bpy.context.view_layer.update()
            base = os.path.join(OUT, f"badger_{name}_r{rot}")
            swap.restore()
            render(sc, base + "_shade.png", ARGS.samples)
            swap.to_id()
            render(sc, base + "_id.png", 1)
            swap.restore()
        feet = {}
        top.rotation_euler = (top.rotation_euler.x, top.rotation_euler.y, 0.0)
        bpy.context.view_layer.update()
        for bn in ("foot.L", "foot.R"):
            h = arm.matrix_world @ arm.pose.bones[bn].head
            feet[bn] = [round(h.x, 4), round(h.z, 4)]     # Fußgelenk: x = Blickrichtung, z = Höhe
        meta["poses"].append({"name": name, "action": action, "frame": frame, "ankle": feet})
        print("SPRITE", name)
    with open(os.path.join(OUT, "badger_meta.json"), "w") as f:
        json.dump(meta, f, indent=1)


# ---------------------------------------------------------------------------------------------
# Requisiten aus harbor.glb: nur eine Ansicht (wie Dekorationen der Zeit, immer zur Kamera)

PROPS = {
    # name: (Objekte, Leinwand w, h, Fußpunkt x, y, Drehung in Grad)
    "barrel": (["Barrel1"], 28, 34, 14, 32, 0.0),
    "rope": (["RopeCoil"], 30, 14, 15, 12, 0.0),
    "bollard": (["Bollards"], 16, 22, 8, 20, 0.0),
    "lanternpost": (["LanternPost", "LanternGlass"], 34, 84, 26, 81, 0.0),
}


def props():
    for pname, (objs, cw, ch, ox, oy, rot) in PROPS.items():
        sc = base_scene()
        bpy.ops.import_scene.gltf(filepath=os.path.join(ROOT, "shared/3d/harbor.glb"))
        sc = bpy.context.scene
        keep = set(objs)
        for ob in list(bpy.data.objects):
            if ob.type == "MESH" and ob.name not in keep:
                bpy.data.objects.remove(ob, do_unlink=True)
        meshes = [o for o in bpy.data.objects if o.type == "MESH"]
        # Mittelpunkt der Grundfläche auf den Ursprung schieben
        root = bpy.data.objects[objs[0]]
        if pname == "bollard":
            # drei Poller in einem Objekt: nur den mittleren behalten (Eckpunkte mit |x| > 1 m löschen)
            import bmesh
            bm = bmesh.new()
            bm.from_mesh(root.data)
            mw = root.matrix_world
            xs = sorted({round((mw @ v.co).x, 1) for v in bm.verts})
            centers = []
            for v in bm.verts:
                centers.append((mw @ v.co).x)
            cx = sorted(centers)[len(centers) // 2]
            dele = [v for v in bm.verts if abs((mw @ v.co).x - cx) > 0.6]
            bmesh.ops.delete(bm, geom=dele, context="VERTS")
            bm.to_mesh(root.data)
            bm.free()
        bpy.context.view_layer.update()
        pts = []
        for ob in meshes:
            for v in ob.data.vertices:
                pts.append(ob.matrix_world @ v.co)
        minx = min(p.x for p in pts); maxx = max(p.x for p in pts)
        miny = min(p.y for p in pts); maxy = max(p.y for p in pts)
        minz = min(p.z for p in pts)
        if pname == "lanternpost":
            # Fußpunkt = Mitte des Pfahls (höchster Punkt ist der Pfahl selbst)
            top_z = max(p.z for p in pts)
            post = [p for p in pts if p.z > top_z - 0.05]
            cx = sum(p.x for p in post) / len(post)
            cy = sum(p.y for p in post) / len(post)
        else:
            cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
        for ob in meshes:
            if ob.parent is None or ob.parent.name not in keep:
                ob.location = ob.location - Vector((cx, cy, minz))
        bpy.context.view_layer.update()
        S, K = ARGS.scale, ARGS.super
        e = math.radians(ARGS.elev)
        center_z = (oy - ch / 2) / S / math.cos(e)
        # waagrechte Lage: Fußpunkt bei ox statt Mitte -> Kamera seitlich verschieben
        cam_ob = setup_render(sc, cw * K, ch * K, center_z, ch / S)
        shift = (cw / 2 - ox) / S
        cam_ob.location.x += shift
        bpy.context.view_layer.update()
        for ob in meshes:
            ob.rotation_euler.z += math.radians(rot)
        swap = MatSwap(meshes)
        base = os.path.join(OUT, f"prop_{pname}")
        render(sc, base + "_shade.png", ARGS.samples)
        swap.to_id()
        render(sc, base + "_id.png", 1)
        swap.restore()
        with open(base + "_meta.json", "w") as f:
            json.dump({"canvas": [cw, ch], "origin": [ox, oy], "scale": S, "super": K}, f)
        print("SPRITE", pname)


if "badger" in ARGS.only:
    badger()
if "props" in ARGS.only:
    props()
print("FERTIG", OUT)
