"""Hintergrund vorrendern (Cycles, 4× Überabtastung).

blender -b --factory-startup -P blender/render_bg.py -- OUTDIR [--samples N] [--water-frames 12] [--only back,front,water]

Schreibt nach OUTDIR:
  back.png          ganze Szene ohne die Sprite-Objekte (Boot A, Fässer, Laternenpfahl, Kisten);
                    diese bleiben für Schatten und Spiegelungen in der Szene, nur unsichtbar für die Kamera
  front.png         nur Kai, Poller und Häuschen (RGBA): liegt in Godot vor dem Boot
  water_XX.png      Wasserband (Zeilen WATER_ROWS) mit Wellen in Schleife, Phase auf einem Kreis
  bg_meta.json      Kameradaten und Bildlage der Sprites
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Vector  # noqa: E402

import vs_scene as S  # noqa: E402

SPRITE_OBJS = ["BoatA", "Barrel1", "Barrel2", "LanternPost", "CrateStack"]
FRONT_OBJS = ["Quay", "Bollards", "Cottage"]
WATER_ROWS = (118, 166)       # Zielzeilen des Wasserbands (Horizont 126, Kaikante ≈ 158)


def parse():
    a = S.arg_list()
    out = a[0]
    opts = {"samples": 128, "water_frames": 12, "only": "back,front,water", "water_r": 0.55}
    i = 1
    while i < len(a):
        k = a[i].lstrip("-").replace("-", "_")
        opts[k] = type(opts[k])(a[i + 1])
        i += 2
    return out, opts


def children(name):
    ob = bpy.data.objects[name]
    return [ob] + list(ob.children_recursive)


def set_camera_visible(names, visible):
    for n in names:
        for o in children(n):
            o.visible_camera = visible


def main():
    out, o = parse()
    os.makedirs(out, exist_ok=True)
    S.reset()
    S.load_harbor()
    S.apply_materials()
    lamp = S.unique_glass("LighthouseLamp", 5.0)
    S.unique_glass("LanternGlass", 7.0)
    S.world_sky()
    S.scene_lights()
    cam = S.bg_camera()
    sc = S.render_setup("CYCLES", samples=o["samples"])
    sea_noise = bpy.data.materials["Water"].node_tree.nodes[bpy.data.materials["Water"]["noise_node"]]
    # Wasser in Schleife: Vector = (x, y, R cos θ), W = R sin θ → periodisch in θ
    mat = bpy.data.materials["Water"]
    nt = mat.node_tree
    mp = [n for n in nt.nodes if n.bl_idname == "ShaderNodeMapping"][0]
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(mp.outputs[0], sep.inputs[0])
    nt.links.new(sep.outputs["X"], comb.inputs["X"])
    nt.links.new(sep.outputs["Y"], comb.inputs["Y"])
    nt.links.new(comb.outputs[0], sea_noise.inputs["Vector"])

    def water_phase(theta):
        comb.inputs["Z"].default_value = o["water_r"] * math.cos(theta)
        sea_noise.inputs["W"].default_value = o["water_r"] * math.sin(theta)

    water_phase(0.0)
    set_camera_visible(SPRITE_OBJS, False)
    only = o["only"].split(",")
    meta = {"camera": {"x": S.CAM_X, "h": S.CAM_H, "d": S.CAM_D, "px_per_m": S.PX_PER_M,
                       "horizon_row": S.HORIZON_ROW, "lens_mm": cam.data.lens, "shift_y": cam.data.shift_y},
            "ss": S.SS, "water_rows": WATER_ROWS, "water_frames": o["water_frames"]}
    if "back" in only:
        sc.render.film_transparent = False
        sc.render.filepath = os.path.join(out, "back.png")
        bpy.ops.render.render(write_still=True)
    if "back" in only:
        # Himmelsmaske: 1 Strahl, Hintergrund durchsichtig (für Sterne)
        sc.render.film_transparent = True
        cy = sc.cycles
        keep = (cy.samples, cy.use_denoising)
        cy.samples, cy.use_denoising = 1, False
        sc.render.filepath = os.path.join(out, "skymask.png")
        bpy.ops.render.render(write_still=True)
        cy.samples, cy.use_denoising = keep
        sc.render.film_transparent = False
    if "front" in only:
        all_names = [ob.name for ob in bpy.data.objects if ob.type == "MESH" and ob.parent is None]
        hide = [n for n in all_names if n not in FRONT_OBJS]
        set_camera_visible(hide, False)
        sc.render.film_transparent = True
        sc.render.filepath = os.path.join(out, "front.png")
        bpy.ops.render.render(write_still=True)
        set_camera_visible(hide, True)
        set_camera_visible(SPRITE_OBJS, False)
        sc.render.film_transparent = False
    if "water" in only:
        r0, r1 = WATER_ROWS
        sc.render.use_border = True
        sc.render.use_crop_to_border = True
        sc.render.border_min_x, sc.render.border_max_x = 0.0, 1.0
        sc.render.border_min_y = 1.0 - r1 / S.H
        sc.render.border_max_y = 1.0 - r0 / S.H
        n = o["water_frames"]
        for k in range(n):
            water_phase(2 * math.pi * k / n)
            sc.render.filepath = os.path.join(out, f"water_{k:02d}.png")
            bpy.ops.render.render(write_still=True)
        sc.render.use_border = False
    # Bildlage einiger Punkte (Zielpixel) zur Kontrolle und für Godot
    pts = {}
    for name in ["LanternLight", "LighthouseLight", "CottageWindow", "BoatA", "Barrel1", "Barrel2",
                 "LanternPost", "CrateStack", "ChimneySmoke"]:
        p = bpy.data.objects[name].matrix_world.translation
        v = world_to_camera_view(sc, cam, p)
        pts[name] = [round(v.x * S.W, 2), round((1 - v.y) * S.H, 2), round(v.z, 3)]
    for x in (-8.0, -6.0, -4.0):
        v = world_to_camera_view(sc, cam, Vector((x, S.WALK_Y, 0.0)))
        pts[f"walk_{x}"] = [round(v.x * S.W, 2), round((1 - v.y) * S.H, 2), round(v.z, 3)]
    meta["points"] = pts
    with open(os.path.join(out, "bg_meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    print("BG fertig", json.dumps(pts))


main()
