"""Gemeinsame Bausteine der Blender-Skripte von iso-vorgerendert (wird von render_bg.py und render_badger.py
importiert, nicht direkt aufgerufen).

- Szenendaten aus assets/scene.json (Kamera, Kartenausschnitt, Lageänderungen, Sonne, Laufweg)
- Iso-Kamera: orthografisch, 30° Neigung, 45° Drehung; Weltpunkt -> Kartenpixel exakt wie im Godot-Skript
- prozedurale Cycles-Materialien nach Materialnamen (Grundlage: styles/vorgerendert-fixkamera/blender/render_bg.py,
  dort entwickelt und geprüft; hier für Aufsicht und harte Abendsonne angepasst)
- Licht: tiefe Abendsonne mit harten Schatten, Dämmerungshimmel, Laterne, Fensterlicht, Leuchtfeuer
"""
import json
import math
import os

import bpy
from mathutils import Euler, Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
STYLE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(STYLE))
SCENE = json.load(open(os.path.join(STYLE, "assets", "scene.json")))

CAM = SCENE["camera"]
EUL = Euler([math.radians(a) for a in CAM["euler_blender_deg"]], "XYZ")
R = EUL.to_matrix() @ Vector((1, 0, 0))     # Bild rechts (Blender)
U = EUL.to_matrix() @ Vector((0, 1, 0))     # Bild oben
D = EUL.to_matrix() @ Vector((0, 0, -1))    # Blickrichtung


def gb(v):
    """Godot (x, y, z) -> Blender (x, -z, y)."""
    return Vector((v[0], -v[2], v[1]))


def bg(v):
    return [v[0], v[2], -v[1]]


def px_per_m():
    return CAM["cycle_px"][0] / (CAM["stride_m"] * math.cos(math.radians(45)))


def map_frame():
    """Iso-Koordinaten (X0, Ytop) der linken oberen Ecke der Karte und px/m."""
    m = SCENE["map"]
    s = px_per_m()
    return m["X0"], m["Ytop_view"] + m["view_row"] / s, s


def world_to_map(p_godot):
    """Godot-Weltpunkt -> Kartenpixel (u, v), kontinuierlich (Pixel i deckt [i, i+1))."""
    X0, Yt, s = map_frame()
    p = gb(p_godot)
    return ((p.dot(R) - X0) * s, (Yt - p.dot(U)) * s)


def setup_camera(sc, size, X0, Ytop, s, ss=1, name="IsoCam"):
    """Orthografische Kamera, deren Bild (size[0] x size[1] Zielpixel, ss-fach gerendert) links oben bei den
    Iso-Koordinaten (X0, Ytop) beginnt."""
    w, h = size
    cd = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    cd.type = "ORTHO"
    cd.sensor_fit = "HORIZONTAL" if w >= h else "VERTICAL"
    cd.ortho_scale = max(w, h) / s
    cd.clip_start, cd.clip_end = 0.5, 400.0
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = bpy.data.objects.new(name, cd)
        sc.collection.objects.link(ob)
    ob.rotation_euler = EUL
    Xc, Yc = X0 + w / 2.0 / s, Ytop - h / 2.0 / s
    ob.location = Xc * R + Yc * U - 120.0 * D
    sc.camera = ob
    sc.render.resolution_x, sc.render.resolution_y = w * ss, h * ss
    sc.render.resolution_percentage = 100
    sc.render.pixel_aspect_x = sc.render.pixel_aspect_y = 1.0
    return ob


def view_depth(p_blender, cam_ob):
    """Abstand entlang der Blickachse (wie 'View Z Depth' der orthografischen Kamera)."""
    return (p_blender - cam_ob.location).dot(D)


