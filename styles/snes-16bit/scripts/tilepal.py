"""Kachelpaletten nach SNES-Regeln: jede 8×8-Kachel einer 4bpp-Ebene nutzt genau eine von P Paletten mit je
15 Farben (+ Index 0 = transparent).

Vorgehen (k-means über Kacheln):
  * Alle Pixel sind schon auf eine gemeinsame Quellpalette (≤ 128 Farben, 5 Bit) gebracht; jede Kachel ist ein
    Histogramm über diese Farben.
  * Fehler(Kachel, Palette) = Σ Anzahl · Oklab-Abstand² zur nächsten Palettenfarbe. Jede Kachel nimmt die Palette
    mit dem kleinsten Fehler (erzwungene Kacheln behalten ihre Palette).
  * Neue Palettenfarben: gewichtetes k-means über die Quellfarben der zugeordneten Kacheln (Gewicht √Anzahl, damit
    kleine Lichter und Konturen nicht untergehen), danach wird jedes Zentrum auf die gewichtigste Quellfarbe seines
    Clusters gesetzt: Paletten bestehen nur aus Farben, die im Bild wirklich vorkommen.
  * Danach Tauschsuche (k-Medoids): jede Palettenfarbe wird probeweise gegen jede Quellfarbe der zugeordneten
    Kacheln getauscht, solange der gewichtete Fehler sinkt. Gewicht je Kachel und Farbe = Anzahl^GAMMA
    (GAMMA < 1): kleine, deutlich andere Farben (roter Streifen am Boot, Lichtkanten) zählen mehr als bei
    reinem Quadratfehler, große Flächen dominieren weniger.
  * Feste Einträge (animierte Lichter) belegen Plätze in einer bestimmten Palette und werden nur von markierten
    Pixeln benutzt.
"""
import numpy as np
from sneslib import kmeans, nearest

GAMMA = 0.45
DEXP = 1.0          # Fehler = (Abstand²)^DEXP; 1,5 (große Abweichungen stärker) brachte den rotbraunen Bootsstreifen nicht zurück und erhöhte den mittleren Fehler (0,0156 -> 0,0189)


def swap_refine(pal, W, dist, rounds=3):
    """pal: Indizes der Palettenfarben; W: (C,) Gewichte; dist: (C, C) Abstände². Greedy-Tausch."""
    pal = list(pal)
    cand = np.flatnonzero(W > 0)
    for _ in range(rounds):
        improved = False
        for s in range(len(pal)):
            others = [q for j, q in enumerate(pal) if j != s]
            dmin = dist[:, others].min(1) if others else np.full(len(W), 1e9)
            cur = W @ np.minimum(dmin, dist[:, pal[s]])
            newd = np.minimum(dmin[:, None], dist[:, cand])        # (C, K)
            errs = W @ newd
            k = int(np.argmin(errs))
            if errs[k] < cur - 1e-9 and cand[k] not in pal:
                pal[s] = int(cand[k])
                improved = True
        if not improved:
            break
    return np.array(sorted(set(pal)), dtype=int)


def tile_hist(lbl, valid, ncol, size=8):
    """lbl: (H, W) Quellfarbindex, valid: Maske der zu zählenden Pixel. -> (Kacheln, ncol), Kachel-Id je Pixel."""
    H, W = lbl.shape
    tw = (W + size - 1) // size
    ty, tx = np.mgrid[0:H, 0:W]
    tid = (ty // size) * tw + (tx // size)
    nt = ((H + size - 1) // size) * tw
    hist = np.zeros((nt, ncol))
    np.add.at(hist, (tid[valid], lbl[valid]), 1)
    return hist, tid


def optimise(hists, src_lab, npal, slots, forced=None, iters=25, seed=0, init=None, tile_w=None):
    """hists: (T, C) Histogramme; src_lab: (C, 3); slots: freie Plätze je Palette (Liste, len npal).
    forced: dict Kachel -> Palette; tile_w: Gewicht je Kachel (nach GAMMA). Gibt (Zuordnung T, Paletten als Liste von Quellfarb-Indizes) zurück."""
    T, C = hists.shape
    forced = forced or {}
    used = hists.sum(1) > 0
    hw = hists ** GAMMA
    if tile_w is not None:
        hw = hw * tile_w[:, None]            # wichtige Kacheln (Motiv) zählen mehrfach
    dist = ((src_lab[:, None, :] - src_lab[None]) ** 2).sum(-1) ** DEXP
    # Start: k-means über Kachel-Mittelwerte (Oklab) + Streuung
    mean = (hists @ src_lab) / np.maximum(hists.sum(1, keepdims=True), 1)
    var = (hists @ (src_lab ** 2)) / np.maximum(hists.sum(1, keepdims=True), 1) - mean ** 2
    feat = np.hstack([mean, np.sqrt(np.maximum(var, 0)) * 0.5])
    assign = np.full(T, -1)
    if init is not None:
        assign = np.where(used, np.maximum(init, 0), -1)
    else:
        cen = kmeans(feat[used], npal, iters=30, seed=seed)
        assign[used] = nearest(feat[used], cen)
    for t, p in forced.items():
        assign[t] = p
    pals = [None] * npal
    for it in range(iters):
        # Paletten neu bestimmen
        for p in range(npal):
            w = hists[assign == p].sum(0)
            idx = np.flatnonzero(w > 0)
            k = slots[p]
            if len(idx) == 0:
                pals[p] = np.array([], dtype=int)
                continue
            if len(idx) <= k:
                pals[p] = idx
                continue
            ww = np.sqrt(w[idx])
            init = None
            if pals[p] is not None and len(pals[p]) == k:
                init = src_lab[pals[p]]
            c = kmeans(src_lab[idx], k, iters=15, seed=seed + p, w=ww, init=init)
            lab = nearest(src_lab[idx], c)
            sel = []
            for j in range(k):
                m = np.flatnonzero(lab == j)
                if len(m):
                    sel.append(idx[m[np.argmax(w[idx[m]])]])
            pals[p] = swap_refine(np.unique(np.array(sel, dtype=int)), hw[assign == p].sum(0), dist)
        # Kacheln neu zuordnen
        D = np.full((C, npal), 1e9)
        for p in range(npal):
            if len(pals[p]):
                D[:, p] = dist[:, pals[p]].min(1)
        err = hw @ D
        new = np.where(used, err.argmin(1), -1)
        for t, p in forced.items():
            new[t] = p
        changed = int((new != assign).sum())
        assign = new
        if changed == 0 and it > 3:
            break
    optimise.last_error = float(sum(err[t, assign[t]] for t in range(T) if assign[t] >= 0))
    return assign, pals


def map_pixels(lbl, valid, tid, assign, pals, src_lab):
    """Je Pixel die nächste Farbe der Kachelpalette: gibt (Palette je Pixel, Slot je Pixel) zurück."""
    H, W = lbl.shape
    pal_px = np.full((H, W), -1)
    slot_px = np.full((H, W), -1)
    for p, pl in enumerate(pals):
        if not len(pl):
            continue
        m = valid & (assign[tid] == p)
        if not m.any():
            continue
        d = ((src_lab[lbl[m]][:, None, :] - src_lab[pl][None]) ** 2).sum(-1)
        pal_px[m] = p
        slot_px[m] = d.argmin(1)
    return pal_px, slot_px
