"""Kleine Vektorisier-Bibliothek für polygon-kino (nur NumPy): Bereiche finden, Umriss abnehmen, vereinfachen,
prüfen und wie die Grafikkarte rastern (Pixelmitten, keine Kantenglättung).

Koordinaten: Bildpunkte, x nach rechts, y nach unten; Pixel (x, y) deckt [x, x+1) × [y, y+1).
"""
import numpy as np


# ----------------------------------------------------------------------------------------------
# Zusammenhangskomponenten (4er-Nachbarschaft) über Läufe je Zeile
# ----------------------------------------------------------------------------------------------
def runs_of_row(row):
    """Läufe gleicher Werte != -1 in einer Zeile: Liste (start, ende, wert)."""
    n = row.shape[0]
    change = np.flatnonzero(row[1:] != row[:-1]) + 1
    starts = np.concatenate(([0], change))
    ends = np.concatenate((change, [n]))
    vals = row[starts]
    keep = vals != -1
    return list(zip(starts[keep].tolist(), ends[keep].tolist(), vals[keep].tolist()))


def components(lab):
    """lab: int-Bild, -1 = leer. Rückgabe: comp-Bild (int32, -1 = leer) und Liste je Komponente
    (wert, fläche, bbox[x0, y0, x1, y1])."""
    h, w = lab.shape
    parent = []

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    rows = []
    rid = 0
    prev = []
    for y in range(h):
        cur = []
        for s, e, v in runs_of_row(lab[y]):
            parent.append(rid)
            cur.append((s, e, v, rid))
            rid += 1
        i = j = 0
        while i < len(prev) and j < len(cur):
            ps, pe, pv, pr = prev[i]
            cs, ce, cv, cr = cur[j]
            if ps < ce and cs < pe and pv == cv:
                a, b = find(pr), find(cr)
                if a != b:
                    parent[max(a, b)] = min(a, b)
            if pe <= ce:
                i += 1
            else:
                j += 1
        rows.append(cur)
        prev = cur
    comp = np.full((h, w), -1, np.int32)
    roots = {}
    info = []
    for y, cur in enumerate(rows):
        for s, e, v, r in cur:
            root = find(r)
            if root not in roots:
                roots[root] = len(info)
                info.append([v, 0, [s, y, e, y + 1]])
            c = roots[root]
            comp[y, s:e] = c
            it = info[c]
            it[1] += e - s
            bb = it[2]
            bb[0] = min(bb[0], s)
            bb[2] = max(bb[2], e)
            bb[3] = y + 1
    return comp, info


# ----------------------------------------------------------------------------------------------
# Morphologie (rechteckig, getrennt nach Achsen)
# ----------------------------------------------------------------------------------------------
def dilate(m, r):
    if r <= 0:
        return m.copy()
    out = m.copy()
    for d in range(1, r + 1):
        out[:, d:] |= m[:, :-d]
        out[:, :-d] |= m[:, d:]
    m2 = out.copy()
    for d in range(1, r + 1):
        out[d:, :] |= m2[:-d, :]
        out[:-d, :] |= m2[d:, :]
    return out


def close_pinches(m):
    """Diagonale Berührungen (nur über eine Ecke verbundene Pixel) schließen, damit der Umriss einfach bleibt."""
    m = m.copy()
    for _ in range(50):
        a, b, c, d = m[:-1, :-1], m[:-1, 1:], m[1:, :-1], m[1:, 1:]
        p1 = b & c & ~a & ~d
        p2 = a & d & ~b & ~c
        if not (p1.any() or p2.any()):
            break
        m[:-1, :-1] |= p1
        m[:-1, 1:] |= p2
    return m


