"""Pixelgrafik des Eintrags als Text: ein Zeichen je Pixel, Hexziffer = Farbnummer der 16-Farben-Palette,
"." = durchsichtig. Im Sprite-Blatt steht für "durchsichtig" Rosa (14); gezeichnet wird mit
palt(0,false) palt(14,true), damit Schwarz (0) als Farbe nutzbar ist.

Konturregel: Alles, was vor dem Meer (Dunkelblau 1) steht, hat schwarze Konturen (0). Eine dunkelblaue Kontur
verschwindet dort, und das Ding scheint 1-2 px über dem Kai zu schweben. Dunkelblau bleibt für Konturen vor dem
Himmel und auf hellen Flächen (Leuchtturm, Schornstein, Fenster, Tür, Dachs).

0 schwarz  1 dunkelblau  2 dunkelviolett  3 dunkelgrün  4 braun  5 dunkelgrau  6 hellgrau  7 weiß
8 rot  9 orange  a gelb  b grün  c blau  d lavendel  e rosa  f pfirsich

Alles von Hand gesetzt; das KI-Bild assets/raw/bg.png diente nur als Lageplan (wo was steht, welche
Farben wohin), das KI-Blatt assets/raw/badger.png als Vorlage für Kopfform und Kostümfarben.
"""

# --- Häuschen (Bildschirm x 0..31, y 33..76) -------------------------------------------------------------
# Schornstein (x 20..25, y 33..40) und Dach/Wand werden in build_cart.py zusammengesetzt.
CHIMNEY = [
    "111111",
    "166661",
    ".1d51.",
    ".1d51.",
    ".1551.",
    ".1d51.",
    ".1d51.",
]

WINDOW = [          # 7x8, Glas gelb/orange, Sprossenkreuz dunkelblau
    "1111111",
    "1aa1aa1",
    "1aa1aa1",
    "1111111",
    "1a91a91",
    "1991991",
    "1111111",
    "6666666",
]

DOOR = [            # 8x17, Bretter braun, Fugen dunkelviolett, Klinke orange
    ".111111.",
    "11444411",
    "14424241",
    "14424241",
    "14424241",
    "14424241",
    "14424241",
    "14424241",
    "14424241",
    "14424291",
    "14424241",
    "14424241",
    "14424241",
    "14424241",
    "14424241",
    "14424241",
    "11111111",
]

# --- Leuchtturm (x 108..118, y 11..44) --------------------------------------------------------------------
LIGHTHOUSE = [
    "....111....",
    "...15551...",
    "..1555551..",
    ".111111111.",
    "...1aaa1...",
    "...1aaa1...",
    ".111111111.",
    ".1d1d1d1d1.",
    "..1777761..",
    "..1777761..",
    "..1717761..",
    "..1777761..",
    "..1777761..",
    "..1777761..",
    "..1888821..",
    "..1888821..",
    "..1888821..",
    "..1888821..",
    ".117777661.",
    ".177777761.",
    ".171777761.",
    ".177777761.",
    ".177777761.",
    ".177777761.",
    ".177777661.",
    ".177111661.",
    ".171555161.",
    ".171555161.",
    ".171555161.",
    ".111111111.",
]

# --- Felsnase (x 92..127, y 38..58) -----------------------------------------------------------------------
# 3 Gras dunkel, b Gras hell, d Fels im Abendlicht, 5 Fels, 1 Schatten
HEADLAND = [
    "......................3333bbbbbbbbbb",   # y 41  (Leuchtturm steht bei y <= 41 auf dem Plateau)
    "...................333333333b3333bbb",
    ".................1dd33333333333333bb",
    "...............1ddd55d33333333333333",
    "..............1dd5555555d33333333333",
    "............1dd5555155555d5533333333",
    "...........1d55555515555555555d33333",
    "..........1d555511155555515555555d33",
    ".........1d555511555555511555555555d",
    "........1d5555555555555115555115555d",
    ".......1d555555155555555555551155555",
    "......1d5555551155555555555555555555",
    ".....1d55555555555555511555555555555",
    "....1d555555555555555111555555511555",
    "...1d5555555555551155555555555511555",
    "..1d55555555555555555555555555555555",
    ".1111111111111111111111111111111111d",
]

