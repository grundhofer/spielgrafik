"""Kleine Bildoperationen mit NumPy (kein SciPy im Projekt-venv)."""
import numpy as np
from PIL import Image


def load(path, mode="RGB"):
    return np.asarray(Image.open(path).convert(mode), dtype=np.float32) / 255.0


def save(path, a):
    a = np.clip(a, 0, 1)
    Image.fromarray((a * 255 + 0.5).astype(np.uint8)).save(path)


def lum(c):
    return c[..., 0] * 0.2126 + c[..., 1] * 0.7152 + c[..., 2] * 0.0722


def box(a, r):
    """Kastenfilter mit Radius r (Fenster 2r+1), am Rand normiert."""
    if r <= 0:
        return a.copy()
    a = a.astype(np.float32)
    def along(x, axis):
        n = x.shape[axis]
        c = np.cumsum(x, axis=axis, dtype=np.float64)
        pad = [(0, 0)] * x.ndim
        pad[axis] = (1, 0)
        c = np.pad(c, pad)
        idx = np.arange(n)
        hi = np.minimum(idx + r + 1, n)
        lo = np.maximum(idx - r, 0)
        s = np.take(c, hi, axis=axis) - np.take(c, lo, axis=axis)
        shape = [1] * x.ndim
        shape[axis] = n
        return (s / (hi - lo).reshape(shape)).astype(np.float32)
    return along(along(a, 0), 1)


def blur(a, sigma):
    """Annähernd gaußsch: drei Kastenfilter."""
    r = max(1, int(round(sigma * 0.85)))
    for _ in range(3):
        a = box(a, r)
    return a


def guided(I, p, r, eps):
    """Guided Filter (He et al.) mit Farbführung I (H,W,3) für eine Maske p (H,W)."""
    mI = box(I, r)
    mp = box(p, r)
    mIp = box(I * p[..., None], r)
    cov_Ip = mIp - mI * mp[..., None]
    var = np.empty(I.shape[:2] + (3, 3), np.float32)
    for i in range(3):
        for j in range(i, 3):
            v = box(I[..., i] * I[..., j], r) - mI[..., i] * mI[..., j]
            var[..., i, j] = v
            var[..., j, i] = v
    var += eps * np.eye(3, dtype=np.float32)
    a = np.linalg.solve(var, cov_Ip[..., None])[..., 0]
    b = mp - (a * mI).sum(-1)
    return (box(a, r) * I).sum(-1) + box(b, r)


def pull_push(img, w, levels=10):
    """Füllt Pixel mit Gewicht w≈0 aus der Umgebung (Pyramide herunter, gewichtet hinauf)."""
    pyr = []
    c, ww = img * w[..., None], w.copy()
    for _ in range(levels):
        pyr.append((c, ww))
        h, wd = ww.shape
        if h < 4 or wd < 4:
            break
        h2, w2 = h // 2, wd // 2
        c = c[:h2 * 2, :w2 * 2].reshape(h2, 2, w2, 2, -1).sum((1, 3))
        ww = ww[:h2 * 2, :w2 * 2].reshape(h2, 2, w2, 2).sum((1, 3))
    col = c / np.maximum(ww, 1e-6)[..., None]
    for c, ww in reversed(pyr[:-1]):
        h, wd = ww.shape
        up = np.stack([np.asarray(Image.fromarray(col[..., k]).resize((wd, h), Image.BILINEAR))
                       for k in range(col.shape[-1])], -1)
        known = c / np.maximum(ww, 1e-6)[..., None]
        a = np.clip(ww, 0, 1)[..., None]
        col = known * a + up * (1 - a)
    return col


def resize(a, size, resample=Image.LANCZOS):
    """Größe ändern für float-Arrays (H,W) oder (H,W,C)."""
    if a.ndim == 2:
        return np.asarray(Image.fromarray(a.astype(np.float32), "F").resize(size, resample))
    return np.stack([resize(a[..., k], size, resample) for k in range(a.shape[-1])], -1)
