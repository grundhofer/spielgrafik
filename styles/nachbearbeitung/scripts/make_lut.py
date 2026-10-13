#!/usr/bin/env python3
"""Farb-LUT als 32³-Streifen (1024×32 PNG) erzeugen.

Aufbau des Streifens (so liest ihn shaders/world_post.gdshader → lut()):
  32 Kacheln zu 32×32 nebeneinander; Kachel b = Blauwert, innerhalb der Kachel x = Rot, y = Grün.
  Werte in sRGB (wie das Bild im Viewport), keine Gammaumrechnung im Shader nötig.

    .venv/bin/python styles/nachbearbeitung/scripts/make_lut.py --identity --out /tmp/x/identity.png
    .venv/bin/python styles/nachbearbeitung/scripts/make_lut.py            # Kalte Nacht -> assets/ und demo/textures/
    .venv/bin/python styles/nachbearbeitung/scripts/make_lut.py --preview frame.png --preview-out graded.png

Der Look „Kalte Nacht“ ist eine Gradierung, wie man sie sonst in einem Bildprogramm auf ein Bildschirmfoto
mit eingebettetem Identitäts-LUT anwendet: Schatten und Mitten kalt (Blaugrün) und entsättigt, Kontrast höher,
Lichter (Lampen) bleiben warm. Hier als Formel, damit der LUT reproduzierbar ist. Gemessen in der Demo: Das
orange Horizontband (sRGB-Helligkeit um 0,6) wird fast neutral, nur sein hellster Streifen bleibt blassgelb.
"""
import argparse
import pathlib

import numpy as np
from PIL import Image

N = 32
HERE = pathlib.Path(__file__).resolve().parent.parent


def identity():
    r, g, b = np.meshgrid(np.arange(N), np.arange(N), np.arange(N), indexing="xy")
    # r: x innerhalb der Kachel, g: y, b: Kachel
    return np.stack([r, g, b], axis=-1).astype(np.float64) / (N - 1)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def to_srgb(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def grade_kalte_nacht(c):
    """c: (..., 3) sRGB 0..1 -> sRGB 0..1.

    Split-Toning: Schatten und Mitten kalt (Blaugrün), entsättigt und dunkler; Lichter laufen zu warmem
    Bernstein (Übergang zwischen sRGB-Helligkeit 0,5 und 0,92). Dadurch wird aus der Abendszene eine kalte Nacht,
    in der Lampen und Strahl warm bleiben; das Horizontband liegt im Übergang und wird fast neutral.
    Kontrast über eine S-Kurve in sRGB.
    """
    lin = to_linear(c)
    lum = (lin @ np.array([0.2126, 0.7152, 0.0722]))[..., None]
    lum_s = to_srgb(lum)
    # kalter Zweig
    cold = lum + (lin - lum) * 0.30
    cold = cold * 0.55 * np.array([0.50, 0.86, 1.22])
    cold_s = to_srgb(cold)
    # warmer Zweig für die Lichter: Helligkeit behalten, Farbe zu Bernstein
    warm = lum * np.array([1.25, 0.92, 0.55]) * 1.15
    warm = warm + (lin - lum) * 0.6
    warm_s = to_srgb(warm)
    w = smoothstep(0.50, 0.92, lum_s)
    out = cold_s * (1 - w) + warm_s * w
    out = out + 0.18 * (smoothstep(0.0, 1.0, out) - out)          # S-Kurve
    out = out * 0.95 + np.array([0.004, 0.016, 0.040])            # Schwarz bläulich angehoben
    return np.clip(out, 0.0, 1.0)


def to_strip(lut):
    # lut[g, r, b] -> Streifen (32, 1024): Kachel b an x = b*32
    strip = np.zeros((N, N * N, 3))
    for b in range(N):
        strip[:, b * N:(b + 1) * N] = lut[:, :, b]
    return strip


def apply_lut(img, lut):
    """Trilinear wie im Shader (Kontrolle offline)."""
    c = img.astype(np.float64) / 255.0
    p = c * (N - 1)
    i0 = np.floor(p).astype(int)
    i1 = np.minimum(i0 + 1, N - 1)
    f = p - i0
    out = np.zeros_like(c)
    for dr in (0, 1):
        for dg in (0, 1):
            for db in (0, 1):
                ir = i1[..., 0] if dr else i0[..., 0]
                ig = i1[..., 1] if dg else i0[..., 1]
                ib = i1[..., 2] if db else i0[..., 2]
                w = (f[..., 0] if dr else 1 - f[..., 0]) * (f[..., 1] if dg else 1 - f[..., 1]) * \
                    (f[..., 2] if db else 1 - f[..., 2])
                out += w[..., None] * lut[ig, ir, ib]
    return (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--identity", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--preview", default=None, help="Bild, auf das der LUT offline angewendet wird")
    ap.add_argument("--preview-out", default=None)
    a = ap.parse_args()
    ident = identity()                      # [g, r, b, 3]
    lut = ident if a.identity else grade_kalte_nacht(ident)
    strip = (np.clip(to_strip(lut), 0, 1) * 255 + 0.5).astype(np.uint8)
    outs = [pathlib.Path(a.out)] if a.out else [HERE / "assets" / "lut_kalte_nacht.png",
                                                 HERE / "demo" / "textures" / "lut_kalte_nacht.png"]
    for o in outs:
        o.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(strip, "RGB").save(o)
        print("geschrieben:", o)
    if a.preview:
        img = np.asarray(Image.open(a.preview).convert("RGB"))
        Image.fromarray(apply_lut(img, lut)).save(a.preview_out)
        print("Vorschau:", a.preview_out)


if __name__ == "__main__":
    main()
