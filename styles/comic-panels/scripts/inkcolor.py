#!/usr/bin/env python3
"""Trennt ein KI-Comicbild in Tusche (schwarze Linien und Schwarzflächen) und Farbflächen (Flats), wie ein Comic
gedruckt wird: Schwarzplatte = Zeichnung, Farbplatten = Kolorierung darunter.

    from inkcolor import separate, downscale_rgb, downscale_cov

Tusche-Deckung je Pixel: dunkel (k = 1 - max(rgb)) und unbunt (Abstand max - min klein):
    ink = smoothstep(K_LO, K_HI, k) * (1 - smoothstep(S_LO, S_HI, sat))
Grenzen aus den Bildern gemessen: Tusche k > 0,85; Übergang 0,75–0,85 schmal, damit die Tusche im Quellbild fast nur 0 oder 1 ist
(Graustufen entstehen erst beim Verkleinern als Kantenglättung); dunkles Fell des Dachses k ≈ 0,71–0,72 (bleibt Farbe, wird im
Druck zu Rasterpunkten); dunkles Nachtblau ist bunt (sat > 0,4) und bleibt Farbe.
Farbflächen unter der Tusche: Pixel mit ink > 0,15 gelten als unbekannt und werden schrittweise mit dem Mittel ihrer
bekannten Nachbarn gefüllt (8er-Nachbarschaft, bis zu 60 Durchgänge); Reste in großen Schwarzflächen behalten ihre
Farbe (die Tusche deckt sie ohnehin).
"""
import numpy as np
from PIL import Image

K_LO, K_HI = 0.75, 0.85
S_LO, S_HI = 0.16, 0.30


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def ink_coverage(rgb):
    mx = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    k = 1.0 - mx
    sat = mx - mn
    return smoothstep(K_LO, K_HI, k) * (1.0 - smoothstep(S_LO, S_HI, sat))


def fill_unknown(rgb, known, passes=60):
    col = rgb.copy()
    known = known.copy()
    h, w = known.shape
    for _ in range(passes):
        if known.all():
            break
        acc = np.zeros_like(col)
        cnt = np.zeros((h, w))
        kf = known.astype(np.float64)
        pad_c = np.pad(col * kf[..., None], ((1, 1), (1, 1), (0, 0)))
        pad_k = np.pad(kf, 1)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                acc += pad_c[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]
                cnt += pad_k[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]
        new = (~known) & (cnt > 0)
        col[new] = acc[new] / cnt[new][:, None]
        known = known | new
    return col


def separate(rgb, alpha=None):
    """rgb: float 0..1 (H, W, 3); alpha optional (Figur). Gibt (farbe, tusche) zurück, tusche in 0..1."""
    ink = ink_coverage(rgb)
    if alpha is not None:
        ink = ink * alpha
    known = ink <= 0.15
    if alpha is not None:
        known &= alpha > 0.5
        # außerhalb der Figur: nichts bekannt, aber auch nicht füllen (Alpha bleibt 0)
    col = fill_unknown(rgb, known)
    return col, ink


def downscale_rgb(rgb, size):
    chans = [np.asarray(Image.fromarray(rgb[..., k].astype(np.float32), "F").resize(size, Image.LANCZOS))
             for k in range(rgb.shape[2])]
    return np.clip(np.stack(chans, axis=2), 0.0, 1.0)


def ink_curve(cov):
    """Nach dem Verkleinern: Kantenglättung der Linien zusammenziehen (0,08–0,65 -> 0–1). Dünn gewordene Linien
    werden so wieder satt schwarz statt grau (Strichstärke wie im Druck, nicht wie ein verkleinertes Foto)."""
    t = np.clip((cov - 0.08) / (0.65 - 0.08), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def downscale_cov(cov, size):
    c = np.clip(np.asarray(Image.fromarray(cov.astype(np.float32), "F").resize(size, Image.LANCZOS)), 0.0, 1.0)
    return ink_curve(c)


def save_rgb(rgb, path):
    Image.fromarray((np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB").save(path)


def save_ink(cov, path):
    """Tusche als RGBA: schwarz, Alpha = Deckung."""
    h, w = cov.shape
    out = np.zeros((h, w, 4), np.uint8)
    out[..., 3] = (np.clip(cov, 0, 1) * 255 + 0.5).astype(np.uint8)
    Image.fromarray(out, "RGBA").save(path)
