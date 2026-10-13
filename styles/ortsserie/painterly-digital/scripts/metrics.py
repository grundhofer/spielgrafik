"""Bildmaße für die Ortsserie (nur NumPy und Pillow, deterministisch).

Layout-Kopie   gray_corr: Pearson-Korrelation der Helligkeit, auf 48x32 verkleinert (grobe Tonwertverteilung;
                          hoch schon, wenn beide Bilder oben hell und unten dunkel sind)
               edge_corr: Pearson-Korrelation der Kantenstärke (Sobel auf 640 px Breite, weich, auf 64x43 gemittelt)
               struct_corr: Pearson-Korrelation des Bandpasses der Helligkeit (Gauß 2 px minus Gauß 8 px auf
                          640 px Breite, auf 160x107 gemittelt): gleiche Formen an gleicher Stelle (Wolken, Kanten
                          von Objekten). Unabhängige Bilder liegen bei |r| <= 0,03; struct_top dasselbe nur für die
                          oberen 45 % (Himmel)
Palette        Oklab, k-means mit festem Startwert auf 24 000 Stichproben je Bild
               palette_matched: 8 Farben je Bild, beste 1:1-Zuordnung (alle 8! Permutationen), mittlerer
                                Abstand der Paare (gewichtet mit dem mittleren Anteil), in Oklab x 100
               palette_chamfer: 12 Farben, je Farbe Abstand zur nächsten Farbe des anderen Bilds, mit Anteil
                                gewichtet, beide Richtungen gemittelt (Oklab x 100)
               mean_dE:         Abstand der Oklab-Mittelwerte (x 100)
Detail         grad_energy:     mittlerer Helligkeitsgradient (Oklab L x 100 je Pixel) bei 1264 px Breite
               edge_density:    Anteil der Pixel mit Gradient > 2,5 (L x 100 je Pixel) bei 1264 px Breite
               texture_energy:  mittlere Abweichung vom 3-px-Gauß (8-bit-Helligkeit) bei 1264 px Breite, wie
                                hintergrund-serie/tools/prep.py texture_energy
Ruhe           calm(): Streuung und Gradient der Helligkeit in einem Rechteck (Textleiste)
Alle Bilder werden vorher auf dieselbe Breite gebracht (3:2-Rohbilder von agy 1264x848, Codex 1536x1024).
"""
import itertools

import numpy as np
from PIL import Image, ImageFilter

DETAIL_W = 1264


def load(path, width=None):
    im = Image.open(path).convert("RGB")
    if width and im.width != width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    return im


def to_float(im):
    return np.asarray(im, np.float32) / 255.0


def srgb_to_oklab(rgb):
    c = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                   [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]])
    M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                   [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]])
    lms = np.cbrt(c @ M1.T)
    return lms @ M2.T


def _pearson(a, b):
    a = a.ravel() - a.mean()
    b = b.ravel() - b.mean()
    return float((a * b).sum() / (np.sqrt((a * a).sum() * (b * b).sum()) + 1e-12))


def _blockmean(a, w, h):
    return np.asarray(Image.fromarray(a.astype(np.float32), "F").resize((w, h), Image.BOX), np.float64)


def _sobel(L):
    p = np.pad(L, 1, mode="edge")
    gx = (p[1:-1, 2:] - p[1:-1, :-2]) * 2 + (p[:-2, 2:] - p[:-2, :-2]) + (p[2:, 2:] - p[2:, :-2])
    gy = (p[2:, 1:-1] - p[:-2, 1:-1]) * 2 + (p[2:, :-2] - p[:-2, :-2]) + (p[2:, 2:] - p[:-2, 2:])
    return np.hypot(gx, gy) / 8.0


def _gauss(a, sigma):
    r = int(3 * sigma + 0.5)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    p = np.pad(a, r, mode="edge")
    p = np.apply_along_axis(lambda v: np.convolve(v, k, "valid"), 1, p)
    return np.apply_along_axis(lambda v: np.convolve(v, k, "valid"), 0, p)


def layout_features(path):
    im = load(path, 640)
    L = srgb_to_oklab(to_float(im))[..., 0]
    g = _gauss(_sobel(L), 2.0)
    band = _gauss(L, 2.0) - _gauss(L, 8.0)
    return {"gray": _blockmean(L, 48, 32), "edge": _blockmean(g, 64, 43), "band": _blockmean(band, 160, 107)}


