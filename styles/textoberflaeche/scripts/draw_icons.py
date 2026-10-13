#!/usr/bin/env python3
"""Inventar-Icons aus Code: Paket, Schlüssel, Brief, Kompass, Seekarte, Hering.

Bilderbuch-Anmutung passend zum gemalten Dachs: dunkelbraune Tuschekontur, flache Farbflächen mit je einer
Schatten- und einer Lichtfläche. Gezeichnet auf 512 px (8-fach) ohne Kantenglättung, dann mit vormultipliziertem
Alpha auf 64 px verkleinert; das ergibt die Kantenglättung. Kein Zufall, zwei Läufe sind bitgleich.

    .venv/bin/python styles/textoberflaeche/scripts/draw_icons.py OUTDIR   # schreibt OUTDIR/<name>.png (64 px)
"""
import math, pathlib, sys

from PIL import Image, ImageDraw

S = 512            # Zeichenfläche
OUT = 64           # Endgröße
INK = (43, 29, 20, 255)
LW = 22            # Konturbreite auf 512 px (≈ 2,75 px bei 64, ≈ 1,3 px in der 30-px-Anzeige)

NAMES = ["parcel", "key", "letter", "compass", "chart", "herring"]


def rgba(h, a=255):
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def rot(pts, ang, c=(S / 2, S / 2)):
    ca, sa = math.cos(ang), math.sin(ang)
    return [(c[0] + (x - c[0]) * ca - (y - c[1]) * sa, c[1] + (x - c[0]) * sa + (y - c[1]) * ca) for x, y in pts]


def poly(d, pts, fill, outline=True, w=LW):
    d.polygon(pts, fill=fill)
    if outline:
        d.line(list(pts) + [pts[0]], fill=INK, width=w, joint="curve")
        for p in pts:   # runde Ecken
            d.ellipse([p[0] - w / 2, p[1] - w / 2, p[0] + w / 2, p[1] + w / 2], fill=INK)


def ell(d, box, fill, outline=True, w=LW):
    d.ellipse(box, fill=fill, outline=INK if outline else None, width=w if outline else 0)


def line(d, pts, fill=INK, w=LW):
    d.line(pts, fill=fill, width=w, joint="curve")
    for p in (pts[0], pts[-1]):
        d.ellipse([p[0] - w / 2, p[1] - w / 2, p[0] + w / 2, p[1] + w / 2], fill=fill)