def srgb_lin(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


# ---------------------------------------------------------------------------------------------
# Knoten-Helfer
# ---------------------------------------------------------------------------------------------
class NT:
    def __init__(self, tree):
        self.t = tree
        self.n = tree.nodes
        self.l = tree.links

    def node(self, kind, **props):
        nd = self.n.new(kind)
        for k, v in props.items():
            setattr(nd, k, v)
        return nd

    def link(self, a, b):
        self.l.new(a, b)

    def math(self, op, a, b=None, clamp=False):
        nd = self.n.new("ShaderNodeMath")
        nd.operation = op
        nd.use_clamp = clamp
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                nd.inputs[i].default_value = v
            else:
                self.l.new(v, nd.inputs[i])
        return nd.outputs[0]

    def vmath(self, op, a, b=None):
        nd = self.n.new("ShaderNodeVectorMath")
        nd.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (tuple, list, Vector)):
                nd.inputs[i].default_value = v
            else:
                self.l.new(v, nd.inputs[i])
        return nd.outputs["Value"] if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else nd.outputs["Vector"]

    def mix(self, fac, a, b, blend="MIX"):
        nd = self.n.new("ShaderNodeMix")
        nd.data_type = "RGBA"
        nd.blend_type = blend
        for sock, v in ((nd.inputs[0], fac), (nd.inputs[6], a), (nd.inputs[7], b)):
            if isinstance(v, (int, float)):
                sock.default_value = v
            elif isinstance(v, tuple):
                sock.default_value = (*v, 1.0) if len(v) == 3 else v
            else:
                self.l.new(v, sock)
        return nd.outputs[2]

    def ramp(self, fac, stops):
        nd = self.n.new("ShaderNodeValToRGB")
        self.l.new(fac, nd.inputs["Fac"])
        cr = nd.color_ramp
        while len(cr.elements) < len(stops):
            cr.elements.new(0.5)
        for el, (pos, col) in zip(cr.elements, stops):
            el.position = pos
            el.color = (*col, 1.0) if len(col) == 3 else col
        return nd.outputs["Color"]

    def noise(self, vec, scale, detail=4.0, rough=0.55, dims="3D", w=None, distortion=0.0):
        nd = self.n.new("ShaderNodeTexNoise")
        nd.noise_dimensions = dims
        nd.inputs["Scale"].default_value = scale
        nd.inputs["Detail"].default_value = detail
        nd.inputs["Roughness"].default_value = rough
        nd.inputs["Distortion"].default_value = distortion
        if vec is not None:
            self.l.new(vec, nd.inputs["Vector"])
        if w is not None:
            if isinstance(w, (int, float)):
                nd.inputs["W"].default_value = w
            else:
                self.l.new(w, nd.inputs["W"])
        return nd


def new_material(name):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = NT(m.node_tree)
    for nd in list(nt.n):
        nt.n.remove(nd)
    return m, nt


def principled(nt, color, rough, normal=None, metal=0.0, spec=0.5, emission=None, emission_strength=0.0):
    p = nt.node("ShaderNodeBsdfPrincipled")
    for sock, v in (("Base Color", color), ("Roughness", rough)):
        if isinstance(v, (int, float)):
            p.inputs[sock].default_value = v
        elif isinstance(v, tuple):
            p.inputs[sock].default_value = (*v, 1.0)
        else:
            nt.link(v, p.inputs[sock])
    p.inputs["Metallic"].default_value = metal
    p.inputs["Specular IOR Level"].default_value = spec
    if normal is not None:
        nt.link(normal, p.inputs["Normal"])
    if emission is not None:
        p.inputs["Emission Color"].default_value = (*emission, 1.0)
        p.inputs["Emission Strength"].default_value = emission_strength
    out = nt.node("ShaderNodeOutputMaterial")
    nt.link(p.outputs["BSDF"], out.inputs["Surface"])
    return p


def bump(nt, height, strength, distance=0.02):
    b = nt.node("ShaderNodeBump")
    b.inputs["Strength"].default_value = strength
    b.inputs["Distance"].default_value = distance
    nt.link(height, b.inputs["Height"])
    return b.outputs["Normal"]


def coords(nt, kind="Object", scale=(1, 1, 1)):
    tc = nt.node("ShaderNodeTexCoord")
    v = tc.outputs[kind]
    if scale != (1, 1, 1):
        v = nt.vmath("MULTIPLY", v, scale)
    return v


def ao_dirt(nt, color, distance=0.35, amount=0.55):
    """Ecken und Fugen abdunkeln (Ambient Occlusion), wie die Schmutzschicht vorgerenderter Hintergründe."""
    ao = nt.node("ShaderNodeAmbientOcclusion")
    ao.inputs["Distance"].default_value = distance
    ao.samples = 8
    fac = nt.math("SUBTRACT", 1.0, ao.outputs["AO"])
    fac = nt.math("MULTIPLY", fac, amount, clamp=True)
    return nt.mix(fac, color, (0.0, 0.0, 0.0), "MULTIPLY")


