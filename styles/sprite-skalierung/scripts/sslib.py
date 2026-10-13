"""Hilfsfunktionen für sprite-skalierung: Raster finden, Objekte trennen, auf das Kunstraster einrasten,
Palette auf 15 Farben mit 15-Bit-RGB (5 Bit je Kanal) bringen."""
import numpy as np
from PIL import Image


def load_rgba(path):
    return np.asarray(Image.open(path).convert("RGBA")).astype(np.int32)


def oklab(rgb):
    c = np.clip(np.asarray(rgb, dtype=np.float64), 0, 255) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]])
    m2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]])
    return np.cbrt(c @ m1.T) @ m2.T


def snap5(rgb):
    """Auf das 15-Bit-Raster: 32 Stufen je Kanal, als 8 Bit k*255/31 gerundet."""
    k = np.round(np.asarray(rgb, dtype=np.float64) * 31 / 255)
    return np.round(k * 255 / 31).astype(np.int32)


def edge_signal(rgba, axis):
    a = rgba.astype(np.float64)
    d = np.abs(np.diff(a[..., :3], axis=axis)).sum(-1)
    m = (a[..., 3] > 127)
    if axis == 1:
        mm = m[:, 1:] | m[:, :-1]
        return (d * mm).sum(0)
    mm = m[1:, :] | m[:-1, :]
    return (d * mm).sum(1)


def find_grid(rgba, lo=3.0, hi=16.0):
    """Kunstpixelgröße und Phase je Achse aus den Farbkanten (Kanten liegen auf dem Raster)."""
    res = []
    for axis in (1, 0):
        e = edge_signal(rgba, axis)
        e = e / (e.mean() + 1e-9)
        best = None
        for p in np.arange(lo, hi, 0.01):
            n = int(len(e) / p)
            for ph in np.arange(0, p, 0.25):
                pos = np.round(ph + np.arange(n) * p - 1).astype(int)
                pos = pos[(pos >= 0) & (pos < len(e))]
                if len(pos) < 8:
                    continue
                s = e[pos].mean()
                if best is None or s > best[0]:
                    best = (s, p, ph)
        res.append(best)
    return res  # [(score, px, phase) für x, (score, py, phase) für y]


