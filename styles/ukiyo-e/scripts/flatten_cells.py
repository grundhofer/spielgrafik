#!/usr/bin/env python3
"""Flache Farbflächen im KI-Druckbild: Zellen der Schlüsselkontur einzeln füllen (Modul für build_bg.py).

Das Bildmodell hat Kaimauer, Pflaster, Hausmauer und Felsen gesprenkelt bzw. mit Licht- und Schattenflächen
gemalt. Im Holzschnitt ist jede Fläche, die von der Kontur des Schlüsselstocks umschlossen ist, mit einem Farbstock
flach gedruckt. Ablauf (in KI-Auflösung, vor dem Verkleinern):
  1. Schutz = Schlüsselkontur (RGB-Summe < 110) oder feine dunkle Linien (Summe mehr als LINE_D unter beiden
     Nachbarn im Abstand 2 oder 3 px, waagerecht oder senkrecht, z. B. Plattenfugen); Schutzflecken unter SPECK px
     (Sprenkel) zählen nicht als Schutz.
  2. Zellen = zusammenhängende ungeschützte Flächen innerhalb der Bearbeitungsbereiche (Rechtecke + Farbregel).
  3. Je Zelle: Helligkeit innerhalb der Zelle stark geglättet (Kastenfilter, nur Zellpixel). Ist der Umfang
     (p90 - p10) klein, wird die Zelle mit ihrer Medianfarbe gefüllt; sonst in 2 Töne (Felsen bis 3) geteilt
     (Schwellen auf der geglätteten Helligkeit), jeder Ton = Medianfarbe seiner Pixel.
  4. Felsen: zusätzlich eine Bokashi-Kante: das untere Drittel jeder Felszelle läuft zur Unterkante dunkler aus.
  5. Geschützte Pixel (Kontur, Fugen) bleiben unverändert; ihr 1-px-Saum (Kantenglättung) wird um dieselbe
     Farbverschiebung wie die Zelle versetzt, damit keine gesprenkelten Ränder stehen bleiben.
"""
import numpy as np

KEY_SUM = 110
LINE_D = 45          # Fuge: Summe mindestens so viel dunkler als beide Nachbarn im Abstand 2 bzw. 3 px (quer zur Linie)
SPECK = 14           # Schutzflecken kleiner als das gelten als Sprenkel


def box(a, r):
    """Kastenfilter (2r+1) über die letzten beiden Achsen, Randpixel wiederholt."""
    p = np.pad(a, ((r + 1, r), (r + 1, r)), mode="edge").astype(np.float64)
    c = p.cumsum(0).cumsum(1)
    k = 2 * r + 1
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)


def label(b):
    """Zusammenhangsflächen (4er-Nachbarschaft) per Min-Label-Ausbreitung mit Zeigersprung. 0 = Hintergrund."""
    h, w = b.shape
    lab = np.where(b, np.arange(1, h * w + 1).reshape(h, w), 0).astype(np.int64)
    big = h * w + 10
    while True:
        old = lab
        m = np.where(lab > 0, lab, big)
        n = m.copy()
        n[1:] = np.minimum(n[1:], m[:-1])
        n[:-1] = np.minimum(n[:-1], m[1:])
        n[:, 1:] = np.minimum(n[:, 1:], m[:, :-1])
        n[:, :-1] = np.minimum(n[:, :-1], m[:, 1:])
        n = np.where(b, n, 0)
        # Zeigersprung: Label auf das Label des Pixels zeigen lassen, dessen Nummer es trägt
        flat = n.ravel()
        idx = np.where(flat > 0, flat - 1, 0)
        jumped = np.where(flat > 0, np.minimum(flat, np.where(b.ravel()[idx], flat.reshape(-1)[idx], big)), 0)
        lab = jumped.reshape(h, w)
        if np.array_equal(lab, old):
            break
    # fortlaufend nummerieren
    u, inv = np.unique(lab, return_inverse=True)
    return inv.reshape(h, w), len(u) - 1