# ---------------------------------------------------------------------------------------------
# Materialien
# ---------------------------------------------------------------------------------------------
def mat_paving():
    m, nt = new_material("R_Paving")
    v = coords(nt)
    n1 = nt.noise(v, 1.1, 3)
    n2 = nt.noise(v, 22.0, 6, 0.7)
    base = nt.ramp(n1.outputs["Fac"], [(0.3, srgb_lin("#6C665D")), (0.7, srgb_lin("#948D80"))])
    cell = nt.node("ShaderNodeTexVoronoi", feature="F1")
    cell.inputs["Scale"].default_value = 1.6
    nt.link(v, cell.inputs["Vector"])
    csep = nt.node("ShaderNodeSeparateColor")
    nt.link(cell.outputs["Color"], csep.inputs["Color"])
    tint = nt.ramp(csep.outputs["Red"], [(0.0, (0.84, 0.85, 0.88)), (0.5, (1.0, 0.99, 0.97)),
                                         (1.0, (1.12, 1.06, 0.97))])
    base = nt.mix(1.0, base, tint, "MULTIPLY")
    speck = nt.ramp(n2.outputs["Fac"], [(0.35, (0.72, 0.72, 0.72)), (0.65, (1.14, 1.12, 1.06))])
    col = nt.mix(1.0, base, speck, "MULTIPLY")
    geo = nt.node("ShaderNodeNewGeometry")
    sz = nt.node("ShaderNodeSeparateXYZ")
    nt.link(geo.outputs["Position"], sz.inputs[0])
    joint = nt.math("MULTIPLY", nt.math("SUBTRACT", -0.004, sz.outputs["Z"]), 60.0, clamp=True)
    col = nt.mix(nt.math("MULTIPLY", joint, 0.85), col, srgb_lin("#33352A"))
    wet = nt.noise(v, 0.35, 2, 0.5)
    wetm = nt.math("MULTIPLY", nt.math("SUBTRACT", wet.outputs["Fac"], 0.52), 6.0, clamp=True)
    col = nt.mix(nt.math("MULTIPLY", wetm, 0.35), col, (0.0, 0.0, 0.0))
    rough = nt.math("SUBTRACT", 0.7, nt.math("MULTIPLY", wetm, 0.45))
    col = ao_dirt(nt, col, 0.2, 0.45)
    principled(nt, col, rough, bump(nt, n2.outputs["Fac"], 0.3))
    return m


