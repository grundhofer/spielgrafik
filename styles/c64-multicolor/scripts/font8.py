"""Zeichensatz „font8“ für den Textbereich (Fassung 2, eigener Entwurf, CC0).

Fassung 1 dieses Eintrags war entgegen ihrer Beschreibung weitgehend der Zeichensatz-ROM des Rechners: Ein
Abgleich gegen einen ROM-Abzug ergab 47 von 75 Zeichen pixelgleich. Sie ist verworfen; diese Fassung ist neu
gezeichnet und nach eigenen Regeln gebaut, die bewusst vom ROM abweichen:

  * Breite 7 px (Spalten 0-6), 1 px Abstand (Spalte 7); der ROM-Satz ist 6 px breit mit 2 px Abstand.
  * Senkrechte Striche 2 px, waagerechte 1 px, Innenräume 3 px (ROM: 2 px); Mittelstämme von T, I, Y, X, V 3 px,
    damit sie in 7 px mittig stehen.
  * Querbalken von A tiefer (Zeile 4), A mit breiter Spitze, M mit zwei Bögen, l/i/t mit Fuß nach rechts statt
    Serifen, r mit Bogen, m mit flachem Dach, w mit Mittelstamm, c/s mit geraden Enden, Ü mit Punkten im Innenraum.
  * Großbuchstaben und Ziffern 7 Zeilen (0-6), Kleinbuchstaben 5 Zeilen (2-6), Oberlängen ab Zeile 0,
    Unterlängen in Zeile 6-7.

Prüfung gegen den ROM-Abzug (Vergleich nur lokal, der ROM ist nicht Teil des Eintrags): Abstand je Zeichen als
Anzahl abweichender Pixel, kleinster Wert über alle Verschiebungen um ±1 Zeile/Spalte: 0 von 62 Buchstaben und
Ziffern pixelgleich (Fassung 1: 39), Median 9. Zwangsläufig ähnlich bleiben nur Formen ohne Spielraum (L 1 px,
F 3 px, Leerzeichen, Punkt, Komma, Bindestrich).

Umlaute liegen wie in deutschen 7-Bit-Zeichensätzen auf [ \\ ] { | } ~ (Ä Ö Ü ä ö ü ß).
Codes 128-255 sind die invertierten Zeichen 0-127 (Revers-Darstellung, z. B. Cursorblock = 128 + Leerzeichen).

charset() -> bytes (256 Zeichen x 8 Bytes, Bit 7 = linkes Pixel)
code(ch)  -> Bildschirmcode eines Zeichens
"""
G = {}


def _g(ch, text):
    rows = [r.strip() for r in text.strip("\n").split("\n") if r.strip()]
    rows = [r.ljust(8, ".") for r in rows]
    rows += ["........"] * (8 - len(rows))
    assert len(rows) == 8 and all(len(r) == 8 and r[7] == "." for r in rows), ch
    G[ch] = rows


