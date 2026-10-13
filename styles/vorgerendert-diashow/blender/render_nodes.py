"""Knotenansichten des Hafens von Lornholm wie frühe CGI rendern (Cycles, Raytracing, harte Schatten).

Aufruf (aus dem Projektordner):
  blender -b --factory-startup -P styles/vorgerendert-diashow/blender/render_nodes.py -- \
      --node steg --what loop|badger|still [--frames 0-29|all] [--samples 48] [--out DIR] [--res 544x332]

Look „frühe CGI um 1993–1997“ statt moderner Physik:
  - keine indirekte diffuse Beleuchtung (diffuse_bounces = 0) und kein Himmelslicht auf Flächen;
    stattdessen ein konstanter Umgebungsanteil je Material (Emission = Grundfarbe × AMBIENT), wie das
    „ambient“-Glied im Phong-Modell der Zeit
  - Lichter ohne Ausdehnung (Sonne angle = 0, Punktlichter radius = 0): harte Schatten der Hauptsonne, dazu eine
    schwache, ebenfalls schattenwerfende Gegensonne (zweiter, blasser Schatten)
  - Messung der Schatten: --no-shadow key|fill rendert dieselbe Ansicht ohne den Schatten einer Sonne
    (scripts/measure_shadows.py); SETTINGS-Zeile im Log nennt Samples, Bounces und Lichter
  - glatte, glänzende Oberflächen, klare Spiegelungen (Wasser fast Spiegel, Metall verchromt)
  - prozedurale Materialien ohne Schmutz: Brick-Knoten (Pflaster, Mauer, Schiefer), Wave-Knoten (Holzmaserung)
  - Farbumsetzung „Standard“ (hartes Clipping), keine Entrauschung nötig

Zeit: Umgebung als Schleife LOOP_S = 2 s mit FPS = 15 (Wasser, Boote, Laterne, Leuchtfeuer, Rauch periodisch),
Dachs-Clip aus demo/data/badger_clip.json (Weg, Zeiten). Alles deterministisch (feste Seeds, Zeit aus Bildnummer).

  loop    Umgebungsschleife ohne Dachs: Bild i zeigt t = i / FPS
  badger  Dachs-Clip: Bild j zeigt den Dachs zur Zeit j / FPS und die Umgebung zur Zeit (j / FPS) mod LOOP_S
  still   ein Bild (Umgebung t = 0), für Vorschau und Kamerawahl
  mask    nur zur Prüfung: Dachs-Clip als Deckungsmaske (alles andere Holdout, transparenter Film, RGBA), daraus
          misst scripts/measure_badger.py Kopf und Füße ohne Störung durch Schatten, Spiegelung und Dithering
Ausgaben nach assets/raw/render/<node>/<what>_NNNN.png (16 Bit, nicht im Git).
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
STYLE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(STYLE))

LOOP_S = 2.0
SMOKE_N = 5
# Rauchballen: je Kugel eigene Größe, Drift und Pendelphase, damit sich das Bild erst nach 2 s wiederholt
# (gleiche Kugeln im Abstand LOOP_S / SMOKE_N ergäben eine Periode von nur 0,4 s, der Rauch „pumpte“)
SMOKE_SIZE = (1.0, 0.78, 1.18, 0.88, 1.06)
SMOKE_DRIFT = (1.0, 0.75, 1.2, 0.9, 1.1)
SMOKE_PHASE = (0.0, 2.1, 4.0, 1.1, 5.2)
FPS = 15
SEED = 1993
AMBIENT = (0.0425, 0.0475, 0.0675)   # konstanter Umgebungsanteil (linear), leicht blau; klein, damit Schatten hart bleiben
# Hauptsonne seitlich hinter den Kameras (Westsüdwest, 36° hoch): ihr Schlagschatten fällt auf beleuchtete, sichtbare
# Flächen (Steg rechts neben dem Dachs, Pflaster, Turmwand neben der Tür). Aus der Richtung des Abendglühens
# (Nordwest, 12° hoch) fielen die Schatten lang ins Wasser und zur Kamera hin, die Flächen wären nur streifend
# beleuchtet; direkt hinter der Kamera verdeckte der Dachs seinen eigenen Schatten.
KEY_ELEV, KEY_AZ = 36.0, -115.0      # Grad; Azimut 0 = Norden (Godot −Z), positiv = Osten
KEY_ENERGY = 5.4
FILL_ENERGY = 0.35                   # kühle Gegensonne aus Südost (vorher 1,35): zweiter, schwacher Schatten


def gb(v):
    """Godot (x, y, z) -> Blender (x, -z, y)."""
    return Vector((v[0], -v[2], v[1]))


def srgb_lin(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


# ---------------------------------------------------------------------------------------------
# Knoten-Helfer
# ---------------------------------------------------------------------------------------------
class NT:
    def __init__(self, tree):
        self.t, self.n, self.l = tree, tree.nodes, tree.links

    def node(self, kind, **props):
        nd = self.n.new(kind)
        for k, v in props.items():
            setattr(nd, k, v)
        return nd

    def link(self, a, b):
        self.l.new(a, b)

    def _in(self, sock, v):
        if isinstance(v, (int, float)):
            sock.default_value = v
        elif isinstance(v, tuple):
            sock.default_value = (*v, 1.0) if (len(v) == 3 and len(sock.default_value) == 4) else v
        else:
            self.l.new(v, sock)

    def math(self, op, a, b=None, clamp=False):
        nd = self.n.new("ShaderNodeMath")
        nd.operation = op
        nd.use_clamp = clamp
        for i, v in enumerate((a, b)):
            if v is not None:
                self._in(nd.inputs[i], v)
        return nd.outputs[0]

    def vmath(self, op, a, b=None):
        nd = self.n.new("ShaderNodeVectorMath")
        nd.operation = op
        for i, v in enumerate((a, b)):
            if v is not None:
                self._in(nd.inputs[i], v)
        return nd.outputs["Value"] if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else nd.outputs["Vector"]

    def mix(self, fac, a, b, blend="MIX"):
        nd = self.n.new("ShaderNodeMix")
        nd.data_type = "RGBA"
        nd.blend_type = blend
        self._in(nd.inputs[0], fac)
        self._in(nd.inputs[6], a)
        self._in(nd.inputs[7], b)
        return nd.outputs[2]

    def ramp(self, fac, stops, interp="LINEAR"):
        nd = self.n.new("ShaderNodeValToRGB")
        self.l.new(fac, nd.inputs["Fac"])
        cr = nd.color_ramp
        cr.interpolation = interp
        while len(cr.elements) < len(stops):
            cr.elements.new(0.5)
        for el, (pos, col) in zip(cr.elements, stops):
            el.position = pos
            el.color = (*col, 1.0)
        return nd.outputs["Color"]

    def noise(self, vec, scale, detail=2.0, rough=0.5, dims="3D", distortion=0.0):
        nd = self.n.new("ShaderNodeTexNoise")
        nd.noise_dimensions = dims
        nd.inputs["Scale"].default_value = scale
        nd.inputs["Detail"].default_value = detail
        nd.inputs["Roughness"].default_value = rough
        nd.inputs["Distortion"].default_value = distortion
        if vec is not None:
            self.l.new(vec, nd.inputs["Vector"])
        return nd


def new_material(name):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    # Die Emission dient nur als konstanter Umgebungsanteil bzw. Leuchtfläche; als Lichtquelle abgetastet
    # würde jede Fläche zum Licht und das Bild verrauscht (die Punktlichter beleuchten).
    m.cycles.emission_sampling = "NONE"
    nt = NT(m.node_tree)
    for nd in list(nt.n):
        nt.n.remove(nd)
    return m, nt


def cg_surface(nt, color, rough, spec=0.6, metal=0.0, normal=None, ambient=True, coat=0.0):
    """Principled-Fläche im Stil früher Raytracer: glatt, Glanzpunkt, konstanter Umgebungsanteil."""
    p = nt.node("ShaderNodeBsdfPrincipled")
    nt._in(p.inputs["Base Color"], color)
    nt._in(p.inputs["Roughness"], rough)
    p.inputs["Metallic"].default_value = metal
    p.inputs["Specular IOR Level"].default_value = spec
    if coat:
        p.inputs["Coat Weight"].default_value = coat
        p.inputs["Coat Roughness"].default_value = 0.05
    if normal is not None:
        nt.link(normal, p.inputs["Normal"])
    if ambient:
        amb = nt.mix(1.0, color, AMBIENT, "MULTIPLY")
        nt.link(amb, p.inputs["Emission Color"])
        p.inputs["Emission Strength"].default_value = 1.0
    out = nt.node("ShaderNodeOutputMaterial")
    nt.link(p.outputs["BSDF"], out.inputs["Surface"])
    return p


def uvw(nt):
    """UV in Metern (1 UV-Einheit = 1 m in shared/3d) als Vektor."""
    return nt.node("ShaderNodeTexCoord").outputs["UV"]


def bump(nt, height, strength, distance=0.02):
    b = nt.node("ShaderNodeBump")
    b.inputs["Strength"].default_value = strength
    b.inputs["Distance"].default_value = distance
    nt.link(height, b.inputs["Height"])
    return b.outputs["Normal"]


def brick(nt, vec, c1, c2, mortar, scale, mortar_size, row_h, brick_w, offset=0.5, bias=0.0):
    br = nt.node("ShaderNodeTexBrick")
    br.offset = offset
    nt.link(vec, br.inputs["Vector"])
    br.inputs["Color1"].default_value = (*c1, 1)
    br.inputs["Color2"].default_value = (*c2, 1)
    br.inputs["Mortar"].default_value = (*mortar, 1)
    br.inputs["Scale"].default_value = scale
    br.inputs["Mortar Size"].default_value = mortar_size
    br.inputs["Mortar Smooth"].default_value = 0.0
    br.inputs["Bias"].default_value = bias
    br.inputs["Brick Width"].default_value = brick_w
    br.inputs["Row Height"].default_value = row_h
    return br


# ---------------------------------------------------------------------------------------------
# Materialien (alle prozedural, sauber, ohne Schmutz)
# ---------------------------------------------------------------------------------------------
def mat_paving():
    m, nt = new_material("CG_Paving")
    br = brick(nt, uvw(nt), srgb_lin("#9A938A"), srgb_lin("#B4ADA2"), srgb_lin("#55504A"),
               1.0, 0.025, 0.5, 0.75)
    cg_surface(nt, br.outputs["Color"], 0.32, 0.7, normal=bump(nt, br.outputs["Fac"], 0.35, 0.02))
    return m


def mat_wall():
    m, nt = new_material("CG_Wall")
    br = brick(nt, uvw(nt), srgb_lin("#A89C88"), srgb_lin("#C2B6A0"), srgb_lin("#6E665C"),
               1.0, 0.02, 0.26, 0.52)
    cg_surface(nt, br.outputs["Color"], 0.38, 0.6, normal=bump(nt, br.outputs["Fac"], 0.3, 0.02))
    return m


def mat_stone_dark():
    m, nt = new_material("CG_StoneDark")
    br = brick(nt, uvw(nt), srgb_lin("#5E5A55"), srgb_lin("#6C6761"), srgb_lin("#3A3734"),
               1.0, 0.018, 0.4, 0.8)
    cg_surface(nt, br.outputs["Color"], 0.35, 0.6, normal=bump(nt, br.outputs["Fac"], 0.25, 0.02))
    return m


def mat_wood(name, c0, c1, rough=0.22, scale=(1.0, 1.0, 1.0), spec=0.6):
    """Klassisches prozedurales Holz: Ringe aus dem Wave-Knoten, leicht verzerrt, lackiert glänzend."""
    m, nt = new_material(name)
    v = uvw(nt)
    mp = nt.node("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = scale
    nt.link(v, mp.inputs["Vector"])
    wv = nt.node("ShaderNodeTexWave", wave_type="BANDS", bands_direction="Y", wave_profile="SIN")
    wv.inputs["Scale"].default_value = 1.1
    wv.inputs["Distortion"].default_value = 4.0
    wv.inputs["Detail"].default_value = 1.5
    wv.inputs["Detail Scale"].default_value = 0.6
    nt.link(mp.outputs["Vector"], wv.inputs["Vector"])
    col = nt.ramp(wv.outputs["Fac"], [(0.0, srgb_lin(c0)), (0.55, srgb_lin(c1)), (1.0, srgb_lin(c0))])
    cg_surface(nt, col, rough, spec, normal=bump(nt, wv.outputs["Fac"], 0.08, 0.01))
    return m


def mat_plain(name, hexc, rough, spec=0.6, metal=0.0, coat=0.0):
    m, nt = new_material(name)
    cg_surface(nt, srgb_lin(hexc), rough, spec, metal, coat=coat)
    return m


def mat_roof():
    m, nt = new_material("CG_Roof")
    br = brick(nt, uvw(nt), srgb_lin("#3E4A5E"), srgb_lin("#48556B"), srgb_lin("#252B36"),
               1.0, 0.012, 0.18, 0.32)
    cg_surface(nt, br.outputs["Color"], 0.2, 0.8, normal=bump(nt, br.outputs["Fac"], 0.3, 0.02))
    return m


def mat_noise(name, c0, c1, scale, rough, bump_s=0.25):
    """Glatte Rausch-Fläche (Fels, Sand, Gras), wie frühe 'fraktale' Materialien: weich, ohne Schmutz."""
    m, nt = new_material(name)
    tc = nt.node("ShaderNodeTexCoord").outputs["Object"]
    nz = nt.noise(tc, scale, 2.0, 0.45)
    col = nt.ramp(nz.outputs["Fac"], [(0.3, srgb_lin(c0)), (0.7, srgb_lin(c1))])
    cg_surface(nt, col, rough, 0.5, normal=bump(nt, nz.outputs["Fac"], bump_s, 0.1))
    return m


def mat_glass(name, hexc, strength):
    m, nt = new_material(name)
    em = nt.node("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*srgb_lin(hexc), 1)
    em.inputs["Strength"].default_value = strength
    out = nt.node("ShaderNodeOutputMaterial")
    nt.link(em.outputs[0], out.inputs["Surface"])
    return m, em


def mat_water(state):
    """Fast-Spiegel mit periodischen Wellen (nahtlose Schleife über LOOP_S)."""
    m, nt = new_material("CG_Water")
    pos = nt.node("ShaderNodeNewGeometry").outputs["Position"]
    sep = nt.node("ShaderNodeSeparateXYZ")
    nt.link(pos, sep.inputs[0])
    ph = nt.node("ShaderNodeValue")          # Phase 0..2π über die Schleife
    state["water_phase"] = ph
    h = None
    # (Richtung Grad, Wellenlänge m, Amplitude, Umläufe je Schleife)
    for deg, lam, amp, cyc in [(75, 3.4, 1.0, 1), (120, 2.1, 0.7, 2), (35, 1.3, 0.45, 3), (160, 0.8, 0.3, 4)]:
        dx, dy = math.cos(math.radians(deg)), math.sin(math.radians(deg))
        k = 2 * math.pi / lam
        arg = nt.math("ADD", nt.math("MULTIPLY", sep.outputs["X"], dx * k),
                      nt.math("MULTIPLY", sep.outputs["Y"], dy * k))
        arg = nt.math("SUBTRACT", arg, nt.math("MULTIPLY", ph.outputs[0], float(cyc)))
        term = nt.math("MULTIPLY", nt.math("SINE", arg), amp)
        h = term if h is None else nt.math("ADD", h, term)
    # weiter weg flacher: sonst flimmert das Meer in 544×332 nur noch als Rauschen
    cam = nt.node("ShaderNodeCameraData")
    fade = nt.math("SUBTRACT", 1.0, nt.math("MULTIPLY", nt.math("SUBTRACT", cam.outputs["View Z Depth"], 12.0),
                                             1 / 60.0, clamp=True))
    b = nt.node("ShaderNodeBump")
    b.inputs["Distance"].default_value = 0.03
    nt.link(nt.math("MULTIPLY", fade, 0.22), b.inputs["Strength"])
    nt.link(h, b.inputs["Height"])
    # Spiegel + dunkles Wasser, Anteil über Fresnel (früher „reflectivity“-Regler)
    gl = nt.node("ShaderNodeBsdfGlossy")
    gl.distribution = "SHARP" if "SHARP" in [e.identifier for e in gl.bl_rna.properties["distribution"].enum_items] else "GGX"
    gl.inputs["Roughness"].default_value = 0.0
    gl.inputs["Color"].default_value = (0.82, 0.86, 0.9, 1)
    nt.link(b.outputs["Normal"], gl.inputs["Normal"])
    em = nt.node("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*srgb_lin("#123540"), 1)
    em.inputs["Strength"].default_value = 1.0
    fr = nt.node("ShaderNodeLayerWeight")
    fr.inputs["Blend"].default_value = 0.35
    nt.link(b.outputs["Normal"], fr.inputs["Normal"])
    fac = nt.math("ADD", nt.math("MULTIPLY", fr.outputs["Fresnel"], 0.55), 0.38, clamp=True)
    mx = nt.node("ShaderNodeMixShader")
    nt.link(fac, mx.inputs[0])
    nt.link(em.outputs[0], mx.inputs[1])
    nt.link(gl.outputs[0], mx.inputs[2])
    out = nt.node("ShaderNodeOutputMaterial")
    nt.link(mx.outputs[0], out.inputs["Surface"])
    return m


def mat_smoke():
    """Rauchballen wie in frühen CGI-Filmen: halbdurchsichtige, glatte Kugeln ohne Volumen."""
    m, nt = new_material("CG_Smoke")
    tr = nt.node("ShaderNodeBsdfTransparent")
    em = nt.node("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*srgb_lin("#9A94A8"), 1)
    em.inputs["Strength"].default_value = 0.4
    fr = nt.node("ShaderNodeLayerWeight")
    fr.inputs["Blend"].default_value = 0.5
    # Rand durchsichtiger als die Mitte (Facing)
    alpha = nt.node("ShaderNodeValue")
    alpha.outputs[0].default_value = 0.5
    fac = nt.math("MULTIPLY", nt.math("SUBTRACT", 1.0, fr.outputs["Facing"]), alpha.outputs[0])
    mx = nt.node("ShaderNodeMixShader")
    nt.link(fac, mx.inputs[0])
    nt.link(tr.outputs[0], mx.inputs[1])
    nt.link(em.outputs[0], mx.inputs[2])
    out = nt.node("ShaderNodeOutputMaterial")
    nt.link(mx.outputs[0], out.inputs["Surface"])
    return m, alpha


def build_materials(state):
    mats = {
        "Stone": mat_paving(),
        "StoneDark": mat_stone_dark(),
        # Stegplanken etwas weniger Glanz (0,4): Der gespiegelte Himmel liegt gleich hell auf Licht und Schatten und
        # nähme dem Schatten des Dachses sonst ein Drittel seines Abfalls
        "Wood": mat_wood("CG_Wood", "#7A5230", "#A97A4C", spec=0.4),
        "WoodDark": mat_wood("CG_WoodDark", "#3E2A1A", "#5E4129", 0.25),
        "WhitePaint": mat_plain("CG_WhitePaint", "#E6E2D8", 0.18, 0.7, coat=0.3),
        "RedPaint": mat_plain("CG_RedPaint", "#B5281F", 0.16, 0.7, coat=0.3),
        "Roof": mat_roof(),
        "Rope": mat_wood("CG_Rope", "#A68E62", "#CDB689", 0.4, (1.0, 4.0, 1.0)),
        "Metal": mat_plain("CG_Metal", "#B8BCC4", 0.06, 0.8, metal=1.0),
        "Rock": mat_noise("CG_Rock", "#5F5B57", "#8A847C", 0.9, 0.35, 0.4),
        "Sand": mat_noise("CG_Sand", "#B9A578", "#D2C094", 3.0, 0.5, 0.1),
        "Grass": mat_noise("CG_Grass", "#4E6A2E", "#6F8C3A", 1.4, 0.45, 0.15),
        "Water": mat_water(state),
    }
    wall = mat_wall()
    glass = {}
    for obj, (hexc, strength) in {"LanternGlass": ("#FFB84A", 1.6), "CottageWindow": ("#FFAE48", 1.25),
                                  "LighthouseLamp": ("#FFD98A", 1.8)}.items():
        glass[obj] = mat_glass("CG_Glass_" + obj, hexc, strength)
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
                slot.material = wall
            elif name in mats:
                slot.material = mats[name]
            elif name in BADGER_MATS:
                slot.material = badger_material(name)
            else:
                print("WARNUNG: Material ohne Ersatz:", name, ob.name)


# Dachs: Farben aus dem glTF-Material, aber glatter Kunststoff-Look der frühen CGI-Figuren
BADGER_MATS = {"FurDark": 0.3, "FurLight": 0.3, "Cap": 0.25, "Brass": 0.1, "Vest": 0.3, "Shirt": 0.35,
               "Scarf": 0.35, "Satchel": 0.22, "Parcel": 0.25, "Nose": 0.08, "Eye": 0.05}
# Farben, die vom glTF abweichen: Das Paket (#C08B57) war bei 62–80 px Figurenhöhe nur ein dunkler Fleck an der
# Hüfte; helleres, wärmeres Packpapier mit Glanzpunkt und eigenem Kantenlicht hebt es als hellen Block heraus.
BADGER_COLOR = {"Parcel": "#E2B577"}
BADGER_RIM_EXTRA = {"Parcel": 1.8}     # Faktor auf die Kantenlicht-Stärke
_bm_cache = {}


def badger_material(name):
    if name in _bm_cache:
        return _bm_cache[name]
    src = bpy.data.materials[name]
    col = (0.5, 0.5, 0.5)
    if src.node_tree:
        for nd in src.node_tree.nodes:
            if nd.type == "BSDF_PRINCIPLED":
                col = tuple(nd.inputs["Base Color"].default_value)[:3]
    if name in BADGER_COLOR:
        col = srgb_lin(BADGER_COLOR[name])
    m, nt = new_material("CG_B_" + name)
    p = cg_surface(nt, col, BADGER_MATS[name], 0.7, metal=1.0 if name == "Brass" else 0.0)
    if BADGER_RIM:
        rim = dict(BADGER_RIM)
        rim["strength"] = rim["strength"] * BADGER_RIM_EXTRA.get(name, 1.0)
        add_rim(nt, p, col, rim)
    _bm_cache[name] = m
    return m


BADGER_RIM = None    # aus nodes.json → badger_clip.rim, in main() gesetzt


def add_rim(nt, p, col, spec):
    """Kantenlicht als Materialterm (wie die „rim“-/Fresnel-Glieder früher Renderer): leuchtet an Kanten, deren
    Normale zur Seite rechts hinten zeigt. Trennt den dunklen Winkearm vom dunklen Fels dahinter.
    Bewusst kein zusätzliches Licht: Ein Licht ändert die Lichtauswahl von Cycles und damit das Rauschen im
    ganzen Bild, dann wiche der Dachs-Clip überall von der Umgebungsschleife ab."""
    L = gb(spec["dir"]).normalized()
    n = nt.node("ShaderNodeNewGeometry").outputs["Normal"]
    side = nt.math("MAXIMUM", nt.vmath("DOT_PRODUCT", n, tuple(L)), 0.0)
    lw = nt.node("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.5
    edge = nt.math("POWER", lw.outputs["Facing"], spec.get("power", 1.5))
    r = nt.math("MULTIPLY", nt.math("MULTIPLY", side, edge), spec["strength"])
    rim_col = nt.mix(1.0, srgb_lin(spec["color"]), col, "MULTIPLY") if spec.get("tint") else srgb_lin(spec["color"])
    amb = p.inputs["Emission Color"].links[0].from_socket
    nt.link(nt.mix(r, amb, rim_col, "ADD"), p.inputs["Emission Color"])


# ---------------------------------------------------------------------------------------------
# Himmel (nur für Kamera- und Spiegelstrahlen sichtbar, beleuchtet nichts)
# ---------------------------------------------------------------------------------------------
GLOW_DIR = Vector((-0.55, 1.0, 0.0)).normalized()   # Blender: Nachglühen im Nordwesten


def build_world(sky_image=None):
    w = bpy.data.worlds.new("Dusk")
    bpy.context.scene.world = w
    try:
        w.use_nodes = True
    except Exception:
        pass
    nt = NT(w.node_tree)
    for nd in list(nt.n):
        nt.n.remove(nd)
    d = nt.vmath("NORMALIZE", nt.node("ShaderNodeTexCoord").outputs["Generated"])
    sep = nt.node("ShaderNodeSeparateXYZ")
    nt.link(d, sep.inputs[0])
    el = nt.math("MAXIMUM", sep.outputs["Z"], 0.0)
    if sky_image:
        # Himmelsbild (Mattepainting) über Azimut und Höhe gelegt
        img = bpy.data.images.load(sky_image)
        tex = nt.node("ShaderNodeTexImage")
        tex.image = img
        tex.extension = "EXTEND"
        tex.interpolation = "Linear"
        az = nt.math("ARCTAN2", sep.outputs["X"], sep.outputs["Y"])    # 0 = Norden (Blender +Y)
        u = nt.math("DIVIDE", nt.math("SUBTRACT", az, math.radians(SKY_AZ[0])), math.radians(SKY_AZ[1] - SKY_AZ[0]))
        v = nt.math("DIVIDE", nt.math("ARCSINE", el), math.radians(SKY_EL))
        uv = nt.node("ShaderNodeCombineXYZ")
        nt.link(u, uv.inputs[0])
        nt.link(v, uv.inputs[1])
        nt.link(uv.outputs[0], tex.inputs["Vector"])
        sky = tex.outputs["Color"]
    else:
        toward = nt.vmath("DOT_PRODUCT", d, tuple(GLOW_DIR))
        glow = nt.math("POWER", nt.math("MULTIPLY", nt.math("ADD", toward, 1.0), 0.5, clamp=True), 3.0)
        e = nt.math("POWER", el, 0.6)
        base = nt.ramp(e, [(0.0, srgb_lin("#C9879A")), (0.12, srgb_lin("#8A6C9E")), (0.35, srgb_lin("#3E4C8C")),
                           (0.75, srgb_lin("#1A2458")), (1.0, srgb_lin("#0E1438"))])
        band = nt.ramp(e, [(0.0, srgb_lin("#FFB060")), (0.10, srgb_lin("#F07A50")), (0.25, srgb_lin("#3E4C8C"))])
        sky = nt.mix(glow, base, band)
        # flache, glatte Wolkenbänder (gestrecktes Rauschen), nur nahe am Horizont
        sc_v = nt.vmath("MULTIPLY", d, (1.0, 1.0, 9.0))
        cn = nt.noise(sc_v, 2.2, 3.0, 0.55)
        cl = nt.math("MULTIPLY", nt.math("SUBTRACT", cn.outputs["Fac"], 0.56), 7.0, clamp=True)
        cl = nt.math("MULTIPLY", cl, nt.math("SUBTRACT", 1.0, nt.math("MULTIPLY", el, 3.2), clamp=True))
        cl = nt.math("MULTIPLY", cl, nt.math("MULTIPLY", el, 30.0, clamp=True))
        ccol = nt.mix(glow, srgb_lin("#6A5A86"), srgb_lin("#E89A80"))
        sky = nt.mix(cl, sky, ccol)
        # Sterne: Voronoi-Punkte, erst ab etwa 12° Höhe
        vor = nt.node("ShaderNodeTexVoronoi")
        vor.feature = "F1"
        vor.inputs["Scale"].default_value = 140.0
        nt.link(d, vor.inputs["Vector"])
        star = nt.math("LESS_THAN", vor.outputs["Distance"], 0.045)
        star = nt.math("MULTIPLY", star, nt.math("GREATER_THAN", vor.outputs["Color"], 0.0))
        rnd = nt.node("ShaderNodeSeparateColor")
        nt.link(vor.outputs["Color"], rnd.inputs[0])
        star = nt.math("MULTIPLY", star, nt.math("GREATER_THAN", rnd.outputs[0], 0.72))
        star = nt.math("MULTIPLY", star, nt.math("MULTIPLY", nt.math("SUBTRACT", el, 0.2), 6.0, clamp=True))
        star = nt.math("MULTIPLY", star, nt.math("SUBTRACT", 1.0, cl))
        sky = nt.mix(star, sky, (1.0, 0.96, 0.85))
    bgn = nt.node("ShaderNodeBackground")
    nt.link(sky, bgn.inputs["Color"])
    bgn.inputs["Strength"].default_value = 1.0
    out = nt.node("ShaderNodeOutputWorld")
    nt.link(bgn.outputs[0], out.inputs["Surface"])
    # Himmel beleuchtet nichts (kein Umgebungslicht), ist aber in Spiegelungen zu sehen
    vis = w.cycles_visibility
    vis.camera, vis.glossy, vis.transmission = True, True, True
    vis.diffuse, vis.scatter = False, False
    try:
        w.cycles.sampling_method = "NONE"
    except Exception:
        pass
    return w


SKY_AZ = (-110.0, 60.0)   # Azimutbereich des Himmelsbilds (Grad, 0 = Norden/-Z in Godot, positiv = Osten)
SKY_EL = 55.0             # Höhe des oberen Bildrands in Grad


# ---------------------------------------------------------------------------------------------
# Lichter
# ---------------------------------------------------------------------------------------------
def link_obj(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def sun(name, toward_sun_godot, energy, hexc):
    ld = bpy.data.lights.new(name, "SUN")
    ld.energy = energy
    ld.color = srgb_lin(hexc)
    ld.angle = 0.0
    o = link_obj(bpy.data.objects.new(name, ld))
    d = gb(toward_sun_godot).normalized()
    o.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    return o


def point(name, loc_bl, energy, hexc, shadow=True):
    ld = bpy.data.lights.new(name, "POINT")
    ld.energy = energy
    ld.color = srgb_lin(hexc)
    ld.shadow_soft_size = 0.0
    ld.use_shadow = shadow
    o = link_obj(bpy.data.objects.new(name, ld))
    o.location = loc_bl
    return o


def build_lights(state, extra=(), no_shadow=()):
    e, az = math.radians(KEY_ELEV), math.radians(KEY_AZ)
    key_dir = (math.cos(e) * math.sin(az), math.sin(e), -math.cos(e) * math.cos(az))   # Godot, zur Sonne hin
    state["key"] = sun("KeySun", key_dir, KEY_ENERGY, "#FFB27A")                  # Südwest, warm
    state["fill"] = sun("FillSun", (0.55, 0.62, 0.62), FILL_ENERGY, "#93A2DA")    # Südost, kühl, eigene Schatten
    # nur zur Messung (scripts/measure_shadows.py): Schatten einer Sonne abschalten
    for k in no_shadow:
        state[k].data.use_shadow = False
    ll = bpy.data.objects["LanternLight"].matrix_world.translation.copy()
    state["lantern"] = point("LanternPt", ll, 45.0, "#FFB860")
    cw = bpy.data.objects["CottageWindow"]
    # vor dem Frontfenster (Fenster zeigt nach Süden = Blender -Y)
    state["window"] = point("WindowPt", cw.matrix_world.translation + Vector((0.0, -0.6, 0.0)), 30.0, "#FFB060")
    lh = bpy.data.objects["LighthouseLight"].matrix_world.translation.copy()
    state["lamp"] = point("LampPt", lh, 300.0, "#FFE0A0", shadow=True)
    for n in ("LanternGlass", "LighthouseLamp", "CottageWindow"):
        ob = bpy.data.objects[n]
        ob.visible_shadow = False
    # zusätzliche Lichter je Knoten (wie bei vorgerenderten Spielen üblich: Licht je Einstellung gesetzt)
    for i, L in enumerate(extra):
        point(f"Extra{i}", gb(L["pos"]), L["energy"], L["color"], L.get("shadow", True))


def fix_lighthouse_door():
    """Durchstoß aus shared/3d/harbor.glb beheben (nur in dieser Szene): Die Turmwand ist unten breiter als oben, die
    flache Tür steht davor; an der Türschwelle links ragt ein Eckpunkt der Wand 1 cm vor die Türfläche und erscheint
    als weißes Dreieck in der Tür. Eckpunkte der Wand am Turmfuß, die vor der Türebene liegen, rücken 3 cm hinter sie."""
    ob = bpy.data.objects["Lighthouse"]
    me, mw = ob.data, ob.matrix_world
    inv = mw.inverted()
    door = [p for p in me.polygons if ob.material_slots[p.material_index].material.name.split(".")[0] == "WoodDark"
            and (mw @ p.center).z < 5.5]
    if not door:
        print("WARNUNG: Leuchtturmtür nicht gefunden")
        return 0
    big = max(door, key=lambda p: p.area)
    n = (mw.to_3x3() @ big.normal).normalized()
    c = mw @ big.center
    xs = [(mw @ me.vertices[v].co) for p in door for v in p.vertices]
    lo = min(v.dot(n.cross(Vector((0, 0, 1)))) for v in xs)
    hi = max(v.dot(n.cross(Vector((0, 0, 1)))) for v in xs)
    side = n.cross(Vector((0, 0, 1)))
    moved = 0
    white = {p.index for p in me.polygons if ob.material_slots[p.material_index].material.name.split(".")[0] == "WhitePaint"}
    wverts = {v for p in me.polygons if p.index in white for v in p.vertices}
    for vi in wverts:
        w = mw @ me.vertices[vi].co
        if w.z > c.z + 0.2 or not (lo - 0.05 <= w.dot(side) <= hi + 0.05):
            continue
        d = (w - c).dot(n)          # > 0: vor der Tür (zur Kamera hin)
        if d > -0.03:
            me.vertices[vi].co = inv @ (w - n * (d + 0.03))
            moved += 1
    me.update()
    print(f"Leuchtturmtür: {moved} Eckpunkte der Turmwand hinter die Tür gerückt")
    return moved


def hide_cut_bollards(node):
    """Poller, die nur angeschnitten im Bild stehen, aus der Szene nehmen (Kai unten rechts, Steg unten links).
    Als Chrom spiegelten die Stümpfe am Bildrand nur den Himmel und wirkten wie Glasglocken."""
    import bmesh
    ob = bpy.data.objects["Bollards"]
    mw = ob.matrix_world
    cam, tgt = gb(node["pos"]), gb(node["target"])
    fwd = (tgt - cam).normalized()
    right = fwd.cross(Vector((0, 0, 1))).normalized()
    up = right.cross(fwd)
    W, H = 544, 332
    f = (W / 2) / math.tan(math.radians(node["hfov"]) / 2)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    # Poller = Eckpunkte, deren Lage (x, y) näher als 0,5 m beieinanderliegt
    groups = []
    for v in bm.verts:
        w = mw @ v.co
        for g in groups:
            if (g[0] - w.xy).length < 0.5:
                g[1].append(v)
                break
        else:
            groups.append([w.xy.copy(), [v]])
    removed = []
    for center, verts in groups:
        pts = []
        for v in verts:
            d = mw @ v.co - cam
            z = d.dot(fwd)
            pts.append((W / 2 + f * d.dot(right) / z, H / 2 - f * d.dot(up) / z) if z > 0.05 else None)
        if any(p is None for p in pts):
            continue
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        inside = max(xs) > 0 and min(xs) < W and max(ys) > 0 and min(ys) < H
        whole = min(xs) >= 0 and max(xs) < W and min(ys) >= 0 and max(ys) < H
        if inside and not whole:
            bmesh.ops.delete(bm, geom=verts, context="VERTS")
            removed.append((round(center.x, 2), round(-center.y, 2)))
    bm.to_mesh(ob.data)
    bm.free()
    print("Angeschnittene Poller entfernt (Godot x, z):", removed)


def build_smoke(state):
    """SMOKE_N Rauchballen steigen periodisch aus dem Schornstein (je 2 s Lebensdauer, gleichmäßig versetzt)."""
    mat, alpha = mat_smoke()
    state["smoke_alpha"] = alpha
    origin = bpy.data.objects["ChimneySmoke"].matrix_world.translation.copy()
    puffs = []
    for i in range(SMOKE_N):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=1.0, location=origin)
        ob = bpy.context.active_object
        ob.name = f"SmokePuff{i}"
        ob.data.materials.append(mat)
        bpy.ops.object.shade_smooth()
        ob.visible_shadow = False
        # jede Kugel bekommt ein eigenes Material, damit die Deckkraft einzeln abnimmt
        m2 = mat.copy()
        ob.data.materials[0] = m2
        a2 = next(nd for nd in m2.node_tree.nodes if nd.type == "VALUE")
        puffs.append((ob, a2))
    state["smoke"] = (origin, puffs)


# ---------------------------------------------------------------------------------------------
# Dachs
# ---------------------------------------------------------------------------------------------
def import_badger():
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(ROOT, "shared", "3d", "badger.glb"))
    new = [o for o in bpy.data.objects if o not in before]
    arm = next(o for o in new if o.type == "ARMATURE")
    for o in new:
        if o.name.startswith("Icosphere"):
            o.hide_render = True
    ad = arm.animation_data
    for tr in list(ad.nla_tracks):
        ad.nla_tracks.remove(tr)
    acts = {n: bpy.data.actions[n] for n in ("Idle", "Walk", "Wave")}
    return arm, acts, [o for o in new if o.type == "MESH" and not o.name.startswith("Icosphere")]


def pose_of(arm, act, t_sec):
    """Pose (je Knochen: Ort, Drehung, Größe) einer Aktion zur Zeit t_sec (Sekunden ab Aktionsbeginn)."""
    ad = arm.animation_data
    ad.action = act
    if hasattr(ad, "action_slot") and act.slots:
        ad.action_slot = act.slots[0]
    f = t_sec * 24.0   # Aktionen beginnen bei Bild 0, glTF-Import mit 24 Bildern/s
    sc = bpy.context.scene
    sc.frame_set(int(math.floor(f)), subframe=f - math.floor(f))
    out = {}
    for pb in arm.pose.bones:
        out[pb.name] = (pb.location.copy(), pb.rotation_quaternion.copy(), pb.scale.copy())
    return out


def apply_pose(arm, pa, pb=None, k=0.0):
    arm.animation_data.action = None
    for bone in arm.pose.bones:
        la, ra, sa = pa[bone.name]
        if pb is not None and k > 0.0:
            lb, rb, sb = pb[bone.name]
            la = la.lerp(lb, k)
            ra = ra.slerp(rb, k)
            sa = sa.lerp(sb, k)
        bone.rotation_mode = "QUATERNION"
        bone.location, bone.rotation_quaternion, bone.scale = la, ra, sa
    bpy.context.view_layer.update()


def smoothstep(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def badger_state(clip, t):
    """Lage, Blickrichtung und Pose-Rezept des Dachses zur Clip-Zeit t (Sekunden). Spiegelbild in demo/main.gd
    nicht nötig: Godot spielt nur die gerenderten Bilder ab."""
    s = clip["speed_scale"]
    t_w, t_d = clip["walk_s"], clip["decel_s"]
    # Aktionszeit des Laufs: volle Geschwindigkeit bis t_w, danach linear auf 0 bis t_w + t_d
    if t <= t_w:
        a = s * t
    else:
        u = min(t - t_w, t_d)
        a = s * t_w + s * (u - u * u / (2 * t_d))
    dist = 0.367 * a
    p0, p1 = Vector(clip["start"]), Vector(clip["end"])
    dirv = (p1 - p0).normalized()
    pos = p0 + dirv * dist
    yaw_walk = math.atan2(-dirv.z, dirv.x)                 # Godot: Drehung um y, 0 = Blick nach +X
    stop = t_w + t_d
    t_wave = stop + clip["blend_to_wave_s"]
    yaw_face = math.radians(clip["face_yaw_deg"])
    k_turn = smoothstep((t - stop) / clip["blend_to_wave_s"])
    yaw = yaw_walk + (yaw_face - yaw_walk) * k_turn
    walk_t = a % 1.0
    if t < stop:
        recipe = ("Walk", walk_t, None, 0.0, 0.0)
    elif t < t_wave:
        recipe = ("Walk", walk_t, "Wave", 0.0, smoothstep((t - stop) / clip["blend_to_wave_s"]))
    else:
        tw = t - t_wave
        t_idle0 = t_wave + 1.5
        if tw < 1.5:
            recipe = ("Wave", tw, None, 0.0, 0.0)
        else:
            ti = t - t_idle0
            k = smoothstep(ti / clip["blend_to_idle_s"])
            recipe = ("Wave", 1.5, "Idle", ti % 2.0, k)
    return pos, yaw, recipe, dist


def set_badger(state, clip, t):
    arm = state["arm"]
    pos, yaw, (a1, t1, a2, t2, k), _ = badger_state(clip, t)
    root = state["badger_root"]
    root.location = gb(pos)
    root.rotation_mode = "XYZ"
    root.rotation_euler = (0.0, 0.0, yaw)
    pa = pose_of(arm, state["acts"][a1], t1)
    pb = pose_of(arm, state["acts"][a2], t2) if a2 else None
    apply_pose(arm, pa, pb, k)


# ---------------------------------------------------------------------------------------------
# Zeit
# ---------------------------------------------------------------------------------------------
def lantern_flicker(t):
    """Periodisch über LOOP_S (ganzzahlige Umläufe), deterministisch, zwischen etwa 0,6 und 1,1."""
    w = 2 * math.pi * t / LOOP_S
    f = (0.85 + 0.10 * math.sin(3 * w + 0.4) + 0.07 * math.sin(7 * w + 1.9)
         + 0.05 * math.sin(13 * w + 4.1) + 0.04 * math.sin(19 * w + 2.6))
    return f


def lamp_flash(t):
    """Leuchtfeuer: ein Blitz je Schleife (Kennung „Blz. 2 s“), weich an- und abschwellend, Höhepunkt bei 0,4 s."""
    x = ((t - 0.4) / LOOP_S + 0.5) % 1.0 - 0.5   # -0.5..0.5, 0 = Höhepunkt
    return math.exp(-(x * LOOP_S / 0.12) ** 2)


def set_time(state, t):
    tl = t % LOOP_S
    w = 2 * math.pi * tl / LOOP_S
    state["water_phase"].outputs[0].default_value = w
    # Boote: Rollen und Stampfen, periodisch
    for name, ph, amp in (("BoatA", 0.0, 1.0), ("BoatB", 1.7, 1.3)):
        ob = bpy.data.objects[name]
        base_loc, base_rot = state["boat_base"][name]
        ob.location = base_loc + Vector((0, 0, 0.025 * amp * math.sin(w + ph + 0.8)))
        ob.rotation_euler = (base_rot[0] + math.radians(1.6 * amp) * math.sin(w + ph),
                             base_rot[1] + math.radians(0.7 * amp) * math.sin(w + ph + 1.3),
                             base_rot[2])
    # Flackern nur, wo die Laterne im Bild ist; sonst bliebe ein schwaches Flimmern auf entfernten Flächen,
    # und das ganze Bild würde zur Bildfolge
    f = lantern_flicker(tl) if state.get("flicker", True) else lantern_flicker(0.0)
    state["lantern"].data.energy = 45.0 * f
    state["glass"]["LanternGlass"][1].inputs["Strength"].default_value = 1.6 * f
    # Blitz nur in der Lampe selbst (und als Stern in scripts/bake.py), nicht als Licht auf der Szene
    fl = lamp_flash(tl)
    state["glass"]["LighthouseLamp"][1].inputs["Strength"].default_value = 1.8 + 6.0 * fl
    # Rauch: Kugel i ist seit (tl + i·LOOP_S/SMOKE_N) mod 2 s unterwegs; sie steigt in 2 s etwa 2,3 m, treibt nach
    # Osten, pendelt seitlich, wächst auf das Vier- bis Fünffache und verblasst. Alles hängt nur vom Alter ab, die
    # Schleife ist also nahtlos; die je Kugel verschiedenen Werte verhindern eine kürzere Periode.
    origin, puffs = state["smoke"]
    for i, (ob, alpha) in enumerate(puffs):
        age = (tl + i * LOOP_S / len(puffs)) % LOOP_S / LOOP_S      # 0..1
        sway = 0.10 * math.sin(2 * math.pi * 1.2 * age + SMOKE_PHASE[i])
        drift = SMOKE_DRIFT[i] * (0.55 * age * age + 0.2 * age)
        ob.location = origin + Vector((drift + sway, -0.15 * age, 0.05 + 1.7 * age + 0.6 * age * age))
        r = SMOKE_SIZE[i] * (0.12 + 0.46 * age)
        ob.scale = (r, r, r * 0.85)
        alpha.outputs[0].default_value = 0.55 * smoothstep(age / 0.12) * (1.0 - smoothstep((age - 0.3) / 0.7))


# ---------------------------------------------------------------------------------------------
def parse_frames(s, n):
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
    ap.add_argument("--node", required=True)
    ap.add_argument("--what", default="still", choices=["still", "loop", "badger", "mask"])
    ap.add_argument("--frames", default="all")
    ap.add_argument("--res", default="544x332")
    ap.add_argument("--samples", type=int, default=48)
    ap.add_argument("--out", default=None)
    ap.add_argument("--sky", default=None, help="Himmelsbild (Mattepainting) statt prozeduralem Himmel")
    ap.add_argument("--no-badger", action="store_true")
    ap.add_argument("--blend", default=None)
    ap.add_argument("--no-shadow", default="", help="nur zur Messung: key,fill ohne Schatten")
    ap.add_argument("--prefix", default=None, help="Dateiname statt <what>_NNNN (z. B. für Messbilder)")
    a = ap.parse_args(argv)

    data = json.load(open(os.path.join(STYLE, "demo", "data", "nodes.json")))
    node = data["nodes"][a.node]
    clip = data["badger_clip"]
    out = a.out or os.path.join(STYLE, "assets", "raw", "render", a.node)
    os.makedirs(out, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = 24
    bpy.ops.import_scene.gltf(filepath=os.path.join(ROOT, "shared", "3d", "harbor.glb"))
    state = {}
    arm, acts, bmeshes = import_badger()
    state["arm"], state["acts"] = arm, acts
    state["badger_root"] = arm
    global BADGER_RIM
    BADGER_RIM = clip.get("rim")
    fix_lighthouse_door()           # vor build_materials: braucht die Materialnamen aus dem glTF
    build_materials(state)
    if node.get("hide_cut_bollards"):
        hide_cut_bollards(node)
    sky = a.sky or (os.path.join(STYLE, data["sky_image"]) if data.get("sky_image") else None)
    if sky and not os.path.exists(sky):
        sky = None
    build_world(sky)
    no_shadow = [k for k in a.no_shadow.split(",") if k]
    build_lights(state, node.get("extra_lights", []), no_shadow)
    build_smoke(state)
    state["flicker"] = node.get("lantern_flicker", True)
    state["boat_base"] = {n: (bpy.data.objects[n].location.copy(), bpy.data.objects[n].rotation_euler.copy())
                          for n in ("BoatA", "BoatB")}
    show_badger = a.what in ("badger", "mask") and not a.no_badger
    for o in [arm] + bmeshes:
        o.hide_render = not show_badger

    W, H = map(int, a.res.split("x"))
    cd = bpy.data.cameras.new("NodeCam")
    cd.sensor_fit = "HORIZONTAL"
    cd.sensor_width = 36.0
    cd.lens = 18.0 / math.tan(math.radians(node["hfov"]) / 2)
    cd.clip_start, cd.clip_end = 0.05, 3000.0
    cam = link_obj(bpy.data.objects.new("NodeCam", cd))
    cam.location = gb(node["pos"])
    cam.rotation_euler = (gb(node["target"]) - gb(node["pos"])).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam

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
    sc.cycles.use_adaptive_sampling = False
    sc.cycles.use_denoising = False
    sc.cycles.max_bounces = 6
    sc.cycles.diffuse_bounces = 0
    sc.cycles.glossy_bounces = 3
    sc.cycles.transmission_bounces = 3
    sc.cycles.transparent_max_bounces = 16
    sc.cycles.volume_bounces = 0
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.cycles.filter_width = 1.2
    sc.cycles.sample_clamp_indirect = float(os.environ.get("CLAMP_IND", "0"))
    sc.render.use_persistent_data = True
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = data.get("exposure", 0.0)
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_depth = "16"
    sc.render.image_settings.color_mode = "RGB"
    if a.what == "mask":
        # Verdeckung durch Steg, Poller und Pfahl bleibt erhalten (Holdout), Schatten und Spiegelungen fallen weg
        sc.render.film_transparent = True
        sc.render.image_settings.color_mode = "RGBA"
        sc.cycles.samples = 16
        for ob in bpy.data.objects:
            if ob.type == "MESH" and ob not in bmeshes:
                ob.is_holdout = True

    if a.what == "still":
        frames, n = [0], 1
    elif a.what == "loop":
        n = int(round(LOOP_S * FPS))
        frames = parse_frames(a.frames, n)
    else:
        n = clip["frames"]
        frames = parse_frames(a.frames, n)
    print(f"SETTINGS node={a.node} what={a.what} samples={sc.cycles.samples} res={W}x{H} "
          f"diffuse_bounces={sc.cycles.diffuse_bounces} glossy_bounces={sc.cycles.glossy_bounces} "
          f"key=({KEY_ELEV}°, az {KEY_AZ}°, {KEY_ENERGY}) fill={FILL_ENERGY} ambient={AMBIENT} "
          f"no_shadow={no_shadow or '-'} seed={SEED}", flush=True)
    if a.blend:
        set_time(state, 0.0)
        bpy.ops.wm.save_as_mainfile(filepath=a.blend)
    for i in frames:
        t = i / FPS
        set_time(state, t)
        if show_badger:
            set_badger(state, clip, t)
        sc.render.filepath = os.path.join(out, f"{a.prefix or a.what}_{i:04d}.png")
        bpy.ops.render.render(write_still=True)
        print(f"FRAME {a.node} {a.what} {i}/{n}", flush=True)


main()
