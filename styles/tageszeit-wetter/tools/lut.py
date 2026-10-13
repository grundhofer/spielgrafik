"""3D-Farb-LUTs (32³) für die Zustände: anpassen aus einem Bildpaar, entwerfen per Formel, anwenden.

Ablage als Streifen 1024×32 je LUT: Spalte = b_scheibe·32 + r, Zeile = g (wie im Shader lut_sample()).
"""
import numpy as np

N = 32


def grid():
    v = np.linspace(0, 1, N, dtype=np.float32)
    r, g, b = np.meshgrid(v, v, v, indexing="ij")
    return np.stack([r, g, b], -1)            # [ri, gi, bi] -> rgb


def apply(lut, img):
    """Trilineare Abtastung, img (...,3) in 0..1."""
    x = np.clip(img, 0, 1) * (N - 1)
    i0 = np.floor(x).astype(np.int32)
    i0 = np.minimum(i0, N - 2)
    f = x - i0
    out = np.zeros(img.shape, np.float32)
    for dr in (0, 1):
        wr = f[..., 0] if dr else 1 - f[..., 0]
        for dg in (0, 1):
            wg = f[..., 1] if dg else 1 - f[..., 1]
            for db in (0, 1):
                wb = f[..., 2] if db else 1 - f[..., 2]
                out += (wr * wg * wb)[..., None] * lut[i0[..., 0] + dr, i0[..., 1] + dg, i0[..., 2] + db]
    return out


def _smooth3(a):
    k = np.array([1, 4, 6, 4, 1], np.float32) / 16
    for ax in range(3):
        p = [(0, 0)] * a.ndim
        p[ax] = (2, 2)
        ap = np.pad(a, p, mode="edge")
        a = sum(k[i] * np.take(ap, np.arange(i, i + N), axis=ax) for i in range(5))
    return a


def affine_fit(src, dst):
    X = np.concatenate([src, np.ones((len(src), 1), np.float32)], 1)
    M, *_ = np.linalg.lstsq(X, dst, rcond=None)
    return M


def fit(src, dst, passes=2, k=6.0):
    """LUT aus Pixelpaaren src->dst (je (n,3)). Leere Zellen: gewichtet zur Affin-Anpassung."""
    idx = np.clip(np.round(src * (N - 1)).astype(np.int32), 0, N - 1)
    flat = (idx[:, 0] * N + idx[:, 1]) * N + idx[:, 2]
    cnt = np.bincount(flat, minlength=N ** 3).astype(np.float32).reshape(N, N, N)
    sums = np.stack([np.bincount(flat, dst[:, c], minlength=N ** 3) for c in range(3)], -1)
    sums = sums.astype(np.float32).reshape(N, N, N, 3)
    for _ in range(passes):
        cnt, sums = _smooth3(cnt), _smooth3(sums)
    mean = sums / np.maximum(cnt, 1e-6)[..., None]
    M = affine_fit(src, dst)
    g = grid().reshape(-1, 3)
    aff = (np.concatenate([g, np.ones((len(g), 1), np.float32)], 1) @ M).reshape(N, N, N, 3)
    w = (cnt / (cnt + k))[..., None]
    return np.clip(w * mean + (1 - w) * aff, 0, 1).astype(np.float32), M


def to_strip(lut):
    """[ri,gi,bi,3] -> Bild (32, 1024, 3)."""
    out = np.zeros((N, N * N, 3), np.float32)
    for bi in range(N):
        out[:, bi * N:(bi + 1) * N] = lut[:, :, bi].transpose(1, 0, 2)   # Zeile g, Spalte r
    return out


# ---- Bausteine für entworfene LUTs ----------------------------------------------------------
def luma(c):
    return c[..., 0] * 0.2126 + c[..., 1] * 0.7152 + c[..., 2] * 0.0722


def sat(c, s):
    l = luma(c)[..., None]
    return l + (c - l) * s


def contrast(c, k, pivot=0.45):
    return pivot + (c - pivot) * k


def split_tone(c, shadow, highlight, lo=0.15, hi=0.75):
    t = np.clip((luma(c) - lo) / (hi - lo), 0, 1)[..., None]
    t = t * t * (3 - 2 * t)
    return c * (np.asarray(shadow) * (1 - t) + np.asarray(highlight) * t)