_g("A", """
..###..
.##.##.
##...##
##...##
#######
##...##
##...##""")
_g("B", """
######.
##...##
##...##
######.
##...##
##...##
######.""")
_g("C", """
.#####.
##...##
##.....
##.....
##.....
##...##
.#####.""")
_g("D", """
#####..
##..##.
##...##
##...##
##...##
##..##.
#####..""")
_g("E", """
#######
##.....
##.....
######.
##.....
##.....
#######""")
_g("F", """
#######
##.....
##.....
######.
##.....
##.....
##.....""")
_g("G", """
.#####.
##...##
##.....
##.####
##...##
##...##
.#####.""")
_g("H", """
##...##
##...##
##...##
#######
##...##
##...##
##...##""")
_g("I", """
.#####.
..###..
..###..
..###..
..###..
..###..
.#####.""")
_g("J", """
....###
.....##
.....##
.....##
.....##
##...##
.#####.""")
_g("K", """
##...##
##..##.
##.##..
####...
##.##..
##..##.
##...##""")
_g("L", """
##.....
##.....
##.....
##.....
##.....
##.....
#######""")
_g("M", """
.##.##.
##.#.##
##.#.##
##.#.##
##...##
##...##
##...##""")
_g("N", """
##...##
###..##
####.##
##.####
##..###
##...##
##...##""")
_g("O", """
.#####.
##...##
##...##
##...##
##...##
##...##
.#####.""")
_g("P", """
######.
##...##
##...##
######.
##.....
##.....
##.....""")
_g("Q", """
.#####.
##...##
##...##
##...##
##.#.##
##..##.
.###.##""")
_g("R", """
######.
##...##
##...##
######.
##..##.
##...##
##...##""")
_g("S", """
.#####.
##...##
##.....
.#####.
.....##
##...##
.#####.""")
_g("T", """
#######
..###..
..###..
..###..
..###..
..###..
..###..""")
_g("U", """
##...##
##...##
##...##
##...##
##...##
##...##
.#####.""")
_g("V", """
##...##
##...##
##...##
##...##
.##.##.
.##.##.
..###..""")
_g("W", """
##...##
##...##
##...##
##.#.##
##.#.##
#######
.##.##.""")
_g("X", """
##...##
##...##
.##.##.
..###..
.##.##.
##...##
##...##""")
_g("Y", """
##...##
##...##
.##.##.
..###..
..###..
..###..
..###..""")
_g("Z", """
#######
.....##
....##.
..###..
.##....
##.....
#######""")
_g("a", """
.......
.......
.#####.
.....##
.######
##...##
.######""")
_g("b", """
##.....
##.....
######.
##...##
##...##
##...##
######.""")
_g("c", """
.......
.......
.######
##.....
##.....
##.....
.######""")
_g("d", """
.....##
.....##
.######
##...##
##...##
##...##
.######""")
_g("e", """
.......
.......
.#####.
##...##
#######
##.....
.#####.""")
_g("f", """
...####
..##...
######.
..##...
..##...
..##...
..##...""")
_g("g", """
.......
.......
.######
##...##
##...##
.######
.....##
######.""")
_g("h", """
##.....
##.....
######.
##...##
##...##
##...##
##...##""")
_g("i", """
..##...
.......
.###...
..##...
..##...
..##...
..####.""")
_g("j", """
....##.
.......
...###.
....##.
....##.
....##.
##..##.
.####..""")
_g("k", """
##.....
##.....
##...##
##..##.
#####..
##..##.
##...##""")
_g("l", """
.###...
..##...
..##...
..##...
..##...
..##...
...###.""")
_g("m", """
.......
.......
######.
##.#.##
##.#.##
##.#.##
##.#.##""")
_g("n", """
.......
.......
######.
##...##
##...##
##...##
##...##""")
_g("o", """
.......
.......
.#####.
##...##
##...##
##...##
.#####.""")
_g("p", """
.......
.......
######.
##...##
##...##
######.
##.....
##.....""")
_g("q", """
.......
.......
.######
##...##
##...##
.######
.....##
.....##""")
_g("r", """
.......
.......
##.###.
###..##
##.....
##.....
##.....""")
_g("s", """
.......
.......
.######
##.....
.#####.
.....##
######.""")
_g("t", """
.##....
.##....
######.
.##....
.##....
.##....
..####.""")
_g("u", """
.......
.......
##...##
##...##
##...##
##...##
.######""")
_g("v", """
.......
.......
##...##
##...##
##...##
.##.##.
..###..""")
_g("w", """
.......
.......
##...##
##.#.##
##.#.##
##.#.##
.##.##.""")
_g("x", """
.......
.......
##...##
.##.##.
..###..
.##.##.
##...##""")
_g("y", """
.......
.......
##...##
##...##
##...##
.######
.....##
######.""")
_g("z", """
.......
.......
#######
....##.
..###..
.##....
#######""")
_g("0", """
.#####.
##...##
##..###
##.#.##
###..##
##...##
.#####.""")
_g("1", """
..###..
.####..
...##..
...##..
...##..
...##..
.######""")
_g("2", """
.#####.
##...##
.....##
..####.
.##....
##.....
#######""")
_g("3", """
.#####.
##...##
.....##
..####.
.....##
##...##
.#####.""")
_g("4", """
....###
...####
..##.##
.##..##
#######
.....##
.....##""")
_g("5", """
#######
##.....
######.
.....##
.....##
##...##
.#####.""")
_g("6", """
..####.
.##....
##.....
######.
##...##
##...##
.#####.""")
_g("7", """
#######
.....##
....##.
...##..
..##...
..##...
..##...""")
_g("8", """
.#####.
##...##
##...##
.#####.
##...##
##...##
.#####.""")
_g("9", """
.#####.
##...##
##...##
.######
.....##
....##.
.####..""")
_g(" ", "")
_g(".", """
.......
.......
.......
.......
.......
..##...
..##...""")
_g(",", """
.......
.......
.......
.......
.......
..##...
..##...
.##....""")
_g("!", """
..###..
..###..
..###..
..##...
..##...
.......
..##...""")
_g("?", """
.#####.
##...##
.....##
...###.
..##...
.......
..##...""")
_g(":", """
.......
..##...
..##...
.......
.......
..##...
..##...""")
_g("-", """
.......
.......
.......
.#####.
.......
.......
.......""")
_g(">", """
##.....
.##....
..##...
...##..
..##...
.##....
##.....""")
_g("'", """
..##...
..##...
.##....""")
_g("\"", """
##.##..
##.##..
.#..#..""")
_g("(", """
...###.
..##...
..##...
..##...
..##...
..##...
...###.""")
_g(")", """
.###...
...##..
...##..
...##..
...##..
...##..
.###...""")
_g("/", """
.....##
.....##
....##.
...##..
..##...
.##....
##.....""")
# Umlaute: Ä Ö mit 1-px-Punkten an den Ecken über einem 6 Zeilen hohen Körper; Ü mit Punkten im Innenraum
# (über den Stämmen würden sie mit ihnen verschmelzen); Kleinbuchstaben mit 2-px-Punkten und Leerzeile.
_g("[", """
#.....#
.#####.
##...##
##...##
#######
##...##
##...##""")
_g("\\", """
#.....#
.#####.
##...##
##...##
##...##
##...##
.#####.""")
_g("]", """
..#.#..
##...##
##...##
##...##
##...##
##...##
.#####.""")
_g("{", """
.##.##.
.......
.#####.
.....##
.######
##...##
.######""")
_g("|", """
.##.##.
.......
.#####.
##...##
##...##
##...##
.#####.""")
_g("}", """
.##.##.
.......
##...##
##...##
##...##
##...##
.######""")
_g("~", """
.####..
##..##.
##..##.
##.##..
##..##.
##...##
##.###.""")

