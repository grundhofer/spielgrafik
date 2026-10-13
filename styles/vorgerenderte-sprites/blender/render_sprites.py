"""Sprites vorrendern (Cycles, 4× Überabtastung, durchsichtiger Hintergrund).

blender -b --factory-startup -P blender/render_sprites.py -- OUTDIR GRUPPE [--samples N]

Gruppen:
  badger    Dachs (orthografisch, PX_PER_M): walk (8 Bilder, Vorschub im Bild), stand, turn (O, SO, S),
            wave (23 Bilder), idle (30 Bilder, von vorn); dazu je Bild ein Schattenbild
  dirs      Dachs-Laufzyklus auf der Stelle in 8 Richtungen (8 × 8 Bilder) – Bogen für spätere Spiele
  boat      Boot A schaukelt (30 Bilder, Szenenkamera, an seiner Stelle im Bild)
  lantern   Laternenpfahl mit 4 Helligkeiten des Glases (Szenenkamera)
  props     Fässer und Kistenstapel (Szenenkamera)
  beam      Lichtkegel des Leuchtfeuers (24 Bilder je Umdrehung, additiv, Szenenkamera)
  cursor    Paket als drehender Zeiger für die Textbox (8 Bilder)
  frame     Holzrahmen der Textbox (9-Teile-Vorlage)
Jede Gruppe schreibt Einzelbilder <gruppe>/<anim>_NN.png und <gruppe>/meta.json.
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

CELL_W, CELL_H = 64, 64      # Zelle je Dachsbild in Zielpixeln
ORIGIN_COL, ORIGIN_ROW = 20, 60   # Wurzel des Dachses (Boden zwischen den Füßen) in der Zelle
SPRITE_FPS = 15
WALK_FRAMES = 8              # 8 Bilder je Zyklus bei 15 Bildern/s → speed_scale 1,875, 17 px je Zyklus
WALK_PHASE = 0.4             # Bild k zeigt Zyklusphase (k + 0,4)/8: Bild 2 und 6 = Durchgang
STEP_M = 0.367               # Weg je Zyklus (Walk dauert 1,0 s bei 0,367 m/s)


def parse():
    a = S.arg_list()
    out, group = a[0], a[1]
    opts = {"samples": 64, "anims": "walk,stand,turn,wave,idle"}
    i = 2
    while i < len(a):
        k = a[i].lstrip("-").replace("-", "_")
        opts[k] = type(opts.get(k, ""))(a[i + 1]) if k in opts else a[i + 1]
        i += 2
    return out, group, opts


def save(sc, path):
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


# ------------------------------------------------------------------------------------------
# Dachs
# ------------------------------------------------------------------------------------------
def badger_scene(samples):
    S.reset()
    arm, objs = S.load_badger()
    S.apply_materials()
    S.world_sky(strength=0.6, clouds=False)
    S.sprite_lights()
    sc = S.render_setup("CYCLES", samples=samples, transparent=True, w=CELL_W, h=CELL_H)
    # Schattenfänger auf dem Kai
    bpy.ops.mesh.primitive_plane_add(size=12, location=(0, S.WALK_Y, 0.0))
    catcher = bpy.context.active_object
    catcher.name = "Boden"
    catcher.is_shadow_catcher = True
    catcher.visible_camera = True
    meshes = [o for o in objs if o.type == "MESH" and not o.name.startswith("Icosphere")]
    return sc, arm, meshes, catcher


def cell_camera(root_x0):
    """Zelle so legen, dass die Wurzel bei root_x0 genau auf Spalte ORIGIN_COL, Zeile ORIGIN_ROW liegt."""
    left = root_x0 - ORIGIN_COL / S.PX_PER_M
    bottom = -(CELL_H - ORIGIN_ROW) / S.PX_PER_M
    return S.sprite_camera(left + CELL_W / S.PX_PER_M / 2, bottom, CELL_W, CELL_H)


SHADOW_W, SHADOW_H, SHADOW_ROW = 64, 48, 8   # Schattenzelle: Wurzel auf (ORIGIN_COL, SHADOW_ROW)


def shadow_camera(root_x0):
    """Orthografisch, um den Blickwinkel der Szenenkamera auf den Laufweg geneigt (atan(h/d)),
    damit der Boden so gestaucht erscheint wie im Hintergrund."""
    p = math.atan2(S.CAM_H, S.CAM_D)
    cd = bpy.data.cameras.new("ShadowCam")
    cd.type = "ORTHO"
    cd.sensor_fit = "HORIZONTAL"
    cd.ortho_scale = SHADOW_W / S.PX_PER_M
    co = S._link(bpy.data.objects.new("ShadowCam", cd))
    co.rotation_euler = (math.radians(90) - p, 0, 0)
    # Bildmitte relativ zur Wurzel: dx = (W/2 - col)/ppm, dy_bild = (row - H/2)/ppm (nach unten)
    right = Vector((1, 0, 0))
    up = co.rotation_euler.to_matrix() @ Vector((0, 1, 0))
    fwd = co.rotation_euler.to_matrix() @ Vector((0, 0, -1))
    root = Vector((root_x0, S.WALK_Y, 0.0))
    centre = root + right * ((SHADOW_W / 2 - ORIGIN_COL) / S.PX_PER_M) - up * ((SHADOW_H / 2 - SHADOW_ROW) / S.PX_PER_M)
    co.location = centre - fwd * 30.0
    cd.clip_start, cd.clip_end = 0.1, 100.0
    return co


def render_pair(sc, meshes, catcher, path_base, cams=None, ids=None):
    """Figur ohne Schatten, Kennungsbild, dann nur den Schatten (Figur für die Kamera unsichtbar)."""
    cam, scam = cams
    catcher.hide_render = True
    for m in meshes:
        m.visible_camera = True
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = CELL_W * S.SS, CELL_H * S.SS
    save(sc, path_base + ".png")
    if ids is not None:
        ids.render(sc, path_base + "_id.png")
    catcher.hide_render = False
    for m in meshes:
        m.visible_camera = False
    sc.camera = scam
    sc.render.resolution_x, sc.render.resolution_y = SHADOW_W * S.SS, SHADOW_H * S.SS
    save(sc, path_base + "_shadow.png")
    for m in meshes:
        m.visible_camera = True


def do_badger(out, o):
    sc, arm, meshes, catcher = badger_scene(o["samples"])
    os.makedirs(out, exist_ok=True)
    meta = {"cell": [CELL_W, CELL_H], "origin": [ORIGIN_COL, ORIGIN_ROW], "px_per_m": S.PX_PER_M,
            "fps": SPRITE_FPS, "anims": {}}
    x0 = 0.0
    cam = cell_camera(x0)
    scam = shadow_camera(x0)
    ids = S.IdSwap(meshes)
    meta["shadow"] = {"cell": [SHADOW_W, SHADOW_H], "origin": [ORIGIN_COL, SHADOW_ROW]}

    want = set(o["anims"].split(","))

    def frame(anim, idx, action, t, rot_deg=0.0, root_dx=0.0):
        if anim not in want:
            return
        arm.location = (x0 + root_dx, S.WALK_Y, 0.0)
        arm.rotation_euler = (0.0, 0.0, math.radians(rot_deg))
        S.set_action(arm, action, t)
        render_pair(sc, meshes, catcher, os.path.join(out, f"{anim}_{idx:02d}"), (cam, scam), ids)

    # Laufen nach rechts mit Vorschub im Bild: Standfuß steht im Bild still
    walk = []
    for k in range(WALK_FRAMES):
        ph = (k + WALK_PHASE) / WALK_FRAMES
        frame("walk", k, "Walk", ph * 1.0, 0.0, STEP_M * ph)
        walk.append({"phase": ph, "dx_px": STEP_M * ph * S.PX_PER_M})
    meta["anims"]["walk"] = {"frames": WALK_FRAMES, "fps": SPRITE_FPS, "loop": True,
                             "advance_px": round(STEP_M * S.PX_PER_M, 3), "detail": walk}
    # Stehen nach dem Durchgang (Bild 6 = Phase 0,8): Wurzel an derselben Stelle
    stand_dx = STEP_M * (6 + WALK_PHASE) / WALK_FRAMES
    frame("stand", 0, "Idle", 0.0, 0.0, stand_dx)
    meta["anims"]["stand"] = {"frames": 1, "root_dx_px": round(stand_dx * S.PX_PER_M, 3), "after_walk_frame": 6}
    # Drehen in 45°-Schritten (8-Richtungs-Raster): O → SO → S
    for i, a in enumerate((-45.0, -90.0)):
        frame("turn", i, "Idle", 0.0, a, stand_dx)
    meta["anims"]["turn"] = {"frames": 2, "fps": 10, "angles": [-45, -90], "root_dx_px": round(stand_dx * S.PX_PER_M, 3)}
    # Winken von vorn (Wave 1,5 s → 23 Bilder bei 15/s)
    n_wave = int(1.5 * SPRITE_FPS) + 1
    for i in range(n_wave):
        frame("wave", i, "Wave", min(1.5, i / SPRITE_FPS), -90.0, stand_dx)
    meta["anims"]["wave"] = {"frames": n_wave, "fps": SPRITE_FPS, "loop": False}
    # Stehen von vorn (Idle 2,0 s → 30 Bilder)
    n_idle = int(2.0 * SPRITE_FPS)
    for i in range(n_idle):
        frame("idle", i, "Idle", i / SPRITE_FPS, -90.0, stand_dx)
    meta["anims"]["idle"] = {"frames": n_idle, "fps": SPRITE_FPS, "loop": True}
    with open(os.path.join(out, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)


def do_dirs(out, o):
    sc, arm, meshes, catcher = badger_scene(o["samples"])
    catcher.hide_render = True
    ids = S.IdSwap(meshes)
    os.makedirs(out, exist_ok=True)
    left = -32 / S.PX_PER_M
    S.sprite_camera(left + CELL_W / S.PX_PER_M / 2, -(CELL_H - ORIGIN_ROW) / S.PX_PER_M, CELL_W, CELL_H)
    names = ["O", "SO", "S", "SW", "W", "NW", "N", "NO"]
    for d, name in enumerate(names):
        rot = -45.0 * d
        for k in range(WALK_FRAMES):
            arm.location = (0.0, S.WALK_Y, 0.0)
            arm.rotation_euler = (0.0, 0.0, math.radians(rot))
            S.set_action(arm, "Walk", (k + WALK_PHASE) / WALK_FRAMES)
            save(sc, os.path.join(out, f"{name}_{k:02d}.png"))
            ids.render(sc, os.path.join(out, f"{name}_{k:02d}_id.png"))
    with open(os.path.join(out, "meta.json"), "w") as f:
        json.dump({"cell": [CELL_W, CELL_H], "origin": [32, ORIGIN_ROW], "dirs": names,
                   "frames": WALK_FRAMES, "fps": SPRITE_FPS, "in_place": True}, f, indent=1)


# ------------------------------------------------------------------------------------------
# Szenen-Sprites: durch die Szenenkamera an ihrer Stelle gerendert, auf ihren Kasten beschnitten
# ------------------------------------------------------------------------------------------
def harbor_scene(samples, lantern=1.0):
    S.reset()
    S.load_harbor()
    S.apply_materials()
    S.unique_glass("LighthouseLamp", 5.0)
    S.unique_glass("LanternGlass", 7.0)
    S.world_sky()
    lights = S.scene_lights(lantern=lantern)
    cam = S.bg_camera()
    sc = S.render_setup("CYCLES", samples=samples, transparent=True)
    return sc, cam, lights


def only_visible(names):
    keep = set()
    for n in names:
        ob = bpy.data.objects[n]
        keep.add(ob)
        keep.update(ob.children_recursive)
    for ob in bpy.data.objects:
        if ob.type == "MESH":
            ob.visible_camera = ob in keep


def bbox_px(sc, cam, objs, margin=3):
    bpy.context.view_layer.update()      # Matrizen nach dem Versetzen und der neuen Kamera auffrischen
    us, vs = [], []
    for ob in objs:
        for c in ob.bound_box:
            p = ob.matrix_world @ Vector(c)
            v = world_to_camera_view(sc, cam, p)
            us.append(v.x * S.W)
            vs.append((1 - v.y) * S.H)
    x0 = max(0, int(math.floor(min(us))) - margin)
    x1 = min(S.W, int(math.ceil(max(us))) + margin)
    y0 = max(0, int(math.floor(min(vs))) - margin)
    y1 = min(S.H, int(math.ceil(max(vs))) + margin)
    return [x0, y0, x1, y1]


def set_border(sc, box):
    x0, y0, x1, y1 = box
    sc.render.use_border = True
    sc.render.use_crop_to_border = True
    sc.render.border_min_x, sc.render.border_max_x = x0 / S.W, x1 / S.W
    sc.render.border_min_y, sc.render.border_max_y = 1 - y1 / S.H, 1 - y0 / S.H


def do_boat(out, o):
    sc, cam, _ = harbor_scene(o["samples"])
    os.makedirs(out, exist_ok=True)
    boat = bpy.data.objects["BoatA"]
    only_visible(["BoatA"])
    bpy.data.objects["Sea"].visible_camera = True
    bpy.data.objects["Sea"].is_holdout = True        # Rumpf unter Wasser schneidet ab
    base_loc = boat.location.copy()
    base_rot = boat.rotation_euler.copy()
    n = 30
    # Kasten über alle Lagen: grob mit Rand, Rotation klein
    box = bbox_px(sc, cam, [boat] + list(boat.children_recursive), margin=4)
    set_border(sc, box)
    ids = S.IdSwap([boat] + list(boat.children_recursive))
    for k in range(n):
        th = 2 * math.pi * k / n
        boat.location = base_loc + Vector((0, 0, 0.05 * math.sin(th + 0.6)))
        boat.rotation_euler = (base_rot.x + math.radians(4.0) * math.sin(th),
                               base_rot.y + math.radians(2.6) * math.sin(th + 1.3),
                               base_rot.z)
        save(sc, os.path.join(out, f"boat_{k:02d}.png"))
        ids.render(sc, os.path.join(out, f"boat_{k:02d}_id.png"))
    with open(os.path.join(out, "meta.json"), "w") as f:
        json.dump({"box": box, "frames": n, "fps": 10}, f, indent=1)


def do_lantern(out, o):
    sc, cam, lights = harbor_scene(o["samples"])
    os.makedirs(out, exist_ok=True)
    only_visible(["LanternPost"])
    post = bpy.data.objects["LanternPost"]
    box = bbox_px(sc, cam, [post] + list(post.children_recursive), margin=3)
    set_border(sc, box)
    ids = S.IdSwap([post] + list(post.children_recursive))
    glass = bpy.data.materials["Glass_LanternGlass"]
    bsdf = [n for n in glass.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"][0]
    levels = [0.3, 0.5, 0.75, 1.1]
    for i, lv in enumerate(levels):
        bsdf.inputs["Emission Strength"].default_value = 5.0 * lv
        lights["lantern"].data.energy = 90 * lv
        save(sc, os.path.join(out, f"lantern_{i:02d}.png"))
        ids.render(sc, os.path.join(out, f"lantern_{i:02d}_id.png"))
    # Lichthof je Stufe als eigenes, additives Bild (nur die Kugel sichtbar, Laterne unsichtbar)
    ll = bpy.data.objects["LanternLight"].matrix_world.translation.copy()
    gm = glow_material("LanternGlow", "#FFB45A", 1.0)
    halo = glow_sphere("LanternHalo", ll, 0.3, gm)
    for ob in bpy.data.objects:
        if ob.type == "MESH":
            ob.visible_camera = ob is halo
    hbox = bbox_px(sc, cam, [halo], margin=1)
    set_border(sc, hbox)
    mul = gm.node_tree.nodes[gm["mul"]]
    for i, lv in enumerate(levels):
        mul.inputs[1].default_value = 0.3 * lv
        save(sc, os.path.join(out, f"halo_{i:02d}.png"))
    with open(os.path.join(out, "meta.json"), "w") as f:
        json.dump({"box": box, "levels": levels, "halo": {"box": hbox, "frames": len(levels)}}, f, indent=1)


def do_props(out, o):
    sc, cam, _ = harbor_scene(o["samples"])
    os.makedirs(out, exist_ok=True)
    meta = {}
    for name, objs in (("barrels", ["Barrel1", "Barrel2"]), ("crates", ["CrateStack"])):
        only_visible(objs)
        obl = [bpy.data.objects[n] for n in objs]
        box = bbox_px(sc, cam, obl, margin=3)
        if box[2] <= box[0]:
            continue
        set_border(sc, box)
        save(sc, os.path.join(out, f"{name}_00.png"))
        S.IdSwap(obl).render(sc, os.path.join(out, f"{name}_00_id.png"))
        meta[name] = {"box": box}
    with open(os.path.join(out, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)


def beam_material():
    m = bpy.data.materials.new("Beam")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    add = nt.nodes.new("ShaderNodeAddShader")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = S.rgba("#FFE2A0")
    # Stärke: nach außen (UV.x = Länge 0..1) schwächer, am Rand (Blickwinkel) weich
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    fall = nt.nodes.new("ShaderNodeMapRange")
    fall.inputs["From Min"].default_value = 0.0
    fall.inputs["From Max"].default_value = 1.0
    fall.inputs["To Min"].default_value = 1.0
    fall.inputs["To Max"].default_value = 0.0
    nt.links.new(sep.outputs["X"], fall.inputs["Value"])
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.5
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    nt.links.new(lw.outputs["Facing"], inv.inputs[1])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    sq = nt.nodes.new("ShaderNodeMath")
    sq.operation = "POWER"
    sq.inputs[1].default_value = 2.0
    nt.links.new(fall.outputs["Result"], sq.inputs[0])
    nt.links.new(sq.outputs[0], mul.inputs[0])
    nt.links.new(inv.outputs[0], mul.inputs[1])
    mul2 = nt.nodes.new("ShaderNodeMath")
    mul2.operation = "MULTIPLY"
    mul2.inputs[1].default_value = 0.9
    nt.links.new(mul.outputs[0], mul2.inputs[0])
    nt.links.new(mul2.outputs[0], em.inputs["Strength"])
    nt.links.new(tr.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs["Surface"])
    m.blend_method = "BLEND" if hasattr(m, "blend_method") else None
    return m


def glow_material(name, color, strength):
    """Lichthof: Emission × (1 − Facing)^-… → in der Mitte hell, zum Rand weich, sonst durchsichtig.
    Gerendert über durchsichtigem Grund ergibt das einen additiven Beitrag (Farbrechnung)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    add = nt.nodes.new("ShaderNodeAddShader")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = S.rgba(color)
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.5
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    nt.links.new(lw.outputs["Facing"], inv.inputs[1])
    pw = nt.nodes.new("ShaderNodeMath")
    pw.operation = "POWER"
    pw.inputs[1].default_value = 3.0
    nt.links.new(inv.outputs[0], pw.inputs[0])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = strength
    nt.links.new(pw.outputs[0], mul.inputs[0])
    nt.links.new(mul.outputs[0], em.inputs["Strength"])
    nt.links.new(tr.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs["Surface"])
    m["mul"] = mul.name
    return m