def ellipse_pts(cx, cy, rx, ry, a0=0.0, a1=2 * math.pi, n=48):
    return [(cx + rx * math.cos(a0 + (a1 - a0) * i / n), cy + ry * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def parcel(d):
    # Schräg von oben: Deckfläche, Vorderseite, rechte Seite; Schnur über Kreuz, Schleife oben
    paper, shade, light = rgba("c39058"), rgba("9a6a3c"), rgba("dcb27a")
    top = [(96, 200), (300, 140), (420, 196), (216, 262)]
    front = [(96, 200), (216, 262), (216, 420), (96, 352)]
    side = [(216, 262), (420, 196), (420, 350), (216, 420)]
    poly(d, front, shade)
    poly(d, side, paper)
    poly(d, top, light)
    string, sw = rgba("f1e4c4"), 14
    # Schnur: Mitte der Deckfläche in beide Richtungen, dann die Seiten hinunter
    line(d, [(156, 231), (360, 168)], string, sw)
    line(d, [(198, 170), (318, 229)], string, sw)
    line(d, [(318, 229), (318, 386)], string, sw)
    line(d, [(156, 231), (156, 387)], string, sw)
    # Schleife
    cx, cy = 258, 199
    for sgn in (-1, 1):
        loop = [(cx, cy), (cx + sgn * 58, cy - 46), (cx + sgn * 72, cy - 8), (cx + sgn * 20, cy + 6)]
        poly(d, loop, string, True, 12)
    ell(d, [cx - 16, cy - 14, cx + 16, cy + 14], string, True, 12)


def key(d):
    brass, shade, light = rgba("c9a043"), rgba("94712a"), rgba("ecd27f")
    ang = -math.pi / 4
    # Schaft und Bart (in waagerechter Lage gezeichnet, dann gedreht)
    shaft = [(232, 236), (446, 236), (446, 276), (232, 276)]
    bit = [(372, 276), (446, 276), (446, 346), (420, 346), (420, 316), (398, 316), (398, 346), (372, 346)]
    poly(d, rot(bit, ang), shade)
    poly(d, rot(shaft, ang), brass)
    line(d, rot([(250, 247), (430, 247)], ang), light, 10)
    # Reide (Ring) mit Loch
    c = rot([(176, 256)], ang)[0]
    ell(d, [c[0] - 92, c[1] - 92, c[0] + 92, c[1] + 92], brass)
    d.chord([c[0] - 80, c[1] - 80, c[0] + 80, c[1] + 80], 20, 160, fill=shade)
    d.arc([c[0] - 66, c[1] - 66, c[0] + 66, c[1] + 66], 200, 290, fill=light, width=12)
    ell(d, [c[0] - 38, c[1] - 38, c[0] + 38, c[1] + 38], (0, 0, 0, 0))
    d.ellipse([c[0] - 38 + LW / 2, c[1] - 38 + LW / 2, c[0] + 38 - LW / 2, c[1] + 38 - LW / 2], fill=(0, 0, 0, 0))


def letter(d):
    paper, shade, light = rgba("efe4c8"), rgba("cdbd98"), rgba("faf4e4")
    body = [(70, 150), (442, 150), (442, 380), (70, 380)]
    poly(d, body, paper)
    # untere Klappen (leicht dunkler)
    poly(d, [(70, 380), (256, 262), (442, 380)], shade, False)
    line(d, [(70, 380), (256, 262), (442, 380)], INK, 14)
    # obere Klappe
    poly(d, [(70, 150), (442, 150), (256, 290)], light)
    # Siegel
    red, red_d, red_l = rgba("a8352b"), rgba("7a2219"), rgba("d0665a")
    blob = [(256 + 50 * math.cos(a) * (1 + 0.08 * math.sin(5 * a)), 286 + 46 * math.sin(a) * (1 + 0.08 * math.sin(5 * a)))
            for a in [i * 2 * math.pi / 40 for i in range(40)]]
    poly(d, blob, red, True, 16)
    ell(d, [226, 258, 286, 314], red_d, False)
    d.arc([236, 266, 276, 306], 200, 300, fill=red_l, width=8)


def compass(d):
    brass, shade, light = rgba("c49a3e"), rgba("8f6b26"), rgba("ead07c")
    dial, dial_d = rgba("f0e7cf"), rgba("d6c9a6")
    cx, cy = 256, 280
    # Bügel oben
    ell(d, [cx - 40, 64, cx + 40, 144], (0, 0, 0, 0))
    d.ellipse([cx - 40 + LW / 2, 64 + LW / 2, cx + 40 - LW / 2, 144 - LW / 2], fill=(0, 0, 0, 0))
    poly(d, [(cx - 30, 120), (cx + 30, 120), (cx + 30, 160), (cx - 30, 160)], brass)
    # Gehäuse
    ell(d, [cx - 170, cy - 170, cx + 170, cy + 170], brass)
    d.chord([cx - 158, cy - 158, cx + 158, cy + 158], 10, 170, fill=shade)
    d.arc([cx - 150, cy - 150, cx + 150, cy + 150], 195, 290, fill=light, width=14)
    ell(d, [cx - 124, cy - 124, cx + 124, cy + 124], dial)
    d.chord([cx - 112, cy - 112, cx + 112, cy + 112], 20, 160, fill=dial_d)
    # Teilstriche (keine Buchstaben)
    for i in range(8):
        a = i * math.pi / 4
        r0 = 92 if i % 2 == 0 else 102
        line(d, [(cx + r0 * math.cos(a), cy + r0 * math.sin(a)), (cx + 112 * math.cos(a), cy + 112 * math.sin(a))],
             INK, 10 if i % 2 == 0 else 7)
    # Nadel, leicht gedreht
    a = -0.35
    n = rot([(cx, cy - 100), (cx + 26, cy), (cx - 26, cy)], a, (cx, cy))
    s_ = rot([(cx, cy + 100), (cx + 26, cy), (cx - 26, cy)], a, (cx, cy))
    poly(d, s_, rgba("3b3d48"), True, 12)
    poly(d, n, rgba("b23a2c"), True, 12)
    ell(d, [cx - 16, cy - 16, cx + 16, cy + 16], brass, True, 10)


def chart(d):
    paper, shade, light = rgba("e6d6aa"), rgba("c2ad7c"), rgba("f5ead0")
    ribbon, ribbon_d = rgba("3d6390"), rgba("294466")
    ang = -math.pi / 7
    L, R, T, B = 92, 420, 206, 306          # Rolle waagerecht, dann gedreht
    ry = (B - T) / 2
    cyl = [(L, T), (R, T)] + ellipse_pts(R, (T + B) / 2, 26, ry, -math.pi / 2, math.pi / 2)[1:] + [(L, B)]
    poly(d, rot(cyl, ang), paper)
    # Schattenband unten und Lichtkante oben
    poly(d, rot([(L, B - 26), (R, B - 26), (R + 14, B - 18), (R, B), (L, B)], ang), shade, False)
    line(d, rot([(L + 20, T + 20), (R - 10, T + 20)], ang), light, 10)
    # Stirnseite links mit Wicklung
    end = ellipse_pts(L, (T + B) / 2, 26, ry)
    poly(d, rot(end, ang), light)
    spiral = [(L + 13 * math.cos(t) * (t / 12), (T + B) / 2 + ry * 0.5 * math.sin(t) * (t / 12)) for t in
              [i * 0.25 for i in range(1, 49)]]
    d.line(rot(spiral, ang), fill=INK, width=8, joint="curve")
    # Band in der Mitte mit Schleifenenden
    m = (L + R) / 2
    poly(d, rot([(m - 18, T - 6), (m + 18, T - 6), (m + 18, B + 6), (m - 18, B + 6)], ang), ribbon)
    poly(d, rot([(m - 6, B), (m - 46, B + 78), (m - 18, B + 70), (m + 2, B + 18)], ang), ribbon_d, True, 14)
    poly(d, rot([(m + 6, B), (m + 40, B + 84), (m + 14, B + 80), (m - 4, B + 18)], ang), ribbon, True, 14)


def herring(d):
    back, side, belly = rgba("587080"), rgba("aebcc4"), rgba("e7eef0")
    ang = -math.pi / 9
    body = [(84 + (360 - 84) * u, 256 - 92 * math.sin(math.pi * u) ** 0.8 * (1 - 0.25 * u)) for u in
            [i / 24 for i in range(25)]]
    under = [(84 + (360 - 84) * u, 256 + 64 * math.sin(math.pi * u) ** 0.8 * (1 - 0.3 * u)) for u in
             [i / 24 for i in range(25)]]
    tail = [(346, 248), (448, 176), (426, 256), (448, 336), (346, 264)]
    poly(d, rot(tail, ang), back)
    outline = body + under[::-1]
    poly(d, rot(outline, ang), side)
    # Rücken dunkel, Bauch hell (ohne Kontur, innen)
    mid = [(84 + (360 - 84) * u, 256 - 34 * math.sin(math.pi * u) * (1 - 0.25 * u)) for u in [i / 24 for i in range(25)]]
    poly(d, rot(body[2:-2] + mid[::-1][2:-2], ang), back, False)
    low = [(84 + (360 - 84) * u, 256 + 26 * math.sin(math.pi * u) * (1 - 0.3 * u)) for u in [i / 24 for i in range(25)]]
    poly(d, rot(low[3:-3] + under[::-1][3:-3], ang), belly, False)
    d.line(rot(outline + [outline[0]], ang), fill=INK, width=LW, joint="curve")
    # Kiemenbogen, Auge, Glanzstrich
    d.arc([*rot([(108, 200)], ang)[0], *rot([(188, 300)], ang)[0]], 300, 60, fill=INK, width=10)
    e = rot([(132, 236)], ang)[0]
    ell(d, [e[0] - 17, e[1] - 17, e[0] + 17, e[1] + 17], rgba("f4f1e8"), True, 9)
    d.ellipse([e[0] - 7, e[1] - 7, e[0] + 7, e[1] + 7], fill=INK)
    line(d, rot([(190, 238), (320, 230)], ang), rgba("f6fafb"), 10)


DRAW = {"parcel": parcel, "key": key, "letter": letter, "compass": compass, "chart": chart, "herring": herring}


def downsample(img, size):
    """Vormultipliziert verkleinern: keine dunklen Säume an den Kanten."""
    return img.convert("RGBa").resize((size, size), Image.LANCZOS).convert("RGBA")


def render(name, size=OUT):
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    DRAW[name](ImageDraw.Draw(img))
    return downsample(img, size)


def main():
    out = pathlib.Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for n in NAMES:
        render(n).save(out / f"{n}.png")
    print("ok", len(NAMES))


if __name__ == "__main__":
    main()
