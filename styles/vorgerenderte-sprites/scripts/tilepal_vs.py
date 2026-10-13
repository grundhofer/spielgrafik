"""Kachelpaletten nach der Regel der 16-Bit-Konsole (Mode 1, 4 bpp): jede 8×8-Kachel einer Ebene nutzt genau
eine von P Paletten mit je 15 Farben (+ Durchsichtig). Hintergrundebenen teilen sich die P Paletten.

Eigene, kompakte Fassung (Idee wie styles/snes-16bit/scripts/tilepal.py, nicht kopiert):
  1. Quellpalette: alle Pixel aller Ebenen und Bildfolgen auf N Quellfarben (k-means, 15 Bit).
  2. Jede Kachel ist ein Histogramm über die Quellfarben (Bildfolgen: Summe über alle Bilder, weil die
     Palettennummer einer Kachel in der Kachelkarte steht und nicht je Bild wechselt).
  3. Start: Kacheln nach mittlerer Farbe in P Gruppen. Dann abwechselnd: je Palette 15 Farben aus den
     Quellfarben ihrer Kacheln (gewichtetes k-means, Zentren auf vorkommende Farben gezogen), je Kachel die
     Palette mit dem kleinsten Fehler (Σ Anzahl^γ · Oklab-Abstand²).
"""
import numpy as np

import vs_color as C

GAMMA = 0.6


def _kmeans_idx(lab, w, k, seed, iters=30):
    """Gewichtetes k-means über Punkte lab (n,3); Rückgabe: Indizes der gewählten (vorkommenden) Punkte."""
    n = len(lab)
    if n <= k:
        return np.arange(n)
    rng = np.random.default_rng(seed)
    first = int(np.argmax(w))
    cent = [lab[first]]
    d2 = ((lab - cent[0]) ** 2).sum(-1)
    for _ in range(1, k):
        p = d2 * w
        if p.sum() <= 0:
            break
        i = rng.choice(n, p=p / p.sum())
        cent.append(lab[i])
        d2 = np.minimum(d2, ((lab - lab[i]) ** 2).sum(-1))
    Cn = np.array(cent)
    for _ in range(iters):
        a = ((lab[:, None] - Cn[None]) ** 2).sum(-1).argmin(1)
        new = Cn.copy()
        for j in range(len(Cn)):
            m = a == j
            if m.any():
                new[j] = (lab[m] * w[m, None]).sum(0) / w[m].sum()
        if np.allclose(new, Cn, atol=1e-6):
            break
        Cn = new
    a = ((lab[:, None] - Cn[None]) ** 2).sum(-1).argmin(1)
    out = []
    for j in range(len(Cn)):
        m = np.flatnonzero(a == j)
        if len(m):
            out.append(m[np.argmin(((lab[m] - Cn[j]) ** 2).sum(-1))])
    return np.array(sorted(set(out)))


def solve(layers, n_src=192, npal=8, per=15, iters=12, seed=5):
    """layers: Liste von (Bilder, Maske) je Ebene; Bilder: Liste float-RGB (H,W,3) gleicher Größe
    (Bildfolge), Maske (H,W) bool = zählende Pixel (deckend). Rückgabe: Paletten (npal, per, 3) als 8-Bit,
    je Ebene Kachel-Palettenkarte (th, tw) und je Bild Indexbild (Palette, Eintrag)."""
    allpx = np.concatenate([im[m] for ims, m in layers for im in ims])
    src = C.kmeans_palette(allpx, n_src, weight_pow=0.5)
    src_lab = C.oklab(src / 255.0)
    D = ((src_lab[:, None] - src_lab[None]) ** 2).sum(-1)
    # Histogramme je Kachel
    tiles = []           # (ebene, ty, tx, hist)
    lbls = []
    for li, (ims, m) in enumerate(layers):
        H, W = m.shape
        lb = [C.map_to_palette(im, src) for im in ims]
        lbls.append(lb)
        th, tw = (H + 7) // 8, (W + 7) // 8
        for ty in range(th):
            for tx in range(tw):
                hist = np.zeros(len(src))
                sl = (slice(ty * 8, ty * 8 + 8), slice(tx * 8, tx * 8 + 8))
                mm = m[sl]
                if not mm.any():
                    continue
                for l in lb:
                    np.add.at(hist, l[sl][mm], 1)
                tiles.append((li, ty, tx, hist))
    Hs = np.array([t[3] for t in tiles])
    Wt = Hs ** GAMMA
    # Start: k-means über mittlere Kachelfarbe
    mean_lab = (Hs @ src_lab) / Hs.sum(1, keepdims=True)
    rng = np.random.default_rng(seed)
    cent = mean_lab[rng.choice(len(Hs), npal, replace=False)]
    for _ in range(20):
        a = ((mean_lab[:, None] - cent[None]) ** 2).sum(-1).argmin(1)
        for j in range(npal):
            if (a == j).any():
                cent[j] = mean_lab[a == j].mean(0)
    assign = a
    pals = [None] * npal
    for it in range(iters):
        for j in range(npal):
            sel = assign == j
            if not sel.any():
                # leere Palette: Kachel mit dem größten Fehler übernehmen
                worst = int(np.argmax(err_t)) if it else int(rng.integers(len(Hs)))
                sel = np.zeros(len(Hs), bool)
                sel[worst] = True
                assign[worst] = j
            w = Wt[sel].sum(0)
            idx = np.flatnonzero(w > 0)
            pick = _kmeans_idx(src_lab[idx], w[idx], per, seed + j)
            pals[j] = idx[pick]
        # Fehler je Kachel und Palette
        E = np.stack([Wt @ D[:, p].min(1) for p in pals], 1)
        new = E.argmin(1)
        err_t = E[np.arange(len(Hs)), new]
        changed = int((new != assign).sum())
        assign = new
        if changed == 0:
            break
    pal8 = np.array([np.vstack([src[p], np.repeat(src[p][:1], per - len(p), 0)]) for p in pals])
    # Abbilden
    maps, out = [], []
    for li, (ims, m) in enumerate(layers):
        H, W = m.shape
        th, tw = (H + 7) // 8, (W + 7) // 8
        tmap = np.full((th, tw), -1, int)
        for (l2, ty, tx, _), pj in zip(tiles, assign):
            if l2 == li:
                tmap[ty, tx] = pj
        maps.append(tmap)
        res = []
        for im in ims:
            rgb = np.zeros((H, W, 3), np.uint8)
            for ty in range(th):
                for tx in range(tw):
                    pj = tmap[ty, tx]
                    if pj < 0:
                        continue
                    sl = (slice(ty * 8, ty * 8 + 8), slice(tx * 8, tx * 8 + 8))
                    ix = C.map_to_palette(im[sl], pal8[pj])
                    rgb[sl] = pal8[pj][ix]
            res.append(rgb)
        out.append(res)
    return pal8, maps, out, float(err_t.sum() / Wt.sum())
