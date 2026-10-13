"""Hilfsfunktionen für den Amiga-OCS-Look: 12-Bit-Palette (16 Stufen je Kanal), Paletten-Auswahl in Oklab,
geordnetes Muster-Dithering mit Farbpaaren (wie von Hand gesetzte Schachbrett- und Kreuzraster).

Nur NumPy/Pillow. Alle Funktionen sind deterministisch (feste Seeds).
"""
import numpy as np

BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], dtype=np.float64)


def srgb_to_lin(c):
    c = np.clip(np.asarray(c, dtype=np.float64), 0, 255) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055) * 255.0


def lin_to_oklab(c):
    m1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]])
    m2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]])
    return np.cbrt(np.maximum(c, 0) @ m1.T) @ m2.T


def oklab(rgb):
    return lin_to_oklab(srgb_to_lin(rgb))


def snap12(rgb):
    """Auf das 12-Bit-Raster des Amiga bringen: je Kanal 16 Stufen (0x0..0xF), angezeigt als n*17."""
    return np.clip(np.round(np.asarray(rgb, dtype=np.float64) / 17.0), 0, 15).astype(int) * 17


def to_hex12(rgb):
    r, g, b = (int(v) // 17 for v in rgb)
    return f"{r:X}{g:X}{b:X}"


def kmeans_lab(px, k, iters=20, seed=1, init=None, fixed=0):
    """k-means in Oklab (px: sRGB Nx3). init: Startzentren (sRGB); die ersten `fixed` davon bleiben fest
    (z. B. Figurenfarben), die übrigen werden mitoptimiert. Gibt sRGB-Zentren und Zuordnung zurück."""
    rng = np.random.default_rng(seed)
    lab = oklab(px)
    cent = [] if init is None else list(oklab(np.asarray(init, dtype=np.float64)))
    if not cent:
        cent.append(lab[rng.integers(len(lab))])
    d = np.min([((lab - c) ** 2).sum(1) for c in cent], 0)
    while len(cent) < k:
        c = lab[rng.choice(len(lab), p=d / d.sum())]
        cent.append(c)
        d = np.minimum(d, ((lab - c) ** 2).sum(1))
    cent = np.array(cent)
    for _ in range(iters):
        lbl = np.argmin(((lab[:, None] - cent[None]) ** 2).sum(-1), 1)
        for j in range(fixed, k):
            m = lbl == j
            if m.any():
                cent[j] = lab[m].mean(0)
    lbl = np.argmin(((lab[:, None] - cent[None]) ** 2).sum(-1), 1)
    rgb = np.array([px[lbl == j].mean(0) if (lbl == j).any() else px[0] for j in range(k)])
    if fixed:
        rgb[:fixed] = np.asarray(init, dtype=np.float64)[:fixed]
    return rgb, lbl


def pair_candidates(pal, levels=16, allowed=None, spread=0.35):
    """Alle Mischungen zweier Palettenfarben (i, j, Anteil r von j) als Oklab-Farbe plus Strafwert für
    unähnliche Paare (gegen Blau-Orange-Schachbretter). allowed: Liste erlaubter Indizes (z. B. ohne
    Animationsfarben). Mischung in linearem Licht wie auf dem Bildschirm."""
    idx = np.arange(len(pal)) if allowed is None else np.asarray(allowed)
    lin = srgb_to_lin(pal[idx])
    lab = lin_to_oklab(lin)
    I, J, R, C, P = [], [], [], [], []
    for a in range(len(idx)):
        for b in range(a, len(idx)):
            dist = np.sqrt(((lab[a] - lab[b]) ** 2).sum())
            rs = [0] if a == b else range(1, levels)
            for r in rs:
                f = r / levels
                mix = lin_to_oklab(lin[a] * (1 - f) + lin[b] * f)
                I.append(idx[a]); J.append(idx[b]); R.append(r); C.append(mix)
                P.append(spread * dist * dist * (0.5 + abs(f - 0.5)) if a != b else 0.0)
    return np.array(I), np.array(J), np.array(R), np.array(C), np.array(P)


def dither(rgb, pal, mask=None, levels=16, allowed=None, spread=0.35, bayer=BAYER4, chunk=1500):
    """Geordnetes Muster-Dithering: je Pixel das Paar (i, j) und den Anteil r, deren Mischung der Zielfarbe am
    nächsten kommt (Oklab, plus Strafwert für unähnliche Paare); die Bayer-Schwelle entscheidet, welcher der
    beiden Einträge gesetzt wird. rgb: HxWx3 sRGB; gibt HxW Indizes (-1 außerhalb mask)."""
    H, W = rgb.shape[:2]
    I, J, R, C, P = pair_candidates(pal, levels, allowed, spread)
    target = oklab(rgb.reshape(-1, 3))
    best = np.zeros(len(target), int)
    for s in range(0, len(target), chunk):
        t = target[s:s + chunk]
        d = ((t[:, None, :] - C[None]) ** 2).sum(-1) + P[None]
        best[s:s + chunk] = np.argmin(d, 1)
    ys, xs = np.mgrid[0:H, 0:W]
    n = bayer.shape[0]
    th = ((bayer[ys % n, xs % n] + 0.5) / bayer.size * levels).reshape(-1)
    out = np.where(th < R[best], J[best], I[best]).reshape(H, W)
    if mask is not None:
        out = np.where(mask, out, -1)
    return out


def nearest_idx(rgb, pal, allowed=None):
    idx = np.arange(len(pal)) if allowed is None else np.asarray(allowed)
    lab = oklab(np.asarray(rgb, dtype=np.float64).reshape(-1, 3))
    plab = oklab(pal[idx])
    d = ((lab[:, None] - plab[None]) ** 2).sum(-1)
    return idx[np.argmin(d, 1)].reshape(np.asarray(rgb).shape[:-1])
