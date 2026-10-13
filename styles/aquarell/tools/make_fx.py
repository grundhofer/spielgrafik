#!/usr/bin/env python3
"""Erzeugt alle Code-Assets des Aquarell-Eintrags (deterministisch, feste Seeds):

  paper.png          512x512, kachelbar: Höhenfeld eines kaltgepressten Aquarellpapiers (Papierkorn-Shader)
  fx/cloud_<n>.png   Wolkenlasuren (Farbe = Lasurfarbe, Alpha = Deckung; in Godot multiplikativ)
  fx/smoke_<n>.png   Rauchtupfer
  fx/water_glaze.png waagerecht kachelbare Lasurebene mit Wellenschlieren für das Hafenbecken
  fx/gull.png        Möwe aus zwei Pinselstrichen, 3 Flügelstellungen nebeneinander
  fx/shadow.png      Schattenfleck unter der Figur
  fx/glow.png        weicher, aufgehellter Fleck für Laterne, Fenster und Lampe
  fx/beam.png        Lichtkeil des Leuchtturms als ausgewaschene (aufgehellte) Bahn
  ui/swatch.png      Farbstreifen hinter der gewählten Antwort, ui/dot_<n>.png Aufzählungstupfer,
  ui/rule.png        Pinselstrich unter dem Ortsnamen

    .venv/bin/python styles/aquarell/tools/make_fx.py [--preview out.png]
"""
import argparse, pathlib
import numpy as np
from PIL import Image

import wc
from blot import blot, ellipse, stroke, tide

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "assets"


def tile_noise(n, cells, seed, octaves=4, persistence=0.55):
    rng = np.random.default_rng(seed)
    out = np.zeros((n, n))
    amp, tot, c = 1.0, 0.0, cells
    for _ in range(octaves):
        g = rng.random((c, c)).astype(np.float32)
        big = Image.fromarray(np.tile(g, (3, 3)), "F").resize((3 * n, 3 * n), Image.BICUBIC)
        out += amp * np.asarray(big)[n:2 * n, n:2 * n]
        tot += amp
        amp *= persistence
        c *= 2
    out /= tot
    return (out - out.min()) / (out.max() - out.min())


def paper(n=512):
    tooth = tile_noise(n, 48, 1, 3, 0.5)              # Körnung des kaltgepressten Papiers (ca. 10 px)
    big = tile_noise(n, 6, 2, 3, 0.5)                 # leichte Wolkigkeit der Leimung
    fine = tile_noise(n, 256, 3, 1)
    # Fasern: kurze, helle Linien
    rng = np.random.default_rng(4)
    fib = Image.new("F", (n, n), 0.0)
    from PIL import ImageDraw
    dr = ImageDraw.Draw(fib)
    for _ in range(260):
        x, y = rng.random(2) * n
        a = rng.random() * np.pi
        L = rng.uniform(6, 22)
        for ox in (-n, 0, n):
            for oy in (-n, 0, n):
                dr.line([(x + ox, y + oy), (x + ox + L * np.cos(a), y + oy + L * np.sin(a))], fill=1.0, width=1)
    fib = wc.blur(np.asarray(fib), 0.6)
    h = 0.62 * tooth + 0.18 * big + 0.12 * fine + 0.10 * np.clip(fib, 0, 1)
    h = (h - h.min()) / (h.max() - h.min())
    return Image.fromarray((h * 255).astype(np.uint8), "L")


def glaze_rgba(cov, top, bottom=None, grad_axis=0):
    h, w = cov.shape
    top = np.asarray(top, dtype=np.float64)
    bottom = top if bottom is None else np.asarray(bottom, dtype=np.float64)
    t = np.linspace(0, 1, h)[:, None, None] if grad_axis == 0 else np.linspace(0, 1, w)[None, :, None]
    # Verlauf entlang der tatsächlichen Deckung (Oberkante bis Unterkante des Flecks)
    rows = np.where(cov.max(1) > 0.05)[0]
    if grad_axis == 0 and len(rows):
        t = np.clip((np.arange(h) - rows[0]) / max(1, rows[-1] - rows[0]), 0, 1)[:, None, None]
    col = top[None, None] * (1 - t) + bottom[None, None] * t
    rgb = np.broadcast_to(col, (h, w, 3))
    return Image.fromarray((np.dstack([rgb, cov]) * 255 + 0.5).clip(0, 255).astype(np.uint8), "RGBA")


