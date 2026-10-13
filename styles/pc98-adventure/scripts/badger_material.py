"""Materialtreue Verkleinerung des Dachs-Brustbilds auf das 16-Farben-Raster.

1. Jedes Pixel der Vorlage (Ausschnitt aus der KI-Vorderansicht) wird einem Material zugeordnet (nächste
   Referenzfarbe in Oklab), danach glättet ein 5x5-Mehrheitsfilter die feine Fellzeichnung.
2. Je Zielpixel entscheidet die Mehrheit der Materialien in seiner Zelle; Konturpixel gewinnen schon ab
   einem Drittel, damit die Anime-Kontur geschlossen bleibt.
3. Die Farbe des Zielpixels ist der Mittelwert nur der Vorlagepixel dieses Materials (keine Mischfarben an
   Kanten), gerastert nur mit den Paletteneinträgen, die zum Material gehören. So entsteht kein grünes oder
   blaues Einzelpixel im Gesicht, Schatten werden zu Schachbrett- und Punktrastern innerhalb eines Materials.
"""
import numpy as np
from PIL import Image

from pc98lib import hexc, oklab, pattern_dither, to_linear

# Referenzfarben je Material (aus einem k-means über die KI-Vorlage abgelesen, auf 12 Bit gerundet)
MATERIALS = {
    "outline": ["110000", "221100"],
    "fur": ["332222", "443322", "554444"],
    "fur_light": ["886655"],
    "red": ["771111", "992222"],
    "green": ["444422", "555533", "665533"],
    "leather": ["774433"],
    "tan": ["aa8855"],
    "cream": ["bb9988", "ddbbaa", "eeddbb"],
}
# erlaubte Paletteneinträge je Material (als Farbwerte; je Wert gilt der nächste Eintrag der Palette)
ALLOWED = {
    "outline": ["000000"],
    "fur": ["000000", "221122", "553333", "776666"],
    "fur_light": ["553333", "776666", "aa8866"],
    "red": ["993322", "553333", "000000"],
    "green": ["556633", "553333", "000000"],
    "leather": ["553333", "993322", "aa8866", "000000"],
    "tan": ["aa8866", "ee9977", "eeddbb", "776666"],
    "cream": ["eeddbb", "aa8866", "776666", "ee9977"],
}


def mode_filter(lbl, valid, n, r=2):
    """Mehrheitsfilter (2r+1)^2 über Materialnummern; transparente Pixel zählen nicht."""
    h, w = lbl.shape
    counts = np.zeros((n, h, w), np.int32)
    pad = np.pad(np.where(valid, lbl, -1), r, constant_values=-1)
    for dy in range(2 * r + 1):
        for dx in range(2 * r + 1):
            win = pad[dy:dy + h, dx:dx + w]
            for k in range(n):
                counts[k] += win == k
    out = counts.argmax(0)
    return np.where(valid, out, -1)


def build(raw_path, crop, size, pal, origin, levels=4):
    im = Image.open(raw_path).convert("RGBA").crop(crop)
    a = np.asarray(im).astype(np.float32)
    rgb, alpha = a[..., :3], a[..., 3]
    mag = (rgb[..., 0] > rgb[..., 1] + 60) & (rgb[..., 2] > rgb[..., 1] + 60)   # Magenta-Reste
    valid = (alpha >= 128) & ~mag
    names = list(MATERIALS)
    refs, ref_mat = [], []
    for k, n in enumerate(names):
        for hx in MATERIALS[n]:
            refs.append(hexc(hx))
            ref_mat.append(k)
    refs_lab = oklab(np.array(refs))
    lab = oklab(rgb.reshape(-1, 3).clip(0, 255))
    d = ((lab[:, None, :] - refs_lab[None]) ** 2).sum(-1)
    lbl = np.array(ref_mat)[d.argmin(1)].reshape(alpha.shape)
    outline_raw = (lbl == names.index("outline")) & valid
    lbl = mode_filter(lbl, valid, len(names))
    # Konturen nicht wegfiltern: dünne Linien der Vorlage bleiben Kontur
    lbl = np.where(outline_raw, names.index("outline"), lbl)

    H0, W0 = alpha.shape
    W, H = size
    sx, sy = W0 / W, H0 / H
    cy = np.minimum((np.arange(H0) / sy).astype(int), H - 1)
    cx = np.minimum((np.arange(W0) / sx).astype(int), W - 1)
    cell = (cy[:, None] * W + cx[None, :]).ravel()
    n = len(names)
    lin = to_linear(rgb.reshape(-1, 3).clip(0, 255))
    v = valid.ravel()
    l = lbl.ravel()
    cnt = np.zeros((W * H, n), np.float32)
    np.add.at(cnt, (cell[v], l[v]), 1)
    tot = np.bincount(cell, minlength=W * H).astype(np.float32)
    cov = cnt.sum(1) / np.maximum(tot, 1)
    mask = (cov >= 0.5).reshape(H, W)
    share = cnt / np.maximum(cnt.sum(1, keepdims=True), 1)
    win = share.argmax(1)
    oi = names.index("outline")
    win = np.where(share[:, oi] >= 0.34, oi, win)
    # Mittelwert nur der Pixel des Gewinner-Materials
    sums = np.zeros((W * H, n, 3), np.float32)
    np.add.at(sums, (cell[v], l[v]), lin[v])
    col_lin = sums[np.arange(W * H), win] / np.maximum(cnt[np.arange(W * H), win], 1)[:, None]
    col = np.where(col_lin <= 0.0031308, col_lin * 12.92, 1.055 * np.maximum(col_lin, 0) ** (1 / 2.4) - 0.055)
    col = (col * 255).clip(0, 255).astype(np.uint8).reshape(H, W, 3)
    win = win.reshape(H, W)

    pal_lab = oklab(np.asarray(pal))

    def nearest(hx):
        return int((((pal_lab - oklab(hexc(hx)[None])) ** 2).sum(-1)).argmin())

    idx = np.zeros((H, W), np.int32)
    for k, name in enumerate(names):
        sel = (win == k) & mask
        if not sel.any():
            continue
        allowed = sorted({nearest(h) for h in ALLOWED[name]})
        q = pattern_dither(col, pal, allowed=allowed, levels=levels, ox=origin[0], oy=origin[1])
        idx[sel] = q[sel]
    return idx, mask, win, names
