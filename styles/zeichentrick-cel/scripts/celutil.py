"""Hilfsfunktionen für den Ink-&-Paint-Schritt (nur NumPy und Pillow)."""
import numpy as np


def srgb_to_lab(rgb):
    """rgb: float-Array (..., 3) in 0..255 -> Lab (D65)."""
    c = rgb / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], -1)


def box(img, r):
    """Kastenfilter mit Radius r über die letzten beiden Achsen (Summen, Rand mit Nullen)."""
    if r <= 0:
        return img.astype(np.float64)
    a = np.pad(img.astype(np.float64), [(0, 0)] * (img.ndim - 2) + [(r + 1, r), (r + 1, r)])
    c = a.cumsum(-1)
    a = c[..., 2 * r + 1:] - c[..., :-2 * r - 1]
    c = a.cumsum(-2)
    return c[..., 2 * r + 1:, :] - c[..., :-2 * r - 1, :]


def blur_masked(val, mask, r, passes=3):
    """Weichzeichnen nur innerhalb der Maske (normierte Faltung, dreifacher Kasten ~ Gauß)."""
    num = val * mask
    den = mask.astype(np.float64)
    for _ in range(passes):
        num = box(num, r)
        den = box(den, r)
        # Kasten-Summen wieder auf Mittelwerte bringen, damit die Zahlen klein bleiben
        n = (2 * r + 1) ** 2
        num, den = num / n, den / n
    return np.where(den > 1e-6, num / np.maximum(den, 1e-6), val)


def mode_filter(labels, k, r, keep=None, iters=1):
    """Mehrheitsfilter für Etiketten 0..k-1 im (2r+1)²-Fenster. keep: Maske, die unverändert bleibt."""
    lab = labels.copy()
    for _ in range(iters):
        votes = np.stack([box((lab == i).astype(np.float32), r) for i in range(k)])
        if keep is not None:
            votes[:, keep] = 0
        new = votes.argmax(0)
        if keep is not None:
            new = np.where(keep, lab, new)
        lab = new
    return lab


def components(mask, max_iter=4000):
    """Zusammenhangskomponenten (4er-Nachbarschaft) über Minimum-Ausbreitung. Gibt Etiketten (0 = Hintergrund)."""
    h, w = mask.shape
    big = h * w + 1
    lab = np.where(mask, np.arange(1, h * w + 1).reshape(h, w), big)
    for _ in range(max_iter):
        p = np.pad(lab, 1, constant_values=big)
        n = np.minimum.reduce([p[1:-1, 1:-1], p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]])
        n = np.where(mask, n, big)
        if np.array_equal(n, lab):
            break
        lab = n
    lab = np.where(mask, lab, 0)
    u, inv = np.unique(lab, return_inverse=True)
    return inv.reshape(h, w)


def downscale_premul(rgba, size):
    """Vormultipliziert verkleinern (Lanczos), damit keine dunklen oder hellen Säume entstehen."""
    from PIL import Image
    a = rgba.astype(np.float32) / 255.0
    pm = np.concatenate([a[..., :3] * a[..., 3:], a[..., 3:]], -1)
    chans = [np.array(Image.fromarray(pm[..., i]).resize(size, Image.LANCZOS)) for i in range(4)]
    out = np.stack(chans, -1)
    al = np.clip(out[..., 3], 0, 1)
    rgb = np.where(al[..., None] > 1e-4, out[..., :3] / np.maximum(al[..., None], 1e-4), 0)
    res = np.concatenate([np.clip(rgb, 0, 1), al[..., None]], -1)
    return (res * 255 + 0.5).astype(np.uint8)


def _filt(img, r, fn):
    from numpy.lib.stride_tricks import sliding_window_view as swv
    p = np.pad(img, ((0, 0), (r, r)), mode="edge")
    a = fn(swv(p, 2 * r + 1, axis=1), axis=-1)
    p = np.pad(a, ((r, r), (0, 0)), mode="edge")
    return fn(swv(p, 2 * r + 1, axis=0), axis=-1)


def max_filter(img, r):
    return _filt(img, r, np.max)


def min_filter(img, r):
    return _filt(img, r, np.min)


def black_tophat(img, r):
    """Schließen (Max, dann Min) minus Bild: hebt dunkle Strukturen hervor, die schmaler als 2r+1 sind."""
    return min_filter(max_filter(img, r), r) - img