def layout_similarity(fa, fb):
    return {"gray_corr": round(_pearson(fa["gray"], fb["gray"]), 3),
            "edge_corr": round(_pearson(fa["edge"], fb["edge"]), 3),
            "struct_corr": round(_pearson(fa["band"], fb["band"]), 3),
            "struct_top": round(_pearson(fa["band"][:48], fb["band"][:48]), 3)}


def _kmeans(X, k, seed=7, iters=30):
    rng = np.random.default_rng(seed)
    # k-means++ Start
    c = [X[rng.integers(len(X))]]
    for _ in range(1, k):
        d = np.min(((X[:, None, :] - np.array(c)[None]) ** 2).sum(-1), 1)
        c.append(X[rng.choice(len(X), p=d / d.sum())])
    c = np.array(c)
    for _ in range(iters):
        lab = ((X[:, None, :] - c[None]) ** 2).sum(-1).argmin(1)
        new = np.array([X[lab == i].mean(0) if (lab == i).any() else c[i] for i in range(k)])
        if np.allclose(new, c, atol=1e-6):
            break
        c = new
    lab = ((X[:, None, :] - c[None]) ** 2).sum(-1).argmin(1)
    w = np.bincount(lab, minlength=k) / len(lab)
    order = np.argsort(-w)
    return c[order], w[order]


def palette_features(path, n=24000, seed=11):
    lab = srgb_to_oklab(to_float(load(path, 640))).reshape(-1, 3)
    rng = np.random.default_rng(seed)
    X = lab[rng.choice(len(lab), min(n, len(lab)), replace=False)]
    c8, w8 = _kmeans(X, 8)
    c12, w12 = _kmeans(X, 12)
    return {"mean": lab.mean(0), "c8": c8, "w8": w8, "c12": c12, "w12": w12}


PERM8 = np.array(list(itertools.permutations(range(8))))


def palette_distance(pa, pb):
    D8 = np.linalg.norm(pa["c8"][:, None] - pb["c8"][None], axis=-1)
    W8 = (pa["w8"][:, None] + pb["w8"][None]) / 2
    costs = D8[np.arange(8), PERM8].sum(1)
    best = PERM8[costs.argmin()]
    wpair = W8[np.arange(8), best]
    matched = float((D8[np.arange(8), best] * wpair).sum() / wpair.sum())
    D12 = np.linalg.norm(pa["c12"][:, None] - pb["c12"][None], axis=-1)
    ch = 0.5 * float((D12.min(1) * pa["w12"]).sum() + (D12.min(0) * pb["w12"]).sum())
    return {"palette_matched": round(matched * 100, 2), "palette_chamfer": round(ch * 100, 2),
            "mean_dE": round(float(np.linalg.norm(pa["mean"] - pb["mean"])) * 100, 2)}


def detail_features(path):
    im = load(path, DETAIL_W)
    L = srgb_to_oklab(to_float(im))[..., 0] * 100
    g = _sobel(L)
    lum = im.convert("L")
    a = np.asarray(lum, np.float64)
    b = np.asarray(lum.filter(ImageFilter.GaussianBlur(3)), np.float64)
    return {"grad_energy": round(float(g.mean()), 3), "edge_density": round(float((g > 2.5).mean()), 4),
            "texture_energy": round(float(np.abs(a - b).mean()), 3)}


def detail_ratio(da, db):
    return {k + "_ratio": round(da[k] / db[k], 3) for k in ("grad_energy", "edge_density", "texture_energy")}


def calm(img_path_or_im, rect):
    """Ruhe in rect = (x, y, w, h): Streuung der Helligkeit (Oklab L x 100) und mittlerer Gradient."""
    im = img_path_or_im if isinstance(img_path_or_im, Image.Image) else load(img_path_or_im)
    x, y, w, h = rect
    L = srgb_to_oklab(to_float(im.crop((x, y, x + w, y + h))))[..., 0] * 100
    g = _sobel(L)
    return {"L_std": round(float(L.std()), 2), "L_mean": round(float(L.mean()), 2),
            "grad_mean": round(float(g.mean()), 3)}
