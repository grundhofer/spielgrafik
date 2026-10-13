#!/usr/bin/env python3
"""Hintergrund für skelett-2d aufbereiten.

    .venv/bin/python styles/skelett-2d/scripts/prep_bg.py

1. agy hat das 3:2-Bild als 16:9-Bild mit hellgrauen Balken oben und unten gemalt: Balken abschneiden
   (Zeilen 57..746), auf 16:9 beschneiden und auf 1280×720 bringen (Faktor 1,0435).
2. Den trotz Prompt gemalten Rauch über dem Schornstein entfernen (Rauch kommt animiert aus Godot):
   Maske = heller als der Himmel derselben Zeile, zeilenweise aus den Nachbarn aufgefüllt, Pinselstruktur
   aus einem Himmelsstück daneben übernommen.
3. Wassermaske (R) und Himmelsmaske (G) als RGB-Bild für den Hintergrund-Shader; Lichtpunkte messen.

Schreibt assets/bg.png, assets/bg_mask.png, assets/scene.json und Kopien nach demo/art/.
"""
import json, pathlib, shutil

import numpy as np
from PIL import Image, ImageFilter

HERE = pathlib.Path(__file__).resolve().parents[1]
RAW = HERE / "assets" / "raw" / "bg.png"
Y0, Y1 = 57, 747          # Inhalt ohne Balken (Zeile 56 und 747 sind Übergänge)
X0 = 12                    # links 12 px, rechts 25 px abschneiden
W, H = 1280, 720


def remove_smoke(im):
    a = im.astype(np.float32)
    lum = a @ np.array([0.299, 0.587, 0.114], np.float32)
    bx0, bx1, by0, by1 = 118, 300, 50, 136
    out = a.copy()
    mask = np.zeros(lum.shape, bool)
    for y in range(by0, by1):
        ref = np.median(lum[y, 300:360])
        row = lum[y, bx0:bx1] - ref
        mask[y, bx0:bx1] = row > 5.0
    # Schornstein (dunkel, unter y≈134) nicht anfassen
    mask[128:, :] &= lum[128:, :] > 105
    m = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(7))
    mask = np.asarray(m) > 0
    # Struktur des Himmels aus einem Stück rechts daneben (Hochpass)
    blur = np.asarray(Image.fromarray(im).filter(ImageFilter.GaussianBlur(4))).astype(np.float32)
    hp = a - blur
    for y in range(by0, by1):
        xs = np.nonzero(mask[y])[0]
        if not len(xs):
            continue
        for run in np.split(xs, np.nonzero(np.diff(xs) > 1)[0] + 1):
            l, r = run[0] - 1, run[-1] + 1
            cl = blur[y, max(l - 3, 0):l + 1].mean(axis=0)
            cr = blur[y, r:r + 4].mean(axis=0)
            t = (run - l) / float(r - l)
            fill = cl[None, :] * (1 - t[:, None]) + cr[None, :] * t[:, None]
            out[y, run] = fill + hp[y, run + 230]
    return np.clip(out, 0, 255).astype(np.uint8), mask


def main():
    raw = np.asarray(Image.open(RAW).convert("RGB"))
    clean, smoke = remove_smoke(raw)
    crop = clean[Y0:Y1, X0:X0 + round((Y1 - Y0) * 16 / 9)]
    s = H / crop.shape[0]
    bg = Image.fromarray(crop).resize((W, H), Image.LANCZOS)
    bg.save(HERE / "assets" / "bg.png")

    a = np.asarray(bg).astype(np.float32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    hy = round((425 - Y0) * s)                     # Horizont
    yy, xx = np.mgrid[0:H, 0:W]
    water = (yy > hy + 1) & (b > r + 30) & (g > r + 15) & (b > 105)
    # Quai, Steg, Boote, Felsen sind warm oder dunkel und fallen schon über die Farbe heraus;
    # Kai-Vorderkante (unter y=606) sicher ausschließen
    water &= yy < round((585 - Y0) * s)
    wm = Image.fromarray((water * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    sky = (yy < hy) & (b > 110)
    sm = Image.fromarray((sky * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0))
    mask = np.zeros((H, W, 3), np.uint8)
    mask[..., 0] = np.asarray(wm)
    mask[..., 1] = np.asarray(sm)
    Image.fromarray(mask).save(HERE / "assets" / "bg_mask.png")

    def P(x, y):  # Rohbild-Koordinaten -> Bildschirm
        return [round((x - X0) * s, 1), round((y - Y0) * s, 1)]

    scene = {
        "source": "assets/raw/bg.png", "crop": [X0, Y0, X0 + crop.shape[1], Y1], "scale": round(s, 5),
        "horizon_y": hy,
        "lamp": P(1083, 148), "lantern": P(825, 400), "window": P(200, 467),
        "chimney": P(152, 134), "smoke_pixels_removed": int(smoke.sum()),
    }
    (HERE / "assets" / "scene.json").write_text(json.dumps(scene, indent=1))
    art = HERE / "demo" / "art"
    art.mkdir(parents=True, exist_ok=True)
    for n in ("bg.png", "bg_mask.png"):
        shutil.copy(HERE / "assets" / n, art / n)
    print(json.dumps(scene))


if __name__ == "__main__":
    main()
