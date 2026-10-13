"""Vertex-Animation-Texturen (VAT) für die Demo bauen: Fahne (Stoffsimulation) und Möwe (Flügelschlag).

    blender -b --factory-startup -P styles/vertex-animation/blender/build_vat.py -- \
        --demo styles/vertex-animation/demo --assets styles/vertex-animation/assets [--preview DIR]

Ablauf je Objekt:
  1. Mesh im Skript bauen (Ruhelage), zwei UV-Maps: `UVMap` (Muster) und `VAT` (Punktindex: u = (i + 0,5) / N).
  2. Ruhelage als glb exportieren (nur dieses Objekt, ohne Modifier) -> demo/models/<name>.glb
  3. Bewegung in Blender erzeugen:
     - Fahne: Stoffsimulation (Cloth) mit Wind- und Turbulenzfeld, Kante am Mast gepinnt. SIM_FRAMES Bilder
       simulieren, WARMUP verwerfen, LOOP Bilder als Schleife verwenden; die BLEND Bilder nach der Schleife
       werden in deren Anfang überblendet, damit Bild LOOP-1 -> Bild 0 nahtlos ist.
     - Möwe: Armature mit fünf Knochen, Flügelschlag als Keyframes (ein Schlag = GULL_FRAMES Bilder).
  4. Je Bild das ausgewertete Mesh lesen (depsgraph), Versatz zur Ruhelage und Normale in Godot-Achsen
     (Godot x, y, z = Blender x, z, -y) umrechnen und als Zeile in eine Float-Textur schreiben:
     Spalte = Punkt, Zeile = Bild (Zeile 0 = oberste Bildzeile = Bild 0). OpenEXR, RGBA, 16 Bit Half Float.
  5. Bericht (assets/vat_report.json): Texturgrößen, Bytes, Rundungsfehler durch Half Float, Schleifennaht.
     Referenzpositionen (float32) einiger Bilder für die Prüfung in Godot: assets/measure/flag_ref.bin.

Deterministisch: keine Zufallszahlen außer den festen Seeds der Kraftfelder. Laufzeit wenige Sekunden.
"""
import json
import math
import os
import struct
import sys

import bpy
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


DEMO = os.path.abspath(arg("--demo", "styles/vertex-animation/demo"))
ASSETS = os.path.abspath(arg("--assets", "styles/vertex-animation/assets"))
PREVIEW = arg("--preview")  # optional: Ordner für Workbench-Vorschaubilder der Fahne

# --- Fahne -----------------------------------------------------------------------------------------
FLAG_W, FLAG_H = 1.5, 1.0          # m; Blender x = Flugrichtung, z = oben, Oberkante bei z = 0
FLAG_NX, FLAG_NY = 30, 20          # Felder -> 31 x 21 = 651 Punkte
FPS = 30
WARMUP, LOOP, BLEND = 90, 120, 40  # Bilder: Einschwingen, Schleife (4 s), Überblendung
SIM_FRAMES = WARMUP + LOOP + BLEND
WIND_STRENGTH = float(arg("--wind", "10000"))
TURB_STRENGTH = float(arg("--turb", "200"))
BENDING = float(arg("--bend", "3.0"))
SELF_COLLISION = "--no-self-collision" not in argv

# --- Möwe ------------------------------------------------------------------------------------------
GULL_FRAMES = 24                   # Bilder je Flügelschlag (Abspieltempo setzt Godot je Möwe)


def to_godot(a):
    """Blender (x, y, z) -> Godot (x, z, -y) für Arrays (..., 3)."""
    return np.stack([a[..., 0], a[..., 2], -a[..., 1]], axis=-1)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.frame_start, sc.frame_end = 1, SIM_FRAMES
    return sc


def add_index_uv(me):
    """UV-Map 'VAT': jeder Ecke ihres Punktes u = (i + 0,5) / N, v = 0,5 (glTF: TEXCOORD_1, Godot: UV2)."""
    n = len(me.vertices)
    uv = me.uv_layers.new(name="VAT")
    vidx = np.zeros(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", vidx)
    co = np.zeros((len(me.loops), 2), np.float32)
    co[:, 0] = (vidx + 0.5) / n
    co[:, 1] = 0.5
    uv.data.foreach_set("uv", co.ravel())


def export_glb(obj, path):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_yup=True,
                              export_apply=False, export_texcoords=True, export_normals=True,
                              export_vertex_color="ACTIVE", export_animations=False, export_skins=False,
                              export_morph=False, export_cameras=False, export_lights=False,
                              export_materials="NONE")


