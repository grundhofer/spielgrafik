"""Vorgerenderte Iso-Karte des Hafens (640×480 Kartenpixel) für iso-vorgerendert.

Aufruf (aus dem Projektordner):
  blender -b --factory-startup -P styles/iso-vorgerendert/blender/render_bg.py -- --out <dir> --pass <name> [...]

Pässe (alle mit derselben orthografischen Kamera, Kartenraster aus assets/scene.json):
  preview   EEVEE, schnell, nur zum Prüfen des Ausschnitts (--badger x,z,grad;... setzt Dachs-Marker)
  beauty    Cycles, ss-fach (Standard 2), Bild 0 der Schleife: Sonne, Himmel, Laterne, Fenster, Leuchtfeuer
  frames    Cycles, Schleife für Wasser und Boote (LOOP_S, FPS); Bild 0 = beauty
  depth     Tiefe entlang der Blickachse, 1 Strahl je Kartenpixel-Mitte -> depth.npy (float32, Meter)
  emit      nur Leuchtflächen (Glas) -> emit.png (16 Bit)
  beam      nur der Strahl des Leuchtfeuers als Volumen (Bildfolge, BEAM_S, BEAM_FPS) -> beam_XXXX.png
Deterministisch (feste Seeds, Zeit nur aus der Bildnummer).
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Euler, Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import isocam as ic  # noqa: E402

LOOP_S = 3.0      # Wasser und Boote: Schleife in Sekunden
FPS = 10          # Bildrate der Wasserfolge (geht in 30 fps auf: jedes Bild 3 Aufnahmebilder)
BEAM_S = 6.0      # eine Umdrehung des Leuchtfeuers
BEAM_FPS = 15


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--pass", dest="pas", required=True,
                    choices=["preview", "beauty", "frames", "depth", "emit", "beam"])
    ap.add_argument("--ss", type=int, default=2)
    ap.add_argument("--samples", type=int, default=96)
    ap.add_argument("--frames", default="all")
    ap.add_argument("--badger", default="", help="preview: Dachs-Marker x,z,blick_grad;... (Godot, Blick 0 = +x)")
    ap.add_argument("--crop", default="", help="nur Kartenbereich x0,y0,x1,y1 rendern (Pixel)")
    return ap.parse_args(argv)


def set_time(state, t):
    ph = 2 * math.pi * (t % LOOP_S) / LOOP_S
    for sock, cycles in state["water_phase"]:
        sock.default_value = cycles * ph
    Rr = 1.2
    state["water_circle"].inputs[0].default_value = Rr * math.cos(ph)
    state["water_w"].default_value = Rr * math.sin(ph)
    for k, name in enumerate(("BoatA", "BoatB")):
        ob = bpy.data.objects[name]
        base = state["boat_base"][name]
        roll = math.radians(2.2) * math.sin(ph + 1.7 * k)
        pitch = math.radians(0.9) * math.sin(2 * ph + 0.8 + 1.7 * k)
        heave = 0.035 * math.sin(ph + 2.1 + 1.7 * k)
        ob.matrix_world = Matrix.Translation((0, 0, heave)) @ base @ Euler((roll, pitch, 0)).to_matrix().to_4x4()


def build_beam(state):
    """Sichtbarer Strahl: Kegel mit Emissionsvolumen an LighthouseLight, dreht um die Hochachse."""
    lh = bpy.data.objects["LighthouseLight"].matrix_world.translation.copy()
    rotor = ic.link_obj(bpy.data.objects.new("BeamRotor", None))
    rotor.location = lh
    L = 18.0
    r0, r1 = 0.22, 2.6
    bpy.ops.mesh.primitive_cone_add(vertices=40, radius1=r0, radius2=r1, depth=L, end_fill_type="NGON",
                                    location=(0, 0, 0))
    cone = bpy.context.active_object
    cone.name = "Beam"
    cone.data.transform(Matrix.Translation((0, 0, L / 2)))
    cone.parent = rotor
    cone.rotation_euler = Euler((math.radians(-90 - 3), 0, 0))
    m, nt = ic.new_material("R_Beam")
    tc = nt.node("ShaderNodeTexCoord")
    sep = nt.node("ShaderNodeSeparateXYZ")
    nt.link(tc.outputs["Object"], sep.inputs[0])
    u = nt.math("DIVIDE", sep.outputs["Z"], L)
    rad = nt.math("ADD", r0, nt.math("MULTIPLY", u, r1 - r0))
    comb = nt.node("ShaderNodeCombineXYZ")
    rr = nt.vmath("LENGTH", comb.outputs[0])
    nt.link(sep.outputs["X"], comb.inputs[0])
    nt.link(sep.outputs["Y"], comb.inputs[1])
    radial = nt.math("SUBTRACT", 1.0, nt.math("POWER", nt.math("DIVIDE", rr, rad, clamp=False), 2.0), clamp=True)
    along = nt.math("POWER", nt.math("SUBTRACT", 1.0, u, clamp=True), 1.6)
    dens = nt.math("MULTIPLY", radial, along)
    em = nt.node("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*ic.srgb_lin("#FFE6B8"), 1)
    nt.link(nt.math("MULTIPLY", dens, 0.9), em.inputs["Strength"])
    out = nt.node("ShaderNodeOutputMaterial")
    nt.link(em.outputs["Emission"], out.inputs["Volume"])
    cone.data.materials.append(m)
    cone.visible_shadow = False
    state["beam"] = cone
    state["rotor"] = rotor


def set_beam_time(state, t, cam_ob):
    """Eine Umdrehung je BEAM_S; zur Zeit 1,0 s zeigt der Strahl waagrecht zur Kamera (Aufblitzen)."""
    to_cam = -ic.D.copy()
    to_cam.z = 0
    to_cam.normalize()
    yaw_cam = math.atan2(-to_cam.x, to_cam.y)
    yaw = yaw_cam + 2 * math.pi * (t - 1.0) / BEAM_S
    state["rotor"].rotation_euler = (0, 0, yaw)
    beam_dir = Vector((-math.sin(yaw), math.cos(yaw), 0))
    facing = max(0.0, beam_dir.dot(to_cam)) ** 16
    lamp = state["glass"]["LighthouseLamp"][1]
    lamp.inputs["Emission Strength"].default_value = 14.0 + 50.0 * facing
    return facing


def parse_frames(s, n):
    if s in ("", "all"):
        return list(range(n))
    out = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def add_badger_markers(spec):
    for item in spec.split(";"):
        bx, bz, byaw = map(float, item.split(","))
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=os.path.join(ic.ROOT, "shared", "3d", "badger.glb"))
        root = next(o for o in bpy.data.objects if o not in before and o.parent is None)
        root.rotation_mode = "XYZ"
        root.location = ic.gb((bx, 0.0, bz))
        root.rotation_euler = (0, 0, math.radians(byaw))


def main():
    a = parse()
    os.makedirs(a.out, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    ic.import_harbor()
    ic.apply_layout_changes()
    state = {"water_phase": []}
    ic.build_materials(state)
    world, bgn = ic.build_world()
    sun = ic.add_sun()
    ic.build_scene_lights(state)
    state["boat_base"] = {n: bpy.data.objects[n].matrix_world.copy() for n in ("BoatA", "BoatB")}
    if a.badger:
        add_badger_markers(a.badger)
    build_beam(state)
    state["beam"].hide_render = True

    X0, Yt, s = ic.map_frame()
    W, H = ic.SCENE["map"]["size"]
    ss = a.ss if a.pas in ("beauty", "frames", "preview", "emit") else 1
    cam = ic.setup_camera(sc, (W, H), X0, Yt, s, ss)
    if a.crop:
        x0, y0, x1, y1 = map(int, a.crop.split(","))
        sc.render.use_border = True
        sc.render.use_crop_to_border = True
        sc.render.border_min_x, sc.render.border_max_x = x0 / W, x1 / W
        sc.render.border_min_y, sc.render.border_max_y = 1 - y1 / H, 1 - y0 / H

    meta = {"map": [W, H], "X0": X0, "Ytop": Yt, "px_per_m": s, "cam_location": list(cam.location),
            "R": list(ic.R), "U": list(ic.U), "D": list(ic.D), "loop_s": LOOP_S, "fps": FPS,
            "beam_s": BEAM_S, "beam_fps": BEAM_FPS,
            "lantern": ic.bg(bpy.data.objects["LanternLight"].matrix_world.translation),
            "lighthouse_light": ic.bg(bpy.data.objects["LighthouseLight"].matrix_world.translation),
            "window": ic.bg(bpy.data.objects["CottageWindow"].matrix_world.translation),
            "sun_dir": ic.bg(ic.sun_direction())}
    json.dump(meta, open(os.path.join(a.out, "bg_meta.json"), "w"), indent=1)

    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.image_settings.color_depth = "8"
    sc.render.film_transparent = False

    if a.pas == "preview":
        sc.render.engine = "BLENDER_EEVEE"
        sc.eevee.taa_render_samples = 32
        sc.view_settings.view_transform = "Standard"
        set_time(state, 0.0)
        sc.render.image_settings.color_depth = "8"
        sc.render.filepath = os.path.join(a.out, "preview.png")
        bpy.ops.render.render(write_still=True)
        print("PREVIEW OK", flush=True)
        return

    ic.cycles_setup(sc, a.samples)

    if a.pas in ("beauty", "frames"):
        n = int(round(LOOP_S * FPS))
        frames = [0] if a.pas == "beauty" else parse_frames(a.frames, n)
        for i in frames:
            set_time(state, i / FPS)
            sc.render.filepath = os.path.join(a.out, "beauty.png" if a.pas == "beauty" else f"f_{i:04d}.png")
            bpy.ops.render.render(write_still=True)
            print(f"FRAME {i} ok", flush=True)

    elif a.pas == "emit":
        set_time(state, 0.0)
        black, nt = ic.new_material("R_Black")
        e = nt.node("ShaderNodeEmission")
        e.inputs["Strength"].default_value = 0.0
        o = nt.node("ShaderNodeOutputMaterial")
        nt.link(e.outputs[0], o.inputs["Surface"])
        glass_mats = {g[0] for g in state["glass"].values()}
        for ob in bpy.data.objects:
            if ob.type == "MESH":
                for slot in ob.material_slots:
                    if slot.material not in glass_mats:
                        slot.material = black
            if ob.type == "LIGHT":
                ob.hide_render = True
        bgn.inputs["Strength"].default_value = 0.0
        sc.cycles.samples = 16
        sc.cycles.use_denoising = False
        sc.render.filepath = os.path.join(a.out, "emit.png")
        bpy.ops.render.render(write_still=True)
        print("EMIT ok", flush=True)

    elif a.pas == "beam":
        black, nt = ic.new_material("R_Black")
        e = nt.node("ShaderNodeEmission")
        e.inputs["Strength"].default_value = 0.0
        o = nt.node("ShaderNodeOutputMaterial")
        nt.link(e.outputs[0], o.inputs["Surface"])
        lamp_mat = state["glass"]["LighthouseLamp"][0]
        for ob in bpy.data.objects:
            if ob.type == "MESH" and ob.name != "Beam":
                for slot in ob.material_slots:
                    if slot.material is not lamp_mat:
                        slot.material = black
            if ob.type == "LIGHT":
                ob.hide_render = True
        bgn.inputs["Strength"].default_value = 0.0
        state["beam"].hide_render = False
        sc.cycles.samples = 24
        sc.cycles.use_denoising = True
        sc.cycles.volume_step_rate = 2.0
        set_time(state, 0.0)
        n = int(round(BEAM_S * BEAM_FPS))
        flashes = {}
        for i in parse_frames(a.frames, n):
            flashes[i] = set_beam_time(state, i / BEAM_FPS, cam)
            sc.render.filepath = os.path.join(a.out, f"beam_{i:04d}.png")
            bpy.ops.render.render(write_still=True)
            print(f"BEAM {i} ok", flush=True)
        json.dump(flashes, open(os.path.join(a.out, "beam_flash.json"), "w"))

    elif a.pas == "depth":
        set_time(state, 0.0)
        m, nt = ic.new_material("R_Depth")
        camd = nt.node("ShaderNodeCameraData")
        em = nt.node("ShaderNodeEmission")
        nt.link(camd.outputs["View Z Depth"], em.inputs["Strength"])
        em.inputs["Color"].default_value = (1, 1, 1, 1)
        o = nt.node("ShaderNodeOutputMaterial")
        nt.link(em.outputs["Emission"], o.inputs["Surface"])
        bpy.context.view_layer.material_override = m
        for ob in bpy.data.objects:
            if ob.type == "LIGHT":
                ob.hide_render = True
        bgn.inputs["Color"].default_value = (1, 1, 1, 1)
        for lk in list(world.node_tree.links):
            if lk.to_node == bgn and lk.to_socket.name == "Color":
                world.node_tree.links.remove(lk)
        bgn.inputs["Strength"].default_value = 1000.0
        sc.cycles.samples = 1
        sc.cycles.use_adaptive_sampling = False
        sc.cycles.use_denoising = False
        sc.cycles.max_bounces = 0
        sc.cycles.pixel_filter_type = "BOX"
        sc.cycles.filter_width = 0.01
        sc.cycles.seed = 0
        sc.render.image_settings.file_format = "OPEN_EXR"
        sc.render.image_settings.color_depth = "32"
        sc.render.image_settings.exr_codec = "ZIP"
        p = os.path.join(a.out, "depth.exr")
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        import numpy as np
        img = bpy.data.images.load(p)
        arr = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)[::-1, :, 0]
        np.save(os.path.join(a.out, "depth.npy"), arr)
        print("DEPTH ok", float(arr.min()), float(arr.max()), flush=True)
    print("RENDER_BG OK", a.pas, flush=True)


main()
