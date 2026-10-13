#!/usr/bin/env python3
"""Gemeinsame 256-Farben-Palette, Farbtabelle (COLORMAP) und Einrastfunktionen des Raycaster-Eintrags.

Aufbau wie die Paletten der Sektor-Shooter 1993–1996: 16 Rampen zu je 16 Stufen, jede Rampe von hell
(Index 16·r) nach dunkel (16·r + 15). Index 255 ist reserviert: "durchsichtig" in Sprites und "Himmel"
im Bildspeicher; keine Textur und keine Farbtabellenzeile verweist darauf.

Farbtabelle: 32 Lichtstufen x 256 Indizes. Zeile k enthält für jede Palettenfarbe die nächstliegende
Palettenfarbe nach Abdunkeln um k/32 in Richtung NIGHT (sehr dunkles Nachtblau). Zeile 0 = unverändert.

    python3 scripts/rc_palette.py            # schreibt assets/palette.png, assets/colormap.png, Vorschau

Als Modul: from rc_palette import PALETTE, quantize, nearest_index
"""
import json
import pathlib

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent
ASSETS = ENTRY / "assets"

TRANSPARENT = 255
NIGHT = (10, 10, 24)
LEVELS = 32

# Rampen: Name, Ankerfarben hell -> dunkel (sRGB). Zwischen den Ankern wird in OKLab interpoliert.
RAMPS = [
    ("grau", ["#ecebe6", "#9a9894", "#5c5b59", "#121216"]),
    ("granit", ["#f4efe4", "#b3aa9c", "#6c645a", "#14110e"]),
    ("schiefer", ["#c4cedc", "#7e8a9a", "#46505e", "#0b0d14"]),
    ("holz", ["#e4c496", "#a98058", "#5e4430", "#130d09"]),
    ("rostbraun", ["#e0a080", "#a8604a", "#5c3024", "#120806"]),
    ("rot", ["#ffa08a", "#d8483a", "#8e1c18", "#1a0505"]),
    ("orange", ["#ffe0a0", "#ffa040", "#c05818", "#1e0a04"]),
    ("gelb", ["#fffff0", "#fff090", "#f0b830", "#2a1a04"]),
    ("gruen", ["#b4d498", "#6a9258", "#34522c", "#060c06"]),
    ("oliv", ["#e2daa0", "#a49c5c", "#5c5830", "#0d0c06"]),
    ("meer", ["#a0e0dc", "#4c98a0", "#24525e", "#040a10"]),
    ("blau", ["#b4c8f8", "#6a84c8", "#2c3c78", "#06081c"]),
    ("violett", ["#e4c4f0", "#a07ab8", "#563c74", "#0c0616"]),
    ("rosa", ["#ffd0c4", "#f09090", "#a84868", "#18060e"]),
    ("creme", ["#fffcf4", "#f2e6cc", "#c4b08c", "#1a150e"]),
    ("nacht", ["#5a5470", "#2c2a44", "#16152a", "#000000"]),
]


# ---------------------------------------------------------------------------------------------
# OKLab

def srgb_to_linear(c):
    c = np.asarray(c, dtype=np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055) * 255.0


def to_oklab(rgb):
    lin = srgb_to_linear(rgb)
    m1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                   [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]])
    lms = lin @ m1.T
    lms = np.cbrt(lms)
    m2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                   [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]])
    return lms @ m2.T


def from_oklab(lab):
    m2i = np.array([[1.0, 0.3963377774, 0.2158037573],
                    [1.0, -0.1055613458, -0.0638541728],
                    [1.0, -0.0894841775, -1.2914855480]])
    lms = lab @ m2i.T
    lms = lms ** 3
    m1i = np.array([[4.0767416621, -3.3077115913, 0.2309699292],
                    [-1.2684380046, 2.6097574011, -0.3413193965],
                    [-0.0041960863, -0.7034186147, 1.7076147010]])
    return linear_to_srgb(lms @ m1i.T)


def hexrgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def ramp(anchors, n=16):
    labs = to_oklab(np.array([hexrgb(a) for a in anchors], dtype=np.float64))
    # Anker gleichmäßig über die Stufen verteilen
    pos = np.linspace(0, n - 1, len(anchors))
    out = []
    for i in range(n):
        j = min(np.searchsorted(pos, i, side="right") - 1, len(anchors) - 2)
        t = (i - pos[j]) / (pos[j + 1] - pos[j])
        out.append(labs[j] * (1 - t) + labs[j + 1] * t)
    return np.clip(np.round(from_oklab(np.array(out))), 0, 255).astype(np.uint8)


def build_palette():
    pal = np.concatenate([ramp(a) for _, a in RAMPS]).astype(np.uint8)
    assert pal.shape == (256, 3)
    pal[TRANSPARENT] = (255, 0, 255)       # Marker, wird nie gezeichnet
    return pal


