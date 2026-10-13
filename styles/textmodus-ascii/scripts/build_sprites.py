#!/usr/bin/env python3
"""Dachs-Kurier als Zeichen-Sprite aus Halbblöcken (▀ ▄ █).

Oberkörper fest (von Hand gesetzt), Beine je Bild aus Hüfte und Fußposition gezogen, damit der Standfuß beim
Laufen ortsfest bleibt: Der Körper rückt je Laufbild genau eine Zelle vor, der Standfuß relativ zum Körper eine
Zelle zurück. 8 Laufbilder je Doppelschritt, Schrittweite 4 Zellen. 10 Spalten × 16 Halbzeilen (10×8 Zellen).

Ausgabe: demo/data/sprites.json, assets/badger_sheet.png (Vorschau ×4 vor Kai und Meer)

    .venv/bin/python styles/textmodus-ascii/scripts/build_sprites.py
"""
import json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tmscreen import *  # noqa: E402,F401

ROOT = pathlib.Path(__file__).resolve().parent.parent
W, H = 11, 16
HIP_V = 12            # erste Beinzeile

# Oberkörper nach rechts (Laufrichtung). k schwarz, d dunkelgrau, w weiß, l hellgrau, g grün, r rot,
# R hellrot, n braun, y gelb, '.' durchsichtig. Zellen sind Zeilenpaare (0/1, 2/3 …): zwei helle Farben
# (d w R y …) dürfen nicht übereinander in einem Paar liegen. Kopf ragt nach vorn, Schnauze spitz.
UPPER = [
    "....gggg...",
    "...gggggggg",
    "...dwwwww..",
    "..ddkkkwwwk",
    "..ddkkwwww.",
    "..dddwww...",
    ".rrrrrrr...",
    "_rRrrrrr...",
    "_.lllgggd..",
    "r.lldggnnd.",
    ".nnggggnyn.",
    ".nnggggnnn.",
]
SCARF = {  # Schalende hinter dem Hals, zwei Windstellungen (Platzhalter "_" in Zeile 7 und 8)
    0: ("r", "r"),
    1: ("R", "."),
}

FRONT = [
    "..gggggg...",
    ".ggggyggg..",
    "lwkkwwkkwl.",
    ".wklwwlkw..",
    "..wwkkww...",
    "..rrrrrr...",
    ".rrrrrrRr..",
    "ldgggggrdl.",
    "ldggyggrdl.",
    ".dgggnnnd..",
    ".dgggnynd..",
    "..gggnnn...",
    "..wwwwww...",
    "..kkkkkk...",
    "..kk..kk...",
    ".kkk..kkk..",
]
# Vorderansicht, rechte Hand an der Mütze (Gruß)
FRONT_TIP = [
    "..gggggg...",
    ".ggggygggd.",
    "lwkkwwkkwld",
    ".wklwwlkwd.",
    "..wwkkwwd..",
    "..rrrrrrk..",
    ".rrrrrrRr..",
    "ldgggggrl..",
    "ldggyggrl..",
    ".dgggnnn...",
    ".dgggnyn...",
    "..gggnnn...",
    "..wwwwww...",
    "..kkkkkk...",
    "..kk..kk...",
    ".kkk..kkk..",
]


# Bildnis für das Gesprächsfenster: 18 Spalten × 16 Halbzeilen (18×8 Zellen), von vorn
PORTRAIT = [
    "......gggggg......",
    "....gggggggggg....",
    "...gggggyyggggg...",
    "...nnnnnnnnnnnn...",
    "..lkwkkkwwkkkwkl..",
    "..lwwklkwwklkwwl..",
    "...wwwkkwwkkwww...",
    "....wwwkwwkwww....",
    ".....wwwkkwww.....",
    "......wwkkww......",
    ".......wwww.......",
    "...rrrrrrrrrrrr...",
    ".llrRrrrrrrrRrrll.",
    ".lllggggrrnggglll.",
    ".lllggyggrrnyglll.",
    ".dddggggrrggnggddd",
]
PORTRAIT_BLINK = list(PORTRAIT)
PORTRAIT_BLINK[5] = "..lwwkkkwwkkkwwl.."     # Augen zu


