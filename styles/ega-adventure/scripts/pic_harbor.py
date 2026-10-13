#!/usr/bin/env python3
"""Hafen von Lornholm als Zeichenbefehle (160×168, 16 EGA-Farben, Doppelpixel).

Reihenfolge wie bei den Bildern der Vorbilder: zuerst Umrisse, die eine Fläche begrenzen, dann Flutfüllung,
Details als Linien obendrauf. Weiße Flächen (Leuchtturm, Hauswand, Bootsrumpf) entstehen, indem ihr Umriss vor
der umgebenden Füllung gezogen und das Innere nie gefüllt wird. Die Füllstartpunkte rechnet das Skript aus
(ein Punkt je weißer Teilfläche im angegebenen Rechteck, Innenflächen von Gegenständen ausgenommen); in der
Befehlsliste stehen sie als feste Koordinaten.

Prioritätsebene: Fässer und Laternenpfahl stehen vorn auf dem Kai (Fußlinie 162/163 -> Band 14);
der Dachs läuft auf y=146 (Band 13) und wird von ihnen verdeckt.

    .venv/bin/python styles/ega-adventure/scripts/pic_harbor.py
Ausgabe: demo/art/harbor.pic.json, assets/harbor_visual.png, assets/harbor_priority.png
"""
import json, pathlib, sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
SD = HERE.parent
sys.path.insert(0, str(HERE))
from agipic import Pic, W, H, band, line_points, replay, to_rgb  # noqa: E402

K, BL, GR, CY, RD, MG, BR, LG, DG, LB, LGR, LC, LR, LM, YE, WH = range(16)

# Lagen, die die Demo kennt (Views und Animationen hängen daran)
LAYOUT = {
    "chimney_top": [20, 47],
    "lamp": [138, 16, 142, 21],          # Laternenglas des Leuchtturms (x0, y0, x1, y1)
    "lantern": [119, 104, 121, 108],     # Glas der Kai-Laterne
    "window": [15, 95, 23, 105],
    "walk_y": 146,                       # Fußlinie des Dachses
    "horizon": 67,
    "quay_edge": 116,
}

# Innenflächen, die keine Hintergrundfüllung betreten darf (werden später eigens gefüllt oder bleiben weiß)
PROTECT = [
    (140, 40), (140, 18), (140, 12), (140, 59),          # Leuchtturm: Turm, Laterne, Kuppel, Tür
    (140, 80), (155, 61),                                 # Landzunge: Fels, Grasstreifen
    (20, 70), (20, 52), (20, 115), (19, 99), (6, 110),   # Haus: Dach, Schornstein, Wand, Fenster, Tür
    (28, 32), (88, 44), (60, 54),                         # Wolken
    (72, 65),                                             # ferne Insel
    (56, 102), (100, 103), (99, 93), (77, 106),           # Boote, Kajüte, Steg
    (39, 118), (39, 113), (39, 105), (53, 121),           # Kisten (unter und über der Kaikante), Tau
    (139, 150), (148, 150), (120, 106),                   # Fässer, Laterne
]


def components(p, box, target=WH):
    x0, y0, x1, y1 = box
    vis = p.vis
    seen = np.zeros_like(vis, bool)
    seeds = []
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if vis[y, x] == target and not seen[y, x]:
                seeds.append((x, y))
                stack = [(x, y)]
                while stack:
                    cx, cy = stack.pop()
                    if seen[cy, cx] or vis[cy, cx] != target:
                        continue
                    seen[cy, cx] = True
                    for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                        if 0 <= nx < W and 0 <= ny < H and not seen[ny, nx] and vis[ny, nx] == target:
                            stack.append((nx, ny))
    return seeds, seen


def fill_box(p, color, box, protect=True):
    """Füllt jede weiße Teilfläche, die das Rechteck berührt (ein Startpunkt je Teilfläche).
    protect=True: Teilflächen, die eine geschützte Innenfläche enthalten, bleiben weiß."""
    p.color(color)
    seeds, _ = components(p, box)
    keep = []
    for s in seeds:
        if protect:
            _, comp = components(p, (s[0], s[1], s[0], s[1]))
            if any(comp[y, x] for x, y in PROTECT):
                continue
        keep.append(s)
    if keep:
        p.fill(*keep)
    return keep


