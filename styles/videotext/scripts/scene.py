#!/usr/bin/env python3
"""Vorlage des Hafens als 80 × 57 Mosaikpunkte (Zeichenzeilen 1–19) mit 8 Videotext-Farben.

Gezeichnet mit PIL-Formen auf ein Palettenbild, Formen am Zellraster (2 × 3 Punkte) ausgerichtet. Grundlage
für Komposition und Farbaufteilung war das KI-Bild assets/raw/bg_a.png (Himmelsbänder Blau/Magenta/Rot/Gelb,
weißer Leuchtturm mit rotem Band rechts auf dunkler Felsnase, Häuschen links). Neben den Zielfarben liefert die
Vorlage Gewichte (wichtige Formen zählen mehr), den Wunsch nach getrennten Mosaiken je Zelle und die Aus-Phase
der blinkenden Punkte. Koordinaten: x 0–79, y 0–56; Zeichenzeile = 1 + y // 3, Spalte = x // 2.
"""
import numpy as np
from PIL import Image, ImageDraw

import ttxlib as T

W, H = 80, 57
K, R, G, Y, B, M, C, Wh = range(8)

# Lage der animierten Teile (auch für build_stream.py)
LAMP = (70, 9, 71, 11)          # Lampe: Zelle 35, Zeile 4
CHIMNEY_TOP = (9, 14)           # Rauchfuß direkt über der Schornsteinmündung (x, y); Mündung bei y = 15
LANTERN = (56, 36, 57, 38)      # Glas der Laterne: Zelle 28, Zeile 13
DOOR = (14, 39, 23, 56)         # offene Tür: Zellen 7–11, Zeilen 14–19
BADGER_Y = 42                   # Oberkante des Dachses (Zeile 15)
STARS = [(3, 7), (29, 12), (31, 6), (44, 12), (57, 8), (78, 13), (23, 14), (36, 10), (61, 15), (54, 14)]
FLASH_STARS = [(31, 6), (61, 15)]
GLINTS = []   # blinkende Lichtpunkte auf dem Wasser: verworfen, im engen Wasserband fanden die Flash-Codes keinen Platz
# Wasser: Abendlicht-Streifen (gelb) und Wellenkämme (cyan); je Zustand um dx verschoben
STREAKS = [(34, 45, 30, 0), (37, 42, 31, 1), (39, 44, 32, 3)]
CRESTS = [(51, 55, 31, 0), (38, 40, 37, 2)]
WATER_DX = [0, 1, 1, 0, -1, -1]          # Wellenversatz je Phase
N_WATER = 4
ROCK_CRACKS = [(64, 67, 31), (74, 77, 32), (61, 64, 34), (70, 74, 35), (65, 69, 37), (76, 79, 38)]
N_SKY = 12


# Bahn eines Rauchwölkchens je Alter (x0, y0, x1, y1): steigt vom Schornstein nach rechts oben und wird größer
SMOKE_PATH = [(9, 13, 10, 13), (10, 12, 11, 13), (10, 11, 12, 12), (11, 10, 13, 12), (12, 10, 14, 11),
              (13, 9, 15, 11), (14, 8, 17, 10), (15, 8, 18, 10), (16, 7, 19, 9), (18, 7, 21, 9),
              (19, 6, 22, 8), (21, 6, 24, 7)]


def smoke_puffs(state):
    """Rauch als Kette, vom Wind nach rechts oben gedrückt: ein fester Rauchfuß direkt auf der Mündung und alle
    4 Zustände ein neues Wölkchen, das der Bahn SMOKE_PATH folgt (1 Punkt nach rechts je Zustand, Lebensdauer 12,
    also immer drei Wölkchen hintereinander). Der Schornstein endet mit dem roten Topf an der Zellenzeile 6
    (y 15–17), der Rauch liegt darüber in den Zeilen 3–5: so braucht keine Zelle drei Farben.
    Farbe nach Zellenzeile: weiß in Zeile 4–5 (y ≥ 9), cyan in Zeile 3 (dünn, oben)."""
    out = [(CHIMNEY_TOP[0], CHIMNEY_TOP[1], CHIMNEY_TOP[0] + 1, CHIMNEY_TOP[1], Wh)]
    for spawn in (0, 4, 8):
        x0, y0, x1, y1 = SMOKE_PATH[(state - spawn) % N_SKY]
        if y1 >= 9:
            out.append((x0, max(y0, 9), x1, y1, Wh))
        if y0 <= 8:
            out.append((x0, y0, x1, min(y1, 8), C))
    return out


# Leuchtfeuer dreht in 12 Zuständen: links lang -> kürzer -> zum Betrachter (Aufblenden) -> nach rechts aus dem
# Bild bzw. hinter den Turm (nichts) -> von hinten wieder links. Rechts vom Turm sind nur 3 Zellen bis zum Rand;
# nach Steuerzeichen für Hintergrund, Farbe und Steady bliebe dort keine Zelle für den Strahl.
BEAM = ["L40", "L44", "L52", "L60", "F", "", "", "", "L64", "L56", "L48", "L42"]