def flatten(img, region, rock, keep_cell=None, verbose=True):
    """img: HxWx3 uint8 (KI-Auflösung). region: bool HxW, Bereiche, die geglättet werden dürfen.
    rock: bool HxW, Teilbereich, in dem bis zu 3 Töne und eine Bokashi-Kante erlaubt sind.
    keep_cell: optional f(Medianfarbe, Felsbereich?) -> True, wenn die Zelle unverändert bleiben soll (z. B. Himmel).
    Gibt (neues Bild, Statistik) zurück."""
    a = img.astype(np.float64)
    S = a.sum(-1)
    key = S < KEY_SUM
    line = np.zeros(S.shape, bool)
    for d in (2, 3):
        for ax in (0, 1):
            nb = np.minimum(np.roll(S, d, ax), np.roll(S, -d, ax))
            line |= S < nb - LINE_D
    prot = key | line
    plab, pn = label(prot)
    psz = np.bincount(plab.ravel())
    small = (psz < SPECK)
    small[0] = False
    prot = prot & ~small[plab]
    cells = region & ~prot
    lab, n = label(cells)
    out = a.copy()
    shift = np.zeros_like(a)
    stats = {"cells": 0, "one": 0, "two": 0, "three": 0, "std_before": [], "std_after": [], "px": 0}
    ys_all, xs_all = np.nonzero(lab)
    order = np.argsort(lab[ys_all, xs_all], kind="stable")
    ys_all, xs_all = ys_all[order], xs_all[order]
    bounds = np.searchsorted(lab[ys_all, xs_all], np.arange(1, n + 2))
    for i in range(1, n + 1):
        ys, xs = ys_all[bounds[i - 1]:bounds[i]], xs_all[bounds[i - 1]:bounds[i]]
        if len(ys) == 0:
            continue
        col = a[ys, xs]
        is_rock = rock[ys, xs].mean() > 0.5
        if keep_cell is not None and keep_cell(np.median(col, 0), is_rock):
            continue
        stats["cells"] += 1
        stats["px"] += len(ys)
        lum = col @ np.array([0.299, 0.587, 0.114])
        if len(ys) < 60:
            tone = np.zeros(len(ys), int)
            k = 1
        else:
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            m = np.zeros((y1 - y0, x1 - x0))
            m[ys - y0, xs - x0] = 1
            L = np.zeros_like(m)
            L[ys - y0, xs - x0] = lum
            r = max(3, min(9, int(np.sqrt(len(ys)) / 6)))
            Lb = box(box(L * m, r), r) / np.maximum(box(box(m, r), r), 1e-6)
            lb = Lb[ys - y0, xs - x0]
            spread = np.percentile(lb, 90) - np.percentile(lb, 10)
            if spread < (16 if not is_rock else 12):
                tone = np.zeros(len(ys), int)
                k = 1
            else:
                k = 3 if (is_rock and spread > 40) else 2
                qs = np.percentile(lb, np.linspace(0, 100, k + 1)[1:-1]) if k == 3 else [otsu(lb)]
                tone = np.digitize(lb, qs)
        flat = np.zeros_like(col)
        for t in range(k):
            sel = tone == t
            if sel.any():
                flat[sel] = np.median(col[sel], 0)
        if is_rock and k >= 2 and len(ys) >= 200:
            # Bokashi-Kante: das untere Drittel der Zelle läuft zur Unterkante bis 16 % dunkler aus (waagerechtes Band)
            y_lo, y_hi = ys.min(), ys.max()
            band = max(6.0, 0.35 * (y_hi - y_lo))
            fac = 1 - 0.16 * np.clip((ys - (y_hi - band)) / band, 0, 1)
            flat *= fac[:, None]
        stats[{1: "one", 2: "two", 3: "three"}[k]] += 1
        stats["std_before"].append(float(col.std(0).mean()) * len(ys))
        stats["std_after"].append(float(flat.std(0).mean()) * len(ys))
        out[ys, xs] = flat
        shift[ys, xs] = flat - col.mean(0)
    # Saum der geschützten Pixel (1 px) innerhalb der Bereiche: um die mittlere Verschiebung der Nachbarzellen
    ring = prot & region & ~key
    nb = np.zeros_like(a)
    cnt = np.zeros(S.shape)
    cm = cells.astype(np.float64)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nb += np.roll(np.roll(shift * cm[..., None], dy, 0), dx, 1)
        cnt += np.roll(np.roll(cm, dy, 0), dx, 1)
    rr = ring & (cnt > 0)
    out[rr] = a[rr] + nb[rr] / cnt[rr][:, None]
    tot = max(1, stats["px"])
    stats["std_before"] = round(sum(stats["std_before"]) / tot, 2)
    stats["std_after"] = round(sum(stats["std_after"]) / tot, 2)
    if verbose:
        print("   Zellen", stats)
    return np.clip(out + 0.5, 0, 255).astype(np.uint8), stats


def otsu(v):
    h, e = np.histogram(v, 64)
    c = (e[:-1] + e[1:]) / 2
    w0 = np.cumsum(h)
    w1 = w0[-1] - w0
    m0 = np.cumsum(h * c) / np.maximum(w0, 1)
    m1 = (np.sum(h * c) - np.cumsum(h * c)) / np.maximum(w1, 1)
    j = np.argmax(w0 * w1 * (m0 - m1) ** 2)
    return c[j]
