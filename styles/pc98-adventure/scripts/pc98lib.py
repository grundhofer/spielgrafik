"""Gemeinsame Funktionen für den Eintrag pc98-adventure: 12-Bit-Palette, Musterdithering, Indexbilder.

Musterdithering (geordnet, zwei Farben je Pixel): Für jedes Pixel wird das Farbpaar aus der Palette gesucht,
dessen Mischung im festen Raster die Farbe am besten trifft. Das Mischverhältnis wird auf wenige Stufen
gerundet (0, 1/4, 1/2, 3/4, 1 bei levels=4), die Bayer-4x4-Schwelle entscheidet, welches der beiden Pixel
gesetzt wird. Ergebnis: flache Flächen bleiben flach, Verläufe werden zu Schachbrett- und Punktrastern
(wie von Hand gesetzte Kachelmuster), kein Rauschen wie bei Fehlerverteilung. Ein Strafterm für weit
auseinanderliegende Paare verhindert Mischungen wie Rot+Grün.
"""
import numpy as np

BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], dtype=np.float32)


def c12(rgb):
    """Jeden Kanal auf 4 Bit runden (16 Stufen: 0x00, 0x11, ... 0xff) wie die Palettenregister."""
    return (np.round(np.asarray(rgb, dtype=np.float32) / 17.0) * 17).clip(0, 255).astype(np.uint8)


def hexc(h):
    h = h.strip().lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.uint8)


def tohex(c):
    return "%02x%02x%02x" % tuple(int(v) for v in c)


def to_linear(rgb):
    c = np.asarray(rgb, dtype=np.float32) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_oklab(lin):
    m1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]], dtype=np.float32)
    m2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]], dtype=np.float32)
    return np.cbrt(np.maximum(lin, 0) @ m1.T) @ m2.T


def oklab(rgb):
    return lin_to_oklab(to_linear(rgb))


def kmeans_fixed(pixels_lab, fixed_lab, init_lab, iters=25, weights=None):
    """k-means in Oklab, bei dem die festen Zentren (Akzentfarben) nicht wandern."""
    free = np.array(init_lab, dtype=np.float32)
    fixed = np.array(fixed_lab, dtype=np.float32).reshape(-1, 3)
    w = np.ones(len(pixels_lab), np.float32) if weights is None else weights.astype(np.float32)
    for _ in range(iters):
        cent = np.vstack([fixed, free])
        d = ((pixels_lab[:, None, :] - cent[None]) ** 2).sum(-1)
        lab = d.argmin(1)
        for k in range(len(free)):
            m = lab == len(fixed) + k
            if m.any():
                free[k] = (pixels_lab[m] * w[m, None]).sum(0) / w[m].sum()
    return free


def oklab_to_rgb(lab):
    m2i = np.linalg.inv(np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                                  [1.9779984951, -2.4285922050, 0.4505937099],
                                  [0.0259040371, 0.7827717662, -0.8086757660]]))
    m1i = np.linalg.inv(np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                                  [0.2119034982, 0.6806995451, 0.1073969566],
                                  [0.0883024619, 0.2817188376, 0.6299787005]]))
    lms = (np.asarray(lab, dtype=np.float64) @ m2i.T) ** 3
    lin = np.clip(lms @ m1i.T, 0, 1)
    srgb = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055)
    return np.clip(srgb * 255, 0, 255)


def pattern_dither(rgb, pal, allowed=None, levels=4, lam=0.6, mask=None, ox=0, oy=0):
    """rgb (H,W,3) uint8, pal (K,3) uint8 -> Indexbild (H,W) int.

    allowed: Liste erlaubter Paletteneinträge (oder (H,W,K)-bool-Maske je Pixel über mask_allowed).
    levels: Stufen des Mischverhältnisses (4 -> 0, 1/4, 1/2, 3/4, 1).
    lam: Strafe für Paare mit großem Farbabstand (Oklab), skaliert mit t*(1-t).
    ox, oy: Lage des Bildes auf dem Bildschirm, damit das Raster bildschirmfest ist.
    """
    h, w, _ = rgb.shape
    K = len(pal)
    idx_ok = list(range(K)) if allowed is None else list(allowed)
    pairs = [(a, a) for a in idx_ok] + [(a, b) for i, a in enumerate(idx_ok) for b in idx_ok[i + 1:]]
    pa = np.array([p[0] for p in pairs]); pb = np.array([p[1] for p in pairs])
    plin = to_linear(pal)
    plab = lin_to_oklab(plin)
    A, B = plin[pa], plin[pb]
    D = B - A
    DD = (D * D).sum(-1)
    pair_dist2 = ((plab[pa] - plab[pb]) ** 2).sum(-1)
    px = to_linear(rgb.reshape(-1, 3))
    plab_px = lin_to_oklab(px)
    best_err = np.full(len(px), np.inf, np.float32)
    best_p = np.zeros(len(px), np.int32)
    best_t = np.zeros(len(px), np.float32)
    CH = 4096
    for s in range(0, len(px), CH):
        c = px[s:s + CH]
        cl = plab_px[s:s + CH]
        t = ((c[:, None, :] - A[None]) * D[None]).sum(-1) / np.maximum(DD[None], 1e-9)
        t = np.clip(np.round(np.clip(t, 0, 1) * levels) / levels, 0, 1)
        mix = A[None] + t[..., None] * D[None]
        ml = lin_to_oklab(mix)
        err = ((ml - cl[:, None, :]) ** 2).sum(-1) + lam * pair_dist2[None] * t * (1 - t)
        j = err.argmin(1)
        best_err[s:s + CH] = err[np.arange(len(c)), j]
        best_p[s:s + CH] = j
        best_t[s:s + CH] = t[np.arange(len(c)), j]
    yy, xx = np.mgrid[0:h, 0:w]
    th = ((BAYER4[(yy + oy) % 4, (xx + ox) % 4] + 0.5) / 16.0).reshape(-1)
    out = np.where(th < best_t, pb[best_p], pa[best_p])
    return out.reshape(h, w)


def index_png(idx, alpha=None):
    """Indexbild als RGBA-PNG-Daten: Rot = Grün = Blau = Index * 17 (Godot liest Index = round(r * 15))."""
    v = (np.asarray(idx, dtype=np.int32) * 17).astype(np.uint8)
    a = np.full(v.shape, 255, np.uint8) if alpha is None else np.where(alpha, 255, 0).astype(np.uint8)
    v = np.where(a > 0, v, 0).astype(np.uint8)
    return np.dstack([v, v, v, a])


def colorize(idx, pal, alpha=None):
    rgb = np.asarray(pal, dtype=np.uint8)[idx]
    if alpha is None:
        return rgb
    return np.dstack([rgb, np.where(alpha, 255, 0).astype(np.uint8)])
