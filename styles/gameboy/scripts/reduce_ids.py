"""Materialkarte (Blender, 10-fach) -> Zielraster per Mehrheit je Zielpixel.

reduce(path) liefert ein Array 32x24 mit Materialnamen-Indizes (-1 = leer). Ein Zielpixel ist belegt, wenn mindestens
COVER der Unterpixel zur Figur gehören; das Material ist das häufigste darunter (kleine, wichtige Teile wie Nase und
Auge werden gewichtet, sonst verschwinden sie).
"""
import numpy as np
from PIL import Image

NAMES = ["FurDark", "FurLight", "Cap", "Brass", "Vest", "Shirt", "Scarf", "Satchel", "Parcel", "Nose", "Eye"]
COLS = np.array([(0, 0, 255), (255, 255, 255), (0, 255, 0), (255, 255, 0), (0, 128, 0), (255, 128, 0),
                 (255, 0, 0), (128, 0, 0), (255, 0, 255), (0, 255, 255), (128, 0, 255)], np.float32)
WEIGHT = {"Nose": 3.0, "Eye": 4.0, "Brass": 0.5}
COVER = 0.4


def reduce(path, ss=10):
    a = np.asarray(Image.open(path).convert("RGBA")).astype(np.float32)
    h, w = a.shape[0] // ss, a.shape[1] // ss
    rgb, alpha = a[..., :3], a[..., 3]
    d = ((rgb[:, :, None, :] - COLS[None, None]) ** 2).sum(-1)
    idx = d.argmin(-1)
    idx[alpha < 128] = -1
    out = np.full((h, w), -1, np.int8)
    wts = np.array([WEIGHT.get(n, 1.0) for n in NAMES])
    for y in range(h):
        for x in range(w):
            cell = idx[y * ss:(y + 1) * ss, x * ss:(x + 1) * ss].ravel()
            fig = cell[cell >= 0]
            if fig.size < COVER * ss * ss:
                continue
            cnt = np.bincount(fig, minlength=len(NAMES)) * wts
            out[y, x] = int(cnt.argmax())
    return out


def ascii_map(m):
    keys = "KWCBVSRTPNE"
    return "\n".join("".join("." if v < 0 else keys[v] for v in row) for row in m)
