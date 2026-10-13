#!/usr/bin/env python3
"""Baut die Cartridge demo/cart/lornholm.p8 im Textformat der Fantasy-Konsole (__gfx__ + __map__).

1. Feste Bildteile (Häuschen, Felsnase mit Leuchtturm, Steg, Fässer, Kisten, Tau, Laternenpfahl, Kai) werden in
   Bildschirmkoordinaten aus den Textgrafiken in art.py zusammengesetzt (Ebene "static").
2. Die Ebene wird in 8x8-Felder zerlegt. Die Karte liegt 3 px höher als der Bildschirm (Feldzeile r deckt
   y = 8r-3 … 8r+4), damit die Kaioberkante (y 77) auf einer Feldgrenze liegt. Gleiche Felder werden
   zusammengelegt, leere Felder sind Sprite 0 (wird von map() nicht gezeichnet).
3. Sprite-Blatt 128x128 (256 Sprites): Zeilen 0-3 Akteure (Dachs 16x16, Boote, Möwe, Paket, Laterne),
   ab Sprite 64 die Kartenfelder. Grenze: 256 Sprites; das Skript bricht ab, wenn es nicht passt.
   Durchsichtig ist in allen Sprites und Feldern Rosa (14); main.gd zeichnet mit palt(0,false) palt(14,true),
   damit schwarze Konturen (0) vor dem Meer stehen bleiben (Konturregel in art.py).
4. Schreibt demo/cart/lornholm.p8, demo/cart/sprites.json (Lage der Akteure im Blatt),
   assets/spritesheet.png (×4), assets/static_layer.png (×4) und gibt die Feldstatistik aus.

    ../../.venv/bin/python scripts/build_cart.py
"""
import json, pathlib, sys
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import art
from p8pal import PAL

MAP_SY = -3          # Bildschirm-y der Feldzeile 0
MAP_ROWS = 12        # y -3 … 92 (die Textbox deckt ab y 91 alles ab)
QUAY_Y = 77          # Kaioberkante

# --- Ebene "static" in Bildschirmkoordinaten ------------------------------------------------------------
static = {}


def put(x, y, c):
    if 0 <= x < 128 and MAP_SY <= y < MAP_SY + MAP_ROWS * 8:
        static[(x, y)] = c


def stamp(rows, x0, y0, flip=False):
    for dy, r in enumerate(rows):
        if flip:
            r = r[::-1]
        for dx, ch in enumerate(r):
            if ch != ".":
                put(x0 + dx, y0 + dy, int(ch, 16))


def build_quay():
    """Kaioberfläche y 77..92: Platten 16x7 im Verband (Fugen dunkelgrau), Lichtkante oben."""
    for y in range(QUAY_Y, MAP_SY + MAP_ROWS * 8):
        for x in range(128):
            ry = y - QUAY_Y
            if ry == 0:
                c = 7                                   # Kante im Abendlicht
            elif ry == 1:
                c = 13
            else:
                band = (ry - 2) // 7                    # Plattenreihe
                yy = (ry - 2) % 7
                xo = (x + (8 if band % 2 else 0)) % 16
                if yy == 6:
                    c = 5                               # waagrechte Fuge
                elif xo == 0:
                    c = 5                               # senkrechte Fuge
                elif yy == 0 and xo in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14):
                    c = 6 if xo > 1 else 6
                else:
                    c = 6
                # ein paar Steinflecken (fest, periodisch je Platte)
                if (xo, yy) in ((5, 2), (11, 4), (12, 4)) and c == 6:
                    c = 13
            put(x, y, c)


def build_cottage():
    # Wand y 56..76, x 0..23 (links aus dem Bild), Bruchstein: Grund lavendel, Fugen dunkelgrau
    for y in range(56, 77):
        for x in range(0, 24):
            ry = y - 56
            c = 13
            row = ry // 4
            if ry % 4 == 3:
                c = 5
            elif (x + (3 if row % 2 else 0)) % 6 == 5:
                c = 5
            elif (x + row * 2) % 11 == 0 and ry % 4 == 0:
                c = 6
            put(x, y, c)
        put(24, y, 0)                       # rechte Hauskante (vor dem Meer: schwarz)
    for x in range(0, 24):
        put(x, 56, 5)                       # Traufschatten auf der Wand
    # Dach y 40..55: Ziegelreihen, Firstlinie, rechte Kante schräg
    for y in range(40, 56):
        ry = y - 40
        right = 25 + ry // 3                # Dach steht nach rechts über (Ortgang)
        for x in range(0, right + 1):
            if y == 40 or x == right:
                c = 0                       # Dachkontur (rechts vor dem Meer: schwarz)
            else:
                tr = (ry - 1) // 3
                yy = (ry - 1) % 3
                if yy == 2:
                    c = 2
                elif (x + (2 if tr % 2 else 0)) % 4 == 0:
                    c = 2
                else:
                    c = 9 if ry == 1 else 4
            put(x, y, c)
    for x in range(0, 31):
        put(x, 55, 0)                       # Traufkante
    stamp(art.CHIMNEY, 17, 33)
    stamp(art.WINDOW, 3, 60)
    stamp(art.DOOR, 13, 60)


