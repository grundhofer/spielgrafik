"""Kleine Pixelhilfen für Bilder aus Tonnummern (0 = hellster ... 3 = dunkelster Ton, -1 = durchsichtig)."""
import numpy as np
from PIL import Image

GB = [(0x9b, 0xbc, 0x0f), (0x8b, 0xac, 0x0f), (0x30, 0x62, 0x30), (0x0f, 0x38, 0x0f)]   # Palette gb (sprites.py)


def stamp(text):
    """ASCII-Bild -> Array. '.' = durchsichtig, '0'..'3' = Ton."""
    rows = [r for r in text.strip("\n").split("\n")]
    rows = [r.strip() for r in rows]
    w = max(len(r) for r in rows)
    a = np.full((len(rows), w), -1, np.int8)
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch in "0123":
                a[y, x] = int(ch)
    return a


def put(canvas, s, x, y, flip=False):
    if flip:
        s = s[:, ::-1]
    h, w = s.shape
    H, W = canvas.shape
    for yy in range(h):
        for xx in range(w):
            v = s[yy, xx]
            cx, cy = x + xx, y + yy
            if v >= 0 and 0 <= cx < W and 0 <= cy < H:
                canvas[cy, cx] = v


def rgb(canvas, transparent=(255, 0, 255)):
    h, w = canvas.shape
    out = np.zeros((h, w, 3), np.uint8)
    out[:] = transparent
    for i, c in enumerate(GB):
        out[canvas == i] = c
    return out


def save_preview(canvas, path, scale=1, transparent=(255, 0, 255)):
    im = Image.fromarray(rgb(canvas, transparent))
    if scale != 1:
        im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
    im.save(path)
