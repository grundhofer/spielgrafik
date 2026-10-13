"""Grobe Blockschrift 3x5 für das Textband (eigene Zeichnung, CC0).

Nur Großbuchstaben (Blockschrift), Ziffern, Satzzeichen, Ä/Ö/Ü mit Punkten in der Zeile über dem Zeichen
(Großbuchstaben bleiben dabei volle 5 Zeilen hoch), ß wird als SS geschrieben. Die meisten Zeichen sind 3 Pixel
breit, M und W 5, N 4 (in 3 Pixeln nicht lesbar); Vorschub = Breite + 1, Zeilenabstand 7.
Auf dem Bildschirm ist jedes Pixel doppelt so breit wie hoch; ein Zeichen wirkt dadurch etwa 6x5.
"""
GLYPHS = {
    "A": ".#.|#.#|###|#.#|#.#", "B": "##.|#.#|##.|#.#|##.", "C": ".##|#..|#..|#..|.##",
    "D": "##.|#.#|#.#|#.#|##.", "E": "###|#..|##.|#..|###", "F": "###|#..|##.|#..|#..",
    "G": ".##|#..|#.#|#.#|.##", "H": "#.#|#.#|###|#.#|#.#", "I": "###|.#.|.#.|.#.|###",
    "J": "..#|..#|..#|#.#|.#.", "K": "#.#|#.#|##.|#.#|#.#", "L": "#..|#..|#..|#..|###",
    "M": "#...#|##.##|#.#.#|#...#|#...#", "N": "#..#|##.#|#.##|#..#|#..#", "O": ".#.|#.#|#.#|#.#|.#.",
    "P": "##.|#.#|##.|#..|#..", "Q": ".#.|#.#|#.#|##.|.##", "R": "##.|#.#|##.|#.#|#.#",
    "S": ".##|#..|.#.|..#|##.", "T": "###|.#.|.#.|.#.|.#.", "U": "#.#|#.#|#.#|#.#|###",
    "V": "#.#|#.#|#.#|#.#|.#.", "W": "#...#|#...#|#.#.#|##.##|#...#", "X": "#.#|#.#|.#.|#.#|#.#",
    "Y": "#.#|#.#|.#.|.#.|.#.", "Z": "###|..#|.#.|#..|###",
    "0": "###|#.#|#.#|#.#|###", "1": ".#.|##.|.#.|.#.|###", "2": "##.|..#|.#.|#..|###",
    "3": "##.|..#|.#.|..#|##.", "4": "#.#|#.#|###|..#|..#", "5": "###|#..|##.|..#|##.",
    "6": ".##|#..|###|#.#|###", "7": "###|..#|.#.|.#.|.#.", "8": "###|#.#|###|#.#|###",
    "9": "###|#.#|###|..#|##.",
    ".": "...|...|...|...|.#.", ",": "...|...|...|.#.|#..", "!": ".#.|.#.|.#.|...|.#.",
    "?": "##.|..#|.#.|...|.#.", ":": "...|.#.|...|.#.|...", "-": "...|...|###|...|...",
    ">": "#..|.#.|..#|.#.|#..", "'": ".#.|.#.|...|...|...", '"': "#.#|#.#|...|...|...",
    "(": ".#.|#..|#..|#..|.#.", ")": ".#.|..#|..#|..#|.#.", "/": "..#|..#|.#.|#..|#..",
    " ": "...|...|...|...|...", "_": "###|###|###|###|###",   # _ = Eingabemarke (Block)
    "*": "#..|##.|###|##.|#..",                               # * = Auswahlpfeil
}
UMLAUT = {"Ä": "A", "Ö": "O", "Ü": "U"}


def glyph(ch):
    """Breite und 6 Zeilen als Bitmuster (linkes Pixel = höchstes Bit): Zeile 0 = Punkte, 1-5 = Zeichen."""
    base = UMLAUT.get(ch, ch)
    parts = GLYPHS[base].split("|")
    w = len(parts[0])
    rows = [int(r.replace("#", "1").replace(".", "0"), 2) for r in parts]
    return {"w": w, "rows": [0b101 if ch in UMLAUT else 0] + rows}


FONT_JSON = {ch: glyph(ch) for ch in list(GLYPHS) + list(UMLAUT)}


def text_width(text):
    return sum(FONT_JSON.get(ch, FONT_JSON["?"])["w"] + 1 for ch in prepare(text)) - 1


def prepare(text):
    return text.upper().replace("ß", "SS")


def render_rows(lines, y0, x0=8, pitch=7):
    """Vorschau: Zeilen -> {Bildzeile: 160 Bits}. Zeichenoberkante (Punkte) in Zeile y0 + 7k."""
    out = {}
    for k, line in enumerate(lines):
        rows = [[0] * 160 for _ in range(6)]
        x = x0
        for ch in prepare(line):
            g = FONT_JSON.get(ch, FONT_JSON["?"])
            for r in range(6):
                for b in range(g["w"]):
                    if x + b < 160 and (g["rows"][r] >> (g["w"] - 1 - b)) & 1:
                        rows[r][x + b] = 1
            x += g["w"] + 1
        for r in range(6):
            yy = y0 + pitch * k + r
            if yy < 192:
                out[yy] = rows[r]
    return out
