"""Die gemeinsame CGRAM (256 Einträge, 15 Bit) des Eintrags mode7.

Aufteilung wie auf der Konsole, wenn oben Mode 1 und unten Mode 7 läuft (beide lesen dieselbe CGRAM):
    0          Hintergrundfarbe (wird je Zeile per HDMA zum Himmelsverlauf umgeschrieben)
    1..15      BG3-Paletten 0..3 des Textfensters (2bpp, je 3 Farben; 0/4/8/12 durchsichtig)
    16..63     BG1/BG2-Paletten 1..3 des Horizonts (4bpp, je 15 Farben; 16/32/48 durchsichtig)
    64..127    Farben der Mode-7-Ebene (8bpp; die Ebene darf nur diese 64 Einträge benutzen)
    128..255   OBJ-Paletten 0..7 (Sprites, je 15 Farben; 128+16p durchsichtig)
Ein Bauskript holt sich Indizes über die Namen; write_cgram() schreibt demo/art/cgram.png und
demo/data/cgram.json (Namen, Indizes, Grundfarben, Animationen für main.gd).
"""
import json
import pathlib

from PIL import Image

STYLE = pathlib.Path(__file__).resolve().parent.parent


def c5(hexstr):
    """#rrggbb -> (r5, g5, b5)"""
    h = hexstr.lstrip("#")
    return tuple(round(int(h[i:i + 2], 16) * 31 / 255) for i in (0, 2, 4))


def rgb8(c):
    return tuple(round(v * 255 / 31) for v in c)


# ---------------------------------------------------------------------------------------------
# Mode-7-Ebene: 64..127
# ---------------------------------------------------------------------------------------------
PLANE = [
    # Wasser
    ("w_shadow", "#121732"), ("w_deep", "#1a2244"), ("w_base", "#212b52"), ("w_mid", "#29355f"),
    ("w_light", "#364678"), ("w_hi", "#4f6092"), ("w_shallow", "#26405f"), ("w_shallow2", "#2f4f70"),
    ("foam1", "#6f7ca6"), ("foam2", "#a6b0d0"), ("foam3", "#dde2f2"),
    # Glitzern (Palettenanimation)
    ("glint0", "#29355f"), ("glint1", "#29355f"), ("glint2", "#29355f"), ("glint3", "#29355f"),
    # Kai: Pflaster und Kante
    ("p_joint", "#33303e"), ("p_dark", "#47424f"), ("p_base", "#57515e"), ("p_light", "#69626e"),
    ("p_hi", "#7d7682"), ("k_shadow", "#24202e"), ("k_top", "#857e8c"), ("k_hi", "#a19aa6"),
    # Steg: Holz
    ("j_gap", "#21171a"), ("j_dark", "#3e2c26"), ("j_base", "#523a2e"), ("j_light", "#664a38"),
    ("j_hi", "#7c5c44"), ("j_pile", "#2f2420"), ("j_cut", "#6e5848"),
    # Fels
    ("r_dark", "#28243a"), ("r_base", "#393348"), ("r_mid", "#4a4258"), ("r_light", "#5e5468"),
    ("r_hi", "#776a7c"),
    # Gras
    ("g_dark", "#1f2c28"), ("g_base", "#2a3a2e"), ("g_mid", "#354832"), ("g_light", "#445a3a"),
    ("g_hi", "#566c44"),
    # Mauer am Kai-Rand zum Gras
    ("wall_top", "#6e6874"), ("wall_dark", "#3a3644"),
]

# Glitzerfolge: jeder der vier Einträge läuft dieselbe Folge mit Versatz (Bilder zu 1/10 s)
GLINT_SEQ = ["#29355f", "#29355f", "#3d4a80", "#7a6c9c", "#c78a92", "#f2b47e", "#c78a92", "#7a6c9c",
             "#3d4a80", "#29355f", "#29355f", "#29355f"]

ENTRIES = {}


def _assign(names, start, stop, skip_every=None):
    i = start
    for name, hx in names:
        while skip_every and (i % skip_every == 0):
            i += 1
        if i >= stop:
            raise SystemExit(f"CGRAM-Bereich {start}..{stop - 1} voll bei {name}")
        ENTRIES[name] = (i, hx)
        i += 1


