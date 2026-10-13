#!/usr/bin/env python3
"""Views (Sprites) im AGI-Raster: Doppelpixel, 16 EGA-Farben, 1-Bit-Transparenz.

Der Dachs ist von Hand gesetzt (Vorlage: Ausgabe von draft_badger.py aus shared/badger/walk_painted.png).
Bei 9–10 Doppelpixeln Breite entscheidet jedes Pixel; Verkleinern allein ergibt keine lesbare Figur.
Die Beine werden je Bild aus Hüfte und Fußposition gesetzt, damit der Standfuß über mehrere Bilder
ortsfest bleibt (Vorschub je Bild steht in views.json -> walk.advance).

Ausgabe: demo/art/views.json (Bilder als Zeichenketten) und assets/views_preview.png (Ansicht).
    .venv/bin/python styles/ega-adventure/scripts/build_views.py
"""
import json, pathlib

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
SD = HERE.parent
EGA = ["000000", "0000aa", "00aa00", "00aaaa", "aa0000", "aa00aa", "aa5500", "aaaaaa",
       "555555", "5555ff", "55ff55", "55ffff", "ff5555", "ff55ff", "ffff55", "ffffff"]
# Zeichen -> EGA-Index ('.' = transparent)
CH = {"K": 0, "b": 1, "G": 2, "c": 3, "R": 4, "m": 5, "B": 6, "L": 7, "D": 8, "u": 9, "g": 10,
      "C": 11, "r": 12, "M": 13, "Y": 14, "W": 15}

W, H = 10, 31          # Zelle des Dachses (Doppelpixel); Figur 30 hoch, eine Zeile Luft für den Körperhub
TOP = 1                # Körper beginnt in Zeile 1, beim Hub in Zeile 0
HIP_Y = 24             # unterste Zeile des Körpers
FOOT_Y = 30            # Fußzeile (Standlinie)

# Körper nach rechts blickend, Zeilen 0..23; Schalende (Spalten 0–1, Zeilen 9–14) wird je Bild ersetzt.
BODY = """
....GGG...
...GGGGG..
...GGYGGGG
...DDWWW..
..DDKKWWW.
..DDDKKWWK
..DDWWWWW.
...DDWW...
..RRRRRR..
..RRRRRRR.
..GGWWRR..
..GGWWGR..
..GGWWGG..
..GGDBWBB.
..GGDWWWW.
.BGGDBWBB.
.BGGGDDDD.
.BGGGGGG..
..GGGGGG..
..DDDKKK..
..DDDKKK..
..DDKKKK..
..DDKKKK..
...DKKK...
"""

# Schalende hinter dem Rücken in drei Windstellungen (Spalten 0–2, Zeilen 8–15), '_' = Körper unverändert
TAILS = [
    """
___
R__
RR_
RR_
R__
R__
___
___
""",
    """
___
RR_
RR_
R__
R__
___
___
___
""",
    """
R__
RR_
RR_
R__
___
___
___
___
""",
]

# Vorderansicht (Blick zum Spieler), 10×30
FRONT = """
...GGGG...
..GGGGGG..
.GGGYGGGG.
.DWKWWKWD.
.DKKWWKKD.
..KWWWWK..
..WWKKWW..
...WWWW...
..RRRRRR..
.RRRRRRRR.
.WGRRGGGW.
.WGRRGGGW.
.DGRRGBWBB
.DGGRGWWWW
.DGGRGBWBB
..GGRGDDDD
..GGGGGG..
..GGGGGG..
..DGGGGD..
..DKKKKD..
..DKKKKD..
..DKKKKD..
..KKKKKK..
..KKKKKK..
..KK..KK..
..KK..KK..
..KK..KK..
..KK..KK..
..KK..KK..
.KKK..KKK.
"""

# zweite Vorderansicht: Schalenden im Wind eine Spalte nach links
FRONT2_SCARF = {10: ".WRRGGGGW.", 11: ".WRRGGGGW.", 12: ".DRRGGBWBB", 13: ".DGRGGWWWW",
                14: ".DGRGGBWBB", 15: "..GGRGDDDD"}

# Umgebungs-Views (Doppelpixel, '.' transparent)
AMBIENT = {
    # Leuchtturm-Laterne: Glas 138..142 × 16..21, Pfosten x=140 bleibt; Ursprung (131, 15)
    "lamp": {"origin": [131, 15], "frames": [
        ["...................",
         ".......WW.WW.......",
         ".......WW.WW.......",
         ".......WW.WW.......",
         ".......WW.WW.......",
         ".......WW.WW.......",
         ".......WW.WW.......",
         "..................."],
        ["...................",
         "...Y...WW.WW...Y...",
         ".......WW.WW.......",
         "YYYYYW.WW.WW.WYYYYY",
         "YYYYYW.WW.WW.WYYYYY",
         ".......WW.WW.......",
         "...Y...WW.WW...Y...",
         "..................."]]},
    "gull": {"frames": [["W.W", ".W."], ["...", "WWW"]]},
    "smoke": {"frames": [["L"], ["LL"], ["LL", "LL"], [".LL", "LLL"], [".DD", "DDD"], ["D.D", ".D."]]},
}


