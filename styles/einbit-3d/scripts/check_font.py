#!/usr/bin/env python3
"""Prüft die Schrift der Oberfläche im gerenderten Bild gegen eine unabhängige Rasterung mit Pillow.

    .venv/bin/python styles/einbit-3d/scripts/check_font.py [--frame 156] [--png bild.png] [--dump "mMwW>"]

Rendert ein Bild der Demo (640×360, wie tools/capture.py) und setzt jede Textzeile aus ui.gd mit Pillow
(FreeType ohne Kantenglättung, fontmode "1") in derselben Größe neu: Jersey 10 in 18 2/3 px (Raster 75 von
1400 Einheiten), Jacquard 12 in 21 px (Raster 60 von 1260). Bei Rasterschriften in nativer Größe liegen alle
Umrisse auf ganzen Pixeln, die Rasterung ist dann eindeutig: Jede Abweichung ist ein Fehler im Bild. Gibt je
Zeile die Zahl abweichender Pixel aus und einen ASCII-Abzug der Zeichen aus --dump, wie sie im Bild stehen.
Verglichen wird je Zeile das Rechteck der Schrift (eine Zeile und ein Pixel Rand), also ohne Nachbarzeilen.
Die Lagen (x, Grundlinie) stehen in lines() und müssen zu ui.gd passen.
"""
import argparse, pathlib, sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
FONTS = HERE.parent / "demo" / "fonts"
sys.path.insert(0, str(HERE))
from snap import render  # noqa: E402

BODY = (FONTS / "Jersey10-Regular.ttf", 1400 / 75)
TITLE = (FONTS / "Jacquard12-Regular.ttf", 21)
BOX = (300, 261, 332, 91)                      # ui.gd BOX
X0 = BOX[0] + 10
Y1 = BOX[1] + 19
YS = Y1 + 14 + 5


def lines():
    body = ImageFont.truetype(str(BODY[0]), BODY[1])
    px = BOX[0] + BOX[2] - 12 - 7 - int(body.getlength("> nimm paket"))
    # (Schrift, Text, x, Grundlinie, Tinte auf Papier?)
    return [
        (TITLE, "Hafen von Lornholm", 18, 28, True),
        (BODY, "Die Laterne flackert im Wind.", X0, Y1, True),
        (BODY, "Am Kai wartet ein Paket auf dich.", X0, Y1 + 14, True),
        (BODY, "Zum Leuchtturm gehen", X0 + 12, YS + 14, False),     # ausgewählt: Papier auf Tinte
        (BODY, "Das Paket ansehen", X0 + 12, YS + 28, True),
        (BODY, "Mit dem Dachs sprechen", X0 + 12, YS + 42, True),
        (BODY, "> nimm paket", px, YS + 42, True),
    ]


def reference(font, text, x, base, size):
    im = Image.new("L", size, 0)
    d = ImageDraw.Draw(im)
    d.fontmode = "1"
    d.text((x, base), text, font=font, fill=255, anchor="ls")
    return np.asarray(im) > 127


def dump(a):
    return "\n".join("".join("#" if v else "." for v in row) for row in a)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", type=int, default=156)
    ap.add_argument("--png", default=None)
    ap.add_argument("--dump", default="mMwW>")
    a = ap.parse_args()
    if a.png:
        img = np.asarray(Image.open(a.png).convert("L"))
    else:
        pngs, _log, errs = render(a.frame + 1, [])
        for e in errs[:10]:
            print("!!", e)
        img = np.asarray(Image.open(pngs[a.frame]).convert("L"))
    if img.shape != (360, 640):
        sys.exit(f"Bild {img.shape[::-1]}, erwartet 640×360")
    dark = img < 128
    total = 0
    for (path, size), text, x, base, ink in lines():
        font = ImageFont.truetype(str(path), size)
        ref = reference(font, text, x, base, (640, 360))
        got = dark if ink else ~dark
        x1 = x + int(font.getlength(text))
        rows = np.nonzero(ref.any(1))[0]          # Zeilen mit Schrift (ohne Nachbarzeilen und Auswahlbalken)
        box = (slice(rows.min() - 1, rows.max() + 2), slice(x - 1, x1 + 1))
        diff = int((ref[box] != got[box]).sum())
        total += diff
        print(f"{path.stem:22s} {size:5.2f} px  {diff:3d} Pixel abweichend  „{text}“")
        # ASCII-Abzug der gewünschten Zeichen, wie sie im Bild stehen
        for ch in a.dump:
            i = text.find(ch)
            if i < 0 or not ink:
                continue
            cx = x + int(font.getlength(text[:i]))
            w = int(font.getlength(ch))
            print(f"  '{ch}' aus „{text}“ (x {cx}, Breite {w} px):")
            for row in dump(got[base - 11:base + 3, cx:cx + w]).splitlines():
                print("    " + row)
        a.dump = "".join(c for c in a.dump if c not in text or not ink)
    print(f"Summe: {total} abweichende Pixel")
