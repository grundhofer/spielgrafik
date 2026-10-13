"""Eigener Zeichensatz font57, Fassung 2: 7×8-Zellen (Großbuchstaben, Ziffern, Satzzeichen, Ä Ö Ü) für den Text.

    .venv/bin/python styles/apple2-hires/scripts/font57.py
    # schreibt demo/data/font.json (8 Bytes je Zeichen) und assets/font_preview.png (fringe, crisp, ideal, 1 Bit)

Jede Zelle ist genau ein Byte breit (7 Bildpunkte), Zeile 7 bleibt frei. Ein Byte je Zeile, Bit 0 = linker
Bildpunkt – also direkt das Format der Bildschirmzeile. Die Glyphen stehen unten als Text in den Spalten 1–5
der Zelle (CC0).

Fassung 1 war ein 5×7-Satz im Raster des Zeichengenerators und lag zu nah an dessen Formen: Ein Abgleich gegen
eine 5×7-Nachbildung der Apple-II-Schrift ergab 21 von 44 Zeichen pixelgleich (B C D E F H J L O P T U Y Z 2 4 5 8
! - >). Sie ist verworfen; diese Fassung ist neu gezeichnet und anders gebaut:

  * Schmal: die meisten Zeichen 4 Punkte breit (Spalten 1–4) mit 2 Punkten Innenraum und 3 Punkten Abstand;
    nur die Diagonal-Buchstaben M, N, V, W und Y 5 Punkte (M und N liefen 4 Punkte breit im Farbmodell ganz
    zu), I und T 1 bzw. 3 Punkte. Das Vorbild ist 5 Punkte breit mit 3 Punkten Innenraum.
  * Senkrechte Striche 1 Punkt breit (werden im Farbmodell farbig), waagerechte durchgehend (werden weiß).
    Ein Innenraum von 2 Punkten bleibt im Farbmodell schwarz; Zeilen der Form X.X (eine Lücke zwischen zwei
    gesetzten Punkten wird zur Farbfläche) bleiben nur bei G, K, M, N, R, V, W, 0 und 1.
  * Eigene Formen: A mit flachem Dach, I ohne Serifen, J mit Kopf, M mit breiten Schultern, X mit
    2 Punkte breiter Mitte, Y mit Querbalken, 4 oben offen, Satzzeichen . , : ! > aus 2 Punkte breiten Strichen.
  * Ä Ö Ü mit Punkten in Zeile 0 über einem 6 Zeilen hohen Körper.

Prüfung (nur lokal, die Vergleichsschrift ist nicht Teil des Eintrags): Abstand je Zeichen als Anzahl
abweichender Punkte, kleinster Wert über Verschiebungen um ±1 Zeile/Spalte: 0 von 36 Buchstaben und Ziffern
pixelgleich (Fassung 1: 18), Median 7. Nahe bleiben nur L (1), T (2), Bindestrich (1) und Komma (2).
"""
import json, pathlib
import numpy as np

ENTRY = pathlib.Path(__file__).resolve().parent.parent

