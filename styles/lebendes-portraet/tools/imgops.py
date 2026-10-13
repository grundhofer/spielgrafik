"""Kleine Bildoperationen nur mit NumPy und Pillow (kein SciPy im Projekt-venv)."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def to_l(mask):
    # .copy(): Pillow 12 teilt sonst den NumPy-Speicher schreibgeschützt, floodfill bliebe wirkungslos
    return Image.fromarray((np.asarray(mask, bool) * 255).astype(np.uint8), "L").copy()


def from_l(img):
    return np.asarray(img) > 127


def dilate(mask, r):
    if r <= 0:
        return mask.copy()
    return from_l(to_l(mask).filter(ImageFilter.MaxFilter(2 * r + 1)))


def erode(mask, r):
    if r <= 0:
        return mask.copy()
    return from_l(to_l(mask).filter(ImageFilter.MinFilter(2 * r + 1)))


def close(mask, r):
    return erode(dilate(mask, r), r)


def open_(mask, r):
    return dilate(erode(mask, r), r)


def blur(arr, radius):
    """Gaußsche Unschärfe eines float-Arrays 0..1 (2D)."""
    img = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8), "L")
    return np.asarray(img.filter(ImageFilter.GaussianBlur(radius)), np.float32) / 255.0


def label(mask):
    """Zusammenhangskomponenten (8er-Nachbarschaft) durch Minimum-Ausbreitung mit Zeigersprüngen. 0 = Hintergrund."""
    m = np.asarray(mask, bool)
    h, w = m.shape
    idx = np.arange(1, h * w + 1, dtype=np.int64).reshape(h, w)
    lab = np.where(m, idx, 0)
    big = h * w + 10
    for _ in range(4000):
        L = np.where(m, lab, big)
        P = np.pad(L, 1, constant_values=big)
        nb = L.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy or dx:
                    nb = np.minimum(nb, P[1 + dy:1 + dy + h, 1 + dx:1 + dx + w])
        nb = np.where(m, nb, 0)
        # Zeigersprung: Label auf das Label des Label-Pixels setzen
        flat = nb.reshape(-1)
        nz = flat > 0
        jumped = flat.copy()
        jumped[nz] = flat[flat[nz] - 1]
        jumped = np.where(nz & (jumped > 0), np.minimum(flat, jumped), flat).reshape(h, w)
        if np.array_equal(jumped, lab):
            break
        lab = jumped
    return lab


def components(mask, min_area=1):
    """Zusammenhangskomponenten (8er-Nachbarschaft). Liefert Liste (fläche, maske), größte zuerst."""
    lab = label(mask)
    ids, counts = np.unique(lab[lab > 0], return_counts=True)
    out = [(int(c), lab == i) for i, c in zip(ids, counts) if c >= min_area]
    out.sort(key=lambda t: -t[0])
    return out


def fill_holes(mask):
    m = np.asarray(mask, bool)
    h, w = m.shape
    pad = np.zeros((h + 2, w + 2), bool)
    pad[1:-1, 1:-1] = m
    img = to_l(~pad)
    ImageDraw.floodfill(img, (0, 0), 100, thresh=0)
    outside = np.asarray(img) == 100
    return ~outside[1:-1, 1:-1]


def pull_push(rgb, known, levels=10):
    """Füllt unbekannte Pixel aus den bekannten (Pull-Push, gewichtet). rgb: HxWxC float, known: HxW bool."""
    w0 = known.astype(np.float32)
    c0 = rgb * w0[..., None]
    pyr = [(c0, w0)]
    c, w = c0, w0
    for _ in range(levels):
        h, wd = w.shape
        if h < 2 or wd < 2:
            break
        h2, w2 = h // 2 * 2, wd // 2 * 2
        c = c[:h2, :w2].reshape(h2 // 2, 2, w2 // 2, 2, -1).sum((1, 3))
        w = w[:h2, :w2].reshape(h2 // 2, 2, w2 // 2, 2).sum((1, 3))
        pyr.append((c, w))
    c, w = pyr[-1]
    est = c / np.maximum(w, 1e-6)[..., None]
    for c, w in reversed(pyr[:-1]):
        h, wd = w.shape
        up = np.repeat(np.repeat(est, 2, 0), 2, 1)
        up = np.pad(up, ((0, h - up.shape[0]), (0, wd - up.shape[1]), (0, 0)), mode="edge")
        # glätten, damit keine Blockkanten entstehen
        upi = Image.fromarray(np.clip(up * 255, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0))
        up = np.asarray(upi, np.float32) / 255.0
        a = np.clip(w, 0, 1)[..., None]
        est = (c / np.maximum(w, 1e-6)[..., None]) * a + up * (1 - a)
    return est
