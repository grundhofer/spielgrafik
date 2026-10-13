#!/usr/bin/env python3
"""Erzeugt die Drucktexturen (Code, feste Seeds) für den Druck-Shader der Demo.

    .venv/bin/python styles/holzschnitt/scripts/make_textures.py

Ergebnis in assets/ und demo/art/:
  paper.png   1280x720 RGB  Papierfarbe mit Fasern und leichter Wolkigkeit (Bütten, cremefarben)
  grain.png   1280x720 RGB  R = Holzmaserung des Schwarzstocks (helle Fasern, in denen Farbe fehlt; fest, gehört zum
                            Stock und wandert mit dessen Passerversatz), G = Linol-Sprenkel der Farbplatten (fest),
                            B = Papierzahn (Höhe der Papieroberfläche; je Druckfassung versetzt abgetastet)
  noise.png   512x512 RGB   kachelbar: R, G = glattes Rauschen für das Wackeln der Schnittkanten,
                            B = großflächige Einfärbung (Walze gibt ungleich Farbe ab)
Alle Rauschfelder kommen aus gefiltertem Weißrauschen (FFT), sind also nahtlos kachelbar.
"""
import pathlib
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = [ROOT / "assets", ROOT / "demo/art"]


def band_noise(rng, h, w, lo, hi, aniso=(1.0, 1.0)):
    """Weißrauschen, im Frequenzraum auf Wellenlängen zwischen lo und hi Pixeln begrenzt; kachelbar, 0..1."""
    n = rng.standard_normal((h, w))
    fy = np.fft.fftfreq(h)[:, None] * aniso[0]
    fx = np.fft.fftfreq(w)[None, :] * aniso[1]
    f = np.sqrt(fx * fx + fy * fy)
    mask = (f >= 1.0 / hi) & (f <= 1.0 / lo)
    out = np.real(np.fft.ifft2(np.fft.fft2(n) * mask))
    out -= out.min()
    return out / max(out.max(), 1e-9)


def gauss_noise(rng, h, w, sigma, aniso=(1.0, 1.0)):
    n = rng.standard_normal((h, w))
    fy = np.fft.fftfreq(h)[:, None] * aniso[0]
    fx = np.fft.fftfreq(w)[None, :] * aniso[1]
    g = np.exp(-2 * (np.pi * sigma) ** 2 * (fx * fx + fy * fy))
    out = np.real(np.fft.ifft2(np.fft.fft2(n) * g))
    out = (out - out.mean()) / (out.std() + 1e-9)
    return out


def save(name, arr):
    im = Image.fromarray(np.clip(arr * 255 + 0.5, 0, 255).astype(np.uint8))
    for d in OUT:
        d.mkdir(parents=True, exist_ok=True)
        im.save(d / name)
    print("ok", name, im.size, im.mode)


def main():
    W, H = 1280, 720
    rng = np.random.default_rng(19210512)

    # --- Papier: Bütten, cremefarben. Großflächig leicht wolkig, feine Fasern (kurze, gerichtete Striche).
    base = np.array([0.933, 0.898, 0.816])          # #EEE5D0
    cloud = gauss_noise(rng, H, W, 60) * 0.012 + gauss_noise(rng, H, W, 14) * 0.008
    fib = gauss_noise(rng, H, W, 1.2, aniso=(1.0, 4.0))     # in x gestreckt: Fasern
    fib = np.clip(fib - 1.6, 0, None) * 0.03
    tooth = gauss_noise(rng, H, W, 0.8) * 0.010
    lum = 1.0 + cloud - fib + tooth
    paper = base[None, None, :] * lum[..., None]
    save("paper.png", paper)

    # --- Holzmaserung (R): Jahresringe als leicht wellige, fast waagerechte Linien mit Ästen; nur die dünnen
    # hellen Fasern zählen (dort nimmt der Stock in Schwarzflächen weniger Farbe an).
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    warp = gauss_noise(rng, H, W, 90, aniso=(1.0, 3.0)) * 9.0 + gauss_noise(rng, H, W, 25, aniso=(1.0, 3.0)) * 2.5
    v = yy + warp
    for kx, ky, r in [(260, 140, 70), (930, 470, 90), (640, 650, 55), (1150, 90, 60)]:   # Äste: Ringe weichen aus
        d = np.sqrt((xx - kx) ** 2 * 0.25 + (yy - ky) ** 2)
        v += 18 * np.exp(-(d / r) ** 2) * np.sign(yy - ky + 1e-3)
    spacing = 9.0 + gauss_noise(rng, H, W, 120) * 1.5
    ph = (v / spacing) % 1.0
    ring = np.clip(1.0 - np.abs(ph - 0.5) / 0.06, 0, 1)            # schmale Linie je Ring
    broken = gauss_noise(rng, H, W, 6, aniso=(1.0, 6.0))          # Fasern reißen ab
    ring *= np.clip(broken * 0.9 - 0.1, 0, 1)
    fine = np.clip(gauss_noise(rng, H, W, 0.9, aniso=(1.0, 8.0)) - 1.4, 0, 1) * 0.8   # feine Kratzer längs
    wood = np.clip(ring + fine, 0, 1)

    # --- Linol-Sprenkel (G): typische „Salz“-Struktur großer Linolflächen: kleine helle Flecken.
    lino = np.clip(gauss_noise(rng, H, W, 1.3) * 0.6 + gauss_noise(rng, H, W, 5) * 0.4 - 1.25, 0, 1)
    lino = np.clip(lino * 2.2, 0, 1)

    # --- Papierzahn (B): Höhe der Papieroberfläche, 0..1; Täler nehmen bei wenig Farbe nichts an.
    zahn = gauss_noise(rng, H, W, 0.9) * 0.55 + gauss_noise(rng, H, W, 2.5) * 0.35 + gauss_noise(rng, H, W, 1.0, aniso=(1.0, 3.0)) * 0.25
    zahn = (zahn - zahn.min()) / (zahn.max() - zahn.min())
    save("grain.png", np.stack([wood, lino, zahn], -1))

    # --- Rauschen für Kantenwackeln und Einfärbung, 512x512 kachelbar.
    n = 512
    r = band_noise(rng, n, n, 10, 40)
    g = band_noise(rng, n, n, 10, 40)
    b = band_noise(rng, n, n, 60, 260)
    save("noise.png", np.stack([r, g, b], -1))


if __name__ == "__main__":
    main()
