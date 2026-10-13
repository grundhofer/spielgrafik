#!/usr/bin/env python3
"""Stilreferenz für die Figuren-Nachbesserung (Prüfung 1): Ausschnitte mit echter Lasur aus dem KI-Hintergrund
(Fässer, Kisten mit Seil und Poller, Kaipflaster) statt des ganzen Bildes, damit das Bildmodell die Maltechnik
(flache Lasuren, Trockenränder, Granulation) und nicht die Postkarten-Stimmung übernimmt.

    .venv/bin/python styles/aquarell/tools/make_style_ref.py

Ergebnis: assets/ref/wash_style.png (1024x1024), Ausschnitte in Rohbild-Pixeln von assets/raw/bg.png.
"""
import pathlib
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
CROPS = [((100, 590, 370, 730), (0, 0, 512, 266)),          # Fässer und Poller
         ((950, 580, 1290, 740), (512, 0, 1024, 266)),      # Kisten, Seil, Poller
         ((0, 740, 760, 1024), (0, 266, 1024, 648)),        # Kaipflaster (flache Lasuren mit Trockenrand)
         ((760, 740, 1536, 1024), (0, 648, 1024, 1024))]    # Kaipflaster rechts


def main():
    src = Image.open(ROOT / "assets/raw/bg.png").convert("RGB")
    out = Image.new("RGB", (1024, 1024), (244, 239, 228))
    for box, (x0, y0, x1, y1) in CROPS:
        out.paste(src.crop(box).resize((x1 - x0, y1 - y0), Image.LANCZOS), (x0, y0))
    p = ROOT / "assets/ref/wash_style.png"
    out.save(p)
    print("ok", p)


if __name__ == "__main__":
    main()
