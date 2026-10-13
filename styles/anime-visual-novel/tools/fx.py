#!/usr/bin/env python3
"""Effekt-Texturen für den Eintrag anime-visual-novel, ganz aus Code (Pillow + NumPy, kein KI-Bild).

Aufruf aus dem Projektordner:
    .venv/bin/python styles/anime-visual-novel/tools/fx.py

Alle Formen werden 4-fach überabgetastet gezeichnet und dann verkleinert: saubere, glatte Kanten wie bei
Cel-Animation. Ausgabe nach assets/fx/ und als Kopie nach demo/art/fx/.
  sparkle.png   Vierstrahliger Funkelstern (Wasserglitzern, Sterne)
  glow.png      Weicher runder Lichthof (Laterne, Fenster, Lampe)
  flare.png     Strahlenkranz mit dünnen Strahlen (Lampenhaus)
  beam.png      Lichtkegel des Leuchtturms, am Lampenhaus schmal, nach außen breiter und blasser
  puff1-3.png   Rauchwolken mit zwei harten Tönen (Licht oben, Schatten unten), weiß; Farbe kommt aus Godot
  gull.png      Möwe, 4 Flügelstellungen nebeneinander (hframes = 4), Cel-Schattierung mit Kontur
  gull_near.png Große Möwe für den Vorbeiflug vor der Kamera (4 x 512x256), Gegenlicht, Kontur wie die Figur
  emote.png     Drei Schreck-Striche (Manga-Zeichen für Überraschung)
"""
import math, pathlib, shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SD = pathlib.Path(__file__).resolve().parent.parent
OUT = SD / "assets" / "fx"
DEMO = SD / "demo" / "art" / "fx"
SS = 4  # Überabtastung


def save(im, name):
    OUT.mkdir(parents=True, exist_ok=True)
    DEMO.mkdir(parents=True, exist_ok=True)
    im.save(OUT / name, optimize=True)
    shutil.copy2(OUT / name, DEMO / name)
    print(f"assets/fx/{name}  {im.size[0]}x{im.size[1]}")


def down(im, size):
    return im.resize(size, Image.LANCZOS)


def radial(w, h, power=1.0):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((x - (w - 1) / 2) / (w / 2)) ** 2 + ((y - (h - 1) / 2) / (h / 2)) ** 2)
    return np.clip(1 - r, 0, 1) ** power