PALETTE = build_palette()
PAL_LAB = to_oklab(PALETTE.astype(np.float64))
USABLE = np.ones(256, bool)
USABLE[TRANSPARENT] = False
# doppelte Farben nur einmal anbieten (die erste gewinnt)
_seen = {}
for _i, _c in enumerate(map(tuple, PALETTE)):
    if _c in _seen and USABLE[_i]:
        USABLE[_i] = False
    _seen.setdefault(_c, _i)


def nearest_index(rgb, allowed=None):
    """rgb: (..., 3) sRGB 0..255 -> Palettenindex (..., ) nach OKLab-Abstand."""
    rgb = np.asarray(rgb, dtype=np.float64)
    shp = rgb.shape[:-1]
    lab = to_oklab(rgb.reshape(-1, 3))
    mask = USABLE if allowed is None else (USABLE & allowed)
    idx = np.nonzero(mask)[0]
    out = np.empty(len(lab), dtype=np.uint8)
    for s in range(0, len(lab), 8192):
        d = ((lab[s:s + 8192, None, :] - PAL_LAB[None, idx, :]) ** 2).sum(-1)
        out[s:s + 8192] = idx[d.argmin(1)]
    return out.reshape(shp)


def ramp_mask(names):
    m = np.zeros(256, bool)
    for r, (n, _) in enumerate(RAMPS):
        if n in names:
            m[r * 16:(r + 1) * 16] = True
    return m


def quantize(img_rgb, allowed=None):
    """PIL-Bild oder Array (H, W, 3) -> Indexbild (H, W) uint8."""
    a = np.asarray(img_rgb.convert("RGB") if hasattr(img_rgb, "convert") else img_rgb)
    return nearest_index(a[..., :3], allowed)


def build_colormap():
    cm = np.zeros((LEVELS, 256), dtype=np.uint8)
    night = np.array(NIGHT, dtype=np.float64)
    for k in range(LEVELS):
        f = 1.0 - k / LEVELS
        dark = night + (PALETTE.astype(np.float64) - night) * f
        cm[k] = nearest_index(dark)
    cm[:, TRANSPARENT] = TRANSPARENT
    return cm


def index_to_rgb(idx):
    return PALETTE[np.asarray(idx)]


def save_index_png(idx, path):
    """Indexbild als 8-Bit-Graustufen-PNG (Wert = Palettenindex), wie es Godot lädt."""
    Image.fromarray(np.asarray(idx, dtype=np.uint8), "L").save(path)


GOLD = (215, 186, 69)   # Tönung beim Aufheben eines Gegenstands (Zeilen 1–4: 12,5 … 50 %)


def palette_rows():
    # gleiche Rechnung wie shaders/flash.gdshader: floor(c·(1−f) + Gold·f + 0,5), f in Achteln (exakt)
    rows = [PALETTE.astype(np.float64)]
    for k in range(1, 5):
        f = 0.125 * k
        rows.append(np.floor(PALETTE * (1 - f) + np.array(GOLD) * f + 0.5))
    out = np.clip(np.stack(rows), 0, 255).astype(np.uint8)
    out[:, TRANSPARENT] = PALETTE[TRANSPARENT]
    return out


def main():
    ASSETS.mkdir(exist_ok=True)
    demo = ENTRY / "demo"
    Image.fromarray(palette_rows(), "RGB").save(ASSETS / "palette.png")
    cm = build_colormap()
    save_index_png(cm, ASSETS / "colormap.png")
    if demo.exists():
        Image.fromarray(palette_rows(), "RGB").save(demo / "palette.png")
        save_index_png(cm, demo / "colormap.png")
    # Vorschau: Palette 16x16 (Zeile = Rampe) und Farbtabelle als Farbbild
    prev = Image.fromarray(PALETTE.reshape(16, 16, 3), "RGB").resize((256, 256), Image.NEAREST)
    prev.save(ASSETS / "palette_preview.png")
    Image.fromarray(PALETTE[cm], "RGB").resize((512, 128), Image.NEAREST).save(ASSETS / "colormap_preview.png")
    info = {"ramps": [{"name": n, "first": i * 16, "last": i * 16 + 15} for i, (n, _) in enumerate(RAMPS)],
            "transparent": TRANSPARENT, "night": NIGHT, "levels": LEVELS,
            "unique_colors": int(len({tuple(c) for c in PALETTE[USABLE]}))}
    (ASSETS / "palette.json").write_text(json.dumps(info, indent=1, ensure_ascii=False))
    print("Palette:", info["unique_colors"], "verschiedene Farben; Farbtabelle", cm.shape)


if __name__ == "__main__":
    main()
