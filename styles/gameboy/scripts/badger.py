"""Dachs-Kurier als Handheld-Sprite: 16x24 Pixel im 16x32-Rahmen aus vier 8x16-Sprites (OBP0 = Töne 0, 2, 3).

Von Hand gepixelt (ASCII unten), zweite Fassung nach der Prüfung (die erste las sich als Ente oder Kind):
- Profil (Laufen): großer Kopf (11 Zeilen), spitze weiße Schnauze, die nach unten zur dunklen Nase zuläuft,
  breiter schwarzer Augenstreif vom Ohr über das Auge (weißes Lichtpixel) zur Nase, darüber ein schmaler weißer
  Stirnstreif bis unter den Mützenschirm, darunter die große weiße Wange; Ohr mit hellem Rand hinter der Mütze,
  grauer Hinterkopf. Arm und Hand dunkel (Fell), Paket mit Schnur vorn, Tasche hinten, Schalende flattert.
- Front (Stehen, Blinzeln, Atmen): die Figur dreht sich nach dem Laufen zur Kamera. Von vorn liest sich der Dachs
  am deutlichsten: zwei schwarze Streifen laufen von den Ohren über die Augen zur Nase, dazwischen der weiße
  Mittelstreif, außen weiße Wangen, Nase unten mittig.
Vorlage für Kostüm und Proportionen: shared/badger/master_sheet.png (Seiten- und Vorderansicht).

Aufbau wie bei klassischen Handheld-Figuren aus Teilen: ein fester Oberkörper (Zeilen 0-19) und Beine, die je
Laufbild aus der Fußstellung erzeugt werden. Der Oberkörper wippt um 1 px (Kontakt 0, Abfedern +1, Durchgang 0,
Hoch -1), die Füße stehen immer auf Rahmenzeile FOOT_ROW.
"""
import numpy as np

from pix import stamp

FOOT_ROW = 28          # unterste Fußzeile im 16x32-Rahmen
TOP = FOOT_ROW - 23    # Mützenoberkante (Rahmenzeile 5)

UPPER = """
...33333333.....
..3222222223....
.322222220223...
.33333333333....
303233333003....
3223333030003...
32203333330003..
322000333333003.
3220000003333333
.32000000000033.
..32000000033...
.332323232323...
3.33232323233...
3.3200032223....
..3200032223....
.33323332333333.
322322233303003.
322322222303003.
322300000303003.
.33333333333333.
"""
# Profil nach rechts. Zeile 0-3 Mütze mit Messingknopf und Schirm, 4 Ohr (heller Rand) und Mützenband, 4-10 Kopf:
# Stirnstreif (0) über dem Augenstreif (3, Auge in Zeile 5), Wange (0), Nase rechts in Zeile 8-9, grauer
# Hinterkopf (2); 11-12 Schal mit Strickmuster und Ende hinten, 13-14 Hemdärmel (0) über der Weste (2),
# 15-19 dunkler Arm und Hand am Paket (vorn, Schnur), Tasche hinten, heller Bauch.

FRONT = """
....33333333....
...3222222223...
..322222002223..
.33333333333333.
3033330000333303
3303033003303033
3003333003333003
3000333003330003
3000030330300003
.30000033000003.
..300000000003..
..333232323333..
.33232323232333.
3003222002223003
3003222003223003
3332222223222333
3333322222322303
303032222322233.
30003300003223..
.33333000033333.
"""
FRONT_LEGS = """
..3333....3333..
..3333....3333..
..3333....3333..
.33333....33333.
"""
# Front: Mütze mit Knopf, Ohren außen (heller Rand), Streifen mit Augen (Zeile 5), Nase Zeile 8, Schal mit
# hängendem Ende, Ärmel hell, Arme dunkel, Paket links unter dem Arm, Bauch hell, kurze dunkle Beine.

SCARF_TAIL = [  # Schalende hinten (Zeilen 11-13, Spalte 0) in zwei Flatterstellungen
    {(11, 0): -1, (12, 0): 3, (13, 0): 3},
    {(11, 0): 3, (12, 0): 3, (13, 0): -1},
]

