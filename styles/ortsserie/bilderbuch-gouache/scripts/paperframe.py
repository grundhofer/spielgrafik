"""Papierrand finden und 16:9 schneiden (agy malt bei Gouache einen Rand aus unbemaltem Papier mit).

  painted_bbox(img)     bemalte Fläche (x0, y0, x1, y1) im Rohbild: Zeilen/Spalten, in denen weniger als 85 % der
                        Pixel papierfarben sind (hell, kaum bunt), von außen nach innen gesucht
  crop_box(img, dy=0)   16:9-Ausschnitt in der bemalten Fläche, 10 px eingerückt (ausgefranster Trockenpinsel-Rand),
                        volle Breite, senkrecht mittig plus dy (Rohpixel, auf den Spielraum begrenzt)
Im Hafenbild des Stils (raw/bg.png) liegt die von Hand gemessene Fläche bei (48, 100, 1218, 758).
"""
import numpy as np

from gmetrics import oklab

INSET = 10


def paper_mask(img):
    lab = oklab(img[::2, ::2])
    L, C = lab[..., 0], np.hypot(lab[..., 1], lab[..., 2])
    m = (L > 0.88) & (C < 0.045)
    return np.repeat(np.repeat(m, 2, 0), 2, 1)[:img.shape[0], :img.shape[1]]


def painted_bbox(img, thr=0.85):
    m = paper_mask(img)
    h, w = m.shape
    col = m.mean(0)
    row = m.mean(1)

    def first(prof, n):
        for i in range(n // 3):
            if prof[i] < thr:
                return i
        return 0

    x0 = first(col, w)
    x1 = w - first(col[::-1], w)
    y0 = first(row, h)
    y1 = h - first(row[::-1], h)
    return int(x0), int(y0), int(x1), int(y1)


def crop_box(img, dy=0):
    x0, y0, x1, y1 = painted_bbox(img)
    x0, y0, x1, y1 = x0 + INSET, y0 + INSET, x1 - INSET, y1 - INSET
    w = x1 - x0
    h = int(round(w * 9 / 16))
    if h > y1 - y0:                       # zu flach: Breite verringern, mittig
        h = y1 - y0
        nw = int(round(h * 16 / 9))
        x0 += (w - nw) // 2
        w = nw
    slack = (y1 - y0) - h
    top = y0 + slack // 2 + int(np.clip(dy, -(slack // 2), slack - slack // 2))
    return int(x0), int(top), int(x0 + w), int(top + h), {"bbox": [x0 - INSET, y0 - INSET, x1 + INSET, y1 + INSET],
                                                          "slack_px": int(slack)}
