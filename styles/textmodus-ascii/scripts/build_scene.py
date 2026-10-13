#!/usr/bin/env python3
"""Zeichnet den Hafen von Lornholm als Textmodus-Bild (80 Spalten, Bildzeilen 1–19) und schreibt

  assets/hafen.ans            das Bild als ANSI-Datei (CP437 + SGR-Farben + SAUCE), lesbar in ANSI-Editoren
  demo/data/scene.json        aus hafen.ans zurückgelesen + Lage der animierten Teile (für main.gd)
  assets/hafen_preview.png    Vorschau ×2 (Bild allein)

Arbeitsweise: Flächen mit Verlauf (Himmel, Meer) sind Zellen mit Schattierzeichen ░▒▓ und Textzeichen.
Gegenstände werden auf einer Halbblock-Ebene (80×50 „Pixel“, je Zelle oben/unten) mit PIL-Formen gezeichnet
und dann in Zellen umgesetzt (▀ ▄ █, zwei helle Farben in einer Zelle sind verboten). Zum Schluss setzen
einzelne Textzeichen Details (Sterne, Wellen, Fensterkreuz, Seile).

    .venv/bin/python styles/textmodus-ascii/scripts/build_scene.py
"""
import json, pathlib, random, sys

from PIL import Image, ImageDraw

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tmscreen import *  # noqa: E402,F401

ROOT = pathlib.Path(__file__).resolve().parent.parent
PIC_TOP, PIC_BOTTOM = 1, 19          # Bildzeilen
HORIZON = 11                         # erste Meereszeile
QUAY = 15                            # erste Kaizeile
T = 255                              # durchsichtig auf der Halbblock-Ebene


def py(row, half=0):
    return row * 2 + half


class Layer:
    """Halbblock-Ebene 80×50 mit Palettenindizes; T = durchsichtig."""

    def __init__(self):
        self.im = Image.new("L", (80, 50), T)
        self.d = ImageDraw.Draw(self.im)

    def stamp(self, s):
        a = self.im.load()
        for y in range(50):
            for x in range(80):
                if a[x, y] != T:
                    s.px(x, y, a[x, y])


# ---------------------------------------------------------------------------------------------------------
def sky(s):
    bands = {
        1: (" ", BLUE, BLACK), 2: (" ", BLUE, BLACK), 3: ("░", BLUE, BLACK), 4: ("▒", BLUE, BLACK),
        5: (" ", LGRAY, BLUE), 6: ("░", MAGENTA, BLUE), 7: ("▒", MAGENTA, BLUE),
        8: ("░", BLUE, MAGENTA), 9: ("▒", RED, MAGENTA), 10: ("▒", YELLOW, RED),
    }
    for y, (ch, fg, bg) in bands.items():
        s.fill(0, y, 79, y, ch, fg, bg)


def stars(s):
    rng = random.Random(7)
    pos = []
    while len(pos) < 18:
        x, y = rng.randrange(22, 80), rng.choice([1, 1, 2, 2, 5])
        if any(abs(x - a) < 3 and y == b for a, b in pos) or s.ch[y, x] != SPACE or 64 <= x <= 73:
            continue
        pos.append((x, y))
        s.cell(x, y, rng.choice("··∙.+*"), rng.choice([WHITE, LGRAY, LCYAN, DGRAY]))
    return pos


WAVE_ROWS = {  # Zeile -> (Muster, Farbe); das Muster wird in der Demo zeilenweise verschoben
    11: ("  ~      -~    ", LBLUE),
    12: ("~≈    ~       ≈~  ", LBLUE),
    13: ("   ~≈~     ~   ", CYAN),
    14: ("≈~      ~≈    ~  ", LCYAN),
}
GLOW_X = 38
GLOW = {11: (12, "═-─=-─"), 12: (8, "─ =- "), 13: (5, "- ─ ="), 14: (3, " -  ")}


