"""Dachs-Kurier für Ligne-claire-Sprites rendern: Farb- und Tiefenpass je Bild, ohne Licht, ohne Kantenglättung.

    blender -b --factory-startup -P styles/ligne-claire/blender/render_badger.py -- \
        --glb shared/3d/badger.glb --out styles/ligne-claire/assets/raw/render [--ppm 600] [--only walk,turn]

Die Konturen entstehen danach in scripts/ink_badger.py aus den Pässen (Farbgrenzen + Tiefensprünge, eine feste
Linienstärke). Freestyle wurde getestet und verworfen: Es übersieht Grenzen zwischen sich durchdringenden Teilen
(Schal/Weste, Gesichtsstreifen) und zeichnet ungleichmäßig.
Vor beiden Pässen: Subdivision Surface (Stufe --subsurf) hinter dem Armature-Modifier und Smooth Shading, damit die
Umrisse rund statt facettiert sind; die Pfoten bekommen über das Handgewicht eine eigene Renderfarbe (Linie am
Handgelenk).

Ausgabe je Bild: <reihe>_<nn>_col.png (RGBA, Palettenfarben exakt, 8 bit) und <reihe>_<nn>_z.png (16 bit Grau,
Kameratiefe), dazu render.json mit Maßstab, Fußpunkt und Fußpositionen (aus den Knochen) je Bild.
Alle Bilder nutzen dieselbe orthografische Kamera: 1 px = 1/ppm m, der Ursprung der Figur liegt immer auf
demselben Pixel.

Reihen:
  walk   Walk (1,0 s) in N gleichmäßigen Bildern, Seitenansicht (Blick nach +X = rechts)
  turn   Idle-Pose (t = 0), Drehung von 0° auf -TURN° (zur Kamera) in 5 Bildern (Bild 0 = Stand seitlich)
  wave   Wave (1,5 s) bei 15 Bildern/s, gedreht um -TURN°
  idle   Idle (2,0 s) bei 15 Bildern/s, gedreht um -TURN°
"""
import argparse, json, math, pathlib, sys

import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--glb", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--ppm", type=float, default=600.0, help="Pixel pro Meter im Render")
ap.add_argument("--walk-frames", type=int, default=10)
ap.add_argument("--turn", type=float, default=55.0, help="Drehung zur Kamera in Grad")
ap.add_argument("--tilt", type=float, default=5.0, help="Kamera schaut so viele Grad von oben")
ap.add_argument("--only", default="walk,turn,wave,idle")
ap.add_argument("--preset", default="full", choices=["full", "cu"], help="Bildfeld: ganze Figur oder Brustbild")
ap.add_argument("--snap", type=int, default=3, help="Fußpunkt auf Vielfache dieses Werts legen (= Verkleinerung)")
ap.add_argument("--subsurf", type=int, default=2,
                help="Subdivision-Surface-Stufe hinter dem Armature-Modifier (0 = aus): runde Umrisse statt Facetten")
a = ap.parse_args(argv)

out = pathlib.Path(a.out)
out.mkdir(parents=True, exist_ok=True)

# Flache Ligne-claire-Palette (sRGB). Das dunkle Fell als Schiefergrau statt Schwarz, damit die schwarze Kontur
# lesbar bleibt; Weste und Mütze in zwei klar getrennten Grüns.
PALETTE = {
    "FurDark": "5d5c66", "FurLight": "f7f2e6", "Cap": "2f6440", "Brass": "e3b23c", "Vest": "3f7d4d",
    "Shirt": "ead9a8", "Scarf": "d0392b", "Satchel": "8e4d2b", "Parcel": "d9a463", "Nose": "1c1c1e",
    # Auge: eigene Renderfarbe (sonst nicht von der Nase zu unterscheiden, der Tusche-Pass braucht es getrennt für
    # --face-simple), gefüllt wie die Nase.
    "Eye": "1c1c4a",
    # Pfoten: eigene Palettennummer (das Fellmaterial schaltet über das Handgewicht um, siehe unten), damit der
    # Tusche-Pass am Handgelenk eine Linie zieht. Renderfarbe nur zur Unterscheidung, gefüllt wird mit FurDark
    # (FILL_AS, ink_badger.py).
    "Paw": "6b6a75",
}
FILL_AS = {"Paw": "FurDark", "Eye": "Nose"}


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_lin(h):
    return [srgb_to_linear(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4)] + [1.0]


bpy.ops.wm.read_factory_settings(use_empty=True)
# merge_vertices: glTF trennt Punkte an Normalen-/UV-Nähten; ungetrennt reißt die Subdivision dort nicht auf.
bpy.ops.import_scene.gltf(filepath=a.glb, merge_vertices=a.subsurf > 0)
scene = bpy.context.scene
for ob in list(bpy.data.objects):
    if ob.name.startswith("Icosphere"):          # Knochenanzeige des Importers, wird nicht gebraucht
        bpy.data.objects.remove(ob)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
arm.rotation_mode = "XYZ"                                 # Import setzt Quaternionen; Drehung unten über Euler