def white_alpha(a):
    a = np.clip(a, 0, 1)
    rgba = np.zeros(a.shape + (4,), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = (a * 255).round().astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def sparkle():
    n = 96
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    c = (n - 1) / 2
    dx, dy = np.abs(x - c) / c, np.abs(y - c) / c
    # zwei schlanke Strahlen (waagerecht länger), dazu ein schwaches Diagonalkreuz und ein heller Kern
    ray_h = np.clip(1 - dx, 0, 1) ** 1.6 * np.exp(-(dy * 26) ** 2)
    ray_v = np.clip(1 - dy * 1.25, 0, 1) ** 1.6 * np.exp(-(dx * 26) ** 2)
    u, v = (x - c + y - c) / (c * 1.414), (x - c - (y - c)) / (c * 1.414)
    diag = (np.clip(1 - np.abs(u) * 2.4, 0, 1) * np.exp(-(v * 30) ** 2)
            + np.clip(1 - np.abs(v) * 2.4, 0, 1) * np.exp(-(u * 30) ** 2)) * 0.35
    core = np.exp(-((dx ** 2 + dy ** 2) * 60))
    halo = np.exp(-((dx ** 2 + dy ** 2) * 9)) * 0.25
    save(white_alpha(ray_h + ray_v + diag + core + halo), "sparkle.png")


def glow():
    a = radial(256, 256, 2.2)
    save(white_alpha(a), "glow.png")


def flare():
    n = 256
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    c = (n - 1) / 2
    ang = np.arctan2(y - c, x - c)
    r = np.sqrt((x - c) ** 2 + (y - c) ** 2) / c
    rng = np.random.default_rng(7)
    rays = np.zeros_like(r)
    for k in range(14):
        a0 = k * math.tau / 14 + rng.uniform(-0.08, 0.08)
        length = rng.uniform(0.45, 1.0) if k % 2 else 1.0
        width = rng.uniform(0.012, 0.022)
        d = np.angle(np.exp(1j * (ang - a0)))
        rays += np.exp(-(d / width) ** 2) * np.clip(1 - r / length, 0, 1) ** 2
    core = np.exp(-(r * 6) ** 2) + 0.3 * np.exp(-(r * 2.2) ** 2)
    save(white_alpha(rays * 0.8 + core), "flare.png")


def beam():
    w, h = 640, 160
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    u = x / (w - 1)                      # 0 am Lampenhaus, 1 am Ende
    half = 0.05 + 0.45 * u               # halbe Breite relativ zur Höhe
    v = np.abs(y - (h - 1) / 2) / ((h - 1) / 2)
    edge = np.clip((half - v) / (0.25 * half + 0.02), 0, 1)    # weiche, aber klare Kegelkante
    core = np.exp(-(v / (half * 0.45 + 0.01)) ** 2) * 0.5
    fall = (1 - u) ** 1.3 * np.clip(u * 12, 0, 1)
    save(white_alpha((edge * 0.55 + core) * fall), "beam.png")


def cel_puff(seed, name):
    """Rauchwolke wie im Anime-Hintergrund: Vereinigung weniger Kreise, Lichtseite oben, harter Schatten unten."""
    n = 128 * SS
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:n, 0:n].astype(np.float32) / n
    blobs = [(0.5, 0.56, 0.3)] + [(0.5 + rng.uniform(-0.2, 0.2), 0.5 + rng.uniform(-0.18, 0.1),
                                    rng.uniform(0.15, 0.22)) for _ in range(4)]
    inside = np.zeros((n, n), bool)
    for cx, cy, r in blobs:
        inside |= (x - cx) ** 2 + (y - cy) ** 2 < r ** 2
    # Schattenform: dieselben Kreise, nach unten rechts versetzt und etwas kleiner -> die Lichtkappe oben bleibt frei
    lit = np.zeros((n, n), bool)
    for cx, cy, r in blobs:
        lit |= (x - cx + 0.05) ** 2 + (y - cy + 0.07) ** 2 < (r * 0.92) ** 2
    rgba = np.zeros((n, n, 4), np.float32)
    rgba[..., 3] = inside
    # Rot = Lichtanteil (1 Licht, 0 Schatten); Grün/Blau = 1. Die Farben setzt der Puff-Shader in Godot.
    rgba[..., 0] = np.where(lit, 1.0, 0.0)
    rgba[..., 1] = 1.0
    rgba[..., 2] = 1.0
    im = Image.fromarray((rgba * 255).astype(np.uint8), "RGBA")
    save(down(im, (128, 128)), name)