def sea(s):
    s.fill(0, HORIZON, 79, QUAY - 1, " ", LBLUE, BLUE)
    for y, (pat, fg) in WAVE_ROWS.items():
        for x in range(80):
            c = pat[x % len(pat)]
            if c != " ":
                s.cell(x, y, c, fg)
    for y, (half, pat) in GLOW.items():
        for x in range(GLOW_X - half, GLOW_X + half + 1):
            c = pat[(x * 7 + y) % len(pat)]
            if c != " ":
                s.cell(x, y, c, YELLOW if abs(x - GLOW_X) < half * 0.6 else LRED)


def hill_west(L):
    pts = [(0, py(6)), (8, py(6, 1)), (16, py(8)), (21, py(9, 1)), (24, py(10, 1)), (26, py(11, 1)),
           (27, py(12, 1)), (27, py(QUAY)), (0, py(QUAY))]
    L.d.polygon(pts, fill=BLACK)


def hill_glyphs(s):
    # dunkler Hang: Baumreihe auf dem Kamm (♣ ♠), darunter Grasbüschel – Spielkartenzeichen wie in Roguelikes
    rng = random.Random(21)
    for x in range(0, 28):
        col = [y for y in range(5, QUAY) if s.ch[y, x] == SPACE and s.bg[y, x] == BLACK]
        if not col:
            continue
        top = col[0]
        s.cell(x, top, rng.choice("♣♣♠"), GREEN)
        for y in col[1:]:
            r = rng.random()
            if r < 0.22:
                s.cell(x, y, '"', GREEN)
            elif r < 0.30:
                s.cell(x, y, "♣", GREEN)


def headland(L):
    pts = [(61, py(14, 1)), (62, py(13, 1)), (63, py(12, 1)), (64, py(11, 1)), (65, py(10, 1)), (66, py(9, 1)),
           (79, py(9, 1)), (79, py(QUAY)), (61, py(QUAY))]
    L.d.polygon(pts, fill=BLACK)
    L.d.line([(61, py(14)), (62, py(13)), (63, py(12)), (64, py(11)), (65, py(10))], fill=BROWN)
    L.d.line([(66, py(9, 1)), (79, py(9, 1))], fill=GREEN)


def headland_glyphs(s):
    # Felsnase: Grasbüschel oben, Felsblöcke (▄▀ in Dunkelgrau) an der Flanke, Sträucher am Turmfuß
    rng = random.Random(4)
    for x in range(66, 80):
        if s.ch[10, x] == SPACE and s.bg[10, x] == BLACK and rng.random() < 0.5:
            s.cell(x, 10, rng.choice('"",♣'), GREEN)
    for x, y, ch in ((63, 12, "▄"), (64, 12, "▄"), (65, 11, "▄"), (66, 11, "▄"), (67, 11, "▄"),
                     (64, 13, "▀"), (65, 13, "▀"), (68, 12, "▄"), (69, 12, "▄"), (70, 12, "▄"),
                     (66, 13, "▄"), (67, 13, "▄"), (72, 11, "▄"), (73, 11, "▄"), (75, 12, "▄"), (76, 12, "▄"),
                     (71, 13, "▀"), (72, 13, "▀"), (73, 13, "▀"), (77, 13, "▀"), (78, 13, "▀")):
        if s.ch[y, x] == SPACE and s.bg[y, x] == BLACK:
            s.cell(x, y, ch, DGRAY)
    for x, y in ((64, 12), (65, 11), (63, 13), (66, 10)):
        if s.ch[y, x] == SPACE and s.bg[y, x] == BLACK:
            s.cell(x, y, "░", BROWN)


LH_X = 70            # linke Turmspalte


def lighthouse(L):
    x0, x1 = LH_X, LH_X + 2
    L.d.rectangle([x0, py(3, 1), x1, py(9, 1)], fill=WHITE)
    L.d.rectangle([x1, py(3, 1), x1, py(9, 1)], fill=LGRAY)        # Schattenseite
    L.d.rectangle([x0, py(6), x1 - 1, py(6, 1)], fill=LRED)        # rotes Band
    L.d.rectangle([x1, py(6), x1, py(6, 1)], fill=RED)
    L.d.rectangle([x0 + 1, py(8, 1), x0 + 1, py(9, 1)], fill=BROWN)  # Tür
    L.d.point((x0 + 1, py(4, 1)), fill=BLACK)                      # Fenster
    L.d.point((x0 + 1, py(7, 1)), fill=BLACK)
    L.d.rectangle([x0 - 1, py(3), x1 + 1, py(3)], fill=BLACK)       # Galerie
    L.d.rectangle([x0, py(1, 1), x1, py(1, 1)], fill=RED)           # Dach
    L.d.point((x0 + 1, py(1)), fill=RED)


