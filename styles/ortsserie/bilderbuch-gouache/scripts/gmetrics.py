"""Messwerte für die Ortsserie bilderbuch-gouache (NumPy + Pillow, ohne SciPy). Alle Maße auf 1280x720-Bildern.

Farbraum Oklab (L 0..1); ΔE hier = euklidischer Oklab-Abstand × 100 (≈ gleiche Größenordnung wie ΔE76/2..1).

  layout_sim(a, b)      Layout-Kopie: Pearson-Korrelation der Graustufen (64x36) und der weichgezeichneten
                        Kantenbilder (Sobel-Betrag auf 320x180, dann 80x45)
  palette_de(a, b)      Palettenabstand: k-means (k = 12) in Oklab je Bild, jede Farbe zur nächsten Farbe des
                        anderen Bildes, nach Flächenanteil gewichtet, symmetrisch gemittelt; Mittel und Streuung
                        über 8 Seeds
  detail(img)           Gradientenenergie (mittlerer |∇L| ×100), Kantendichte (Anteil |∇L| > 0,03), Texturmaß
                        wie hintergrund-serie (mittlere Abweichung der 8-bit-Helligkeit vom 3-px-Weichzeichner)
  calm(img, rect)       Ruhe einer Fläche: Streuung von L, Gradientenenergie, Kantendichte, mittleres L
"""
import numpy as np
from PIL import Image, ImageFilter


def oklab(rgb_u8):
    c = np.asarray(rgb_u8, np.float64) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                   [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]])
    M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                   [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]])
    lms = np.cbrt(c @ M1.T)
    return lms @ M2.T


def load(path, size=(1280, 720)):
    im = Image.open(path).convert("RGB")
    if im.size != size:
        im = im.resize(size, Image.LANCZOS)
    return np.asarray(im)


def _z(x):
    x = x.astype(np.float64).ravel()
    return (x - x.mean()) / (x.std() + 1e-9)


def _sobel(L):
    gx = np.zeros_like(L)
    gy = np.zeros_like(L)
    gx[:, 1:-1] = L[:, 2:] - L[:, :-2]
    gy[1:-1] = L[2:] - L[:-2]
    return np.hypot(gx, gy) / 2.0


def lum(img):
    return oklab(img)[..., 0]


def layout_sim(a, b):
    def gray(img, size):
        return np.asarray(Image.fromarray(img).convert("L").resize(size, Image.BOX), np.float64)

    def edges(img):
        L = lum(np.asarray(Image.fromarray(img).resize((320, 180), Image.BOX)))
        e = _sobel(L)
        return np.asarray(Image.fromarray((e * 1000).astype(np.float32), "F").resize((80, 45), Image.BOX))

    g = float(np.mean(_z(gray(a, (64, 36))) * _z(gray(b, (64, 36)))))
    e = float(np.mean(_z(edges(a)) * _z(edges(b))))
    return {"gray_r": round(g, 3), "edge_r": round(e, 3)}


def kmeans(x, k=12, iters=25, seed=7):
    rng = np.random.RandomState(seed)
    # k-means++-Start
    c = [x[rng.randint(len(x))]]
    for _ in range(k - 1):
        d = np.min(((x[:, None, :] - np.array(c)[None]) ** 2).sum(-1), 1)
        c.append(x[rng.choice(len(x), p=d / d.sum())])
    c = np.array(c)
    for _ in range(iters):
        lab = np.argmin(((x[:, None, :] - c[None]) ** 2).sum(-1), 1)
        for j in range(k):
            m = lab == j
            if m.any():
                c[j] = x[m].mean(0)
    lab = np.argmin(((x[:, None, :] - c[None]) ** 2).sum(-1), 1)
    w = np.bincount(lab, minlength=k) / len(x)
    return c, w


def palette(img, k=12, n=30000, seed=7):
    lab = oklab(img).reshape(-1, 3)
    idx = np.random.RandomState(seed).choice(len(lab), min(n, len(lab)), replace=False)
    return kmeans(lab[idx], k, seed=seed)


def palette_de(a, b, k=12, seeds=8):
    """Mittel und Streuung über 8 Läufe mit verschiedenen Seeds (Stichprobe und k-means-Start): ein einzelner Lauf
    schwankt um ±0,3–0,4; derselbe Anker gegen sich selbst ergibt so etwa 1 (Rauschboden)."""
    vals = []
    for s in range(1, seeds + 1):
        ca, wa = palette(a, k, seed=s)
        cb, wb = palette(b, k, seed=s + 100)
        d = np.sqrt(((ca[:, None, :] - cb[None]) ** 2).sum(-1)) * 100
        vals.append((float((d.min(1) * wa).sum()) + float((d.min(0) * wb).sum())) / 2)
    return round(float(np.mean(vals)), 2), round(float(np.std(vals)), 2)


def mean_lab(img):
    lab = oklab(img).reshape(-1, 3)
    m = lab.mean(0)
    return [round(float(m[0]) * 100, 1), round(float(m[1]) * 100, 2), round(float(m[2]) * 100, 2),
            round(float(np.hypot(lab[:, 1], lab[:, 2]).mean()) * 100, 2)]


def detail(img):
    L = lum(img)
    g = _sobel(L)
    l8 = Image.fromarray(img).convert("L")
    a8 = np.asarray(l8, np.float64)
    b8 = np.asarray(l8.filter(ImageFilter.GaussianBlur(3)), np.float64)
    return {"grad_energy": round(float(g.mean()) * 100, 3),
            "edge_density": round(float((g > 0.03).mean()), 4),
            "texture_energy": round(float(np.abs(a8 - b8).mean()), 2)}


def calm(img, rect):
    x0, y0, x1, y1 = rect
    sub = img[y0:y1, x0:x1]
    L = lum(sub)
    g = _sobel(L)
    return {"L_mean": round(float(L.mean()) * 100, 1), "L_std": round(float(L.std()) * 100, 2),
            "L_p05": round(float(np.percentile(L, 5)) * 100, 1), "L_p95": round(float(np.percentile(L, 95)) * 100, 1),
            "grad_energy": round(float(g.mean()) * 100, 3), "edge_density": round(float((g > 0.03).mean()), 4)}


def rel_lum(rgb_u8):
    c = np.asarray(rgb_u8, np.float64) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return c @ np.array([0.2126, 0.7152, 0.0722])


def contrast(text_rgb, img, rect):
    """WCAG-Kontrast der Schriftfarbe gegen den Hintergrund der Fläche: Median und ungünstigstes 5-%-Quantil."""
    x0, y0, x1, y1 = rect
    bg = rel_lum(img[y0:y1, x0:x1]).ravel()
    t = float(rel_lum(np.array(text_rgb, np.float64)))
    cr = (np.maximum(bg, t) + 0.05) / (np.minimum(bg, t) + 0.05)
    return {"median": round(float(np.median(cr)), 2), "p05": round(float(np.percentile(cr, 5)), 2)}
