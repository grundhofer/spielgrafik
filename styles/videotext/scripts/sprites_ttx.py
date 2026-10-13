#!/usr/bin/env python3
"""Dachs-Bilder aus badger.txt lesen und in die Vorlage setzen."""
import numpy as np

import ttxlib as T

HERE = T.HERE
COL = {c: i for i, c in enumerate(T.NAMES)}


def load(path=HERE / "scripts" / "badger.txt"):
    frames, cur, name = {}, [], None
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if line.startswith("#") or not line.strip():
            continue
        if line.startswith("= "):
            if name:
                frames[name] = cur
            name, cur = line[2:].strip(), []
            continue
        cur.append(line)
    if name:
        frames[name] = cur
    out = {}
    for n, rows in frames.items():
        w = max(len(r) for r in rows)
        a = np.full((len(rows), w), -1, dtype=int)
        for y, r in enumerate(rows):
            for x, ch in enumerate(r):
                if ch != ".":
                    a[y, x] = COL[ch]
        out[n] = a
    return out


def paste(t_on, t_off, w, sprite, x, y, weight=6.0, clip=None, sep=None):
    """Setzt das Bild in Vorlage und Gewichte (beide Blinkphasen gleich). clip: (x0, x1) sichtbarer Bereich.
    sep: Trennwunsch je Zelle; Zellen mit Figurpunkten werden zusammenhängend (0)."""
    h, wd = sprite.shape
    for j in range(h):
        for i in range(wd):
            v = sprite[j, i]
            X, Y = x + i, y + j
            if v < 0 or not (0 <= X < t_on.shape[1] and 0 <= Y < t_on.shape[0]):
                continue
            if clip and not (clip[0] <= X <= clip[1]):
                continue
            t_on[Y, X] = v
            t_off[Y, X] = v
            w[Y, X] = weight
            if sep is not None:
                sep[Y // 3, X // 2] = 0
    # Pflasterpunkte (blau, getrennt) in Zellen der Figur entfernen: dort sind Mosaike zusammenhängend, ein
    # Punkt würde als voller blauer Block neben den Beinen erscheinen
    if sep is not None:
        cells = {(Y // 3, X // 2) for j in range(h) for i in range(wd) if sprite[j, i] >= 0
                 for X, Y in [(x + i, y + j)] if 0 <= X < t_on.shape[1] and 0 <= Y < t_on.shape[0]}
        for r, c in cells:
            blk = (slice(3 * r, 3 * r + 3), slice(2 * c, 2 * c + 2))
            mask = (w[blk] < weight) & (t_on[blk] == 4)
            t_on[blk][mask] = 0
            t_off[blk][mask] = 0
    return t_on, t_off, w
