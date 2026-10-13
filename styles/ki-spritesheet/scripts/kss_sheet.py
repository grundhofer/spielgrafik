"""Gemeinsame Hilfen für ki-spritesheet: Blätter zerlegen, Kopf und Füße messen, ausrichten.

Nur NumPy und Pillow. Koordinaten immer in Pixeln des KI-Blatts (Quellmaß), bis ausdrücklich skaliert wird.
"""
from collections import deque

import numpy as np
from PIL import Image

ALPHA = 24  # ab diesem Alphawert zählt ein Pixel zur Figur


def label(mask):
    """Zusammenhangskomponenten (8er-Nachbarschaft) per Breitensuche; gibt (labels, n) zurück."""
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    n = 0
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys.tolist(), xs.tolist()):
        if lab[y0, x0]:
            continue
        n += 1
        lab[y0, x0] = n
        q = deque([(y0, x0)])
        while q:
            y, x = q.popleft()
            for yy in (y - 1, y, y + 1):
                if yy < 0 or yy >= h:
                    continue
                row = mask[yy]
                lrow = lab[yy]
                for xx in (x - 1, x, x + 1):
                    if 0 <= xx < w and row[xx] and not lrow[xx]:
                        lrow[xx] = n
                        q.append((yy, xx))
    return lab, n


def split_frames(path, n, alpha=ALPHA):
    """Zerlegt ein Blatt in n Figuren über Zusammenhangskomponenten des Alphakanals.

    Spalten reichen nicht: Schalenden ragen in die Spalten des Nachbarbilds. Kleine Splitter (Fransen, Krümel)
    gehen an die nächstgelegene große Komponente. Gibt eine Liste von dicts zurück:
    {img: RGBA-Ausschnitt nur mit den eigenen Pixeln, x0, y0: Lage im Blatt, mask}.
    """
    sheet = np.asarray(Image.open(path).convert("RGBA"))
    mask = sheet[..., 3] > alpha
    lab, k = label(mask)
    sizes = np.bincount(lab.ravel(), minlength=k + 1)
    sizes[0] = 0
    big = list(np.argsort(sizes)[::-1][:n])
    if sizes[big[-1]] < 0.2 * sizes[big[0]]:
        # Figuren berühren sich (z. B. zwei erhobene Pfoten): Maske schrittweise erodieren, bis n große
        # Komponenten entstehen, dann die Etiketten innerhalb der Originalmaske zurückwachsen lassen.
        lab, k = touching_split(mask, n)
        sizes = np.bincount(lab.ravel(), minlength=k + 1)
        sizes[0] = 0
        big = list(np.argsort(sizes)[::-1][:n])
    boxes = {}
    for b in big:
        ys, xs = np.nonzero(lab == b)
        boxes[b] = (xs.min(), ys.min(), xs.max(), ys.max())
    owner = np.zeros(k + 1, np.int32)
    for b in big:
        owner[b] = b
    for c in range(1, k + 1):
        if owner[c] or not sizes[c]:
            continue
        ys, xs = np.nonzero(lab == c)
        cx, cy = xs.mean(), ys.mean()

        def dist(b):
            x0, y0, x1, y1 = boxes[b]
            return max(x0 - cx, 0, cx - x1) + max(y0 - cy, 0, cy - y1)
        owner[c] = min(big, key=dist)
    frames = []
    for b in sorted(big, key=lambda b: boxes[b][0]):
        own = owner[lab] == b
        ys, xs = np.nonzero(own)
        x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
        crop = sheet[y0:y1, x0:x1].copy()
        crop[..., 3] = np.where(own[y0:y1, x0:x1], crop[..., 3], 0)
        frames.append({"img": crop, "x0": int(x0), "y0": int(y0), "mask": crop[..., 3] > alpha})
    return frames


def _erode(m):
    e = m.copy()
    e[1:] &= m[:-1]; e[:-1] &= m[1:]; e[:, 1:] &= m[:, :-1]; e[:, :-1] &= m[:, 1:]
    return e