UMLAUT = {"Ä": "[", "Ö": "\\", "Ü": "]", "ä": "{", "ö": "|", "ü": "}", "ß": "~"}


def code(ch):
    ch = UMLAUT.get(ch, ch)
    c = ord(ch)
    assert c < 128 and ch in G, f"Zeichen fehlt im Zeichensatz: {ch!r}"
    return c


def charset():
    out = bytearray(256 * 8)
    for ch, rows in G.items():
        c = ord(ch)
        for y, r in enumerate(rows):
            b = 0
            for x, px in enumerate(r):
                if px == "#":
                    b |= 0x80 >> x
            out[c * 8 + y] = b
            out[(c + 128) * 8 + y] = b ^ 0xFF
    for c in range(128):  # fehlende Codes: Revers als voller Block (128 + Leerzeichen gilt als Cursor)
        if chr(c) not in G:
            for y in range(8):
                out[(c + 128) * 8 + y] = 0xFF
    return bytes(out)


def preview(path, scale=3):
    """Vorschau wie im Textbereich: weiß auf Blau, 40 Spalten (assets/font_preview.png)."""
    from PIL import Image
    lines = ["ABCDEFGHIJKLMNOPQRSTUVWXYZ ÄÖÜ", "abcdefghijklmnopqrstuvwxyz äöüß", "0123456789 .,!?:-'\"()/>",
             "Hafen von Lornholm", "Die Laterne flackert im Wind. Am Kai", "wartet ein Paket auf dich.",
             "> nimm paket" + chr(0)]
    cs = charset()
    img = Image.new("RGB", (40 * 8, len(lines) * 8), (0x35, 0x28, 0x79))
    px = img.load()
    for row, text in enumerate(lines):
        for col, ch in enumerate(text[:40]):
            c = 128 + code(" ") if ch == chr(0) else code(ch)       # chr(0): Cursorblock (Revers-Leerzeichen)
            for y in range(8):
                for x in range(8):
                    if cs[c * 8 + y] & (0x80 >> x):
                        px[col * 8 + x, row * 8 + y] = (255, 255, 255)
    img.resize((img.width * scale, img.height * scale), Image.NEAREST).save(path)


if __name__ == "__main__":
    import pathlib
    out = pathlib.Path(__file__).resolve().parents[1] / "assets/font_preview.png"
    preview(out)
    print(out.name)
