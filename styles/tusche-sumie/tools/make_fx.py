#!/usr/bin/env python3
"""Code-Effekte für die Demo (ohne Bildmodell).

    .venv/bin/python styles/tusche-sumie/tools/make_fx.py

Ergebnis in assets/fx/:
  mist_a.png, mist_b.png   1024x192, waagerecht kachelbare Nebelmasken (nur Alpha zählt): lang gezogene,
                           weiche Schwaden mit ausgefranstem Rand
  glow.png                 128x128 weicher, leicht unregelmäßiger Lichtfleck (Alpha) für Lampe, Laterne, Fenster
  bg_noise.png             320x180 wolkiges Rauschen (Graustufen) für das Einziehen der Tusche beim Szenenstart
"""
import math

import numpy as np
from PIL import Image

from inkutil import ROOT, noise, rng


def periodic_noise(h, w, cx, cy, seed, octaves=3):
    """Wertrauschen, waagerecht periodisch über w (cx muss w teilen)."""
    r = rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        gx, gy = max(2, int(round(w / (cx / 2 ** o)))), max(2, int(round(h / (cy / 2 ** o))) + 1)
        g = r.uniform(-1, 1, (gy, gx)).astype(np.float32)
        gp = np.concatenate([g[:, -2:], g, g[:, :3]], axis=1)          # waagerecht umlaufend
        sx = w / gx
        big = np.asarray(Image.fromarray(gp, "F").resize((int(round(gp.shape[1] * sx)), h), Image.BICUBIC),
                         np.float32)
        x0 = int(round(2 * sx))
        out += amp * big[:, x0:x0 + w]
        tot += amp
        amp *= 0.5
    return out / tot


def mist(seed, w=1024, h=192, cover=0.0):
    n = periodic_noise(h, w, 512, 56, seed, octaves=4)
    fine = periodic_noise(h, w, 64, 6, seed + 5, octaves=2)
    v = n + fine * 0.10 + cover
    a = np.clip((v + 0.12) * 1.5, 0, 1) ** 1.6
    return Image.fromarray((np.dstack([np.full((h, w), 255, np.float32)] * 3 + [a * 255])).astype(np.uint8), "RGBA")


def glow(size=128, seed=3):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    c = (size - 1) / 2
    ang = np.arctan2(yy - c, xx - c)
    r = np.hypot(xx - c, yy - c) / c
    wob = 1.0 + 0.10 * np.sin(ang * 5 + 1.3) + 0.06 * np.sin(ang * 9 + 0.4)
    a = np.clip(1.0 - r * wob, 0, 1) ** 1.6
    return Image.fromarray(np.dstack([np.full_like(a, 255)] * 3 + [a * 255]).astype(np.uint8), "RGBA")


def main():
    out = ROOT / "assets/fx"
    out.mkdir(parents=True, exist_ok=True)
    mist(21).save(out / "mist_a.png")
    mist(37, cover=-0.05).save(out / "mist_b.png")
    glow().save(out / "glow.png")
    n = noise(180, 320, 40, 5, octaves=4)
    n = (n - n.min()) / (n.max() - n.min())
    Image.fromarray((n * 255).astype(np.uint8), "L").save(out / "bg_noise.png")
    print("ok fx")


if __name__ == "__main__":
    main()
