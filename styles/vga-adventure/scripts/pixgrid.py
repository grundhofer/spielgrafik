"""Hilfsfunktionen: KI-Pixel-Art auf ihr echtes Raster einrasten und Sprite-Frames verkleinern."""
import numpy as np
from PIL import Image


def oklab(rgb):
    c = np.clip(rgb, 0, 255) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]])
    m2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]])
    return np.cbrt(c @ m1.T) @ m2.T


def kmeans(px, k, iters=15, seed=1):
    """k-means im Oklab-Raum, gibt RGB-Zentren zurück."""
    rng = np.random.default_rng(seed)
    lab = oklab(px)
    # k-means++ Start
    cent = [lab[rng.integers(len(lab))]]
    d = ((lab - cent[0]) ** 2).sum(1)
    for _ in range(1, k):
        c = lab[rng.choice(len(lab), p=d / d.sum())] if d.sum() > 0 else lab[rng.integers(len(lab))]
        cent.append(c)
        d = np.minimum(d, ((lab - c) ** 2).sum(1))
    cent = np.array(cent)
    for _ in range(iters):
        lbl = np.argmin(((lab[:, None] - cent[None]) ** 2).sum(-1), 1)
        for j in range(k):
            m = lbl == j
            if m.any():
                cent[j] = lab[m].mean(0)
    lbl = np.argmin(((lab[:, None] - cent[None]) ** 2).sum(-1), 1)
    rgb = np.array([px[lbl == j].mean(0) if (lbl == j).any() else px[0] for j in range(k)])
    return np.clip(np.round(rgb), 0, 255)


def nearest(rgb, pal):
    """Index der nächsten Palettenfarbe (Oklab) für ein HxWx3-Array."""
    lab = oklab(rgb.reshape(-1, 3).astype(np.float64))
    plab = oklab(pal.astype(np.float64))
    best = np.full(len(lab), np.inf); idx = np.zeros(len(lab), np.int32)
    for k in range(len(pal)):
        d = ((lab - plab[k]) ** 2).sum(1)
        m = d < best; best[m] = d[m]; idx[m] = k
    return idx.reshape(rgb.shape[:2])


def snap(im, pitch, ox=0.0, oy=0.0, cover=0.5):
    """Raster mit gegebener (gebrochener) Teilung: je Zelle Mittel der opaken Pixel aus dem Zellkern."""
    a = np.asarray(im.convert('RGBA')).astype(np.float64)
    H, W = a.shape[:2]
    nx, ny = int((W - ox) / pitch), int((H - oy) / pitch)
    out = np.zeros((ny, nx, 4))
    for j in range(ny):
        y0, y1 = oy + j * pitch, oy + (j + 1) * pitch
        # Zellkern (mittlere 60 %), damit Kanten zwischen Blöcken nicht mischen
        cy0, cy1 = int(y0 + 0.2 * pitch), int(np.ceil(y1 - 0.2 * pitch))
        for i in range(nx):
            x0, x1 = ox + i * pitch, ox + (i + 1) * pitch
            cx0, cx1 = int(x0 + 0.2 * pitch), int(np.ceil(x1 - 0.2 * pitch))
            cell = a[cy0:cy1, cx0:cx1].reshape(-1, 4)
            op = cell[:, 3] > 128
            if op.mean() >= cover:
                out[j, i, :3] = np.median(cell[op, :3], 0)
                out[j, i, 3] = 255
    return out


def best_phase(im, pitch, steps=6):
    """Rasterversatz suchen, bei dem die Zellen am gleichmäßigsten sind (kleinste Varianz im Kern)."""
    a = np.asarray(im.convert('RGB')).astype(np.float64)
    best = None
    for oy in np.linspace(0, pitch, steps, endpoint=False):
        for ox in np.linspace(0, pitch, steps, endpoint=False):
            H, W = a.shape[:2]
            nx, ny = int((W - ox) / pitch), int((H - oy) / pitch)
            xs = (ox + (np.arange(nx) + 0.5) * pitch).astype(int)
            ys = (oy + (np.arange(ny) + 0.5) * pitch).astype(int)
            # Abweichung der Pixel neben der Zellmitte von der Mitte
            off = max(1, int(pitch * 0.3))
            c = a[np.ix_(ys, xs)]
            v = sum(np.abs(a[np.ix_(np.clip(ys + dy, 0, H - 1), np.clip(xs + dx, 0, W - 1))] - c).mean()
                    for dy, dx in ((off, 0), (-off, 0), (0, off), (0, -off)))
            if best is None or v < best[0]:
                best = (v, ox, oy)
    return best[1], best[2]


def half(g, pal, dark_lum=0.30, dark_w=1.6, cover=2):
    """Pixel-Art exakt auf halbe Größe: je 2x2-Block die häufigste Palettenfarbe, dunkle Konturfarben bevorzugt."""
    H, W = g.shape[0] // 2 * 2, g.shape[1] // 2 * 2
    g = g[:H, :W]
    op = g[..., 3] > 128
    idx = nearest(g[..., :3], pal)
    L = oklab(pal.astype(np.float64))[:, 0]
    w = np.where(L < dark_lum, dark_w, 1.0)
    out = np.zeros((H // 2, W // 2, 4))
    for y in range(H // 2):
        for x in range(W // 2):
            m = op[2 * y:2 * y + 2, 2 * x:2 * x + 2]
            if m.sum() < cover:
                continue
            cnt = np.bincount(idx[2 * y:2 * y + 2, 2 * x:2 * x + 2][m], minlength=len(pal)) * w
            out[y, x, :3] = pal[cnt.argmax()]
            out[y, x, 3] = 255
    return out
