"""Bildoperationen für das lebende Standbild (nur NumPy und Pillow).

guided()   Kantentreuer Filter (He et al. 2010, Farbführung): grobe Maske -> Maske, die an den Kanten des Bildes sitzt.
pushpull() Füllt unbekannte Pixel aus der Umgebung (Pull-Push-Pyramide). Für "saubere Platten" hinter Objekten.
tile_noise() Kachelbares Rauschen über das Frequenzspektrum (periodisch per Konstruktion, fester Seed).
"""
import numpy as np
from PIL import Image, ImageDraw


def load_rgb(path):
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0


def save_rgb(arr, path):
    Image.fromarray(np.clip(arr * 255.0 + 0.5, 0, 255).astype(np.uint8)).save(path)


def save_gray(arr, path):
    Image.fromarray(np.clip(arr * 255.0 + 0.5, 0, 255).astype(np.uint8), "L").save(path)


def luma(img):
    return img[..., 0] * 0.299 + img[..., 1] * 0.587 + img[..., 2] * 0.114


def box(a, r):
    """Mittelwert über ein (2r+1)^2-Fenster, Ränder mit tatsächlicher Anzahl normiert."""
    a = a.astype(np.float64)
    h, w = a.shape[:2]

    def csum(x, axis):
        c = np.cumsum(x, axis=axis)
        pad = [(0, 0)] * x.ndim
        pad[axis] = (1, 0)
        c = np.pad(c, pad)
        n = x.shape[axis]
        hi = np.minimum(np.arange(n) + r + 1, n)
        lo = np.maximum(np.arange(n) - r, 0)
        return np.take(c, hi, axis=axis) - np.take(c, lo, axis=axis)

    s = csum(csum(a, 0), 1)
    ones = np.ones((h, w))
    cnt = csum(csum(ones, 0), 1)
    if a.ndim == 3:
        cnt = cnt[..., None]
    return (s / cnt).astype(np.float32)


def guided(I, p, r=8, eps=1e-3):
    """Guided Filter mit Farbbild I (H,W,3) und Eingangsmaske p (H,W)."""
    I = I.astype(np.float64)
    p = p.astype(np.float64)
    mI = box(I, r).astype(np.float64)
    mp = box(p, r).astype(np.float64)
    mIp = box(I * p[..., None], r).astype(np.float64)
    cov_Ip = mIp - mI * mp[..., None]
    var = np.empty(I.shape[:2] + (3, 3))
    for i in range(3):
        for j in range(i, 3):
            v = box(I[..., i] * I[..., j], r) - mI[..., i] * mI[..., j]
            var[..., i, j] = v
            var[..., j, i] = v
    var += eps * np.eye(3)
    a = np.linalg.solve(var, cov_Ip[..., None])[..., 0]
    b = mp - (a * mI).sum(-1)
    ma = box(a, r)
    mb = box(b, r)
    return np.clip((ma * I).sum(-1) + mb, 0, 1).astype(np.float32)


def _down(c, w):
    h, wd = w.shape
    h2, w2 = (h + 1) // 2, (wd + 1) // 2
    cp = np.zeros((h2 * 2, w2 * 2, c.shape[2]), np.float64)
    wp = np.zeros((h2 * 2, w2 * 2), np.float64)
    cp[:h, :wd] = c * w[..., None]
    wp[:h, :wd] = w
    cs = cp.reshape(h2, 2, w2, 2, -1).sum((1, 3))
    ws = wp.reshape(h2, 2, w2, 2).sum((1, 3))
    cn = np.where(ws[..., None] > 1e-9, cs / np.maximum(ws, 1e-9)[..., None], 0)
    return cn, np.minimum(ws, 1.0)


def _up(c, shape):
    h, w = shape
    im = [np.asarray(Image.fromarray(c[..., k].astype(np.float32), "F").resize((w, h), Image.BILINEAR))
          for k in range(c.shape[2])]
    return np.stack(im, -1).astype(np.float64)


