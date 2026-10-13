#!/usr/bin/env python3
"""Zerlegt die Vorderansicht des gemeinsamen Referenzblatts in Körper, Schalende und Lider.

    .venv/bin/python styles/tageszeit-wetter/tools/prep_badger.py [--height 172] [--debug DIR]

Quelle (nur lesend): shared/badger/master_sheet_alpha.png, linke Figur (Vorderansicht). Keine KI-Erzeugung:
Der Hintergrund dieses Eintrags ist im selben Zeichenstil (dunkle Kontur, weiche Zellschattierung) erzeugt,
deshalb passt die Figur ohne Übermalung. Die Figur trägt kein eigenes Licht; Tönung, Lampenlicht und Nebel
setzt der Shader je Zustand.

Ausgang assets/ und demo/art/: badger_body.png (Schalende entfernt, dahinter aufgefüllt), badger_scarf.png
(nur das hängende Schalende), badger_lids.png (geschlossene Lider), badger.json (Maße in Sprite-Pixeln).
Fester Bezug auf das Referenzblatt (Pixel im Blatt 1536×1024): Augenmitten und Schalbereich unten.
"""
import argparse, json, pathlib, shutil, sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import imgops as io  # noqa: E402

ENTRY = pathlib.Path(__file__).resolve().parent.parent
ROOT = ENTRY.parents[1]
SHEET = ROOT / "shared" / "badger" / "master_sheet_alpha.png"
OUT, ART = ENTRY / "assets", ENTRY / "demo" / "art"

BOX = (4, 79, 540, 891)                 # Vorderansicht samt Rand (Figur 12..529 × 87..882)
EYES = [(228.75, 231.25), (330.5, 232.5)]
EYE_R = (15.0, 14.0)
SCARF = (292, 368, 402, 562)            # hängendes Schalende (x0, y0, x1, y1) im Blatt
FEET_Y = 882                            # unterste Figurzeile im Blatt


def dilate(b, r):
    return io.box(b.astype(np.float32), r) > 1e-3