def gull():
    """Möwe von schräg vorn als geschwungenes „M“ (typische Silhouette im Anime-Hintergrund).
    4 Flügelstellungen (oben, Mitte, unten, Mitte) als Streifen, je 128x80 Pixel, Kopf nach rechts."""
    fw, fh = 128, 80
    S = SS
    sheet = Image.new("RGBA", (fw * 4 * S, fh * S), (0, 0, 0, 0))
    ink = (58, 50, 74, 255)
    white = (252, 249, 244, 255)
    shade = (184, 178, 204, 255)
    tip = (44, 40, 58, 255)
    # (Winkel Oberarm, Winkel Handschwinge) in Grad, positiv = nach oben
    poses = [(48, 18), (12, -4), (-28, -48), (12, -4)]
    for k, (a1, a2) in enumerate(poses):
        im = Image.new("RGBA", (fw * S, fh * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        cx, cy = 64 * S, 44 * S

        def wing(side, scale):
            r1, r2 = math.radians(a1), math.radians(a2)
            sh = (cx + side * 4 * S, cy - 1 * S)
            wr = (sh[0] + side * 24 * S * scale * math.cos(r1), sh[1] - 24 * S * scale * math.sin(r1))
            tp = (wr[0] + side * 30 * S * scale * math.cos(r2), wr[1] - 30 * S * scale * math.sin(r2))
            # Vorderkante oben, Hinterkante unten; an der Hand schmaler
            th0, th1 = 9 * S * scale, 6 * S * scale
            nx1, ny1 = math.sin(r1) * side, math.cos(r1)
            nx2, ny2 = math.sin(r2) * side, math.cos(r2)
            poly = [sh, wr, tp,
                    (wr[0] + nx2 * th1 * 0.4 + side * 4 * S, wr[1] + ny2 * th1),
                    (sh[0] + nx1 * th0 * 0.3, sh[1] + ny1 * th0)]
            under = [(sh[0] + nx1 * th0 * 0.15, sh[1] + ny1 * th0 * 0.55),
                     (wr[0] + nx2 * th1 * 0.2, wr[1] + ny2 * th1 * 0.55),
                     (wr[0] + nx2 * th1 * 0.4 + side * 4 * S, wr[1] + ny2 * th1),
                     (sh[0] + nx1 * th0 * 0.3, sh[1] + ny1 * th0)]
            # schwarze Flügelspitze: letztes Drittel der Handschwinge
            f = 0.62
            p = (wr[0] + (tp[0] - wr[0]) * f, wr[1] + (tp[1] - wr[1]) * f)
            q = (p[0] + nx2 * th1 * 0.45, p[1] + ny2 * th1 * 0.6)
            return poly, under, [p, tp, q]

        # hinterer (linker) Flügel etwas kürzer und dunkler -> leichte Schrägsicht
        for side, sc, fill in ((-1, 0.82, shade), (1, 1.0, white)):
            poly, under, tipp = wing(side, sc)
            d.polygon(poly, fill=fill, outline=ink, width=S)
            d.polygon(under, fill=shade)
            d.polygon(tipp, fill=tip)
            d.line(poly + [poly[0]], fill=ink, width=S, joint="curve")
            if side < 0:
                # Körper zwischen den Flügeln, Kopf nach rechts, Schnabel
                d.ellipse([cx - 9 * S, cy - 5 * S, cx + 9 * S, cy + 6 * S], fill=white, outline=ink, width=S)
                d.chord([cx - 9 * S, cy - 5 * S, cx + 9 * S, cy + 6 * S], 10, 170, fill=shade)
                d.ellipse([cx + 4 * S, cy - 8 * S, cx + 13 * S, cy + 1 * S], fill=white, outline=ink, width=S)
                d.polygon([(cx + 12 * S, cy - 4 * S), (cx + 19 * S, cy - 2.5 * S), (cx + 12 * S, cy - 1 * S)],
                          fill=(244, 180, 64, 255), outline=ink)
                d.ellipse([cx + 8.5 * S, cy - 5.5 * S, cx + 10.5 * S, cy - 3.5 * S], fill=ink)
        sheet.paste(im, (k * fw * S, 0))
    save(down(sheet, (fw * 4, fh)), "gull.png")


def bez(p0, p1, p2, n=16):
    """Quadratische Bézierkurve als Punktliste (ohne Endpunkt)."""
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in (i / n for i in range(n))]


def gull_near():
    """Nahe Möwe für den Vorbeiflug dicht vor der Kamera: dieselbe M-Silhouette wie gull.png, aber groß und im
    Zeichenstil der Figur (dünne dunkle Kontur, zwei harte Töne je Fläche, warmes Kantenlicht an den
    Vorderkanten). Gegenlicht vom Abendhimmel: Unterseite kühl-lila im Schatten. 4 Flügelstellungen (oben,
    Mitte, unten, Mitte), je 512x256 Pixel, Kopf nach rechts (in Godot gespiegelt)."""
    fw, fh = 512, 256
    S = SS
    ink = (52, 36, 48, 255)
    light = (246, 242, 248, 255)
    shade = (170, 162, 204, 255)
    rimc = (255, 204, 156, 255)
    black = (40, 34, 50, 255)
    lw = int(2.2 * S)
    sheet = Image.new("RGBA", (fw * 4 * S, fh * S), (0, 0, 0, 0))
    poses = [(38, 20), (6, -8), (-18, -34), (6, -8)]   # (Oberarm, Handschwinge) in Grad, positiv = nach oben
    for k, (a1, a2) in enumerate(poses):
        im = Image.new("RGBA", (fw * S, fh * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        cx, cy = 256 * S, 118 * S

        def wing(side, sc):
            r1, r2 = math.radians(a1), math.radians(a2)
            u1 = (side * math.cos(r1), -math.sin(r1))
            u2 = (side * math.cos(r2), -math.sin(r2))
            n1 = (math.sin(r1) * side, math.cos(r1))     # zur Hinterkante
            n2 = (math.sin(r2) * side, math.cos(r2))
            sh = (cx + side * 10 * S, cy - 4 * S)
            L1, L2 = 86 * S * sc, 120 * S * sc
            wr = (sh[0] + u1[0] * L1, sh[1] + u1[1] * L1)
            tp = (wr[0] + u2[0] * L2, wr[1] + u2[1] * L2)
            w_arm, w_hand = 46 * S * sc, 34 * S * sc

            def at(base, u, n, a, b):
                return (base[0] + u[0] * a + n[0] * b, base[1] + u[1] * a + n[1] * b)
            # Vorderkante gewölbt (Handgelenk als Buckel)
            lead = bez(sh, at(sh, u1, n1, L1 * 0.5, -10 * S), wr) + bez(wr, at(wr, u2, n2, L2 * 0.45, -4 * S), tp, 20)
            # Hinterkante: 5 Handschwingen als spitze Federn (Spitze -> Handgelenk), dann Armschwingen zum Körper
            trail = [tp]
            for i in range(5):
                f1 = 1.0 - (i + 1) * 0.1
                trail.append(at(wr, u2, n2, L2 * (f1 + 0.03), w_hand * (0.32 + 0.04 * i)))      # Kerbe
                if i < 4:
                    trail.append(at(wr, u2, n2, L2 * (f1 - 0.02), w_hand * (0.62 + 0.09 * i)))  # Federspitze
            hw = at(wr, u2, n2, L2 * 0.38, w_hand * 1.0)
            bt = at(sh, u1, n1, 0, w_arm)
            mid = ((hw[0] + bt[0]) / 2 + n1[0] * 8 * S, (hw[1] + bt[1]) / 2 + n1[1] * 8 * S)
            trail += [hw] + bez(hw, mid, bt)[1:] + [bt]
            outline = lead + trail
            # heller Streifen an der Vorderkante, sonst Schatten (Unterseite im Gegenlicht)
            band = [at(p, (0, 0), n1 if j < 16 else n2, 0, 9 * S * sc) for j, p in enumerate(lead)]
            lit = lead + band[::-1]
            # schwarze Spitze: äußere 36 % der Hand
            f = 0.64
            tz_lead = [q for q in lead[16:] if (q[0] - wr[0]) * u2[0] + (q[1] - wr[1]) * u2[1] >= L2 * f]
            tz_trail = [q for q in trail if (q[0] - wr[0]) * u2[0] + (q[1] - wr[1]) * u2[1] >= L2 * (f - 0.02)]
            tipzone = [at(wr, u2, n2, L2 * f, 0)] + tz_lead + tz_trail + [at(wr, u2, n2, L2 * (f - 0.02), w_hand * 0.5)]
            spot = at(wr, u2, n2, L2 * 0.88, w_hand * 0.24)
            return outline, lit, tipzone, spot, lead

        def draw_wing(side, sc, base, lit_col):
            outline, lit, tipzone, spot, lead = wing(side, sc)
            d.polygon(outline, fill=base)
            d.polygon(lit, fill=lit_col)
            d.polygon(tipzone, fill=black)
            r = 5 * S * sc
            d.ellipse([spot[0] - r, spot[1] - r, spot[0] + r, spot[1] + r], fill=(236, 232, 244, 255))
            d.line(outline + [outline[0]], fill=ink, width=lw, joint="curve")
            # warmes Kantenlicht innen an der Vorderkante (Abendhimmel)
            d.line([(p[0], p[1] + 2.6 * S) for p in lead[2:28]], fill=rimc, width=int(2.4 * S), joint="curve")

        # hinterer (linker) Flügel kürzer und dunkler -> leichte Schrägsicht
        draw_wing(-1, 0.8, (140, 132, 180, 255), (214, 208, 234, 255))
        draw_wing(1, 1.0, shade, light)
        # Körper (Unterseite: oben hell, unten Schatten), Kopf nach rechts mit Schnabel
        body = [cx - 46 * S, cy - 18 * S, cx + 38 * S, cy + 26 * S]
        d.ellipse(body, fill=light)
        d.chord(body, 12, 168, fill=shade)
        d.ellipse(body, outline=ink, width=lw)
        head = [cx + 16 * S, cy - 40 * S, cx + 56 * S, cy]
        d.ellipse(head, fill=light)
        d.chord(head, 30, 150, fill=shade)
        d.ellipse(head, outline=ink, width=lw)
        bk = [(cx + 52 * S, cy - 23 * S), (cx + 80 * S, cy - 17 * S), (cx + 52 * S, cy - 11 * S)]
        d.polygon(bk, fill=(246, 192, 70, 255), outline=ink, width=int(1.6 * S))
        d.ellipse([cx + 66 * S, cy - 16.5 * S, cx + 70 * S, cy - 13 * S], fill=(214, 70, 54, 255))
        d.ellipse([cx + 37 * S, cy - 29 * S, cx + 45 * S, cy - 21 * S], fill=ink)
        d.ellipse([cx + 40.5 * S, cy - 28 * S, cx + 42.5 * S, cy - 26 * S], fill=(255, 255, 255, 255))
        sheet.paste(im, (k * fw * S, 0))
    save(down(sheet, (fw * 4, fh)), "gull_near.png")


def emote():
    """Drei spitz zulaufende Striche, die vom Kopf weg strahlen; dunkle Füllung mit heller Kante."""
    n = 128
    im = Image.new("RGBA", (n * SS, n * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, cy = 0.15 * n * SS, 0.95 * n * SS          # Ursprung unten links (am Kopf)
    for ang, length in ((-80, 0.62), (-50, 0.7), (-20, 0.62)):
        a = math.radians(ang)
        ux, uy = math.cos(a), math.sin(a)
        px, py = -uy, ux
        r0, r1 = 0.32 * n * SS, (0.32 + length * 0.55) * n * SS
        w0, w1 = 0.012 * n * SS, 0.05 * n * SS
        pts = [(cx + ux * r0 + px * w0, cy + uy * r0 + py * w0), (cx + ux * r1 + px * w1, cy + uy * r1 + py * w1),
               (cx + ux * (r1 + w1) , cy + uy * (r1 + w1)),
               (cx + ux * r1 - px * w1, cy + uy * r1 - py * w1), (cx + ux * r0 - px * w0, cy + uy * r0 - py * w0)]
        d.polygon(pts, fill=(255, 250, 240, 255))
    # heller Rand: Maske dehnen, darunter legen
    a = np.asarray(im)[..., 3]
    halo = Image.fromarray(a).filter(ImageFilter.MaxFilter(4 * SS + 1))
    base = Image.new("RGBA", im.size, (60, 34, 70, 0))
    base.putalpha(halo)
    out = Image.alpha_composite(base, im)
    # Innenfarbe dunkel, Rand hell: umdrehen, wie Manga-Zeichen auf hellem Grund würden sie dunkel sein.
    # Vor dem Abendhimmel liest sich hell mit dunkler Kontur besser.
    save(down(out, (n, n)), "emote.png")


if __name__ == "__main__":
    sparkle(); glow(); flare(); beam()
    for i, s in enumerate((3, 11, 23), 1):
        cel_puff(s, f"puff{i}.png")
    gull(); gull_near(); emote()
