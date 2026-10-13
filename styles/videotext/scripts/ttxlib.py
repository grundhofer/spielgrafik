#!/usr/bin/env python3
"""Videotext-Grundlagen: Palette, deutscher G0-Satz, Decoder (Level 1) und Wiedergabe einer Seite.

Eine Seite sind 25 Zeilen à 40 Bytes (7 Bit). 0x00–0x1F sind Steuerzeichen (Spacing Attributes), die selbst
eine Zelle belegen. Der Decoder hält sich an die Level-1-Regeln (ETS 300 706, Abschnitt 12.2 / SAA5050):

  Set-At   (gilt schon für die Steuerzelle):  Steady 09, Normal Size 0C, Conceal 18, Contiguous 19,
           Separated 1A, Black Background 1C, New Background 1D, Hold Mosaics 1E
  Set-After (gilt ab der nächsten Zelle):     Alpha-Farbe 01–07, Flash 08, Double Height 0D,
           Mosaik-Farbe 11–17, Release Mosaics 1F

Eine Steuerzelle zeigt die Hintergrundfarbe; nur bei Hold Mosaics im Mosaikmodus zeigt sie das zuletzt
empfangene Mosaikzeichen („held mosaic“). Wechsel Alpha/Mosaik und Wechsel der Größe löschen das gehaltene
Zeichen. Jede Zeile beginnt mit Weiß, Alpha, schwarzem Hintergrund, zusammenhängend, ohne Hold/Flash.
Doppelte Höhe: Die Zeile darunter wird nicht aus eigenen Daten angezeigt, sondern zeigt die unteren Hälften;
Zeichen normaler Höhe der oberen Zeile erscheinen dort als Leerzelle in deren Hintergrundfarbe.
"""
import pathlib

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent.parent
ROWS, COLS = 25, 40
CW, CH = 20, 28                      # Zelle in Bildpunkten (6×10-Punkt-Raster des SAA5050, 576i-Seitenverhältnis)
PAGE_W, PAGE_H = COLS * CW, ROWS * CH  # 800×700

# 0 schwarz, 1 rot, 2 grün, 3 gelb, 4 blau, 5 magenta, 6 cyan, 7 weiß (Farbnummer = Bits B G R)
PALETTE = np.array([(0, 0, 0), (255, 0, 0), (0, 255, 0), (255, 255, 0),
                    (0, 0, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255)], dtype=np.uint8)
NAMES = "krgybmcw"   # Buchstaben in Textdateien (k = schwarz)

# Deutscher nationaler Zeichensatz (G0 Latin, nationale Option Deutsch)
NATIONAL_DE = {0x23: "#", 0x24: "$", 0x40: "§", 0x5B: "Ä", 0x5C: "Ö", 0x5D: "Ü", 0x5E: "^", 0x5F: "_",
               0x60: "°", 0x7B: "ä", 0x7C: "ö", 0x7D: "ü", 0x7E: "ß", 0x7F: "■"}
G0 = {c: NATIONAL_DE.get(c, chr(c)) for c in range(0x20, 0x80)}
UNI2G0 = {v: k for k, v in G0.items()}

# Steuerzeichen
ALPHA = {n: i for i, n in enumerate(NAMES) if i}            # Alpha-Farbe: ALPHA['y'] = 0x03
GFX = {n: 0x10 + i for i, n in enumerate(NAMES) if i}       # Mosaik-Farbe: GFX['y'] = 0x13
FLASH, STEADY, NORMAL, DOUBLE = 0x08, 0x09, 0x0C, 0x0D
CONTIG, SEPAR, BLACKBG, NEWBG, HOLD, RELEASE = 0x19, 0x1A, 0x1C, 0x1D, 0x1E, 0x1F

# Mosaikzeichen: Bit je Sechstel (oben links, oben rechts, Mitte links, Mitte rechts, unten links, unten rechts)
SEXT_BITS = (0x01, 0x02, 0x04, 0x08, 0x10, 0x40)


def mosaic_byte(pattern):
    """pattern: 6 Bit (Bit i = Sechstel i) -> Zeichencode 0x20–0x3F / 0x60–0x7F."""
    b = 0x20
    for i, bit in enumerate(SEXT_BITS):
        if pattern >> i & 1:
            b |= bit
    return b


def mosaic_pattern(b):
    return sum(1 << i for i, bit in enumerate(SEXT_BITS) if b & bit)


def text_bytes(s):
    out = []
    for ch in s:
        if ch not in UNI2G0:
            raise ValueError(f"Zeichen nicht im deutschen G0-Satz: {ch!r}")
        out.append(UNI2G0[ch])
    return out


# Zellarten
BLANK, CHAR, MOSAIC = 0, 1, 2


def decode_row(row):
    """Liefert je Zelle (art, code, fg, bg, sep, flash, dh); code = Zeichen (CHAR) oder Muster (MOSAIC).
    Zusätzlich, ob die Zeile ein Double-Height-Zeichen enthält."""
    fg, bg, mosaic, sep, hold, flash, dh = 7, 0, False, False, False, False, False
    held = (0, False)
    cells, has_dh = [], False
    for b in row:
        b &= 0x7F
        if b < 0x20:
            # Set-At
            if b == STEADY:
                flash = False
            elif b == NORMAL:
                if dh:
                    held = (0, False)
                dh = False
            elif b == CONTIG:
                sep = False
            elif b == SEPAR:
                sep = True
            elif b == BLACKBG:
                bg = 0
            elif b == NEWBG:
                bg = fg
            elif b == HOLD:
                hold = True
            if hold and mosaic:
                cells.append((MOSAIC, held[0], held[1], fg, bg, flash, dh))
            else:
                cells.append((BLANK, 0, False, fg, bg, flash, dh))
            # Set-After
            if 0x01 <= b <= 0x07:
                if mosaic:
                    held = (0, False)
                fg, mosaic = b, False
            elif b == FLASH:
                flash = True
            elif b == DOUBLE:
                if not dh:
                    held = (0, False)
                dh, has_dh = True, True
            elif 0x11 <= b <= 0x17:
                if not mosaic:
                    held = (0, False)
                fg, mosaic = b - 0x10, True
            elif b == RELEASE:
                hold = False
        elif mosaic and (b & 0x20):
            p = mosaic_pattern(b)
            cells.append((MOSAIC, p, sep, fg, bg, flash, dh))
            held = (p, sep)
        else:
            cells.append((CHAR, b, False, fg, bg, flash, dh))
    # Zeile kürzer als 40: Rest leer
    while len(cells) < COLS:
        cells.append((BLANK, 0, False, fg, bg, flash, dh))
    return cells, has_dh