EYE = (5, 7)                       # Profil: weißes Lichtpixel im Augenstreif; Blinzeln = Streif geschlossen
FRONT_EYES = [(5, 4), (5, 11)]


def upper(blink=False, scarf=0):
    a = stamp(UPPER)
    for (y, x), v in SCARF_TAIL[scarf].items():
        a[y, x] = v
    if blink:
        a[EYE] = 3
    return a


def leg(box, foot_x, lift, hip_x, hip_row, near):
    """Ein Bein vom Hüftpunkt zum Fuß: Bein 4 px breit, Fuß 5 px (Zehe vorn). Fernes Bein dunkel gefüllt."""
    foot_row = FOOT_ROW - lift
    rows = list(range(hip_row, foot_row))
    n = len(rows)
    for k, y in enumerate(rows):
        t = (k + 1) / (n + 1)
        x0 = int(round(hip_x + (foot_x - hip_x) * t))
        for dx in range(4):
            x = x0 + dx
            if 0 <= x < 16:
                box[y, x] = 3 if (near or dx in (0, 3)) else 2
    for dx in range(5):
        x = foot_x + dx
        if 0 <= x < 16:
            box[foot_row, x] = 3 if (near or dx in (0, 4)) else 2


def compose(near_foot, far_foot, bob=0, blink=False, scarf=0):
    """near_foot/far_foot = (x, Hebung). Oberkörper um bob verschoben (positiv = tiefer)."""
    box = np.full((32, 16), -1, np.int8)
    u = upper(blink, scarf)
    y0 = TOP + bob
    box[y0:y0 + u.shape[0], :u.shape[1]] = np.where(u >= 0, u, box[y0:y0 + u.shape[0], :u.shape[1]])
    hip_row = y0 + u.shape[0]                       # erste Beinzeile
    # hinteres (fernes) Bein zuerst, dann das nahe darüber
    leg(box, far_foot[0], far_foot[1], 4, hip_row, near=False)
    leg(box, near_foot[0], near_foot[1], 8, hip_row, near=True)
    return box


# Laufzyklus: 8 Bilder, 2 Schritte. Standfuß wandert je Bild 2 px nach hinten (Rahmen rückt 2 px vor).
STANCE = [10, 8, 6, 4]           # linke Fußkante: Kontakt, Abfedern, Durchgang, Hoch
SWING = [(2, 0), (3, 1), (6, 2), (9, 1)]
BOB = [0, 1, 0, -1]
STEP_PX = 2                      # Vorschub je Laufbild
STAND = {"near": (8, 0), "far": (2, 0)}


def walk_frames():
    out = []
    for k in range(8):
        p = k % 4
        stance = (STANCE[p], 0)
        swing = SWING[p]
        if k < 4:
            near, far = stance, swing
        else:
            near, far = swing, stance
        out.append(compose(near, far, BOB[p], scarf=(k // 2) % 2))
    return out


def front(bob=0, blink=False):
    """Vorderansicht im 16x32-Rahmen; Beine fest, Oberkörper um bob tiefer (Atmen)."""
    box = np.full((32, 16), -1, np.int8)
    legs = stamp(FRONT_LEGS)
    box[FOOT_ROW - 3:FOOT_ROW + 1] = legs
    u = stamp(FRONT)
    if blink:
        for p in FRONT_EYES:
            u[p] = 3
    y0 = TOP + bob
    box[y0:y0 + u.shape[0]] = np.where(u >= 0, u, box[y0:y0 + u.shape[0]])
    return box


def stand_frames():
    n, f = STAND["near"], STAND["far"]
    return {
        "stand": compose(n, f, 0),             # Profil, kurz nach dem Halt
        "front": front(),
        "front_blink": front(blink=True),
        "front_breathe": front(bob=1),
    }


def check_palette(box, allowed=(0, 2, 3)):
    bad = set(np.unique(box[box >= 0]).tolist()) - set(allowed)
    if bad:
        raise ValueError(f"Töne {bad} nicht in OBP0 {allowed}")