# Runde Konturen: Das gemeinsame Modell ist für Echtzeit facettiert (10-eckige Arme, kantige Mützenschirme). Für
# Ligne claire Dreiecke zu Vierecken zusammenfassen (nur innerhalb eines Materials, damit Farbgrenzen bleiben),
# Smooth Shading und Subdivision Surface hinter dem Armature-Modifier: erst verformen, dann glätten.
# Pfoten: Das Modell hat am Handgelenk keine Material- oder Geometriekante, der Arm endet sonst als grauer Stumpf.
# Die Handgewichte der Knochen werden als Punktattribut "hand_w" gespeichert; das Fellmaterial schaltet bei
# hand_w > 0,5 auf die Hilfsfarbe "Paw" um. Die Grenze ist die Höhenlinie des (durch die Subdivision geglätteten)
# Gewichts und damit ein runder Ring ums Handgelenk; eine Zuordnung über ganze Flächen ergab eine Zickzacklinie.
for ob in bpy.data.objects:
    if ob.type != "MESH" or "hand.L" not in ob.vertex_groups or "FurDark" not in [m.name for m in ob.data.materials if m]:
        continue                                          # Paket hängt auch an der Hand, hat aber kein Fell
    gi = {ob.vertex_groups[n].index for n in ("hand.L", "hand.R")}
    w_hand = [min(1.0, sum(g.weight for g in v.groups if g.group in gi)) for v in ob.data.vertices]
    at = ob.data.attributes.new("hand_w", "FLOAT", "POINT")
    at.data.foreach_set("value", w_hand)
    print("Pfoten:", ob.name, sum(w > 0.5 for w in w_hand), "Punkte mit Handgewicht > 0,5")

if a.subsurf > 0:
    import bmesh
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bmesh.ops.join_triangles(bm, faces=bm.faces[:], cmp_materials=True, cmp_seam=False, cmp_sharp=False,
                                 cmp_uvs=False, cmp_vcols=False, angle_face_threshold=math.radians(40),
                                 angle_shape_threshold=math.radians(40))
        bm.to_mesh(ob.data)
        bm.free()
        ob.data.shade_smooth()
        sub = ob.modifiers.new("Subdivision", "SUBSURF")
        sub.levels = sub.render_levels = a.subsurf
        print("Subdivision", ob.name, [m.type for m in ob.modifiers], len(ob.data.polygons), "Flächen")


def emission_material(name, color=None):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    nt = m.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], o.inputs[0])
    if color:
        em.inputs["Color"].default_value = color
    return m, nt, em


missing = []
for m in list(bpy.data.materials):
    if m.name in PALETTE:
        emission_material(m.name, hex_lin(PALETTE[m.name]))
    else:
        missing.append(m.name)
if missing:
    print("WARNUNG: Material ohne Palettenfarbe:", missing)
# Fell: hand_w > 0,5 -> Pfotenfarbe (harte Schwelle, keine Mischfarbe; der Tusche-Pass zieht dort die Linie)
_m, _nt, _em = emission_material("FurDark")
_at = _nt.nodes.new("ShaderNodeAttribute")
_at.attribute_name = "hand_w"
_gt = _nt.nodes.new("ShaderNodeMath")
_gt.operation = "GREATER_THAN"
_gt.inputs[1].default_value = 0.5
_mix = _nt.nodes.new("ShaderNodeMix")
_mix.data_type = "RGBA"
_mix.inputs["A"].default_value = hex_lin(PALETTE["FurDark"])
_mix.inputs["B"].default_value = hex_lin(PALETTE["Paw"])
_nt.links.new(_at.outputs["Fac"], _gt.inputs[0])
_nt.links.new(_gt.outputs[0], _mix.inputs["Factor"])
_nt.links.new(_mix.outputs["Result"], _em.inputs["Color"])

# Tiefenmaterial: Kameratiefe (View Z) linear auf 0..1 um die Figur, ausgegeben als 16-bit-Grau im Raw-Farbraum.
D_CAM = 20.0
Z_NEAR, Z_RANGE = D_CAM - 1.5, 3.0
zmat, znt, zem = emission_material("DepthPass")
cd = znt.nodes.new("ShaderNodeCameraData")
mr = znt.nodes.new("ShaderNodeMapRange")
mr.inputs["From Min"].default_value = Z_NEAR
mr.inputs["From Max"].default_value = Z_NEAR + Z_RANGE
znt.links.new(cd.outputs["View Z Depth"], mr.inputs["Value"])
znt.links.new(mr.outputs["Result"], zem.inputs["Color"])

scene.world = bpy.data.worlds.new("W")
scene.world.color = (0, 0, 0)
scene.render.engine = "BLENDER_EEVEE"
scene.eevee.taa_render_samples = 1
scene.render.filter_size = 0.0                          # keine Kantenglättung: Grenzen pixelgenau
scene.render.film_transparent = True
scene.render.image_settings.file_format = "PNG"
scene.render.fps = 24                                   # glTF-Import legt die Aktionen auf 24 fps an

