"""KI-Pixelbild auf ein echtes Pixelraster bringen: je Zielpixel die häufigste Farbe im Zellinneren.

Das Bildmodell zeichnet ein ungleichmäßiges Pseudo-Raster (hier 4,5–4,9 Bildpixel je Kunstpixel) mit weichen
Kanten. BOX-Mitteln mischt an jeder Kante Zwischentöne; reines Nearest trifft oft die Kante. Hier wird das
Quellbild erst mit k-means (Oklab) auf K Farben vorquantisiert, dann gewinnt je Zielzelle die Farbe, die im
inneren Teil der Zelle (Rand um `inset` gekürzt) am häufigsten vorkommt. Ergebnis: harte Pixel, nur Farben,
die im Bild flächig vorkommen.
"""
import numpy as np
from sneslib import kmeans, nearest, oklab, oklab_to_rgb


def reduce_mode(rgb, out_w, out_h, k=128, inset=0.22, seed=1, sample=120000):
    rgb = np.asarray(rgb, dtype=np.float64)[..., :3]
    H, W = rgb.shape[:2]
    lab = oklab(rgb.reshape(-1, 3))
    rng = np.random.default_rng(seed)
    smp = lab[rng.choice(len(lab), min(sample, len(lab)), replace=False)]
    cent = kmeans(smp, k, iters=25, seed=seed)
    lbl = nearest(lab, cent).reshape(H, W)
    sx, sy = W / out_w, H / out_h
    out = np.zeros((out_h, out_w), dtype=np.int64)
    for y in range(out_h):
        y0 = int(np.floor((y + inset) * sy)); y1 = max(y0 + 1, int(np.ceil((y + 1 - inset) * sy)))
        for x in range(out_w):
            x0 = int(np.floor((x + inset) * sx)); x1 = max(x0 + 1, int(np.ceil((x + 1 - inset) * sx)))
            out[y, x] = np.bincount(lbl[y0:y1, x0:x1].ravel(), minlength=k).argmax()
    pal = np.clip(oklab_to_rgb(cent), 0, 255)
    return out, pal, cent
