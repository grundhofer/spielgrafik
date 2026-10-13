"""Gemeinsame Helfer: Farbtrennung eines KI-Drucks in drei Druckplatten.

Ein Pixel des KI-Bildes wird der Plattenkombination zugeordnet, deren Druckfarbe ihm am nächsten liegt
(CIELAB-Abstand). Die Kombinationen und ihre Farben im KI-Bild stehen in SEPARATION (aus k-means der Bilder gelesen).
Platten: K = Schwarzstock (Holz), T = Petrol (Linol), O = Zinnober (Linol).
Ausgabe als RGB-Bild: R = K, G = T, B = O (Deckung 0..1). Papier ist (0, 0, 0).
"""
import numpy as np

# Farbe im KI-Bild -> (K, T, O). Aus k-means von raw/bg2.png bzw. raw/bg.png abgelesen (siehe build_plates.py).
SEPARATION = [
    ("paper",      (240, 214, 172), (0, 0, 0)),
    ("black",      (11, 13, 13),    (1, 0, 0)),
    ("black_teal", (5, 28, 35),     (1, 1, 0)),   # Schwarz über Petrol: blauschwarzer Nachthimmel
    ("teal",       (22, 87, 104),   (0, 1, 0)),
    ("teal_dark",  (11, 58, 73),    (0, 1, 0)),   # dunkles Petrol des Modells: als Petrol drucken
    ("orange",     (235, 107, 36),  (0, 0, 1)),
    ("brown",      (92, 62, 40),    (0, 1, 1)),   # Überdruck Petrol + Zinnober
]


def srgb_to_lab(rgb):
    c = np.asarray(rgb, dtype=np.float64) / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ m.T / np.array([0.9505, 1.0, 1.089])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], -1)


def classify(rgb, separation=SEPARATION):
    """rgb: HxWx3 uint8 -> Index-Bild HxW in separation."""
    lab = srgb_to_lab(rgb)
    cen = srgb_to_lab(np.array([s[1] for s in separation], dtype=np.float64))
    d = ((lab[:, :, None, :] - cen[None, None]) ** 2).sum(-1)
    return d.argmin(-1)


def majority3(idx, n):
    """3x3-Mehrheitsfilter auf einem Indexbild (entfernt Einzelpixel-Sprenkel des Modells)."""
    h, w = idx.shape
    pad = np.pad(idx, 1, mode="edge")
    counts = np.zeros((n, h, w), np.int16)
    for dy in range(3):
        for dx in range(3):
            win = pad[dy:dy + h, dx:dx + w]
            for k in range(n):
                counts[k] += (win == k)
    return counts.argmax(0)


def plates_from_index(idx, separation=SEPARATION):
    lut = np.array([s[2] for s in separation], dtype=np.float32)
    return lut[idx]          # HxWx3, 0/1


def kmeans(px, k, seed=0, iters=30):
    rng = np.random.default_rng(seed)
    c = px[rng.choice(len(px), k, replace=False)].astype(np.float64)
    for _ in range(iters):
        d = ((px[:, None, :] - c[None]) ** 2).sum(-1)
        lab = d.argmin(1)
        c = np.array([px[lab == j].mean(0) if (lab == j).any() else c[j] for j in range(k)])
    return c, np.bincount(lab, minlength=k) / len(lab)