def fill_at(p, color, *pts):
    """Flutfüllung an festen Startpunkten (für Gegenstände)."""
    p.color(color)
    p.fill(*pts)


def protected_mask(p, limit=3000):
    """Innenflächen geschlossener Gegenstände (Komponente eines Schutzpunkts, höchstens `limit` Pixel)."""
    m = np.zeros(p.vis.shape, bool)
    for x, y in PROTECT:
        if p.vis[y, x] != WH or m[y, x]:
            continue
        _, comp = components(p, (x, y, x, y))
        if comp.sum() <= limit:
            m |= comp
    return m


def outside(p, color, *pts):
    """Linienzug nur auf weißen Pixeln außerhalb geschlossener Gegenstände (Himmelsbänder, Horizont):
    die Linie endet genau am Umriss des Gegenstands, der Umriss setzt die Grenze fort."""
    m = protected_mask(p)
    p.color(color)
    for a, b in zip(pts[:-1], pts[1:]):
        run = []
        seg = line_points(*a, *b)
        for i, (x, y) in enumerate(seg):
            ok = 0 <= x < W and 0 <= y < H and p.vis[y, x] == WH and not m[y, x]
            if ok:
                run.append((x, y))
            if (not ok or i == len(seg) - 1) and run:
                if len(run) == 1:
                    p.dots(run[0])
                elif line_points(*run[0], *run[-1]) == run:
                    p.line(run[0], run[-1])
                else:
                    p.dots(*run)
                run = []


def over(p, color, a, b, on):
    """Linie nur dort ziehen, wo die sichtbare Ebene schon die Farbe(n) `on` hat (Fugen, Wellen, Streifen)."""
    on = (on,) if isinstance(on, int) else tuple(on)
    pts = line_points(*a, *b)
    run = []
    p.color(color)

    def flush():
        if not run:
            return
        if len(run) == 1:
            p.dots(run[0])
        elif line_points(*run[0], *run[-1]) == run:
            p.line(run[0], run[-1])
        else:
            p.dots(*run)

    for (x, y) in pts:
        if 0 <= x < W and 0 <= y < H and p.vis[y, x] in on:
            run.append((x, y))
        else:
            flush()
            run = []
    flush()