# ----------------------------------------------------------------------------------------------
# Umriss (Kantenverfolgung auf den Pixelkanten, Bereich rechts, 4er-Nachbarschaft)
# ----------------------------------------------------------------------------------------------
def trace_outer(m):
    """Äußerer Umriss eines 4-zusammenhängenden Bereichs als Liste von Ecken (x, y) im Uhrzeigersinn
    (Bildkoordinaten). Löcher werden ignoriert (das gefüllte Polygon deckt sie)."""
    h, w = m.shape
    W = w + 2
    pad = np.zeros((h + 2, W), np.uint8)
    pad[1:-1, 1:-1] = m
    ys, xs = np.nonzero(pad)
    k = np.lexsort((xs, ys))[0]
    y0, x0 = int(ys[k]), int(xs[k])
    flat = pad.tobytes()
    x, y, dx, dy = x0, y0, 1, 0
    pts = [(x0, y0)]
    start = (x0, y0, 1, 0)
    for _ in range(4 * (h + 2) * W):
        x, y = x + dx, y + dy
        rx, ry = -dy, dx                     # rechte Seite
        # Pixel vorn rechts und vorn links: Komponente +1 -> gleicher Index, -1 -> Index - 1
        arx, ary = x + (dx + rx - 1) // 2, y + (dy + ry - 1) // 2
        alx, aly = x + (dx - rx - 1) // 2, y + (dy - ry - 1) // 2
        ar = flat[ary * W + arx]
        al = flat[aly * W + alx]
        if not ar:
            ndx, ndy = -dy, dx               # rechts abbiegen
        elif al:
            ndx, ndy = dy, -dx               # links abbiegen
        else:
            ndx, ndy = dx, dy
        if (ndx, ndy) != (dx, dy):
            pts.append((x, y))
        dx, dy = ndx, ndy
        if (x, y, dx, dy) == start:
            break
    if pts[-1] == pts[0]:
        pts.pop()
    return [(px - 1, py - 1) for px, py in pts]


# ----------------------------------------------------------------------------------------------
# Vereinfachen (Douglas-Peucker, geschlossen) und Prüfen
# ----------------------------------------------------------------------------------------------
def _dp(pts, eps):
    if len(pts) < 3:
        return pts
    a, b = np.asarray(pts[0], float), np.asarray(pts[-1], float)
    p = np.asarray(pts, float)
    ab = b - a
    L = np.hypot(*ab)
    if L < 1e-12:
        d = np.hypot(*(p - a).T)
    else:
        d = np.abs(ab[0] * (p[:, 1] - a[1]) - ab[1] * (p[:, 0] - a[0])) / L
    i = int(np.argmax(d))
    if d[i] > eps:
        left = _dp(pts[:i + 1], eps)
        right = _dp(pts[i:], eps)
        return left[:-1] + right
    return [pts[0], pts[-1]]


def simplify_closed(pts, eps):
    n = len(pts)
    if n <= 4:
        return list(pts)
    p = np.asarray(pts, float)
    i = 0
    j = int(np.argmax(np.hypot(*(p - p[i]).T)))
    i = int(np.argmax(np.hypot(*(p - p[j]).T)))
    i, j = min(i, j), max(i, j)
    chain1 = list(pts[i:j + 1])
    chain2 = list(pts[j:]) + list(pts[:i + 1])
    s1 = _dp(chain1, eps)
    s2 = _dp(chain2, eps)
    return s1[:-1] + s2[:-1]


def area(pts):
    p = np.asarray(pts, float)
    x, y = p[:, 0], p[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(np.roll(x, -1), y))


