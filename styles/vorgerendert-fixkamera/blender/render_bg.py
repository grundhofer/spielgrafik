"""Vorgerenderte Hintergründe für den Hafen von Lornholm (Cycles), je feste Einstellung.

Aufruf (aus dem Projektordner):
  blender -b --factory-startup -P styles/vorgerendert-fixkamera/blender/render_bg.py -- \
      --shot nah [--frames 0-89|0,10,20|none] [--still] [--dim] [--depth] [--res 1280x960] [--samples 64]

Liest die Einstellungen aus styles/vorgerendert-fixkamera/demo/shots.json (Godot-Koordinaten:
Position, Ziel, vertikaler Bildwinkel; 4:3). Baut die Szene aus shared/3d/harbor.glb (nur lesen),
ersetzt die stilneutralen Materialien nach Namen durch prozedurale Cycles-Materialien (keine Texturdateien),
setzt Abendhimmel, Laterne, Fensterlicht, Leuchtfeuer mit sichtbarem Strahl (Volumen) und rendert:

  frames   Bildfolge der Schleife (LOOP_S Sekunden, FPS Bilder/s): Wasser, Strahl, Boote, Rauch bewegen sich,
           alles periodisch, so dass Bild N wieder Bild 0 ist.
  --dim    Bild 0 ohne Laterne (für die Lichtebene: Laterne = Bild 0 - dim; flackert in Godot)
  --depth  Tiefenbild: Abstand entlang der Blickachse (wie Godots linearer Tiefenwert), 1 Strahl je Pixel
           ohne Filter, Strahl und Rauch ausgeblendet; Himmel = 10000 m.

Ausgaben nach assets/raw/render/<shot>/ (nicht im Git, rund 480 MB je Einstellung; volle Auflösung,
verkleinert wird in scripts/bake.py):
  f_0000.png ... (16 Bit, AgX), dim.png, depth.exr (32 Bit, linear), camera.json (Kamera wie gerendert).
Alles deterministisch (feste Seeds, Zeit nur aus der Bildnummer).
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Euler, Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
STYLE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(STYLE))

LOOP_S = 6.0      # Länge der Schleife in Sekunden (Strahl: eine Umdrehung)
FPS = 15          # Bildrate der Bildfolge (geht in 30 fps auf: jedes Bild 2× gezeigt)
SEED = 20261010


def gb(v):
    """Godot (x, y, z) -> Blender (x, -z, y)."""
    return Vector((v[0], -v[2], v[1]))


def bg(v):
    """Blender (x, y, z) -> Godot (x, z, -y)."""
    return [v[0], v[2], -v[1]]


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
            if k.startswith("in_"):
                nd.inputs[k[3:].replace("_", " ")].default_value = v
            else:
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
    """Dunkelt Ecken und Fugen ab (Ambient Occlusion): typisch für die Radiosity-Optik der Zeit."""
    ao = nt.node("ShaderNodeAmbientOcclusion")
    ao.inputs["Distance"].default_value = distance
    ao.samples = 8
    fac = nt.math("SUBTRACT", 1.0, ao.outputs["AO"])
    fac = nt.math("MULTIPLY", fac, amount, clamp=True)
    return nt.mix(fac, color, (0.0, 0.0, 0.0), "MULTIPLY")


# ---------------------------------------------------------------------------------------------
# Materialien (prozedural; Farben aus harbor_notes.md als Mittelwert)
# ---------------------------------------------------------------------------------------------
def mat_stone_paving():
    m, nt = new_material("R_Paving")
    v = coords(nt)
    n1 = nt.noise(v, 1.1, 3)
    n2 = nt.noise(v, 22.0, 6, 0.7)
    base = nt.ramp(n1.outputs["Fac"], [(0.3, srgb_lin("#6F6A62")), (0.7, srgb_lin("#958F84"))])
    # Fleckige Tönung je Platte (Voronoi-Zellen etwa in Plattengröße), mal wärmer, mal kühler
    cell = nt.node("ShaderNodeTexVoronoi", feature="F1")
    cell.inputs["Scale"].default_value = 1.6
    nt.link(v, cell.inputs["Vector"])
    csep = nt.node("ShaderNodeSeparateColor")
    nt.link(cell.outputs["Color"], csep.inputs["Color"])
    tint = nt.ramp(csep.outputs["Red"], [(0.0, (0.86, 0.86, 0.88)), (0.5, (1.0, 0.99, 0.97)),
                                         (1.0, (1.1, 1.05, 0.98))])
    base = nt.mix(1.0, base, tint, "MULTIPLY")
    speck = nt.ramp(n2.outputs["Fac"], [(0.35, (0.75, 0.75, 0.75)), (0.65, (1.12, 1.1, 1.05))])
    col = nt.mix(1.0, base, speck, "MULTIPLY")
    # Fugen (Geometrie 5 cm tiefer): Moos und Schmutz nach Welthöhe
    geo = nt.node("ShaderNodeNewGeometry")
    sz = nt.node("ShaderNodeSeparateXYZ")
    nt.link(geo.outputs["Position"], sz.inputs[0])
    joint = nt.math("MULTIPLY", nt.math("SUBTRACT", -0.004, sz.outputs["Z"]), 60.0, clamp=True)
    col = nt.mix(nt.math("MULTIPLY", joint, 0.8), col, srgb_lin("#3E4030"))
    # Pfützen: glattere, dunklere Flecken (fangen Laternen- und Himmelslicht)
    wet = nt.noise(v, 0.35, 2, 0.5)
    wetm = nt.math("MULTIPLY", nt.math("SUBTRACT", wet.outputs["Fac"], 0.5), 6.0, clamp=True)
    col = nt.mix(nt.math("MULTIPLY", wetm, 0.35), col, (0.0, 0.0, 0.0))
    rough = nt.math("SUBTRACT", 0.62, nt.math("MULTIPLY", wetm, 0.45))
    col = ao_dirt(nt, col, 0.2, 0.4)
    principled(nt, col, rough, bump(nt, n2.outputs["Fac"], 0.25))
    return m


def mat_fieldstone(name, base_hex, mortar_hex, scale=3.2):
    """Bruchsteinmauer: Voronoi-Steine mit Mörtelfugen (Objektkoordinaten in Metern)."""
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
    stone = nt.ramp(sep.outputs["Red"], [(0.0, srgb_lin("#6E675C")), (0.5, srgb_lin(base_hex)),
                                         (1.0, srgb_lin("#A69E8E"))])
    grain = nt.noise(coords(nt), 14.0, 5, 0.65)
    stone = nt.mix(0.35, stone, nt.ramp(grain.outputs["Fac"], [(0.3, (0.7, 0.7, 0.7)), (0.7, (1.1, 1.1, 1.1))]),
                   "MULTIPLY")
    edge = vor.outputs["Distance"]
    mortar_mask = nt.math("LESS_THAN", edge, 0.045)
    col = nt.mix(mortar_mask, stone, srgb_lin(mortar_hex))
    col = ao_dirt(nt, col, 0.3, 0.5)
    h = nt.math("MULTIPLY", nt.math("MINIMUM", edge, 0.12), 8.0)
    h = nt.math("ADD", h, nt.math("MULTIPLY", grain.outputs["Fac"], 0.25))
    principled(nt, col, 0.85, bump(nt, h, 0.6))
    return m


def mat_stone_dark():
    m, nt = new_material("R_StoneDark")
    v = coords(nt)
    n1 = nt.noise(v, 2.0, 4)
    n2 = nt.noise(v, 18.0, 6, 0.7)
    col = nt.ramp(n1.outputs["Fac"], [(0.3, srgb_lin("#47443F")), (0.7, srgb_lin("#66625A"))])
    col = nt.mix(0.5, col, nt.ramp(n2.outputs["Fac"], [(0.3, (0.75, 0.75, 0.75)), (0.7, (1.1, 1.1, 1.1))]),
                 "MULTIPLY")
    # Algen und Nässe unterhalb der Wasserlinie (Blender-Z < -0,35)
    geo = nt.node("ShaderNodeNewGeometry")
    sz = nt.node("ShaderNodeSeparateXYZ")
    nt.link(geo.outputs["Position"], sz.inputs[0])
    wetline = nt.math("MULTIPLY", nt.math("SUBTRACT", -0.25, sz.outputs["Z"]), 3.0, clamp=True)
    col = nt.mix(wetline, col, srgb_lin("#26301F"))
    rough = nt.math("SUBTRACT", 0.85, nt.math("MULTIPLY", wetline, 0.6))
    col = ao_dirt(nt, col, 0.3, 0.55)
    principled(nt, col, rough, bump(nt, n2.outputs["Fac"], 0.35))
    return m


def mat_wood(name, c0, c1, rough=0.75, stretch=(0.25, 0.25, 6.0)):
    m, nt = new_material(name)
    v = coords(nt, scale=stretch)
    grain = nt.noise(v, 6.0, 8, 0.6, distortion=1.5)
    col = nt.ramp(grain.outputs["Fac"], [(0.35, srgb_lin(c0)), (0.65, srgb_lin(c1))])
    big = nt.noise(coords(nt), 1.5, 2)
    col = nt.mix(nt.math("MULTIPLY", big.outputs["Fac"], 0.5), col, srgb_lin(c0))
    col = ao_dirt(nt, col, 0.25, 0.6)
    principled(nt, col, rough, bump(nt, grain.outputs["Fac"], 0.3))
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
    br.inputs["Mortar Size"].default_value = 0.012
    br.inputs["Brick Width"].default_value = 0.32
    br.inputs["Row Height"].default_value = 0.16
    br.inputs["Color1"].default_value = (*srgb_lin("#3E4652"), 1)
    br.inputs["Color2"].default_value = (*srgb_lin("#55606E"), 1)
    br.inputs["Mortar"].default_value = (*srgb_lin("#1E2228"), 1)
    nt.link(v, br.inputs["Vector"])
    n = nt.noise(coords(nt), 9.0, 5)
    col = nt.mix(0.4, br.outputs["Color"], nt.ramp(n.outputs["Fac"], [(0.3, (0.75, 0.78, 0.8)),
                                                                      (0.7, (1.1, 1.1, 1.1))]), "MULTIPLY")
    col = ao_dirt(nt, col, 0.3, 0.5)
    principled(nt, col, 0.6, bump(nt, br.outputs["Fac"], 0.4))
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
    """Wasser: dunkel, glänzend; Wellen als Summe periodischer Bänder -> nahtlose Schleife."""
    m, nt = new_material("R_Water")
    geo = nt.node("ShaderNodeNewGeometry")
    h = None
    # (Richtung in Grad, Wellenlänge m, Amplitude, Umläufe je Schleife)
    waves = [(80, 5.0, 1.0, 2), (115, 3.1, 0.6, 3), (40, 1.9, 0.45, 4), (150, 1.15, 0.3, 5), (10, 0.7, 0.18, 7)]
    for i, (deg, lam, amp, cycles) in enumerate(waves):
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
    # Feine Kräuselung: 4D-Rauschen auf einem Kreis in (W, Versatz) -> periodisch
    off = nt.node("ShaderNodeCombineXYZ")
    state["water_circle"] = off
    pos = nt.vmath("ADD", geo.outputs["Position"], off.outputs[0])
    rn = nt.noise(pos, 3.5, 3, 0.5, dims="4D")
    state["water_w"] = rn.inputs["W"]
    h = nt.math("ADD", h, nt.math("MULTIPLY", rn.outputs["Fac"], 0.5))
    # weiter weg flacher (sonst flimmert das Meer in 320×240)
    cam = nt.node("ShaderNodeCameraData")
    fade = nt.math("SUBTRACT", 1.0, nt.math("MULTIPLY", nt.math("SUBTRACT", cam.outputs["View Z Depth"], 30.0),
                                             1 / 120.0, clamp=True))
    strength = nt.math("MULTIPLY", fade, 0.35)
    b = nt.node("ShaderNodeBump")
    b.inputs["Distance"].default_value = 0.05
    nt.link(strength, b.inputs["Strength"])
    nt.link(h, b.inputs["Height"])
    p = principled(nt, srgb_lin("#1C3A44"), 0.07, b.outputs["Normal"], spec=0.6)
    p.inputs["IOR"].default_value = 1.33
    return m


def build_materials(state):
    mats = {
        "Stone": mat_stone_paving(),
        "StoneDark": mat_stone_dark(),
        "Wood": mat_wood("R_Wood", "#6E4B2E", "#9C7652"),
        "WoodDark": mat_wood("R_WoodDark", "#2E2016", "#4E3726", 0.6),
        "WhitePaint": mat_paint("R_WhitePaint", "#E3DED2", "#8A7F70", 0.28, 0.5),
        "RedPaint": mat_paint("R_RedPaint", "#A3271F", "#5A4A3E", 0.3, 0.5),
        "Roof": mat_roof(),
        "Rope": mat_simple_noise("R_Rope", "#8F7A55", "#C4AE82", 30.0, 0.95, 0.6),
        "Metal": mat_rust(),
        "Rock": mat_simple_noise("R_Rock", "#4F4B46", "#7A746B", 2.5, 0.9, 0.7),
        "Sand": mat_simple_noise("R_Sand", "#9C8A68", "#C2AE88", 12.0, 0.95, 0.2),
        "Grass": mat_simple_noise("R_Grass", "#3D4A2A", "#66763F", 6.0, 0.95, 0.4),
        "Water": mat_water(state),
    }
    cottage_wall = mat_fieldstone("R_Fieldstone", "#8A8273", "#B4AD9D")
    glass = {}
    for obj, (hexc, strength) in {"LanternGlass": ("#FFC46A", 6.0), "CottageWindow": ("#FFB45C", 4.0),
                                  "LighthouseLamp": ("#FFE0A0", 12.0)}.items():
        glass[obj] = mat_glass("R_Glass_" + obj, hexc, strength)
    state["glass"] = glass
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
            else:
                print("WARNUNG: Material ohne Ersatz:", name, ob.name)


# ---------------------------------------------------------------------------------------------
# Himmel
# ---------------------------------------------------------------------------------------------
SUNSET_DIR = Vector((0.30, 1.0, 0.0)).normalized()   # Blender: Richtung des Nachglühens (hinten, leicht rechts)
SKY_LIGHT = 3.0                                      # Stärke des Himmels als Lichtquelle (sichtbar bleibt 1,0)
LANTERN_W = 90.0


def build_world():
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
    el = nt.math("ABSOLUTE", sep.outputs["Z"])               # sin(Höhe); unter dem Horizont gespiegelt
    toward = nt.vmath("DOT_PRODUCT", d, tuple(SUNSET_DIR))     # -1..1, 1 = Richtung Nachglühen
    glow_az = nt.math("POWER", nt.math("MULTIPLY", nt.math("ADD", toward, 1.0), 0.5, clamp=True), 2.0)
    # Grundverlauf nach Höhe
    sky = nt.ramp(nt.math("POWER", nt.math("MAXIMUM", el, 0.0), 0.55),
                  [(0.0, srgb_lin("#C7774A")), (0.12, srgb_lin("#A0607A")), (0.3, srgb_lin("#4C3F72")),
                   (0.6, srgb_lin("#1B2550")), (1.0, srgb_lin("#0B1230"))])
    # Orangefarbenes Band am Horizont, stärker zum Nachglühen
    band = nt.math("POWER", nt.math("SUBTRACT", 1.0, nt.math("MULTIPLY", nt.math("MAXIMUM", el, 0.0), 9.0,
                                                               clamp=True)), 3.0)
    band = nt.math("MULTIPLY", band, nt.math("ADD", 0.25, nt.math("MULTIPLY", glow_az, 1.6)))
    sky = nt.mix(nt.math("MINIMUM", band, 1.0), sky, srgb_lin("#FF9A45"), "SCREEN")
    # Wolken: flache Schichtwolken, Ebenenprojektion (d.xy / d.z), nur über dem Horizont
    comb = nt.node("ShaderNodeCombineXYZ")
    proj = nt.vmath("DIVIDE", d, comb.outputs[0])
    zc = nt.math("MAXIMUM", el, 0.02)
    for i in range(3):
        nt.link(zc, comb.inputs[i])
    proj = nt.vmath("MULTIPLY", proj, (0.55, 0.55, 0.0))
    proj = nt.vmath("MULTIPLY", proj, (1.0, 3.2, 1.0))      # in Blickrichtung (Y) gestaucht: lange Bänder
    cn = nt.noise(proj, 1.3, 6, 0.62)
    cm = nt.math("MULTIPLY", nt.math("SUBTRACT", cn.outputs["Fac"], 0.5), 5.0, clamp=True)
    cm = nt.math("MULTIPLY", cm, nt.math("MULTIPLY", nt.math("SUBTRACT", el, 0.015), 25.0, clamp=True))
    cm = nt.math("MULTIPLY", cm, nt.math("SUBTRACT", 1.0, nt.math("MULTIPLY", nt.math("SUBTRACT", el, 0.25), 4.0,
                                                                    clamp=True)))
    lit = nt.math("MULTIPLY", nt.math("ADD", 0.25, glow_az), nt.math("SUBTRACT", 1.0, nt.math("MULTIPLY", el, 4.0,
                                                                                            clamp=True)))
    cloud_col = nt.mix(nt.math("MINIMUM", lit, 1.0), srgb_lin("#3A3550"), srgb_lin("#E07A5A"))
    sky_cam = nt.mix(nt.math("MULTIPLY", cm, 0.85), sky, cloud_col)
    # Sterne: nur im oberen Teil, schwach
    vor = nt.node("ShaderNodeTexVoronoi", feature="F1")
    vor.inputs["Scale"].default_value = 160.0
    vor.inputs["Randomness"].default_value = 1.0
    nt.link(d, vor.inputs["Vector"])
    star = nt.math("LESS_THAN", vor.outputs["Distance"], 0.045)
    star = nt.math("MULTIPLY", star, nt.math("MULTIPLY", nt.math("SUBTRACT", el, 0.3), 3.0, clamp=True))
    star = nt.math("MULTIPLY", star, nt.math("SUBTRACT", 1.0, cm))
    sky_cam = nt.mix(nt.math("MULTIPLY", star, 0.7), sky_cam, (1.0, 0.95, 0.85), "ADD")
    # Wolken und Sterne nur über dem Horizont (unter dem Horizont liegt nur der ferne Meeresrand)
    above = nt.math("GREATER_THAN", sep.outputs["Z"], 0.0)
    sky_cam = nt.mix(above, sky, sky_cam)
    # Kamera- und Spiegelstrahlen sehen Wolken und Sterne; das Licht für die Szene kommt aus dem glatten
    # Verlauf, verstärkt (SKY_LIGHT), damit die Schattenseiten nicht absaufen
    lp = nt.node("ShaderNodeLightPath")
    seen = nt.math("MAXIMUM", lp.outputs["Is Camera Ray"], lp.outputs["Is Glossy Ray"])
    b_cam = nt.node("ShaderNodeBackground")
    nt.link(sky_cam, b_cam.inputs["Color"])
    b_lit = nt.node("ShaderNodeBackground")
    nt.link(sky, b_lit.inputs["Color"])
    b_lit.inputs["Strength"].default_value = SKY_LIGHT
    ms = nt.node("ShaderNodeMixShader")
    nt.link(seen, ms.inputs[0])
    nt.link(b_lit.outputs[0], ms.inputs[1])
    nt.link(b_cam.outputs[0], ms.inputs[2])
    out = nt.node("ShaderNodeOutputWorld")
    nt.link(ms.outputs[0], out.inputs["Surface"])
    return w, b_cam


# ---------------------------------------------------------------------------------------------
# Lichter, Strahl, Rauch
# ---------------------------------------------------------------------------------------------
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


def build_lights(state):
    W = lambda n: bpy.data.objects[n].matrix_world.translation.copy()
    # Restlicht der untergegangenen Sonne: sehr flach von hinten rechts, warm, schwach
    sun_dir = Vector((-0.25, -1.0, -0.06)).normalized()   # Ausbreitungsrichtung (zur Kamera, leicht nach unten)
    add_light("DuskSun", "SUN", (0, 0, 50), 1.5, "#FF9C5A", size=4.0,
              rot=sun_dir.to_track_quat("-Z", "Y").to_euler())
    state["lantern"] = add_light("Lantern", "POINT", W("LanternLight"), LANTERN_W, "#FFB25E", 0.06)
    # Fensterlicht: Flächenlichter direkt vor den Scheiben, nach außen gerichtet
    cw = W("CottageWindow")
    add_light("WindowFront", "AREA", cw + Vector((0, -0.06, 0)), 35.0, "#FFB060", (0.8, 0.9),
              rot=Euler((math.radians(-90), 0, 0)))
    # Seitenfenster an der +X-Giebelwand (Glasmitte Blender (-6,585 | 1,15 | 1,5)), Licht nach +X
    add_light("WindowSide", "AREA", Vector((-6.525, 1.15, 1.5)), 15.0, "#FFB060", (0.6, 0.7),
              rot=Euler((0, math.radians(-90), 0)))
    lh = W("LighthouseLight")
    state["lh_point"] = add_light("LighthousePoint", "POINT", lh, 300.0, "#FFE2A8", 0.4)

    # Sichtbarer Strahl: Kegel mit reinem Emissionsvolumen, dreht um das Leuchtfeuer
    rotor = link_obj(bpy.data.objects.new("BeamRotor", None))
    rotor.location = lh
    L = 34.0
    bpy.ops.mesh.primitive_cone_add(vertices=40, radius1=0.35, radius2=4.2, depth=L, end_fill_type="NGON",
                                    location=(0, 0, 0))
    cone = bpy.context.active_object
    cone.name = "Beam"
    # Kegelachse lokal +Z -> horizontal nach +Y des Rotors, Spitze an der Lampe, 4° nach unten geneigt
    cone.data.transform(Matrix.Translation((0, 0, L / 2)))
    cone.parent = rotor
    cone.rotation_euler = Euler((math.radians(-90 - 4), 0, 0))
    m, nt = new_material("R_Beam")
    tc = nt.node("ShaderNodeTexCoord")
    sep = nt.node("ShaderNodeSeparateXYZ")
    nt.link(tc.outputs["Object"], sep.inputs[0])
    u = nt.math("DIVIDE", sep.outputs["Z"], L)                       # 0 an der Lampe, 1 am Ende
    rad = nt.math("ADD", 0.35, nt.math("MULTIPLY", u, 4.2 - 0.35))
    comb = nt.node("ShaderNodeCombineXYZ")
    r = nt.vmath("LENGTH", comb.outputs[0])
    nt.link(sep.outputs["X"], comb.inputs[0])
    nt.link(sep.outputs["Y"], comb.inputs[1])
    radial = nt.math("SUBTRACT", 1.0, nt.math("POWER", nt.math("DIVIDE", r, rad), 2.0), clamp=True)
    along = nt.math("POWER", nt.math("SUBTRACT", 1.0, u, clamp=True), 1.7)
    dens = nt.math("MULTIPLY", radial, along)
    em = nt.node("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*srgb_lin("#FFE3B0"), 1)
    nt.link(nt.math("MULTIPLY", dens, 0.55), em.inputs["Strength"])
    out = nt.node("ShaderNodeOutputMaterial")
    nt.link(em.outputs["Emission"], out.inputs["Volume"])
    cone.data.materials.append(m)
    cone.visible_shadow = False
    state["beam"] = cone
    state["rotor"] = rotor
    state["beam_strength"] = em.inputs["Strength"]

    # Rauch aus dem Schornstein: Volumen in einer schrägen Säule, Dichte aus wanderndem Rauschen
    cs = W("ChimneySmoke")
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=1.0, depth=1.0, location=(0, 0, 0))
    col = bpy.context.active_object
    col.name = "Smoke"
    col.data.transform(Matrix.Translation((0, 0, 0.5)))
    col.location = cs - Vector((0, 0, 0.35))
    col.scale = (1.6, 1.6, 3.4)
    m, nt = new_material("R_Smoke")
    tc = nt.node("ShaderNodeTexCoord")
    sep = nt.node("ShaderNodeSeparateXYZ")
    nt.link(tc.outputs["Object"], sep.inputs[0])
    hgt = sep.outputs["Z"]                                           # 0 unten, 1 oben (Objektraum)
    # Säule: Mitte wandert mit der Höhe nach +X (Wind), Radius wächst
    cx = nt.math("MULTIPLY", nt.math("POWER", hgt, 1.4), 1.1)
    dx = nt.math("SUBTRACT", sep.outputs["X"], cx)
    rr = nt.math("ADD", 0.10, nt.math("MULTIPLY", hgt, 0.45))
    comb = nt.node("ShaderNodeCombineXYZ")
    dist = nt.vmath("LENGTH", comb.outputs[0])
    nt.link(dx, comb.inputs[0])
    nt.link(sep.outputs["Y"], comb.inputs[1])
    core = nt.math("SUBTRACT", 1.0, nt.math("DIVIDE", dist, rr), clamp=True)
    # zwei gegeneinander überblendete Rauschfelder, die nach oben wandern (nahtlose Schleife)
    off_a = nt.node("ShaderNodeCombineXYZ")
    off_b = nt.node("ShaderNodeCombineXYZ")
    state["smoke_off"] = (off_a, off_b)
    pa = nt.vmath("SUBTRACT", tc.outputs["Object"], off_a.outputs[0])
    pb = nt.vmath("SUBTRACT", tc.outputs["Object"], off_b.outputs[0])
    na = nt.noise(nt.vmath("MULTIPLY", pa, (1.0, 1.0, 3.4)), 2.2, 4, 0.55)
    nb = nt.noise(nt.vmath("MULTIPLY", pb, (1.0, 1.0, 3.4)), 2.2, 4, 0.55)
    blend = nt.node("ShaderNodeMix")
    blend.data_type = "FLOAT"
    nt.link(na.outputs["Fac"], blend.inputs[2])
    nt.link(nb.outputs["Fac"], blend.inputs[3])
    state["smoke_blend"] = blend.inputs[0]
    n = blend.outputs[0]
    puff = nt.math("MULTIPLY", nt.math("SUBTRACT", n, 0.42), 3.0, clamp=True)
    fade = nt.math("MULTIPLY", nt.math("SUBTRACT", 1.0, hgt, clamp=True), nt.math("MULTIPLY", hgt, 12.0, clamp=True))
    dens = nt.math("MULTIPLY", nt.math("MULTIPLY", core, puff), fade)
    pv = nt.node("ShaderNodeVolumePrincipled")
    pv.inputs["Color"].default_value = (*srgb_lin("#C4C0C8"), 1)
    nt.link(nt.math("MULTIPLY", dens, 18.0), pv.inputs["Density"])
    out = nt.node("ShaderNodeOutputMaterial")
    nt.link(pv.outputs["Volume"], out.inputs["Volume"])
    col.data.materials.append(m)
    state["smoke"] = col


# ---------------------------------------------------------------------------------------------
# Zeitabhängiger Zustand (alles periodisch in LOOP_S)
# ---------------------------------------------------------------------------------------------
def set_time(state, t, cam_pos):
    ph = 2 * math.pi * t / LOOP_S
    for sock, cycles in state["water_phase"]:
        sock.default_value = cycles * ph
    R = 1.4
    state["water_circle"].inputs[0].default_value = R * math.cos(ph)
    state["water_w"].default_value = R * math.sin(ph)
    # Boote schaukeln um ihren Ursprung (Wasserlinie), Perioden = LOOP_S / ganze Zahl
    for k, name in enumerate(("BoatA", "BoatB")):
        ob = bpy.data.objects[name]
        base = state["boat_base"][name]
        roll = math.radians(2.0) * math.sin(2 * ph + 1.7 * k)
        pitch = math.radians(0.8) * math.sin(3 * ph + 0.8 + 1.7 * k)
        heave = 0.03 * math.sin(2 * ph + 2.1 + 1.7 * k)
        ob.matrix_world = Matrix.Translation((0, 0, heave)) @ base @ Euler((roll, pitch, 0)).to_matrix().to_4x4()
    # Leuchtfeuer: eine Umdrehung je Schleife; Blitz, wenn der Strahl zur Kamera zeigt
    yaw = state["beam_yaw0"] + ph
    state["rotor"].rotation_euler = (0, 0, yaw)
    beam_dir = Vector((-math.sin(yaw), math.cos(yaw), 0))
    to_cam = (cam_pos - state["rotor"].location)
    to_cam.z = 0
    facing = max(0.0, beam_dir.dot(to_cam.normalized())) ** 24
    lamp = state["glass"]["LighthouseLamp"][1]
    lamp.inputs["Emission Strength"].default_value = 12.0 + 60.0 * facing
    state["lh_point"].data.energy = 300.0 + 900.0 * facing
    # Rauch: zwei Rauschfelder wandern nach oben, Überblendung im Dreieck -> nahtlos
    u = (t % LOOP_S) / LOOP_S
    rise = 0.9  # Objektraum-Einheiten je Schleife (Säule ist 3,4 m hoch skaliert)
    off_a, off_b = state["smoke_off"]
    off_a.inputs[2].default_value = rise * u
    off_b.inputs[2].default_value = rise * (u - 1.0)
    # Feld A (bei u=0 am Start) blendet linear in Feld B über, das bei u=1 genau dort ankommt -> nahtlos
    state["smoke_blend"].default_value = u


# ---------------------------------------------------------------------------------------------
def parse_frames(s, n):
    if s in ("", "none"):
        return []
    if s == "all":
        return list(range(n))
    out = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", required=True)
    ap.add_argument("--frames", default="all")
    ap.add_argument("--dim", action="store_true")
    ap.add_argument("--depth", action="store_true")
    ap.add_argument("--res", default="1280x960")
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--out", default=None)
    ap.add_argument("--blend", default=None, help=".blend zum Nachsehen speichern (nicht einchecken)")
    a = ap.parse_args(argv)

    shots = json.load(open(os.path.join(STYLE, "demo", "shots.json")))
    shot = next(s for s in shots["shots"] if s["name"] == a.shot)
    out = a.out or os.path.join(STYLE, "assets", "raw", "render", a.shot)
    os.makedirs(out, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=os.path.join(ROOT, "shared", "3d", "harbor.glb"))
    state = {"water_phase": []}
    build_materials(state)
    world, bgn = build_world()
    build_lights(state)
    state["boat_base"] = {n: bpy.data.objects[n].matrix_world.copy() for n in ("BoatA", "BoatB")}

    sc = bpy.context.scene
    W, H = map(int, a.res.split("x"))
    cd = bpy.data.cameras.new("ShotCam")
    cd.sensor_fit = "VERTICAL"
    cd.sensor_height = 24.0
    cd.lens = 12.0 / math.tan(math.radians(shot["fov"]) / 2)
    cd.clip_start, cd.clip_end = 0.05, 3000.0
    cam = link_obj(bpy.data.objects.new("ShotCam", cd))
    cam.location = gb(shot["pos"])
    cam.rotation_euler = (gb(shot["target"]) - gb(shot["pos"])).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    bpy.context.view_layer.update()
    # Phase des Strahls in Weltzeit, für beide Einstellungen gleich: Zur Zeit beam_face_t (s) zeigt er zum
    # Bezugspunkt beam_ref (Standard: Hauptkamera aus shared/3d), so blitzt die Lampe in der Totale bei 1,0 s.
    lh = state["rotor"].location
    ref = gb(shots.get("beam_ref", [-1.8, 3.4, 14.5]))
    to_ref = ref - lh
    yaw_ref = math.atan2(-to_ref.x, to_ref.y)
    state["beam_yaw0"] = yaw_ref - 2 * math.pi * shots.get("beam_face_t", 1.0) / LOOP_S

    mw = cam.matrix_world
    C = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0)))
    basis = C @ mw.to_3x3()
    camjson = {"shot": a.shot, "fov": shot["fov"], "res": [W, H], "origin": bg(mw.translation),
               "basis_columns": [[basis[r][c] for r in range(3)] for c in range(3)],
               "loop_s": LOOP_S, "fps": FPS}
    json.dump(camjson, open(os.path.join(out, "camera.json"), "w"), indent=1)

    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    for dv in prefs.devices:
        dv.use = dv.type == "METAL"
    sc.cycles.device = "GPU"
    sc.cycles.seed = SEED
    sc.cycles.use_animated_seed = False
    sc.cycles.samples = a.samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.02
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
    sc.cycles.max_bounces = 6
    sc.cycles.diffuse_bounces = 3
    sc.cycles.glossy_bounces = 3
    sc.cycles.transmission_bounces = 2
    sc.cycles.volume_bounces = 0
    sc.cycles.sample_clamp_indirect = 6.0
    sc.cycles.volume_step_rate = 2.0
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    sc.view_settings.exposure = 1.0
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_depth = "16"
    sc.render.image_settings.color_mode = "RGB"

    n = int(round(LOOP_S * FPS))
    frames = parse_frames(a.frames, n)
    if a.blend:
        set_time(state, 0.0, cam.location)
        bpy.ops.wm.save_as_mainfile(filepath=a.blend)
    for i in frames:
        set_time(state, i / FPS, cam.location)
        sc.render.filepath = os.path.join(out, f"f_{i:04d}.png")
        bpy.ops.render.render(write_still=True)
        print(f"FRAME {i} ok", flush=True)

    if a.dim:
        set_time(state, 0.0, cam.location)
        state["lantern"].data.energy = 0.0
        g = state["glass"]["LanternGlass"][1]
        old = g.inputs["Emission Strength"].default_value
        g.inputs["Emission Strength"].default_value = 0.0
        sc.render.filepath = os.path.join(out, "dim.png")
        bpy.ops.render.render(write_still=True)
        state["lantern"].data.energy = LANTERN_W
        g.inputs["Emission Strength"].default_value = old
        print("DIM ok", flush=True)

    if a.depth:
        set_time(state, 0.0, cam.location)
        state["beam"].hide_render = True
        state["smoke"].hide_render = True
        m, nt = new_material("R_Depth")
        camd = nt.node("ShaderNodeCameraData")
        em = nt.node("ShaderNodeEmission")
        nt.link(camd.outputs["View Z Depth"], em.inputs["Strength"])
        em.inputs["Color"].default_value = (1, 1, 1, 1)
        o = nt.node("ShaderNodeOutputMaterial")
        nt.link(em.outputs["Emission"], o.inputs["Surface"])
        bpy.context.view_layer.material_override = m
        far = NT(world.node_tree)
        # Himmel = 10000 m
        for nd in list(far.n):
            far.n.remove(nd)
        b2 = far.node("ShaderNodeBackground")
        b2.inputs["Color"].default_value = (1, 1, 1, 1)
        b2.inputs["Strength"].default_value = 10000.0
        wo = far.node("ShaderNodeOutputWorld")
        far.link(b2.outputs["Background"], wo.inputs["Surface"])
        sc.cycles.samples = 1
        sc.cycles.use_adaptive_sampling = False
        sc.cycles.use_denoising = False
        sc.cycles.max_bounces = 0
        sc.cycles.filter_width = 0.01
        sc.cycles.seed = 0
        sc.view_settings.view_transform = "Standard"
        sc.view_settings.look = "None"
        sc.view_settings.exposure = 0.0
        sc.render.image_settings.file_format = "OPEN_EXR"
        sc.render.image_settings.color_depth = "32"
        sc.render.image_settings.exr_codec = "ZIP"
        sc.render.filepath = os.path.join(out, "depth.exr")
        bpy.ops.render.render(write_still=True)
        print("DEPTH ok", flush=True)
    print("RENDER_BG OK", flush=True)


main()
