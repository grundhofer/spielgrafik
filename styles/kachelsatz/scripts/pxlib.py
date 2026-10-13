"""Hilfsfunktionen für den Eintrag kachelsatz: Farben quantisieren, KI-Pixelbilder auf ein echtes Raster bringen."""
import numpy as np
from PIL import Image


def srgb_to_oklab(rgb):
    c = rgb.astype(np.float64) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    l = 0.4122214708 * c[..., 0] + 0.5363325363 * c[..., 1] + 0.0514459929 * c[..., 2]
    m = 0.2119034982 * c[..., 0] + 0.6806995451 * c[..., 1] + 0.1073969566 * c[..., 2]
    s = 0.0883024619 * c[..., 0] + 0.2817188376 * c[..., 1] + 0.6299787005 * c[..., 2]
    l, m, s = np.cbrt(l), np.cbrt(m), np.cbrt(s)
    return np.stack([0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
                     1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
                     0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s], -1)


def kmeans(points, k, iters=30, seed=1):
    """k-means in Oklab; gibt (Zentren in Oklab, Zuordnung) zurück. Deterministisch."""
    rng = np.random.default_rng(seed)
    pts = points.reshape(-1, 3)
    # k-means++ Start
    cent = [pts[rng.integers(len(pts))]]
    for _ in range(1, k):
        d = np.min(((pts[:, None, :] - np.array(cent)[None]) ** 2).sum(-1), 1)
        cent.append(pts[rng.choice(len(pts), p=d / d.sum())])
    cent = np.array(cent)
    for _ in range(iters):
        lab = np.argmin(((pts[:, None, :] - cent[None]) ** 2).sum(-1), 1)
        new = np.array([pts[lab == i].mean(0) if (lab == i).any() else cent[i] for i in range(k)])
        if np.allclose(new, cent):
            break
        cent = new
    return cent, lab


def palette_from(rgb_pixels, k, seed=1, sample=60000):
    """k repräsentative Farben (echte Bildfarben, Medoid je Cluster) aus RGB-Pixeln."""
    px = rgb_pixels.reshape(-1, 3)
    rng = np.random.default_rng(seed)
    if len(px) > sample:
        px = px[rng.choice(len(px), sample, replace=False)]
    lab = srgb_to_oklab(px)
    cent, asg = kmeans(lab, k, seed=seed)
    pal = []
    for i in range(k):
        m = asg == i
        if not m.any():
            continue
        j = np.argmin(((lab[m] - cent[i]) ** 2).sum(-1))
        pal.append(px[m][j])
    pal = np.array(pal, dtype=np.uint8)
    # nach Helligkeit sortieren (dunkel -> hell)
    order = np.argsort(srgb_to_oklab(pal)[:, 0])
    return pal[order]


def nearest_index(rgb, pal):
    lab = srgb_to_oklab(rgb.reshape(-1, 3))
    pl = srgb_to_oklab(pal)
    idx = np.argmin(((lab[:, None, :] - pl[None]) ** 2).sum(-1), 1)
    return idx.reshape(rgb.shape[:-1])


def snap_grid(rgb, pal, cells_x, cells_y, x0=0.0, y0=0.0, cw=None, ch=None, inner=0.6):
    """Je Zielzelle die häufigste Palettenfarbe im inneren Teil der Zelle (harte Pixel, keine Mischfarben)."""
    h, w = rgb.shape[:2]
    cw = cw or (w - x0) / cells_x
    ch = ch or (h - y0) / cells_y
    idx = nearest_index(rgb, pal)
    out = np.zeros((cells_y, cells_x), dtype=np.int32)
    m = (1 - inner) / 2
    for j in range(cells_y):
        ya, yb = int(round(y0 + (j + m) * ch)), int(round(y0 + (j + 1 - m) * ch))
        for i in range(cells_x):
            xa, xb = int(round(x0 + (i + m) * cw)), int(round(x0 + (i + 1 - m) * cw))
            cell = idx[ya:max(yb, ya + 1), xa:max(xb, xa + 1)].ravel()
            out[j, i] = np.bincount(cell, minlength=len(pal)).argmax()
    return out


def snap_sprite(rgba, pal, out_w, out_h, alpha_cut=200, inner=0.7, alpha_share=0.5):
    """Sprite (RGBA, freigestellt, eng beschnitten) auf out_w x out_h Pixel: Mehrheitsfarbe je Zelle, 1-Bit-Alpha."""
    h, w = rgba.shape[:2]
    a = rgba[..., 3] >= alpha_cut
    idx = nearest_index(rgba[..., :3], pal)
    res = np.zeros((out_h, out_w, 4), dtype=np.uint8)
    cw, ch = w / out_w, h / out_h
    m = (1 - inner) / 2
    for j in range(out_h):
        ya, yb = int(j * ch), max(int((j + 1) * ch), int(j * ch) + 1)
        yi0, yi1 = int(round((j + m) * ch)), int(round((j + 1 - m) * ch))
        for i in range(out_w):
            xa, xb = int(i * cw), max(int((i + 1) * cw), int(i * cw) + 1)
            if a[ya:yb, xa:xb].mean() < alpha_share:
                continue
            xi0, xi1 = int(round((i + m) * cw)), int(round((i + 1 - m) * cw))
            sel = a[yi0:max(yi1, yi0 + 1), xi0:max(xi1, xi0 + 1)]
            cell = idx[yi0:max(yi1, yi0 + 1), xi0:max(xi1, xi0 + 1)][sel]
            if cell.size == 0:
                cell = idx[ya:yb, xa:xb][a[ya:yb, xa:xb]]
            k = np.bincount(cell, minlength=len(pal)).argmax()
            res[j, i, :3] = pal[k]
            res[j, i, 3] = 255
    return res


def save_zoom(arr, path, z=8):
    im = Image.fromarray(arr)
    im.resize((im.width * z, im.height * z), Image.NEAREST).save(path)