def components(alpha, min_px=400, gap=6):
    """Zusammenhängende Objekte (Alpha > 127), über kleine Lücken hinweg verbunden. Gibt Boxen zurück."""
    from collections import deque
    m = alpha > 127
    # Lücken schließen: Dilatation um gap Pixel (Quadrat)
    h, w = m.shape
    dil = m.copy()
    for dy in range(-gap, gap + 1, max(1, gap // 2)):
        for dx in range(-gap, gap + 1, max(1, gap // 2)):
            sh = np.zeros_like(m)
            ys, ye = max(0, dy), h + min(0, dy)
            xs, xe = max(0, dx), w + min(0, dx)
            sh[ys:ye, xs:xe] = m[ys - dy:ye - dy, xs - dx:xe - dx]
            dil |= sh
    lab = np.zeros((h, w), dtype=np.int32)
    boxes = []
    cur = 0
    for y0 in range(h):
        row = dil[y0]
        for x0 in np.nonzero(row & (lab[y0] == 0))[0]:
            if lab[y0, x0]:
                continue
            cur += 1
            q = deque([(y0, x0)])
            lab[y0, x0] = cur
            ys, xs = [y0], [x0]
            while q:
                y, x = q.popleft()
                for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                    if 0 <= ny < h and 0 <= nx < w and dil[ny, nx] and not lab[ny, nx]:
                        lab[ny, nx] = cur
                        q.append((ny, nx))
                        ys.append(ny)
                        xs.append(nx)
            ys, xs = np.array(ys), np.array(xs)
            sel = m[ys, xs]
            if sel.sum() >= min_px:
                boxes.append((int(xs[sel].min()), int(ys[sel].min()), int(xs[sel].max()) + 1, int(ys[sel].max()) + 1,
                              int(sel.sum())))
    return boxes


def kmeans_lab(cols, weights, k, iters=30, seed=7):
    """k-means in Oklab über Farben mit Gewichten; Startwerte k-means++ mit festem Seed."""
    rng = np.random.default_rng(seed)
    lab = oklab(cols)
    k = min(k, len(cols))
    cent = [lab[np.argmax(weights)]]
    for _ in range(1, k):
        d = np.min([((lab - c) ** 2).sum(1) for c in cent], axis=0) * weights
        cent.append(lab[rng.choice(len(lab), p=d / d.sum())] if d.sum() > 0 else lab[rng.integers(len(lab))])
    cent = np.array(cent)
    for _ in range(iters):
        d = ((lab[:, None] - cent[None]) ** 2).sum(-1)
        a = d.argmin(1)
        for j in range(k):
            s = a == j
            if s.any():
                cent[j] = (lab[s] * weights[s, None]).sum(0) / weights[s].sum()
    d = ((lab[:, None] - cent[None]) ** 2).sum(-1)
    a = d.argmin(1)
    # Palettenfarbe = gewichtet häufigste echte Farbe im Cluster (keine Mischfarben)
    pal = []
    for j in range(k):
        s = np.nonzero(a == j)[0]
        if len(s):
            pal.append(cols[s[np.argmax(weights[s])]])
    return np.array(pal)


def to_grid(rgba, box, px, py, phx, phy, pre_colors=48, trim=0.2):
    """Ausschnitt auf das Kunstraster einrasten: je Zelle Mehrheit für Alpha, häufigste (vorquantisierte)
    Farbe im Zellinneren für die Farbe."""
    x0, y0, x1, y1 = box[:4]
    # Zellgrenzen am globalen Raster ausrichten
    cx0 = int(np.floor((x0 - phx) / px))
    cx1 = int(np.ceil((x1 - phx) / px))
    cy0 = int(np.floor((y0 - phy) / py))
    cy1 = int(np.ceil((y1 - phy) / py))
    W, H = cx1 - cx0, cy1 - cy0
    src = rgba
    opaque = src[..., 3] > 127
    cols = src[..., :3][opaque]
    uniq, inv, cnt = np.unique(cols, axis=0, return_inverse=True, return_counts=True)
    pal = kmeans_lab(uniq.astype(np.float64), cnt.astype(np.float64), pre_colors)
    out = np.zeros((H, W, 4), dtype=np.int32)
    plab = oklab(pal)
    for j in range(H):
        for i in range(W):
            xa = phx + (cx0 + i) * px
            ya = phy + (cy0 + j) * py
            xs0, xs1 = int(round(xa)), int(round(xa + px))
            ys0, ys1 = int(round(ya)), int(round(ya + py))
            xs0, ys0 = max(xs0, 0), max(ys0, 0)
            xs1, ys1 = min(xs1, src.shape[1]), min(ys1, src.shape[0])
            if xs1 <= xs0 or ys1 <= ys0:
                continue
            cell = src[ys0:ys1, xs0:xs1]
            if not (x0 - px <= xa <= x1 and y0 - py <= ya <= y1):
                continue
            a = cell[..., 3] > 127
            if a.mean() < 0.5:
                continue
            tx, ty = int((xs1 - xs0) * trim), int((ys1 - ys0) * trim)
            inner = cell[ty:max(ty + 1, ys1 - ys0 - ty), tx:max(tx + 1, xs1 - xs0 - tx)]
            ia = inner[..., 3] > 127
            c = inner[..., :3][ia] if ia.any() else cell[..., :3][a]
            d = ((oklab(c)[:, None] - plab[None]) ** 2).sum(-1).argmin(1)
            k = np.bincount(d, minlength=len(pal)).argmax()
            out[j, i, :3] = pal[k]
            out[j, i, 3] = 255
    return out


def reduce_palette(img, n=15, boost_mask=None, boost=40.0):
    """Höchstens n Farben (ohne Transparenz) auf dem 15-Bit-Raster. Pixel unter boost_mask zählen boost-fach
    (kleine, wichtige Teile wie Leuchtfeuer oder Fensterglas behalten ihre Farbe)."""
    a = img[..., 3] > 0
    cols = img[..., :3][a]
    uniq, inv, cnt = np.unique(cols, axis=0, return_inverse=True, return_counts=True)
    if boost_mask is not None:
        wpx = np.where(boost_mask[a], boost, 1.0)
        cnt = np.bincount(inv.ravel(), weights=wpx, minlength=len(uniq))
    if len(uniq) > n:
        w = cnt.astype(np.float64) ** 0.6
        pal = kmeans_lab(uniq.astype(np.float64), w, n)
    else:
        pal = uniq
    pal = np.unique(snap5(pal), axis=0)
    d = ((oklab(uniq)[:, None] - oklab(pal)[None]) ** 2).sum(-1).argmin(1)
    out = img.copy()
    out[..., :3][a] = pal[d][inv.ravel()]
    out[..., 3] = np.where(a, 255, 0)
    return out, pal


def save(img, path):
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGBA").save(path)
