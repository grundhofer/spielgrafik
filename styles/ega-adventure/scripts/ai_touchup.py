#!/usr/bin/env python3
"""Handnacharbeit am automatisch umgewandelten KI-Bild (Variante ai_bg_flat_detail -> ai_bg_flat_touchup).

Die automatische Umwandlung (process_raw.py) trifft Himmel, Meer, Haus, Laterne, Fässer und Leuchtturm. Steg und
Boote zerfallen dagegen: Im KI-Bild hat jeder Pfosten eine schwarze Kontur, darunter liegen Schatten und
Spiegelungen, und auf 160 Doppelpixeln Breite gewinnt in vielen Zielpixeln Schwarz die Mehrheit. Hier wird dieser
Bereich (x 34–112, y 56–139) so nachgezeichnet, wie ihn ein Grafiker im Bildeditor der Zeit nachgezogen hätte:
Lage und Farben aus dem KI-Bild (Koordinaten über assets/raw/bg_flat.png mit Raster abgelesen), Formen vereinfacht.

Ablauf: Fremdfarben aus dem Himmel nehmen (Masten, Takelage), Wasser neu anlegen (Wellenstriche oberhalb von
y=102 bleiben), dann Steg, Boote, Pfosten, Taue und Spiegelungen zeichnen. Jede Zeichenoperation zählt in
`ops` (Aufwand der Nacharbeit). Danach erzeugt vectorize.py daraus wie gewohnt die Befehlsliste.

Zweite Runde (nach der Prüfung): Auch die beiden Fässer und der Laternenpfahl vorn rechts (x 122–157, y 82–167)
waren Klumpen (rechte Fasshälften schwarz, Deckel braun-schwarz gestreift, Böden bis in die letzte Zeile). Sie
werden nach dem KI-Bild neu gezeichnet; die Böden liegen 3 Zeilen über der Unterkante, weil der Ausschnitt die
Fässer im KI-Bild knapp über ihrem Fuß abschneidet. probe_badger.py liest POLE und BARRELS für die
Verdeckungsprüfung.
"""
import numpy as np
from PIL import Image, ImageDraw

from agipic import W, H, line_points

SKY = {1, 4, 5, 12, 14}
SEA = 1
STROKES = {7, 9, 11, 14, 15}
QUAY = 140                       # Kaikante dieses Bildes (ai_layout findet dieselbe Zeile)
PAVE, JOINT = 7, 8
POLE = (123, 82, 160)            # Laternenpfahl: linke Kontur x (Pfahl x 123–126, Fuß x 122–127), erste und letzte Zeile
BARRELS = ((129, 142, 130, 164), (144, 156, 137, 164))   # Fässer: x0, x1, oberste Deckelzeile, Bodenzeile


class Canvas:
    def __init__(self, idx):
        self.a = idx.copy()
        self.ops = 0

    def px(self, x, y, c):
        if 0 <= x < W and 0 <= y < H:
            self.a[y, x] = c

    def rect(self, x0, y0, x1, y1, c):
        self.a[y0:y1 + 1, x0:x1 + 1] = c
        self.ops += 1

    def line(self, pts, c):
        """Linienzug mit dem Linienalgorithmus der Demo (agipic.line_points)."""
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            for x, y in line_points(x0, y0, x1, y1):
                self.px(x, y, c)
        self.ops += 1

    def poly(self, pts, c):
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).polygon(pts, fill=255, outline=255)
        self.a[np.asarray(m) > 0] = c
        self.ops += 1


def post(cv, x, top, bottom):
    """Pfosten: 2 Doppelpixel Holz, rechts eine schwarze Schattenkante, oben hell angeschnitten."""
    cv.rect(x, top, x + 1, bottom, 6)
    cv.line([(x + 2, top + 1), (x + 2, bottom)], 0)
    cv.line([(x, top), (x + 1, top)], 0)