def grid(s, w=None):
    rows = [r for r in s.strip("\n").split("\n")]
    w = w or max(len(r) for r in rows)
    return [list(r.ljust(w, ".")) for r in rows]


def leg(g, hip_x, foot_x, lift, col, toe_col):
    """2 Doppelpixel breites Bein von der Hüfte (Zeile HIP_Y) bis zum Fuß; Zehe zeigt nach rechts."""
    bottom = FOOT_Y - lift
    span = bottom - HIP_Y
    for y in range(HIP_Y, bottom + 1):
        k = (y - HIP_Y) / span if span else 1.0
        x = int(round(hip_x + (foot_x - hip_x) * k))
        for dx in (0, 1):
            if 0 <= x + dx < W:
                g[y][x + dx] = col
    if 0 <= foot_x + 2 < W:
        g[bottom][foot_x + 2] = toe_col


# Laufzyklus, 6 Bilder: (Fuß nah, Hub nah, Fuß fern, Hub fern, Körper-Hub)
# Standfuß rückt je Bild genau um den Vorschub des Körpers zurück -> ortsfest auf dem Kai.
WALK = [
    (6, 0, 1, 0, 0),   # 0 Kontakt, nahes Bein vorn
    (4, 0, 2, 1, 0),   # 1 nahes Bein trägt, fernes hebt ab
    (3, 0, 4, 1, 1),   # 2 Durchgang (Körper 1 px höher)
    (2, 0, 6, 0, 0),   # 3 Kontakt, fernes Bein vorn
    (2, 1, 4, 0, 0),   # 4 fernes Bein trägt, nahes hebt ab
    (4, 1, 3, 0, 1),   # 5 Durchgang
]
ADVANCE = [2, 1, 1, 2, 1, 1]   # Vorschub nach Bild i (Doppelpixel)


def body_frame(tail, bob):
    g = [["."] * W for _ in range(H)]
    b = grid(BODY, W)
    t = grid(TAILS[tail], 3)
    for ty in range(len(t)):
        for tx in range(3):
            if t[ty][tx] != "_":
                b[8 + ty][tx] = t[ty][tx]
    for y in range(len(b)):
        yy = y + TOP - bob
        if 0 <= yy < H:
            for x in range(W):
                if b[y][x] != ".":
                    g[yy][x] = b[y][x]
    return g


def walk_frame(i):
    nf, nl, ff, fl, bob = WALK[i]
    g = body_frame(i % 3, bob)
    leg(g, 3, ff, fl, "D", "K")      # fernes Bein dunkelgrau (Tiefe), nahes schwarz wie Brust und Bauch
    leg(g, 4, nf, nl, "K", "K")
    return g


def stand_frame(tail):
    g = body_frame(tail, 0)
    # Stand passt zu Laufbild 5 (fernes Bein trägt bei 3): nahes Bein setzt bei 5 auf, kein Rutschen
    leg(g, 3, 3, 0, "D", "K")
    leg(g, 4, 5, 0, "K", "K")
    return g


def to_str(g):
    return ["".join(r) for r in g]


def render(frames, scale=6, bg=(170, 170, 170)):
    fw = max(len(f[0]) for f in frames)
    img = np.zeros((H * scale, (fw * 2 + 2) * len(frames) * scale, 3), np.uint8)
    img[:] = bg
    for i, f in enumerate(frames):
        for y, r in enumerate(f):
            for x, c in enumerate(r):
                if c == ".":
                    continue
                rgb = tuple(int(EGA[CH[c]][k:k + 2], 16) for k in (0, 2, 4))
                x0 = (i * (fw * 2 + 2) + x * 2) * scale
                img[y * scale:(y + 1) * scale, x0:x0 + 2 * scale] = rgb
    return Image.fromarray(img)


def main():
    walk = [to_str(walk_frame(i)) for i in range(6)]
    stand = [to_str(stand_frame(k)) for k in range(3)]
    front = [to_str([["."] * W] + grid(FRONT, W))]
    f2 = [list(r) for r in front[0]]
    for y, r in FRONT2_SCARF.items():
        f2[y + TOP] = list(r)
    front.append(to_str(f2))
    data = {
        "palette": EGA, "chars": CH,
        "badger": {
            "w": W, "h": H, "baseline": FOOT_Y, "facing": "right",
            "walk": {"frames": walk, "advance": ADVANCE, "fps": 10},
            "stand": {"frames": stand, "fps": 6},
            "front": {"frames": front, "fps": 5},
        },
        "ambient": AMBIENT,
    }
    art = SD / "demo" / "art"
    art.mkdir(parents=True, exist_ok=True)
    for d in (art, SD / "assets"):     # verarbeitetes Asset in assets/, Kopie für die Demo in demo/art/
        d.mkdir(parents=True, exist_ok=True)
        (d / "views.json").write_text(json.dumps(data, indent=1))
    rows = [render(walk + stand + front), render(walk + stand + front, bg=(0, 0, 170))]
    out = Image.new("RGB", (rows[0].width, rows[0].height * 2 + 12), (0, 0, 0))
    out.paste(rows[0], (0, 0))
    out.paste(rows[1], (0, rows[0].height + 12))
    (SD / "assets").mkdir(exist_ok=True)
    out.save(SD / "assets" / "views_preview.png")
    print("ok", art / "views.json")


if __name__ == "__main__":
    main()
