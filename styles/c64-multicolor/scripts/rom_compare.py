#!/usr/bin/env python3
"""Abgleich des Zeichensatzes font8 mit einem Zeichensatz-ROM (4096 Bytes, Großbuchstaben-Satz + Klein-Satz).

Der ROM gehört nicht zum Eintrag und wird nicht mitgeliefert; Aufruf mit einem eigenen Abzug:
    python3 scripts/rom_compare.py /pfad/zu/chargen.bin [font8.py]
Je Zeichen: abweichende Pixel direkt und als kleinster Wert über alle Verschiebungen um ±1 Zeile/Spalte
(fängt verschobene Kopien). Großbuchstaben aus dem ersten Satz (Codes 1-26), Kleinbuchstaben aus dem zweiten
Satz (Codes 1-26), Ziffern und Satzzeichen aus den Codes 32-63.
"""
import importlib.util, pathlib, sys

import numpy as np


def load_font(path):
    spec = importlib.util.spec_from_file_location("font8_cmp", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def bits(b8):
    return np.array([[(int(b) >> (7 - x)) & 1 for x in range(8)] for b in b8], np.uint8)


def rom_glyph(rom, ch):
    if "A" <= ch <= "Z":
        c = ord(ch) - 64
    elif "a" <= ch <= "z":
        c = 256 + ord(ch) - 96
    elif 32 <= ord(ch) < 64:
        c = ord(ch)
    else:
        return None
    return bits(rom[c * 8:c * 8 + 8])


def shift(g, dy, dx):
    out = np.zeros_like(g)
    out[max(0, dy):8 + min(0, dy), max(0, dx):8 + min(0, dx)] = g[max(0, -dy):8 + min(0, -dy),
                                                                   max(0, -dx):8 + min(0, -dx)]
    return out


def main():
    rom = np.frombuffer(pathlib.Path(sys.argv[1]).read_bytes(), np.uint8)
    if len(rom) != 4096:
        raise SystemExit(f"{sys.argv[1]}: {len(rom)} Bytes, erwartet 4096")
    font = load_font(sys.argv[2] if len(sys.argv) > 2 else pathlib.Path(__file__).with_name("font8.py"))
    res = {}
    for ch in sorted(font.G):
        r = rom_glyph(rom, ch)
        if r is None:
            continue
        m = np.array([[1 if c == "#" else 0 for c in row] for row in font.G[ch]], np.uint8)
        direct = int((m != r).sum())
        best = min(int((shift(m, dy, dx) != r).sum()) for dy in (-1, 0, 1) for dx in (-1, 0, 1))
        res[ch] = (direct, best)
    alnum = {c: v for c, v in res.items() if c.isalnum()}
    mins = sorted(b for _, b in alnum.values())
    print(f"verglichen: {len(res)} Zeichen, davon {len(alnum)} Buchstaben und Ziffern")
    print("pixelgleich (direkt):", "".join(c for c, (d, _) in res.items() if d == 0) or "-")
    print("pixelgleich nach Verschiebung:", "".join(c for c, (_, b) in res.items() if b == 0) or "-")
    print("Buchstaben/Ziffern mit höchstens 3 px Abstand:", "".join(c for c, (_, b) in alnum.items() if b <= 3) or "-")
    print(f"Buchstaben/Ziffern: Median {mins[len(mins) // 2]} px, Mittel {sum(mins) / len(mins):.1f} px")
    print("je Zeichen (kleinster Abstand):", " ".join(f"{c}:{b}" for c, (_, b) in res.items()))


if __name__ == "__main__":
    main()