def mat_fieldstone(name, base_hex, mortar_hex, scale=3.2):
    m, nt = new_material(name)
    v = coords(nt, scale=(1.0, 1.0, 1.6))
    vor = nt.node("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
    vor.inputs["Scale"].default_value = scale
    vor.inputs["Randomness"].default_value = 0.85
    nt.link(v, vor.inputs["Vector"])
    vcol = nt.node("ShaderNodeTexVoronoi", feature="F1")
    vcol.inputs["Scale"].default_value = scale
    vcol.inputs["Randomness"].default_value = 0.85
    nt.link(v, vcol.inputs["Vector"])
    sep = nt.node("ShaderNodeSeparateColor")
    nt.link(vcol.outputs["Color"], sep.inputs["Color"])
    stone = nt.ramp(sep.outputs["Red"], [(0.0, srgb_lin("#6A6357")), (0.5, srgb_lin(base_hex)),
                                         (1.0, srgb_lin("#A89F8C"))])
    grain = nt.noise(coords(nt), 14.0, 5, 0.65)
    stone = nt.mix(0.35, stone, nt.ramp(grain.outputs["Fac"], [(0.3, (0.7, 0.7, 0.7)), (0.7, (1.1, 1.1, 1.1))]),
                   "MULTIPLY")
    edge = vor.outputs["Distance"]
    mortar_mask = nt.math("LESS_THAN", edge, 0.045)
    col = nt.mix(mortar_mask, stone, srgb_lin(mortar_hex))
    col = ao_dirt(nt, col, 0.3, 0.5)
    h = nt.math("MULTIPLY", nt.math("MINIMUM", edge, 0.12), 8.0)
    h = nt.math("ADD", h, nt.math("MULTIPLY", grain.outputs["Fac"], 0.25))
    principled(nt, col, 0.85, bump(nt, h, 0.7))
    return m


def mat_stone_dark():
    m, nt = new_material("R_StoneDark")
    v = coords(nt)
    n1 = nt.noise(v, 2.0, 4)
    n2 = nt.noise(v, 18.0, 6, 0.7)
    col = nt.ramp(n1.outputs["Fac"], [(0.3, srgb_lin("#45423D")), (0.7, srgb_lin("#68635A"))])
    col = nt.mix(0.5, col, nt.ramp(n2.outputs["Fac"], [(0.3, (0.72, 0.72, 0.72)), (0.7, (1.12, 1.12, 1.12))]),
                 "MULTIPLY")
    geo = nt.node("ShaderNodeNewGeometry")
    sz = nt.node("ShaderNodeSeparateXYZ")
    nt.link(geo.outputs["Position"], sz.inputs[0])
    wetline = nt.math("MULTIPLY", nt.math("SUBTRACT", -0.25, sz.outputs["Z"]), 3.0, clamp=True)
    col = nt.mix(wetline, col, srgb_lin("#26301F"))
    rough = nt.math("SUBTRACT", 0.85, nt.math("MULTIPLY", wetline, 0.6))
    col = ao_dirt(nt, col, 0.3, 0.55)
    principled(nt, col, rough, bump(nt, n2.outputs["Fac"], 0.4))
    return m


def mat_wood(name, c0, c1, rough=0.75, stretch=(0.25, 0.25, 6.0)):
    m, nt = new_material(name)
    v = coords(nt, scale=stretch)
    grain = nt.noise(v, 6.0, 8, 0.6, distortion=1.5)
    col = nt.ramp(grain.outputs["Fac"], [(0.35, srgb_lin(c0)), (0.65, srgb_lin(c1))])
    big = nt.noise(coords(nt), 1.5, 2)
    col = nt.mix(nt.math("MULTIPLY", big.outputs["Fac"], 0.5), col, srgb_lin(c0))
    col = ao_dirt(nt, col, 0.25, 0.6)
    principled(nt, col, rough, bump(nt, grain.outputs["Fac"], 0.35))
    return m


def mat_paint(name, hex_paint, hex_under, wear=0.35, rough=0.55):
    m, nt = new_material(name)
    v = coords(nt)
    n1 = nt.noise(v, 3.0, 6, 0.6)
    chips = nt.math("MULTIPLY", nt.math("SUBTRACT", n1.outputs["Fac"], 1.0 - wear), 12.0, clamp=True)
    streak = nt.noise(coords(nt, scale=(4.0, 4.0, 0.4)), 4.0, 3)
    paint = nt.mix(nt.math("MULTIPLY", streak.outputs["Fac"], 0.35), srgb_lin(hex_paint), (0.35, 0.33, 0.3),
                   "MULTIPLY")
    col = nt.mix(chips, paint, srgb_lin(hex_under))
    col = ao_dirt(nt, col, 0.25, 0.5)
    principled(nt, col, rough, bump(nt, chips, 0.15))
    return m


def mat_roof():
    m, nt = new_material("R_Roof")
    v = coords(nt, "UV")
    br = nt.node("ShaderNodeTexBrick")
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Mortar Size"].default_value = 0.014
    br.inputs["Brick Width"].default_value = 0.32
    br.inputs["Row Height"].default_value = 0.16
    br.inputs["Color1"].default_value = (*srgb_lin("#3A424E"), 1)
    br.inputs["Color2"].default_value = (*srgb_lin("#56606E"), 1)
    br.inputs["Mortar"].default_value = (*srgb_lin("#1A1E24"), 1)
    nt.link(v, br.inputs["Vector"])
    n = nt.noise(coords(nt), 9.0, 5)
    col = nt.mix(0.4, br.outputs["Color"], nt.ramp(n.outputs["Fac"], [(0.3, (0.75, 0.78, 0.8)),
                                                                      (0.7, (1.1, 1.1, 1.1))]), "MULTIPLY")
    moss = nt.noise(coords(nt), 2.5, 4)
    mm = nt.math("MULTIPLY", nt.math("SUBTRACT", moss.outputs["Fac"], 0.58), 5.0, clamp=True)
    col = nt.mix(nt.math("MULTIPLY", mm, 0.6), col, srgb_lin("#4E5A33"))
    col = ao_dirt(nt, col, 0.3, 0.5)
    principled(nt, col, 0.65, bump(nt, br.outputs["Fac"], 0.5))
    return m


def mat_simple_noise(name, c0, c1, scale, rough, bump_s=0.3, metal=0.0, ao=0.5):
    m, nt = new_material(name)
    v = coords(nt)
    n1 = nt.noise(v, scale, 6, 0.6)
    n2 = nt.noise(v, scale * 0.15, 3)
    col = nt.ramp(n1.outputs["Fac"], [(0.3, srgb_lin(c0)), (0.7, srgb_lin(c1))])
    col = nt.mix(nt.math("MULTIPLY", n2.outputs["Fac"], 0.5), col, srgb_lin(c0))
    col = ao_dirt(nt, col, 0.3, ao)
    principled(nt, col, rough, bump(nt, n1.outputs["Fac"], bump_s), metal=metal)
    return m


def mat_rust():
    m, nt = new_material("R_Metal")
    v = coords(nt)
    n1 = nt.noise(v, 6.0, 6, 0.6)
    rust = nt.math("MULTIPLY", nt.math("SUBTRACT", n1.outputs["Fac"], 0.52), 8.0, clamp=True)
    col = nt.mix(rust, srgb_lin("#33353A"), srgb_lin("#6B3A1E"))
    rough = nt.math("ADD", 0.45, nt.math("MULTIPLY", rust, 0.45))
    metal = nt.math("SUBTRACT", 0.8, nt.math("MULTIPLY", rust, 0.8))
    p = principled(nt, col, rough, bump(nt, n1.outputs["Fac"], 0.3))
    nt.link(metal, p.inputs["Metallic"])
    return m


def mat_glass(name, color_hex, strength):
    m, nt = new_material(name)
    p = principled(nt, srgb_lin(color_hex), 0.2, emission=srgb_lin(color_hex), emission_strength=strength)
    return m, p


def mat_water(state):
    """Wasser: dunkel, glänzend; Wellen als Summe periodischer Bänder (nahtlose Schleife über state['loop_s'])."""
    m, nt = new_material("R_Water")
    geo = nt.node("ShaderNodeNewGeometry")
    h = None
    waves = [(80, 4.0, 1.0, 1), (115, 2.6, 0.6, 2), (40, 1.6, 0.45, 2), (150, 1.0, 0.3, 3), (10, 0.6, 0.2, 4)]
    for deg, lam, amp, cycles in waves:
        wv = nt.node("ShaderNodeTexWave", wave_type="BANDS", bands_direction="X", wave_profile="SIN")
        wv.inputs["Scale"].default_value = 1.0 / lam
        wv.inputs["Distortion"].default_value = 1.2
        wv.inputs["Detail"].default_value = 1.5
        wv.inputs["Detail Scale"].default_value = 1.0
        mp = nt.node("ShaderNodeMapping")
        mp.inputs["Rotation"].default_value = (0, 0, math.radians(deg))
        nt.link(geo.outputs["Position"], mp.inputs["Vector"])
        nt.link(mp.outputs["Vector"], wv.inputs["Vector"])
        state["water_phase"].append((wv.inputs["Phase Offset"], cycles))
        term = nt.math("MULTIPLY", wv.outputs["Fac"], amp)
        h = term if h is None else nt.math("ADD", h, term)
    off = nt.node("ShaderNodeCombineXYZ")
    state["water_circle"] = off
    pos = nt.vmath("ADD", geo.outputs["Position"], off.outputs[0])
    rn = nt.noise(pos, 3.0, 3, 0.5, dims="4D")
    state["water_w"] = rn.inputs["W"]
    h = nt.math("ADD", h, nt.math("MULTIPLY", rn.outputs["Fac"], 0.6))
    b = nt.node("ShaderNodeBump")
    b.inputs["Distance"].default_value = 0.05
    b.inputs["Strength"].default_value = 0.45
    nt.link(h, b.inputs["Height"])
    p = principled(nt, srgb_lin("#173540"), 0.06, b.outputs["Normal"], spec=0.6)
    p.inputs["IOR"].default_value = 1.33
    return m


def build_materials(state):
    mats = {
        "Stone": mat_paving(),
        "StoneDark": mat_stone_dark(),
        "Wood": mat_wood("R_Wood", "#6B482B", "#9E7650"),
        "WoodDark": mat_wood("R_WoodDark", "#2C1F15", "#4E3726", 0.6),
        "WhitePaint": mat_paint("R_WhitePaint", "#E3DED2", "#8A7F70", 0.28, 0.5),
        "RedPaint": mat_paint("R_RedPaint", "#A3271F", "#5A4A3E", 0.3, 0.5),
        "Roof": mat_roof(),
        "Rope": mat_simple_noise("R_Rope", "#8F7A55", "#C4AE82", 30.0, 0.95, 0.6),
        "Metal": mat_rust(),
        "Rock": mat_simple_noise("R_Rock", "#4C4843", "#7A746B", 2.5, 0.9, 0.8),
        "Sand": mat_simple_noise("R_Sand", "#9A8866", "#C2AE88", 12.0, 0.95, 0.25),
        "Grass": mat_simple_noise("R_Grass", "#36452A", "#62733E", 6.0, 0.95, 0.5),
        "Water": mat_water(state),
    }
    cottage_wall = mat_fieldstone("R_Fieldstone", "#8A8273", "#B4AD9D")
    glass = {}
    for obj, (hexc, strength) in {"LanternGlass": ("#FFC46A", 8.0), "CottageWindow": ("#FFB45C", 5.0),
                                  "LighthouseLamp": ("#FFE6B0", 14.0)}.items():
        glass[obj] = mat_glass("R_Glass_" + obj, hexc, strength)
    state["glass"] = glass
    state["mats"] = mats
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        for slot in ob.material_slots:
            if slot.material is None:
                continue
            name = slot.material.name.split(".")[0]
            if name == "Glass":
                slot.material = glass[ob.name][0]
            elif name == "Stone" and ob.name == "Cottage":
                slot.material = cottage_wall
            elif name in mats:
                slot.material = mats[name]
            elif name.startswith("R_"):
                pass
            else:
                print("WARNUNG: Material ohne Ersatz:", name, ob.name)


# ---------------------------------------------------------------------------------------------
# Himmel und Licht
# ---------------------------------------------------------------------------------------------
def sun_direction():
    """Einheitsvektor zur Sonne (Blender)."""
    s = SCENE["sun"]
    az, el = math.radians(s["azimuth_deg"]), math.radians(s["elevation_deg"])
    g = (math.cos(az) * math.cos(el), math.sin(el), -math.sin(az) * math.cos(el))
    return gb(g).normalized()


def build_world(strength=0.9):
    """Dämmerungshimmel: von oben tiefblau, zur Sonne hin orange. In der Aufsicht nur in Spiegelungen sichtbar,
    sonst Umgebungslicht (kühl) gegen die warme Sonne."""
    w = bpy.data.worlds.new("Dusk")
    bpy.context.scene.world = w
    try:
        w.use_nodes = True
    except Exception:
        pass
    nt = NT(w.node_tree)
    for nd in list(nt.n):
        nt.n.remove(nd)
    tc = nt.node("ShaderNodeTexCoord")
    d = nt.vmath("NORMALIZE", tc.outputs["Generated"])
    sep = nt.node("ShaderNodeSeparateXYZ")
    nt.link(d, sep.inputs[0])
    el = nt.math("MAXIMUM", sep.outputs["Z"], 0.0)
    sd = sun_direction()
    toward = nt.vmath("DOT_PRODUCT", d, tuple(sd))
    glow = nt.math("POWER", nt.math("MULTIPLY", nt.math("ADD", toward, 1.0), 0.5, clamp=True), 3.0)
    sky = nt.ramp(nt.math("POWER", el, 0.5), [(0.0, srgb_lin("#B86A55")), (0.2, srgb_lin("#6A4E7C")),
                                              (0.5, srgb_lin("#253262")), (1.0, srgb_lin("#101A3C"))])
    sky = nt.mix(nt.math("MULTIPLY", glow, nt.math("SUBTRACT", 1.0, el)), sky, srgb_lin("#FF9A50"), "SCREEN")
    b = nt.node("ShaderNodeBackground")
    nt.link(sky, b.inputs["Color"])
    b.inputs["Strength"].default_value = strength
    out = nt.node("ShaderNodeOutputWorld")
    nt.link(b.outputs[0], out.inputs["Surface"])
    return w, b


def link_obj(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def add_light(name, kind, loc, energy, color_hex, size=0.05, rot=None):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = srgb_lin(color_hex)
    if kind == "POINT":
        ld.shadow_soft_size = size
    elif kind == "AREA":
        ld.shape = "RECTANGLE"
        ld.size, ld.size_y = size
    elif kind == "SUN":
        ld.angle = math.radians(size)
    ob = link_obj(bpy.data.objects.new(name, ld))
    ob.location = loc
    if rot is not None:
        ob.rotation_euler = rot
    return ob


def add_sun(energy=3.0):
    """Tiefe Abendsonne mit fast punktförmiger Scheibe (0,4°): harte Schlagschatten."""
    sd = sun_direction()
    return add_light("Sun", "SUN", (0, 0, 50), energy, "#FFD6B0", size=0.4,
                     rot=(-sd).to_track_quat("-Z", "Y").to_euler())


def build_scene_lights(state, lantern_w=55.0):
    W = lambda n: bpy.data.objects[n].matrix_world.translation.copy()
    state["lantern"] = add_light("Lantern", "POINT", W("LanternLight"), lantern_w, "#FFB25E", 0.05)
    cw = W("CottageWindow")
    add_light("WindowFront", "AREA", cw + Vector((0, -0.08, 0)), 22.0, "#FFB060", (0.8, 0.9),
              rot=Euler((math.radians(-90), 0, 0)))
    add_light("WindowSide", "AREA", Vector((-6.52, 1.15, 1.5)), 10.0, "#FFB060", (0.6, 0.7),
              rot=Euler((0, math.radians(-90), 0)))
    state["lh_point"] = add_light("LighthousePoint", "POINT", W("LighthouseLight"), 60.0, "#FFE2A8", 0.2)


# ---------------------------------------------------------------------------------------------
# Lageänderungen gegenüber shared/3d (begründet in style.json)
# ---------------------------------------------------------------------------------------------
def apply_layout_changes():
    ch = SCENE["layout_changes"]
    bpy.context.view_layer.update()
    for name, spec in ch.items():
        ob = bpy.data.objects[name]
        ob.rotation_mode = "XYZ"
        if "pos" in spec:
            ob.location = gb(spec["pos"])
        if "scale" in spec:
            ob.scale = (spec["scale"],) * 3
        if "face_deg" in spec:
            ob.rotation_euler = (0, 0, math.radians(spec["face_deg"]))
    lh = ch.get("Lighthouse")
    if lh:
        # Felssockel im Wasser unter dem versetzten Leuchtturm: verzerrte Ikosphäre, Material Rock
        import bmesh
        from mathutils import noise
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
        for v in bm.verts:
            n = noise.noise(v.co * 1.7 + Vector((3.1, 1.7, 0.4)))
            v.co *= 1.0 + 0.22 * n
            v.co.x *= 1.75
            v.co.y *= 1.55
            v.co.z *= 0.95
            if v.co.z > 0.62:
                v.co.z = 0.62 + (v.co.z - 0.62) * 0.15
        me = bpy.data.meshes.new("LighthouseRock")
        bm.to_mesh(me)
        bm.free()
        for p in me.polygons:
            p.use_smooth = False
        rock = bpy.data.objects.new("LighthouseRock", me)
        link_obj(rock)
        base = gb(lh["pos"])
        rock.location = base + Vector((0.0, 0.0, -0.66))
        rock.data.materials.append(bpy.data.materials.get("Rock") or bpy.data.materials.new("Rock"))
    bpy.context.view_layer.update()


def import_harbor():
    bpy.ops.import_scene.gltf(filepath=os.path.join(ROOT, "shared", "3d", "harbor.glb"))


def cycles_setup(sc, samples=64, gpu=True, denoise=True):
    sc.render.engine = "CYCLES"
    if gpu:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        for dv in prefs.devices:
            dv.use = dv.type == "METAL"
        sc.cycles.device = "GPU"
    sc.cycles.seed = 20261013
    sc.cycles.use_animated_seed = False
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.02
    sc.cycles.use_denoising = denoise
    if denoise:
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
    sc.cycles.max_bounces = 6
    sc.cycles.diffuse_bounces = 3
    sc.cycles.glossy_bounces = 3
    sc.cycles.transmission_bounces = 2
    sc.cycles.volume_bounces = 0
    sc.cycles.sample_clamp_indirect = 6.0
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = 0.0
    sc.view_settings.gamma = 1.0
    sc.render.dither_intensity = 0.0
