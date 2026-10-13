#!/usr/bin/env python3
"""Bereitet die KI-Miniatur (assets/raw/bg2.png, gpt-image 1536x1024) für die Demo auf.

    .venv/bin/python styles/buchmalerei/scripts/build_miniature.py

1. Mitgemalten Rauch über dem Schornstein entfernen (Rauch wird in Godot animiert): Maske aus hellen, unbunten
   Pixeln im Rauchfenster, aufgedickt, gefüllt mit demselben Bildstück 48 px weiter rechts (gleiche Zeilen:
   Wolkenband und Abendstreifen laufen fast waagerecht), Rand weich überblendet.
2. Auf das Miniaturfenster der Seite verkleinern: 1536 -> 792 px (Faktor 0,515625, Lanczos), 2 Zeilen oben und
   unten abschneiden -> 792x524.
3. Masken als RGB (nie im Alphakanal, siehe PIPELINE.md): R = Blattgold (Farbton 36-58°, Sättigung > 0,38,
   Helligkeit > 0,42, nur über der Horizontlinie plus goldene Spiegelstriche im Wasser, ohne Lampe),
   G = Wasser (blaue Pixel unter dem Horizont, geschlossen, damit die weißen Wellenkringel dazugehören; danach
       nur blaue, weißliche und goldene Pixel, damit Masten und Wanten nicht mitwabern),
   B = Licht der Laterne (helle warme Pixel im Laternenglas).
4. mini_nocrest.png: Miniatur, in der die weißen Wellenkringel durch das umgebende Blau ersetzt sind.
5. miniature.json: Lage von Horizont, Schornstein, Leuchtfeuer, Laterne und Kai in Fensterkoordinaten.
"""
import json, pathlib

import numpy as np
from PIL import Image, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "assets/raw/bg2.png"
OUT = ROOT / "assets"
S = 792 / 1536
CROP_TOP = 2
WIN = (792, 524)


def hsv(a):
    a = a.astype(np.float32) / 255.0
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(-1), a.min(-1)
    d = mx - mn
    h = np.zeros_like(mx)
    m = d > 1e-6
    rr = m & (mx == r)
    gg = m & (mx == g) & ~rr
    bb = m & ~rr & ~gg
    h[rr] = ((g - b)[rr] / d[rr]) % 6
    h[gg] = (b - r)[gg] / d[gg] + 2
    h[bb] = (r - g)[bb] / d[bb] + 4
    h *= 60
    s = np.where(mx > 0, d / np.maximum(mx, 1e-6), 0)
    return h, s, mx


def dilate(m, r):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy > r * r:
                continue
            out |= np.roll(np.roll(m, dy, 0), dx, 1)
    return out


def erode(m, r):
    return ~dilate(~m, r)