def build_headland():
    """Felsnase x 92..127, y 40..57: Grasdecke auf dem Plateau, Fels in drei Flächen (Lichtkante lavendel,
    Körper dunkelgrau, Schattenseite dunkelblau), unten eine dunkle Wasserkante."""
    top, bottom = 40, 57
    for y in range(top, bottom + 1):
        r = y - top
        xl = 112 - (r * 20) // (bottom - top)          # linke Hangkante
        for x in range(xl, 128):
            dx = x - xl
            if r <= 2 and x >= 110:
                c = 11 if (r == 0 or (x + r) % 7 == 0) else 3
            elif r == 3 and x >= 110:
                c = 3 if x % 3 else 1
            elif dx == 0:
                c = 1
            elif dx <= 2:
                c = 13                                  # Lichtkante zum Abendhimmel
            elif dx == 3 and r % 3 == 0:
                c = 6
            else:
                # große Felsflächen: eine Kluft schräg nach rechts unten, rechts Schatten
                k = x - (xl + 9 + r // 2)
                if k == 0 or (x - 118 + r // 3) == 0 and r > 6:
                    c = 1
                elif x > 121 - r // 4:
                    c = 1 if (x + y) % 2 else 5
                else:
                    c = 5
            if y == bottom:
                c = 1
            put(x, y, c)
    stamp(art.LIGHTHOUSE, 113, 11)


def build_jetty():
    """Steg im Mittelgrund (Seitenansicht): Planke y 63..66 auf kurzen Pfählen, die an der Wasserlinie (y 69)
    enden; dort kleine Wellenringe. Am linken Ende führt ein Plankengang (von vorn gesehen, nach hinten
    schmaler) vom Kai zum Steg. Rechts am Stegende liegt Boot B, links Boot A (main.gd). Konturen schwarz,
    weil alles vor dem Meer steht."""
    x0, x1, y = 52, 70, 64
    water = 69
    for px in range(x0 + 1, x1, 7):
        for yy in range(y + 3, water + 1):
            put(px, yy, 4)
            put(px + 1, yy, 2)
        put(px - 1, water + 1, 13)          # Wellenring am Pfahl
        put(px + 2, water + 1, 13)
        put(px, water + 1, 5)
        put(px + 1, water + 1, 5)
    for x in range(x0, x1 + 1):
        put(x, y - 1, 0)
        put(x, y, 9)                        # Plankenkante im Abendlicht
        put(x, y + 1, 2 if x % 5 == 0 else 4)
        put(x, y + 2, 0)
    for yy in (y, y + 1):
        put(x0, yy, 0)
        put(x1, yy, 0)
    # Plankengang zum Kai: y 67..76, unten 7 px breit, oben 5 px; Bretter quer im Abendlicht, Fugen braun
    gx = x0
    for yy in range(y + 3, QUAY_Y):
        k = yy - (y + 3)                    # 0 oben … 9 unten
        inset = 1 if k < 5 else 0
        xa, xb = gx + inset, gx + 6 - inset
        put(xa, yy, 0)
        put(xb, yy, 0)
        for x in range(xa + 1, xb):
            put(x, yy, 4 if k % 2 == 1 else 9)


def build_props():
    # Fässer 8x10 und Kisten 9x9 stehen mit ihrer schwarzen Unterkante direkt auf der Kaikante (y 76);
    # die obere Kiste teilt sich die Kontur mit den unteren (keine doppelte Linie, keine Lücke).
    stamp(art.BARREL, 25, 67)
    stamp(art.BARREL, 32, 67)
    stamp(art.CRATE, 102, 68)
    stamp(art.CRATE, 110, 68)
    stamp(art.CRATE, 106, 60)
    stamp(art.ROPE, 119, 72)
    stamp(art.BOLLARD, 45, 72)
    # Laternenpfahl x 96..99 (Pfahl 97..98), Arm nach links bis x 90, Haken bei x 93; die Laterne hängt als
    # Sprite daran (main.gd, y 52)
    stamp(art.POST, 90, 48)


build_cottage()
build_headland()
build_jetty()
build_props()
build_quay()

# --- Akteure ----------------------------------------------------------------------------------------------
sheet = [[0] * 128 for _ in range(128)]
used = [[False] * 128 for _ in range(128)]
actors = {}


def place(name, rows, sx, sy, w=None, h=None, key=14):
    """key: Farbe, die im Blatt für "durchsichtig" steht. Alle Sprites nutzen 14 (rosa) und werden mit
    palt(0,false) palt(14,true) gezeichnet, wie auf der Konsole üblich, damit Schwarz zeichnen kann."""
    w = w or max(len(r) for r in rows)
    h = h or len(rows)
    for dy in range(h):
        r = rows[dy] if dy < len(rows) else ""
        for dx in range(w):
            ch = r[dx] if dx < len(r) else "."
            sheet[sy + dy][sx + dx] = key if ch == "." else int(ch, 16)
            used[sy + dy][sx + dx] = True
    actors[name] = {"sx": sx, "sy": sy, "w": w, "h": h, "key": key}


# Dachs: Stand (Schalende a/b, eingeatmet a/b, Blinzeln) und Lauf (Schalende wechselt mit jedem Laufbild).
# 9 Posen à 16x16: 7 in Blattzeile 0-1 (x 16..127), 2 in Blattzeile 2-3 (x 80..111).
BADGER_POSES = {
    "stand_a": ("stand", 0, False), "stand_b": ("stand", 1, False),
    "breath_a": ("breath", 0, False), "breath_b": ("breath", 1, False),
    "blink": ("stand", 1, True),
    "contact": ("contact", 0, False), "pass": ("pass", 1, False),
    "contact2": ("contact2", 0, False), "pass2": ("pass2", 1, False),
}
slots = [(16 + k * 16, 0) for k in range(7)] + [(80, 16), (96, 16)]
for (name, (pose, scarf, blink)), (sx, sy) in zip(BADGER_POSES.items(), slots):
    place("badger_" + name, art.badger_frame(pose, scarf, blink), sx, sy, 16, 16)
place("boat_a", art.BOAT_A, 0, 16)
place("boat_b", art.BOAT_B, 24, 16)
place("gull_0", art.GULL[0], 48, 16)
place("gull_1", art.GULL[1], 56, 16)
place("parcel", art.PARCEL, 64, 16)
place("lantern", art.LANTERN, 72, 16)

# --- Felder -----------------------------------------------------------------------------------------------
tiles = {}           # Inhalt -> Sprite-Nummer
mapcells = [[0] * 128 for _ in range(32)]
next_sprite = 64
for r in range(MAP_ROWS):
    for c in range(16):
        px = tuple(static.get((c * 8 + x, MAP_SY + r * 8 + y), -1) for y in range(8) for x in range(8))
        if all(v < 0 for v in px):
            continue
        if px not in tiles:
            if next_sprite > 255:
                sys.exit("Sprite-Blatt voll: mehr als 192 verschiedene Kartenfelder")
            tiles[px] = next_sprite
            n = next_sprite
            for i, v in enumerate(px):
                sheet[(n // 16) * 8 + i // 8][(n % 16) * 8 + i % 8] = 14 if v < 0 else v
                used[(n // 16) * 8 + i // 8][(n % 16) * 8 + i % 8] = True
            next_sprite += 1
        mapcells[r][c] = tiles[px]

used_cells = sum(1 for r in mapcells for v in r if v)
# freie 8x8-Blöcke: kein einziges Pixel beschrieben (Lücken zwischen den Akteuren in Zeile 0-3 zählen mit)
empty_blocks = sum(1 for n in range(256)
                   if not any(used[(n // 16) * 8 + y][(n % 16) * 8 + x] for y in range(8) for x in range(8)))

# --- Ausgabe ----------------------------------------------------------------------------------------------
cart = ROOT / "demo" / "cart"
cart.mkdir(parents=True, exist_ok=True)
hexd = "0123456789abcdef"
lines = ["pico-8 cartridge // http://www.pico-8.com", "version 41", "__lua__",
         "-- hafen von lornholm (katalogeintrag pico8-fantasy)",
         "-- grafikdaten fuer die godot-demo; das spielprogramm steht in demo/scripts/main.gd",
         "__gfx__"]
lines += ["".join(hexd[v] for v in row) for row in sheet]
lines.append("__map__")
lines += ["".join(f"{v:02x}" for v in row) for row in mapcells]
(cart / "lornholm.p8").write_text("\n".join(lines) + "\n")
(cart / "sprites.json").write_text(json.dumps({"actors": actors, "map_sy": MAP_SY, "map_rows": MAP_ROWS,
                                               "badger_poses": list(BADGER_POSES)}, indent=1))

img = Image.new("RGB", (128, 128))
img.putdata([PAL[v] for row in sheet for v in row])
img.resize((512, 512), Image.NEAREST).save(ROOT / "assets" / "spritesheet.png")
lay = Image.new("RGBA", (128, MAP_ROWS * 8), (0, 0, 0, 0))
for (x, y), c in static.items():
    lay.putpixel((x, y - MAP_SY), PAL[c] + (255,))
lay.resize((512, MAP_ROWS * 32), Image.NEAREST).save(ROOT / "assets" / "static_layer.png")
print(f"Kartenfelder: {used_cells} belegt, {len(tiles)} verschieden (Sprites 64-{next_sprite - 1}); "
      f"Akteure: {len(actors)}; nach den Kartenfeldern frei: {256 - next_sprite} Sprites; "
      f"ganz leere 8x8-Blöcke im Blatt: {empty_blocks} von 256")
