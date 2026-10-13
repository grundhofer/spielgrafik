"""Gemeinsame Hilfen für den Eintrag tusche-sumie: Rauschen, Papier, Tusche-Modell.

Tusche-Modell: Jedes Element wird als Tuschedichte d (0 = Papier, 1 = tiefstes Schwarz) und optional als
Zinnober-Dichte r gespeichert. Farbe = Papier * T mit T = (1 - d * (1 - INK)) * (1 - r * (1 - VERMILION)).
So bleiben die Papierfasern überall sichtbar, und Tusche über Tusche wird dunkler (wie auf echtem Papier).
"""
import math
import pathlib

import numpy as np
from PIL import Image, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parents[1]          # styles/tusche-sumie
PROJECT = ROOT.parents[1]
W, H = 1280, 720

PAPER_RGB = np.array([238, 232, 217], np.float32) / 255.0  # warmes Reispapier
INK_RGB = np.array([22, 22, 26], np.float32) / 255.0        # Tusche (sehr leicht kühl)
VERMILION_RGB = np.array([196, 52, 36], np.float32) / 255.0  # Zinnober (Stempelpaste)
# Godots Textur-Import ("fix alpha border") ersetzt die Farbe aller Pixel mit Alpha < 20/255 durch die Farbe des
# nächsten deckenderen Pixels (Radius 4). Texturen, deren RGB auch bei kleinem Alpha zählt (Hintergrund,
# Figur), speichern Alpha deshalb als ALPHA_FLOOR + a * (1 - ALPHA_FLOOR); die Shader rechnen das zurück.
ALPHA_FLOOR = 21 / 255


def rng(seed):
    return np.random.default_rng(seed)


def blur(a, sigma):
    """Gauß-Weichzeichner für float-Arrays (über Pillow, Kanal F)."""
    if sigma <= 0:
        return a
    a = np.asarray(a, np.float32)
    p = int(math.ceil(sigma * 3))
    out = np.pad(a, [(p, p), (p, p)] + [(0, 0)] * (a.ndim - 2), mode="reflect")
    hh, ww = out.shape[:2]
    fy = np.fft.fftfreq(hh)[:, None]
    fx = np.fft.rfftfreq(ww)[None, :]
    g = np.exp(-2 * (math.pi * sigma) ** 2 * (fy ** 2 + fx ** 2)).astype(np.float32)
    if a.ndim == 3:
        g = g[..., None]
    out = np.fft.irfft2(np.fft.rfft2(out, axes=(0, 1)) * g, s=(hh, ww), axes=(0, 1)).astype(np.float32)
    return out[p:p + a.shape[0], p:p + a.shape[1]]


def noise(h, w, cell, seed, octaves=1, falloff=0.5):
    """Wertrauschen (bikubisch hochskaliertes Zufallsraster), Mittel 0, ungefähr -1..1."""
    r = rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        c = max(2, cell / (2 ** o))
        gh, gw = int(h / c) + 3, int(w / c) + 3
        g = r.uniform(-1, 1, (gh, gw)).astype(np.float32)
        im = Image.fromarray(g, mode="F").resize((int(gw * c), int(gh * c)), Image.BICUBIC)
        a = np.asarray(im, np.float32)
        oy, ox = r.integers(0, max(1, a.shape[0] - h)), r.integers(0, max(1, a.shape[1] - w))
        out += amp * a[oy:oy + h, ox:ox + w]
        tot += amp
        amp *= falloff
    return out / tot


def compose(paper, d, r=None):
    """Papier (H,W,3 float 0..1) * Transmission von Tusche d und Zinnober r."""
    t = 1.0 - d[..., None] * (1.0 - INK_RGB)
    if r is not None:
        t = t * (1.0 - r[..., None] * (1.0 - VERMILION_RGB))
    return paper * t


def transmission_rgba(d, r=None, alpha=None):
    """Bild für Godot-Ebenen: RGB = Transmission (weiß = Papier durchlassen), A = Deckung/Silhouette."""
    t = 1.0 - d[..., None] * (1.0 - INK_RGB)
    if r is not None:
        t = t * (1.0 - r[..., None] * (1.0 - VERMILION_RGB))
    a = np.ones(d.shape, np.float32) if alpha is None else alpha
    rgba = np.concatenate([t, a[..., None]], axis=2)
    return Image.fromarray((np.clip(rgba, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA")


def save_rgb(a, path):
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB").save(path)
