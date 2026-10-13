#!/usr/bin/env python3
"""Zerlegt die KI-Figur (assets/raw/badger.png, gpt-image mit echtem Alphakanal) in zwei Teile für eine
Schnittfiguren-Animation und verkleinert sie auf Spielgröße.

    .venv/bin/python styles/buchmalerei/scripts/build_badger.py [--height 330] [--preview out.png]

Teile:
  badger_arm.png   erhobener Unterarm mit Redegestus (zwei Finger), liegt HINTER dem Körper und dreht sich um die
                   Mitte der Ärmelmanschette. Nach unten verlängert (in Achsrichtung verschmiert), damit beim Drehen
                   unter der Manschette keine Lücke aufgeht.
  badger_body.png  alles andere, mit Manschette samt deren Kontur.
Trennung: Polygon um Unterarm und Hand (Quellkoordinaten); daraus wird die Manschette entfernt (cremefarbene
große Fläche, geöffnet, damit die weißen Glanzstriche des Fells nicht mitzählen, und um 9 px aufgedickt, damit ihre
Kontur beim Körper bleibt).
Verkleinern: vormultipliziertes Alpha, Lanczos, Höhe Fingerspitzen bis Sohle = --height.
badger.json: Bildgröße, Fußpunkt (Mitte der Sohlen, Unterkante), Drehpunkt des Arms (in beiden Bildern gleich,
beide Teile haben dieselbe Leinwand), Maßstab.
"""
import argparse, json, pathlib

import numpy as np
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "assets/raw/badger.png"
OUT = ROOT / "assets"

# Quellkoordinaten (1024x1536), gemessen an assets/raw/badger.png
ARM_POLY = [(800, 70), (1010, 70), (1010, 440), (965, 520), (930, 515), (800, 432), (788, 380), (786, 220)]
CUFF_BOX = (770, 400, 1010, 640)        # hier wird die Manschette gesucht
PIVOT_SRC = (872, 478)                  # Mitte der Manschettenöffnung
AXIS_DOWN = np.array([-0.18, 1.0])      # Richtung vom Handgelenk zur Manschette (verlängert den Arm nach unten)
PAD = 70                                # Rand der Leinwand in Quellpixeln (Platz für den gedrehten Arm)


def dilate(m, r):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r:
                out |= np.roll(np.roll(m, dy, 0), dx, 1)
    return out


def erode(m, r):
    return ~dilate(~m, r)


