"""Blockskizze für den Hintergrund (erste Referenz für das Bildmodell).

Die Szene ist in Bildschirmkoordinaten (1280×720) geplant. Die Skizze hat das Format des Bildauftrags
(1536×1024); der 16:9-Ausschnitt liegt in den Zeilen 80–944, Faktor 1,2:
    Skizze = (x · 1,2, 80 + y · 1,2)
Gezeichnet werden nur Himmel, Kimm, ferne Inseln, Landzunge, Meer, Kai und Steg; Häuschen, Leuchtturm,
Laterne, Fässer, Kisten, Tau und Boote sind eigene Cels und fehlen absichtlich.

    .venv/bin/python styles/gummischlauch/scripts/make_layout.py
"""
import pathlib

from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent.parent
OUT = HERE / "assets" / "ref" / "layout_bg.png"

S, OY = 1.2, 80


def P(pts):
    return [(x * S, OY + y * S) for x, y in pts]


def main():
    im = Image.new("RGB", (1536, 1024), (236, 176, 140))
    d = ImageDraw.Draw(im)
    # Himmel in drei Bändern (oben dunkler, an der Kimm hell-orange)
    d.rectangle([0, 0, 1536, OY + 150 * S], fill=(176, 120, 110))
    d.rectangle([0, OY + 150 * S, 1536, OY + 270 * S], fill=(214, 150, 120))
    d.rectangle([0, OY + 270 * S, 1536, OY + 330 * S], fill=(240, 170, 110))
    # ferne Inseln auf der Kimm
    d.polygon(P([(100, 330), (170, 314), (260, 309), (330, 318), (420, 312), (520, 322), (560, 330)]),
              fill=(110, 120, 112))
    # Meer
    d.rectangle([0, OY + 330 * S, 1536, OY + 520 * S], fill=(70, 130, 125))
    # Landzunge rechts (Felsen, oben ein freies Plateau für den Leuchtturm)
    d.polygon(P([(900, 520), (915, 420), (955, 372), (1000, 330), (1040, 290), (1070, 268), (1120, 262),
                 (1180, 262), (1240, 266), (1280, 270), (1280, 520)]), fill=(120, 92, 70), outline=(30, 20, 20))
    d.polygon(P([(1055, 272), (1080, 262), (1180, 260), (1240, 264), (1260, 280), (1150, 284), (1070, 286)]),
              fill=(120, 140, 90))
    # Kai (Steinfläche) mit dunkler Kante zum Wasser
    d.rectangle([0, OY + 520 * S, 1536, 1024], fill=(150, 128, 110), outline=(30, 20, 20))
    d.rectangle([0, OY + 520 * S, 1536, OY + 534 * S], fill=(96, 78, 66))
    # Holzsteg vom Kai aufs Wasser, mit Pfosten
    d.polygon(P([(392, 522), (548, 522), (520, 440), (446, 440)]), fill=(140, 96, 60), outline=(30, 20, 20))
    for x0, y0, y1 in [(396, 500, 532), (540, 500, 532), (444, 438, 470), (518, 438, 470), (420, 470, 500),
                       (530, 470, 500)]:
        d.rectangle(P([(x0 - 5, y0), (x0 + 5, y1)]), fill=(96, 64, 40))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    im.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