def barrel(cv, x0, x1, top, bottom):
    """Fass: flacher brauner Körper mit 1 Doppelpixel schwarzer Kontur, bauchig in Treppenstufen (mittlere Hälfte
    1 Doppelpixel breiter), ovaler Deckel aus 4 Zeilen, zwei Dauben als schwarze Linien, eine Schattenspalte innen
    an der rechten Kontur, zwei dunkelgraue Reifen à 2 Zeilen, geschlossener Boden."""
    h = bottom - top
    m0, m1 = top + int(np.ceil(0.3 * h)), top + int(0.75 * h)       # Zeilen der breiten Mitte
    b0 = top + 3                                                     # Körper beginnt unter dem Deckelrand
    cv.rect(x0 + 1, b0, x1 - 1, m0 - 1, 6)
    cv.rect(x0, m0, x1, m1, 6)
    cv.rect(x0 + 1, m1 + 1, x1 - 1, bottom - 1, 6)
    w = x1 - x0 + 1
    for sx in (x0 + round(0.3 * w), x0 + round(0.65 * w)):            # Dauben
        cv.line([(sx, b0), (sx, bottom - 1)], 0)
    cv.line([(x1 - 2, b0), (x1 - 2, m0 - 1), (x1 - 1, m0), (x1 - 1, m1), (x1 - 2, m1 + 1), (x1 - 2, bottom - 1)], 0)
    for hy in (top + 5, m1 + 1):                                     # Reifen (beide in den schmalen Zonen)
        cv.rect(x0 + 2, hy, x1 - 2, hy + 1, 8)
    cv.line([(x0 + 1, top + 1), (x0 + 1, m0 - 1), (x0, m0), (x0, m1), (x0 + 1, m1 + 1), (x0 + 1, bottom - 1)], 0)
    cv.line([(x1 - 1, top + 1), (x1 - 1, m0 - 1), (x1, m0), (x1, m1), (x1 - 1, m1 + 1), (x1 - 1, bottom - 1)], 0)
    cv.line([(x0 + 2, top), (x1 - 2, top)], 0)                       # Deckel: Oberkante, Fläche, vorderer Rand
    cv.rect(x0 + 2, top + 1, x1 - 2, top + 2, 6)
    cv.line([(x0 + 1, top + 3), (x1 - 1, top + 3)], 0)
    cv.line([(x0 + 2, bottom), (x1 - 2, bottom)], 0)                 # Boden


def lamp_pole(cv, x, top, bottom):
    """Laternenpfahl unter dem Laternenarm: 2 Doppelpixel Holz zwischen schwarzen Konturen, dunkelgraue Manschette,
    Fuß 6 Doppelpixel breit und 6 Zeilen hoch."""
    foot = bottom - 5
    cv.rect(x + 1, top, x + 2, foot - 1, 6)
    cv.line([(x, top), (x, foot - 1)], 0)
    cv.line([(x + 3, top), (x + 3, foot - 1)], 0)
    cv.rect(x + 1, 124, x + 2, 126, 8)
    cv.rect(x - 1, foot, x + 4, bottom, 8)
    cv.line([(x - 1, foot), (x + 4, foot), (x + 4, bottom), (x - 1, bottom), (x - 1, foot)], 0)