def lighthouse_glyphs(s):
    # Laternenhaus: Zeile 2, Lampe in der Mitte (in der Demo animiert)
    s.cell(LH_X, 2, "▐", DGRAY, BLACK)
    s.cell(LH_X + 1, 2, "☼", YELLOW, BLACK)
    s.cell(LH_X + 2, 2, "▌", DGRAY, BLACK)
    return (LH_X + 1, 2)


BOAT = {"x0": 49, "x1": 61, "mast": 56, "mast_top": 6}


def boat(L):
    x0, x1 = BOAT["x0"], BOAT["x1"]
    hull = [(x0, py(12, 1)), (x1, py(12, 1)), (x1 - 2, py(13, 1)), (x0 + 1, py(13, 1))]
    L.d.polygon(hull, fill=WHITE)
    L.d.line([(x0 + 1, py(13)), (x1 - 1, py(13))], fill=RED)
    L.d.rectangle([x0 + 2, py(11, 1), x0 + 5, py(12)], fill=WHITE)      # Kajüte
    L.d.rectangle([x0 + 2, py(11, 1), x0 + 5, py(11, 1)], fill=LRED)
    L.d.point((x0 + 4, py(12)), fill=BLACK)


def boat_glyphs(s):
    m, top = BOAT["mast"], BOAT["mast_top"]
    for y in range(top, 12):
        s.cell(m, y, "│", BLACK)
    s.cell(m, top - 1, "▄", BLACK)
    # Wanten
    for i, y in enumerate(range(top + 1, 12)):
        x = m + 1 + i
        if x <= BOAT["x1"]:
            s.cell(x, y, "\\", BLACK)


def jetty(L):
    # Steg vor dem Boot: Bohlen auf Halbzeile py(14), Pfähle darunter
    L.d.line([(47, py(14)), (66, py(14))], fill=BROWN)
    for x in range(48, 67, 4):
        L.d.point((x, py(14, 1)), fill=BROWN)


def quay(s, L):
    s.fill(0, QUAY, 79, PIC_BOTTOM, " ", DGRAY, BLACK)
    L.d.line([(0, py(QUAY)), (79, py(QUAY))], fill=LGRAY)


def quay_glyphs(s):
    # Steinplatten: volle Zellen, Stoßfugen als halbe Zelle (▐), Platten nach vorn breiter.
    # Farbe hier Dunkelgrau (Schatten); lantern_light() hellt den Lichtkreis der Laterne auf.
    widths = {16: 4, 17: 5, 18: 6, 19: 7}
    for y, w in widths.items():
        off = (y * 3) % w
        for x in range(80):
            if s.ch[y, x] != SPACE or s.bg[y, x] != BLACK:
                continue
            s.cell(x, y, "▐" if (x + off) % w == w - 1 else "█", DGRAY)


