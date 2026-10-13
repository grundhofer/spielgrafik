#!/usr/bin/env python3
"""Wandelt ein fertiges 160×168-Indexbild (16 EGA-Farben) automatisch in Zeichenbefehle um (Linien + Füllungen).

Für den KI-Weg: KI-Bild -> snap_ai_bg.py (Raster, Palette, Aufräumen) -> vectorize.py -> dieselbe Godot-Demo.
Verfahren je Farbfläche (4-zusammenhängend, nicht weiß), größte Flächen zuerst:
  1. Randpixel, die an noch nicht gezeichnete (weiße) Pixel grenzen, als gerade Linienstücke ziehen; jedes Stück
     wird mit demselben Linienalgorithmus gerastert wie in der Demo und darf nur diese Randpixel treffen.
  2. Den Rest der Fläche (je Teilstück ein Startpunkt) flutfüllen. Er ist vom eigenen Rand oder von schon
     gefüllten Flächen umschlossen, daher läuft keine Füllung aus.
  Schichten (Standard): dünne Flächen ohne Innenpixel (Fugen, Wellen, Konturen, Sterne) werden beim Füllen der
  Umgebung zugeschlagen und am Ende als Linien darübergezogen, wie beim Zeichnen von Hand.
Weiße Flächen bleiben einfach stehen (die Leinwand ist weiß). Ergebnis wird per Wiedergabe geprüft.

    .venv/bin/python styles/ega-adventure/scripts/vectorize.py in_index.png out.pic.json [--preview out.png]
Eingabe: PNG in EGA-Farben (160×168 oder 320×168 mit Doppelpixeln).
"""
import argparse, json, pathlib, sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from agipic import EGA_RGB, W, H, line_points, replay, to_rgb  # noqa: E402

N8 = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]


def load_index(path):
    rgb = np.asarray(Image.open(path).convert("RGB")).astype(int)
    if rgb.shape[1] == 2 * W:
        rgb = rgb[:, 0::2]
    assert rgb.shape[:2] == (H, W), rgb.shape
    d = ((rgb[:, :, None, :] - EGA_RGB[None, None].astype(int)) ** 2).sum(-1)
    return d.argmin(-1).astype(np.uint8)


def label4(idx):
    lab = -np.ones(idx.shape, np.int32)
    n = 0
    for y in range(H):
        for x in range(W):
            if lab[y, x] >= 0:
                continue
            c = idx[y, x]
            stack = [(x, y)]
            lab[y, x] = n
            while stack:
                cx, cy = stack.pop()
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if 0 <= nx < W and 0 <= ny < H and lab[ny, nx] < 0 and idx[ny, nx] == c:
                        lab[ny, nx] = n
                        stack.append((nx, ny))
            n += 1
    return lab, n


def segments(border):
    """Deckt eine Pixelmenge mit geraden Linienstücken ab (gierig: jeweils das Stück, das die meisten noch
    offenen Pixel trifft und ganz in der Menge liegt)."""
    rest = set(border)
    segs = []
    while rest:
        # Startpunkt: offenes Pixel mit den wenigsten offenen Nachbarn (Kettenende)
        p = min(rest, key=lambda q: (sum((q[0] + dx, q[1] + dy) in rest for dx, dy in N8), q[1], q[0]))
        best, best_pts = p, [p]
        # Kandidaten: Pixel der Menge im Umkreis, die über eine 8-Kette erreichbar sind
        frontier, seen = [p], {p}
        while frontier:
            nxt = []
            for q in frontier:
                for dx, dy in N8:
                    r = (q[0] + dx, q[1] + dy)
                    if r in border and r not in seen and abs(r[0] - p[0]) <= 48 and abs(r[1] - p[1]) <= 48:
                        seen.add(r)
                        nxt.append(r)
            frontier = nxt
        for q in seen:
            pts = line_points(p[0], p[1], q[0], q[1])
            if len(pts) <= len(best_pts):
                continue
            if all(t in border for t in pts):
                gain = sum(t in rest for t in pts)
                if gain > sum(t in rest for t in best_pts) or (gain == sum(t in rest for t in best_pts)
                                                               and len(pts) > len(best_pts)):
                    best, best_pts = q, pts
        segs.append((p, best))
        rest.difference_update(best_pts)
    return segs


def chain(segs):
    """Hängt Stücke mit gemeinsamem Endpunkt zu Linienzügen zusammen."""
    out = []
    pool = list(segs)
    while pool:
        a, b = pool.pop(0)
        poly = [a, b]
        grown = True
        while grown:
            grown = False
            for i, (c, d) in enumerate(pool):
                # der Linienalgorithmus ist richtungsabhängig: umgedreht nur, wenn er dieselben Pixel trifft
                if c == poly[-1] and c != d:
                    poly.append(d)
                elif d == poly[-1] and c != d and set(line_points(*d, *c)) == set(line_points(*c, *d)):
                    poly.append(c)
                else:
                    continue
                pool.pop(i)
                grown = True
                break
        out.append(poly)
    return out