def glow_sphere(name, loc, radius, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=loc, segments=32, ring_count=16)
    ob = bpy.context.active_object
    ob.name = name
    ob.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    return ob


def do_beam(out, o):
    sc, cam, _ = harbor_scene(o["samples"])
    os.makedirs(out, exist_ok=True)
    lh = bpy.data.objects["LighthouseLight"].matrix_world.translation.copy()
    # Kegel: 26 m lang, Öffnung 6°, Spitze im Leuchtfeuer, Achse +X
    L, R = 16.0, 16.0 * math.tan(math.radians(5))
    bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=R, radius2=0.25, depth=L, end_fill_type="NOTHING",
                                    location=(0, 0, 0))
    cone = bpy.context.active_object
    cone.name = "Beam"
    cone.rotation_euler = (0, math.radians(-90), 0)   # Achse auf +X, schmale Seite zur Lampe
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    for v in cone.data.vertices:
        v.co.x += L / 2
    cone.data.materials.append(beam_material())
    pivot = bpy.data.objects.new("BeamPivot", None)
    S._link(pivot)
    pivot.location = lh
    cone.parent = pivot
    # Alles außer dem Kegel unsichtbar für die Kamera; Leuchtturm verdeckt als Ausschnitt
    for ob in bpy.data.objects:
        if ob.type == "MESH" and ob is not cone:
            ob.visible_camera = True
            ob.is_holdout = True
    for ob in bpy.data.objects:
        if ob.type == "LIGHT":
            ob.hide_render = True
    sc.world = None
    bpy.context.view_layer.update()
    v = world_to_camera_view(sc, cam, lh)
    cx, cy = v.x * S.W, (1 - v.y) * S.H
    box = [0, 0, S.W, 120]
    set_border(sc, box)
    # Aufblitzen: Lichthof um die Lampe, stark, wenn der Strahl zur Kamera zeigt
    fm = glow_material("Flash", "#FFF0C8", 1.0)
    # 3 m zur Kamera hin versetzt: Ein Blendlicht liegt vor dem Turm, wird also nicht vom Laternenhaus
    # (Ausschnitt) beschnitten
    toward = (cam.matrix_world.translation - lh).normalized()
    flash = glow_sphere("Flash", lh + toward * 3.0, 1.0, fm)
    flash.is_holdout = False
    fmul = fm.node_tree.nodes[fm["mul"]]
    to_cam = cam.matrix_world.translation - lh
    to_cam.z = 0
    to_cam.normalize()
    n = 24
    flashes = []
    for k in range(n):
        a = 2 * math.pi * k / n
        pivot.rotation_euler = (0, 0, a)
        d = max(0.0, math.cos(a) * to_cam.x + math.sin(a) * to_cam.y)
        f = d ** 6
        flashes.append(round(f, 3))
        fmul.inputs[1].default_value = 1.2 * f
        flash.hide_render = f < 0.01
        save(sc, os.path.join(out, f"beam_{k:02d}.png"))
    with open(os.path.join(out, "meta.json"), "w") as f:
        json.dump({"box": box, "frames": n, "fps": 6, "lamp_px": [cx, cy], "flash": flashes}, f, indent=1)


def main():
    out, group, o = parse()
    fn = {"badger": do_badger, "dirs": do_dirs, "boat": do_boat, "lantern": do_lantern,
          "props": do_props, "beam": do_beam}[group]
    fn(os.path.join(out, group), o)
    print("fertig", group)


main()