def evaluated_frames(obj, frames):
    """Liste (Positionen, Normalen) des ausgewerteten Meshes für die Bilder `frames` (Blender-Achsen, lokal)."""
    sc = bpy.context.scene
    out = []
    n = len(obj.data.vertices)
    for f in frames:
        sc.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        ev = obj.evaluated_get(dg)
        me = ev.to_mesh()
        assert len(me.vertices) == n, "Punktzahl ändert sich (Modifier ändert Topologie)"
        co = np.zeros(n * 3, np.float32)
        me.vertices.foreach_get("co", co)
        nr = np.zeros(n * 3, np.float32)
        me.vertex_normals.foreach_get("vector", nr)
        out.append((co.reshape(n, 3).copy(), nr.reshape(n, 3).copy()))
        ev.to_mesh_clear()
    return out


def save_exr(path, rgb):
    """rgb: (Bilder, Punkte, 3) float32 -> OpenEXR RGBA Half, Zeile 0 der Datei = Bild 0."""
    frames, n, _ = rgb.shape
    img = bpy.data.images.new(os.path.basename(path), width=n, height=frames, alpha=True,
                              float_buffer=True, is_data=True)
    img.colorspace_settings.name = "Non-Color"
    px = np.ones((frames, n, 4), np.float32)
    px[..., :3] = rgb
    img.pixels.foreach_set(px[::-1].ravel())  # Blender speichert Pixel von unten nach oben
    sc = bpy.context.scene
    st = sc.render.image_settings
    st.file_format = "OPEN_EXR"
    st.color_mode = "RGBA"
    st.color_depth = "16"
    st.exr_codec = "NONE"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save_render(path, scene=sc)
    bpy.data.images.remove(img)
    return os.path.getsize(path)


def read_exr_half(path):
    """Unkomprimiertes Scanline-EXR (Half) lesen -> (Zeilen, Spalten, Kanäle in Dateireihenfolge A, B, G, R)."""
    data = open(path, "rb").read()
    assert struct.unpack("<I", data[:4])[0] == 20000630
    pos, attrs = 8, {}
    while data[pos] != 0:
        end = data.index(b"\0", pos)
        name = data[pos:end].decode()
        pos = end + 1
        end = data.index(b"\0", pos)
        typ = data[pos:end].decode()
        pos = end + 1
        size = struct.unpack("<i", data[pos:pos + 4])[0]
        pos += 4
        attrs[name] = (typ, data[pos:pos + size])
        pos += size
    pos += 1
    assert attrs["compression"][1][0] == 0, "nur unkomprimiert"
    ch, chans = attrs["channels"][1], []
    p = 0
    while ch[p] != 0:
        end = ch.index(b"\0", p)
        nm = ch[p:end].decode()
        ptype = struct.unpack("<i", ch[end + 1:end + 5])[0]
        chans.append((nm, ptype))
        p = end + 17
    x0, y0, x1, y1 = struct.unpack("<4i", attrs["dataWindow"][1])
    w, h = x1 - x0 + 1, y1 - y0 + 1
    offsets = struct.unpack(f"<{h}Q", data[pos:pos + 8 * h])
    out = np.zeros((h, len(chans), w), np.float16)
    for off in offsets:
        y = struct.unpack("<i", data[off:off + 4])[0] - y0
        row = np.frombuffer(data, np.float16, count=w * len(chans), offset=off + 8)
        out[y] = row.reshape(len(chans), w)
    return {nm: out[:, i, :].astype(np.float32) for i, (nm, _) in enumerate(chans)}, [c[1] for c in chans]


def check_exr(path, rgb):
    """Datei zurücklesen und mit den float32-Werten vergleichen (Fehler in mm bzw. Normalen-Einheiten)."""
    ch, types = read_exr_half(path)
    back = np.stack([ch["R"], ch["G"], ch["B"]], axis=-1)
    err = np.abs(back - rgb)
    return {"channel_types": sorted(set("half" if t == 1 else "float" if t == 2 else str(t) for t in types)),
            "max_err": float(err.max()), "mean_err": float(err.mean()),
            "alpha_ok": bool(np.allclose(ch["A"], 1.0))}