G = {
    " ": [".....", ".....", ".....", ".....", ".....", ".....", "....."],
    "A": [".XX..", "X..X.", "X..X.", "XXXX.", "X..X.", "X..X.", "X..X."],
    "B": ["XXX..", "X..X.", "X..X.", "XXX..", "X..X.", "X..X.", "XXX.."],
    "C": [".XX..", "X..X.", "X....", "X....", "X....", "X..X.", ".XX.."],
    "D": ["XXX..", "X..X.", "X..X.", "X..X.", "X..X.", "X..X.", "XXX.."],
    "E": ["XXXX.", "X....", "X....", "XX...", "X....", "X....", "XXXX."],
    "F": ["XXXX.", "X....", "X....", "XX...", "X....", "X....", "X...."],
    "G": [".XXX.", "X....", "X....", "X.XX.", "X..X.", "X..X.", ".XXX."],
    "H": ["X..X.", "X..X.", "X..X.", "XXXX.", "X..X.", "X..X.", "X..X."],
    "I": [".X...", ".X...", ".X...", ".X...", ".X...", ".X...", ".X..."],
    "J": ["..XX.", "...X.", "...X.", "...X.", "...X.", "X..X.", ".XX.."],
    "K": ["X..X.", "X..X.", "X.X..", "XX...", "X.X..", "X..X.", "X..X."],
    "L": ["X....", "X....", "X....", "X....", "X....", "X....", "XXXX."],
    "M": ["X...X", "XX.XX", "XX.XX", "X.X.X", "X...X", "X...X", "X...X"],
    "N": ["X...X", "XX..X", "X.X.X", "X.X.X", "X..XX", "X...X", "X...X"],
    "O": [".XX..", "X..X.", "X..X.", "X..X.", "X..X.", "X..X.", ".XX.."],
    "P": ["XXX..", "X..X.", "X..X.", "XXX..", "X....", "X....", "X...."],
    "Q": [".XX..", "X..X.", "X..X.", "X..X.", "X..X.", ".XX..", "..XX."],
    "R": ["XXX..", "X..X.", "X..X.", "XXX..", "X.X..", "X..X.", "X..X."],
    "S": [".XXX.", "X....", "X....", ".XX..", "...X.", "...X.", "XXX.."],
    "T": ["XXX..", ".X...", ".X...", ".X...", ".X...", ".X...", ".X..."],
    "U": ["X..X.", "X..X.", "X..X.", "X..X.", "X..X.", "X..X.", ".XX.."],
    "V": ["X...X", "X...X", ".X.X.", ".X.X.", ".X.X.", "..X..", "..X.."],
    "W": ["X...X", "X...X", "X...X", "X...X", "X.X.X", "X.X.X", ".X.X."],
    "X": ["X..X.", "X..X.", ".XX..", ".XX..", ".XX..", "X..X.", "X..X."],
    "Y": ["X...X", "X...X", "X...X", ".XXX.", "..X..", "..X..", "..X.."],
    "Z": ["XXXX.", "...X.", "..X..", "..X..", ".X...", "X....", "XXXX."],
    "Ä": ["X..X.", ".XX..", "X..X.", "XXXX.", "X..X.", "X..X.", "X..X."],
    "Ö": ["X..X.", ".XX..", "X..X.", "X..X.", "X..X.", "X..X.", ".XX.."],
    "Ü": ["X..X.", ".....", "X..X.", "X..X.", "X..X.", "X..X.", ".XX.."],
    "0": [".XX..", "X..X.", "X..X.", "X.XX.", "XX.X.", "X..X.", ".XX.."],
    "1": [".XX..", "X.X..", "..X..", "..X..", "..X..", "..X..", "..X.."],
    "2": [".XX..", "X..X.", "...X.", "..X..", ".X...", "X....", "XXXX."],
    "3": ["XXX..", "...X.", "...X.", ".XX..", "...X.", "...X.", "XXX.."],
    "4": ["X..X.", "X..X.", "X..X.", "XXXX.", "...X.", "...X.", "...X."],
    "5": ["XXXX.", "X....", "XXX..", "...X.", "...X.", "X..X.", ".XX.."],
    "6": [".XX..", "X....", "X....", "XXX..", "X..X.", "X..X.", ".XX.."],
    "7": ["XXXX.", "...X.", "...X.", "..X..", "..X..", ".X...", ".X..."],
    "8": [".XX..", "X..X.", "X..X.", ".XX..", "X..X.", "X..X.", ".XX.."],
    "9": [".XX..", "X..X.", "X..X.", ".XXX.", "...X.", "...X.", ".XX.."],
    ".": [".....", ".....", ".....", ".....", ".....", ".XX..", ".XX.."],
    ",": [".....", ".....", ".....", ".....", ".XX..", ".XX..", "X...."],
    ":": [".....", ".XX..", ".XX..", ".....", ".XX..", ".XX..", "....."],
    "!": [".XX..", ".XX..", ".XX..", ".XX..", ".....", ".XX..", ".XX.."],
    "?": [".XX..", "X..X.", "...X.", "..X..", ".X...", ".....", ".X..."],
    "-": [".....", ".....", ".....", "XXXX.", ".....", ".....", "....."],
    ">": [".....", "XX...", ".XX..", "..XX.", ".XX..", "XX...", "....."],
    "'": [".XX..", "..X..", ".X...", ".....", ".....", ".....", "....."],
}


def glyph_bytes(ch):
    """8 Bytes (Zeilen) einer Zelle; Bit k = Bildpunkt k, Glyphe in Spalten 1–5."""
    rows = G[ch]
    out = []
    for r in range(8):
        v = 0
        if r < 7:
            for k, c in enumerate(rows[r]):
                if c == "X":
                    v |= 1 << (k + 1)
        out.append(v)
    return out


def table():
    return {ch: glyph_bytes(ch) for ch in G}


def main():
    from PIL import Image
    from a2lib import render
    text = ["ABCDEFGHIJKLMNOPQRSTUVWXYZ ÄÖÜ",
            "0123456789 .,:!?->'",
            "HAFEN VON LORNHOLM. DIE LATERNE FLACKERT",
            "IM WIND. AM KAI WARTET EIN PAKET AUF",
            ">NIMM PAKET"]
    mem = np.zeros((8 * len(text), 40), np.uint8)
    for li, line in enumerate(text):
        for ci, ch in enumerate(line[:40]):
            for r, v in enumerate(glyph_bytes(ch)):
                mem[8 * li + r, ci] = v
    imgs = []
    for model in ("fringe", "crisp", "ideal"):
        imgs.append(render(mem, model))
        imgs.append(np.zeros((4, 280, 3), np.uint8))
    mono = np.zeros((mem.shape[0], 280), np.uint8)
    for k in range(7):
        mono[:, k::7] = (mem >> k) & 1
    imgs.append(np.repeat(mono[..., None] * 255, 3, 2).astype(np.uint8))
    img = np.vstack(imgs)
    Image.fromarray(np.repeat(np.repeat(img, 3, 0), 3, 1)).save(ENTRY / "assets" / "font_preview.png")
    (ENTRY / "demo" / "data" / "font.json").write_text(json.dumps({"glyphs": table()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
