#!/usr/bin/env python3
"""Dachs-Kurier als 16-Bit-Sprite: KI-Blatt (6 Lauf-, 4 Stehbilder, ≈ 60 Kunstpixel hoch) -> ≈ 24×32.

    .venv/bin/python styles/snes-16bit/scripts/build_badger.py [--preview out.png]

Materialtreue Verkleinerung (Vorgehen aus vga-adventure/scripts/build_badger.py, hier für 32 px und eine
SNES-Sprite-Palette mit 15 Farben + Transparenz):
  * Rohpixel werden per Oklab-Regel einem Material zugeordnet (Kontur, Fell, Weste/Mütze, Schal, Leder, Paket,
    Hell). Je Zielpixel gewinnt das Material mit den meisten Rohpixeln (dunkle Kleinteile mit Vorrang), der
    Ton kommt nur aus diesem Material und wird auf dessen Tonleiter gerundet.
  * Alle Bilder auf einem gemeinsamen Maßstab, Ursprung am Kopf (oberes Viertel) und an der Fußlinie der Reihe.
  * Kontur: jeder opake Randpixel bekommt die Konturfarbe (dunkles Braunviolett, nicht Schwarz).
Ausgabe: demo/art/badger.png (Zellen 32×32 in einer Reihe), demo/art/badger.json (Zellen, Palette, Anker).
"""
import argparse, json, pathlib, sys
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sneslib import c5, kmeans, oklab  # noqa: E402

STYLE = HERE.parent
RAW = STYLE / 'assets/raw/badger.png'          # erstes Blatt (6 Lauf-, 4 Stehbilder), nur noch Vergleich
ROW1 = (136, 536)
CUTS1 = [0, 272, 530, 779, 1037, 1289, 1536]
ROW2 = (592, 984)
RAW2 = STYLE / 'assets/raw/badger2.png'        # zweites Blatt: große Kopf-Proportionen, 4 Bilder in einer Reihe
ROW_B2 = (289, 803)
CUTS_B2 = [0, 390, 770, 1150, 1536]            # grob; genaue Schnitte an den Spaltenminima ±60 px
BODY_H = 30                    # Figur ohne Kontur; mit Kontur oben/unten 32
CELL = 32

MATERIALS = ('dunkel', 'fell', 'gruen', 'rot', 'leder', 'paket', 'hell')
RAMPS = {'dunkel': 1, 'fell': 2, 'gruen': 3, 'rot': 3, 'leder': 2, 'paket': 2, 'hell': 2}
PRIORITY = {'dunkel': 1.25, 'fell': 1.0, 'gruen': 1.0, 'rot': 1.05, 'leder': 1.1, 'paket': 1.1, 'hell': 1.05}


def classify(lab):
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    M = {m: i for i, m in enumerate(MATERIALS)}
    m = np.full(L.shape, M['fell'])
    m[(a < -0.004) & (b > 0.022)] = M['gruen']
    m[(a >= 0.05) & (b >= 0.04) & (L < 0.5)] = M['leder']
    m[(L >= 0.48) & (b > 0.045) & (L < 0.80)] = M['paket']
    m[(L >= 0.74) & (b <= 0.07)] = M['hell']
    m[L >= 0.86] = M['hell']
    red = (a > 0.075) & (a > 1.25 * b)
    m[red] = M['rot']
    m[(L < 0.255) & ~red] = M['dunkel']
    return m


def largest_component(op):
    H, W = op.shape
    lbl = np.zeros((H, W), int)
    best, bsize, n = 0, 0, 0
    for y, x in zip(*np.nonzero(op)):
        if lbl[y, x]:
            continue
        n += 1
        stack = [(y, x)]; lbl[y, x] = n; size = 0
        while stack:
            cy, cx = stack.pop(); size += 1
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    yy, xx = cy + dy, cx + dx
                    if 0 <= yy < H and 0 <= xx < W and op[yy, xx] and not lbl[yy, xx]:
                        lbl[yy, xx] = n; stack.append((yy, xx))
        if size > bsize:
            best, bsize = n, size
    return lbl == best