# Kamera: orthografisch, Blick von -Y nach +Y (Godot: von +Z), um tilt Grad nach unten geneigt.
# Bildfeld in Metern (Breite, Höhe, Unterkante vor der Neigung): ganze Figur oder Brustbild für das Nahaufnahme-Panel.
PRESETS = {"full": (1.40, 1.45, -0.18), "cu": (0.667, 0.76, 0.47)}
W_M, H_M, Z0 = PRESETS[a.preset]
res_x, res_y = round(W_M * a.ppm), round(H_M * a.ppm)
scene.render.resolution_x, scene.render.resolution_y = res_x, res_y
scene.render.resolution_percentage = 100
cam_data = bpy.data.cameras.new("Cam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = max(W_M, H_M)
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
t = math.radians(a.tilt)
center = Vector((0.0, 0.0, Z0 + H_M / 2))
cam.location = center + Vector((0, -D_CAM * math.cos(t), D_CAM * math.sin(t)))
cam.rotation_euler = (math.pi / 2 - t, 0, 0)
cam_data.clip_start, cam_data.clip_end = 0.1, 100.0
bpy.context.view_layer.update()


def project(p):
    """Weltpunkt -> Pixel (x nach rechts, y nach unten) im Render."""
    v = world_to_camera_view(scene, cam, p)
    return [v.x * res_x, (1 - v.y) * res_y]


# Kamera so verschieben, dass der Fußpunkt der Figur genau auf einer Pixelecke liegt, deren Koordinaten Vielfache
# von --snap sind. Dann bleibt er nach dem Verkleinern um diesen Faktor ganzzahlig (Sprites ohne Subpixel-Versatz).
for _ in range(3):
    ox, oy = project(Vector((0, 0, 0)))
    tx, ty = round(ox / a.snap) * a.snap, round(oy / a.snap) * a.snap
    span = max(res_x, res_y)
    cam_data.shift_x += (ox - tx) / span
    cam_data.shift_y -= (oy - ty) / span
    bpy.context.view_layer.update()


def set_pose(action, seconds, rot_deg):
    arm.animation_data.action = action
    f = seconds * scene.render.fps
    scene.frame_set(int(math.floor(f)), subframe=f - math.floor(f))
    arm.rotation_euler = (0, 0, math.radians(rot_deg))
    bpy.context.view_layer.update()


def render(path, depth):
    vl = scene.view_layers[0]
    if depth:
        vl.material_override = zmat
        scene.view_settings.view_transform = "Raw"
        scene.render.image_settings.color_mode = "BW"
        scene.render.image_settings.color_depth = "16"
    else:
        vl.material_override = None
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"
        scene.render.image_settings.color_mode = "RGBA"
        scene.render.image_settings.color_depth = "8"
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


info = {"ppm": a.ppm, "tilt": a.tilt, "preset": a.preset, "field_m": [W_M, H_M, Z0], "size": [res_x, res_y], "origin_px": project(Vector((0, 0, 0))),
        "depth": {"near": Z_NEAR, "range": Z_RANGE}, "palette": PALETTE, "fill_as": FILL_AS, "subsurf": a.subsurf,
        "rows": {}}
print("Ursprung im Bild:", info["origin_px"])

acts = {x.name: x for x in bpy.data.actions}
rows = []
if "walk" in a.only:
    n = a.walk_frames
    rows.append(("walk", [(acts["Walk"], i / n, 0.0) for i in range(n)]))
if "turn" in a.only:
    rows.append(("turn", [(acts["Idle"], 0.0, -a.turn * k / 4) for k in range(0, 5)]))
if "wave" in a.only:
    rows.append(("wave", [(acts["Wave"], i / 15, -a.turn) for i in range(int(1.5 * 15) + 1)]))
if "idle" in a.only:
    rows.append(("idle", [(acts["Idle"], i / 15, -a.turn) for i in range(30)]))

for name, poses in rows:
    feet = []
    for i, (act, sec, rot) in enumerate(poses):
        set_pose(act, sec, rot)
        fr = {}
        for side in ("L", "R"):
            pb = arm.pose.bones["foot." + side]
            h, tl = arm.matrix_world @ pb.head, arm.matrix_world @ pb.tail
            fr[side] = {"heel_px": project(h), "toe_px": project(tl), "heel_m": list(h), "toe_m": list(tl)}
        hb = arm.pose.bones["head"]           # Kopfknochen (Halsansatz bis Scheitel): Gesichtsbereich für den Tusche-Pass
        fr["head_px"] = [project(arm.matrix_world @ hb.head), project(arm.matrix_world @ hb.tail)]
        feet.append(fr)
        render(out / f"{name}_{i:02d}_col.png", False)
        render(out / f"{name}_{i:02d}_z.png", True)
    info["rows"][name] = {"frames": len(poses), "poses": [[p[0].name, p[1], p[2]] for p in poses], "feet": feet}
    print("Reihe", name, len(poses))

(out / "render.json").write_text(json.dumps(info, indent=1))
print("fertig:", out)
