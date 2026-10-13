#!/usr/bin/env python3
"""Dachs-Kurier als Schnittfigur aus EINEM gemalten Bild (nur lesend: shared/badger/walk_painted.png, Bild 3).

Warum keine Einzelbilder: Die sechs KI-Laufbilder des gemeinsamen Blatts bilden keinen sauberen Zyklus. Zwischen
Durchschwung (Bild 3) und dem nächsten Bild mit Standfuß fehlt die Hochphase; der Standfuß springt dort um
~120 px Quellmaß (gemessen, siehe NOTES.md; dieselbe Beobachtung steht in styles/painterly-digital). Abgespielt mit
gemessenem Vorschub ergäbe das einen Satz von ~12 px in einem Bild. Deshalb: Rumpf und ein Bein ausschneiden, in
Godot das Bein als nahes und (abgedunkelt) fernes Bein drehen und den Standfuß rechnerisch festhalten.

Landmarken (Hüfte, Ferse, Zehe, Schnittlinie, Beinpolygon) wurden am Bild nachgemessen; sie stimmen mit denen von
styles/painterly-digital/scripts/build_badger.py überein (dort zuerst ermittelt). Die Hüfte liegt über der Mitte der
Sohle, damit Ferse und Zehe symmetrisch zur Drehachse liegen (gleiche Hüfthöhe beim Abrollen über Ferse und Zehe).
"""
import pathlib

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = ROOT / "shared" / "badger" / "walk_painted.png"
BOX = (735, 90, 1062, 662)           # Bild 3 im Blatt (Quellpixel)
TOP, SOLE = 111, 645                 # Mützenspitze und Fußsohle
HIP = (939, 500)
HEEL = (884, 645)
TOE = (994, 645)                     # Sohle waagerecht angenommen (gemessen 641; 4 px Quellmaß = 0,4 px Endmaß)
CUT_Y, CUT_FEATHER = 544, 6          # Rumpf endet hier (gezackte Fellkante)
LEG_POLY = [(868, 488), (942, 488), (960, 540), (966, 590), (996, 614), (1004, 652), (878, 652), (873, 600),
            (857, 560), (855, 520)]
LEG_FEATHER = (490, 516)             # Bein blendet oben weich aus (liegt dort unter dem Rumpf)


def _downscale(im, k):
    """Vormultipliziert mit Lanczos verkleinern, Überschwinger begrenzen (keine hellen oder dunklen Säume)."""
    arr = np.asarray(im).astype(np.float32)
    pm = np.dstack([arr[..., :3] * arr[..., 3:4] / 255.0, arr[..., 3:4]])
    size = (max(1, round(im.width * k)), max(1, round(im.height * k)))
    ch = [np.asarray(Image.fromarray(pm[..., c], "F").resize(size, Image.LANCZOS)) for c in range(4)]
    sm = np.dstack(ch)
    al = np.clip(sm[..., 3:4], 0, 255)
    prgb = np.clip(sm[..., :3], 0, al)
    rgb = np.where(al > 0.5, prgb * 255.0 / np.maximum(al, 1e-3), 0)
    return Image.fromarray(np.dstack([rgb, al]).clip(0, 255).round().astype(np.uint8), "RGBA")


def build(height_px):
    """Liefert (body, leg, rig): Teile in Endgröße und Maße relativ zur Hüfte (Endpixel)."""
    k = height_px / (SOLE - TOP)
    src = Image.open(SRC).convert("RGBA").crop(BOX)
    a = np.asarray(src).astype(np.float32)
    h, w, _ = a.shape
    yy, xx = np.mgrid[0:h, 0:w]
    Y = yy + BOX[1]
    xs = np.arange(w) + BOX[0]
    rng = np.random.default_rng(7)
    tuft = np.repeat(rng.uniform(-1, 1, w // 7 + 2), 7)[:w]
    edge = CUT_Y + 5.0 * np.abs(np.sin((xs - 780) * np.pi / 9.0)) + 3.0 * tuft
    body_m = np.clip((edge[None, :] + CUT_FEATHER / 2 - Y) / (CUT_FEATHER / 2), 0, 1)
    pm = Image.new("L", (w, h), 0)
    ImageDraw.Draw(pm).polygon([(x - BOX[0], y - BOX[1]) for x, y in LEG_POLY], fill=255)
    pm = np.asarray(pm.filter(ImageFilter.GaussianBlur(1.0))) / 255.0
    leg_m = pm * np.clip((Y - LEG_FEATHER[0]) / (LEG_FEATHER[1] - LEG_FEATHER[0]), 0, 1)

    def part(mask):
        out = a.copy()
        out[..., 3] *= mask
        im = Image.fromarray(out.clip(0, 255).astype(np.uint8), "RGBA")
        al = np.asarray(im)[..., 3]
        ys, xs_ = np.nonzero(al > 2)
        # Ausschnitt so legen, dass die Hüfte nach dem Verkleinern auf einer ganzen Pixelkante liegt
        x0 = xs_.min() - 2
        y0 = ys.min() - 2
        x0 -= (1.0 - (HIP[0] - BOX[0] - x0) * k % 1) / k
        y0 -= (1.0 - (HIP[1] - BOX[1] - y0) * k % 1) / k
        x0, y0 = int(np.floor(x0)), int(np.floor(y0))
        x1, y1 = xs_.max() + 3, ys.max() + 3
        im = im.crop((x0, y0, x1, y1))
        res = _downscale(im, k)
        pivot = [round((HIP[0] - BOX[0] - x0) * k, 2), round((HIP[1] - BOX[1] - y0) * k, 2)]
        return res, pivot

    body, body_pivot = part(body_m)
    leg, leg_pivot = part(leg_m)

    def from_hip(p):
        return [round((p[0] - HIP[0]) * k, 3), round((p[1] - HIP[1]) * k, 3)]

    rig = {"scale": round(k, 5), "height_px": height_px, "body_pivot": body_pivot, "leg_pivot": leg_pivot,
           "heel": from_hip(HEEL), "toe": from_hip(TOE), "head_top": from_hip((965, TOP)),
           "source": "shared/badger/walk_painted.png, Bild 3 (Box %s)" % (BOX,)}
    return body, leg, rig


def preview(body, leg, rig, scale=4):
    """Rumpf + fernes (dunkles) und nahes Bein in Ruhe, vergrößert zur Sichtprüfung."""
    pv = Image.new("RGBA", (body.width + 30, body.height + 20), (70, 88, 96, 255))
    hip = (15 + rig["body_pivot"][0], 6 + rig["body_pivot"][1])
    fa = np.asarray(leg).astype(np.float32).copy()
    fa[..., :3] *= 0.62
    far = Image.fromarray(fa.astype(np.uint8), "RGBA")
    pv.alpha_composite(far, (round(hip[0] - rig["leg_pivot"][0] - 3), round(hip[1] - rig["leg_pivot"][1])))
    pv.alpha_composite(leg, (round(hip[0] - rig["leg_pivot"][0]), round(hip[1] - rig["leg_pivot"][1])))
    pv.alpha_composite(body, (15, 6))
    return pv.resize((pv.width * scale, pv.height * scale), Image.NEAREST)
