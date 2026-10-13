"""Dachs-Kurier als vorgerenderte Sprite-Bilder mit derselben Iso-Kamera wie die Karte (iso-vorgerendert).

Aufruf (aus dem Projektordner):
  blender -b --factory-startup -P styles/iso-vorgerendert/blender/render_badger.py -- --out <dir> [--only walk,stand,idle,wave]
          [--ss 4] [--samples 64]

Je Bild drei Pässe in einer Zelle von CELL Zielpixeln (ss-fach gerendert, Python verkleinert):
  <name>.png        Farbe (RGBA, 16 Bit, Standard-Ansicht), Licht wie die Karte (Sonne + Dämmerungshimmel)
  <name>_z.png      Tiefe entlang der Blickachse relativ zum Ankerpunkt: (d - d_anker) / 2,56 m + 0,5 (Raw, 16 Bit)
  <name>_sh.png     Schlagschatten auf der Bodenebene y = 0 (weiße Ebene, nur Sonne; Figur für die Kamera unsichtbar)
Der Ankerpunkt (Welt-Ursprung = Bodenpunkt des Dachses zu Zyklusbeginn) liegt in jeder Zelle auf der Pixelecke ANCHOR.
Laufen: Wurzelbewegung im Bild (Bild i um i/8 Schrittlänge versetzt), Godot verschiebt nur je Zyklus.
Richtungen nach Bildschirm-Kompass: S (zur Kamera), SW, W, NW, N, NE, E, SE.
Schreibt <out>/badger.json mit Schrittlänge, Zyklusvektor je Richtung und Bildliste.
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import isocam as ic  # noqa: E402

CELL = (112, 76)
ANCHOR = (36, 58)
DEPTH_RANGE = 2.56
DIRS = ["S", "SW", "W", "NW", "N", "NE", "E", "SE"]


def screen_dir_to_world(name):
    """Bildschirmrichtung -> Blickrichtung des Dachses in der Bodenebene (Blender-Vektor, normiert).
    Kamera-Rechts R und -oben U auf den Boden projiziert; S = zur Kamera."""
    r = Vector((ic.R.x, ic.R.y, 0)).normalized()
    up = Vector((ic.U.x, ic.U.y, 0)).normalized()     # Bildschirm-oben auf dem Boden = von der Kamera weg
    k = DIRS.index(name)
    ang = math.radians(45 * k)                        # S=0, SW=45 ... im Uhrzeigersinn über W, N, E
    # S = -up, W = -r, N = up, E = r
    v = -up * math.cos(ang) - r * math.sin(ang)
    return v.normalized()


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="walk,stand,idle,wave")
    ap.add_argument("--ss", type=int, default=4)
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--dirs", default=",".join(DIRS))
    ap.add_argument("--head-tilt", type=float, default=-28.0, help="Kopf nach hinten kippen (Grad), Gesicht zur Iso-Kamera")
    ap.add_argument("--head-scale", type=float, default=1.3)
    return ap.parse_args(argv)


def foot_info(meshes):
    dg = bpy.context.evaluated_depsgraph_get()
    res = {}
    for ob in meshes:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ev.matrix_world
        for side in "LR":
            vg = ob.vertex_groups.get("foot." + side)
            if vg is None:
                continue
            pts = [mw @ v.co for v in me.vertices if any(g.group == vg.index and g.weight > 0.5 for g in v.groups)]
            if pts:
                zmin = min(p.z for p in pts)
                sole = [p for p in pts if p.z < zmin + 0.01]
                res[side] = {"zmin": zmin, "x": sum(p.x for p in sole) / len(sole),
                             "y": sum(p.y for p in sole) / len(sole)}
        ev.to_mesh_clear()
    return res


def main():
    a = parse()
    os.makedirs(a.out, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = 30
    bpy.ops.import_scene.gltf(filepath=os.path.join(ic.ROOT, "shared", "3d", "badger.glb"))
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    root = arm
    while root.parent is not None:
        root = root.parent
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    scale = ic.SCENE["badger"]["scale"]
    root.scale = (scale, scale, scale)
    root.rotation_mode = "XYZ"

    # Kopf für die hohe Sicht: größer und nach hinten gekippt, sonst verdeckt die Mützenkrempe das Gesicht
    # (Verfahren aus styles/iso-pixel/blender/iso_render.py; Constraints wirken nach der Animation)
    ctl = bpy.data.objects.new("HeadCtl", None)
    sc.collection.objects.link(ctl)
    ctl.location = (1, 0, 0)
    pb = arm.pose.bones["head"]
    c = pb.constraints.new("TRANSFORM")
    c.target, c.target_space, c.owner_space = ctl, "WORLD", "LOCAL"
    c.map_from = "LOCATION"
    c.from_min_x, c.from_max_x = 0.0, 1.0
    c.map_to = "ROTATION"
    c.map_to_x_from = "X"
    c.to_min_x_rot, c.to_max_x_rot = 0.0, math.radians(a.head_tilt)
    c.mix_mode_rot = "AFTER"
    c2 = pb.constraints.new("TRANSFORM")
    c2.target, c2.target_space, c2.owner_space = ctl, "WORLD", "LOCAL"
    c2.map_from = "LOCATION"
    c2.from_min_x, c2.from_max_x = 0.0, 1.0
    c2.map_to = "SCALE"
    c2.map_to_x_from = c2.map_to_y_from = c2.map_to_z_from = "X"
    c2.to_min_x_scale = c2.to_min_y_scale = c2.to_min_z_scale = 1.0
    c2.to_max_x_scale = c2.to_max_y_scale = c2.to_max_z_scale = a.head_scale
    c2.mix_mode_scale = "MULTIPLY"

    # Materialien: glTF-Grundfarben bleiben (die Figur ist im Stil einfarbig modelliert), nur rauer
    for m in bpy.data.materials:
        if m.node_tree:
            for nd in m.node_tree.nodes:
                if nd.type == "BSDF_PRINCIPLED":
                    nd.inputs["Roughness"].default_value = max(nd.inputs["Roughness"].default_value, 0.6)
    world, bgn = ic.build_world()
    sun = ic.add_sun()

    # Bodenebene für den Schattenpass
    bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 0, 0))
    plane = bpy.context.active_object
    plane.name = "ShadowPlane"
    pm, nt = ic.new_material("R_ShadowPlane")
    ic.principled(nt, (1.0, 1.0, 1.0), 1.0, spec=0.0)
    plane.data.materials.append(pm)
    plane.hide_render = True

    s = ic.px_per_m()
    w, h = CELL
    # Kamera so, dass der Welt-Ursprung auf der Pixelecke ANCHOR liegt
    X0 = -ANCHOR[0] / s
    Yt = ANCHOR[1] / s
    cam = ic.setup_camera(sc, CELL, X0, Yt, s, a.ss, name="SpriteCam")
    d_anchor = ic.view_depth(Vector((0, 0, 0)), cam)

    ic.cycles_setup(sc, a.samples)
    sc.render.film_transparent = True
    sc.cycles.pixel_filter_type = "BOX"
    sc.cycles.filter_width = 1.0

    # Tiefenmaterial (relativ zum Anker)
    dm, nt = ic.new_material("R_DepthRel")
    camd = nt.node("ShaderNodeCameraData")
    v = nt.math("ADD", nt.math("DIVIDE", nt.math("SUBTRACT", camd.outputs["View Z Depth"], d_anchor),
                                DEPTH_RANGE), 0.5)
    em = nt.node("ShaderNodeEmission")
    comb = nt.node("ShaderNodeCombineColor")
    for i in range(3):
        nt.link(v, comb.inputs[i])
    nt.link(comb.outputs[0], em.inputs["Color"])
    em.inputs["Strength"].default_value = 1.0
    o = nt.node("ShaderNodeOutputMaterial")
    nt.link(em.outputs[0], o.inputs["Surface"])

    def set_action(nm):
        ad = arm.animation_data or arm.animation_data_create()
        act = next(x for x in bpy.data.actions if x.name == nm or x.name.startswith(nm + "_") or x.name.startswith(nm + "."))
        ad.action = act
        if getattr(ad, "action_slot", None) is None and len(act.slots):
            ad.action_slot = act.slots[0]

    def render_frame(name):
        # 1) Farbe
        sc.view_settings.view_transform = "Standard"
        sc.render.image_settings.file_format = "PNG"
        sc.render.image_settings.color_mode = "RGBA"
        sc.render.image_settings.color_depth = "8"
        bgn.inputs["Strength"].default_value = 0.9
        sun.hide_render = False
        sc.cycles.samples = a.samples
        sc.cycles.use_denoising = True
        sc.cycles.max_bounces = 6
        sc.render.filepath = os.path.join(a.out, name + ".png")
        bpy.ops.render.render(write_still=True)
        # 2) Tiefe
        bpy.context.view_layer.material_override = dm
        sc.view_settings.view_transform = "Raw"
        sc.cycles.samples = 1
        sc.cycles.use_denoising = False
        sc.cycles.max_bounces = 0
        sc.render.filepath = os.path.join(a.out, name + "_z.png")
        bpy.ops.render.render(write_still=True)
        bpy.context.view_layer.material_override = None
        # 3) Schatten auf der Ebene: nur Sonne, Figur für die Kamera unsichtbar
        plane.hide_render = False
        for mo in meshes:
            mo.visible_camera = False
        bgn.inputs["Strength"].default_value = 0.0
        sc.render.film_transparent = False
        sc.render.image_settings.color_mode = "RGB"
        sc.cycles.samples = 16
        sc.cycles.max_bounces = 1
        sc.render.filepath = os.path.join(a.out, name + "_sh.png")
        bpy.ops.render.render(write_still=True)
        plane.hide_render = True
        for mo in meshes:
            mo.visible_camera = True
        sc.render.film_transparent = True

    only = set(a.only.split(","))
    dirs = a.dirs.split(",")
    frames = []

    # Schrittlänge messen (Standfuß in der Walk-Schleife, Figur in +X)
    set_action("Walk")
    root.location = (0, 0, 0)
    root.rotation_euler = (0, 0, 0)
    feet = []
    for f in range(31):
        sc.frame_set(f)
        feet.append(foot_info(meshes))
    speeds = []
    for side in "LR":
        seq = [(f, feet[f][side]["x"]) for f in range(31) if side in feet[f] and feet[f][side]["zmin"] < 0.006 * scale]
        for (f0, x0), (f1, x1) in zip(seq, seq[1:]):
            if f1 == f0 + 1:
                speeds.append((x0 - x1) * 30.0)
    speeds.sort()
    stride = speeds[len(speeds) // 2] if speeds else 0.3667 * scale
    print("STRIDE m/cycle %.4f (n=%d, erwartet %.4f)" % (stride, len(speeds), 0.3667 * scale), flush=True)

    def cycle_px(fw):
        d3 = fw * stride
        return [d3.dot(ic.R) * s, -d3.dot(ic.U) * s]

    meta = {"cell": list(CELL), "anchor": list(ANCHOR), "px_per_m": s, "scale": scale, "stride_m": stride,
            "depth_range_m": DEPTH_RANGE, "dirs": DIRS, "cycle_px": {}, "frames": []}

    for dname in dirs:
        fw = screen_dir_to_world(dname)
        yaw = math.atan2(fw.y, fw.x)
        meta["cycle_px"][dname] = cycle_px(fw)
        root.rotation_euler = (0, 0, yaw)
        if "walk" in only:
            for i in range(8):
                set_action("Walk")
                f = 30.0 * i / 8
                sc.frame_set(int(f), subframe=f - int(f))
                root.location = fw * (stride * i / 8)
                bpy.context.view_layer.update()
                nm = "walk_%s_%d" % (dname, i)
                render_frame(nm)
                meta["frames"].append({"name": nm, "dir": dname, "anim": "Walk", "t": f / 30.0,
                                       "root_px": [x * i / 8 for x in meta["cycle_px"][dname]],
                                       "feet": {k: [v["x"], v["y"], v["zmin"]] for k, v in foot_info(meshes).items()}})
            root.location = (0, 0, 0)
        if "stand" in only:
            set_action("Idle")
            sc.frame_set(0)
            nm = "stand_%s" % dname
            render_frame(nm)
            meta["frames"].append({"name": nm, "dir": dname, "anim": "Idle", "t": 0.0})
    if "idle" in only or "wave" in only:
        fw = screen_dir_to_world("S")
        root.rotation_euler = (0, 0, math.atan2(fw.y, fw.x))
        root.location = (0, 0, 0)
    if "idle" in only:
        for i in range(12):
            set_action("Idle")
            f = 60.0 * i / 12
            sc.frame_set(int(f))
            nm = "idle_S_%02d" % i
            render_frame(nm)
            meta["frames"].append({"name": nm, "dir": "S", "anim": "Idle", "t": f / 30.0})
    if "wave" in only:
        for i in range(15):
            set_action("Wave")
            f = 3.0 * i
            sc.frame_set(int(f))
            nm = "wave_S_%02d" % i
            render_frame(nm)
            meta["frames"].append({"name": nm, "dir": "S", "anim": "Wave", "t": f / 30.0})
    json.dump(meta, open(os.path.join(a.out, "badger.json"), "w"), indent=1)
    print("RENDER_BADGER OK", len(meta["frames"]), flush=True)


main()