def pushpull(img, known):
    """img (H,W,C) float, known (H,W) 0..1 Gewicht. Gibt gefülltes Bild zurück (bekannte Pixel bleiben)."""
    cs, ws = [img.astype(np.float64)], [np.clip(known, 0, 1).astype(np.float64)]
    while min(ws[-1].shape) > 2:
        c, w = _down(cs[-1], ws[-1])
        cs.append(c)
        ws.append(w)
    f = cs[-1]
    for lvl in range(len(cs) - 2, -1, -1):
        up = _up(f, ws[lvl].shape)
        w = ws[lvl][..., None]
        f = w * cs[lvl] + (1 - w) * up
    return f.astype(np.float32)


def poly_mask(size, polys, width=0):
    """Polygone (Liste von Punktlisten) als 0/1-Maske; width>0 zeichnet Linien (z. B. Masten)."""
    im = Image.new("L", size, 0)
    d = ImageDraw.Draw(im)
    for p in polys:
        pts = [tuple(map(float, q)) for q in p]
        if width:
            d.line(pts, fill=255, width=width, joint="curve")
        else:
            d.polygon(pts, fill=255)
    return np.asarray(im, np.float32) / 255.0


def blur(a, r):
    """Weiches Verwischen über zwei Box-Durchgänge."""
    return box(box(a, r), r)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def tile_noise(n, beta, seed):
    """Kachelbares Rauschen n x n mit Spektrum 1/f^beta, auf 0..1 normiert."""
    rng = np.random.default_rng(seed)
    fx = np.fft.fftfreq(n)[None, :]
    fy = np.fft.fftfreq(n)[:, None]
    f = np.sqrt(fx * fx + fy * fy)
    f[0, 0] = 1.0
    amp = 1.0 / f ** beta
    amp[0, 0] = 0
    amp[f > 0.45] = 0  # keine Frequenzen nahe Nyquist (sonst Pixelflimmern beim Verzerren)
    ph = rng.uniform(0, 2 * np.pi, (n, n))
    z = np.real(np.fft.ifft2(amp * np.exp(1j * ph)))
    z = (z - z.mean()) / (z.std() * 4) + 0.5
    return np.clip(z, 0, 1).astype(np.float32)


def mirror_fill(img, known, fallback, reach=48):
    """Füllt unbekannte Läufe je Zeile mit dem gespiegelten Inhalt links und rechts davon (Pinselstruktur
    bleibt erhalten, anders als beim Weichzeichnen). Tiefer als `reach` px im Loch und wo keine Quelle
    bekannt ist, gilt `fallback` (z. B. Pull-Push). known: bool (H,W)."""
    h, w = known.shape
    out = fallback.copy()
    for y in range(h):
        row = known[y]
        x = 0
        while x < w:
            if row[x]:
                x += 1
                continue
            a = x
            while x < w and not row[x]:
                x += 1
            b = x  # Loch [a, b)
            n = b - a
            k = np.arange(n)
            acc = np.zeros((n, img.shape[2]), np.float64)
            wsum = np.zeros(n)
            if a > 0:
                src = a - 1 - k
                ok = (src >= 0)
                src = np.clip(src, 0, w - 1)
                ok &= known[y, src]
                wl = np.clip(1 - k / reach, 0, 1) * ok * (1 - (k + 0.5) / (n + 1) * (b < w))
                acc += img[y, src] * wl[:, None]
                wsum += wl
            if b < w:
                kk = n - 1 - k
                src = b + kk
                ok = (src < w)
                src = np.clip(src, 0, w - 1)
                ok &= known[y, src]
                wr = np.clip(1 - kk / reach, 0, 1) * ok * (1 - (kk + 0.5) / (n + 1) * (a > 0))
                acc += img[y, src] * wr[:, None]
                wsum += wr
            m = wsum > 1e-6
            t = np.clip(wsum, 0, 1)[:, None]
            seg = out[y, a:b]
            filled = np.where(m[:, None], acc / np.maximum(wsum, 1e-6)[:, None], seg)
            out[y, a:b] = filled * t + seg * (1 - t)
    return out