def touchup_bg_flat(idx):
    cv = Canvas(idx)
    a = cv.a
    # 1. Himmel im Bereich: alles, was keine Himmelsfarbe ist (Masten, Takelage), durch die Farbe links ersetzen
    for y in range(56, 82):
        for x in range(44, 113):
            if int(a[y, x]) not in SKY:
                xx = x - 1
                while xx > 0 and int(a[y, xx]) not in SKY:
                    xx -= 1
                a[y, x] = a[y, xx]
    cv.ops += 1
    # 2. Wasser neu: oberhalb von y=102 bleiben die Wellenstriche, darunter (Boote, Steg) ganz neu
    for y in range(82, 102):
        for x in range(44, 113):
            if int(a[y, x]) not in STROKES:
                a[y, x] = SEA
    a[102:140, 44:113] = SEA
    a[112:140, 26:44] = SEA
    cv.ops += 2
    # Wellenstriche: das KI-Bild hat sie hellcyan, die Farbgruppen haben sie zu Grau gemacht
    for y in range(82, 140):
        for x in range(W):
            if a[y, x] == 7 and a[y - 1, x] == SEA and a[y + 1, x] == SEA:
                a[y, x] = 11
    cv.ops += 1

    # 3. Steg hinter den Booten: Deck 4 Zeilen, darunter Schattenkante; der vordere linke Teil zeigt seine Unterseite
    cv.rect(34, 115, 108, 118, 6)
    cv.line([(34, 116), (108, 116)], 0)          # Fuge zwischen Planken
    cv.rect(34, 119, 108, 119, 0)
    cv.rect(34, 120, 52, 122, 0)

    # 4. linkes Boot: weißer Rumpf mit hellblauem Streifen, braunes Steuerhaus mit rotem Dach
    cv.line([(59, 62), (53, 109)], 0)            # Takelage
    cv.line([(59, 62), (70, 111)], 0)
    cv.line([(59, 61), (59, 103)], 6)            # Mast
    cv.px(59, 61, 0)
    cv.rect(58, 104, 66, 111, 6)                 # Steuerhaus
    cv.rect(57, 103, 67, 103, 4)                 # Dach
    for wx in (60, 62, 64):
        cv.rect(wx, 106, wx, 107, 0)             # Fenster
    cv.poly([(53, 110), (57, 112), (71, 112), (71, 118), (69, 121), (56, 124), (54, 121)], 15)
    cv.rect(54, 113, 71, 114, 9)                 # Streifen
    cv.line([(55, 118), (70, 118)], 7)           # Planke
    cv.line([(53, 110), (54, 121), (56, 124), (69, 121), (71, 118)], 0)   # Kontur Steven und Kiel

    # 5. rechtes Boot: roter Rumpf mit weißer Kante und dunkelgrünem Unterwasserschiff, Steuerhaus mit weißem Dach
    cv.line([(91, 71), (85, 110)], 0)
    cv.line([(91, 71), (101, 111)], 0)
    cv.line([(91, 70), (91, 104)], 6)
    cv.px(91, 70, 0)
    cv.rect(88, 106, 96, 112, 6)
    cv.rect(87, 105, 97, 105, 15)
    cv.rect(90, 107, 91, 109, 0)
    cv.rect(94, 107, 95, 109, 0)
    cv.poly([(84, 111), (88, 113), (102, 113), (102, 120), (100, 123), (87, 126), (85, 122)], 4)
    cv.line([(84, 111), (88, 113), (102, 113)], 15)   # weiße Kante
    cv.line([(85, 112), (88, 114), (102, 114)], 15)
    cv.line([(86, 118), (101, 118)], 12)              # helle Planke
    cv.line([(86, 125), (100, 122)], 2)               # Unterwasserschiff
    cv.line([(84, 111), (85, 122), (87, 126), (100, 123), (102, 120)], 0)

    # 6. Pfosten (vor Deck und Booten), Taue gelb durchhängend
    for x, top, bottom in ((38, 113, 127), (47, 110, 130), (50, 113, 128), (72, 113, 130), (79, 114, 130),
                           (82, 110, 117), (103, 112, 129), (107, 110, 129)):
        post(cv, x, top, bottom)
    cv.line([(49, 113), (51, 116), (53, 112)], 14)
    cv.line([(71, 114), (73, 116)], 14)
    cv.line([(74, 116), (76, 118), (79, 116)], 14)
    cv.line([(81, 116), (83, 114), (84, 112)], 14)
    cv.line([(102, 114), (103, 116)], 14)
    cv.line([(105, 115), (107, 113)], 14)

    # 7. Kisten, Tauwerk und Poller links vorn (in der Umwandlung zu einem braun-schwarzen Klumpen geworden)
    cv.rect(20, 114, 33, 131, 6)                                  # hintere Kiste
    cv.line([(20, 114), (33, 114), (33, 131), (20, 131), (20, 114)], 0)
    cv.line([(21, 117), (32, 117)], 0)                            # Kante Deckel
    cv.line([(27, 117), (27, 131)], 0)                            # Kante Vorder-/Seitenfläche
    cv.line([(21, 121), (26, 121)], 0)
    cv.line([(21, 125), (26, 125)], 0)
    cv.line([(30, 118), (30, 130)], 0)
    cv.rect(10, 124, 23, 141, 6)                                  # vordere Kiste
    cv.line([(10, 124), (23, 124), (23, 141), (10, 141), (10, 124)], 0)
    cv.line([(11, 127), (22, 127)], 0)
    cv.line([(19, 127), (19, 141)], 0)
    cv.line([(11, 131), (18, 131)], 0)
    cv.line([(11, 136), (18, 136)], 0)
    cv.line([(21, 128), (21, 140)], 0)
    coil = [(27, 131), (32, 131), (34, 133), (35, 136), (35, 140), (33, 141), (26, 141), (24, 140), (24, 136),
            (25, 133)]
    cv.poly(coil, 6)                                              # Tauring, drei Lagen
    cv.line(coil + [coil[0]], 0)
    cv.line([(26, 134), (33, 134)], 0)
    cv.line([(25, 137), (34, 137)], 0)
    cv.line([(28, 132), (31, 132)], 14)
    cv.line([(27, 135), (32, 135)], 14)
    cv.line([(26, 138), (33, 138)], 14)
    cv.rect(36, 132, 41, 133, 7)                                  # Poller
    cv.rect(37, 134, 40, 140, 8)
    cv.line([(38, 134), (38, 140)], 7)
    cv.line([(36, 131), (41, 131)], 0)

    # 8. Spiegelungen im Wasser
    for x0, x1, y, c in ((55, 59, 127, 9), (62, 67, 128, 9), (57, 63, 130, 11), (88, 92, 128, 9),
                         (95, 100, 127, 9), (90, 97, 130, 11), (74, 77, 133, 9), (44, 47, 134, 9),
                         (104, 109, 133, 11), (66, 70, 136, 9)):
        cv.line([(x0, y), (x1, y)], c)

    # 9. Laternenpfahl und Fässer vorn rechts: alte Klumpen (Schwarz, Braun, Dunkelgrau) über der Kaikante werden
    #    Wasser (Wellenstriche bleiben), darunter Pflaster mit den Fugenzeilen der Umgebung; dann neu zeichnen
    region = a[94:QUAY, 122:158]
    region[np.isin(region, (0, 6, 8))] = SEA
    cv.ops += 1
    cv.rect(122, QUAY, 157, H - 1, PAVE)
    for y in (144, 151, 157, 165):
        cv.line([(122, y), (157, y)], JOINT)
    lamp_pole(cv, *POLE)
    for b in BARRELS:
        barrel(cv, *b)

    # 10. Streupixel: weiße und hellcyane Reste der Wasserspiegelungen auf dem Pflaster werden Pflaster
    quay = a[QUAY:]
    quay[np.isin(quay, (11, 15))] = PAVE
    cv.ops += 1
    return cv.a, cv.ops
