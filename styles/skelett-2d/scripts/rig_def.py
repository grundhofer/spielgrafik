"""Rig-Definition für den Dachs (skelett-2d): Teile im Teileblatt, Platzierung, Knochen.

Alle Koordinaten in Pixeln des KI-Teileblatts assets/raw/parts.png (1536×1024). "Körperraum" = Koordinaten des
Rumpfteils im Blatt; die übrigen Teile werden mit (anchor_sheet -> anchor_body, rot) in den Körperraum gelegt.
Rig-Raum (Godot) = (Körperraum - ORIGIN) * S, Ursprung am Boden unter der Hüfte, y nach unten.
"""

S = 0.30                     # Texturmaßstab = Rig-Pixel je Blatt-Pixel (Figur ≈ 255 px hoch)
ORIGIN = (810.0, 895.0)      # Hüftmitte x, Sohle des nahen Fußes y (Körperraum)
# Sohlenzeile je Bein im Blatt (unterste deckende Zeile ohne Krallenspitzen)
SOLE_SHEET = {"n": ("leg_n", 945), "f": ("leg_f", 943)}
# Abrollpunkt (Fußballen auf der Sohle) je Bein im Blatt: um diesen Punkt dreht der Fuß am Ende der Standphase
ROLL_PIVOT = {"n": ("leg_n", (850, 945)), "f": ("leg_f", (1128, 943))}

# Teile: Komponenten des Blatts (Begrenzungsrahmen der Zusammenhangskomponente) und Platzierung.
# draw: Zeichenreihenfolge (klein = hinten)
PARTS = {
    "arm_f":   {"bbox": (1344, 274, 1497, 643), "anchor_sheet": (1405, 340), "anchor_body": (800, 362), "rot": -2.0, "draw": 0},
    "leg_f":   {"bbox": (944, 686, 1159, 945),  "anchor_sheet": (1040, 790), "anchor_body": (777, 726), "rot": 0.0, "draw": 1},
    "leg_n":   {"bbox": (670, 694, 875, 951),   "anchor_sheet": (766, 785),  "anchor_body": (842, 735), "rot": 0.0, "draw": 2},
    "body":    {"bbox": (580, 38, 1027, 691),   "anchor_sheet": (0, 0),      "anchor_body": (0, 0),     "rot": 0.0, "draw": 3},
    "scarf_b": {"bbox": (1350, 660, 1473, 969), "anchor_sheet": (1372, 668), "anchor_body": (676, 288), "rot": 22.0, "draw": 4},
    "arm_n":   {"bbox": (1054, 274, 1319, 617), "anchor_sheet": (1128, 340), "anchor_body": (722, 374), "rot": 0.0, "draw": 5},
    "scarf_f": {"bbox": (1238, 660, 1350, 916), "anchor_sheet": (1322, 668), "anchor_body": (925, 300), "rot": -10.0, "draw": 6},
}
# Die beiden Schalenden hängen oben zusammen (eine Komponente); Trennung bei x = 1350.
SCARF_SPLIT_X = 1350

# Knochen im Körperraum (Ruhelage), Eltern, Länge bis zum Kind (nur Anzeige) und Farbe für die Rig-Ansicht.
# Gelenke der Gliedmaßen werden aus dem Blatt über die Platzierung des jeweiligen Teils übertragen
# ("sheet": Koordinaten im Teil, "part": Teil).
BONES = [
    # name,      parent,    pos (body) or ("part", sheet xy)
    ("hip",      None,      (810, 640)),
    ("belly",    "hip",     (905, 600)),
    ("tail",     "hip",     (640, 636)),
    ("satchel",  "hip",     (660, 522)),
    ("thigh_f",  "hip",     ("leg_f", (1040, 790))),
    ("shin_f",   "thigh_f", ("leg_f", (1032, 838))),
    ("foot_f",   "shin_f",  ("leg_f", (1028, 884))),
    ("thigh_n",  "hip",     ("leg_n", (766, 785))),
    ("shin_n",   "thigh_n", ("leg_n", (752, 833))),
    ("foot_n",   "shin_n",  ("leg_n", (744, 880))),
    ("spine",    "hip",     (805, 470)),
    ("arm_f",    "spine",   ("arm_f", (1405, 340))),
    ("fore_f",   "arm_f",   ("arm_f", (1418, 446))),
    ("arm_n",    "spine",   ("arm_n", (1128, 340))),
    ("fore_n",   "arm_n",   ("arm_n", (1118, 440))),
    ("neck",     "spine",   (805, 325)),
    ("head",     "neck",    (812, 248)),
    ("scarf_b1", "neck",    ("scarf_b", (1372, 672))),
    ("scarf_b2", "scarf_b1", ("scarf_b", (1386, 760))),
    ("scarf_b3", "scarf_b2", ("scarf_b", (1402, 850))),
    ("scarf_f1", "neck",    ("scarf_f", (1322, 672))),
    ("scarf_f2", "scarf_f1", ("scarf_f", (1312, 745))),
    ("scarf_f3", "scarf_f2", ("scarf_f", (1300, 820))),
]
# Endpunkte für Knochen ohne Kind (Länge/Richtung der Anzeige)
TIPS = {
    "foot_f": ("leg_f", (1140, 928)), "foot_n": ("leg_n", (860, 930)),
    "fore_f": ("arm_f", (1412, 600)), "fore_n": ("arm_n", (1168, 575)),
    "head": (930, 140), "belly": (960, 640), "tail": (612, 676), "satchel": (630, 590),
    "scarf_b3": ("scarf_b", (1418, 950)), "scarf_f3": ("scarf_f", (1288, 905)),
}

# Ketten-Parameter (Blatt-Pixel): Breite des weichen Übergangs an den Gelenken
BLEND = {"knee": 26, "ankle": 14, "hip_top": 60, "elbow": 26, "shoulder": 34, "scarf": 34}

# Fernes Bein/Arm etwas dunkler (Tiefe), wie im Blatt bereits angelegt; zusätzlicher Faktor im Shader
FAR_TINT = 0.86