_assign(PLANE, 64, 128)


def idx(name):
    return ENTRIES[name][0]


def add_block(names, start, stop, skip_every=None):
    _assign(names, start, stop, skip_every)


def add_palette(prefix, names, pal_base):
    """Eine 4bpp-Palette (15 Farben) ab pal_base (Eintrag pal_base selbst bleibt durchsichtig)."""
    if len(names) > 15:
        raise SystemExit(f"Palette {prefix}: {len(names)} > 15 Farben")
    for k, (name, hx) in enumerate(names):
        ENTRIES[f"{prefix}.{name}"] = (pal_base + 1 + k, hx)


def table():
    """256 Einträge als 5-Bit-Tupel (unbelegte = schwarz)."""
    tab = [(0, 0, 0)] * 256
    for name, (i, hx) in ENTRIES.items():
        tab[i] = c5(hx)
    return tab


def write_cgram(anims=None):
    tab = table()
    img = Image.new("RGB", (256, 1))
    img.putdata([rgb8(c) for c in tab])
    (STYLE / "demo/art").mkdir(parents=True, exist_ok=True)
    (STYLE / "demo/data").mkdir(parents=True, exist_ok=True)
    img.save(STYLE / "demo/art/cgram.png")
    data = {
        "names": {n: i for n, (i, _) in sorted(ENTRIES.items(), key=lambda kv: kv[1][0])},
        "base": [list(c) for c in tab],
        "glint_seq": [list(c5(h)) for h in GLINT_SEQ],
        "anims": anims or {},
    }
    (STYLE / "demo/data/cgram.json").write_text(json.dumps(data, indent=1))
    return tab


# ---------------------------------------------------------------------------------------------
# OBJ-Paletten 128..255 (je 15 Farben; Paletten 4..7 nehmen an der Farbmathematik teil)
# ---------------------------------------------------------------------------------------------
OBJ = {
    0: ("badger", [("outline", "#1b1420"), ("fur_d1", "#3a3342"), ("fur_d2", "#5a5262"), ("fur_l1", "#a59c9e"),
                   ("fur_l2", "#ddd4c6"), ("green1", "#253a2c"), ("green2", "#3c5834"), ("green3", "#5c7c44"),
                   ("red1", "#6e1c28"), ("red2", "#ac3238"), ("red3", "#dc5446"), ("brown1", "#553222"),
                   ("brown2", "#87522f"), ("tan1", "#a47a4c"), ("tan2", "#d6ae72")]),
    1: ("boat", [("outline", "#1a1420"), ("white1", "#8a86a0"), ("white2", "#bfbacb"), ("white3", "#e8e2e6"),
                 ("red1", "#6a1e2a"), ("red2", "#a8323a"), ("red3", "#d05048"), ("wood1", "#4a3428"),
                 ("wood2", "#6e4c36"), ("wood3", "#946a48"), ("dark1", "#2c2026"), ("dark2", "#3e2e2c"),
                 ("metal", "#6a6a7c"), ("rope", "#a08c66"), ("glass", "#d8a060")]),
    2: ("cottage", [("outline", "#1a1420"), ("stone1", "#4a4452"), ("stone2", "#686272"), ("stone3", "#8a8494"),
                    ("sdark1", "#36303e"), ("roof1", "#2a2a3a"), ("roof2", "#3e3e52"), ("roof3", "#575a70"),
                    ("wood1", "#3e2c26"), ("wood2", "#6a4a36"), ("white", "#cfc8cc"), ("red", "#9a3038"),
                    ("win0", "#e09848"), ("win1", "#ffe09a"), ("win2", "#a85a30")]),
    3: ("props", [("outline", "#1a1420"), ("wood1", "#3e2c26"), ("wood2", "#5e4232"), ("wood3", "#84603f"),
                  ("metal1", "#34343f"), ("metal2", "#5a5a6a"), ("stone", "#4a4452"), ("glass0", "#f0a848"),
                  ("glass1", "#fff0b0"), ("white1", "#9a98b0"), ("white2", "#e4e2ee"), ("red1", "#8a2430"),
                  ("red2", "#c84040"), ("light", "#ffd070"), ("grey", "#6c6880")]),
    5: ("smoke", [("s1", "#4e4660"), ("s2", "#736a84"), ("s3", "#9c94aa")]),
    6: ("glow", [("g1", "#c05838"), ("g2", "#f0a050"), ("g3", "#ffe0a0")]),
    7: ("shade", [("k", "#0a0812")]),
}
for _p, (_name, _cols) in OBJ.items():
    add_palette(f"obj.{_name}", _cols, 128 + 16 * _p)


