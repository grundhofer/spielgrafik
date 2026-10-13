"""Gemeinsame Helfer für die Rotoskopie-Skripte (NumPy + Pillow, ohne SciPy)."""
import json, pathlib
from collections import deque

import numpy as np
from PIL import Image

ENTRY = pathlib.Path(__file__).resolve().parent.parent
MATS = ["FurDark", "FurLight", "Cap", "Brass", "Vest", "Shirt", "Scarf", "Satchel", "Parcel", "Nose", "Eye"]
NUM = {n: i for i, n in enumerate(MATS)}


def shift(m, dy, dx, fill=0):
    o = np.full_like(m, fill)
    h, w = m.shape[:2]
    o[max(0, dy):h + min(0, dy), max(0, dx):w + min(0, dx)] = \
        m[max(0, -dy):h + min(0, -dy), max(0, -dx):w + min(0, -dx)]
    return o


def dilate(m, r):
    """Binärmaske mit einer Kreisscheibe vom Radius r aufdicken."""
    if r <= 0:
        return m.copy()
    R = int(np.ceil(r))
    o = np.zeros_like(m)
    for dy in range(-R, R + 1):
        for dx in range(-R, R + 1):
            if dx * dx + dy * dy <= r * r + 0.25:
                o |= shift(m, dy, dx, False)
    return o


def erode(m, r):
    return ~dilate(~m, r)


def load_pose(pdir, name, info):
    """Datenpässe einer Pose: Materialnummer (-1 leer), abgewandte Seite, Pfote, Tiefe in m, Licht 0..1."""
    idp = np.asarray(Image.open(pdir / f"{name}_id.png").convert("RGBA")).astype(np.int32)
    alpha = idp[..., 3] > 127
    idx = np.where(alpha, np.clip(np.rint(idp[..., 0] / 16.0).astype(int) - 1, 0, len(MATS) - 1), -1)
    far = alpha & (idp[..., 1] > 64)
    paw = alpha & (idp[..., 2] > 64)
    z = np.asarray(Image.open(pdir / f"{name}_z.png")).astype(np.float32) / 65535.0
    z = z * info["depth"]["range"] + info["depth"]["near"]
    light = np.asarray(Image.open(pdir / f"{name}_light.png").convert("L")).astype(np.float32) / 255.0
    return idx, far, paw, z, light


def ink_edges(idx, far, paw, z, zjump=0.03):
    """Kantenband (2 px, beide Seiten der Grenze): Material-, Seiten-, Pfotenwechsel, Tiefensprung, Umriss."""
    key = np.where(idx >= 0, idx * 4 + far * 2 + paw, -1)
    edge = np.zeros(idx.shape, bool)
    for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        nk = shift(key, dy, dx, -1)
        nz = shift(z, dy, dx, 0.0)
        diff = (nk != key) | ((key >= 0) & (nk >= 0) & (np.abs(nz - z) > zjump))
        edge |= diff & ((key >= 0) | (nk >= 0))
    return edge


def downscale(rgba, size):
    """Vormultipliziert verkleinern (Lanczos): erst hier entsteht die Kantenglättung."""
    im = Image.fromarray(rgba.astype(np.uint8), "RGBA").convert("RGBa")
    return np.asarray(im.resize(size, Image.LANCZOS).convert("RGBA"))


def hexrgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32)


def srgb_to_lin(c):
    c = np.asarray(c, np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def oklab(rgb):
    """sRGB 0..255 (…×3) -> Oklab (L, a, b)."""
    l_ = srgb_to_lin(rgb)
    M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]])
    M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]])
    lms = np.cbrt(l_ @ M1.T)
    return lms @ M2.T


def read_json(p):
    return json.loads(pathlib.Path(p).read_text())


def label(mask):
    """Zusammenhangskomponenten (8er-Nachbarschaft) per Breitensuche; gibt (labels, n) zurück."""
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    n = 0
    for y0, x0 in zip(*[a.tolist() for a in np.nonzero(mask)]):
        if lab[y0, x0]:
            continue
        n += 1
        lab[y0, x0] = n
        q = deque([(y0, x0)])
        while q:
            y, x = q.popleft()
            for yy in (y - 1, y, y + 1):
                if 0 <= yy < h:
                    for xx in (x - 1, x, x + 1):
                        if 0 <= xx < w and mask[yy, xx] and not lab[yy, xx]:
                            lab[yy, xx] = n
                            q.append((yy, xx))
    return lab, n