def is_simple(pts):
    """Keine Selbstüberschneidung und keine doppelten Ecken (Godot verwirft solche Polygone ohne Meldung)."""
    p = np.asarray(pts, float)
    n = len(p)
    if n < 3:
        return False
    if len({(round(a, 6), round(b, 6)) for a, b in p}) != n:
        return False
    a = p
    b = np.roll(p, -1, axis=0)
    for i in range(n):
        # Strecke i gegen alle nicht benachbarten Strecken j > i
        js = np.arange(i + 2, n)
        if i == 0:
            js = js[js != n - 1]
        if js.size == 0:
            continue
        p1, p2 = a[i], b[i]
        q1, q2 = a[js], b[js]
        d1 = (p2[0] - p1[0]) * (q1[:, 1] - p1[1]) - (p2[1] - p1[1]) * (q1[:, 0] - p1[0])
        d2 = (p2[0] - p1[0]) * (q2[:, 1] - p1[1]) - (p2[1] - p1[1]) * (q2[:, 0] - p1[0])
        d3 = (q2[:, 0] - q1[:, 0]) * (p1[1] - q1[:, 1]) - (q2[:, 1] - q1[:, 1]) * (p1[0] - q1[:, 0])
        d4 = (q2[:, 0] - q1[:, 0]) * (p2[1] - q1[:, 1]) - (q2[:, 1] - q1[:, 1]) * (p2[0] - q1[:, 0])
        proper = (d1 * d2 < 0) & (d3 * d4 < 0)
        if np.any(proper):
            return False
        # Berührungen: ein Endpunkt liegt auf der anderen Strecke
        eps = 1e-9

        def on_seg(px, py, ax, ay, bx, by):
            return ((np.minimum(ax, bx) - eps <= px) & (px <= np.maximum(ax, bx) + eps) &
                    (np.minimum(ay, by) - eps <= py) & (py <= np.maximum(ay, by) + eps))

        touch = ((np.abs(d1) < eps) & on_seg(q1[:, 0], q1[:, 1], p1[0], p1[1], p2[0], p2[1])) | \
                ((np.abs(d2) < eps) & on_seg(q2[:, 0], q2[:, 1], p1[0], p1[1], p2[0], p2[1])) | \
                ((np.abs(d3) < eps) & on_seg(p1[0], p1[1], q1[:, 0], q1[:, 1], q2[:, 0], q2[:, 1])) | \
                ((np.abs(d4) < eps) & on_seg(p2[0], p2[1], q1[:, 0], q1[:, 1], q2[:, 0], q2[:, 1]))
        if np.any(touch):
            return False
    return True


def drop_collinear(pts):
    out = list(pts)
    changed = True
    while changed and len(out) > 3:
        changed = False
        for i in range(len(out)):
            a, b, c = out[i - 1], out[i], out[(i + 1) % len(out)]
            cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
            if abs(cr) < 1e-9:
                out.pop(i)
                changed = True
                break
    return out


# ----------------------------------------------------------------------------------------------
# Rastern wie die Grafikkarte: Pixel gesetzt, wenn seine Mitte im Polygon liegt (gerade-ungerade-Regel)
# ----------------------------------------------------------------------------------------------
def raster(img, pts, value):
    h, w = img.shape[:2]
    p = np.asarray(pts, float)
    x0, y0 = p.min(axis=0)
    x1, y1 = p.max(axis=0)
    ya = max(0, int(np.floor(y0 - 0.5)))
    yb = min(h - 1, int(np.ceil(y1 - 0.5)))
    if yb < ya:
        return
    a = p
    b = np.roll(p, -1, axis=0)
    yc = np.arange(ya, yb + 1) + 0.5
    ay, by = a[:, 1][None, :], b[:, 1][None, :]
    cross = ((ay <= yc[:, None]) & (by > yc[:, None])) | ((by <= yc[:, None]) & (ay > yc[:, None]))
    with np.errstate(divide="ignore", invalid="ignore"):
        t = (yc[:, None] - ay) / (by - ay)
        xs = a[:, 0][None, :] + t * (b[:, 0] - a[:, 0])[None, :]
    for r, y in enumerate(range(ya, yb + 1)):
        xr = np.sort(xs[r][cross[r]])
        for k in range(0, len(xr) - 1, 2):
            # Pixel x mit x + 0.5 in [xl, xr)
            xa = int(np.ceil(xr[k] - 0.5))
            xb = int(np.ceil(xr[k + 1] - 0.5))
            xa, xb = max(xa, 0), min(xb, w)
            if xb > xa:
                img[y, xa:xb] = value