def build():
    p = Pic()

    # ------------------------------------------------------------------ Himmel: Bandgrenzen, Horizont, Wolken
    # ------------------------------------------------------------------ Silhouetten: Leuchtturm, Landzunge, Haus
    p.note("Leuchtturm: Umriss")
    p.color(K)
    p.line((136, 62), (137, 25), (143, 25), (144, 62))           # Turm
    p.line((134, 24), (146, 24))                                  # Galerie
    p.line((134, 23), (146, 23))
    p.line((137, 22), (137, 15), (143, 15), (143, 22))            # Laternenhaus
    p.color(RD).poly((136, 14), (139, 10), (141, 10), (144, 14))  # Kuppel
    p.color(K).dots((140, 9))
    p.note("Landzunge: Umriss")
    p.color(GR).line((159, 59), (150, 60), (146, 62), (134, 62), (128, 63), (123, 69))
    p.color(DG).line((123, 69), (120, 77), (117, 86), (115, 92), (111, 98), (159, 98))
    p.color(GR).line((124, 68), (128, 66), (134, 65), (146, 65), (152, 63), (159, 62))
    p.note("Haus: Umriss")
    p.color(K)
    p.line((0, 84), (35, 84), (28, 58), (0, 58))                  # Dach
    p.line((18, 59), (18, 48), (23, 48), (23, 63))                # Schornstein
    p.line((0, 85), (31, 85), (31, 124))                          # Wand
    p.line((31, 124), (0, 124))
    p.color(BR).poly((14, 94), (24, 94), (24, 106), (14, 106))    # Fensterrahmen
    p.color(K).poly((3, 100), (10, 100), (10, 124), (3, 124))     # Tür
    p.note("Masten")
    p.color(BR).line((55, 97), (55, 72))
    p.color(BR).line((106, 97), (106, 56))

    # ------------------------------------------------------------------ Himmel: Bandgrenzen, Horizont, Wolken
    p.note("Himmel: Bandgrenzen und Horizont")
    outside(p, BL, (0, 25), (50, 24), (110, 25), (159, 23))
    outside(p, MG, (0, 40), (60, 41), (120, 39), (159, 40))
    outside(p, LR, (0, 51), (70, 52), (159, 50))
    outside(p, YE, (0, 59), (80, 60), (159, 59))
    outside(p, BL, (0, 67), (159, 67))
    p.note("Wolken und ferne Insel: Umriss")
    p.color(MG).poly((10, 33), (18, 31), (38, 31), (46, 33), (32, 34), (14, 34))
    p.color(BL).poly((66, 45), (76, 43), (100, 43), (110, 45), (94, 46), (72, 46))
    p.color(MG).poly((40, 55), (50, 53), (70, 53), (78, 55), (66, 56), (44, 56))
    p.color(DG).line((52, 66), (58, 64), (66, 63), (78, 63), (86, 65), (92, 66))

    # ------------------------------------------------------------------ Himmel füllen
    p.note("Himmel füllen")
    fill_box(p, K, (0, 0, 159, 22))
    fill_box(p, BL, (0, 25, 159, 39))
    fill_box(p, MG, (0, 41, 159, 50))
    fill_box(p, LR, (0, 52, 159, 58))
    fill_box(p, YE, (0, 60, 159, 66))
    p.note("Wolken, Insel, Sterne")
    fill_at(p, MG, (28, 32))
    fill_at(p, BL, (88, 44))
    fill_at(p, MG, (60, 54))
    fill_at(p, DG, (72, 65))
    p.color(WH).dots((6, 4), (23, 12), (37, 6), (52, 17), (61, 3), (79, 10), (94, 5), (103, 15),
                     (118, 8), (127, 18), (150, 4), (156, 14), (12, 20), (70, 19), (88, 21), (31, 27),
                     (122, 29), (57, 28))
    p.color(LG).dots((44, 9), (110, 20), (16, 9), (84, 30), (149, 33), (63, 36))

    # ------------------------------------------------------------------ Landzunge und Leuchtturm füllen
    p.note("Landzunge füllen")
    fill_at(p, GR, (155, 61))
    fill_at(p, DG, (140, 80))
    for a, b in [((121, 76), (127, 78)), ((127, 78), (134, 77)), ((118, 86), (126, 88)), ((126, 88), (133, 87)),
                 ((135, 71), (142, 72)), ((142, 72), (151, 70)), ((146, 81), (153, 83)), ((153, 83), (159, 82)),
                 ((114, 94), (124, 95)), ((140, 92), (150, 94)), ((150, 94), (159, 93)), ((132, 84), (139, 85))]:
        over(p, K, a, b, DG)
    for a, b in [((122, 71), (119, 80)), ((119, 80), (117, 88)), ((130, 74), (135, 73)), ((139, 81), (145, 80)),
                 ((150, 88), (156, 87)), ((126, 91), (131, 91)), ((144, 75), (150, 74))]:
        over(p, LG, a, b, DG)
    p.note("Leuchtturm: Band, Kuppel, Laterne, Tür")
    over(p, RD, (136, 38), (144, 38), WH)
    over(p, RD, (136, 46), (144, 46), WH)
    fill_box(p, RD, (138, 39, 142, 45), protect=False)
    fill_at(p, RD, (140, 12))
    fill_at(p, YE, (140, 18))
    p.color(K).line((140, 16), (140, 22))
    p.color(K).poly((139, 62), (139, 56), (141, 56), (141, 62))
    p.color(K).line((140, 57), (140, 61))
    p.color(K).dots((140, 30), (140, 51))

    # ------------------------------------------------------------------ Steg, Boote, Kai-Requisiten: Umrisse
    p.note("Steg und Boote: Umriss")
    p.color(K).poly((64, 116), (90, 116), (84, 96), (70, 96))               # Steg
    p.color(K).poly((44, 98), (66, 96), (63, 106), (47, 106))               # Boot 1 (weißer Rumpf)
    p.color(K).poly((90, 97), (112, 96), (110, 107), (93, 107))             # Boot 2
    p.color(K).poly((96, 90), (103, 90), (103, 96), (96, 96))               # Kajüte
    p.note("Kaikante")
    p.color(K).line((32, 116), (159, 116))
    p.color(DG).line((32, 117), (159, 117))
    p.note("Kisten, Tau, Fässer, Laterne: Umriss (Fässer und Laterne mit Priorität)")
    p.color(K).poly((34, 110), (45, 110), (45, 124), (34, 124))
    p.color(K).poly((36, 101), (43, 101), (43, 109), (36, 109))
    p.color(K).poly((48, 120), (51, 118), (55, 118), (58, 120), (55, 123), (51, 123))
    p.prio(band(162))
    for x0 in (136, 145):
        # Fass mit Bauch: Deckel (Ellipse), Rand, gewölbte Seiten
        p.color(K).poly((x0 + 2, 140), (x0 + 5, 140), (x0 + 6, 141), (x0 + 6, 144), (x0 + 7, 146), (x0 + 7, 156),
                        (x0 + 6, 158), (x0 + 6, 160), (x0 + 5, 162), (x0 + 2, 162), (x0 + 1, 160), (x0 + 1, 158),
                        (x0, 156), (x0, 146), (x0 + 1, 144), (x0 + 1, 141))
        p.color(K).line((x0 + 1, 142), (x0 + 6, 142))
    p.prio(band(163))
    p.color(BR).line((120, 110), (120, 163))
    p.color(K).poly((118, 103), (122, 103), (122, 109), (118, 109))
    p.color(K).line((118, 102), (120, 100), (122, 102))
    p.prio(-1)

    # ------------------------------------------------------------------ Wasser
    p.note("Wasser füllen")
    fill_box(p, BL, (0, 68, 159, 115))
    p.note("Wellen und Spiegelungen")
    for (x0, x1, y, c) in [(36, 46, 69, YE), (58, 64, 70, YE), (80, 92, 69, LR), (100, 104, 71, YE),
                           (20, 28, 71, LR), (66, 74, 73, LR), (90, 96, 74, YE), (40, 44, 75, LR),
                           (8, 16, 76, LB), (60, 64, 80, LB), (84, 90, 79, LB), (34, 38, 84, LB),
                           (72, 80, 86, CY), (14, 20, 90, CY), (64, 68, 92, CY), (26, 32, 96, LB),
                           (2, 8, 106, CY), (40, 48, 110, LB), (94, 100, 112, CY), (114, 118, 108, LB),
                           (126, 134, 104, CY), (144, 150, 106, LB), (134, 140, 112, LB), (54, 58, 113, CY),
                           (20, 26, 112, LB), (150, 156, 101, CY), (116, 122, 101, LB)]:
        over(p, c, (x0, y), (x1, y), BL)

    p.note("Steg, Boote füllen")
    fill_at(p, BR, (77, 106))
    for y in (99, 102, 105, 108, 111, 114):
        over(p, K, (60, y), (94, y), BR)
    p.color(K).line((70, 92), (70, 96))
    p.color(K).line((84, 92), (84, 96))
    over(p, RD, (44, 101), (66, 101), WH)
    over(p, RD, (44, 102), (66, 102), WH)
    fill_at(p, BR, (100, 103))
    over(p, K, (90, 100), (112, 100), BR)
    p.color(K).dots((99, 93))
    over(p, LG, (51, 89), (61, 89), BL)
    over(p, LG, (52, 88), (60, 88), BL)
    over(p, LG, (102, 76), (106, 76), BL)

    # ------------------------------------------------------------------ Haus
    p.note("Haus: Dach, Schornstein, Fenster, Tür")
    fill_at(p, RD, (20, 70))
    for y in (64, 70, 76):
        over(p, K, (0, y), (35, y), RD)
    fill_at(p, LG, (20, 52))
    p.color(K).line((18, 49), (23, 49))
    fill_at(p, YE, (19, 99))
    p.color(K).line((19, 95), (19, 105))
    p.color(K).line((15, 100), (23, 100))
    fill_at(p, BR, (6, 110))
    p.color(YE).dots((8, 112))
    for a, b in [((1, 90), (5, 90)), ((26, 91), (30, 91)), ((12, 113), (13, 113)), ((25, 112), (30, 112)),
                 ((14, 118), (20, 118)), ((26, 120), (29, 120)), ((1, 96), (2, 96)), ((24, 109), (27, 109))]:
        over(p, LG, a, b, WH)

    # ------------------------------------------------------------------ Kai
    p.note("Kisten und Tau füllen")
    fill_box(p, BR, (35, 111, 44, 123), protect=False)
    fill_at(p, BR, (39, 105))
    over(p, BR, (35, 116), (44, 116), (K, DG))
    over(p, BR, (35, 117), (44, 117), (K, DG))
    over(p, K, (35, 111), (44, 123), BR)
    over(p, K, (44, 111), (35, 123), BR)
    over(p, K, (37, 102), (42, 108), BR)
    fill_at(p, BR, (53, 121))
    over(p, K, (51, 120), (55, 120), BR)
    over(p, K, (52, 121), (54, 121), BR)

    p.note("Kai füllen")
    fill_box(p, LG, (0, 118, 159, 167))
    p.note("Pflasterfugen")
    rows = [117, 123, 129, 136, 144, 153, 167]
    for y in rows[1:-1]:
        over(p, DG, (0, y), (159, y), LG)
    for i in range(len(rows) - 1):
        y0, y1 = rows[i] + 1, rows[i + 1] - 1
        step = [9, 10, 12, 14, 16, 18][i]
        off = (i % 2) * step // 2
        for x in range(off + 3, 160, step):
            over(p, DG, (x, y0), (x, y1), LG)

    p.note("Fässer und Laterne füllen (Priorität 14)")
    p.prio(band(162))
    for x0 in (136, 145):
        fill_at(p, BR, (x0 + 3, 150))
        fill_at(p, DG, (x0 + 3, 141))
        over(p, K, (x0, 146), (x0 + 7, 146), BR)
        over(p, K, (x0, 156), (x0 + 7, 156), BR)
        over(p, K, (x0 + 5, 147), (x0 + 5, 155), BR)
        over(p, YE, (x0 + 2, 147), (x0 + 2, 155), BR)
    p.prio(band(163))
    fill_at(p, YE, (120, 106))
    p.prio(-1)
    return p