# ===================================================================================================
# Fahne
# ===================================================================================================
def build_flag():
    sc = reset()
    nx, ny = FLAG_NX, FLAG_NY
    verts, faces = [], []
    for r in range(ny + 1):
        for c in range(nx + 1):
            verts.append((FLAG_W * c / nx, 0.0, -FLAG_H * r / ny))
    for r in range(ny):
        for c in range(nx):
            i = r * (nx + 1) + c
            faces.append((i, i + nx + 1, i + nx + 2, i + 1))  # Normale zeigt nach -y (Blender) = +z (Godot)
    me = bpy.data.meshes.new("Flag")
    me.from_pydata(verts, [], faces)
    me.update()
    uv = me.uv_layers.new(name="UVMap")
    vidx = np.zeros(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", vidx)
    v = np.array(verts, np.float32)[vidx]
    # glTF dreht V um: Godot-UV = (x / W, Abstand von der Oberkante / H)
    uv.data.foreach_set("uv", np.stack([v[:, 0] / FLAG_W, 1.0 + v[:, 2] / FLAG_H], 1).ravel())
    add_index_uv(me)
    me.uv_layers.active = me.uv_layers["UVMap"]
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new("Flag", me)
    sc.collection.objects.link(ob)
    export_glb(ob, os.path.join(DEMO, "models", "flag.glb"))

    # Stoff: Kante am Mast (x = 0) gepinnt
    pin = ob.vertex_groups.new(name="Pin")
    pin.add([i for i, co in enumerate(verts) if co[0] < 1e-6], 1.0, "REPLACE")
    md = ob.modifiers.new("Cloth", "CLOTH")
    s = md.settings
    s.quality = 10
    s.mass = 0.25
    s.air_damping = 1.0
    s.tension_stiffness = s.compression_stiffness = 20.0
    s.shear_stiffness = 6.0
    s.bending_stiffness = BENDING
    s.vertex_group_mass = "Pin"
    s.pin_stiffness = 1.0
    md.collision_settings.use_collision = False
    md.collision_settings.use_self_collision = SELF_COLLISION
    md.collision_settings.self_distance_min = 0.008
    md.point_cache.frame_start, md.point_cache.frame_end = 1, SIM_FRAMES

    # Wind entlang +x (Feld bläst entlang seiner lokalen +z-Achse), dazu Turbulenz für das Flattern
    bpy.ops.object.effector_add(type="WIND", location=(-2.0, 0.0, -0.5), rotation=(0.0, math.radians(90.0), 0.0))
    wind = bpy.context.object
    wind.field.strength = WIND_STRENGTH
    wind.field.noise = 2.0
    wind.field.seed = 7
    wind.field.flow = 0.0
    bpy.ops.object.effector_add(type="TURBULENCE", location=(0.75, 0.0, -0.5))
    turb = bpy.context.object
    turb.field.strength = TURB_STRENGTH
    turb.field.size = 0.7
    turb.field.flow = 0.0
    turb.field.noise = 0.0
    turb.field.seed = 11

    rest = np.array(verts, np.float32)
    frames = evaluated_frames(ob, range(1, SIM_FRAMES + 1))
    pos = np.stack([f[0] for f in frames])     # (SIM, N, 3) Blender lokal
    nrm = np.stack([f[1] for f in frames])

    # Schleife: Bild k = WARMUP + k; die BLEND Bilder nach der Schleife in den Anfang überblenden
    a = WARMUP
    loop_pos = pos[a:a + LOOP].copy()
    loop_nrm = nrm[a:a + LOOP].copy()
    for k in range(BLEND):
        w = (k + 0.5) / BLEND
        w = w * w * (3 - 2 * w)
        loop_pos[k] = (1 - w) * pos[a + LOOP + k] + w * pos[a + k]
        loop_nrm[k] = (1 - w) * nrm[a + LOOP + k] + w * nrm[a + k]
    loop_nrm /= np.linalg.norm(loop_nrm, axis=-1, keepdims=True)

    off_g = to_godot(loop_pos - rest[None])
    nrm_g = to_godot(loop_nrm)
    p_pos = os.path.join(DEMO, "vat", "flag_pos.exr")
    p_nrm = os.path.join(DEMO, "vat", "flag_nrm.exr")
    b_pos, b_nrm = save_exr(p_pos, off_g), save_exr(p_nrm, nrm_g)

    # Referenz (float32, Godot-Achsen, absolute lokale Positionen) für die Prüfung in Godot
    ref_frames = [0, 37, 119]
    ref = to_godot(loop_pos[ref_frames])
    os.makedirs(os.path.join(ASSETS, "measure"), exist_ok=True)
    ref.astype("<f4").tofile(os.path.join(ASSETS, "measure", "flag_ref.bin"))

    # Kennzahlen
    step = np.linalg.norm(np.diff(loop_pos, axis=0), axis=-1)            # Bewegung je Bild
    seam = np.linalg.norm(loop_pos[0] - loop_pos[-1], axis=-1)            # Naht Bild 119 -> 0
    raw_seam = np.linalg.norm(pos[a] - pos[a + LOOP - 1], axis=-1)        # ohne Überblendung
    free = np.array([c == FLAG_NX for r in range(FLAG_NY + 1) for c in range(FLAG_NX + 1)])
    pinned = np.array([c == 0 for r in range(FLAG_NY + 1) for c in range(FLAG_NX + 1)])
    if PREVIEW:
        render_flag_preview(ob, [a + 41, a + 56, a + 71, a + 86])   # Schleifenbilder 40, 55, 70, 85 (nicht überblendet)
    return {
        "vertices": int(len(verts)), "triangles": int(2 * FLAG_NX * FLAG_NY),
        "frames": LOOP, "fps": FPS, "loop_seconds": LOOP / FPS,
        "simulated_frames": SIM_FRAMES, "warmup": WARMUP, "blend": BLEND,
        "texture": {"pos": [int(len(verts)), LOOP, "RGBA16F", b_pos], "nrm": [int(len(verts)), LOOP, "RGBA16F", b_nrm]},
        "offset_range_m": [float(off_g.min()), float(off_g.max())],
        "half_check_pos_m": check_exr(p_pos, off_g), "half_check_nrm": check_exr(p_nrm, nrm_g),
        "motion_per_frame_mm": {"mean": float(step.mean() * 1000), "p95": float(np.percentile(step, 95) * 1000),
                                "max": float(step.max() * 1000)},
        "seam_mm": {"max": float(seam.max() * 1000), "mean": float(seam.mean() * 1000),
                    "without_blend_max": float(raw_seam.max() * 1000)},
        "pinned_max_offset_mm": float(np.abs(loop_pos[:, pinned] - rest[None, pinned]).max() * 1000),
        "free_edge_mean_x_m": float(loop_pos[:, free, 0].mean()),
        "free_edge_mean_drop_m": float(-(loop_pos[:, free, 2] - rest[None, free, 2]).mean()),
        "wind_strength": WIND_STRENGTH, "turbulence_strength": TURB_STRENGTH,
        "ref_frames": ref_frames,
    }


def render_flag_preview(ob, frames):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_depth = "8"
    sc.render.resolution_x, sc.render.resolution_y = 400, 300
    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    sc.collection.objects.link(cam)
    cam.location = (2.9, -3.4, 0.5)                      # schräg von vorn, damit die Wellen im Stoff sichtbar sind
    from mathutils import Vector
    cam.rotation_euler = (Vector((0.75, 0.0, -0.5)) - Vector(cam.location)).to_track_quat("-Z", "Y").to_euler()
    cam_data.lens = 40
    sc.camera = cam
    sc.display.shading.light = "STUDIO"
    sc.display.shading.show_cavity = True
    sc.display.shading.color_type = "SINGLE"
    sc.display.shading.single_color = (0.75, 0.72, 0.66)
    sc.display.shading.background_type = "VIEWPORT"
    sc.display.shading.background_color = (0.13, 0.15, 0.19)
    os.makedirs(PREVIEW, exist_ok=True)
    for f in frames:
        sc.frame_set(f)
        sc.render.filepath = os.path.join(PREVIEW, f"flag_{f:03d}.png")
        bpy.ops.render.render(write_still=True)


# ===================================================================================================
# Möwe
# ===================================================================================================
def ring(y, rx, rz, zc, seg):
    return [(rx * math.sin(2 * math.pi * k / seg), y, zc + rz * math.cos(2 * math.pi * k / seg)) for k in range(seg)]


def build_gull():
    sc = reset()
    verts, faces, cols = [], [], []

    def add(vs, col):
        base = len(verts)
        verts.extend(vs)
        cols.extend([col] * len(vs))
        return base

    WHITE, GREY, BLACK, BEAK = (0.92, 0.92, 0.9), (0.52, 0.56, 0.6), (0.06, 0.06, 0.07), (0.95, 0.7, 0.12)
    # Rumpf: Ringe entlang +y (Blender, = Godot -z = vorn), 8 Segmente
    seg = 8
    prof = [(-0.20, 0.030, 0.026, 0.000), (-0.13, 0.050, 0.045, 0.004), (-0.05, 0.062, 0.056, 0.006),
            (0.03, 0.060, 0.054, 0.008), (0.09, 0.045, 0.045, 0.018), (0.14, 0.040, 0.042, 0.030),
            (0.19, 0.032, 0.034, 0.032), (0.225, 0.016, 0.018, 0.030)]
    rings = [add(ring(y, rx, rz, zc, seg), WHITE) for y, rx, rz, zc in prof]
    for a, b in zip(rings, rings[1:]):
        for k in range(seg):
            faces.append((a + k, a + (k + 1) % seg, b + (k + 1) % seg, b + k))
    tail_cap = add([(0.0, -0.215, 0.0)], WHITE)
    for k in range(seg):
        faces.append((rings[0] + (k + 1) % seg, rings[0] + k, tail_cap))
    # Schnabel: Kegel ab dem letzten Ring
    bk = add(ring(0.225, 0.014, 0.014, 0.026, 6), BEAK)
    tip = add([(0.0, 0.30, 0.018)], BEAK)
    for k in range(6):
        faces.append((bk + k, bk + (k + 1) % 6, tip))
    cap = add([(0.0, 0.226, 0.028)], BEAK)
    for k in range(6):
        faces.append((bk + (k + 1) % 6, bk + k, cap))
    # Schwanz: flacher Fächer
    t0 = add([(-0.035, -0.17, 0.004), (0.035, -0.17, 0.004), (0.075, -0.33, 0.0), (-0.075, -0.33, 0.0)], WHITE)
    faces.append((t0, t0 + 1, t0 + 2, t0 + 3))
    # Flügel: Platten, Stationen entlang der Spannweite, je 3 Punkte über die Profiltiefe
    st = [0.03, 0.11, 0.19, 0.27, 0.33, 0.40, 0.47, 0.54, 0.60, 0.66]

    def le(s):   # Vorderkante (y)
        return 0.085 - 0.02 * s / 0.33 if s <= 0.33 else 0.065 - 0.11 * ((s - 0.33) / 0.33) ** 1.4

    def te(s):   # Hinterkante (y)
        return -0.11 + 0.03 * s / 0.33 if s <= 0.33 else -0.08 + 0.005 * (s - 0.33) / 0.33

    for side in (1, -1):
        base = len(verts)
        for s in st:
            col = BLACK if s > 0.57 else GREY
            y0, y1 = le(s), te(s)
            for j, y in enumerate((y0, 0.5 * (y0 + y1) + 0.01, y1)):
                camber = 0.012 if j == 1 else 0.0
                verts.append((side * s, y, 0.012 + camber * (1 - s / 0.7)))
                cols.append(col)
        for i in range(len(st) - 1):
            for j in range(2):
                a, b = base + 3 * i + j, base + 3 * (i + 1) + j
                f = (a, b, b + 1, a + 1) if side == 1 else (a, a + 1, b + 1, b)
                faces.append(f)  # Normale nach oben (+z Blender = +y Godot)

    me = bpy.data.meshes.new("Gull")
    me.from_pydata(verts, [], faces)
    me.update()
    for p in me.polygons:
        p.use_smooth = True
    ca = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    ca.data.foreach_set("color", np.array([(*c, 1.0) for c in cols], np.float32).ravel())
    me.color_attributes.active_color = ca
    uv = me.uv_layers.new(name="UVMap")        # planar (Meter); nur damit 'VAT' wie bei der Fahne TEXCOORD_1 wird
    vidx = np.zeros(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", vidx)
    v = np.array(verts, np.float32)[vidx]
    uv.data.foreach_set("uv", np.stack([v[:, 0], v[:, 1]], 1).ravel())
    add_index_uv(me)
    me.uv_layers.active = me.uv_layers["UVMap"]
    ob = bpy.data.objects.new("Gull", me)
    sc.collection.objects.link(ob)
    export_glb(ob, os.path.join(DEMO, "models", "gull.glb"))

    # Armature: Rumpf, Innen- und Außenflügel je Seite
    arm_data = bpy.data.armatures.new("GullRig")
    arm = bpy.data.objects.new("GullRig", arm_data)
    sc.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_data.edit_bones
    body = eb.new("body")
    body.head, body.tail = (0, -0.1, 0.01), (0, 0.1, 0.01)
    names = {}
    for side, sfx in ((1, "L"), (-1, "R")):
        win = eb.new(f"wing_in.{sfx}")
        win.head, win.tail, win.parent = (side * 0.03, 0.0, 0.012), (side * 0.33, 0.0, 0.012), body
        wout = eb.new(f"wing_out.{sfx}")
        wout.head, wout.tail, wout.parent = (side * 0.33, 0.0, 0.012), (side * 0.66, 0.0, 0.012), win
        win.roll = wout.roll = 0.0
        names[side] = (win.name, wout.name)
    bpy.ops.object.mode_set(mode="OBJECT")
    groups = {n: ob.vertex_groups.new(name=n) for n in ["body", "wing_in.L", "wing_out.L", "wing_in.R", "wing_out.R"]}
    for i, (x, y, z) in enumerate(verts):
        s = abs(x)
        if s < 0.075 or (i < len(verts) - 2 * 3 * len(st)):   # Rumpf, Kopf, Schnabel, Schwanz
            groups["body"].add([i], 1.0, "REPLACE")
            continue
        sfx = "L" if x > 0 else "R"
        w_out = min(1.0, max(0.0, (s - 0.30) / 0.06))
        w_body = min(1.0, max(0.0, (0.12 - s) / 0.09))
        w_in = 1.0 - w_out - w_body
        if w_body > 0:
            groups["body"].add([i], w_body, "REPLACE")
        if w_in > 0:
            groups[f"wing_in.{sfx}"].add([i], w_in, "REPLACE")
        if w_out > 0:
            groups[f"wing_out.{sfx}"].add([i], w_out, "REPLACE")
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = arm

    # Flügelschlag als Keyframes: Abschlag schnell, Aufschlag langsamer, Außenflügel folgt verzögert
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
    for f in range(GULL_FRAMES + 1):
        ph = 2 * math.pi * f / GULL_FRAMES
        inner = math.radians(6 + 26 * math.cos(ph))             # + = Flügel hoch (Drehung um lokale x)
        outer = math.radians(3 + 18 * math.cos(ph - 0.9))
        for side, sfx in ((1, "L"), (-1, "R")):
            pin = arm.pose.bones[f"wing_in.{sfx}"]
            pout = arm.pose.bones[f"wing_out.{sfx}"]
            # Knochen entlang ±x: lokale x-Achse = Welt -y (links) bzw. +y (rechts); +Winkel hebt beide Spitzen
            pin.rotation_euler = (inner, 0.0, 0.0)
            pout.rotation_euler = (outer, 0.0, 0.0)
            pin.keyframe_insert("rotation_euler", frame=f + 1)
            pout.keyframe_insert("rotation_euler", frame=f + 1)
        pb = arm.pose.bones["body"]
        pb.location = (0.0, 0.0, -0.025 * math.cos(ph))          # Rumpf (Knochen entlang +y: lokal z = oben)
        pb.keyframe_insert("location", frame=f + 1)

    rest = np.array(verts, np.float32)
    frames = evaluated_frames(ob, range(1, GULL_FRAMES + 1))
    pos = np.stack([f[0] for f in frames])
    nrm = np.stack([f[1] for f in frames])
    off_g = to_godot(pos - rest[None])
    nrm_g = to_godot(nrm)
    p_pos = os.path.join(DEMO, "vat", "gull_pos.exr")
    p_nrm = os.path.join(DEMO, "vat", "gull_nrm.exr")
    b_pos, b_nrm = save_exr(p_pos, off_g), save_exr(p_nrm, nrm_g)
    wing = np.array([abs(v[0]) > 0.6 for v in verts])
    tip_z = pos[:, wing, 2].mean(axis=1)
    return {
        "vertices": int(len(verts)), "triangles": int(sum(len(f) - 2 for f in faces)),
        "frames": GULL_FRAMES,
        "texture": {"pos": [int(len(verts)), GULL_FRAMES, "RGBA16F", b_pos],
                    "nrm": [int(len(verts)), GULL_FRAMES, "RGBA16F", b_nrm]},
        "offset_range_m": [float(off_g.min()), float(off_g.max())],
        "wingtip_height_m": [float(tip_z.min()), float(tip_z.max())],
        "half_check_pos_m": check_exr(p_pos, off_g), "half_check_nrm": check_exr(p_nrm, nrm_g),
    }


report = {"flag": build_flag(), "gull": build_gull()}
os.makedirs(ASSETS, exist_ok=True)
with open(os.path.join(ASSETS, "vat_report.json"), "w") as fh:
    json.dump(report, fh, indent=1, ensure_ascii=False)
print("VAT-BERICHT", json.dumps(report, ensure_ascii=False))
