"""Dachs-Kurier als Sprite der 8-Bit-Konsole, von Hand gepixelt (16x24, Blick nach rechts).

Gedrungene Figur wie in Konsolen-Rollenspielen (großer Kopf, breiter Rumpf, Beine 4 px), kleiner als die
Haustür. Aufbau aus 8x16-Sprites wie auf der Konsole, vier Ebenen (OAM-Reihenfolge = vorn nach hinten):
  Auflage (Zeilen 12-27, zwei Sprites) Sprite-Palette 2: b Braun, o Orange, c Creme (Ärmel, Paket, Tasche)
  Kopf    (Zeilen -4-11, zwei Sprites) Sprite-Palette 0: K Schwarz, W Weiß, G Dunkelgrün
  Körper  (Zeilen 12-27, zwei Sprites) Sprite-Palette 1: K Schwarz, R Rot, G Dunkelgrün
  Beine   (Zeilen 12-27, zwei Sprites) Sprite-Palette 3: K Schwarz (nahes Bein), g Dunkelgrau $00 (fernes Bein)
Die Grenze Kopf/Körper liegt bei Zeile 12 (Kinn/Schal), damit der rote Schal in der Körperpalette liegt.
Kopf, Körper und Auflage heben sich im Durchgang gemeinsam um 1 px (OAM-Y), die Beine bleiben am Boden
und sind je Pose gezeichnet; so bleibt der Standfuß stehen. Schalende und Tasche schwingen je Pose.
Kopf: Schnauze spitz nach vorn mit schwarzer Nasenspitze, weißer Streif von der Nase über die Stirn bis
unter die Mütze, schwarzer Streif schräg von der Nase durchs Auge zum Ohr, weiße Wange, schwarze Kehle,
Ohr mit weißem Rand hinter der Mütze. Lageplan für das Kostüm: assets/raw/badger.png (KI-Blatt).
"""

W, H = 16, 24
SPLIT = 12         # erste Zeile der Körperebene

HEAD = [  # Zeilen 0-11
    "..KKKKKK........",
    "KKGGGGGGKK......",
    "KGGGGGGGGGK.....",
    "KGGGGGGGGGGKKK..",
    "KKKKKKKKKKKKK...",
    "KWKKKKWWWWWWK...",
    "KWKKKKKKWWWWWK..",
    "KKWKKKKWKKKWWWK.",
    ".KWWKKKKKKKKKWWK",
    ".KKWWWWKKKKKKKKK",
    "..KKKKWWWWWKK...",
    "...KKKKKKKK.....",
]
BLINK = {7: "KKWKKKKKKKKWWWK."}   # Auge zu (Glanzpunkt weg)

BODY = [  # Zeilen 12-19; Tasche (b) hinten an der Hüfte, Paket (o, Schnur b) vorn unter dem Arm
    "...KRRRRRRRK....",
    "..KRRRRRRRRRK...",
    ".KGGGGcccGGGK...",
    ".KGbGcccccGGK...",
    "KbbKGGKoobooK...",
    "KbbbGGKbbbbbK...",
    "KbbKGGKoobooK...",
    ".KKKKKKKKKKKK...",
]
BODY_DROP = BODY[:4] + [  # Tasche 1 px tiefer (bleibt in Welthöhe, während der Körper steigt)
    ".KGbGGKoobooK...",
    "KbbKGGKbbbbbK...",
    "KbbbGGKoobooK...",
    "KbbKKKKKKKKKK...",
]
# Schalende hinter dem Nacken (Spalte 0-1), drei Stellungen; Zeile -> Zeichen ab Spalte 0
TAIL = {
    "up":   {12: ".R", 13: "RR", 14: "R."},
    "mid":  {13: ".R", 14: "RR", 15: "R."},
    "down": {14: ".R", 15: "RR"},
}

# Beine (Zeilen 19-23), von Hand: stämmige 3-px-Stümpfe mit 4-px-Fuß (Zehen nach vorn). Schrittweite 8 px,
# Vorschub 4 px je Laufbild: Fuß vorn x 10-13, Durchgang (Standfuß) x 6-9, hinten x 2-5.
LEGS = {
    "stand": [
        "................",
        "...gggKKK.......",
        "...gggKKK.......",
        "...gggKKK.......",
        "...gggKKKK......",
    ],
    "contact_a": [        # nahes Bein vorn, fernes hinten
        "................",
        "..ggg.....KKK...",
        "..ggg.....KKK...",
        "..ggg.....KKK...",
        "..gggg....KKKK..",
    ],
    "pass_a": [           # nahes Bein steht (x 6-9), fernes schwingt angehoben vorbei (Ferse hinten)
        "....ggKKK.......",
        "....ggKKK.......",
        "....ggKKK.......",
        "...gggKKK.......",
        "......KKKK......",
    ],
    "contact_b": [        # fernes Bein vorn, nahes hinten
        "................",
        "..KKK.....ggg...",
        "..KKK.....ggg...",
        "..KKK.....ggg...",
        "..KKKK....gggg..",
    ],
    "pass_b": [           # fernes Bein steht (x 6-9), nahes schwingt angehoben vorbei
        "....KKggg.......",
        "....KKggg.......",
        "....KKggg.......",
        "...KKKggg.......",
        "......gggg......",
    ],
}

# bob: Kopf, Körper, Auflage 1 px höher; tail: Schalende; drop: Tasche hängt relativ zum Körper 1 px tiefer
POSES = {
    "stand":     dict(bob=0, tail="mid", drop=0),
    "contact_a": dict(bob=0, tail="up", drop=0),
    "pass_a":    dict(bob=1, tail="mid", drop=1),
    "contact_b": dict(bob=0, tail="down", drop=0),
    "pass_b":    dict(bob=1, tail="mid", drop=1),
}
WALK = ["contact_a", "pass_a", "contact_b", "pass_b"]
OVERLAY = "boc"     # Zeichen der Auflage (Palette 2)


def upper(pose, blink=False):
    """Kopf + Körper (Zeilen 0-19) als Zeichenzeilen ohne Anheben; Tasche je Pose verschoben."""
    p = POSES[pose]
    head = list(HEAD)
    if blink:
        for k, v in BLINK.items():
            head[k] = v
    g = [list(r) for r in head + (BODY_DROP if p["drop"] else BODY)]
    for y, s in TAIL[p["tail"]].items():
        for x, ch in enumerate(s):
            if ch != ".":
                g[y][x] = ch
    return ["".join(r) for r in g]


def legs(pose):
    """Zeilen 0-23, nur Beine (K nahes, g fernes Bein)."""
    return ["." * W] * 19 + LEGS[pose]


def figure(pose, blink=False):
    """Ganze Figur (24 Zeilen) wie auf dem Bildschirm, Anheben eingerechnet (Vorschau und Prüfung)."""
    bob = POSES[pose]["bob"]
    out = [list(r) for r in legs(pose)]
    for y, r in enumerate(upper(pose, blink)):
        for x, ch in enumerate(r):
            if ch != "." and 0 <= y - bob < H:
                out[y - bob][x] = ch
    return ["".join(r) for r in out]
