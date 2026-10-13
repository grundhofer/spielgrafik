"""Baut die Grafikdaten (demo/rom/rom.json) und Vorschaubilder (assets/) für den Eintrag atari2600.

    .venv/bin/python styles/atari2600/scripts/build_rom.py

Bild 160x192 wie beim NTSC-Videochip der zweiten Konsolengeneration:
  Zeilen 0-135   Szene (Playfield, Hintergrundfarbe, 2 Spieler, 2 Missiles, Ball)
  Zeilen 136-191 Textband (schwarz, Blockschrift; hier bricht der Eintrag bewusst die Hardwareregel, siehe style.json)

Playfield: 40 Blöcke je Zeile, je 4 Pixel breit, in Doppelzeilen aufgelöst. Farbe COLUPF je Zeile; auf einigen
Zeilen schreibt das Kernel COLUPF mitten in der Zeile um (links Häuschen/Wolken, rechts Felsnase/Turm).
Hintergrund: eine Farbe je Zeile (COLUBK) für Himmel, Horizont, Meer und Kai.
Bewegliche Objekte (Dachs, Boote, Fässer, Möwen, Laterne, Rauch, Sterne, Paket) setzt das Kernel-Skript
demo/scripts/main.gd je Zeile; ihre Bitmuster und Plätze stehen ebenfalls in rom.json.
"""
import json
import pathlib
import sys

from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import art  # noqa: E402
import font35  # noqa: E402
import tia_ref  # noqa: E402

ENTRY = pathlib.Path(__file__).resolve().parent.parent
SCENE_H = 136
TEXT_Y0 = 136
NO_SPLIT = 160

bk = [0x00] * SCENE_H
pfc = [0x00] * SCENE_H        # COLUPF ab Zeilenanfang
pfc_r = [0x00] * SCENE_H      # COLUPF nach dem Umschreiben in der Zeile
split = [NO_SPLIT] * SCENE_H  # Pixel, ab dem pfc_r gilt (Vielfaches von 3: ein CPU-Takt = 3 Pixel)
pf = [0] * SCENE_H            # 40 Bit, Bit i = Block i (Pixel 4i..4i+3)


def band(y0, seq, stop=SCENE_H):
    """seq: Liste (Anzahl Zeilen, Farbe) ab Zeile y0 in bk, höchstens bis vor Zeile stop."""
    y = y0
    for n, c in seq:
        for _ in range(n):
            if y < stop:
                bk[y] = c
            y += 1
    return y


# ------------------------------------------------------------------ Hintergrundfarbe je Zeile
# Himmel: Nacht oben, über Violett und Rosa zum Orange am Horizont
SKY = [
    (5, 0x00), (4, 0xA0), (6, 0x90), (6, 0x80), (6, 0x70), (6, 0x60), (5, 0x62),
    (4, 0x52), (4, 0x54), (3, 0x44), (3, 0x46), (3, 0x36), (3, 0x38), (2, 0x3A), (2, 0x2C), (2, 0x1C),
]
HORIZON = band(0, SKY)            # 64
SEA_END = 122
# Meer: Abendlicht spiegelt sich nahe am Horizont in einzelnen Zeilen, nach vorn dunkler
SEA = [
    (1, 0x62), (1, 0x3A), (2, 0x62), (1, 0x38), (2, 0x72), (1, 0x36), (3, 0x72), (1, 0x34),
    (4, 0x82), (1, 0x44), (6, 0x82), (8, 0x80), (10, 0x90), (100, 0xA0),
]
band(HORIZON, SEA, SEA_END)
QUAY_Y = 122
band(QUAY_Y, [(1, 0x0A), (3, 0x06), (4, 0x04), (6, 0x02)])
FEET_Y = 127


# ------------------------------------------------------------------ Playfield
def fill(y0, y1, c0, c1):
    for yy in range(y0, y1):
        for c in range(c0, c1 + 1):
            pf[yy] |= 1 << c


def clear(y0, y1, c0, c1):
    for yy in range(y0, y1):
        for c in range(c0, c1 + 1):
            pf[yy] &= ~(1 << c)


