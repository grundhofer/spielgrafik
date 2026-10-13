"""Gemeinsamer Szenenaufbau für die Renderskripte von `vorgerenderte-sprites`.

Lädt Hafen und Dachs aus `shared/3d` (nur lesen), gibt ihnen glänzende CG-Materialien im Stil der
vorgerenderten 16-Bit-Grafik (prozedurale Maserung, Fell- und Steinrauschen, Glanzlichter), baut
Abendhimmel, Lichter und die Kameras. Koordinaten in Blender: Z oben, Kamera blickt nach +Y,
Godot (x, y, z) = Blender (x, z, -y).

Wird von render_bg.py und render_sprites.py importiert (sys.path auf diesen Ordner).
"""
import math
import os
import sys

import bpy
from mathutils import Euler, Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
STYLE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(STYLE))
SHARED3D = os.path.join(ROOT, "shared", "3d")

# ------------------------------------------------------------------------------------------
# Bildmaße und Kamera (alle Zahlen in Zielpixeln der 426×240-Szene)
# ------------------------------------------------------------------------------------------
W, H = 426, 240
SS = 4                      # Überabtastung: gerendert wird in 4× (1704×960), dann 4×4 gemittelt
WALK_Y = -1.2               # Laufweg (Godot z = 1,2)
CAM_D = 6.7                 # Abstand Kamera – Laufweg
PX_PER_M = 46.32            # Maßstab auf dem Laufweg: 0,367 m Schrittlänge je Zyklus = 17 px
CAM_X = -4.6
CAM_H = 0.9                 # Augenhöhe über dem Kai (Kamera waagrecht, Bildlage über Objektivverschiebung)
HORIZON_ROW = 126.3         # Zeile des Horizonts im 426×240-Bild
STRIDE_PX = 17              # Vorschub je Laufzyklus in Zielpixeln

# Requisiten, die für den Bildausschnitt versetzt werden (Godot: neues x, neues z oder None = gleiche Tiefe)
MOVES = {
    "LanternPost": (0.2, None),
    "Barrel1": (-6.05, -0.2),
    "Barrel2": (-5.4, -0.62),
}


