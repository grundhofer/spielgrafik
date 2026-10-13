#!/usr/bin/env python3
"""Baut die Videotextseite 100 „Hafen von Lornholm“ (25 × 40 Bytes) aus der Vorlage (scene.py).

    .venv/bin/python styles/videotext/scripts/build_page.py

Zeile 0     Kopfzeile: Spalten 0–7 schreibt das Fernsehgerät (Seitennummer), 8–39 kommen vom Sender
Zeile 1–2   Titel in doppelter Höhe im Himmel (von Hand gesetzt)
Zeile 3–19  Bild: Mosaikzeilen per dynamischer Programmierung (ttxenc.encode_row) aus der Vorlage
Zeile 20–21 Beschreibung, Zeile 22–24 Auswahl mit Farbtasten und Seitennummern
Ausgabe: assets/scene_target.png (Vorlage) und Bericht; build_stream.py nutzt build() für die Grundseite.
"""

import numpy as np
from PIL import Image

import scene
import ttxenc as E
import ttxlib as T

HERE = T.HERE
TEXT_ROWS = {
    20: "Die Laterne flackert im Wind. Am Kai",
    21: "wartet ein Paket auf dich.",
}
CHOICES = [(22, "r", "Zum Leuchtturm gehen", "201"),
           (23, "g", "Das Paket ansehen", "202"),
           (24, "y", "Mit dem Dachs sprechen", "203")]


def header_row(page="100", clock="18:42:07", typed="P100"):
    row = T.text_bytes(typed.ljust(8))
    row += [T.ALPHA["y"]] + T.text_bytes("LORNTEXT") + [T.ALPHA["w"]] + T.text_bytes(f"{page} Di 13.10.")
    row += [T.ALPHA["y"]] + T.text_bytes(clock)
    assert len(row) == 40, len(row)
    return row


def title_rows():
    row = [T.GFX["b"], T.NEWBG, T.DOUBLE, T.ALPHA["y"]] + T.text_bytes("Hafen von Lornholm")
    row += [T.GFX["w"], T.SEPAR]
    # zwei Sterne (getrennte Mosaike, doppelte Höhe) rechts im Titelband
    rest = [0x20] * (40 - len(row))
    rest[5] = T.mosaic_byte(0b000001)     # oben links
    rest[12] = T.mosaic_byte(0b000010)
    row += rest
    assert len(row) == 40
    return row, [0x20] * 40               # Zeile 2 wird als untere Hälfte angezeigt


def text_rows():
    rows = {}
    for r, s in TEXT_ROWS.items():
        rows[r] = ([0x20] + T.text_bytes(s)).__add__([0x20] * 40)[:40]
    for r, key, text, num in CHOICES:
        row = [T.GFX[key], 0x7F, T.ALPHA["w"], 0x20] + T.text_bytes(text) + [0x20]
        row += [T.ALPHA["b"]] + T.text_bytes("." * (36 - len(row) - 1))
        row += [T.ALPHA["y"]] + T.text_bytes(num)
        assert len(row) == 40, (r, len(row))
        rows[r] = row
    return rows


# Laterne: Zeile 13, Spalte 27 = Mosaik-Gelb vor dem Glas (Spalte 28), Spalte 29 setzt die Farbe zurück
# (Grün für den Fels rechts daneben). Das Flackern tauscht nur das Byte in Spalte 27 (Gelb/Weiß), der Rest der
# Zeile bleibt gleich.
LANTERN_ROW, LANTERN_COL = 13, 27
FIXED = {13: {27: T.GFX["y"], 28: 0x7F, 29: T.GFX["g"]}}


def target_rows(t_on, t_off, w, r):
    y0 = 3 * (r - 1)
    a, b_, ww = t_on[y0:y0 + 3].copy(), t_off[y0:y0 + 3].copy(), w[y0:y0 + 3]
    return a, b_, ww


def encode_picture(t_on, t_off, w, sep, rows=range(3, 20), log=True):
    out = {}
    stats = []
    for r in rows:
        a, b_, ww = target_rows(t_on, t_off, w, r)
        bytes_, cost, _ = E.encode_row(a, b_, ww, sep[r - 1], fixed=FIXED.get(r))
        chk = E.row_cost(bytes_, a, b_, ww)
        on, off = E.shown(bytes_)
        miss = int(((on != a) & (a >= 0)).sum())
        ctrl = sum(1 for x in bytes_ if x < 0x20)
        stats.append((r, round(cost, 2), round(chk, 2), miss, ctrl))
        out[r] = bytes_
    if log:
        for s in stats:
            print("Zeile %2d  Kosten %7.2f (Decoder %7.2f)  falsche Sechstel %3d  Steuerzellen %2d" % s)
    return out, stats


def build(t_on=None):
    s_on, t_off, w, sep, _ = scene.draw()
    t_on = s_on if t_on is None else t_on
    page = T.blank_page()
    page[0] = header_row()
    page[1], page[2] = title_rows()
    pic, stats = encode_picture(t_on, t_off, w, sep)
    for r, b in pic.items():
        page[r] = b
    for r, b in text_rows().items():
        page[r] = b
    return page, stats


def compose(img_page):
    """Seite (800×700) mittig in 1280×720 wie in der Demo."""
    canvas = np.zeros((720, 1280, 3), dtype=np.uint8)
    canvas[10:710, 240:1040] = img_page
    return canvas


def main():
    """Vorlage als Bild und Bericht der Kodierung; die Demo-Daten schreibt build_stream.py."""
    page, stats = build()
    s_on, *_ = scene.draw()
    Image.fromarray(T.PALETTE[np.where(s_on < 0, 0, s_on)]).resize((800, 570), Image.NEAREST).save(
        HERE / "assets" / "scene_target.png")
    miss = sum(s[3] for s in stats)
    ctrl = sum(s[4] for s in stats)
    print(f"Bildzeilen 3–19: {miss} von {17 * 240} Sechsteln weichen von der Vorlage ab "
          f"(Spalte 0 mitgezählt), {ctrl} Steuerzellen")


if __name__ == "__main__":
    main()