def color(y0, y1, c, right=None, at=NO_SPLIT):
    for yy in range(y0, y1):
        pfc[yy] = c
        pfc_r[yy] = c if right is None else right
        split[yy] = NO_SPLIT if right is None else at


def stamp(y0, c0, rows, h=2):
    """ASCII-Stempel: jede Textzeile = h Bildzeilen, '#' = Block."""
    for r, s in enumerate(rows):
        for k, ch in enumerate(s):
            if ch == "#":
                for yy in range(y0 + r * h, y0 + r * h + h):
                    pf[yy] |= 1 << (c0 + k)


# Leuchtturm (rechts, Turm in Spalten 34-35 = Pixel 136-143)
fill(6, 8, 34, 35)               # Dachkappe
fill(8, 10, 33, 36)              # Dach
LAMP_Y0, LAMP_Y1 = 10, 18        # Laternenraum (Farbe und Strahl setzt das Kernel)
fill(LAMP_Y0, LAMP_Y1, 34, 35)
fill(18, 20, 33, 36)             # Galerie
fill(20, 62, 34, 35)             # Turm
fill(56, 62, 33, 36)             # Sockel
RED_BAND = (34, 42)
# Felsnase: Silhouette mit gezackter Kante (Doppelzeilen ab Zeile 62), unten Brandung (Kernel)
HEADLAND_Y0 = 62
# linke Kante der Felsnase je Doppelzeile ab Zeile 62 (Spalte), rechts bis zum Bildrand
HEADLAND = [30, 29, 28, 28, 27, 26, 27, 26, 25, 26, 25, 24, 25, 24, 24, 23, 24, 23, 22, 23, 22, 21, 21]
for r, c0 in enumerate(HEADLAND):
    fill(HEADLAND_Y0 + 2 * r, HEADLAND_Y0 + 2 * r + 2, c0, 39)
HEADLAND_Y1 = HEADLAND_Y0 + 2 * len(HEADLAND)   # 108
SURF_Y = HEADLAND_Y1             # Brandung an der Felskante (Kernel)
# Wolken links vom Turm: hohe, vom Abendlicht angestrahlte Streifen
stamp(24, 3, [
    "......#######.......",
    "..##############....",
    "........#########...",
])
stamp(30, 15, [
    "...######",
    ".########",
])
# Niedrige dunkle Wolkenbänke vor dem Horizontlicht
stamp(50, 2, [
    ".......######.....",
    "...##############.",
    "#################.",
    "..##########......",
    "......####........",
])

# Häuschen (links, Giebel zur Kamera, Spalten 2-10 = Pixel 8-43)
fill(70, 80, 8, 8)               # Schornstein
stamp(74, 1, [
    ".....###....",
    ".....###....",
    "....#####...",
    "....#####...",
    "...#######..",
    "...#######..",
    "..#########.",
    "..#########.",
    ".###########",
])
COT_Y0 = 92
fill(COT_Y0, 122, 2, 10)         # Mauer
DOOR = (7, 8, 100)               # Spalten, ab Zeile
clear(DOOR[2], 122, DOOR[0], DOOR[1])
# Kaimauer vorn: Steine im Verband (Doppelzeilen, versetzt)
for r in range(3):
    yy = 130 + 2 * r
    off = 0 if r % 2 == 0 else 2
    for c in range(40):
        if (c + off) % 4 != 3:
            pf[yy] |= 1 << c
            pf[yy + 1] |= 1 << c