def main():
    src = np.array(Image.open(RAW).convert("RGB"))
    H, W = src.shape[:2]
    h, s, v = hsv(src)

    # 1. Rauch entfernen
    yy, xx = np.mgrid[0:H, 0:W]
    box = (xx >= 92) & (xx <= 168) & (yy >= 214) & (yy <= 344)
    smoke = box & (s < 0.30) & (v > 0.52)
    smoke = dilate(smoke, 4) & box
    fill = np.roll(src, -48, axis=1)
    alpha = np.array(Image.fromarray((smoke * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2.0)),
                     np.float32)[..., None] / 255.0
    alpha *= box[..., None]
    clean = (src * (1 - alpha) + fill * alpha).round().astype(np.uint8)
    print("Rauchpixel", int(smoke.sum()))

    # 2. verkleinern
    big = Image.fromarray(clean)
    small = big.resize((WIN[0], round(H * S)), Image.LANCZOS)
    small = small.crop((0, CROP_TOP, WIN[0], CROP_TOP + WIN[1]))
    small.save(OUT / "miniature.png")

    # 3. Masken in Quellauflösung, dann verkleinern
    horizon = 386
    gold = (h >= 36) & (h <= 58) & (s > 0.38) & (v > 0.42)
    lamp_box = (xx >= 1290) & (xx <= 1350) & (yy >= 50) & (yy <= 120)
    sky_gold = gold & (yy < 330) & ~lamp_box
    water_zone = (yy > horizon + 4)
    blue = (h >= 195) & (h <= 250) & (s > 0.30)
    water = blue & water_zone
    water = erode(dilate(water, 7), 7) & water_zone
    # nach dem Schließen nur blaue, weißliche (Wellenkringel) und goldene (Spiegelstriche) Pixel behalten:
    # Masten, Wanten und Pfähle (braun, dunkel) fallen wieder heraus
    whitish = (s < 0.28) & (v > 0.55)
    water &= blue | whitish | gold
    # Wasserfläche: nur, was mit großen blauen Flächen zusammenhängt (Boote, Steg, Kai, Fels fallen heraus)
    water &= ~((v > 0.8) & (s > 0.35) & ~blue)  # helle bunte Flecken (Laternenlicht) nicht
    refl_gold = gold & water & (v > 0.5)
    lantern = (xx >= 1096) & (xx <= 1131) & (yy >= 618) & (yy <= 664) & (v > 0.55) & (h > 18) & (h < 60) & (s > 0.3)

    def shrink(m):
        im = Image.fromarray((m * 255).astype(np.uint8)).resize((WIN[0], round(H * S)), Image.BOX)
        return np.array(im.crop((0, CROP_TOP, WIN[0], CROP_TOP + WIN[1])))

    R = shrink(sky_gold | refl_gold)
    G = shrink(water)
    B = shrink(dilate(lantern, 2))
    Image.fromarray(np.dstack([R, G, B])).save(OUT / "mini_mask.png")

    # 5. Wasser ohne Wellenkringel (für das Kommen und Gehen der Kringel im Shader): weißliche Pixel im Wasser
    #    (1 px aufgedickt) durch den Mittelwert der übrigen Wasserpixel im 11x11-Fenster ersetzen
    sm = np.array(small).astype(np.float32)
    h2, s2, v2 = hsv(sm.astype(np.uint8))
    wat = G > 127
    crest = dilate(wat & (s2 < 0.32) & (v2 > 0.5), 1) & wat
    keep = (wat & ~crest).astype(np.float32)

    def box(a, r):
        c = np.pad(a, ((r + 1, r), (r + 1, r)), mode="edge").cumsum(0).cumsum(1)
        return c[2 * r + 1:, 2 * r + 1:] - c[:-2 * r - 1, 2 * r + 1:] - c[2 * r + 1:, :-2 * r - 1] + c[:-2 * r - 1, :-2 * r - 1]

    wsum = box(keep, 5)
    fill = np.dstack([box(sm[..., i] * keep, 5) for i in range(3)]) / np.maximum(wsum, 1e-3)[..., None]
    nocrest = sm.copy()
    nocrest[crest] = fill[crest]
    Image.fromarray(np.clip(nocrest, 0, 255).round().astype(np.uint8)).save(OUT / "mini_nocrest.png")
    print("Kringelpixel", int(crest.sum()))

    def to_win(x, y):
        return [round(x * S, 1), round(y * S - CROP_TOP, 1)]

    ly, lx = np.nonzero(lantern)
    info = {
        "source": "assets/raw/bg2.png",
        "scale": S, "crop_top": CROP_TOP, "size": list(WIN),
        "horizon_y": to_win(0, horizon)[1],
        "chimney_top": to_win(113, 344),
        "lighthouse_lamp": to_win(1319, 84),
        "lantern": to_win(float(lx.mean()), float(ly.mean())),
        "quay_back_y": to_win(0, 785)[1],
        "gold_px": int((R > 127).sum()), "water_px": int((G > 127).sum()), "lantern_px": int((B > 127).sum()),
    }
    (OUT / "miniature.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info))


if __name__ == "__main__":
    main()