def premul_resize(a, size):
    f = a.astype(np.float32) / 255.0
    rgb = f[..., :3] * f[..., 3:4]
    al = f[..., 3]
    rs = [np.array(Image.fromarray(rgb[..., i]).resize(size, Image.LANCZOS)) for i in range(3)]
    ra = np.clip(np.array(Image.fromarray(al).resize(size, Image.LANCZOS)), 0, 1)
    rgb2 = np.stack(rs, -1) / np.maximum(ra[..., None], 1e-4)
    out = np.dstack([np.clip(rgb2, 0, 1), ra])
    out[ra < 1 / 255.0] = 0
    return (out * 255).round().astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--height", type=int, default=330)
    ap.add_argument("--preview")
    a = ap.parse_args()

    src0 = np.array(Image.open(RAW).convert("RGBA"))
    # rundum PAD Pixel Rand, damit der gedrehte Arm nicht am Bildrand abgeschnitten wird
    src = np.zeros((src0.shape[0] + 2 * PAD, src0.shape[1] + 2 * PAD, 4), np.uint8)
    src[PAD:-PAD, PAD:-PAD] = src0
    H, W = src.shape[:2]
    al = src[..., 3] > 128
    ys, xs = np.nonzero(al)
    top, bot = ys.min(), ys.max()
    # Sohle: unterste Zeile mit nennenswert vielen Pixeln (Krallenspitzen ragen einzeln tiefer)
    rows = al.sum(1)
    sole = max(y for y in range(H) if rows[y] > 60)

    poly = Image.new("L", (W, H), 0)
    ImageDraw.Draw(poly).polygon([(x + PAD, y + PAD) for x, y in ARM_POLY], fill=255)
    poly = np.array(poly) > 0

    f = src[..., :3].astype(np.float32) / 255.0
    mx, mn = f.max(-1), f.min(-1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    yy, xx = np.mgrid[0:H, 0:W]
    x0, y0, x1, y1 = [v + PAD for v in CUFF_BOX]
    inbox = (xx >= x0) & (xx < x1) & (yy >= y0) & (yy < y1)
    cream = al & inbox & (mx > 0.62) & (sat < 0.38)
    cream = dilate(erode(cream, 4), 4)
    cuff = dilate(cream, 9) & al
    # auch halbtransparente Randpixel gehören zum Arm, sonst bleibt ein Geisterumriss im Körper
    arm = poly & (src[..., 3] > 0) & ~cuff
    print("Armpixel", int(arm.sum()), "Manschette", int(cuff.sum()))

    arm_rgba = src.copy()
    arm_rgba[~arm] = 0
    body_rgba = src.copy()
    body_rgba[arm] = 0

    # Arm nach unten verlängern (verdeckt hinter der Manschette)
    ext = np.zeros_like(arm_rgba)
    d = AXIS_DOWN / np.linalg.norm(AXIS_DOWN)
    for k in range(60, 0, -2):
        dx, dy = int(round(d[0] * k)), int(round(d[1] * k))
        sh = np.roll(np.roll(arm_rgba, dy, 0), dx, 1)
        m = sh[..., 3] > 0
        ext[m] = sh[m]
    m = arm_rgba[..., 3] > 0
    ext[m] = arm_rgba[m]
    # Verlängerung nur unterhalb der Schnittkante und innerhalb der Manschette sichtbar halten
    ext[(ext[..., 3] > 0) & ~(m | cuff | dilate(m, 2))] = 0

    # Leinwand: Bounding Box + Rand
    cx0, cy0 = xs.min() - 8, top - 24
    cx1, cy1 = xs.max() + PAD, sole + 4
    s = a.height / float(sole - top)
    size = (round((cx1 - cx0) * s), round((cy1 - cy0) * s))

    def cut(rgba):
        return premul_resize(rgba[cy0:cy1, cx0:cx1], size)

    body = cut(body_rgba)
    armp = cut(ext)
    Image.fromarray(body).save(OUT / "badger_body.png")
    Image.fromarray(armp).save(OUT / "badger_arm.png")

    # Fußpunkt: Mitte der Sohlen in der Sohlenzeile
    sole_cols = np.nonzero(al[sole - 6])[0]
    foot_x = (sole_cols.min() + sole_cols.max()) / 2.0
    info = {
        "source": "assets/raw/badger.png", "scale": s, "size": list(size),
        "crop_src": [int(cx0 - PAD), int(cy0 - PAD), int(cx1 - PAD), int(cy1 - PAD)],
        "foot": [round((foot_x - cx0) * s, 2), round((sole - cy0) * s, 2)],
        "pivot": [round((PIVOT_SRC[0] + PAD - cx0) * s, 2), round((PIVOT_SRC[1] + PAD - cy0) * s, 2)],
        "height_px": a.height,
        "top_src": int(top - PAD), "sole_src": int(sole - PAD),
    }
    (OUT / "badger.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info))

    if a.preview:
        tiles = []
        for ang in (-6, 0, 8, 16, 24):
            can = Image.new("RGBA", size, (226, 210, 170, 255))
            ar = Image.fromarray(armp).rotate(-ang, resample=Image.BICUBIC, center=tuple(info["pivot"]))
            can.alpha_composite(ar)
            can.alpha_composite(Image.fromarray(body))
            tiles.append(can)
        sheet = Image.new("RGB", (size[0] * len(tiles), size[1]))
        for i, t in enumerate(tiles):
            sheet.paste(t, (i * size[0], 0))
        sheet = sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST)
        sheet.save(a.preview)


if __name__ == "__main__":
    main()