def touching_split(mask, n, max_iter=12):
    """Trennt sich berührende Figuren: erodieren bis n große Kerne, dann Kerne in der Maske zurückwachsen."""
    e = mask.copy()
    for it in range(1, max_iter + 1):
        e = _erode(e)
        lab, k = label(e)
        sizes = np.bincount(lab.ravel(), minlength=k + 1)
        sizes[0] = 0
        order = np.argsort(sizes)[::-1]
        if k >= n and sizes[order[n - 1]] > 0.2 * sizes[order[0]]:
            break
    else:
        raise SystemExit(f"Figuren lassen sich nicht trennen ({n} erwartet)")
    keep = np.zeros(k + 1, np.int32)
    for j, c in enumerate(order[:n]):
        keep[c] = j + 1
    cur = keep[lab]
    # zurückwachsen: je Schritt freie Maskenpixel neben einem Etikett übernehmen
    for _ in range(it + 40):
        free = mask & (cur == 0)
        if not free.any():
            break
        grow = np.zeros_like(cur)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sh = np.roll(np.roll(cur, dy, 0), dx, 1)
            grow = np.where((grow == 0) & (sh > 0), sh, grow)
        cur = np.where(free & (grow > 0), grow, cur)
    # Reste (nicht erreichbare Krümel) als eigene kleine Komponenten anhängen
    rest = mask & (cur == 0)
    if rest.any():
        rl, rk = label(rest)
        cur = np.where(rl > 0, rl + n, cur)
        return cur, n + rk
    return cur, n


def ncc_shift(a, b, mask_a, search=24):
    """Verschiebung (dx, dy) von Bild b gegen a, die den Ausschnitt a (nur Pixel in mask_a) am besten trifft.

    a, b: Grauwert-Arrays gleicher Größe (b darf größer sein). Rückgabe: (dx, dy, Korrelation)."""
    h, w = a.shape
    av = a[mask_a].astype(np.float64)
    av = (av - av.mean()) / (av.std() + 1e-6)
    best = (0, 0, -2.0)
    for dy in range(-search, search + 1):
        for dx in range(-search, search + 1):
            ys0, xs0 = max(0, -dy), max(0, -dx)
            ys1, xs1 = min(h, b.shape[0] - dy), min(w, b.shape[1] - dx)
            if ys1 - ys0 < h * 0.6 or xs1 - xs0 < w * 0.6:
                continue
            m = np.zeros_like(mask_a)
            m[ys0:ys1, xs0:xs1] = mask_a[ys0:ys1, xs0:xs1]
            if m.sum() < 0.6 * mask_a.sum():
                continue
            bb = np.zeros_like(a, dtype=np.float64)
            bb[ys0:ys1, xs0:xs1] = b[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx]
            av2 = a[m].astype(np.float64)
            bv = bb[m]
            av2 = (av2 - av2.mean()) / (av2.std() + 1e-6)
            bv = (bv - bv.mean()) / (bv.std() + 1e-6)
            c = float((av2 * bv).mean())
            if c > best[2]:
                best = (dx, dy, c)
    return best


def gray(rgba):
    rgb = rgba[..., :3].astype(np.float64)
    g = rgb @ np.array([0.299, 0.587, 0.114])
    return np.where(rgba[..., 3] > ALPHA, g, 0.0)


def feet(mask, band=6):
    """Bodenläufe: in den untersten `band` Zeilen über der tiefsten Zeile die zusammenhängenden x-Bereiche.

    Gibt (baseline_y, [(x_start, x_end), ...]) im Bildkoordinatensystem des Ausschnitts zurück."""
    ys = np.flatnonzero(mask.any(1))
    base = int(ys[-1])
    cols = mask[max(0, base - band + 1):base + 1].any(0)
    idx = np.flatnonzero(cols)
    runs = []
    if idx.size:
        s = p = idx[0]
        for i in idx[1:]:
            if i - p > 2:
                runs.append((int(s), int(p) + 1))
                s = i
            p = i
        runs.append((int(s), int(p) + 1))
    return base, runs