def erode(b, r):
    return io.box(b.astype(np.float32), r) > 1 - 1e-3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--height", type=float, default=172.0, help="Figurenhöhe in Bildpixeln (720p)")
    ap.add_argument("--debug", default="")
    a = ap.parse_args()

    rgba = io.load(SHEET, "RGBA")
    c, al = rgba[..., :3], rgba[..., 3]

    # Farbsaum: Randpixel (Alpha < 0,98) bekommen die Farbe des nächsten deckenden Pixels
    opaque = (al > 0.98).astype(np.float32)
    fill = io.pull_push(c, opaque)
    c = np.where((al > 0.98)[..., None], c, fill)

    # Hängendes Schalende: rote Pixel im Bereich, Lücken bis 3 px geschlossen, Kontur (2 px) dazu
    red = (c[..., 0] > 0.35) & (c[..., 0] > c[..., 1] * 1.8) & (c[..., 0] > c[..., 2] * 1.6) & (al > 0.5)
    region = np.zeros_like(red)
    x0, y0, x1, y1 = SCARF
    region[y0:y1, x0:x1] = True
    sc = red & region
    sc = erode(dilate(sc, 3), 3) | sc
    sc = dilate(sc, 2) & region & (al > 0.02)
    # weicher Übergang oben (Ansatz am Halswickel), damit dort keine Kante entsteht
    yy = np.arange(c.shape[0])[:, None]
    ramp = np.clip((yy - y0) / 14.0, 0, 1)
    scarf_a = sc.astype(np.float32) * al * ramp

    # Körper: unter dem Schalende aus der Umgebung auffüllen (sichtbar wird davon nur ein Rand von 1–2 px)
    # zeilenweise zwischen den Farben links und rechts der Lücke (Weste), nicht rundum (roter Halswickel)
    hole = dilate(sc, 1)
    body_c = c.copy()
    for y in range(y0, y1):
        xs = np.nonzero(hole[y, x0 - 6:x1 + 6])[0]
        if not len(xs):
            continue
        l, r = x0 - 6 + xs.min(), x0 - 6 + xs.max()
        cl = np.median(c[y, max(l - 4, 0):l], 0)
        cr = np.median(c[y, r + 1:r + 5], 0)
        t = np.linspace(0, 1, r - l + 1)[:, None]
        body_c[y, l:r + 1] = np.where(hole[y, l:r + 1, None], cl * (1 - t) + cr * t, c[y, l:r + 1])
    body_c = np.where(hole[..., None], io.box(body_c, 1), body_c)
    body_a = al.copy()

    # Lider: Ellipse in der Fellfarbe um das Auge, unten eine dunkle Lidlinie
    lids = Image.new("RGBA", (c.shape[1], c.shape[0]), (0, 0, 0, 0))
    d = ImageDraw.Draw(lids)
    yy2, xx2 = np.mgrid[0:c.shape[0], 0:c.shape[1]]
    for ex, ey in EYES:
        ring = (((xx2 - ex) / (EYE_R[0] + 6)) ** 2 + ((yy2 - ey) / (EYE_R[1] + 6)) ** 2 <= 1) & \
               (((xx2 - ex) / (EYE_R[0] + 2)) ** 2 + ((yy2 - ey) / (EYE_R[1] + 2)) ** 2 > 1)
        fur = np.median(c[ring & (al > 0.9)], 0)
        col = tuple(int(v * 255) for v in fur) + (255,)
        rx, ry = EYE_R
        d.ellipse([ex - rx, ey - ry, ex + rx, ey + ry], fill=col)
        line = tuple(int(v * 255 * 0.35) for v in fur) + (255,)
        d.arc([ex - rx, ey - ry * 0.9, ex + rx, ey + ry * 0.55], 15, 165, fill=line, width=4)
    lids_a = np.asarray(lids, np.float32) / 255

    # Ausschnitt und vormultipliziert verkleinern
    bx0, by0, bx1, by1 = BOX
    fig_h = FEET_Y - 87 + 1
    k = a.height / fig_h
    tw, th = int(round((bx1 - bx0) * k)), int(round((by1 - by0) * k))

    def shrink(col, alpha):
        col, alpha = col[by0:by1, bx0:bx1], alpha[by0:by1, bx0:bx1]
        pm = io.resize(col * alpha[..., None], (tw, th), Image.LANCZOS)
        aa = np.clip(io.resize(alpha, (tw, th), Image.LANCZOS), 0, 1)
        out = np.clip(pm / np.maximum(aa, 1e-4)[..., None], 0, 1)
        return np.concatenate([out, aa[..., None]], -1)

    body = shrink(body_c, body_a)
    scarf = shrink(c, scarf_a)
    lid = shrink(lids_a[..., :3], lids_a[..., 3])
    feet = (FEET_Y + 1 - by0) * k
    meta = {
        "size": [tw, th], "scale": round(k, 5), "feet_y": round(feet, 2),
        "figure_height": round(a.height, 1),
        "scarf_root_y": round((y0 + 10 - by0) * k, 2), "scarf_tip_y": round((y1 - by0) * k, 2),
        "scarf_x": [round((x0 - bx0) * k, 2), round((x1 - bx0) * k, 2)],
        "eyes": [[round((ex - bx0) * k, 2), round((ey - by0) * k, 2)] for ex, ey in EYES],
        "source": "shared/badger/master_sheet_alpha.png (Vorderansicht)",
    }
    OUT.mkdir(exist_ok=True)
    ART.mkdir(parents=True, exist_ok=True)
    for name, arr in (("badger_body.png", body), ("badger_scarf.png", scarf), ("badger_lids.png", lid)):
        io.save(OUT / name, arr)
        shutil.copy2(OUT / name, ART / name)
    (OUT / "badger.json").write_text(json.dumps(meta, indent=1))
    shutil.copy2(OUT / "badger.json", ART / "badger.json")
    print(json.dumps(meta))
    if a.debug:
        dbg = pathlib.Path(a.debug)
        dbg.mkdir(parents=True, exist_ok=True)
        prev = Image.new("RGBA", (tw * 3 * 3, th * 3), (40, 50, 70, 255))
        for i, arr in enumerate((body, scarf, lid)):
            im = Image.fromarray((arr * 255).astype(np.uint8)).resize((tw * 3, th * 3), Image.NEAREST)
            prev.alpha_composite(im, (i * tw * 3, 0))
        prev.save(dbg / "badger_parts.png")


if __name__ == "__main__":
    main()