# ------------------------------------------------------------------ Playfield-Farben je Zeile
SPLIT_X = 102                    # Umschreiben von COLUPF bei Pixel 102 (zwischen Wolken und Turm)
ROCK_SPLIT = 54                  # bei Pixel 54 (zwischen Häuschen und Felsnase)
color(6, 10, 0x44)               # rotes Dach
color(10, 18, 0x1E)              # Lampe (Kernel)
color(18, 20, 0x04)              # Galerie
for yy in range(20, 62):         # Turm weiß, rotes Band; links davon Wolken in Abendfarben
    tower = 0x44 if RED_BAND[0] <= yy < RED_BAND[1] else (0x0E if yy < 48 else 0x0C)
    cloud = {24: 0x5A, 25: 0x5A, 26: 0x4A, 27: 0x4A, 28: 0x3C, 29: 0x3C, 30: 0x5A, 31: 0x5A,
             32: 0x4C, 33: 0x4C}.get(yy)
    if yy >= 50:
        cloud = 0x60 if yy < 56 else 0x50
    if cloud is None:
        color(yy, yy + 1, tower)
    else:
        color(yy, yy + 1, cloud, tower, SPLIT_X)
ROCK = {}
for yy in range(56, 112):        # Fels: oben dunkles Gras als Silhouette, darunter einfarbiges Gestein, unten nass
    ROCK[yy] = 0xC0 if yy < 70 else (0x02 if yy < 102 else 0x04)
for yy in range(HEADLAND_Y0, 70):  # Felsnase allein
    color(yy, yy + 1, ROCK[yy])
for yy in range(70, 74):
    color(yy, yy + 1, ROCK[yy])  # Schornstein dunkel wie der Fels
for yy in range(74, 92):         # Dach rostbraun, Fels dunkel
    color(yy, yy + 1, 0x22 if yy < 90 else 0x20, ROCK[yy], ROCK_SPLIT)
