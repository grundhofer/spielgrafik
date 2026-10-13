#!/usr/bin/env python3
"""Misst den Dachs in den gerenderten Godot-Bildern: Füße, Kopf, Vorschub, Fußzeile.

    .venv/bin/python styles/videotext/scripts/check_badger.py <ordner mit f*.png>

Füße: Bildzeile 568 (Seite y 558 = Zeile 19, Glyphenzeile 26) zeigt nur zusammenhängende blaue Mosaike; die
getrennten Pflasterpunkte haben dort ihre Lücke. Jede blaue Folge ist ein Fuß, gemessen in Mosaikpunkten
(10 Bildpunkte). Kopf: oberste grüne Bildzeile (Mütze) und deren linker/rechter Rand im Dachsbereich.
Prüft: Standfuß bei jedem Laufbildwechsel ortsfest (ein Fuß bleibt auf demselben Mosaikpunkt), auch an den
Übergängen Tür → Laufen, Laufen → Stehen und Stehen → Vorderansicht; Vorschub je Laufbild, unterste blaue Zeile
(Fußzeile) in allen Bildern gleich; Paket: gelbe Bildpunkte in der Westenzeile (Zeichenzeile 18) um die Mütze.
"""
import pathlib
import sys

import numpy as np
from PIL import Image

X0, Y0 = 240, 10      # Lage der Seite in der Aufnahme


def feet(img):
    line = img[Y0 + 558, X0:X0 + 800]
    blue = (line[:, 0] < 40) & (line[:, 1] < 40) & (line[:, 2] > 200)
    out, x = [], 0
    while x < 800:
        if blue[x]:
            s = x
            while x < 800 and blue[x]:
                x += 1
            out.append((s // 10, (x - 1) // 10))       # erster und letzter Mosaikpunkt
        else:
            x += 1
    return out


def head(img):
    reg = img[Y0 + 14 * 28:Y0 + 20 * 28, X0 + 140:X0 + 560]
    green = (reg[..., 0] < 40) & (reg[..., 1] > 200) & (reg[..., 2] < 40)
    ys = np.nonzero(green.any(1))[0]
    if not len(ys):
        return None
    y = ys[0]
    xs = np.nonzero(green[y])[0]
    return y, (xs[0] + 140) // 10, (xs[-1] + 140) // 10


def foot_row(img):
    reg = img[Y0 + 14 * 28:Y0 + 20 * 28, X0 + 140:X0 + 560]
    blue_full = (reg[..., 2] > 200) & (reg[..., 0] < 40) & (reg[..., 1] < 40)
    # nur Spalten mit Beinen (zusammenhängend, Zeile 26 der Zelle gesetzt)
    rows = np.nonzero(blue_full.any(1))[0]
    return int(rows[-1]) if len(rows) else None


def parcel(img, hd):
    """Gelbe Bildpunkte in Zeichenzeile 18 (Weste + Paket) im Bereich ±75 px um die Mützenmitte."""
    if not hd:
        return 0
    cx = (hd[1] + hd[2] + 1) * 5
    reg = img[Y0 + 18 * 28:Y0 + 19 * 28, X0 + max(0, cx - 75):X0 + cx + 75]
    return int(((reg[..., 0] > 200) & (reg[..., 1] > 200) & (reg[..., 2] < 40)).sum())


def main():
    d = pathlib.Path(sys.argv[1])
    pngs = sorted(d.glob("f*.png"))
    data = []
    for i, p in enumerate(pngs):
        img = np.asarray(Image.open(p).convert("RGB")).astype(int)
        hd = head(img)
        data.append((i, feet(img), hd, foot_row(img), parcel(img, hd)))
    # Laufbilder: Bilder 12–77, Laufbildwechsel alle 3 Aufnahmebilder. In der unteren Fußzeile steht nur der
    # aufgesetzte Fuß (der schwingende Fuß ist eine Zeile höher). Erwartung: jeder Standfuß bleibt 2 Laufbilder
    # (6 Aufnahmebilder) auf demselben Mosaikpunkt, dann setzt der andere Fuß 4 Punkte weiter vorn auf.
    steps = [(i, ft, hd) for i, ft, hd, fr, _p in data if 12 <= i <= 77 and (i - 12) % 3 == 0]
    runs, cur, adv = [], 1, []
    for (i0, f0, h0), (i1, f1, h1) in zip(steps, steps[1:]):
        if f0 and f1 and f0[0] == f1[0]:
            cur += 1
        else:
            runs.append(cur)
            cur = 1
        if h0 and h1:
            adv.append(int(h1[1] - h0[1]))
    runs.append(cur)
    jumps = []
    for (i0, f0, h0), (i1, f1, h1) in zip(steps, steps[1:]):
        if f0 and f1 and f0[0] != f1[0]:
            jumps.append(int(f1[0][0] - f0[0][0]))
    print(f"Laufbilder: {len(steps)}; Standfuß-Phasen (Laufbilder je ortsfestem Fuß): {runs}")
    print(f"Versatz beim Fußwechsel (neuer minus alter Standfuß, Mosaikpunkte): {sorted(set(jumps))}")
    print("Vorschub der Mütze je Laufbild:", {a: adv.count(a) for a in sorted(set(adv))})
    for i0, i1, label in ((11, 12, "Tür -> erstes Laufbild"), (72, 75, "letztes Laufbild -> Stehen"),
                          (89, 90, "Stehen -> Vorderansicht")):
        if i1 < len(data):
            f0, f1 = data[i0][1], data[i1][1]
            print(f"Übergang {label} (Bild {i0}->{i1}): Füße {f0} -> {f1}, "
                  f"Standfuß bleibt: {'ja' if set(f0) & set(f1) else 'NEIN'}")
    rows = sorted({fr for *_, fr, _p in data if fr is not None})
    print("unterste blaue Bildzeile im Dachsbereich (Fußzeile):", rows)
    heads = sorted({int(hd[0]) for _, _, hd, *_ in data if hd})
    print("oberste Mützenzeile:", heads)
    side = [p for i, *_, p in data if i < 90]
    front = [p for i, *_, p in data if i >= 90]
    print(f"Paket (gelbe Bildpunkte in der Westenzeile): Seitenansicht {min(side)}–{max(side)}, "
          f"Vorderansicht {min(front) if front else '-'}–{max(front) if front else '-'}")
    for i, ft, hd, fr, p in data[:: 6]:
        print(f"  Bild {i:3d}: Füße {ft}  Mütze {tuple(int(v) for v in hd) if hd else None}  Paket {p}")


if __name__ == "__main__":
    main()
