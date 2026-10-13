#!/usr/bin/env python3
"""Hintergrund: Ausschnitt 16:9 aus dem KI-Bild (assets/raw/bg_c.png, 1536x1024), sonst unverändert.

    .venv/bin/python styles/zeichentrick-cel/scripts/build_bg.py

Zeilen 40–904 (864 Zeilen) werden auf 1280x720 verkleinert (Faktor 0,8333, Lanczos). Oben fehlt dadurch nur Sternhimmel,
unten Pflaster. Ergebnis: assets/bg.png. Die Lagen der Lichter und Boote in diesem Ausschnitt stehen als Konstanten in
demo/main.gd (von Hand im Ausschnitt gemessen), die Wasserfläche für den Glitzer baut scripts/build_water_mask.py.

bg_c.png ist Versuch 3: mit bg_b.png (Versuch 2) als Lagereferenz neu gemalt („as if traced on a clear sheet“) und
mit stärker reduziertem Stilblock. Er liegt bis auf 1–4 px (Quelle) deckungsgleich auf bg_b.png.
"""
import pathlib

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
OY = 40
SRC = "assets/raw/bg_c.png"


def main():
    im = Image.open(ROOT / SRC).convert("RGB")
    im = im.crop((0, OY, 1536, OY + 864)).resize((1280, 720), Image.LANCZOS)
    im.save(ROOT / "assets/bg.png")
    print("ok", im.size)


if __name__ == "__main__":
    main()
