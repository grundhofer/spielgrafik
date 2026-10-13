#!/usr/bin/env python3
"""Erzeugt die Papier- und Drucktexturen (Code, feste Seeds) für die Ukiyo-e-Demo.

    .venv/bin/python styles/ukiyo-e/scripts/make_textures.py

Ergebnis in assets/ und demo/art/:
  washi.png   512x512 L, kachelbar. Multiplikationsfaktor für das ganze Bild (255 = keine Änderung):
              Japanpapier mit langen, leicht gebogenen Kozo-Fasern (heller und dunkler als der Grund),
              leichter Wolkigkeit und feinen Druckspuren des Reibers (Baren, kreisförmige Striche).
  spray.png   30x10 RGBA  Gischttropfen in Zielgröße (Durchmesser 5, 7 und 9 px in Zellen zu 10 px): Papierweiß
              mit Indigo-Kontur wie die gedruckten Tropfen der KI-Wellen; ungefiltert in Originalgröße gezeichnet
  spray_close.png  48x16 RGBA dieselben Tropfen für die Nahaufnahme (8, 11 und 14 px in Zellen zu 16 px)
  smoke.png   2600x140 RGBA Rauchfahne als Bildfolge: 20 Bilder à 130x140 (10 Bilder/s, Schleife 2,0 s). Je Bild
              eine Fahne aus dicht gesetzten Kreisen entlang des Wegs (steigt erst senkrecht, treibt dann nach links,
              111 px hoch und 79 px weit in 2,8 s; Ausbuchtungen alle 0,4 s wandern mit dem Rauch nach oben; das
              Ende läuft spitz aus statt auszublenden): deckend, flach grau mit einem Bokashi nach oben (heller),
              feine Sumi-Kontur 1,2 px. Schornsteinmund bei (112, 134) im Bild.
  (Leuchtfeuer und Laterne: scripts/build_lights.py)
Alle Rauschfelder kommen aus gefiltertem Weißrauschen (FFT), sind also nahtlos kachelbar.
"""
import math, pathlib
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = [ROOT / "assets", ROOT / "demo/art"]
INDIGO = (38, 44, 92)
PAPER = (244, 236, 218)


def gauss_noise(rng, h, w, sigma):
    n = rng.standard_normal((h, w))
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.fftfreq(w)[None, :]
    g = np.exp(-2 * (np.pi * sigma) ** 2 * (fx * fx + fy * fy))
    out = np.real(np.fft.ifft2(np.fft.fft2(n) * g))
    return (out - out.mean()) / (out.std() + 1e-9)


def save(name, im):
    for d in OUT:
        d.mkdir(parents=True, exist_ok=True)
        im.save(d / name)
    print("ok", name, im.size, im.mode)


def fibres(rng, size, n, ss, lighter):
    """Lange, leicht gebogene Fasern als Maske (0..1), kachelbar durch Zeichnen mit Versatz +-size."""
    S = size * ss
    im = Image.new("L", (S, S), 0)
    dr = ImageDraw.Draw(im)
    for _ in range(n):
        x, y = rng.uniform(0, S), rng.uniform(0, S)
        ang = rng.uniform(0, math.pi)
        length = rng.uniform(18, 90) * ss
        curl = rng.normal(0, 0.035)
        width = max(1, int(round(rng.uniform(0.5, 1.4) * ss)))
        val = int(rng.uniform(90, 255))
        pts = []
        steps = 24
        for i in range(steps + 1):
            pts.append((x, y))
            ang += curl * (length / steps) / ss * 0.15
            x += math.cos(ang) * length / steps
            y += math.sin(ang) * length / steps
        for ox in (-S, 0, S):
            for oy in (-S, 0, S):
                dr.line([(px + ox, py + oy) for px, py in pts], fill=val, width=width)
    im = im.resize((size, size), Image.LANCZOS)
    return np.asarray(im, np.float32) / 255.0


def make_washi():
    N = 512
    rng = np.random.default_rng(18571012)
    cloud = gauss_noise(rng, N, N, 28) * 0.010 + gauss_noise(rng, N, N, 6) * 0.006
    grain = gauss_noise(rng, N, N, 0.7) * 0.010
    f_dark = fibres(rng, N, 260, 3, False)
    f_light = fibres(rng, N, 420, 3, True)
    # Baren-Spuren: feine, gebogene Rillen (Reiber kreist über den Bogen), nur ganz schwach
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
    swirl = np.zeros((N, N), np.float32)
    for cx, cy, r0 in [(140, 160, 70), (390, 300, 95), (250, 450, 60), (470, 60, 80)]:
        for ox in (-N, 0, N):
            for oy in (-N, 0, N):
                d = np.hypot(xx - cx - ox, yy - cy - oy)
                ring = np.cos(d / 2.6) * np.exp(-((d - r0) / (r0 * 0.55)) ** 2)
                swirl += ring.astype(np.float32)
    v = 0.962 + cloud + grain - 0.045 * f_dark + 0.035 * f_light + 0.006 * swirl
    v = np.clip(v, 0.86, 1.0)
    save("washi.png", Image.fromarray((v * 255 + 0.5).astype(np.uint8), "L"))
    print("   washi Mittel %.3f  Min %.3f" % (v.mean(), v.min()))


