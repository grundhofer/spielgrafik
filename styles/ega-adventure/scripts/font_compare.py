#!/usr/bin/env python3
"""Abgleich der Systemschrift (build_font.py) mit 8×8-Bitmapschriften im Windows-Format .FON.

Die Vergleichsschriften gehören nicht zum Eintrag und werden nicht mitgeliefert. Geprüft wurde Fassung 2 gegen den
Ordner „fon - Bm (windows bitmap)“ des Ultimate Oldschool PC Font Pack v2.2 (int10h.org, CC BY-SA 4.0):

    .venv/bin/python styles/ega-adventure/scripts/font_compare.py /pfad/zu/fon-ordner [Bm437_IBM_EGA_8x8 …]

Je Zeichen: abweichende Pixel als kleinster Wert über alle Verschiebungen um ±1 Zeile/Spalte (auf einer um 1 px
gepolsterten Fläche, damit am Rand nichts verloren geht; fängt verschobene Kopien). Zuordnung über Codepage 437
(auch Ä Ö Ü ä ö ü ß). Gezählt werden nur Schriften mit 8×8-Zellen; Dateien mit -2x/-2y (gestreckt) entfallen.
Ohne Schriftnamen: alle Schriften des Ordners, sortiert nach Anzahl pixelgleicher Zeichen.
"""
import importlib.util, pathlib, struct, sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent


def load_font():
    spec = importlib.util.spec_from_file_location("build_font_cmp", HERE / "build_font.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {ch: np.array([[1 if c == "#" else 0 for c in row] for row in rows], np.uint8)
            for ch, rows in mod.G.items() if ch != " "}


def fon_fonts(path):
    """Alle FNT-Ressourcen (Version 2/3) einer NE-Datei als {"w", "h", "glyphs": {code: array}}."""
    data = path.read_bytes()
    ne = struct.unpack_from("<I", data, 0x3C)[0]
    if data[ne:ne + 2] != b"NE":
        return []
    rt = ne + struct.unpack_from("<H", data, ne + 0x24)[0]
    shift = struct.unpack_from("<H", data, rt)[0]
    p, out = rt + 2, []
    while True:
        tid = struct.unpack_from("<H", data, p)[0]
        if tid == 0:
            break
        cnt = struct.unpack_from("<H", data, p + 2)[0]
        p += 8
        for _ in range(cnt):
            off, ln = struct.unpack_from("<HH", data, p)
            if tid == 0x8008:
                out.append(parse_fnt(data[off << shift:(off << shift) + (ln << shift)]))
            p += 12
    return out


def parse_fnt(f):
    ver = struct.unpack_from("<H", f, 0)[0]
    w, h = struct.unpack_from("<HH", f, 86)
    first, last = f[95], f[96]
    tbl = 118 if ver == 0x200 else 148
    glyphs = {}
    for i in range(last - first + 1):
        if ver == 0x200:
            gw, off = struct.unpack_from("<HH", f, tbl + 4 * i)
        else:
            gw, off = struct.unpack_from("<HI", f, tbl + 6 * i)
        nb = (gw + 7) // 8
        g = np.zeros((h, nb * 8), np.uint8)
        for bc in range(nb):
            for y in range(h):
                b = f[off + bc * h + y]
                for x in range(8):
                    g[y, bc * 8 + x] = (b >> (7 - x)) & 1
        glyphs[first + i] = g[:, :gw]
    return {"w": w, "h": h, "glyphs": glyphs}


def dist(m, r):
    """Kleinste Anzahl abweichender Pixel über Verschiebungen von m um dy, dx aus {-1, 0, 1}."""
    H, W = max(m.shape[0], r.shape[0]) + 2, max(m.shape[1], r.shape[1]) + 2
    R = np.zeros((H, W), np.uint8)
    R[1:1 + r.shape[0], 1:1 + r.shape[1]] = r
    best = None
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            M = np.zeros((H, W), np.uint8)
            M[1 + dy:1 + dy + m.shape[0], 1 + dx:1 + dx + m.shape[1]] = m
            d = int((M != R).sum())
            best = d if best is None else min(best, d)
    return best


def compare(G, font):
    res = {}
    for ch, m in G.items():
        try:
            code = ch.encode("cp437")[0]
        except UnicodeEncodeError:
            continue
        if code in font["glyphs"]:
            res[ch] = dist(m, font["glyphs"][code])
    return res


def main():
    fondir = pathlib.Path(sys.argv[1])
    names = sys.argv[2:]
    G = load_font()
    rows, per_glyph = [], {}
    for p in sorted(fondir.glob("*.FON")):
        if "-2x" in p.name or "-2y" in p.name or (names and p.stem not in names):
            continue
        for k, font in enumerate(fon_fonts(p)):
            if (font["w"], font["h"]) != (8, 8):
                continue
            name = p.stem if k == 0 else f"{p.stem} (Ressource {k + 1})"
            res = compare(G, font)
            for c, b in res.items():
                per_glyph[c] = min(per_glyph.get(c, b), b)
            ident = "".join(c for c, b in res.items() if b == 0)
            near = "".join(c for c, b in res.items() if 0 < b <= 2)
            alnum = sorted(b for c, b in res.items() if c.isalnum())
            rows.append((len(ident), name, len(res), ident, near, alnum[len(alnum) // 2] if alnum else None))
    rows.sort(key=lambda r: (-r[0], r[1]))
    print(f"{len(rows)} Schriften mit 8×8-Zellen verglichen")
    for n, name, cnt, ident, near, med in rows[:25]:
        print(f"{name}: {cnt} Zeichen, pixelgleich {n} ({ident or '-'}), 1–2 px: {near or '-'}, "
              f"Median Buchstaben/Ziffern {med}")
    alnum = {c: b for c, b in per_glyph.items() if c.isalnum()}
    print("Buchstaben/Ziffern pixelgleich mit irgendeiner Schrift:",
          "".join(c for c, b in alnum.items() if b == 0) or "-")
    print("Buchstaben/Ziffern mit 1–2 px Abstand zu irgendeiner Schrift:",
          "".join(c for c, b in alnum.items() if 0 < b <= 2) or "-")
    print("kleinster Abstand je Zeichen über alle Schriften:", " ".join(f"{c}:{b}" for c, b in per_glyph.items()))


if __name__ == "__main__":
    main()