def base_and_strokes(idx):
    """Schichten wie beim Zeichnen von Hand: dünne Flächen (ohne einziges Innenpixel, z. B. Fugen, Wellen,
    Sterne, Konturlinien) werden zum Füllen der Umgebung zugeschlagen und erst danach als Linien darübergezogen."""
    lab, n = label4(idx)
    thin = np.zeros((H, W), bool)
    for r in range(n):
        m = lab == r
        ys, xs = np.nonzero(m)
        inner = False
        for y, x in zip(ys, xs):
            if all(0 <= nx < W and 0 <= ny < H and lab[ny, nx] == r or not (0 <= nx < W and 0 <= ny < H)
                   for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))):
                inner = True
                break
        if not inner:
            thin |= m
    base = idx.copy()
    todo = thin.copy()
    for _ in range(64):
        if not todo.any():
            break
        nxt = todo.copy()
        for y, x in zip(*np.nonzero(todo)):
            nb = [int(base[ny, nx]) for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
                  if 0 <= nx < W and 0 <= ny < H and not todo[ny, nx]]
            if nb:
                base[y, x] = np.bincount(nb, minlength=16).argmax()
                nxt[y, x] = False
        todo = nxt
    return base, thin


def strokes(idx, thin):
    """Linienbefehle für die dünnen Flächen (je Farbe, je 8-zusammenhängendes Stück)."""
    cmds = []
    for c in range(16):
        pts = {(int(x), int(y)) for y, x in zip(*np.nonzero(thin & (idx == c)))}
        if not pts:
            continue
        cmds.append(["c", c])
        dots = []
        for poly in chain(segments(pts)):
            if len(poly) == 2 and poly[0] == poly[1]:
                dots += list(poly[0])
            else:
                cmds.append(["l", [v for pt in poly for v in pt]])
        if dots:
            cmds.append(["s", dots])
    return cmds


def vectorize(idx, layered=True):
    if layered:
        base, thin = base_and_strokes(idx)
        cmds, nreg = vectorize(base, layered=False)
        return cmds + strokes(idx, thin), nreg
    lab, n = label4(idx)
    regions = []
    for r in range(n):
        ys, xs = np.nonzero(lab == r)
        c = int(idx[ys[0], xs[0]])
        if c == 15:
            continue
        regions.append((len(ys), r, c, ys, xs))
    regions.sort(key=lambda t: (-t[0], t[1]))
    cmds = []
    cur = None
    drawn = np.zeros((H, W), bool)
    for area, r, c, ys, xs in regions:
        # Umriss nur dort, wo die Fläche an noch weiße (nicht gezeichnete) Pixel grenzt: an schon gefüllte
        # Nachbarn kann die Flutfüllung nicht auslaufen, dort genügt die Füllung selbst.
        border, inner = [], np.zeros((H, W), bool)
        for y, x in zip(ys, xs):
            edge = False
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < W and 0 <= ny < H and lab[ny, nx] != r and not drawn[ny, nx]:
                    edge = True
                    break
            if edge:
                border.append((int(x), int(y)))
            else:
                inner[y, x] = True
        if cur != c:
            cmds.append(["c", c])
            cur = c
        bset = set(border)
        dots = []
        for poly in chain(segments(bset)):
            if len(poly) == 2 and poly[0] == poly[1]:
                dots += list(poly[0])
            else:
                cmds.append(["l", [v for pt in poly for v in pt]])
        if dots:
            cmds.append(["s", dots])
        # Innenteile: je Teilstück ein Startpunkt
        seeds = []
        seen = np.zeros_like(inner)
        for y, x in zip(*np.nonzero(inner)):
            if seen[y, x]:
                continue
            seeds += [int(x), int(y)]
            stack = [(x, y)]
            seen[y, x] = True
            while stack:
                cx, cy = stack.pop()
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if 0 <= nx < W and 0 <= ny < H and inner[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((nx, ny))
        if seeds:
            cmds.append(["f", seeds])
        drawn[ys, xs] = True
    return cmds, len(regions)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--preview")
    ap.add_argument("--flat", action="store_true", help="ohne Schichten: jede Farbfläche mit Umriss und Füllung")
    a = ap.parse_args()
    idx = load_index(a.inp)
    cmds, nreg = vectorize(idx, layered=not a.flat)
    vis, _ = replay(cmds)
    diff = int((vis != idx).sum())
    n_l = sum(1 for c in cmds if c[0] == "l")
    n_seg = sum(len(c[1]) // 2 - 1 for c in cmds if c[0] == "l")
    n_f = sum(len(c[1]) // 2 for c in cmds if c[0] == "f")
    n_s = sum(len(c[1]) // 2 for c in cmds if c[0] == "s")
    data = {"w": W, "h": H, "commands": cmds}
    pathlib.Path(a.out).write_text(json.dumps(data, separators=(",", ":")))
    if a.preview:
        to_rgb(vis).save(a.preview)
    size = len(json.dumps(cmds, separators=(",", ":")))
    print(f"{nreg} Farbflächen -> {len(cmds)} Befehle: {n_l} Linienzüge ({n_seg} Stücke), {n_s} Einzelpunkte, "
          f"{n_f} Füllstartpunkte; {size} Byte JSON; Abweichung nach Wiedergabe: {diff} Pixel")
    sys.exit(1 if diff else 0)


if __name__ == "__main__":
    main()
