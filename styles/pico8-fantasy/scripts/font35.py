#!/usr/bin/env python3
"""Eigene 3x5-Blockschrift im Raster einer Fantasy-Konsole (4x6-Zelle: 3 px Zeichen + 1 px Abstand,
5 px Zeile + 1 px Abstand). Eigene Zeichnung für diesen Eintrag, CC0.

Wie auf der Konsole gibt es nur eine Buchstabenform: Kleinbuchstaben werden als Großbuchstaben gezeichnet.
Ä/Ö/Ü tragen die Punkte in der Leerzeile darüber (Zeile -1), ß ist ein eigenes Zeichen mit offener Ecke
oben links, offener Unterkante und einer Unterlänge in der Leerzeile darunter (Zeile 5), damit es sich von B
unterscheidet. Sonderzeichen
(▶ ▼ █) dürfen breiter sein; der Vorschub ist Breite + 1.

Schreibt demo/cart/font35.json ({Zeichen: {"w": Breite, "top": oberste Zeile, "rows": [Bitmaske je Zeile]}})
und assets/font_preview.png (Vorschau ×6).

    ../../.venv/bin/python scripts/font35.py
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Zeichen: Liste der Zeilen ab Zeile 0 ("X" = gesetzt). Ein führendes "^" in der ersten Zeile heißt:
# diese Zeile liegt eine Zeile über dem Zeichen (Zeile -1, Umlautpunkte).
G = {
    "A": ["XXX", "X.X", "XXX", "X.X", "X.X"],
    "B": ["XX.", "X.X", "XX.", "X.X", "XXX"],
    "C": [".XX", "X..", "X..", "X..", ".XX"],
    "D": ["XX.", "X.X", "X.X", "X.X", "XX."],
    "E": ["XXX", "X..", "XX.", "X..", "XXX"],
    "F": ["XXX", "X..", "XX.", "X..", "X.."],
    "G": [".XX", "X..", "X.X", "X.X", ".XX"],
    "H": ["X.X", "X.X", "XXX", "X.X", "X.X"],
    "I": ["XXX", ".X.", ".X.", ".X.", "XXX"],
    "J": ["XXX", "..X", "..X", "X.X", ".X."],
    "K": ["X.X", "X.X", "XX.", "X.X", "X.X"],
    "L": ["X..", "X..", "X..", "X..", "XXX"],
    "M": ["X.X", "XXX", "XXX", "X.X", "X.X"],
    "N": ["XX.", "X.X", "X.X", "X.X", "X.X"],
    "O": [".X.", "X.X", "X.X", "X.X", ".X."],
    "P": ["XX.", "X.X", "XX.", "X..", "X.."],
    "Q": [".X.", "X.X", "X.X", "XX.", ".XX"],
    "R": ["XX.", "X.X", "XX.", "X.X", "X.X"],
    "S": [".XX", "X..", ".X.", "..X", "XX."],
    "T": ["XXX", ".X.", ".X.", ".X.", ".X."],
    "U": ["X.X", "X.X", "X.X", "X.X", "XXX"],
    "V": ["X.X", "X.X", "X.X", "X.X", ".X."],
    "W": ["X.X", "X.X", "XXX", "XXX", "X.X"],
    "X": ["X.X", "X.X", ".X.", "X.X", "X.X"],
    "Y": ["X.X", "X.X", ".X.", ".X.", ".X."],
    "Z": ["XXX", "..X", ".X.", "X..", "XXX"],
    "Ä": ["^X.X", ".X.", "X.X", "XXX", "X.X", "X.X"],
    "Ö": ["^X.X", ".X.", "X.X", "X.X", "X.X", ".X."],
    "Ü": ["^X.X", "...", "X.X", "X.X", "X.X", "XXX"],
    "ß": [".XX", "X.X", "XX.", "X.X", "XX.", "X.."],
    "0": ["XXX", "X.X", "X.X", "X.X", "XXX"],
    "1": ["XX.", ".X.", ".X.", ".X.", "XXX"],
    "2": ["XX.", "..X", ".X.", "X..", "XXX"],
    "3": ["XX.", "..X", ".X.", "..X", "XX."],
    "4": ["X.X", "X.X", "XXX", "..X", "..X"],
    "5": ["XXX", "X..", "XX.", "..X", "XX."],
    "6": [".XX", "X..", "XXX", "X.X", "XXX"],
    "7": ["XXX", "..X", ".X.", ".X.", ".X."],
    "8": ["XXX", "X.X", "XXX", "X.X", "XXX"],
    "9": ["XXX", "X.X", "XXX", "..X", "XX."],
    " ": ["...", "...", "...", "...", "..."],
    ".": ["...", "...", "...", "...", ".X."],
    ",": ["...", "...", "...", ".X.", "X.."],
    "!": [".X.", ".X.", ".X.", "...", ".X."],
    "?": ["XX.", "..X", ".X.", "...", ".X."],
    ":": ["...", ".X.", "...", ".X.", "..."],
    ";": ["...", ".X.", "...", ".X.", "X.."],
    "-": ["...", "...", "XXX", "...", "..."],
    "+": ["...", ".X.", "XXX", ".X.", "..."],
    "=": ["...", "XXX", "...", "XXX", "..."],
    "'": [".X.", ".X.", "...", "...", "..."],
    '"': ["X.X", "X.X", "...", "...", "..."],
    "(": [".X.", "X..", "X..", "X..", ".X."],
    ")": [".X.", "..X", "..X", "..X", ".X."],
    "/": ["..X", "..X", ".X.", "X..", "X.."],
    ">": ["X..", ".X.", "..X", ".X.", "X.."],
    "<": ["..X", ".X.", "X..", ".X.", "..X"],
    "_": ["...", "...", "...", "...", "XXX"],
    "▶": ["X..", "XX.", "XXX", "XX.", "X.."],
    "▼": ["XXXXX", ".XXX.", "..X..", ".....", "....."],
    "█": ["XXX", "XXX", "XXX", "XXX", "XXX"],
}


def build():
    font = {}
    for ch, rows in G.items():
        top = 0
        if rows[0].startswith("^"):
            rows = [rows[0][1:]] + rows[1:]
            top = -1
        w = max(len(r) for r in rows)
        masks = []
        for r in rows:
            m = 0
            for i, c in enumerate(r):
                if c == "X":
                    m |= 1 << i
            masks.append(m)
        font[ch] = {"w": w, "top": top, "rows": masks}
    return font


def preview(font, path):
    from PIL import Image
    text = ["ABCDEFGHIJKLMNOPQRSTUVWXYZ", "ÄÖÜß 0123456789 .,!?:;-+='\"()/<>_", "▶ ZUM LEUCHTTURM GEHEN ▼ █",
            "DIE LATERNE FLACKERT IM WIND.", "Grüße aus Lornholm? Öl, Ärger,", "über. B ß Bß GRÜBE GRÜßE"]

    def width(line):
        return sum(font.get(ch if ch in font else ch.upper(), font["?"])["w"] + 1 for ch in line) - 1

    W, H = max(width(t) for t in text) + 4, 7 * len(text) + 4
    im = Image.new("RGB", (W, H), (0, 0, 0))
    px = im.load()
    y = 2
    for line in text:
        x = 2
        for ch in line:
            ch = ch if ch in font else ch.upper()
            g = font.get(ch, font["?"])
            for ry, m in enumerate(g["rows"]):
                for rx in range(g["w"]):
                    if m >> rx & 1:
                        yy = y + g["top"] + ry
                        if 0 <= x + rx < W and 0 <= yy < H:
                            px[x + rx, yy] = (255, 241, 232)
            x += g["w"] + 1
        y += 7
    im.resize((W * 6, H * 6), Image.NEAREST).save(path)


if __name__ == "__main__":
    f = build()
    out = ROOT / "demo" / "cart" / "font35.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(f, ensure_ascii=False, separators=(",", ":")))
    preview(f, ROOT / "assets" / "font_preview.png")
    print(f"{len(f)} Zeichen -> {out}")
