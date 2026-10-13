"""KI-Strichvorlage -> Linienzüge im 280×160-Raster (assets/lines.json, Vorschau assets/lines_preview.png).

    .venv/bin/python styles/apple2-hires/scripts/trace_lines.py [assets/raw/bg_a.png]

1. Ganze Vorlage (CROP_H = None) oder Ausschnitt ab CROP_Y, schwarze Umrisse über die Helligkeit.
2. Verdünnen auf 1 Bildpunkt (Zhang-Suen), Wege verfolgen (Endpunkte zuerst), kurze Sporne weg.
3. Douglas-Peucker in Quellpixeln (EPS), Ecken in das Zielraster rechnen.
Ergebnis: Liste von Linienzügen mit ganzzahligen Zielkoordinaten, gruppiert nach zusammenhängenden Objekten.
"""
import json, pathlib, sys
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent
SRC = ENTRY / (sys.argv[1] if len(sys.argv) > 1 else "assets/raw/bg2_b.png")
TW, TH = 280, 160
# Ganze Vorlage (3:2) auf 280×160: senkrecht 0,85-fach gestaucht. Das entspricht den schmalen Bildpunkten des
# Originals am Fernseher (280×192 auf 4:3); in der Aufnahme mit quadratischen Punkten wirkt das Bild 15 % flacher.
CROP_Y = 0
CROP_H = None
LUMA_MAX = 52          # dunkler als das = Umriss (Himmel liegt bei ~70)
EPS = 2.2              # Douglas-Peucker in Quellpixeln (≈ 0,5 Zielpixel)
SPUR = 10              # freie Enden kürzer als das (Quellpixel) fallen weg


def zhang_suen(img):
    img = img.astype(np.uint8).copy()
    while True:
        changed = False
        for step in (0, 1):
            P = np.pad(img, 1)
            p2, p3, p4 = P[:-2, 1:-1], P[:-2, 2:], P[1:-1, 2:]
            p5, p6, p7 = P[2:, 2:], P[2:, 1:-1], P[2:, :-2]
            p8, p9 = P[1:-1, :-2], P[:-2, :-2]
            nb = [p2, p3, p4, p5, p6, p7, p8, p9, p2]
            B = sum(n.astype(np.int32) for n in nb[:8])
            A = sum(((nb[i] == 0) & (nb[i + 1] == 1)).astype(np.int32) for i in range(8))
            if step == 0:
                c = ((p2 * p4 * p6) == 0) & ((p4 * p6 * p8) == 0)
            else:
                c = ((p2 * p4 * p8) == 0) & ((p2 * p6 * p8) == 0)
            m = (img == 1) & (B >= 2) & (B <= 6) & (A == 1) & c
            if m.any():
                img[m] = 0
                changed = True
        if not changed:
            return img


NB8 = [(-1, 0), (0, 1), (1, 0), (0, -1), (-1, 1), (1, 1), (1, -1), (-1, -1)]


def trace(sk):
    H, W = sk.shape
    pts = set(zip(*np.nonzero(sk)))
    def nbrs(p):
        y, x = p
        return [(y + dy, x + dx) for dy, dx in NB8 if (y + dy, x + dx) in pts]
    deg = {p: len(nbrs(p)) for p in pts}
    visited = set()
    paths = []

    def walk(start, first=None):
        path = [start]
        visited.add(start)
        cur, prev_dir = start, None
        if first is not None:
            path = [first, start]
        while True:
            cand = [q for q in nbrs(cur) if q not in visited]
            if not cand:
                # an eine schon gezeichnete Linie anschließen (Kreuzung), damit keine Lücke bleibt
                touch = [q for q in nbrs(cur) if q in visited and q not in path[-3:]]
                if touch:
                    path.append(touch[0])
                return path
            if prev_dir is not None:
                cand.sort(key=lambda q: -((q[0] - cur[0]) * prev_dir[0] + (q[1] - cur[1]) * prev_dir[1])
                          + (0.1 if abs(q[0] - cur[0]) + abs(q[1] - cur[1]) == 2 else 0))
            else:
                cand.sort(key=lambda q: abs(q[0] - cur[0]) + abs(q[1] - cur[1]))
            nxt = cand[0]
            prev_dir = (nxt[0] - cur[0], nxt[1] - cur[1])
            visited.add(nxt)
            path.append(nxt)
            cur = nxt

    ends = sorted([p for p in pts if deg[p] == 1], key=lambda p: (p[0], p[1]))
    for e in ends:
        if e not in visited:
            paths.append(walk(e))
    while True:
        rest = [p for p in pts if p not in visited]
        if not rest:
            break
        # bevorzugt Punkte neben schon gezeichneten (Abzweig), sonst beliebig (geschlossene Schleife)
        rest.sort(key=lambda p: (0 if any(q in visited for q in nbrs(p)) else 1, p[0], p[1]))
        p = rest[0]
        att = [q for q in nbrs(p) if q in visited]
        paths.append(walk(p, att[0] if att else None))
    return paths


