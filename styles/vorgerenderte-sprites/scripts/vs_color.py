"""Farbwerkzeuge für vorgerenderte Sprites: Verkleinern, 15-Bit-Raster (BGR555), Paletten-k-means in Oklab.

Kein Standardmodulname (mehrere Agenten, eigener Ordner). Nur NumPy und Pillow.
"""
import numpy as np
from PIL import Image


def load_rgba(path):
    """RGBA als float32 0..1 (gerade, nicht vormultipliziert, wie Blender PNG schreibt)."""
    return np.asarray(Image.open(path).convert("RGBA"), dtype=np.float32) / 255.0


def downsample(img, f):
    """f×f-Mittel mit Alpha-Gewichtung: Farbe = Σ(c·a)/Σa, Alpha = Mittel(a)."""
    h, w = img.shape[0] // f, img.shape[1] // f
    a = img[: h * f, : w * f, 3:4]
    c = img[: h * f, : w * f, :3] * a
    c = c.reshape(h, f, w, f, 3).sum((1, 3))
    a = a.reshape(h, f, w, f, 1).sum((1, 3))
    rgb = np.where(a > 1e-6, c / np.maximum(a, 1e-6), 0.0)
    return np.concatenate([rgb, a / (f * f)], -1)


def decode_ids(id_img):
    """Kennungsbild (Blender, siehe vs_scene.IdSwap) → Materialnummer je Pixel, −1 = leer."""
    r = id_img[..., 0] * 255.0
    g = id_img[..., 1] * 255.0
    ok = (id_img[..., 3] > 0.5) & (g > 150)
    return np.where(ok, np.round(r / 9.0).astype(np.int32) - 1, -1)


# Kleine, wichtige Teile gewinnen schon mit weniger Unterpixeln (wie ein Pixelkünstler das Auge setzt):
# Kennungen aus vs_scene.ID_NAMES: 3 Brass, 9 Nose, 10 Eye
PRIORITY = {3: 1.5, 9: 2.0, 10: 4.0}


def downsample_majority(img, ids, f, cover=0.5):
    """f×f-Verkleinerung nach Materialmehrheit: Je Zielpixel gewinnt das häufigste Material im Block;
    die Farbe ist das Mittel nur über dessen Unterpixel. Deckend, wenn ≥ cover des Blocks belegt ist.
    Ergebnis: harte Kanten zwischen Kostümteilen, glatte Schattierung innerhalb."""
    h, w = img.shape[0] // f, img.shape[1] // f
    blk = lambda a: a[: h * f, : w * f].reshape(h, f, w, f, *a.shape[2:]).swapaxes(1, 2).reshape(h, w, f * f, *a.shape[2:])
    ib = blk(ids)
    cb = blk(img[..., :3])
    ab = blk(img[..., 3])
    best_n = np.zeros((h, w), np.float64)
    maj = np.full((h, w), -1, np.int32)
    for k in np.unique(ib):
        if k < 0:
            continue
        n = (ib == k).sum(-1) * PRIORITY.get(int(k), 1.0)
        m = n > best_n
        maj[m], best_n[m] = k, n[m]
    sel = (ib == maj[..., None]) & (ab > 0.5)
    cnt = sel.sum(-1)
    col = (cb * sel[..., None]).sum(2) / np.maximum(cnt, 1)[..., None]
    # Rückfall (Kennung und Farbe weichen an Kanten um einen Unterpixel ab): alphagewichtetes Mittel
    fb = (cb * ab[..., None]).sum(2) / np.maximum(ab.sum(-1), 1e-6)[..., None]
    col = np.where((cnt > 0)[..., None], col, fb)
    cover_n = (ib >= 0).sum(-1)
    alpha = (cover_n >= cover * f * f).astype(np.float32)
    return np.concatenate([col, alpha[..., None]], -1), maj


def srgb_to_lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def oklab(rgb01):
    c = srgb_to_lin(np.clip(rgb01, 0, 1))
    m1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]])
    m2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]])
    return np.cbrt(c @ m1.T) @ m2.T


def oklab_to_rgb(lab):
    m2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]])
    m1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]])
    lms = (lab @ np.linalg.inv(m2).T) ** 3
    lin = np.clip(lms @ np.linalg.inv(m1).T, 0, 1)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055)


GRADE_CHROMA, GRADE_CONTRAST = 1.22, 1.12


def grade(rgb01, chroma=GRADE_CHROMA, contrast=GRADE_CONTRAST):
    """Farbabstimmung vor dem Einrasten (wie die Nachbearbeitung der Renderstudios für den Fernseher):
    Buntheit ×chroma, Helligkeitskontrast um L = 0,5 ×contrast, in Oklab."""
    lab = oklab(rgb01)
    lab[..., 1:] *= chroma
    lab[..., 0] = 0.5 + (lab[..., 0] - 0.5) * contrast
    return oklab_to_rgb(lab)


def to555(rgb01):
    """Auf 5 Bit je Kanal runden; Rückgabe als 8-Bit-Werte wie die Konsole sie ausgibt (v<<3 | v>>2)."""
    v = np.clip(np.round(np.asarray(rgb01) * 31.0), 0, 31).astype(np.int32)
    return (v << 3) | (v >> 2)


def is555(rgb8):
    rgb8 = np.asarray(rgb8, dtype=np.int32)
    v = rgb8 >> 3
    return np.all(((v << 3) | (v >> 2)) == rgb8, axis=-1)