def cloud(seed, w, h):
    rng = np.random.default_rng(seed)
    cov = np.zeros((h, w))
    # Wolkenbank: mehrere flache Ellipsen, unten gerade abgeschnitten wie nass in nass gelegte Bänder
    for k in range(rng.integers(3, 6)):
        cx = rng.uniform(0.3, 0.7) * w
        cy = rng.uniform(0.42, 0.6) * h
        rx = rng.uniform(0.16, 0.28) * w
        ry = rng.uniform(0.07, 0.12) * h
        c = blot(w, h, ellipse(cx, cy, rx, ry, 10, rng, 0.15), seed * 10 + k, layers=34, alpha=0.05, var=0.45)
        cov = 1 - (1 - cov) * (1 - c)
    # nass in nass: Oberkante weich verlaufen lassen, Unterkante trocken und härter
    soft = wc.blur(cov, h * 0.06)
    yy = np.linspace(0, 1, h)[:, None]
    cov = np.where(yy < 0.5, 0.75 * soft + 0.25 * cov, 0.3 * soft + 0.7 * cov)
    cov = tide(cov, 2.0, 0.5) * 0.8
    return glaze_rgba(cov, (0.70, 0.67, 0.80), (0.88, 0.72, 0.74))


def smoke(seed, r):
    s = int(r * 2.6)
    rng = np.random.default_rng(seed)
    cov = blot(s, s, ellipse(s / 2, s / 2, r * 0.7, r * 0.6, 9, rng, 0.2), seed, layers=30, alpha=0.05, var=0.6)
    return glaze_rgba(tide(cov, 1.5, 0.4) * 0.6, (0.84, 0.82, 0.88), (0.88, 0.84, 0.86))


def water_glaze(w=1280, h=200, seed=40):
    rng = np.random.default_rng(seed)
    cov = np.zeros((h, w))
    for k in range(70):
        y = rng.uniform(0.04, 0.96) * h
        x = rng.uniform(0, w)
        L = rng.uniform(40, 170) * (0.6 + 0.8 * y / h)          # vorn längere Schlieren
        th = rng.uniform(1.5, 4.0) * (0.6 + 0.8 * y / h)
        bw, bh = int(L + 40), int(th * 4 + 16)
        c = blot(bw, bh, ellipse(bw / 2, bh / 2, L / 2, th, 8, rng, 0.1), seed * 100 + k, layers=14,
                 alpha=0.09, var=0.5, depth0=2, depth1=2, texture=0.3)
        x0, y0 = int(x - bw / 2), int(y - bh / 2)
        for ox in (0, -w, w):                                   # waagerecht kachelbar
            xa, xb = max(0, x0 + ox), min(w, x0 + ox + bw)
            ya, yb = max(0, y0), min(h, y0 + bh)
            if xa < xb and ya < yb:
                sub = c[ya - y0:yb - y0, xa - x0 - ox:xb - x0 - ox]
                cov[ya:yb, xa:xb] = 1 - (1 - cov[ya:yb, xa:xb]) * (1 - sub * rng.uniform(0.5, 1.0))
    return glaze_rgba(np.clip(cov, 0, 1) * 0.75, (0.64, 0.68, 0.84))