def dp(points, eps):
    pts = np.asarray(points, float)
    if len(pts) < 3:
        return pts
    a, b = pts[0], pts[-1]
    ab = b - a
    n = np.hypot(*ab)
    if n < 1e-9:
        d = np.hypot(*(pts - a).T)
    else:
        d = np.abs(ab[0] * (pts[:, 1] - a[1]) - ab[1] * (pts[:, 0] - a[0])) / n
    i = int(np.argmax(d))
    if d[i] > eps:
        l = dp(pts[:i + 1], eps)
        r = dp(pts[i:], eps)
        return np.vstack([l[:-1], r])
    return np.vstack([a, b])


def main():
    im = np.asarray(Image.open(SRC).convert("RGB")).astype(np.float32)
    H0, W0 = im.shape[:2]
    ch = CROP_H or (H0 - CROP_Y)
    im = im[CROP_Y:CROP_Y + ch]
    luma = im @ np.array([0.299, 0.587, 0.114], np.float32)
    mask = luma < LUMA_MAX
    mask[:2] = mask[-2:] = False
    mask[:, :2] = mask[:, -2:] = False
    sk = zhang_suen(mask)
    paths = trace(sk)
    sx, sy = TW / W0, TH / ch
    strokes = []
    for p in paths:
        length = len(p)
        if length < SPUR:
            continue
        simp = dp(p, EPS)
        tpts = [(int(round(x * sx - 0.5 + 0.5 * sx)), int(round(y * sy - 0.5 + 0.5 * sy))) for y, x in simp]
        tpts = [(min(TW - 1, max(0, x)), min(TH - 1, max(0, y))) for x, y in tpts]
        dedup = [tpts[0]]
        for q in tpts[1:]:
            if q != dedup[-1]:
                dedup.append(q)
        strokes.append({"pts": dedup, "src_len": length,
                        "src": [[round(float(x), 1), round(float(y), 1)] for y, x in simp]})
    out = {"source": str(SRC.relative_to(ENTRY)), "crop_y": CROP_Y, "crop_h": ch, "size": [TW, TH],
           "strokes": strokes}
    (ENTRY / "assets" / "lines.json").write_text(json.dumps(out))
    # Vorschau: Skelett und Zielraster
    prev = np.zeros((TH, TW), np.uint8)
    from bres import line_pixels
    for s in strokes:
        pts = s["pts"]
        if len(pts) == 1:
            prev[pts[0][1], pts[0][0]] = 255
        for a, b in zip(pts, pts[1:]):
            for x, y in line_pixels(a, b):
                prev[y, x] = 255
    Image.fromarray(prev).resize((TW * 3, TH * 3), Image.NEAREST).save(ENTRY / "assets" / "lines_preview.png")
    print(f"{len(paths)} Wege, {len(strokes)} Linienzüge, {sum(len(s['pts']) for s in strokes)} Ecken, "
          f"{int((prev > 0).sum())} Linienpunkte")


if __name__ == "__main__":
    main()