def sole_rows(mask, base, height=40):
    """Für jede Spalte die tiefste Figurzeile (Sohlenprofil) im unteren Streifen; -1, wo nichts ist."""
    h, w = mask.shape
    prof = np.full(w, -1)
    sub = mask[max(0, base - height):base + 1]
    has = sub.any(0)
    last = sub.shape[0] - 1 - np.argmax(sub[::-1], axis=0)
    prof[has] = last[has] + max(0, base - height)
    return prof


def snout_tip(mask, upper=0.45):
    """Rechtester Figurpixel im oberen Teil (Schnauze bei Blick nach rechts): (x, y)."""
    ys = np.flatnonzero(mask.any(1))
    top, bot = ys[0], ys[-1]
    lim = int(top + upper * (bot - top))
    sub = mask[top:lim]
    xs = np.flatnonzero(sub.any(0))
    x = int(xs[-1])
    yy = np.flatnonzero(sub[:, x])
    return x, int(top + yy.mean())


def head_anchors(frames, ref=0, box=(-150, -70, 10, 40), search=14, tip_upper=0.45):
    """Kopfanker je Bild: Lage (x, y) im Bildausschnitt, die dem Anker des Referenzbilds entspricht.

    Startwert ist die Schnauzenspitze; verfeinert per normierter Kreuzkorrelation des Kopfausschnitts
    (box = links, oben, rechts, unten relativ zur Schnauzenspitze des Referenzbilds) in ±search px.
    Gibt [(x, y, korrelation), ...] zurück; für ref ist es die Schnauzenspitze selbst."""
    rf = frames[ref]
    rx, ry = snout_tip(rf["mask"], tip_upper)
    g0 = gray(rf["img"])
    x0, y0, x1, y1 = rx + box[0], ry + box[1], rx + box[2], ry + box[3]
    pad = 200
    G0 = np.pad(g0, pad)
    M0 = np.pad(rf["mask"], pad)
    T = G0[y0 + pad:y1 + pad, x0 + pad:x1 + pad]
    TM = M0[y0 + pad:y1 + pad, x0 + pad:x1 + pad]
    out = []
    for f in frames:
        sx, sy = snout_tip(f["mask"], tip_upper)
        G = np.pad(gray(f["img"]), pad)
        best = (0, 0, -2.0)
        tv = T[TM]
        tv = (tv - tv.mean()) / (tv.std() + 1e-6)
        for dy in range(-search, search + 1):
            for dx in range(-search, search + 1):
                X0, Y0 = sx + box[0] + dx + pad, sy + box[1] + dy + pad
                W = G[Y0:Y0 + T.shape[0], X0:X0 + T.shape[1]]
                if W.shape != T.shape:
                    continue
                wv = W[TM]
                wv = (wv - wv.mean()) / (wv.std() + 1e-6)
                c = float((tv * wv).mean())
                if c > best[2]:
                    best = (dx, dy, c)
        out.append((sx + best[0], sy + best[1], round(best[2], 3)))
    return out


def scaled(frame, s):
    """Bild (dict aus split_frames) mit Lanczos (vormultipliziert) um s skalieren; gibt neues dict zurück."""
    im = frame["img"]
    h, w = im.shape[:2]
    nw, nh = max(1, round(w * s)), max(1, round(h * s))
    pm = Image.fromarray(im, "RGBA").convert("RGBa").resize((nw, nh), Image.LANCZOS).convert("RGBA")
    arr = np.asarray(pm).copy()
    return {"img": arr, "x0": frame["x0"], "y0": frame["y0"], "mask": arr[..., 3] > ALPHA}


def head_scale(ref, frame, lo=0.55, hi=1.1, step=0.01, **kw):
    """Maßstab s, mit dem `frame` skaliert werden muss, damit sein Kopf dem Kopf von `ref` gleicht (NCC)."""
    best = (1.0, -2.0)
    s = lo
    while s <= hi + 1e-9:
        f = scaled(frame, s)
        a = head_anchors([ref, f], 0, search=8, **kw)[1]
        if a[2] > best[1]:
            best = (round(s, 3), a[2])
        s += step
    return best