def cottage(L):
    # Hafenmeisterhaus links, vom Bildrand angeschnitten
    L.d.polygon([(0, py(2, 1)), (9, py(2, 1)), (21, py(6, 1)), (0, py(6, 1))], fill=BLUE)   # Dach
    L.d.line([(9, py(2, 1)), (21, py(6, 1))], fill=DGRAY)
    L.d.rectangle([0, py(7), 19, py(QUAY, 1)], fill=BROWN)                                # Wand
    L.d.rectangle([19, py(7), 19, py(QUAY, 1)], fill=BLACK)
    L.d.rectangle([12, py(1), 14, py(3)], fill=DGRAY)                                      # Schornstein
    L.d.rectangle([12, py(1), 14, py(1)], fill=LGRAY)
    # Fenster mit Sprossen und Läden
    L.d.rectangle([4, py(8), 8, py(10, 1)], fill=YELLOW)
    L.d.rectangle([6, py(8), 6, py(10, 1)], fill=BROWN)
    L.d.rectangle([4, py(9, 1), 8, py(9, 1)], fill=BROWN)
    L.d.rectangle([3, py(8), 3, py(10, 1)], fill=RED)
    L.d.rectangle([9, py(8), 9, py(10, 1)], fill=RED)
    L.d.rectangle([3, py(11), 9, py(11)], fill=LGRAY)                                      # Sims
    # Tür
    L.d.rectangle([13, py(9), 17, py(QUAY, 1)], fill=BLACK)
    L.d.rectangle([14, py(9, 1), 16, py(QUAY, 1)], fill=BROWN)
    return (13, 0)


def cottage_glyphs(s):
    for y in range(3, 7):                       # Schiefer
        for x in range(0, 21):
            if s.ch[y, x] == SPACE and s.bg[y, x] == BLUE:
                s.cell(x, y, "░", BLACK)
    rng = random.Random(12)
    for y in range(7, QUAY + 1):                # Bruchsteinmauer: Fugen mit wechselnder Steinlänge
        x = -rng.randrange(0, 4)
        joints = set()
        while x < 19:
            x += rng.choice((3, 4, 4, 5))
            joints.add(x)
        for x in range(0, 19):
            if s.ch[y, x] == SPACE and s.bg[y, x] == BROWN:
                s.cell(x, y, "┴" if x in joints else "─", BLACK)
    s.cell(16, 12, "·", YELLOW)


CRATES = [(71, 16), (73, 16), (72, 14)]
LANTERN = (45, 12)       # Lampenzelle; Pfahl darunter bis Zeile 17
PARCEL = (46, 18)


def props(s):
    for x, y in CRATES:
        s.cell(x, y, "┌", BLACK, BROWN); s.cell(x + 1, y, "┐", BLACK, BROWN)
        s.cell(x, y + 1, "└", BLACK, BROWN); s.cell(x + 1, y + 1, "┘", BLACK, BROWN)
    s.cell(66, 16, "@", BROWN)
    s.cell(67, 16, "~", BROWN)
    lx, ly = LANTERN
    s.cell(lx, ly - 1, "▄", DGRAY)
    s.cell(lx, ly, "☼", YELLOW, BLACK)
    for y in range(ly + 1, 18):
        s.cell(lx, y, "║", BLACK if y < QUAY else DGRAY)
    s.cell(lx, 18, "╨", DGRAY)


def parcel(s):
    px_, py_ = PARCEL
    s.cell(px_, py_, "▐", BROWN, BLACK)
    s.cell(px_ + 1, py_, "╪", YELLOW, BROWN)
    s.cell(px_ + 2, py_, "▌", BROWN, BLACK)
    return [(px_ + i, py_) for i in range(3)]


POOL_LIT, POOL_EDGE = 6.0, 8.0     # Lichtkreis: hell bis POOL_LIT, Übergang (▓) bis POOL_EDGE


def lantern_light(s):
    # Lichtkreis der Laterne auf den Platten (Abstand in Zellen, waagerecht gestaucht)
    lx, ly = LANTERN
    pool = []
    for y in range(QUAY + 1, PIC_BOTTOM + 1):
        for x in range(80):
            d = ((x - lx + 3) / 2.0) ** 2 + ((y - 17.5) * 2.6) ** 2
            d = d ** 0.5
            if s.ch[y, x] in (FULL, RIGHT) and s.fg[y, x] == DGRAY and d < POOL_EDGE + 1:
                pool.append((x, y, round(d, 2)))
                if d < POOL_LIT:
                    s.cell(x, y, None, LGRAY)
                elif d < POOL_EDGE and s.ch[y, x] == FULL:
                    s.cell(x, y, "▓", LGRAY, BLACK)
    return pool


SEA_CHARS = set(CODE[c] for c in " ~≈-═─=")