# --- Steg (Seitenansicht, Mittelgrund) ----------------------------------------------------------------------
# wird in build_cart.py aus Planken und Pfählen gesetzt

BARREL = [          # 8x10 (etwa 0,8 m neben dem 14 px großen Dachs)
    ".000000.",
    "04999940",
    "05555550",
    "04944420",
    "04944420",
    "04944420",
    "04944420",
    "05555550",
    "04444420",
    ".000000.",
]

CRATE = [           # 9x9, Latten mit Fugen, Oberkante im Abendlicht
    "000000000",
    "099999940",
    "044444420",
    "022222220",
    "044444420",
    "044444420",
    "022222220",
    "044444420",
    "000000000",
]

ROPE = [            # 9x5
    "..00000..",
    ".0999990.",
    "094000490",
    "049999940",
    ".0000000.",
]

POST = [            # Laternenpfahl mit Arm, 10x29 (Bildschirm x 90..99, y 48..76); Laterne hängt am Haken
    "......0000",   # Kappe
    "0000000420",   # Arm oben, der Pfahl läuft durch
    "0444444420",
    "0000000420",
    "...0..0420",   # Haken (x 93)
] + ["......0420"] * 24

BOLLARD = [         # 5x5, Poller auf der Kaikante, Boot A ist daran festgemacht
    ".000.",
    "05660",
    "00500",
    ".050.",
    ".000.",
]

# --- Sprites (Akteure) ------------------------------------------------------------------------------------
LANTERN = [         # 5x8, Glas a/9 (wird beim Flackern über pal() umgefärbt)
    "..0..",
    ".000.",
    "05550",
    "0aaa0",
    "0aaa0",
    "0a9a0",
    "05550",
    ".000.",
]

PARCEL = [          # 7x6, liegt vor dem hellen Kai: Kontur dunkelblau
    ".11111.",
    "1ff4ff1",
    "1444441",
    "1ff4f91",
    "1ff4f91",
    "1111111",
]

GULL = [
    [               # Flügel oben
        "7.....7",
        ".7...7.",
        "..777..",
    ],
    [               # Flügel unten
        ".......",
        "..777..",
        ".7...7.",
    ],
]

BOAT_A = [          # 22x7, Ruderboot von der Seite: Bug rechts hochgezogen, Mast zeichnet main.gd
    "00..................00",
    "090................090",
    "04990000000000000099a0",
    ".044444444444444444400",
    ".04422222222222222440.",
    "..044444444444444440..",
    "...0000000000000000...",
]

BOAT_B = [          # 21x10, Fischkutter: Steuerhaus mit rotem Dach und einem Fenster (kein "Gesicht")
    "....00000000.........",
    "....08888880.........",
    ".....066aa0..........",
    "00...066aa0........00",
    "090..066660.......090",
    "0899999999999999999a0",
    ".0888888888888888880.",
    ".0444444444444444420.",
    "..02222222222222220..",
    "...000000000000000...",
]