def unique_weighted(rgb01, weight_pow=1.0):
    """Farben auf das 5-Bit-Raster bringen und zählen (k-means über höchstens 32768 Punkte)."""
    q = np.clip(np.round(rgb01.reshape(-1, 3) * 31), 0, 31).astype(np.int32)
    key = (q[:, 0] << 10) | (q[:, 1] << 5) | q[:, 2]
    keys, counts = np.unique(key, return_counts=True)
    cols = np.stack([(keys >> 10) & 31, (keys >> 5) & 31, keys & 31], -1) / 31.0
    return cols, counts.astype(np.float64) ** weight_pow


def kmeans_palette(rgb01, k, weight_pow=0.7, iters=40, seed=3, fixed=None):
    """Palette mit k Farben: gewichtetes k-means in Oklab über die 15-Bit-Farben, Ergebnis auf BGR555.

    fixed: optionale feste Farben (8-Bit), die zur Palette gehören und mitzählen.
    Startwerte per k-means++ (deterministisch über seed)."""
    cols, w = unique_weighted(rgb01, weight_pow)
    lab = oklab(cols)
    rng = np.random.default_rng(seed)
    nfix = 0 if fixed is None else len(fixed)
    kk = k - nfix
    if len(cols) <= kk:
        pal01 = cols
    else:
        centers = [lab[np.argmax(w)]]
        d2 = ((lab - centers[0]) ** 2).sum(-1)
        for _ in range(1, kk):
            p = d2 * w
            idx = rng.choice(len(lab), p=p / p.sum())
            centers.append(lab[idx])
            d2 = np.minimum(d2, ((lab - lab[idx]) ** 2).sum(-1))
        C = np.array(centers)
        if fixed is not None:
            fl = oklab(np.asarray(fixed, dtype=np.float64) / 255.0)
        for _ in range(iters):
            allc = C if fixed is None else np.concatenate([C, fl])
            lab_d = ((lab[:, None, :] - allc[None]) ** 2).sum(-1)
            a = lab_d.argmin(1)
            newC = C.copy()
            for j in range(kk):
                m = a == j
                if m.any():
                    # Modus-nah: gewichteter Mittelwert, dann auf die nächstgelegene echte Farbe ziehen
                    mu = (lab[m] * w[m, None]).sum(0) / w[m].sum()
                    newC[j] = mu
            if np.allclose(newC, C, atol=1e-5):
                break
            C = newC
        # Zentren auf echte, vorkommende 15-Bit-Farben ziehen (kein trüber Mittelwert)
        a = ((lab[:, None, :] - C[None]) ** 2).sum(-1).argmin(1)
        pal01 = []
        for j in range(kk):
            m = np.where(a == j)[0]
            if len(m) == 0:
                continue
            dd = ((lab[m] - C[j]) ** 2).sum(-1)
            pal01.append(cols[m[np.argmin(dd)]])
        pal01 = np.array(pal01)
    pal = to555(pal01)
    if fixed is not None:
        pal = np.concatenate([pal, np.asarray(fixed, dtype=np.int32)])
    pal = np.unique(pal, axis=0)
    # nach Helligkeit sortieren (lesbarer Palettenstreifen)
    L = oklab(pal / 255.0)[:, 0]
    return pal[np.argsort(L)]


BAYER4 = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) + 0.5) / 16 - 0.5


def map_to_palette(rgb01, pal8, dither=0.0):
    """Jeden Pixel auf die nächste Palettenfarbe (Oklab). dither > 0: geordnetes 4×4-Bayer in Oklab-L."""
    h, w, _ = rgb01.shape
    lab = oklab(rgb01.reshape(-1, 3)).reshape(h, w, 3)
    if dither:
        t = np.tile(BAYER4, (h // 4 + 1, w // 4 + 1))[:h, :w]
        lab = lab.copy()
        lab[..., 0] += t * dither
    plab = oklab(np.asarray(pal8, dtype=np.float64) / 255.0)
    best = np.full((h, w), np.inf)
    idx = np.zeros((h, w), dtype=np.int32)
    for k in range(len(plab)):
        d = ((lab - plab[k]) ** 2).sum(-1)
        m = d < best
        idx[m] = k
        best[m] = d[m]
    return idx


def save_indexed(path, idx, pal8, alpha_mask=None):
    """Indizierte PNG: Index 0 = durchsichtig (falls alpha_mask), Palette dahinter."""
    pal8 = np.asarray(pal8, dtype=np.uint8)
    if alpha_mask is not None:
        data = np.where(alpha_mask, idx + 1, 0).astype(np.uint8)
        flat = [255, 0, 255] + pal8.flatten().tolist()
    else:
        data = idx.astype(np.uint8)
        flat = pal8.flatten().tolist()
    im = Image.fromarray(data, "P")
    im.putpalette(flat + [0] * (768 - len(flat)))
    if alpha_mask is not None:
        im.info["transparency"] = 0
        im.save(path, transparency=0)
    else:
        im.save(path)


def to_rgba8(idx, pal8, alpha_mask=None):
    rgb = np.asarray(pal8, dtype=np.uint8)[idx]
    a = np.full(idx.shape, 255, np.uint8) if alpha_mask is None else np.where(alpha_mask, 255, 0).astype(np.uint8)
    rgb = np.where(a[..., None] > 0, rgb, 0)
    return np.dstack([rgb, a])