def decode_page(page):
    """page: 25 Listen à 40 Bytes. Ergebnis: 25×40 Zellen (art, code, fg, bg, sep, flash, part),
    part 0 = normal, 1 = obere Hälfte doppelter Höhe, 2 = untere Hälfte."""
    out = []
    r = 0
    while r < ROWS:
        cells, has_dh = decode_row(page[r])
        out.append([(k, c, s, f, g, fl, 1 if d else 0) for (k, c, s, f, g, fl, d) in cells])
        if has_dh and 1 <= r < ROWS - 1:
            low = []
            for (k, c, s, f, g, fl, d) in cells:
                low.append((k, c, s, f, g, fl, 2) if d else (BLANK, 0, False, f, g, fl, 0))
            out.append(low)
            r += 2
        else:
            r += 1
    return out[:ROWS]


# ---------------------------------------------------------------- Geometrie der Mosaikzellen
SEXT_X = ((0, 10), (10, 20))                 # Spalten
SEXT_Y = ((0, 8), (8, 20), (20, 28))          # Zeilen 3:4:3 wie im SAA5050 (8/12/8 Bildpunkte)
SEP_GAP = 3                                   # getrennte Mosaike: 3 px Lücke rechts und unten je Sechstel


def mosaic_mask(pattern, sep, height=CH):
    """Maske CH×CW (oder doppelt hoch) für ein Mosaikzeichen."""
    k = height // CH
    m = np.zeros((height, CW), dtype=bool)
    for i in range(6):
        if not pattern >> i & 1:
            continue
        x0, x1 = SEXT_X[i % 2]
        y0, y1 = SEXT_Y[i // 2]
        y0, y1 = y0 * k, y1 * k
        if sep:
            x1 -= SEP_GAP
            y1 -= SEP_GAP * k
        m[y0:y1, x0:x1] = True
    return m


_MOS = {}


def mosaic_cell(pattern, sep, part):
    key = (pattern, sep, part)
    if key not in _MOS:
        if part == 0:
            _MOS[key] = mosaic_mask(pattern, sep)
        else:
            full = mosaic_mask(pattern, sep, CH * 2)
            _MOS[key] = full[:CH] if part == 1 else full[CH:]
    return _MOS[key]


_ATLAS = None


def atlas():
    """Glyphenatlas (demo/fonts/g0_atlas.png): 96 Zeichen × 3 Fassungen (normal, oben, unten), Deckung 0–255."""
    global _ATLAS
    if _ATLAS is None:
        from PIL import Image
        a = np.asarray(Image.open(HERE / "demo" / "fonts" / "g0_atlas.png").convert("L"), dtype=np.float32) / 255.0
        _ATLAS = a
    return _ATLAS


def glyph(code, part):
    a = atlas()
    i = code - 0x20
    gx, gy = (i % 16) * CW, (i // 16) * CH + part * 6 * CH
    return a[gy:gy + CH, gx:gx + CW]


def render(page_cells, flash_on=True):
    """Dekodierte Seite -> RGB-Bild 800×700 (uint8)."""
    img = np.zeros((PAGE_H, PAGE_W, 3), dtype=np.float32)
    pal = PALETTE.astype(np.float32)
    for r, row in enumerate(page_cells):
        for c, (k, code, sep, fg, bg, fl, part) in enumerate(row):
            y, x = r * CH, c * CW
            if k == BLANK or (fl and not flash_on):
                cov = np.zeros((CH, CW), dtype=np.float32)
            elif k == MOSAIC:
                cov = mosaic_cell(code, sep, part).astype(np.float32)
            else:
                cov = glyph(code, part)
            img[y:y + CH, x:x + CW] = pal[bg] * (1 - cov[..., None]) + pal[fg] * cov[..., None]
    return np.clip(img + 0.5, 0, 255).astype(np.uint8)


def blank_page():
    return [[0x20] * COLS for _ in range(ROWS)]


def page_to_hex(page):
    return ["".join(f"{b:02x}" for b in row) for row in page]


def page_from_hex(rows):
    return [[int(s[i:i + 2], 16) for i in range(0, len(s), 2)] for s in rows]


def mosaic_grid(page_cells, r0, r1, flash_on=True):
    """Angezeigte Farben je Sechstel (Zeilen r0..r1-1) als Feld (3·n)×80 – Grundlage für Vergleiche mit der
    Vorlage. Getrennte Mosaike zählen hier als Vordergrundfarbe."""
    n = r1 - r0
    g = np.zeros((3 * n, 2 * COLS), dtype=np.int8)
    for rr in range(n):
        for c, (k, code, sep, fg, bg, fl, part) in enumerate(page_cells[r0 + rr]):
            for i in range(6):
                on = k == MOSAIC and (code >> i & 1) and (flash_on or not fl)
                g[3 * rr + i // 2, 2 * c + i % 2] = fg if on else bg
    return g