# --- Dachs 16x16 (Blick nach rechts) ------------------------------------------------------------------------
# Oberkörper (Zeilen 0-12) für alle Bilder gleich; die Beine (Zeilen 13-15) je Pose. Im Durchgang und beim
# Einatmen hebt sich der Oberkörper um 1 px. Farben: 3 Mütze, a Knopf, 7 Fell weiß (Gesicht, Ohrrand, Ärmel
# des hellen Hemds), 5 Fell grau, 0 Augenstreif und Nase, 1 Kontur, 8 Schal, 3 Weste, f Paket, 4 Tasche und
# Schnur. Kopf wie im Figurenmotiv: weißes Ohr hinten unter der Mütze, grauer Hinterkopf, schräger schwarzer
# Streif mit hellem Auge, der unter dem Auge als 4-px-Band Richtung Nase läuft, weißes Kinn darunter,
# abgesetzte schwarze Nasenspitze (2 px). Ein Band bis zur Spitze las sich als Schnabel/Schnurrbart, eine ganz
# weiße Schnauze als Fuchs (Blindtest, siehe style.json).
BADGER_TOP = [
    ".....1111.......",
    "....133331......",
    "...13333b31.....",
    "..1444444a4331..",
    ".175500777711...",
    ".1550007077771..",
    ".15770000007771.",
    ".15777770000700.",
    "..155777777771..",
    "..1888888881....",
    ".1433837ff4f1...",
    "1443385444441...",
    "14433335ff4f1...",
]
BLINK = {(6, 5): "5", (7, 5): "5"}  # Auge (x 7, y 5) zu: 2 px dunkelgraues Lid statt hellem Augenpunkt
SCARF_TAIL = [                      # Schalende hinter dem Nacken, flattert im Wind (2 Stellungen)
    {(0, 9): "8", (1, 9): "8"},
    {(0, 8): "8", (1, 9): "8"},
]
BADGER_FRONT = [
    "....111111......",
    "...13333331.....",
    "..1333b33331....",
    "..1444a44441....",
    ".17007770071....",
    ".17067776071....",
    ".17007770071....",
    "..170077001.....",
    "..177707771.....",
    "..1888888881....",
    ".14388888831....",
    ".1473fff3741....",
    ".1453f4f3541....",
]
# Füße je Pose: (Spalte nah, Spalte fern, nah angehoben, fern angehoben, Körper 1 px höher). Ein Fuß ist 3 px
# breit (Ferse links), das Bein steht über den linken 2 px. Laufen: 2 px Vorschub je Bild, der Standfuß wandert
# im Sprite genau um diese 2 px zurück (7 -> 5 -> 3) und bleibt so in der Welt stehen.
BADGER_FEET = {
    "stand":    (7, 3, False, False, False),
    "breath":   (7, 3, False, False, True),     # Stand, Oberkörper 1 px gehoben (Füße bleiben)
    "contact":  (7, 3, False, False, False),
    "pass":     (5, 4, False, True, True),
    "contact2": (3, 7, False, False, False),
    "pass2":    (4, 5, True, False, True),
    "front":    (6, 3, False, False, False),
    "front_blink": (6, 3, False, False, False),
}
WALK = ["contact", "pass", "contact2", "pass2"]


def badger_frame(pose, scarf=None, blink=False):
    """scarf: Stellung des Schalendes (0/1, None = keins), blink: Auge geschlossen."""
    near, far, near_up, far_up, bob = BADGER_FEET[pose]
    body = BADGER_FRONT if pose.startswith("front") else BADGER_TOP
    if pose == "front_blink":
        body = [r.replace("6", "0") for r in BADGER_FRONT]
    body = [list(r) for r in body]
    if not pose.startswith("front"):
        extra = dict(SCARF_TAIL[scarf]) if scarf is not None else {}
        if blink:
            extra.update(BLINK)
        for (x, y), ch in extra.items():
            body[y][x] = ch
    rows = [list("." * 16) for _ in range(16)]
    off = 1 if bob else 0
    for y, r in enumerate(body):
        for x, ch in enumerate(r):
            if ch != "." and 0 <= y + 1 - off < 16:
                rows[y + 1 - off][x] = ch
    # Beine: fern zuerst (dunkelblau), nah darüber (dunkelgrau); Füße schwarz
    if pose.startswith("front"):
        for fx in (4, 8):
            rows[14][fx] = rows[14][fx + 1] = "5"
            rows[15][fx] = rows[15][fx + 1] = "0"
            rows[15][fx - 1] = "1" if fx == 4 else rows[15][fx - 1]
            rows[15][fx + 2] = "1" if fx == 8 else rows[15][fx + 2]
        return ["".join(r) for r in rows]
    for fx, up, leg in ((far, far_up, "1"), (near, near_up, "5")):
        foot_y = 14 if up else 15
        for y in range(14 - off if not up else 13 - off, foot_y):
            if 0 <= y < 16:
                rows[y][fx] = leg
                rows[y][fx + 1] = leg
        for x in range(fx, fx + 3):
            rows[foot_y][x] = "0"
    return ["".join(r) for r in rows]
