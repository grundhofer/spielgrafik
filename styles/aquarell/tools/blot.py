#!/usr/bin/env python3
"""Aquarell-Kleckse aus geschichteten, rekursiv verformten Polygonen (Verfahren nach Tyler Hobbs, 2017).

Ein Grundpolygon wird einige Male verformt (jede Kante bekommt einen versetzten Mittelpunkt). Davon entstehen
30–60 weitere, jeweils neu verformte Abkömmlinge, die mit wenigen Prozent Deckkraft übereinander gelegt werden.
So entsteht ein Fleck mit dichtem Kern, weich auslaufendem, unregelmäßigem Rand und einzelnen Trockenrändern.
"""
import numpy as np
from PIL import Image, ImageDraw

import wc


def deform(pts, var, depth, rng, mutate=0.15):
    pts = np.asarray(pts, dtype=np.float64)
    var = np.asarray(var, dtype=np.float64)
    for _ in range(depth):
        a = pts
        b = np.roll(pts, -1, axis=0)
        L = np.linalg.norm(b - a, axis=1, keepdims=True)
        mid = (a + b) / 2 + rng.normal(0, 1, a.shape) * L * var[:, None] * 0.38
        nv = var * np.exp(rng.normal(0, mutate, var.shape))
        out = np.empty((2 * len(a), 2))
        out[0::2], out[1::2] = a, mid
        vv = np.empty(2 * len(a))
        vv[0::2], vv[1::2] = var, nv
        pts, var = out, vv
    return pts, var


def ellipse(cx, cy, rx, ry, n=10, rng=None, jitter=0.1):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    if rng is not None:
        t = t + rng.normal(0, jitter, n)
    return np.stack([cx + rx * np.cos(t), cy + ry * np.sin(t)], 1)


def blot(w, h, base, seed, layers=40, alpha=0.045, var=0.8, depth0=3, depth1=3, texture=0.5, ss=1):
    """Gibt die Deckung (0..1, h x w) eines Kleckses zurück. base: Grundpolygon in Pixeln."""
    rng = np.random.default_rng(seed)
    v0 = np.full(len(base), var) * np.exp(rng.normal(0, 0.4, len(base)))
    p0, v0 = deform(base, v0, depth0, rng)
    acc = np.zeros((h * ss, w * ss))
    tex_cache = [wc.value_noise(h * ss, w * ss, 14 * ss, seed + 100 + k, 3) for k in range(3)]
    for i in range(layers):
        p, _ = deform(p0, v0 * 0.7, depth1, rng)
        im = Image.new("L", (w * ss, h * ss), 0)
        ImageDraw.Draw(im).polygon([tuple(q * ss) for q in p], fill=255)
        m = np.asarray(im, dtype=np.float64) / 255.0
        if texture > 0:
            t = tex_cache[i % 3]
            m *= np.clip(1.0 - texture + texture * 2.0 * t, 0, 1)
        acc += m * alpha
    acc = 1.0 - np.exp(-acc * 2.2)      # Sättigung: viele Lagen nähern sich voller Deckung
    if ss > 1:
        acc = np.asarray(Image.fromarray(acc.astype(np.float32), "F").resize((w, h), Image.BOX))
    # Sicherheitsfenster: nichts darf an der Bildkante gerade abgeschnitten wirken
    mx, my = max(2, int(w * 0.06)), max(2, int(h * 0.08))
    wx = np.minimum(wc.smoothstep(0, mx, np.arange(w)), wc.smoothstep(0, mx, w - 1 - np.arange(w)))
    wy = np.minimum(wc.smoothstep(0, my, np.arange(h)), wc.smoothstep(0, my, h - 1 - np.arange(h)))
    return np.clip(acc, 0, 1) * wy[:, None] * wx[None, :]


def stroke(w, h, pts, widths, seed, layers=18, alpha=0.09, var=0.35, ss=2):
    """Pinselstrich entlang einer Linie mit veränderlicher Breite, als geschichteter Klecks."""
    pts = np.asarray(pts, dtype=np.float64)
    widths = np.asarray(widths, dtype=np.float64)
    d = np.gradient(pts, axis=0)
    nrm = np.stack([-d[:, 1], d[:, 0]], 1)
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-9
    left = pts + nrm * widths[:, None] / 2
    right = pts - nrm * widths[:, None] / 2
    base = np.concatenate([left, right[::-1]])
    return blot(w, h, base, seed, layers=layers, alpha=alpha, var=var, depth0=2, depth1=2, texture=0.25, ss=ss)


def tide(cov, sigma=2.0, k=0.6):
    """Trockenrand: Pigment sammelt sich innen am Rand des Flecks."""
    return np.clip(cov * (1.0 + k * wc.inner_edge(cov, sigma)), 0, 1)