def obj_idx(pal_name, color):
    return ENTRIES[f"obj.{pal_name}.{color}"][0]


# ---------------------------------------------------------------------------------------------
# Horizont (Mode 1 über der Horizontzeile): BG2 Wolken = Palette 1, BG1 Land = Paletten 2 und 3
# ---------------------------------------------------------------------------------------------
BG_PALS = {
    1: ("clouds", [("c0", "#1c1a44"), ("c1", "#28214f"), ("c2", "#372758"), ("c3", "#4b2d62"), ("c4", "#653669"),
                   ("c5", "#86426e"), ("c6", "#ab5270"), ("c7", "#d06c6a"), ("c8", "#ee9268"), ("c9", "#fbb978"),
                   ("star0", "#c0c0e8"), ("star1", "#7c7cb0")]),
    2: ("land", [("k0", "#140f22"), ("k1", "#1d152d"), ("k2", "#271c39"), ("k3", "#332446"), ("k4", "#452e55"),
                 ("rim1", "#68405f"), ("rim2", "#965466"), ("grass1", "#1b2229"), ("grass2", "#262f33"),
                 ("isl1", "#3a2a52"), ("isl2", "#4d3462"), ("isl3", "#6a426a")]),
    3: ("tower", [("k0", "#140f22"), ("k1", "#1d152d"), ("k2", "#271c39"), ("k3", "#332446"), ("rim1", "#68405f"),
                  ("white1", "#8a8098"), ("white2", "#c4bccc"), ("red1", "#5e1a2c"), ("red2", "#9c2c3c"),
                  ("dark", "#100c1a"), ("lamp0", "#7a5a40"), ("lamp1", "#c08a50"), ("win", "#d89050"),
                  ("grass2", "#262f33")]),
}
for _p, (_name, _cols) in BG_PALS.items():
    add_palette(f"bg.{_name}", _cols, 16 * _p)

# Textfenster (BG3, 2bpp): Palette 0..3 = CGRAM 1..15, je [Füllung, Hell, Dunkel]
WIN_PALS = [   # je [Füllung, Hell, Dunkel]; Hell und Dunkel gleich, die Füllung bildet Titelleiste und Verlauf
    [("fill", "#202452"), ("hi", "#f2e8cc"), ("lo", "#07060f")],
    [("fill", "#3c2f62"), ("hi", "#f2e8cc"), ("lo", "#07060f")],
    [("fill", "#1a1d46"), ("hi", "#f2e8cc"), ("lo", "#07060f")],
    [("fill", "#14163a"), ("hi", "#f2e8cc"), ("lo", "#07060f")],
]
for _p, _cols in enumerate(WIN_PALS):
    for _k, (_n, _hx) in enumerate(_cols):
        ENTRIES[f"win{_p}.{_n}"] = (4 * _p + 1 + _k, _hx)
ENTRIES["backdrop"] = (0, "#101236")

# Himmelsverlauf (Hintergrundfarbe je Zeile per HDMA): Stützstellen (Zeile, Farbe)
SKY = [(0, "#0e1034"), (24, "#1b1946"), (44, "#2f2258"), (58, "#4a2862"), (70, "#743468"), (79, "#a8466a"),
       (86, "#d86660"), (90, "#f08e5e"), (92, "#f8aa6a")]


def bg_idx(pal, color):
    return ENTRIES[f"bg.{pal}.{color}"][0]
