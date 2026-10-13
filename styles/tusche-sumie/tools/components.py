"""Zusammenhangskomponenten ohne SciPy (Union-Find über Zeilenläufe). Für Strichbogen und Figurenbögen."""
import numpy as np


def label(mask):
    """mask: bool (H, W). Rückgabe: Liste von (y0, x0, y1, x1, Pixelzahl) je Komponente (8er-Nachbarschaft)."""
    h, w = mask.shape
    parent = []

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    runs_prev = []   # (x0, x1, id)
    runs_all = []    # (y, x0, x1, id)
    for y in range(h):
        row = mask[y]
        if not row.any():
            runs_prev = []
            continue
        d = np.diff(np.concatenate([[0], row.astype(np.int8), [0]]))
        starts, ends = np.where(d == 1)[0], np.where(d == -1)[0]
        cur = []
        for x0, x1 in zip(starts, ends):
            rid = len(parent)
            parent.append(rid)
            for px0, px1, pid in runs_prev:
                if px0 <= x1 and px1 >= x0:          # 8er-Nachbarschaft: Überlappung um 1 erweitert
                    ra, rb = find(rid), find(pid)
                    if ra != rb:
                        parent[ra] = rb
            cur.append((x0, x1, rid))
            runs_all.append((y, x0, x1, rid))
        runs_prev = cur
    boxes = {}
    for y, x0, x1, rid in runs_all:
        r = find(rid)
        b = boxes.get(r)
        y, x0, x1 = int(y), int(x0), int(x1)
        n = x1 - x0
        if b is None:
            boxes[r] = [y, x0, y + 1, x1, n]
        else:
            b[0] = min(b[0], y); b[1] = min(b[1], x0); b[2] = max(b[2], y + 1); b[3] = max(b[3], x1); b[4] += n
    return sorted((tuple(b) for b in boxes.values()), key=lambda b: (b[0] // 64, b[1]))