def make_spray(name="spray.png", cell=10, dias=(5, 7, 9), line=1.1):
    ss = 8
    im = Image.new("RGBA", (3 * cell * ss, cell * ss), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    for k, dia in enumerate(dias):
        c = (k * cell + cell / 2) * ss
        r = dia * ss / 2
        dr.ellipse([c - r, cell / 2 * ss - r, c + r, cell / 2 * ss + r], fill=INDIGO + (255,))
        ri = r - line * ss
        dr.ellipse([c - ri, cell / 2 * ss - ri, c + ri, cell / 2 * ss + ri], fill=PAPER + (255,))
    save(name, im.resize((3 * cell, cell), Image.LANCZOS))


SMOKE_FRAMES, SMOKE_W, SMOKE_H, SMOKE_ANCHOR = 20, 130, 140, (112, 134)


def smoke_puffs(t):
    """Rauchfahne zur Zeit t als dicht gesetzte Kreise entlang des Wegs (Alter a = 0 … 2,8 s, alle 0,02 s): Stoff,
    der zur Zeit e = t - a aus dem Schornstein kam, steht bei weg(a) mit Radius r(a, e). Die Ausbuchtungen hängen an
    e und wandern deshalb mit dem Rauch nach oben; alles ist in e periodisch mit 2,0 s (Schleife von 20 Bildern)."""
    out = []
    for k in range(141):
        a = k * 0.02
        e = t - a
        sway = 3.0 * math.sin(2 * math.pi * e / 2.0) + 1.5 * math.sin(2 * math.pi * e / 1.0 + 1.3)
        x = -(3.0 * a + 9.0 * a * a) + sway * min(a, 1.0)
        y = -(34.0 * a + 2.0 * a * a)
        base = (3.0 + 4.6 * a) * float(np.clip((2.8 - a) / 1.0, 0, 1)) ** 0.7
        bump = 1 + 0.30 * math.cos(2 * math.pi * e / 0.4) * (0.75 + 0.25 * math.sin(2 * math.pi * e / 2.0))
        r = base * bump
        if r > 0.4:
            out.append((x, y, r))
    return out


def make_smoke():
    ss = 4
    W, H = SMOKE_W * ss, SMOKE_H * ss
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32) / ss
    ax, ay = SMOKE_ANCHOR
    dark, light, sumi = np.array([96, 90, 96.]), np.array([206, 201, 206.]), np.array([35, 30, 35.])
    bok = np.clip((ay - yy) / 110.0, 0, 1)[..., None]           # Bokashi nach oben: unten dunkel, oben hell
    fill = dark * (1 - bok) + light * bok
    sheet = np.zeros((SMOKE_H, SMOKE_W * SMOKE_FRAMES, 4), np.float32)
    for k in range(SMOKE_FRAMES):
        field = np.full((H, W), 1e9, np.float32)
        for x, y, r in smoke_puffs(k * 0.1):
            field = np.minimum(field, np.hypot(xx - (ax + x), yy - (ay + y)) - r)
        inside = (field < 0).astype(np.float32)
        line = ((field < 0) & (field > -1.2)).astype(np.float32)
        col = fill * (inside - line)[..., None] + sumi * line[..., None]
        a = inside.reshape(SMOKE_H, ss, SMOKE_W, ss).mean((1, 3))
        c = col.reshape(SMOKE_H, ss, SMOKE_W, ss, 3).mean((1, 3)) / np.maximum(a[..., None], 1e-4)
        sheet[:, k * SMOKE_W:(k + 1) * SMOKE_W, :3] = c
        sheet[:, k * SMOKE_W:(k + 1) * SMOKE_W, 3] = a * 255
    save("smoke.png", Image.fromarray((np.clip(sheet, 0, 255) + 0.5).astype(np.uint8), "RGBA"))


def main():
    make_washi()
    make_spray()
    make_spray("spray_close.png", 16, (8, 11, 14), 1.7)
    make_smoke()


if __name__ == "__main__":
    main()