def build():
    s = Screen()
    sky(s)
    st = stars(s)
    sky_only = s.copy()                        # Himmel ohne Gegenstände: Maske für Strahl, Rauch, Möwe
    sea(s)
    mid = Layer()
    hill_west(mid)
    headland(mid)
    lighthouse(mid)
    boat(mid)
    jetty(mid)
    mid.stamp(s)
    hill_glyphs(s)
    headland_glyphs(s)
    lamp = lighthouse_glyphs(s)
    boat_glyphs(s)
    q = Layer()
    quay(s, q)
    q.stamp(s)
    quay_glyphs(s)
    front = Layer()
    chim = cottage(front)
    front.stamp(s)
    cottage_glyphs(s)
    props(s)
    pool = lantern_light(s)
    tmp = s.copy()
    parcel_cells = parcel(tmp)                 # Paket ist ein Gegenstand: zeichnet die Demo, nicht das Bild
    parcel_draw = [(x, y, int(tmp.ch[y, x]), int(tmp.attrs()[y, x])) for x, y in parcel_cells]
    meta = {
        "lamp": list(lamp), "lantern": list(LANTERN), "chimney": list(chim), "glow_x": GLOW_X,
        "stars": [[x, y] for x, y in st],
        "pool": [list(p) for p in pool],
        "parcel": [list(c) for c in parcel_draw],
        "waves": {str(y): {"pat": pat, "fg": fg} for y, (pat, fg) in WAVE_ROWS.items()},
        "glow": {str(y): {"half": h, "pat": pat} for y, (h, pat) in GLOW.items()},
        "sea": [[x, y] for y in range(HORIZON, QUAY) for x in range(80)
                if s.bg[y, x] == BLUE and s.ch[y, x] in SEA_CHARS],
        "sky": [[x, y] for y in range(PIC_TOP, 6) for x in range(80)
                if s.ch[y, x] == sky_only.ch[y, x] and s.attrs()[y, x] == sky_only.attrs()[y, x]],
    }
    return s, meta


def main():
    s, meta = build()
    if s.conflicts:
        print("WARNUNG: Farbkonflikte (zwei helle Farben in einer Zelle):", s.conflict_cells)
    ans = ROOT / "assets" / "hafen.ans"
    write_ans(s, ans, rows=range(PIC_TOP, PIC_BOTTOM + 1), title="Hafen von Lornholm", group="spielgrafik")
    back = read_ans(ans, PIC_BOTTOM - PIC_TOP + 1)
    n = PIC_BOTTOM - PIC_TOP + 1
    same = ((back.ch[:n] == s.ch[PIC_TOP:PIC_BOTTOM + 1]).all() and (back.attrs()[:n] == s.attrs()[PIC_TOP:PIC_BOTTOM + 1]).all())
    if not same:
        sys.exit("hafen.ans weicht nach dem Zurücklesen ab")
    data = {"cols": 80, "rows": 25, "pic_top": PIC_TOP, "pic_rows": n,
            "chars": back.ch[:n].flatten().tolist(), "attrs": back.attrs()[:n].flatten().tolist(), **meta}
    out = ROOT / "demo" / "data"
    out.mkdir(parents=True, exist_ok=True)
    (out / "scene.json").write_text(json.dumps(data, separators=(",", ":")))
    full = Screen()
    full.ch[PIC_TOP:PIC_BOTTOM + 1], full.fg[PIC_TOP:PIC_BOTTOM + 1] = back.ch[:n], back.fg[:n]
    full.bg[PIC_TOP:PIC_BOTTOM + 1], full.blink[PIC_TOP:PIC_BOTTOM + 1] = back.bg[:n], back.blink[:n]
    full.render(scale=2).save(ROOT / "assets" / "hafen_preview.png")
    print(f"hafen.ans {ans.stat().st_size} Bytes, zurückgelesen identisch; scene.json; "
          f"{len(meta['sea'])} Meereszellen, {len(meta['sky'])} Himmelszellen, Konflikte {s.conflicts}")


if __name__ == "__main__":
    main()
