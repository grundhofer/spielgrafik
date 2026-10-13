"""Blender-Pässe (Material-ID + Normale, k-fach überabgetastet) -> Pixel-Sprite auf der iso-pixel-Palette.

Je Zielpixel (k×k Abtastungen):
  Deckung   Anteil deckender Abtastungen >= 0,45 (dünne Teile mit hoher Priorität schon ab 0,25)
  Material  Mehrheit, gewichtet mit Priorität (Auge, Nase, Messing, Glas zählen mehr, sonst verschwinden sie)
  Licht     mittlere Normale der Abtastungen dieses Materials -> Stufe 0..3 (isopal.tone)
Danach: einzelne Ausreißerpixel eines Materials (alle 4 Nachbarn anders und gleich) übernehmen die Umgebung,
und eine 1-px-Außenkontur (isopal.OUTLINE) schließt den Umriss.

Als Modul: pixelize(id_path, nrm_path, k, ids) -> (rgba uint8, mat-index int16, tone int8, names)
"""
import numpy as np
from PIL import Image

import isopal

PRIORITY = {"Eye": 4.0, "Nose": 2.5, "Brass": 2.5, "Glass": 2.0, "Scarf": 1.3, "Metal": 1.3, "RedPaint": 1.2}


def load(path):
    return np.asarray(Image.open(path).convert("RGBA"))


def pixelize(id_path, nrm_path, k, ids, cover=0.45, cover_thin=0.25, outline=True, despeckle=True):
    idi = load(id_path)
    nr = load(nrm_path).astype(np.float32)
    H, W = idi.shape[0] // k, idi.shape[1] // k
    names = list(ids.keys())
    cols = np.array([ids[n] for n in names], np.int16)
    # Material je Abtastung
    a = idi[..., 3] > 127
    rgb = idi[..., :3].astype(np.int16)
    d = np.abs(rgb[..., None, :] - cols[None, None, :, :]).sum(-1)
    mi = d.argmin(-1).astype(np.int16)
    mi[~a] = -1
    nv = nr[..., :3] / 255.0 * 2.0 - 1.0
    # Blöcke
    mi_b = mi.reshape(H, k, W, k).transpose(0, 2, 1, 3).reshape(H, W, k * k)
    nv_b = nv.reshape(H, k, W, k, 3).transpose(0, 2, 1, 3, 4).reshape(H, W, k * k, 3)
    nm = len(names)
    counts = np.stack([(mi_b == j).sum(-1) for j in range(nm)], -1).astype(np.float32)
    covf = counts.sum(-1) / (k * k)
    w = np.array([PRIORITY.get(n, 1.0) for n in names], np.float32)
    score = counts * w
    best = score.argmax(-1)
    thin = np.array([PRIORITY.get(n, 1.0) >= 2.0 for n in names])
    best_cov = np.take_along_axis(counts, best[..., None], -1)[..., 0] / (k * k)
    opaque = (covf >= cover) | (thin[best] & (best_cov >= cover_thin))
    mat = np.where(opaque, best, -1).astype(np.int16)
    # mittlere Normale des gewählten Materials
    sel = (mi_b == best[..., None])
    nsum = (nv_b * sel[..., None]).sum(2)
    nlen = np.linalg.norm(nsum, axis=-1, keepdims=True) + 1e-6
    nmean = nsum / nlen
    tn = isopal.tone(nmean)
    if despeckle:
        mat, tn = _despeckle(mat, tn)
    rgba = np.zeros((H, W, 4), np.uint8)
    ramps = [isopal.RAMPS[n] for n in names]
    for j, n in enumerate(names):
        m = mat == j
        if not m.any():
            continue
        r = np.array(ramps[j], np.uint8)
        t = np.full(tn.shape, 2, np.int8) if n in isopal.EMISSIVE else tn
        rgba[m, :3] = r[t[m]]
        rgba[m, 3] = 255
    if outline:
        rgba = add_outline(rgba)
    return rgba, mat, tn, names


def _despeckle(mat, tn):
    """Einzelpixel eines Materials, deren 4 Nachbarn alle dasselbe andere Material haben, angleichen."""
    m = mat.copy()
    t = tn.copy()
    H, W = m.shape
    for y in range(1, H - 1):
        for x in range(1, W - 1):
            c = mat[y, x]
            if c < 0:
                continue
            nb = [mat[y - 1, x], mat[y + 1, x], mat[y, x - 1], mat[y, x + 1]]
            if nb[0] == nb[1] == nb[2] == nb[3] and nb[0] != c and nb[0] >= 0:
                m[y, x] = nb[0]
    return m, t


def add_outline(rgba, color=None):
    color = color or isopal.OUTLINE
    a = rgba[..., 3] > 0
    p = np.pad(a, 1)
    nb = p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
    ring = nb & ~a
    out = rgba.copy()
    out[ring, :3] = color
    out[ring, 3] = 255
    return out


def upscale(img, f):
    return Image.fromarray(img).resize((img.shape[1] * f, img.shape[0] * f), Image.NEAREST)