class Layer:
    def __init__(self, fill):
        self.im = Image.new("L", (W, H), fill)
        self.d = ImageDraw.Draw(self.im)

    def rect(self, x0, y0, x1, y1, c):          # einschließlich x1, y1
        self.d.rectangle([x0, y0, x1, y1], fill=c)

    def poly(self, pts, c):
        self.d.polygon(pts, fill=c)

    def arr(self):
        a = np.asarray(self.im).astype(int)
        return np.where(a == 255, -1, a)


def draw(cobbles=True, water=0, sky=0):
    d = Layer(B)
    # ---------------- Himmel: Bänder je Zeichenzeile, Wolkenstreifen an den Übergängen
    d.rect(0, 0, 79, 17, B)
    d.rect(0, 18, 79, 23, M)
    d.rect(0, 24, 79, 26, R)
    d.rect(0, 27, 79, 29, Y)
    for x0, x1, y, c in ((33, 44, 17, M), (35, 41, 16, M), (50, 60, 17, M),
                         (20, 26, 23, R), (34, 42, 23, R), (50, 58, 23, R), (36, 40, 22, R),
                         (32, 42, 26, Y), (50, 60, 26, Y), (14, 22, 27, R)):
        d.rect(x0, y, x1, y, c)
    # ---------------- Meer (Zeilen 11–13): Abendlicht und Wellenkämme
    d.rect(0, 30, 79, 38, B)
    for x0, x1, y, ph in STREAKS:
        dx = WATER_DX[(water + ph) % len(WATER_DX)] if water >= 0 else 0
        d.rect(x0 + (dx if ph % 2 else 0), y, x1 + dx, y, Y)
    for x0, x1, y, ph in CRESTS:
        dx = WATER_DX[(water * 2 + ph) % len(WATER_DX)]
        d.rect(x0 + dx, y, x1 + dx, y, C)
    # ---------------- Felsnase rechts: grüner Hang (Zeilen 9–10), Fels (Zeilen 11–13)
    d.poly([(60, 29), (62, 27), (64, 25), (66, 24), (79, 24), (79, 29)], G)
    # Fels unter der Felsnase: grüne Wand mit schwarzen Schichtfugen, Kante zum Wasser bei x = 60; links davon
    # (hinter der Laterne) bleibt der Fels schwarz
    d.poly([(54, 38), (57, 34), (59, 31), (60, 30), (79, 30), (79, 38)], K)
    d.rect(60, 30, 79, 38, G)
    for x0, x1, y in ROCK_CRACKS:
        d.rect(x0, y, x1, y, K)
    # ---------------- Leuchtturm (Zellen 34–36)
    d.rect(70, 6, 71, 6, R)                         # Dachspitze
    d.rect(68, 7, 73, 8, R)                         # Dach
    d.rect(68, 9, 73, 11, K)                        # Laternenhaus (Rahmen schwarz)
    d.rect(*LAMP[:2], *LAMP[2:], Y)                 # Lampe
    d.rect(67, 12, 74, 12, Wh)                      # Galerie
    d.rect(68, 13, 73, 26, Wh)                      # Turm
    d.rect(68, 18, 73, 20, R)                       # rotes Band
    d.rect(70, 23, 71, 26, K)                       # Tür
    # Leuchtfeuer (Zustand sky)
    beam = BEAM[sky % N_SKY]
    beam_px = []
    if beam.startswith("L"):
        for x in range(int(beam[1:]), 68):
            beam_px.append((x, 10))
            if 67 - x >= 12:                     # weiter weg breiter
                beam_px += [(x, 9), (x, 11)]
    elif beam == "F":
        d.rect(68, 9, 73, 11, Y)                 # Lampe blendet zum Betrachter auf
    for x, y in beam_px:
        d.rect(x, y, x, y, Y)
    # ---------------- Häuschen links (Zellen 0–11)
    d.poly([(0, 19), (8, 19), (21, 32), (0, 32)], C)  # Schieferdach
    d.rect(8, 15, 11, 21, Wh)                         # Schornstein
    d.rect(8, 15, 11, 17, R)                          # Topf: füllt Zellenzeile 6, Rauch beginnt darüber
    d.rect(0, 30, 23, 56, Wh)                         # Mauer
    d.poly([(0, 30), (19, 30), (21, 32), (0, 32)], C)
    d.rect(22, 33, 23, 38, Wh)
    d.rect(4, 33, 9, 41, Y)                           # Fenster, erleuchtet
    d.rect(6, 33, 6, 41, Wh); d.rect(4, 37, 9, 37, Wh)  # Fensterkreuz
    d.rect(*DOOR, K)                                  # offene Tür
    # ---------------- Boote
    d.rect(26, 35, 37, 35, Wh)                        # Boot 1: weißer Bord, roter Rumpf
    d.poly([(26, 36), (37, 36), (35, 38), (28, 38)], R)
    d.rect(29, 24, 29, 34, Wh)                        # Mast 1
    d.rect(41, 35, 51, 35, R)                         # Boot 2: roter Bord, gelber Rumpf
    d.poly([(41, 36), (51, 36), (49, 38), (43, 38)], Y)
    d.rect(49, 27, 49, 34, Wh)                        # Mast 2
    # ---------------- Kai
    d.rect(24, 39, 79, 41, B)                         # Kaikante (Stirnseite im Schatten)
    d.rect(24, 39, 79, 39, Wh)                        # Kantenstein oben
    d.rect(24, 42, 79, 56, K)                         # Pflaster
    if cobbles:
        for y in (44, 47, 50, 53, 56):
            off = (y // 3) % 2
            for x in range(24 + off * 2, 80, 4):
                d.rect(x, y, x, y, B)
    # Laterne auf Pfahl
    d.rect(55, 35, 58, 35, R)                         # Kappe
    d.rect(*LANTERN[:2], *LANTERN[2:], Y)             # Glas
    d.rect(55, 36, 55, 38, K); d.rect(58, 36, 58, 38, K)
    d.rect(56, 39, 56, 56, Y)                         # Pfahl
    d.rect(52, 39, 59, 39, Y)                         # Lichtschein der Laterne auf dem Kantenstein
    d.rect(60, 39, 61, 39, 255)                       # egal: dort zeigt der Weiß-Code das gehaltene Gelb
    # Paket am Kai (Schnur als Lücke)
    d.rect(48, 51, 53, 56, Y)
    d.rect(51, 51, 51, 56, K); d.rect(48, 54, 53, 54, K)
    # Kisten: Bretter als waagerechte Fugen
    d.rect(62, 45, 69, 56, Y)
    for y in (48, 51, 54):
        d.rect(62, y, 69, y, K)
    d.rect(66, 45, 66, 50, K)
    # Fässer: gerundet, ein Reifen als Lücke
    for x0 in (72, 76):
        d.rect(x0, 49, x0 + 2, 56, R)
        d.rect(x0 + 1, 48, x0 + 1, 48, R)
        d.rect(x0, 52, x0 + 2, 52, K)
    # Rauch
    smoke = smoke_puffs(sky)
    for x0, y0, x1, y1, c in smoke:
        d.rect(x0, max(y0, 6), x1, y1, c)
    t_on = d.arr()

    # Gewichte
    w = np.ones((H, W))
    w[6:27, 66:76] = 4          # Leuchtturm
    w[33:42, 3:11] = 3          # Fenster
    w[35:57, 54:59] = 3         # Laterne
    w[39:42, 56] = 8            # Pfahl auch vor der Kaikante gelb (sonst wird er dort weiß)
    w[30:39, 59:64] = 3         # Felskante neben der Laterne
    w[51:57, 47:54] = 2         # Paket
    w[19:33, 0:22] = 2          # Dach
    w[13:22, 7:12] = 3          # Schornstein

    # Aus-Phase des Blinkens
    t_off = t_on.copy()
    if beam != "F":
        t_off[LAMP[1]:LAMP[3] + 1, LAMP[0]:LAMP[2] + 1] = K
    sep = np.zeros((19, 40), dtype=int)
    for x, y in STARS:
        t_on[y, x] = Wh
        t_off[y, x] = Wh
        sep[y // 3, x // 2] = 1
    for x, y in FLASH_STARS:
        t_off[y, x] = B
    for x, y in GLINTS:
        t_on[y, x] = Wh; t_off[y, x] = B
    for x, y in beam_px:                          # Lichtstrahl: getrennte Mosaike (wirkt wie Lichtpunkte)
        sep[y // 3, x // 2] = 1
        w[y, x] = 2
    for x0, y0, x1, y1, c in smoke:              # Rauch zählt doppelt und ist zusammenhängend (verdeckt Sterne)
        w[max(y0, 6):y1 + 1, x0:x1 + 1] = 2
        for y in range(max(y0, 6), y1 + 1):
            for x in range(x0, x1 + 1):
                sep[y // 3, x // 2] = 0
    if cobbles:
        for r in range(14, 19):              # Zeichenzeilen 15–19: Pflasterzellen getrennt
            for c in range(12, 40):
                blk = t_on[3 * r:3 * r + 3, 2 * c:2 * c + 2]
                if np.isin(blk, (K, B)).all():
                    sep[r, c] = 1
    return t_on, t_off, w, sep, STARS


if __name__ == "__main__":
    t_on, *_ = draw()
    img = T.PALETTE[np.where(t_on < 0, 0, t_on)]
    Image.fromarray(img).resize((W * 8, H * 8), Image.NEAREST).save("/tmp/scene_target.png")
