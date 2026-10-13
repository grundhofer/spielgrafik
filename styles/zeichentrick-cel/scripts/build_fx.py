#!/usr/bin/env python3
"""Effekt-Zeichnungen als Cels (wie in der Effektabteilung des Zeichentricks): Möwe im Flügelschlag, Funkeln des
Leuchtfeuers, weicher Lichthof. Gezeichnet in vierfacher Größe mit Pillow, dann verkleinert.

    .venv/bin/python styles/zeichentrick-cel/scripts/build_fx.py

Ergebnis in assets/fx/: gull.png (4 Bilder à 56x40 nebeneinander), twinkle.png (3 Bilder à 64x64), glow.png (128x128,
weiß mit weich abfallendem Alpha für additive Lichthöfe, entspricht dem Diffusions-Leuchten der Trickkamera).
Farben im Abendfarbmodell des Dachses (Tusche wie dessen Linie).
"""
import json, pathlib

import numpy as np
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/fx"
S = 4


def ink():
    m = json.loads((ROOT / "assets/cel/cels.json").read_text())
    return tuple(m["sheet"]["ink_dusk"])


def P(pts, ox=0, oy=0):
    return [((x + ox) * S, (y + oy) * S) for x, y in pts]


def gull(phase, W=56, H=40):
    """Möwe von der Seite, fliegt nach rechts. phase 0 = Flügel oben, 1 = waagerecht, 2 = unten."""
    im = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    k = ink()
    lw = int(1.4 * S)
    white, shade, grey, dark, beak = (222, 218, 230), (170, 166, 192), (132, 134, 160), (70, 70, 96), (226, 168, 62)
    sx, sy = 29, 21  # Schulter
    wings = {
        0: ([(sx + 3, sy - 1), (sx + 2, sy - 9), (sx - 3, sy - 17), (sx - 7, sy - 18), (sx - 5, sy - 10),
             (sx - 9, sy - 4), (sx - 3, sy + 1)], (-3, -3)),
        1: ([(sx + 3, sy - 1), (sx - 6, sy - 4), (sx - 19, sy - 4), (sx - 21, sy - 2), (sx - 12, sy + 0),
             (sx - 3, sy + 2)], (-2, -2)),
        2: ([(sx + 3, sy), (sx + 1, sy + 7), (sx - 4, sy + 14), (sx - 8, sy + 15), (sx - 6, sy + 8),
             (sx - 9, sy + 3), (sx - 3, sy + 1)], (-3, 2)),
    }
    pts, off = wings[phase]
    # ferner Flügel: dieselbe Form, versetzt und dunkler (liegt hinter dem Körper)
    d.polygon(P([(x + off[0], y + off[1]) for x, y in pts]), fill=grey, outline=k, width=lw)
    # Schwanz, Körper, Bauchschatten
    d.polygon(P([(15, 21), (8, 18.5), (8, 24.5)]), fill=shade, outline=k, width=lw)
    d.ellipse(P([(12, 16.5)])[0] + P([(37, 26)])[0], fill=white, outline=k, width=lw)
    d.chord(P([(14, 17.5)])[0] + P([(35.5, 25)])[0], 20, 160, fill=shade)
    # Kopf und Schnabel
    d.polygon(P([(42, 19), (48.5, 20.3), (42, 21.8)]), fill=beak, outline=k, width=lw)
    d.ellipse(P([(35, 14.5)])[0] + P([(44, 23.5)])[0], fill=white, outline=k, width=lw)
    d.ellipse(P([(39.6, 17.2)])[0] + P([(41.3, 18.9)])[0], fill=k)
    # naher Flügel, Spitze dunkel
    d.polygon(P(pts), fill=white, outline=k, width=lw)
    tip = pts[2:4]
    if phase == 1:
        d.polygon(P([pts[2], pts[3], pts[4]]), fill=dark)
    else:
        d.polygon(P([pts[2], pts[3], pts[4]]), fill=dark)
    d.polygon(P(pts), outline=k, width=lw)
    return im.resize((W, H), Image.LANCZOS)


def twinkle(r, W=64):
    """Vierzackiger Stern (Leuchtfeuer-Funkeln), helles Gelb mit warmer Farblinie statt Tusche."""
    im = Image.new("RGBA", (W * S, W * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = W / 2
    pts = []
    for i in range(8):
        a = np.pi / 4 * i - np.pi / 2
        rr = r if i % 2 == 0 else r * 0.22
        pts.append((c + rr * np.cos(a), c + rr * np.sin(a)))
    d.polygon(P(pts), fill=(255, 246, 196), outline=(240, 160, 60), width=int(1.5 * S))
    inner = [(c + (x - c) * 0.45, c + (y - c) * 0.45) for x, y in pts]
    d.polygon(P(inner), fill=(255, 255, 240))
    return im.resize((W, W), Image.LANCZOS)


def glow(W=128):
    y, x = np.mgrid[:W, :W] + 0.5
    r = np.hypot(x - W / 2, y - W / 2) / (W / 2)
    a = np.clip(np.exp(-(r / 0.42) ** 2) - np.exp(-(1 / 0.42) ** 2), 0, 1)
    a = a / a.max()
    arr = np.zeros((W, W, 4), np.uint8)
    arr[..., :3] = 255
    arr[..., 3] = (a * 255).round().astype(np.uint8)
    return Image.fromarray(arr)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    phases = [0, 1, 2, 1]  # oben, Mitte, unten, Mitte (Rückweg)
    W, H = 56, 40
    sheet = Image.new("RGBA", (W * len(phases), H), (0, 0, 0, 0))
    for i, p in enumerate(phases):
        sheet.alpha_composite(gull(p, W, H), (i * W, 0))
    sheet.save(OUT / "gull.png")
    tw = Image.new("RGBA", (64 * 3, 64), (0, 0, 0, 0))
    for i, r in enumerate([13, 29, 20]):
        tw.alpha_composite(twinkle(r), (i * 64, 0))
    tw.save(OUT / "twinkle.png")
    glow().save(OUT / "glow.png")
    print("ok", OUT)


if __name__ == "__main__":
    main()
