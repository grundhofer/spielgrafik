"""KI-Porträt (agy, über der Blender-Vorlage gemalt) -> 64×64-Pixelbild auf der iso-pixel-Palette.

  .venv/bin/python styles/iso-pixel/scripts/build_portrait.py

Das KI-Bild hält ein sauberes 16-px-Raster, aber um eine halbe Zelle versetzt (gemessen mit
styles/snes-16bit/scripts/gridfind.py: Teilung 15,99, Versatz 7,7, Kantenverhältnis 5,0). Abgetastet wird je Zelle
die Mitte (Median der inneren 10×10 Bildpixel ohne Magenta-Saum, JPEG-Quelle), Deckung als Mehrheit; Farben auf die
Palette (Oklab); danach Außenkontur.
Schreibt demo/art/portrait.png und assets/portrait.png.
"""
import pathlib
import sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_props import to_palette, despeckle  # noqa: E402
from pixelize3d import add_outline  # noqa: E402

ENTRY = HERE.parent
P, OFF = 15.99, 7.7


def main():
    img = np.asarray(Image.open(ENTRY / "assets/raw/portrait.png").convert("RGBA")).astype(np.float64)
    H, W = img.shape[:2]
    n = int(np.ceil((W - OFF) / P)) + 1
    centers = OFF - P / 2 + np.arange(n) * P
    col = np.zeros((n, n, 3))
    a = np.zeros((n, n), bool)
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    good = (img[..., 3] > 127) & ~((r > 110) & (b > 110) & (g < np.minimum(r, b) - 45))   # Magenta-Saum weg
    for j, cy in enumerate(centers):
        for i, cx in enumerate(centers):
            y0, y1 = int(max(0, cy - 5)), int(min(H, cy + 5))
            x0, x1 = int(max(0, cx - 5)), int(min(W, cx + 5))
            if y1 <= y0 or x1 <= x0:
                continue
            m = good[y0:y1, x0:x1]
            if m.mean() < 0.5:
                continue
            a[j, i] = True
            col[j, i] = np.median(img[y0:y1, x0:x1, :3][m], axis=0)
    rgb = despeckle(to_palette(col), a)
    rgba = np.zeros((n, n, 4), np.uint8)
    rgba[..., :3] = rgb
    rgba[..., 3] = np.where(a, 255, 0)
    rgba = add_outline(rgba)
    # auf 64×64 zuschneiden: halbe Randzellen weg, Inhalt unten bündig (Schultern laufen aus dem Bild)
    ys, xs = np.nonzero(rgba[..., 3])
    x0 = max(0, min(xs.min(), n - 64))
    rgba = rgba[n - 64:, x0:x0 + 64] if rgba.shape[0] > 64 else rgba
    print("Zellen", n, "Ausschnitt", rgba.shape, "Farben", len(np.unique(rgba[rgba[..., 3] > 0][:, :3], axis=0)))
    Image.fromarray(rgba).save(ENTRY / "demo/art/portrait.png")
    Image.fromarray(rgba).save(ENTRY / "assets/portrait.png")
    # Blinzeln: nur das Augenfenster ändern (Körper bleibt pixelgleich). Auge = dunkle Pixel und Glanzlicht im
    # Streifen um (29, 24); sie werden zur Streifenfarbe, dazu ein Lidstrich.
    bl = rgba.copy()
    y0, y1, x0, x1 = 22, 27, 26, 34
    win = bl[y0:y1, x0:x1, :3].astype(int)
    stripe = np.array(rgba[24, 26, :3])
    lum = (win * [0.3, 0.59, 0.11]).sum(-1)
    eye = (lum < 30) | ((lum > 80) & (np.abs(win - win.mean((0, 1))).sum(-1) > 40))
    bl[y0:y1, x0:x1, :3][eye] = stripe
    lid = np.array(rgba[23, 28, :3])
    bl[25, 28:32, :3] = lid
    # fernes Auge (klein, links): Glanzlicht und obere Pupille zur Streifenfarbe, untere Pupille bleibt als Lid
    bl[22, 17, :3] = stripe
    bl[23, 17, :3] = stripe
    Image.fromarray(bl).save(ENTRY / "demo/art/portrait_blink.png")


if __name__ == "__main__":
    main()