def hex_lin(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def rgba(h, a=1.0):
    return (*hex_lin(h), a)


# ------------------------------------------------------------------------------------------
# Laden
# ------------------------------------------------------------------------------------------
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = 24
    return sc


def import_glb(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    return [o for o in bpy.data.objects if o not in before]


def load_harbor(move_props=True):
    objs = import_glb(os.path.join(SHARED3D, "harbor.glb"))
    if move_props:
        for name, (gx, gz) in MOVES.items():
            ob = bpy.data.objects[name]
            ob.location.x = gx
            if gz is not None:
                ob.location.y = -gz
    return {o.name: o for o in objs}


def load_badger():
    objs = import_glb(os.path.join(SHARED3D, "badger.glb"))
    arm = None
    for o in objs:
        if o.type == "ARMATURE":
            arm = o
        if o.name.startswith("Icosphere"):
            o.hide_render = True
            o.hide_viewport = True
    arm.rotation_mode = "XYZ"
    ad = arm.animation_data
    for t in list(ad.nla_tracks):
        ad.nla_tracks.remove(t)
    for o in objs:
        if o.type == "MESH" and o.name.startswith(("Badger", "Parcel")):
            sub = o.modifiers.new("Glatt", "SUBSURF")
            sub.levels = 1
            sub.render_levels = 1
            o.data.shade_smooth() if hasattr(o.data, "shade_smooth") else None
    return arm, objs


def set_action(arm, name, t):
    """Pose der Animation `name` zur Zeit t (s) setzen; Animationen haben 24 Bilder/s."""
    ad = arm.animation_data
    act = bpy.data.actions[name]
    if ad.action != act:
        ad.action = act
        if hasattr(ad, "action_slot") and act.slots:
            ad.action_slot = act.slots[0]
    sc = bpy.context.scene
    f = t * 24.0
    sc.frame_set(int(math.floor(f)), subframe=f - math.floor(f))


# ------------------------------------------------------------------------------------------
# Materialien: glänzender CG-Look der vorgerenderten Spiele (1994): Glanzpunkte, Maserung,
# Fellrauschen. Nur prozedurale Knoten, keine Texturdateien.
# ------------------------------------------------------------------------------------------
MATS = {
    # Name: Farbe, Rauheit, Metall, Detail (Art, Maßstab, Farbstreuung, Bump)
    "Stone": ("#8E887C", 0.75, 0.0, ("stone", 2.2, 0.24, 0.5)),
    "StoneDark": ("#5E5951", 0.75, 0.0, ("stone", 2.5, 0.24, 0.5)),
    "Wood": ("#94663E", 0.55, 0.0, ("wood", 1.0, 0.22, 0.25)),
    "WoodDark": ("#563A26", 0.6, 0.0, ("wood", 1.0, 0.22, 0.25)),
    "WhitePaint": ("#E6E1D6", 0.42, 0.0, ("paint", 3.0, 0.05, 0.08)),
    "RedPaint": ("#B32A22", 0.38, 0.0, ("paint", 3.0, 0.08, 0.08)),
    "Roof": ("#46505F", 0.55, 0.0, ("stone", 4.0, 0.14, 0.25)),
    "Rope": ("#BFA77A", 0.8, 0.0, ("rope", 14.0, 0.18, 0.4)),
    "Metal": ("#3E4045", 0.35, 0.85, ("paint", 6.0, 0.1, 0.1)),
    "Rock": ("#6E6A64", 0.85, 0.0, ("rock", 0.8, 0.3, 0.8)),
    "Sand": ("#C2AD84", 0.95, 0.0, ("rock", 2.0, 0.1, 0.2)),
    "Grass": ("#5F7A3E", 0.9, 0.0, ("grass", 1.5, 0.25, 0.3)),
    # Dachs: glatte Flächen mit Glanz statt feinem Rauschen (wird bei 46 px sonst zu Farbbrei)
    "FurDark": ("#4A3F3B", 0.34, 0.0, None),
    "FurLight": ("#F2E6D0", 0.38, 0.0, None),
    "Cap": ("#3F5E2A", 0.4, 0.0, None),
    "Vest": ("#557A34", 0.42, 0.0, None),
    "Shirt": ("#F0E0C4", 0.55, 0.0, None),
    "Scarf": ("#B8262C", 0.42, 0.0, None),
    "Satchel": ("#73402A", 0.3, 0.0, None),
    "Parcel": ("#C68F59", 0.55, 0.0, None),
    "Brass": ("#D09A3A", 0.22, 1.0, None),
    "Nose": ("#2A201D", 0.12, 0.0, None),
    "Eye": ("#E9E2D2", 0.15, 0.0, None),   # hell: liest sich bei 46 px als Augenglanz (Sprite-Kniff)
}


SHEEN = {"FurDark": 0.5, "FurLight": 0.3, "Cap": 0.3, "Vest": 0.3, "Scarf": 0.5}


def _n(nt, kind, loc=(0, 0), **props):
    n = nt.nodes.new(kind)
    n.location = loc
    for k, v in props.items():
        setattr(n, k, v)
    return n


def build_material(mat, color, rough, metal, detail, coat=0.0):
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = _n(nt, "ShaderNodeOutputMaterial", (600, 0))
    bsdf = _n(nt, "ShaderNodeBsdfPrincipled", (300, 0))
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Specular IOR Level"].default_value = 0.6
    if coat:
        bsdf.inputs["Coat Weight"].default_value = coat
    if mat.name.split(".")[0] in SHEEN:
        bsdf.inputs["Sheen Weight"].default_value = SHEEN[mat.name.split(".")[0]]
    base = rgba(color)
    if detail is None:
        bsdf.inputs["Base Color"].default_value = base
        return mat
    kind, scale, var, bump_s = detail
    tc = _n(nt, "ShaderNodeTexCoord", (-900, 0))
    vec = tc.outputs["UV"]
    if kind == "wood":
        # Maserung entlang der längeren UV-Achse: Bänder + Verzerrung
        mp = _n(nt, "ShaderNodeMapping", (-700, 0))
        mp.inputs["Scale"].default_value = (scale * 1.0, scale * 9.0, 1.0)
        nt.links.new(vec, mp.inputs["Vector"])
        tex = _n(nt, "ShaderNodeTexWave", (-500, 0), wave_type="BANDS", bands_direction="Y")
        tex.inputs["Scale"].default_value = 2.5
        tex.inputs["Distortion"].default_value = 6.0
        tex.inputs["Detail"].default_value = 3.0
        nt.links.new(mp.outputs[0], tex.inputs["Vector"])
        fac = tex.outputs["Fac"]
    elif kind == "rope":
        tex = _n(nt, "ShaderNodeTexWave", (-500, 0), wave_type="BANDS", bands_direction="DIAGONAL")
        tex.inputs["Scale"].default_value = scale
        tex.inputs["Distortion"].default_value = 1.0
        nt.links.new(vec, tex.inputs["Vector"])
        fac = tex.outputs["Fac"]
    elif kind == "knit":
        mp = _n(nt, "ShaderNodeMapping", (-700, 0))
        mp.inputs["Scale"].default_value = (scale, scale * 0.35, 1.0)
        nt.links.new(vec, mp.inputs["Vector"])
        tex = _n(nt, "ShaderNodeTexWave", (-500, 0), wave_type="BANDS", bands_direction="X")
        tex.inputs["Scale"].default_value = 1.0
        tex.inputs["Distortion"].default_value = 2.0
        nt.links.new(mp.outputs[0], tex.inputs["Vector"])
        fac = tex.outputs["Fac"]
    elif kind == "stone":
        vor = _n(nt, "ShaderNodeTexVoronoi", (-600, 150))
        vor.inputs["Scale"].default_value = scale
        nt.links.new(vec, vor.inputs["Vector"])
        noi = _n(nt, "ShaderNodeTexNoise", (-600, -150))
        noi.inputs["Scale"].default_value = scale * 6
        noi.inputs["Detail"].default_value = 6
        nt.links.new(vec, noi.inputs["Vector"])
        mix = _n(nt, "ShaderNodeMix", (-350, 0), data_type="FLOAT")
        mix.inputs["Factor"].default_value = 0.45
        nt.links.new(vor.outputs["Distance"], mix.inputs["A"])
        nt.links.new(noi.outputs["Fac"], mix.inputs["B"])
        fac = mix.outputs["Result"]
    else:  # rock, grass, paint, fur, cloth: Rauschen
        noi = _n(nt, "ShaderNodeTexNoise", (-500, 0))
        noi.inputs["Scale"].default_value = scale
        noi.inputs["Detail"].default_value = 8 if kind in ("rock", "grass") else 3
        noi.inputs["Roughness"].default_value = 0.6
        nt.links.new(vec, noi.inputs["Vector"])
        fac = noi.outputs["Fac"]
    # Farbe: Grundfarbe ± var
    mr = _n(nt, "ShaderNodeMapRange", (-200, 200))
    mr.inputs["From Min"].default_value = 0.25
    mr.inputs["From Max"].default_value = 0.75
    mr.inputs["To Min"].default_value = 1.0 - var
    mr.inputs["To Max"].default_value = 1.0 + var
    nt.links.new(fac, mr.inputs["Value"])
    mul = _n(nt, "ShaderNodeMix", (50, 200), data_type="RGBA", blend_type="MULTIPLY")
    mul.inputs["Factor"].default_value = 1.0
    mul.inputs["A"].default_value = base
    nt.links.new(mr.outputs["Result"], mul.inputs["B"])
    nt.links.new(mul.outputs["Result"], bsdf.inputs["Base Color"])
    if kind == "grass":
        hue = _n(nt, "ShaderNodeHueSaturation", (150, 300))
        nt.links.new(mul.outputs["Result"], hue.inputs["Color"])
        nt.links.new(hue.outputs["Color"], bsdf.inputs["Base Color"])
        hue.inputs["Hue"].default_value = 0.47
    bump = _n(nt, "ShaderNodeBump", (50, -200))
    bump.inputs["Strength"].default_value = bump_s
    bump.inputs["Distance"].default_value = 0.02
    nt.links.new(fac, bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def water_material(mat, phase_w=0.0):
    """Wasser: dunkel, spiegelnd, Wellen als Bump aus 4D-Rauschen (W = Phase auf einem Kreis)."""
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = _n(nt, "ShaderNodeOutputMaterial", (700, 0))
    bsdf = _n(nt, "ShaderNodeBsdfPrincipled", (400, 0))
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    bsdf.inputs["Base Color"].default_value = rgba("#0E2430")
    bsdf.inputs["Roughness"].default_value = 0.06
    bsdf.inputs["Specular IOR Level"].default_value = 1.0
    bsdf.inputs["IOR"].default_value = 1.33
    geo = _n(nt, "ShaderNodeNewGeometry", (-900, 0))
    mp = _n(nt, "ShaderNodeMapping", (-700, 0))
    mp.inputs["Scale"].default_value = (0.35, 1.4, 1.0)   # lange, flache Wellen quer zum Blick
    nt.links.new(geo.outputs["Position"], mp.inputs["Vector"])
    noi = _n(nt, "ShaderNodeTexNoise", (-450, 0), noise_dimensions="4D")
    noi.inputs["Scale"].default_value = 1.6
    noi.inputs["Detail"].default_value = 4.0
    noi.inputs["Roughness"].default_value = 0.55
    noi.inputs["W"].default_value = phase_w
    nt.links.new(mp.outputs[0], noi.inputs["Vector"])
    bump = _n(nt, "ShaderNodeBump", (100, -150))
    bump.inputs["Strength"].default_value = 0.22
    bump.inputs["Distance"].default_value = 0.05
    nt.links.new(noi.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    mat["noise_node"] = noi.name
    return mat


def glass_material(mat, strength=6.0):
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = _n(nt, "ShaderNodeOutputMaterial", (400, 0))
    bsdf = _n(nt, "ShaderNodeBsdfPrincipled", (100, 0))
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    bsdf.inputs["Base Color"].default_value = rgba("#FFD27A")
    bsdf.inputs["Roughness"].default_value = 0.3
    bsdf.inputs["Emission Color"].default_value = rgba("#FFB850")
    bsdf.inputs["Emission Strength"].default_value = strength
    return mat


def apply_materials(objs=None):
    for mat in bpy.data.materials:
        name = mat.name.split(".")[0]
        if name in MATS:
            c, r, m, d = MATS[name]
            build_material(mat, c, r, m, d, coat=0.6 if name in ("Eye", "Nose") else 0.0)
        elif name == "Water":
            water_material(mat)
        elif name == "Glass":
            glass_material(mat)


def unique_glass(obj_name, strength):
    """Eigenes Glasmaterial für ein Objekt (Laterne, Leuchtfeuer, Fenster einzeln regeln)."""
    ob = bpy.data.objects[obj_name]
    m = bpy.data.materials.new(f"Glass_{obj_name}")
    glass_material(m, strength)
    for slot in ob.material_slots:
        slot.material = m
    return m


# ------------------------------------------------------------------------------------------
# Himmel: Abendverlauf, Wolkendecke als Ebene im Weltshader, Glutband am Horizont
# ------------------------------------------------------------------------------------------
SUN_AZ = math.radians(-18)  # Glut leicht links der Bildmitte (Drehung um Z, 0 = +Y)


def world_sky(strength=1.0, clouds=True):
    sc = bpy.context.scene
    world = bpy.data.worlds.new("Dusk")
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = _n(nt, "ShaderNodeOutputWorld", (1400, 0))
    bg = _n(nt, "ShaderNodeBackground", (1200, 0))
    bg.inputs["Strength"].default_value = strength
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    tc = _n(nt, "ShaderNodeTexCoord", (-1400, 0))
    sep = _n(nt, "ShaderNodeSeparateXYZ", (-1200, 0))
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    # Höhe über dem Horizont: z (Richtungsvektor ist normiert)
    ramp = _n(nt, "ShaderNodeValToRGB", (-800, 200))
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    cr = ramp.color_ramp
    cr.interpolation = "EASE"
    stops = [(0.0, "#F2A35E"), (0.035, "#E58A62"), (0.09, "#B86C7E"), (0.2, "#6E5A93"),
             (0.38, "#3A3F78"), (0.7, "#1B2350"), (1.0, "#121a3c")]
    cr.elements[0].position, cr.elements[0].color = stops[0][0], rgba(stops[0][1])
    cr.elements[1].position, cr.elements[1].color = stops[-1][0], rgba(stops[-1][1])
    for p, c in stops[1:-1]:
        e = cr.elements.new(p)
        e.color = rgba(c)
    # Glut zur Sonne hin: Richtung in der Ebene · Sonnenrichtung
    sun_dir = Vector((math.sin(SUN_AZ), math.cos(SUN_AZ), 0.0))
    dot = _n(nt, "ShaderNodeVectorMath", (-1000, -300), operation="DOT_PRODUCT")
    nt.links.new(tc.outputs["Generated"], dot.inputs[0])
    dot.inputs[1].default_value = sun_dir
    glow_r = _n(nt, "ShaderNodeMapRange", (-800, -300))
    glow_r.inputs["From Min"].default_value = 0.2
    glow_r.inputs["From Max"].default_value = 1.0
    nt.links.new(dot.outputs["Value"], glow_r.inputs["Value"])
    lowz = _n(nt, "ShaderNodeMapRange", (-800, -500))
    lowz.inputs["From Min"].default_value = 0.16
    lowz.inputs["From Max"].default_value = 0.0
    nt.links.new(sep.outputs["Z"], lowz.inputs["Value"])
    gm = _n(nt, "ShaderNodeMath", (-600, -400), operation="MULTIPLY")
    nt.links.new(glow_r.outputs["Result"], gm.inputs[0])
    nt.links.new(lowz.outputs["Result"], gm.inputs[1])
    gp = _n(nt, "ShaderNodeMath", (-450, -400), operation="POWER")
    nt.links.new(gm.outputs[0], gp.inputs[0])
    gp.inputs[1].default_value = 1.6
    glow = _n(nt, "ShaderNodeMix", (-200, 100), data_type="RGBA", blend_type="ADD")
    nt.links.new(gp.outputs[0], glow.inputs["Factor"])
    nt.links.new(ramp.outputs["Color"], glow.inputs["A"])
    glow.inputs["B"].default_value = rgba("#FFB35A")
    sky = glow.outputs["Result"]
    if clouds:
        # Wolkenbänke in Winkelkoordinaten (Azimut, Höhe): flache, breite Schichten wie gemalt
        az = _n(nt, "ShaderNodeMath", (-1000, 700), operation="ARCTAN2")
        nt.links.new(sep.outputs["X"], az.inputs[0])
        nt.links.new(sep.outputs["Y"], az.inputs[1])
        el = _n(nt, "ShaderNodeMath", (-1000, 550), operation="ARCSINE")
        nt.links.new(sep.outputs["Z"], el.inputs[0])

        def cloud_noise(dy, x0):
            e2 = _n(nt, "ShaderNodeMath", (-850, 550 + x0), operation="ADD")
            nt.links.new(el.outputs[0], e2.inputs[0])
            e2.inputs[1].default_value = dy
            cx = _n(nt, "ShaderNodeCombineXYZ", (-700, 600 + x0))
            ax = _n(nt, "ShaderNodeMath", (-850, 700 + x0), operation="MULTIPLY")
            nt.links.new(az.outputs[0], ax.inputs[0])
            ax.inputs[1].default_value = 2.6
            ey = _n(nt, "ShaderNodeMath", (-850, 450 + x0), operation="MULTIPLY")
            nt.links.new(e2.outputs[0], ey.inputs[0])
            ey.inputs[1].default_value = 11.0
            nt.links.new(ax.outputs[0], cx.inputs["X"])
            nt.links.new(ey.outputs[0], cx.inputs["Y"])
            cx.inputs["Z"].default_value = 4.2
            nz = _n(nt, "ShaderNodeTexNoise", (-500, 600 + x0))
            nz.inputs["Scale"].default_value = 1.0
            nz.inputs["Detail"].default_value = 5.0
            nz.inputs["Roughness"].default_value = 0.55
            nt.links.new(cx.outputs[0], nz.inputs["Vector"])
            return nz.outputs["Fac"]

        n0 = cloud_noise(0.0, 0)
        nb = cloud_noise(-0.02, 300)    # etwas tiefer: ist die Wolke unten dünner, ist hier die Unterkante
        cm = _n(nt, "ShaderNodeMapRange", (-200, 600))
        cm.inputs["From Min"].default_value = 0.52
        cm.inputs["From Max"].default_value = 0.58
        nt.links.new(n0, cm.inputs["Value"])
        band = _n(nt, "ShaderNodeMapRange", (-200, 800))
        band.inputs["From Min"].default_value = 0.42
        band.inputs["From Max"].default_value = 0.18
        nt.links.new(el.outputs[0], band.inputs["Value"])
        band2 = _n(nt, "ShaderNodeMapRange", (-200, 950))
        band2.inputs["From Min"].default_value = 0.02
        band2.inputs["From Max"].default_value = 0.06
        nt.links.new(el.outputs[0], band2.inputs["Value"])
        m1 = _n(nt, "ShaderNodeMath", (0, 700), operation="MULTIPLY")
        nt.links.new(cm.outputs["Result"], m1.inputs[0])
        nt.links.new(band.outputs["Result"], m1.inputs[1])
        m2 = _n(nt, "ShaderNodeMath", (150, 700), operation="MULTIPLY")
        nt.links.new(m1.outputs[0], m2.inputs[0])
        nt.links.new(band2.outputs["Result"], m2.inputs[1])
        # Unterkante: n0 - nb groß → angestrahlt von der Glut
        dif = _n(nt, "ShaderNodeMath", (0, 400), operation="SUBTRACT")
        nt.links.new(n0, dif.inputs[0])
        nt.links.new(nb, dif.inputs[1])
        rim = _n(nt, "ShaderNodeMapRange", (150, 400))
        rim.inputs["From Min"].default_value = 0.008
        rim.inputs["From Max"].default_value = 0.06
        nt.links.new(dif.outputs[0], rim.inputs["Value"])
        glow2 = _n(nt, "ShaderNodeMapRange", (150, 250))
        glow2.inputs["From Min"].default_value = -0.2
        glow2.inputs["From Max"].default_value = 1.0
        glow2.inputs["To Min"].default_value = 0.25
        nt.links.new(dot.outputs["Value"], glow2.inputs["Value"])
        rimg = _n(nt, "ShaderNodeMath", (300, 300), operation="MULTIPLY")
        nt.links.new(rim.outputs["Result"], rimg.inputs[0])
        nt.links.new(glow2.outputs["Result"], rimg.inputs[1])
        # Wolkenkörper: dunkles Violett, nach unten zur Glut hin wärmer
        body = _n(nt, "ShaderNodeValToRGB", (300, 600))
        nt.links.new(el.outputs[0], body.inputs["Fac"])
        body.color_ramp.elements[0].position = 0.02
        body.color_ramp.elements[0].color = rgba("#6A4A6E")
        body.color_ramp.elements[1].position = 0.35
        body.color_ramp.elements[1].color = rgba("#2E2A55")
        lit = _n(nt, "ShaderNodeMix", (500, 450), data_type="RGBA")
        nt.links.new(rimg.outputs[0], lit.inputs["Factor"])
        nt.links.new(body.outputs["Color"], lit.inputs["A"])
        lit.inputs["B"].default_value = rgba("#F7A060")
        mixc = _n(nt, "ShaderNodeMix", (800, 100), data_type="RGBA")
        nt.links.new(m2.outputs[0], mixc.inputs["Factor"])
        nt.links.new(sky, mixc.inputs["A"])
        nt.links.new(lit.outputs["Result"], mixc.inputs["B"])
        sky = mixc.outputs["Result"]
    nt.links.new(sky, bg.inputs["Color"])
    return world


# ------------------------------------------------------------------------------------------
# Lichter
# ------------------------------------------------------------------------------------------
def _link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def sun(name, direction, energy, color, angle=3.0):
    ld = bpy.data.lights.new(name, "SUN")
    ld.energy = energy
    ld.color = hex_lin(color)
    ld.angle = math.radians(angle)
    o = _link(bpy.data.objects.new(name, ld))
    o.rotation_euler = Vector(direction).normalized().to_track_quat("-Z", "Y").to_euler()
    return o


def point(name, pos, energy, color="#FFB860", radius=0.05):
    ld = bpy.data.lights.new(name, "POINT")
    ld.energy = energy
    ld.color = hex_lin(color)
    ld.shadow_soft_size = radius
    o = _link(bpy.data.objects.new(name, ld))
    o.location = pos
    return o


def scene_lights(lantern=1.0, window=1.0, lighthouse=1.0):
    """Abendlicht: warmes Restlicht von hinten links (Kante), kühles Himmelslicht von vorn oben,
    Laterne, Fenster, Leuchtfeuer."""
    sun("Glut", (0.25, -0.95, -0.17), 2.2, "#FF9A5A", angle=4)        # von der Horizontglut, Gegenlicht
    sun("Himmel", (0.45, 0.6, -0.65), 1.4, "#B9B4E6", angle=12)       # von vorn links oben, kühl
    out = {}
    if "LanternLight" in bpy.data.objects:
        ll = bpy.data.objects["LanternLight"].matrix_world.translation
        out["lantern"] = point("LanternPt", ll, 70 * lantern, "#FFB050", 0.06)
    if "CottageWindow" in bpy.data.objects:
        cw = bpy.data.objects["CottageWindow"].matrix_world.translation
        out["window"] = point("WindowPt", cw + Vector((0, -0.45, 0)), 35 * window, "#FFB060", 0.2)
    if "LighthouseLight" in bpy.data.objects:
        lh = bpy.data.objects["LighthouseLight"].matrix_world.translation
        out["lighthouse"] = point("LighthousePt", lh, 900 * lighthouse, "#FFD080", 0.3)
    return out


def sprite_lights():
    """Licht für frei bewegliche Sprites (Dachs): dieselbe Richtung wie die Szene, dazu ein
    warmes Kantenlicht von rechts (steht für die Laterne) statt der Punktlichter."""
    sun("Glut", (0.25, -0.95, -0.17), 4.0, "#FF9A5A", angle=4)
    sun("Himmel", (0.45, 0.6, -0.65), 3.6, "#ECEAF6", angle=6)
    sun("Laterne", (-0.9, 0.35, -0.25), 1.1, "#FFD6A8", angle=8)


# ------------------------------------------------------------------------------------------
# Kameras
# ------------------------------------------------------------------------------------------
def bg_camera():
    """Perspektivische Szenenkamera: waagrecht, Augenhöhe CAM_H, Laufweg im Abstand CAM_D mit
    PX_PER_M Pixeln je Meter; Horizont per Objektivverschiebung auf HORIZON_ROW."""
    cd = bpy.data.cameras.new("BGCam")
    cd.sensor_fit = "VERTICAL"
    cd.sensor_height = 24.0
    f_px = PX_PER_M * CAM_D                   # Brennweite in Zielpixeln
    cd.lens = f_px * cd.sensor_height / H     # mm
    # Objektivverschiebung: bei sensor_fit VERTICAL in Anteilen der Bildhöhe (nachgemessen)
    cd.shift_y = (HORIZON_ROW - H / 2) / H
    cd.clip_start = 0.1
    cd.clip_end = 3000.0
    co = _link(bpy.data.objects.new("BGCam", cd))
    co.location = (CAM_X, WALK_Y - CAM_D, CAM_H)
    co.rotation_euler = Euler((math.radians(90), 0, 0), "XYZ")
    bpy.context.scene.camera = co
    return co


def sprite_camera(cx, z_bottom, w_px, h_px, y=None):
    """Orthografische Kamera mit PX_PER_M (Zielpixel) je Meter; Ausschnitt w_px × h_px,
    linke Kante bei cx - w/2, untere Kante bei z_bottom (Meter)."""
    cd = bpy.data.cameras.new("SpriteCam")
    cd.type = "ORTHO"
    cd.sensor_fit = "HORIZONTAL" if w_px >= h_px else "VERTICAL"
    cd.ortho_scale = max(w_px, h_px) / PX_PER_M
    cd.clip_start = 0.1
    cd.clip_end = 100.0
    co = _link(bpy.data.objects.new("SpriteCam", cd))
    co.location = (cx, (WALK_Y if y is None else y) - 20.0, z_bottom + h_px / PX_PER_M / 2)
    co.rotation_euler = Euler((math.radians(90), 0, 0), "XYZ")
    sc = bpy.context.scene
    sc.camera = co
    sc.render.resolution_x = w_px * SS
    sc.render.resolution_y = h_px * SS
    return co


def render_setup(engine="CYCLES", samples=96, transparent=False, w=W, h=H, denoise=True):
    sc = bpy.context.scene
    sc.render.engine = engine
    sc.render.resolution_x = w * SS
    sc.render.resolution_y = h * SS
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = transparent
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.image_settings.color_depth = "8"
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = 0.0
    if engine == "CYCLES":
        cy = sc.cycles
        cy.samples = samples
        cy.use_denoising = denoise
        cy.use_adaptive_sampling = True
        cy.max_bounces = 6
        cy.caustics_reflective = False
        cy.caustics_refractive = False
        cy.seed = 7
        try:
            prefs = bpy.context.preferences.addons["cycles"].preferences
            prefs.compute_device_type = "METAL"
            prefs.get_devices()
            for d in prefs.devices:
                d.use = True
            cy.device = "GPU"
        except Exception as e:  # CPU als Rückfall
            print("GPU nicht verfügbar:", e)
        sc.render.filter_size = 1.2
    else:
        sc.eevee.taa_render_samples = samples
    return sc


def arg_list():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


# ------------------------------------------------------------------------------------------
# Material-Kennungsbild: jede Fläche in einer festen Kennfarbe (1 Strahl je Pixel, ohne Filter).
# Damit verkleinert reduce_sprites.py nach Materialmehrheit: harte Kanten zwischen Kostümteilen,
# weiche Schattierung innerhalb eines Teils.
# ------------------------------------------------------------------------------------------
ID_NAMES = ["FurDark", "FurLight", "Cap", "Brass", "Vest", "Shirt", "Scarf", "Satchel", "Parcel", "Nose",
            "Eye", "Stone", "StoneDark", "Wood", "WoodDark", "WhitePaint", "RedPaint", "Roof", "Glass",
            "Rope", "Metal", "Rock", "Sand", "Grass", "Water", "Beam"]


def id_rgb8(i):
    return ((i + 1) * 9, 200, 60)


class IdSwap:
    """Tauscht die Materialien aller sichtbaren Meshes gegen Kennfarben und zurück."""

    def __init__(self, objs):
        self.objs = [o for o in objs if o.type == "MESH"]
        self.cache = {}

    def _id_mat(self, base):
        name = base.split(".")[0]
        if name.startswith("Glass"):
            name = "Glass"
        i = ID_NAMES.index(name) if name in ID_NAMES else len(ID_NAMES)
        if i not in self.cache:
            m = bpy.data.materials.new(f"ID_{i}")
            m.use_nodes = True
            nt = m.node_tree
            for n in list(nt.nodes):
                nt.nodes.remove(n)
            out = nt.nodes.new("ShaderNodeOutputMaterial")
            em = nt.nodes.new("ShaderNodeEmission")
            em.inputs["Color"].default_value = rgba("#%02x%02x%02x" % id_rgb8(i))
            nt.links.new(em.outputs[0], out.inputs["Surface"])
            self.cache[i] = m
        return self.cache[i]

    def render(self, sc, path):
        saved = []
        for o in self.objs:
            for k, slot in enumerate(o.material_slots):
                saved.append((o, k, slot.material))
                if slot.material is not None:
                    slot.material = self._id_mat(slot.material.name)
        cy = sc.cycles
        keep = (cy.samples, cy.use_denoising, sc.render.filter_size, cy.use_adaptive_sampling)
        cy.samples, cy.use_denoising, sc.render.filter_size, cy.use_adaptive_sampling = 1, False, 0.01, False
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        cy.samples, cy.use_denoising, sc.render.filter_size, cy.use_adaptive_sampling = keep
        for o, k, m in saved:
            o.material_slots[k].material = m
