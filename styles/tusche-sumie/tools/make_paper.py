#!/usr/bin/env python3
"""Reispapier und Zinnober-Stempel (Code, ohne Bildmodell).

    .venv/bin/python styles/tusche-sumie/tools/make_paper.py

Ergebnis:
  assets/paper.png        1280x720 Reispapier: warmes Grundweiß, wolkige Dichte, lange helle und dunkle Fasern, Korn
  assets/ui/seal.png      Stempel 112x112 (Weißschnitt): Zinnoberfläche mit ausgesparter Dachspfote, ohne Schrift,
                          unregelmäßiger Rand und Fehlstellen wie bei einem echten Abdruck; RGB = Transmission
"""
import math

import numpy as np
from PIL import Image, ImageDraw

from inkutil import ROOT, W, H, PAPER_RGB, blur, noise, rng, transmission_rgba, save_rgb


def paper(w=W, h=H, seed=7):
    r = rng(seed)
    base = np.ones((h, w, 3), np.float32) * PAPER_RGB
    # wolkige Dichte (Faserbrei ungleich verteilt)
    cloud = noise(h, w, 180, seed + 1, octaves=4) * 0.022
    lum = cloud.copy()
    # Fasern: lange, leicht gebogene Linien, meist heller (Bastfasern), einige dunkler
    fib = Image.new("F", (w, h), 0.0)
    d = ImageDraw.Draw(fib)
    for i in range(3400):
        x, y = r.uniform(-40, w + 40), r.uniform(-40, h + 40)
        ang = r.uniform(0, 2 * math.pi)
        ln = r.uniform(8, 45) if r.random() < 0.85 else r.uniform(45, 120)
        val = r.uniform(0.5, 1.0) * (1 if r.random() < 0.7 else -1.3)
        pts = [(x, y)]
        n = max(3, int(ln / 5))
        for k in range(n):
            ang += r.normal(0, 0.35)        # Zufallsweg statt gleichmäßiger Bögen
            x, y = x + math.cos(ang) * ln / n, y + math.sin(ang) * ln / n
            pts.append((x, y))
        d.line(pts, fill=float(val), width=1)
    f = np.asarray(fib, np.float32)
    f = blur(f, 0.6) * 0.035
    lum += f
    grain = r.normal(0, 1, (h, w)).astype(np.float32)
    lum += blur(grain, 0.7) * 0.012
    out = base * (1.0 + lum[..., None])
    # Ecken minimal dunkler (Blatt liegt im Licht)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    v = ((xx / w - 0.5) ** 2 * 1.2 + (yy / h - 0.5) ** 2) * 0.06
    out *= (1.0 - v[..., None])
    return np.clip(out, 0, 1)


def paw(draw, cx, cy, s):
    """Dachspfote: Ballen + fünf Zehen + Krallenstriche (ausgespart)."""
    draw.ellipse([cx - 0.30 * s, cy - 0.02 * s, cx + 0.30 * s, cy + 0.34 * s], fill=0)
    for i, (dx, dy) in enumerate([(-0.36, -0.10), (-0.20, -0.27), (0.0, -0.33), (0.20, -0.27), (0.36, -0.10)]):
        rr = 0.085 * s
        x, y = cx + dx * s, cy + dy * s
        draw.ellipse([x - rr, y - rr * 1.15, x + rr, y + rr * 1.15], fill=0)
        # Kralle
        k = 0.11 * s
        draw.line([(x + dx * 0.25 * s, y - rr * 1.1), (x + dx * 0.45 * s, y - rr * 1.1 - k)], fill=0,
                  width=max(2, int(0.035 * s)))


def seal(size=112, seed=11):
    """Weißschnitt-Stempel: Zinnoberfläche, Pfote ausgespart, Doppelrand innen."""
    S = size * 4
    m = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(m)
    pad = int(S * 0.04)
    d.rounded_rectangle([pad, pad, S - pad, S - pad], radius=int(S * 0.06), fill=255)
    # schmale ausgesparte Innenlinie (wie ein Schnittrand)
    i0 = int(S * 0.12)
    d.rounded_rectangle([i0, i0, S - i0, S - i0], radius=int(S * 0.04), outline=0, width=int(S * 0.022))
    paw(d, S * 0.5, S * 0.52, S * 0.62)
    a = np.asarray(m.resize((size, size), Image.LANCZOS), np.float32) / 255.0
    # Rand verbiegen: Schwelle über Rauschen
    n = noise(size, size, 6, seed, octaves=2) * 0.35 + noise(size, size, 2, seed + 1) * 0.15
    cov = np.clip((a - 0.5 + n * 0.5) * 6 + 0.5, 0, 1)
    # Fehlstellen: Paste nicht ganz aufgenommen
    holes = noise(size, size, 3, seed + 2, octaves=2) + noise(size, size, 25, seed + 4) * 0.5
    cov *= np.clip(1.0 - np.clip(holes - 0.62, 0, 1) * 5, 0, 1)
    # leicht ungleichmäßiger Druck
    press = 0.86 + 0.14 * np.clip(noise(size, size, 30, seed + 3) + 0.4, 0, 1)
    r = cov * press
    return transmission_rgba(np.zeros_like(r), r, alpha=np.clip(cov * 1.4, 0, 1))


def main():
    p = paper()
    save_rgb(p, ROOT / "assets/paper.png")
    (ROOT / "assets/ui").mkdir(parents=True, exist_ok=True)
    seal().save(ROOT / "assets/ui/seal.png")
    print("ok paper, seal")


if __name__ == "__main__":
    main()