def frames():
    im = np.asarray(Image.open(RAW).convert('RGBA'))
    out = []
    y0, y1 = ROW1
    for a, b in zip(CUTS1[:-1], CUTS1[1:]):
        sub = im[y0:y1, a:b].copy()
        keep = largest_component(sub[..., 3] >= 200)
        sub[~keep] = 0
        out.append(('walk', sub))
    y0, y1 = ROW2
    op = im[y0:y1, :, 3] >= 200
    cols = np.flatnonzero(op.any(0))
    runs = np.split(cols, np.flatnonzero(np.diff(cols) > 8) + 1)
    for r in runs:
        if len(r) < 60:
            continue
        sub = im[y0:y1, r[0]:r[-1] + 1].copy()
        keep = largest_component(sub[..., 3] >= 200)
        sub[~keep] = 0
        out.append(('stand', sub))
    return out


def frames2():
    """Blatt 2: Stehen, Blinzeln, Sprechen, Schritt (nur die ersten drei werden verwendet)."""
    im = np.asarray(Image.open(RAW2).convert('RGBA'))
    y0, y1 = ROW_B2
    op = im[y0:y1, :, 3] >= 200
    prof = op.sum(0)
    cuts = [0] + [int(c - 60 + np.argmin(prof[c - 60:c + 60])) for c in CUTS_B2[1:-1]] + [im.shape[1]]
    out = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        sub = im[y0:y1, a:b].copy()
        keep = largest_component(sub[..., 3] >= 200)
        sub[~keep] = 0
        out.append(('stand', sub))
    return out


def head_cx(alpha, frac=0.25):
    ys = np.flatnonzero(alpha.any(1))
    top = alpha[ys[0]: ys[0] + int((ys[-1] - ys[0]) * frac)]
    return float(np.nonzero(top)[1].mean())


def reduce(sub, k, ax_dst):
    """Materialtreue Verkleinerung eines Rohbilds auf eine Zelle CELL×CELL (Fußlinie = Zeile CELL-2)."""
    alpha = sub[..., 3] >= 200
    ys, xs = np.nonzero(alpha)
    lab = oklab(sub[ys, xs, :3].astype(float))
    mat = classify(lab)
    anchor = head_cx(alpha)
    base = sub.shape[0]                     # Fußlinie der Reihe = Unterkante des Ausschnitts
    X = np.floor((xs + 0.5 - anchor) * k + ax_dst).astype(int)
    Y = np.floor((ys + 0.5 - base) * k + (CELL - 1)).astype(int)
    ok = (X >= 0) & (X < CELL) & (Y >= 0) & (Y < CELL)
    X, Y, mat, lab = X[ok], Y[ok], mat[ok], lab[ok]
    NM = len(MATERIALS)
    cnt = np.zeros((CELL, CELL, NM)); np.add.at(cnt, (Y, X, mat), 1)
    lsum = np.zeros((CELL, CELL, NM, 3)); np.add.at(lsum, (Y, X, mat), lab)
    cover = cnt.sum(-1) * k * k
    prio = np.array([PRIORITY[m] for m in MATERIALS])
    win = np.argmax(cnt * prio, -1)
    yy, xx = np.mgrid[0:CELL, 0:CELL]
    n = cnt[yy, xx, win]
    mean = lsum[yy, xx, win] / np.maximum(n, 1)[..., None]
    win[cover < 0.45] = -1
    return win, mean