def main():
    p = build()
    vis, pri = replay(p.cmds)
    assert (vis == p.vis).all() and (pri == p.pri).all(), "Wiedergabe weicht ab"
    art = SD / "demo" / "art"
    art.mkdir(parents=True, exist_ok=True)
    data = p.to_json()
    data["layout"] = LAYOUT
    data["notes"] = p.notes
    for d in (art, SD / "assets"):     # verarbeitetes Asset in assets/, Kopie für die Demo in demo/art/
        d.mkdir(parents=True, exist_ok=True)
        (d / "harbor.pic.json").write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False))
    (SD / "assets").mkdir(exist_ok=True)
    to_rgb(vis).save(SD / "assets" / "harbor_visual.png")
    to_rgb(pri).save(SD / "assets" / "harbor_priority.png")
    white = int((vis == 15).sum())
    n_l = sum(1 for c in p.cmds if c[0] == "l")
    n_f = sum(len(c[1]) // 2 for c in p.cmds if c[0] == "f")
    size = len(json.dumps(p.cmds, separators=(",", ":")))
    print(f"{len(p.cmds)} Befehle ({n_l} Linienzüge, {n_f} Füllstartpunkte, {size} Byte JSON), "
          f"Arbeit {p.work} px, weiß übrig {white} px, Farben {len(np.unique(vis))}")


if __name__ == "__main__":
    main()
