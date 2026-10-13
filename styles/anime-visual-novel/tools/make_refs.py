#!/usr/bin/env python3
"""Layout-Referenz für den Figurenauftrag (Bildauftrag 1), nur aus dem gemeinsamen Referenzblatt (kein KI-Bild).

Aufruf aus dem Projektordner:
    .venv/bin/python styles/anime-visual-novel/tools/make_refs.py

agy hält sich eng an das Layout des ersten Referenzbildes. Gibt man nur das Dreiansichten-Blatt mit, kommt
wieder ein Dreiansichten-Blatt zurück. Deshalb bekommt der Auftrag ein eigenes Layoutbild im Zielformat 3:2:
zweimal die Vorderansicht aus shared/badger/master_sheet_alpha.png nebeneinander, gleich groß, gleiche
Standlinie, mit deutlichem Abstand, flache Magenta-Fläche dahinter. Ergebnis: assets/ref_pair.png (1536x1024).

Getestet und verworfen (11.10.2026): die Figur vorher zu flachen Farbflächen zu vereinfachen (Median, k-means
auf 8 bzw. 12 Farben, Kontur an Farbgrenzen), um die Felltextur herauszunehmen. k-means trennt die Materialien
nicht: Weste, Mütze und dunkles Fell zerfallen in Tarnfleck-Muster, die Augen verschwinden. Ein solches Bild
würde das Modell eher zu Flecken verleiten als zu sauberem Cel-Shading. Der Stil kommt deshalb nur aus dem
Prompt, das Layoutbild bleibt die unveränderte Vorderansicht.
"""
import pathlib

from PIL import Image

SD = pathlib.Path(__file__).resolve().parent.parent
ROOT = SD.parent.parent
SRC = ROOT / "shared" / "badger" / "master_sheet_alpha.png"
OUT = SD / "assets" / "ref_pair.png"
FRONT = (12, 87, 529, 883)          # Vorderansicht im Blatt (gemessen: Spalten bzw. Zeilen mit Deckung)
CANVAS = (1536, 1024)
FIG_H = 930                          # Figurhöhe im Layoutbild (oben und unten je etwa 45 px Rand)
CENTERS = (384, 1152)                # Mitte der linken und rechten Figur (Viertelpunkte, Abstand ≈ 150 px)


def main():
    sheet = Image.open(SRC).convert("RGBA")
    fig = sheet.crop((FRONT[0] - 4, FRONT[1] - 4, FRONT[2] + 4, FRONT[3] + 4))
    s = FIG_H / (FRONT[3] - FRONT[1])
    w, h = round(fig.width * s), round(fig.height * s)
    big = fig.resize((w, h), Image.LANCZOS)
    canvas = Image.new("RGBA", CANVAS, (255, 0, 255, 255))
    top = (CANVAS[1] - h) // 2
    for cx in CENTERS:
        canvas.alpha_composite(big, (cx - w // 2, top))
    canvas.convert("RGB").save(OUT, optimize=True)
    print(f"{OUT.relative_to(ROOT)}  {CANVAS[0]}x{CANVAS[1]}, Figur {w}x{h} ab y={top}, Mitten {CENTERS}")


if __name__ == "__main__":
    main()