def ramps(all_frames):
    px = np.concatenate([f[f[..., 3] >= 220][:, :3] for _, f in all_frames]).astype(float)
    lab = oklab(px)
    mat = classify(lab)
    pal, pmat = [], []
    for mi, m in enumerate(MATERIALS):
        sel = lab[mat == mi]
        if len(sel) > 40000:
            sel = sel[np.random.default_rng(mi).choice(len(sel), 40000, replace=False)]
        if m == 'dunkel':
            tones = np.array([np.percentile(sel, 50, axis=0)])
        else:
            tones = kmeans(sel, RAMPS[m], iters=25, seed=10 + mi)
        tones = tones[np.argsort(-tones[:, 0])]
        pal.extend(tones); pmat.extend([mi] * len(tones))
    return np.array(pal), np.array(pmat)


def tidy(idx, mat, iters=2):
    """Krümel entfernen: Pixel, dessen Material in der 3×3-Nachbarschaft höchstens einmal vorkommt (ohne
    Kontur), übernimmt das häufigste Nachbarmaterial (mit dessen häufigstem Ton)."""
    H, W = idx.shape
    D = MATERIALS.index('dunkel')
    for _ in range(iters):
        src = idx.copy()
        m = np.where(src >= 0, mat[np.maximum(src, 0)], -1)
        for y in range(H):
            for x in range(W):
                if src[y, x] < 0 or m[y, x] == D:
                    continue
                nm = m[max(0, y - 1):y + 2, max(0, x - 1):x + 2].ravel()
                nc = src[max(0, y - 1):y + 2, max(0, x - 1):x + 2].ravel()
                ok = nm >= 0
                nm, nc = nm[ok], nc[ok]
                if (nm == m[y, x]).sum() <= 1:
                    u, c = np.unique(nm[nm != m[y, x]], return_counts=True)
                    if len(u) and c.max() >= 4:
                        w = u[np.argmax(c)]
                        vals, vc = np.unique(nc[nm == w], return_counts=True)
                        idx[y, x] = vals[np.argmax(vc)]
    return idx


def outline(idx, dark):
    pad = np.pad(idx, 1, constant_values=-1)
    edge = (idx >= 0) & ((pad[:-2, 1:-1] < 0) | (pad[2:, 1:-1] < 0) | (pad[1:-1, :-2] < 0) | (pad[1:-1, 2:] < 0))
    idx = idx.copy()
    idx[edge] = dark
    return idx


def build(sheet=2):
    fr = frames() if sheet == 1 else frames2()
    pal_lab, pmat = ramps(fr)
    dark = int(np.flatnonzero(pmat == MATERIALS.index('dunkel'))[0])
    k = BODY_H / ((ROW1[1] - ROW1[0]) if sheet == 1 else (ROW_B2[1] - ROW_B2[0]))
    cells = []
    for kind, sub in fr:
        win, mean = reduce(sub, k, ax_dst=15.5)
        idx = np.full(win.shape, -1)
        for mi in range(len(MATERIALS)):
            sel = win == mi
            if not sel.any():
                continue
            cand = np.flatnonzero(pmat == mi)
            d = ((mean[sel][:, None, :] - pal_lab[cand][None]) ** 2).sum(-1)
            idx[sel] = cand[np.argmin(d, 1)]
        idx = tidy(idx, pmat)
        idx = outline(idx, dark)
        cells.append((kind, idx))
    from sneslib import oklab_to_rgb
    pal = c5(np.clip(oklab_to_rgb(pal_lab), 0, 255))
    return cells, pal, pmat


def to_rgba(idx, pal):
    out = np.zeros(idx.shape + (4,), np.uint8)
    m = idx >= 0
    out[m, :3] = pal[idx[m]]
    out[m, 3] = 255
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview')
    a = ap.parse_args()
    cells, pal, pmat = build()
    print(len(cells), 'Bilder, Palette', len(pal), ['%02x%02x%02x' % tuple(c) for c in pal])
    if a.preview:
        strip = np.concatenate([to_rgba(c, pal) for _, c in cells], 1)
        bg = Image.new('RGBA', (strip.shape[1], strip.shape[0]), (40, 52, 110, 255))
        bg.alpha_composite(Image.fromarray(strip))
        bg.resize((bg.width * 8, bg.height * 8), Image.NEAREST).save(a.preview)