def legs(near, far, lift_near=0, lift_far=0):
    """Beine von der Hüfte zu den Füßen. near/far: Fersenspalte des nahen (dunkelgrau) und fernen (schwarz)
    Fußes relativ zum Sprite; lift hebt den Fuß um eine Halbzeile."""
    rows = [list("." * W) for _ in range(H - HIP_V)]
    rows[0] = list("..dwwwwwd..")           # Bauch

    def leg(foot, col, lift):
        hip = 4
        x1 = int(round(hip + (foot - hip) / 3))         # Oberschenkel (Zeile 1, schwarz wie beim Dachs)
        for dx in (0, 1):
            rows[1][x1 + dx] = "k"
        if lift:
            x2 = int(round(hip + (foot - hip) * 2 / 3))
            rows[2][x2] = col
            rows[2][foot] = "k"
            rows[2][foot + 1] = "k"
        else:
            x2 = int(round(hip + (foot - hip) * 2 / 3))
            for dx in (0, 1):
                rows[2][x2 + dx] = col
            rows[3][foot] = "k"
            rows[3][foot + 1] = "k"
            if foot >= 5:
                rows[3][min(W - 1, foot + 2)] = "k"     # Zehen nach vorn

    leg(far, "k", lift_far)
    leg(near, "d", lift_near)
    return ["".join(r) for r in rows]


def side_frame(near, far, lift_near=0, lift_far=0, scarf=0):
    up = list(UPPER)
    for row, rep in zip((7, 8), SCARF[scarf]):
        up[row] = rep + up[row][1:]
    assert all(len(r) == W for r in up), up
    return up + legs(near, far, lift_near, lift_far)


def walk_cycle():
    """8 Bilder je Doppelschritt. Bild i (0..3) der ersten Hälfte: naher Fuß steht bei 6-i (absolut fest,
    weil der Körper je Bild +1 vorrückt), ferner Fuß schwingt von 2 nach 5 (Bilder 1 und 2 gehoben).
    Zweite Hälfte mit vertauschten Beinen."""
    frames = []
    for half in range(2):
        for i in range(4):
            st, sw, lift = 6 - i, 2 + i, int(i in (1, 2))
            if half == 0:
                frames.append(side_frame(near=st, far=sw, lift_far=lift, scarf=(i // 2)))
            else:
                frames.append(side_frame(near=sw, far=st, lift_near=lift, scarf=(i // 2)))
    return frames


def clashes(rows, py0=0):
    """Zellen, in denen zwei helle Farben (8–15) übereinander liegen; py0: Halbzeile der Sprite-Oberkante."""
    out = []
    for v in range((py0 % 2), len(rows) - 1, 2):
        for x in range(len(rows[v])):
            a, b = rows[v][x], rows[v + 1][x]
            if a != "." and b != "." and COLOR_LETTERS[a] >= 8 and COLOR_LETTERS[b] >= 8 and a != b:
                out.append((x, v))
    return out


def main():
    frames = walk_cycle()
    stand = side_frame(near=4, far=2, scarf=0)
    stand2 = side_frame(near=4, far=2, scarf=1)
    for p_ in (PORTRAIT, PORTRAIT_BLINK):
        assert all(len(r) == 18 for r in p_) and len(p_) == 16, [len(r) for r in p_]
    for name, fr in [("walk%d" % i, f) for i, f in enumerate(frames)] + [("stand", stand), ("stand2", stand2), ("front", FRONT), ("front_tip", FRONT_TIP),
                    ("portrait", PORTRAIT), ("portrait_blink", PORTRAIT_BLINK)]:
        c = clashes(fr, py0=0)
        if c:
            print("Farbkonflikt in", name, c)
    data = {"w": W, "h": H, "walk": frames, "stand": [stand, stand2], "front": [FRONT, FRONT_TIP],
            "portrait": [PORTRAIT, PORTRAIT_BLINK]}
    out = ROOT / "demo" / "data"
    out.mkdir(parents=True, exist_ok=True)
    (out / "sprites.json").write_text(json.dumps(data, indent=0))
    # Vorschau vor dem echten Hafenbild: oben die 8 Laufbilder, unten Stehen, Vorderansicht, Gruß
    import build_scene
    scene, _ = build_scene.build()
    rows = []
    for k, group in enumerate((frames[:4], frames[4:], [stand, stand2, FRONT, FRONT_TIP])):
        s2 = scene.copy()
        for i, f in enumerate(group):
            s2.sprite(4 + i * 14, 39 - H + 1, f)
        rows.append(s2.render(scale=2).crop((0, 11 * 28, 1280, 20 * 28)))
    from PIL import Image
    sheet = Image.new("RGB", (1280, sum(r.height for r in rows)))
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height
    sheet.save(ROOT / "assets" / "badger_sheet.png")


if __name__ == "__main__":
    main()
