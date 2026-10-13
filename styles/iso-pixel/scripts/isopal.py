"""Gemeinsame Palette des Eintrags iso-pixel: Farbleitern je Material (dunkel -> hell) und das Iso-Licht.

Alle Kacheln, die Requisiten aus Blender und der Dachs werden auf diese Leitern gesetzt. Das Licht kommt
von links oben vorn: Oberseiten Stufe 3, linke (vordere) Flächen Stufe 2, rechte Flächen Stufe 1.
"""
import numpy as np


def hx(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


RAMPS_HEX = {
    # Dachs
    "FurDark":   ["#232030", "#37334a", "#4f4a60", "#6b6582"],     # etwas heller als Schwarz: Arme vor dunklem Grund lesbar
    "FurLight":  ["#8a7f94", "#b8acb0", "#ddd2c3", "#f5ecdb"],
    "Cap":       ["#1c2f25", "#2a4630", "#3b5f37", "#567a45"],
    "Brass":     ["#6b4a1e", "#a87a2c", "#d8ad48", "#f2d77a"],
    "Vest":      ["#1f3428", "#304c37", "#466741", "#62844e"],
    "Shirt":     ["#8b7e86", "#b6a796", "#dacbb0", "#f1e4c8"],
    "Scarf":     ["#561824", "#87222f", "#bb3339", "#de5d48"],
    "Satchel":   ["#3a2119", "#5a3522", "#7e4f2e", "#a26c40"],
    "Nose":      ["#120e18", "#1f1a27", "#332b3a", "#4f4557"],
    "Eye":       ["#100c16", "#100c16", "#100c16", "#100c16"],
    "Parcel":    ["#6a492c", "#98703f", "#c39a5b", "#e2bf80"],
    # Hafen
    "Stone":     ["#3d3848", "#5b5563", "#7d777e", "#a29b98"],
    "StoneDark": ["#29252f", "#3c3742", "#524c56", "#6c656c"],
    "Roof":      ["#252838", "#33394f", "#475068", "#606c86"],
    "Wood":      ["#3c2922", "#5c3e2c", "#835839", "#a7764f"],
    "WoodDark":  ["#231917", "#382822", "#50382c", "#6a4c38"],
    "WhitePaint": ["#8c879e", "#b7b2c2", "#dcd8de", "#f5f1eb"],
    "RedPaint":  ["#581924", "#88242f", "#b5363a", "#d8574a"],
    "Glass":     ["#e8963c", "#ffc35a", "#ffe08a", "#fff4c8"],
    "Rope":      ["#6c583b", "#937d4d", "#bca26a", "#dbc48e"],
    "Metal":     ["#1b1b25", "#2b2c37", "#41424e", "#5d5f6e"],
    "Rock":      ["#2e2b35", "#47424b", "#625b62", "#82797a"],
    "Sand":      ["#86705a", "#ad9274", "#ccae8b", "#e4caa2"],
    "Grass":     ["#253d2c", "#355533", "#4f7340", "#6d924e"],
    "Earth":     ["#2c2129", "#43312f", "#5e4637", "#7a5d45"],
    "Water":     ["#13213a", "#1b3452", "#264d68", "#3a6c82"],
}


def _oklab(rgb):
    c = np.asarray(rgb, np.float64) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]])
    M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]])
    return np.cbrt(c @ M1.T) @ M2.T


def _srgb(lab):
    M2i = np.array([[1.0, 0.3963377774, 0.2158037573], [1.0, -0.1055613458, -0.0638541728],
                    [1.0, -0.0894841775, -1.2914855480]])
    M1i = np.array([[4.0767416621, -3.3077115913, 0.2309699292], [-1.2684380046, 2.6097574011, -0.3413193965],
                    [-0.0041960863, -0.7034186147, 1.7076147010]])
    lin = (np.asarray(lab) @ M2i.T) ** 3 @ M1i.T
    lin = np.clip(lin, 0, 1)
    c = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055)
    return tuple(int(round(v * 255)) for v in c)


# Dämmerung: alle Materialien (außer Leuchtendem) dunkler, kühler und etwas entsättigt, in Oklab
DUSK = {"L": 0.84, "chroma": 0.82, "da": 0.006, "db": -0.024}


def dusk(rgb):
    L, a, b = _oklab(rgb)
    return _srgb((L * DUSK["L"], a * DUSK["chroma"] + DUSK["da"], b * DUSK["chroma"] + DUSK["db"]))


RAMPS_DAY = {k: [hx(c) for c in v] for k, v in RAMPS_HEX.items()}
RAMPS = {k: (v if k in ("Glass", "Eye") else [dusk(c) for c in v]) for k, v in RAMPS_DAY.items()}
OUTLINE = hx("#120f1c")          # Außenkontur aller Figuren und Requisiten
EMISSIVE = {"Glass"}             # leuchtet, unabhängig vom Licht

# Iso-Licht (Blender-Welt, Z oben): von links oben vorn
_R = np.array([0.70710678, 0.70710678, 0.0])
_D = np.array([-0.61237244, 0.61237244, -0.5])
L = -0.6 * _R + 0.4 * (-_D) + np.array([0.0, 0.0, 0.7])
L = L / np.linalg.norm(L)
THRESH = (0.35, 0.60, 0.85)      # Halb-Lambert -> Stufe 0..3


def tone(nrm):
    """nrm: (..., 3) Normalen -> Stufen 0..3 (Oberseite 3, links 2, rechts 1)."""
    hl = 0.5 + 0.5 * (nrm @ L)
    t = np.zeros(hl.shape, np.int8)
    for th in THRESH:
        t += (hl >= th)
    return t


def all_colors(day=False):
    out = {OUTLINE}
    for v in (RAMPS_DAY if day else RAMPS).values():
        out.update(v)
    return sorted(out)