def gull_sheet(fw=48, fh=32):
    frames = []
    # Flügelstellung: Flügelspitzen-Höhe relativ zur Körpermitte (oben, waagerecht, unten)
    for k, tip in enumerate((-11, -3, 6)):
        cx, cy = fw / 2, fh / 2 + 2
        lw = [(cx - 19, cy + tip), (cx - 10, cy - 6 + tip * 0.3), (cx - 2, cy)]
        rw = [(cx + 2, cy), (cx + 10, cy - 6 + tip * 0.3), (cx + 19, cy + tip)]
        cov = np.zeros((fh, fw))
        for j, pts in enumerate((lw, rw)):
            p = np.array(pts)
            t = np.linspace(0, 1, 12)
            # quadratische Bézierkurve
            q = ((1 - t) ** 2)[:, None] * p[0] + (2 * (1 - t) * t)[:, None] * p[1] + (t ** 2)[:, None] * p[2]
            wdt = 1.0 + 2.6 * np.sin(np.pi * (t if j == 1 else 1 - t) * 0.9 + 0.15)
            c = stroke(fw, fh, q, wdt, 500 + k * 2 + j, layers=14, alpha=0.12, var=0.25, ss=3)
            cov = 1 - (1 - cov) * (1 - c)
        frames.append(cov)
    sheet = np.concatenate(frames, 1)
    return glaze_rgba(np.clip(sheet * 1.1, 0, 0.92), (0.30, 0.30, 0.40))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", default="")
    a = ap.parse_args()
    (OUT / "fx").mkdir(parents=True, exist_ok=True)
    (OUT / "ui").mkdir(parents=True, exist_ok=True)
    paper().save(OUT / "paper.png")
    for i, (w, h) in enumerate([(420, 90), (300, 70), (520, 110), (260, 60), (380, 80)]):
        cloud(70 + i, w, h).save(OUT / f"fx/cloud_{i}.png")
    for i, r in enumerate((10, 13, 16, 19)):
        smoke(90 + i, r).save(OUT / f"fx/smoke_{i}.png")
    water_glaze().save(OUT / "fx/water_glaze.png")
    gull_sheet().save(OUT / "fx/gull.png")
    rng = np.random.default_rng(5)
    sh = blot(160, 40, ellipse(80, 20, 54, 7, 10, rng, 0.1), 5, layers=30, alpha=0.05, var=0.35)
    glaze_rgba(tide(sh, 1.5, 0.4) * 0.8, (0.62, 0.58, 0.74)).save(OUT / "fx/shadow.png")
    gl = blot(128, 128, ellipse(64, 64, 30, 30, 10, rng, 0.2), 6, layers=40, alpha=0.035, var=0.6)
    glaze_rgba(gl, (1.0, 0.93, 0.74)).save(OUT / "fx/glow.png")
    # Lichtkeil: am Lampenhaus (links) schmal, nach rechts breiter und ausgewaschen
    bw, bh = 520, 120
    keil = np.array([(30, 57), (bw - 60, 26), (bw - 40, 60), (bw - 60, 94), (30, 63)], dtype=float)
    bm = blot(bw, bh, keil, 7, layers=40, alpha=0.04, var=0.25, texture=0.4)
    fade = np.clip(1.0 - np.linspace(0, 1, bw) ** 1.6, 0, 1)[None, :]
    glaze_rgba(bm * fade * 0.9, (1.0, 0.95, 0.80)).save(OUT / "fx/beam.png")
    # UI
    sw = blot(560, 60, np.array([(40, 22), (520, 16), (530, 40), (44, 44)], float), 8, layers=36, alpha=0.05,
              var=0.3, texture=0.5)
    glaze_rgba(tide(sw, 2.0, 0.6) * 0.85, (0.95, 0.83, 0.70)).save(OUT / "ui/swatch.png")
    for i, col in enumerate([(0.45, 0.55, 0.78), (0.80, 0.42, 0.42), (0.52, 0.66, 0.45)]):
        d = blot(28, 28, ellipse(14, 14, 7, 6.5, 8, rng, 0.2), 20 + i, layers=30, alpha=0.06, var=0.7)
        glaze_rgba(tide(d, 1.2, 0.8), col).save(OUT / f"ui/dot_{i}.png")
    t = np.linspace(0, 1, 30)
    q = np.stack([10 + 300 * t, 14 + 3 * np.sin(t * 3.0)], 1)
    rule = stroke(320, 28, q, 2.0 + 5.0 * np.sin(np.pi * t) ** 0.6, 30, layers=20, alpha=0.08, var=0.3, ss=2)
    glaze_rgba(tide(rule, 1.0, 0.6) * 0.8, (0.55, 0.62, 0.82)).save(OUT / "ui/rule.png")
    print("ok")
    if a.preview:
        files = sorted((OUT / "fx").glob("*.png")) + sorted((OUT / "ui").glob("*.png"))
        W = Image.new("RGB", (1400, 900), tuple(int(c * 255) for c in wc.PAPER))
        x = y = 10
        rowh = 0
        for f in files:
            im = Image.open(f).convert("RGBA")
            a_ = np.asarray(im).astype(float) / 255
            # Vorschau wie im Spiel: multiplikativ auf Papier
            base = np.asarray(W.crop((x, y, x + im.width, y + im.height))).astype(float) / 255
            if x + im.width > 1400:
                x, y, rowh = 10, y + rowh + 10, 0
                base = np.asarray(W.crop((x, y, x + im.width, y + im.height))).astype(float) / 255
            m = 1 - a_[..., 3:4] * (1 - a_[..., :3])
            W.paste(Image.fromarray((base * m * 255).astype(np.uint8)), (x, y))
            x += im.width + 10
            rowh = max(rowh, im.height)
        W.save(a.preview)


if __name__ == "__main__":
    main()