for yy in range(92, 122):        # Mauer in warmen Steinlagen, rechts der Fels
    wall = 0xF6 if (yy // 2) % 2 == 0 else 0xF8
    if yy < HEADLAND_Y1:
        color(yy, yy + 1, wall, ROCK[yy], ROCK_SPLIT)
    else:
        color(yy, yy + 1, wall)
for r in range(3):
    color(130 + 2 * r, 132 + 2 * r, 0x06 if r != 1 else 0x04)

# ------------------------------------------------------------------ Objekte (Plätze für das Kernel)
LAYOUT = {
    "feet_y": FEET_Y,
    "badger_h": 22,
    "badger_stop_x": 66,
    "window": {"x": 16, "y0": 99, "y1": 106, "w": 4, "color": 0x1C},
    "lantern": {"x": 94, "y0": 97, "y1": 103, "w": 4, "post_x": 95, "post_y1": 128},
    "parcel": {"x": 82, "y0": 123, "y1": 128, "w": 4, "color": 0x2A},
    "barrels": {"x": 108, "y_bottom": 127, "nusiz": 5},
    "boats": {"x": 50, "water_y": 96, "nusiz": 2, "mast_dx": 3, "mast_h": 14},
    "smoke": {"x": 33, "y_top": 30, "y_bottom": 69},
    # Sterne: Ball, je Stern eine Zeile, dazwischen eine freie Zeile zum Umsetzen; zwei Sätze im Wechsel
    "stars": [[1, 22, 0], [3, 103, 0], [5, 61, 0], [7, 140, 0], [9, 38, 0], [21, 84, 0],
              [1, 131, 1], [3, 47, 1], [5, 152, 1], [7, 72, 1], [9, 112, 1], [21, 18, 1]],
    "surf_y": SURF_Y,
    "lamp_lines": [LAMP_Y0, LAMP_Y1],
    "sea": [HORIZON, SEA_END],
    "quay_y": QUAY_Y,
}

# Fässer: Spieler 1 doppelt breit (NUSIZ 5), beide Fässer in einem Bitmuster (je 3 Bit = 6 px, 4 px Lücke).
# Keine Kopien: sonst würde die Missile 1 (Laternenpfahl) in diesen Zeilen mitkopiert.
BARREL = [
    ("###..###", 0xF2), ("###..###", 0xF6), ("###..###", 0xF6), ("###..###", 0xF2), ("###..###", 0xF6),
    ("###..###", 0xF8), ("###..###", 0xF6), ("###..###", 0xF2), ("###..###", 0xF6), ("###..###", 0xF4),
]
# Fischerboot: Spieler 1, zwei Kopien (NUSIZ 2: 32 px Abstand); Mast = Missile 1 (kopiert mit)
BOAT = [
    ("....##..", 0x0C),   # Ruderhaus
    ("....##..", 0x0C),
    ("#...###.", 0x0E),   # Heck, Ruderhaus, Bug
    ("########", 0x0E),   # weiße Bordwand
    ("#######.", 0x44),   # roter Streifen
    (".#####..", 0x22),   # Rumpf
]


def sprite_json(rows):
    return [[int(bits.replace("#", "1").replace(".", "0"), 2), c] for bits, c in rows]


rom = {
    "scene_h": SCENE_H,
    "text_y0": TEXT_Y0,
    "palette": [f"{c:06x}" for c in tia_ref.NTSC],
    "bk": bk,
    "pfc": pfc,
    "pfc_r": pfc_r,
    "split": split,
    "pf": [[(p >> (8 * k)) & 0xFF for k in range(5)] for p in pf],
    "layout": LAYOUT,
    "sprites": {
        "badger_A": sprite_json(art.badger_side("A")),
        "badger_B": sprite_json(art.badger_side("B")),
        "badger_front": sprite_json(art.BADGER_FRONT),
        "badger_front_wind": sprite_json(art.BADGER_FRONT_WIND),
        "badger_front_breath": sprite_json(art.breath(art.BADGER_FRONT)),
        "badger_front_wind_breath": sprite_json(art.breath(art.BADGER_FRONT_WIND)),
        "barrel": sprite_json(BARREL),
        "boat": sprite_json(BOAT),
    },
    "font": font35.FONT_JSON,
}


def static_lines(badger="badger_front", bx=66):
    """Zeilentabelle für die Vorschau (ohne Animation)."""
    L = []
    for yy in range(192):
        r = {"colubk": 0, "colupf": 0, "colup0": 0, "colup1": 0, "pf": 0, "grp0": 0, "grp1": 0,
             "p0x": 0, "p1x": 0, "m0x": 0, "m1x": 0, "blx": 0, "enam0": 0, "enam1": 0, "enabl": 0,
             "nusiz0": 0, "nusiz1": 0, "refp0": 0, "refp1": 0, "ctrlpf": 0, "hmove": 1}
        if yy < SCENE_H:
            r.update(colubk=bk[yy], colupf=pfc[yy], colupf_r=pfc_r[yy], split=split[yy], pf=pf[yy])
        else:
            r.update(text=1, hmove=0)
        L.append(r)
    sp = rom["sprites"]
    top = FEET_Y - 21
    for i, (bits, c) in enumerate(sp[badger]):
        L[top + i].update(grp0=bits, colup0=c, p0x=bx)
    w = LAYOUT["window"]
    for yy in range(w["y0"], w["y1"]):
        L[yy].update(enam0=1, m0x=w["x"], colup0=w["color"], nusiz0=0x20)
    b = LAYOUT["boats"]
    bt = b["water_y"] - len(BOAT)
    for i, (bits, c) in enumerate(sp["boat"]):
        L[bt + i].update(grp1=bits, colup1=c, p1x=b["x"], nusiz1=b["nusiz"])
    for yy in range(bt - b["mast_h"], bt):
        L[yy].update(enam1=1, m1x=b["x"] + b["mast_dx"], colup1=0x22, nusiz1=b["nusiz"])
    la = LAYOUT["lantern"]
    for yy in range(la["y0"], la["y1"]):
        L[yy].update(enam1=1, m1x=la["x"], colup1=0x1E, nusiz1=0x20)
    br = LAYOUT["barrels"]
    bb = br["y_bottom"] - len(BARREL) + 1
    for i, (bits, c) in enumerate(sp["barrel"]):
        L[bb + i].update(grp1=bits, colup1=c, p1x=br["x"], nusiz1=br["nusiz"])
    for yy in range(la["y1"], la["post_y1"]):
        L[yy].update(enam1=1, m1x=la["post_x"], nusiz1=L[yy]["nusiz1"] & 7)
        if not L[yy]["grp1"]:
            L[yy]["colup1"] = 0xF2
    pa = LAYOUT["parcel"]
    for yy in range(pa["y0"], pa["y1"]):
        L[yy].update(enabl=1, blx=pa["x"], colupf=pa["color"], ctrlpf=0x20)
    for sy, sx, sset in LAYOUT["stars"]:
        if sset:
            continue
        L[sy].update(enabl=1, blx=sx, ctrlpf=0x00)
        if not L[sy]["pf"]:
            L[sy]["colupf"] = 0x0E
    return L


def sheet_assets(out):
    """Palette, Spielerbilder und Schrift als Vorschaubilder (2:1-Pixel wie auf dem Bildschirm)."""
    import numpy as np
    pal = np.zeros((8 * 6, 16 * 6, 3), np.uint8)
    for i, c in enumerate(tia_ref.PAL):
        hue, lum = i // 8, i % 8
        pal[lum * 6:(lum + 1) * 6, hue * 6:(hue + 1) * 6] = c
    Image.fromarray(pal).resize((16 * 48, 8 * 24), Image.NEAREST).save(out / "ntsc_palette.png")
    (out / "ntsc_palette_hex.txt").write_text(tia_ref.PALETTE_HEX + "\n")
    names = ["badger_A", "badger_B", "badger_front", "badger_front_wind", "badger_front_breath", "boat", "barrel"]
    tiles = []
    for n in names:
        rows = rom["sprites"][n]
        a = np.zeros((26, 20, 3), np.uint8)
        a[:] = tia_ref.rgb(0xA0)
        nus = 5 if n == "barrel" else 0
        sc = 2 if nus == 5 else 1
        top = 24 - len(rows)
        for i, (bits, c) in enumerate(rows):
            for b in range(8):
                if (bits >> (7 - b)) & 1:
                    a[top + i, 2 + b * sc:2 + (b + 1) * sc] = tia_ref.rgb(c)
        tiles.append(a)
    tia_ref.to_display(np.concatenate(tiles, axis=1), 4).save(out / "sprites.png")
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ0123456789.,!?:-'\"()/>*_"
    lines = [chars[:29], chars[29:], "Ärger über Böen? Straße, Brücke.", "Die Laterne flackert im Wind."]
    rows = font35.render_rows(lines, 2, x0=4)
    a = np.zeros((2 + 7 * len(lines) + 2, 160, 3), np.uint8)
    for yy, r in rows.items():
        for x, v in enumerate(r):
            if v and yy < a.shape[0]:
                a[yy, x] = tia_ref.rgb(0x0E)
    tia_ref.to_display(a, 3).save(out / "font.png")


def main():
    (ENTRY / "demo" / "rom").mkdir(parents=True, exist_ok=True)
    (ENTRY / "demo" / "rom" / "rom.json").write_text(json.dumps(rom, separators=(",", ":")))
    L = static_lines()
    lines = ["HAFEN VON LORNHOLM", "DIE LATERNE FLACKERT IM WIND.", "AM KAI WARTET EIN PAKET AUF DICH.",
             "  1 ZUM LEUCHTTURM GEHEN", "* 2 DAS PAKET ANSEHEN", "  3 MIT DEM DACHS SPRECHEN", "> NIMM PAKET_"]
    text = font35.render_rows(lines, TEXT_Y0 + 2)
    for yy in range(TEXT_Y0, 192):
        k = (yy - TEXT_Y0 - 2) // 7
        L[yy]["colupf"] = [0x1C, 0x0E, 0x0E, 0x9C, 0x3C, 0x9C, 0x0E, 0x0E][max(0, min(7, k))]
    arr = tia_ref.render_lines(L, text)
    out = ENTRY / "assets"
    out.mkdir(exist_ok=True)
    Image.fromarray(arr).save(out / "scene_preview_native.png")
    tia_ref.to_display(arr, 3).save(out / "scene_preview.png")
    sheet_assets(out)
    print("rom.json geschrieben; Vorschau:", out / "scene_preview.png")


if __name__ == "__main__":
    main()
