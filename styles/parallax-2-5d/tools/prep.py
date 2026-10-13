#!/usr/bin/env python3
"""Gemälde + KI-Tiefenkarte (+ KI-Platte) -> Relief-Daten für die Godot-Demo (drei Schichten).

    .venv/bin/python -I styles/parallax-2-5d/tools/prep.py [--plate=code]

Eingang:  assets/raw/bg.png (Gemälde 1536×1024), assets/raw/depth.png (Tiefenkarte von genimg, hell = nah),
          assets/raw/plate.png (KI-Platte: Gemälde ohne Gegenstände; fehlt sie oder --plate=code, nur Code-Füllung)
Ausgang (assets/scene/, Kopie nach demo/scene/):
  color.png            Gemälde (vordere Schicht)
  front_depth.png      Disparität der vorderen Schicht, 16 bit in R (hoch) und G (niedrig), B = Wassermaske,
                       A = 255 - Lampen-Nummer (1 Laterne, 2 Fenster, 3 Wandlampe, 4 Leuchtfeuer, 9 Sterne)
  front_vtx.png        Disparität der Gitterpunkte (769×513, alle 2 px; nächster Wert der 5×5-Umgebung an Kanten)
  back_color.png       hintere Schicht (saubere Platte): Himmel, Landzunge, Meer, Kai ohne Gegenstände
  back_color_code.png  dieselbe Platte nur aus Code (zeilenweise gespiegelte Fortsetzung), zum Vergleich
  back_depth.png       Disparität der Platte: analytische Ebenen (Himmel, Meer, Kai) bzw. Landzunge
  back_vtx.png         Gitterpunkte der Platte
  mid_color.png        mittlere Schicht (Zwischenfüllung): fernere Gegenstandsflächen hinter näheren fortgesetzt
  mid_depth.png        ihre Disparität (0 = keine Zwischenfüllung, dort verwirft der Shader)
  mid_vtx.png          Gitterpunkte der mittleren Schicht
  calib.json           Kameramodell, Kalibrierung, Raumpunkte der Lampen und des Schornsteins, Prüfwerte
  debug_*.png          Regionen, Disparität, Platte (zur Sichtprüfung)

Kameramodell: waagerechte Lochkamera mit verschobenem Hauptpunkt (Horizont = Zeile YH; senkrechte Linien im Gemälde
bleiben senkrecht). Brennweite F frei gewählt (45° senkrecht über 1024 Zeilen), Augenhöhe HQ über dem Kai.

Aufräumen der Tiefe (nach dem Einrasten an Farbkanten): Säume aus Zwischenwerten an starken Sprüngen, kleine
Segmente (< SMALL_PX), die stark von ihrer Umgebung abweichen, Inseln (< ISLAND_PX), die > 40 % näher liegen als alles
um sie herum, Verdeckungskanten um einen Texel nach außen; Zahlen in calib.json → cleanup.

Kalibrierung der KI-Tiefenkarte:
  * Kai: Für eine Bodenebene gilt Disparität ~ (y - YH). Die KI-Grauwerte des Kais folgen dagegen fast genau
    g = A·ln(y - YH) + B (logarithmische Tonung). A, B werden an den Zeilenmedianen des Kais angepasst; damit wird
    jeder Grauwert ≥ SEA_G auf eine Entfernung Z = HQ·F / exp((g - B)/A) abgebildet. Geprüft an Bodenkontakten
    von Laterne, Fässern, Häuschen und Booten (siehe calib.json → contacts).
  * Meer: Die KI tont das Meer viel flacher (eigene Skala). Es wird durch eine analytische Ebene HS unter dem Auge
    ersetzt; HS ist so gewählt, dass die Wasserlinie der Boote zu deren Entfernung aus der Kai-Kalibrierung passt.
  * Landzunge mit Leuchtturm: Entfernung aus ihrer Wasserlinie (je Spalte gemessen) auf der Meeresebene.
  * Himmel und ferne Inseln: Z_SKY.
"""
import json, pathlib, shutil, warnings
import numpy as np
from PIL import Image, ImageDraw

S = pathlib.Path(__file__).resolve().parent.parent
RAW = S / "assets/raw"
OUT = S / "assets/scene"
DEMO = S / "demo/scene"

F = 1236.0            # Brennweite in Quellpixeln (45° senkrecht über 1024 Zeilen)
CX = 768.0            # Hauptpunkt x (Bildmitte)
YH = 421.0            # Horizontzeile im Gemälde (gemessen: Übergang Himmel/Meer, Spalten 860–930)
YH_I = int(YH)
QUAY_EDGE_ANCHORS = [(1320, 618), (1535, 612)]   # (x, Zeile) der Kai-Kante rechts, am Gemälde abgelesen
PLATE_EDGE = [(0, 563), (100, 570), (200, 580), (300, 590), (400, 600), (500, 612)]   # Kai-Kante in der KI-Platte
AI_RIGHT_END = 1170   # rechts davon Code-Platte (KI hat dort die Mauerecke entfernt)
AI_BLEND = 3          # px: Überblendung Code-Füllung -> KI-Platte am Rand der verdeckten Fläche (vorher 10:
                      # schmale Dinge wie der Laternenpfahl blieben dann fast ganz Code-Füllung, Querstreifen)
import sys as _sys
PLATE_MODE = "code" if "--plate=code" in _sys.argv or not (pathlib.Path(__file__).resolve().parent.parent
                                                           / "assets/raw/plate.png").exists() else "ai"
HQ = 2.0              # Augenhöhe über dem Kai (m)
Z_SKY = 4000.0        # Himmel, ferne Inseln (m)
Z_MIN = 3.0           # nächste darstellbare Entfernung -> Disparität 1,0
SEA_G = 84            # Grauwerte darunter (unterhalb des Horizonts) gelten als Meer
GRID = 2              # Gitterabstand der Reliefpunkte in Quellpixeln
HEAD_X0 = 1100        # ab hier gehört alles Nicht-Himmel oberhalb der Wasserlinie zur Landzunge (links: Takelage)
RIG_ZONES = [(700, 250, 1110, 640)]   # Masten und Takelage der Boote (x0, y0, x1, y1): dort keine Inselregel
SMALL_PX = 50         # kleinere Tiefensegmente, die stark von ihrer Umgebung abweichen, gehen zur Nachbarfläche
ISLAND_PX = 300       # kleinere Inseln, die > 40 % näher liegen als alles um sie herum, werden gemeldet/angehängt
EDGE_PX = 3           # so viele Randtexel der ferneren Seite kommen zusätzlich in die mittlere Schicht
EXT_PX = 48           # höchstens so weit wird eine fernere Gegenstandsfläche hinter einer näheren fortgesetzt
CAM_END = np.array([0.3, -0.25, -0.9])   # Endpunkt der Kamerafahrt (wie main.gd), für die Breite der Zwischenfüllung


def sh(a, dy, dx, fill):
    """out[y, x] = a[y - dy, x - dx] (Rand mit fill)."""
    out = np.full_like(a, fill)
    H, W = a.shape[:2]
    ys, yd = (slice(0, H - dy), slice(dy, H)) if dy >= 0 else (slice(-dy, H), slice(0, H + dy))
    xs, xd = (slice(0, W - dx), slice(dx, W)) if dx >= 0 else (slice(-dx, W), slice(0, W + dx))
    out[yd, xd] = a[ys, xs]
    return out


def filt(a, r, fn, fill):
    o = a.copy()
    for d in range(1, r + 1):
        o = fn(o, fn(sh(a, 0, d, fill), sh(a, 0, -d, fill)))
    p = o.copy()
    for d in range(1, r + 1):
        p = fn(p, fn(sh(o, d, 0, fill), sh(o, -d, 0, fill)))
    return p


def fit_quay(g):
    """g = A·ln(y - YH) + B an den Zeilenmedianen des Kais (Spalten 100–1100, Zeilen 640–990)."""
    rows, med = [], []
    for y in range(640, 991, 10):
        v = g[y, 100:1100]
        v = v[v > 140]
        if len(v) > 400:
            rows.append(y)
            med.append(float(np.median(v)))
    lr = np.log(np.array(rows) - YH)
    A, B = np.polyfit(lr, med, 1)
    res = np.array(med) - (A * lr + B)
    return float(A), float(B), {"rows": rows, "median_g": med, "rms": float(np.sqrt((res ** 2).mean()))}


def z_quay(g, A, B):
    return HQ * F / np.exp((g - B) / A)


def resolve_flying(s, col, cand, r=3, jump=0.5, tol=0.1, iters=3):
    """Fliegende Pixel an starken Tiefensprüngen (Umfang im 7×7-Fenster > Faktor e^0,5): Ein Gegenstandspixel, dessen
    Disparität (log. Maß) mehr als tol von Minimum und Maximum des Fensters entfernt liegt, ist ein Saum aus
    Zwischenwerten (z. B. Ring um die Laterne in 24 m statt 11,7 m). Es geht per Farbvergleich zur nahen oder fernen
    Gruppe (Pixel innerhalb tol am Maximum bzw. Minimum) und erhält deren mittlere Disparität."""
    H, W = s.shape
    n_tot = 0
    for _ in range(iters):
        ls = np.log(s)
        mx = filt(ls, r, np.maximum, -np.inf)
        mn = filt(ls, r, np.minimum, np.inf)
        ys, xs = np.nonzero(cand & ((mx - mn) > jump) & ((mx - ls) > tol) & ((ls - mn) > tol))
        if len(ys) == 0:
            break
        mxk, mnk = mx[ys, xs], mn[ys, xs]
        K = len(ys)
        nn = np.zeros(K); nf = np.zeros(K); sn = np.zeros(K); sf = np.zeros(K)
        cn = np.zeros((K, 3)); cf = np.zeros((K, 3))
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                y2 = np.clip(ys + dy, 0, H - 1); x2 = np.clip(xs + dx, 0, W - 1)
                l2 = ls[y2, x2]; c2 = col[y2, x2]
                a = l2 > mxk - tol; b = l2 < mnk + tol
                nn += a; nf += b; sn += np.where(a, l2, 0); sf += np.where(b, l2, 0)
                cn += c2 * a[:, None]; cf += c2 * b[:, None]
        dn = np.linalg.norm(col[ys, xs] - cn / np.maximum(nn, 1)[:, None], axis=1)
        df = np.linalg.norm(col[ys, xs] - cf / np.maximum(nf, 1)[:, None], axis=1)
        s[ys, xs] = np.exp(np.where(dn <= df, sn / np.maximum(nn, 1), sf / np.maximum(nf, 1)))
        n_tot += K
    return s, n_tot


def label_segments(s, grp, rel=0.07):
    """4-zusammenhängende Tiefensegmente: gleiche Gruppe (0 Himmel/Ferne, 1 Landzunge, 2 Meer, 4 Gegenstand/Kai) und
    stetige Tiefe (Nachbarn weichen weniger als rel ab; beim Meer nur die Gruppe). Läufe je Zeile, dann
    Label-Weitergabe über die senkrechten Verbindungen."""
    def conn(a, b, ga, gb):
        # Meer nur nach Klasse (seine Ebene ändert sich am Horizont von Zeile zu Zeile um mehr als rel)
        return (ga == gb) & ((ga == 2) | (np.abs(a - b) < rel * np.maximum(a, b)))
    hc = conn(s[:, 1:], s[:, :-1], grp[:, 1:], grp[:, :-1])
    start = np.ones(s.shape, bool)
    start[:, 1:] = ~hc
    run = np.cumsum(start.ravel()).reshape(s.shape) - 1
    vc = conn(s[1:], s[:-1], grp[1:], grp[:-1])
    pairs = np.unique(np.stack([run[:-1][vc], run[1:][vc]], 1), axis=0)
    par = np.arange(int(run.max()) + 1)
    while True:
        old = par.copy()
        la, lb = par[pairs[:, 0]], par[pairs[:, 1]]
        m = np.minimum(la, lb)
        for k in (pairs[:, 0], pairs[:, 1], la, lb):
            np.minimum.at(par, k, m)
        while True:
            p2 = par[par]
            if (p2 == par).all():
                break
            par = p2
        if (par == old).all():
            break
    _, inv = np.unique(par[run], return_inverse=True)
    return inv.reshape(s.shape)


RING = [(0, 1), (0, -1), (1, 0), (-1, 0), (0, 2), (0, -2), (2, 0), (-2, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]


def seg_stats(s, col, grp, sel_size):
    """Segmente und ihre Nachbarn: für jedes Segment mit weniger als sel_size Pixeln die Ringpixel (bis 2 px) je
    Nachbarsegment: Anzahl, mittlere log-Disparität, mittlere Farbe."""
    lab = label_segments(s, grp)
    N = int(lab.max()) + 1
    size = np.bincount(lab.ravel(), minlength=N)
    ls = np.log(s)
    own_ls = np.bincount(lab.ravel(), weights=ls.ravel(), minlength=N) / np.maximum(size, 1)
    own_c = np.stack([np.bincount(lab.ravel(), weights=col[..., k].ravel(), minlength=N) for k in range(3)], 1) \
        / np.maximum(size, 1)[:, None]
    own_g = np.zeros(N, np.int64)
    own_g[lab.ravel()] = grp.ravel()
    sel = size < sel_size
    comps, nls, nl2, nc = [], [], [], []
    for dy, dx in RING:
        lb = sh(lab, dy, dx, -1)
        m = (lb >= 0) & (lb != lab) & sel[lab]
        comps.append(lab[m]); nls.append(lb[m]); nl2.append(sh(ls, dy, dx, 0.0)[m]); nc.append(sh(col, dy, dx, 0.0)[m])
    comps = np.concatenate(comps).astype(np.int64); nls = np.concatenate(nls).astype(np.int64)
    nl2 = np.concatenate(nl2); nc = np.concatenate(nc)
    uk, inv, cnt = np.unique(comps * N + nls, return_inverse=True, return_counts=True)
    m_ls = np.bincount(inv, weights=nl2) / cnt
    m_c = np.stack([np.bincount(inv, weights=nc[:, k]) for k in range(3)], 1) / cnt[:, None]
    nb = {}
    cu = uk // N
    cuts = np.nonzero(np.diff(cu))[0] + 1
    for a, b in zip(np.r_[0, cuts], np.r_[cuts, len(uk)]):
        nb[int(cu[a])] = [(int(uk[i] % N), int(cnt[i]), float(m_ls[i]), m_c[i]) for i in range(a, b)]
    return lab, size, own_ls, own_c, own_g, nb


def fix_small(s, col, grp, max_px=SMALL_PX, dev=0.15, cdist_far=45.0):
    """Kleine Tiefensegmente (< max_px), die mehr als dev von der Mehrheit ihrer Nachbarn abweichen (Löcher in
    Gegenständen, Krümel), gehen zu der Nachbarfläche (Anteil am Ring ≥ 15 %), deren Farbe ihrer eigenen am nächsten
    ist, und erhalten deren Disparität und Gruppe. Meer und Landzunge bleiben unberührt (analytische Flächen). Ein
    naher Krümel wird nur dann nach hinten geschoben, wenn er auch farblich zur ferneren Fläche passt (sonst ist er
    ein echtes Detail, z. B. ein Blatt)."""
    lab, size, own_ls, own_c, own_g, nb = seg_stats(s, col, grp, max_px)
    new_ls = np.full(len(size), np.nan); new_g = own_g.copy()
    rep = {"to_near": 0, "to_far": 0, "px": 0}
    for c, lst in nb.items():
        if own_g[c] not in (0, 4):
            continue
        tot = sum(n for _, n, _, _ in lst)
        maj = max(lst, key=lambda e: e[1])
        if abs(own_ls[c] - maj[2]) < np.log(1 + dev):
            continue
        cands = [e for e in lst if e[1] >= 0.15 * tot] or [maj]
        tgt = min(cands, key=lambda e: np.linalg.norm(own_c[c] - e[3]))
        if abs(own_ls[c] - tgt[2]) < np.log(1 + dev):
            continue
        if tgt[2] < own_ls[c] and np.linalg.norm(own_c[c] - tgt[3]) > cdist_far:
            continue
        new_ls[c] = tgt[2]; new_g[c] = own_g[tgt[0]]
        rep["to_near" if tgt[2] > own_ls[c] else "to_far"] += 1
        rep["px"] += int(size[c])
    m = np.isfinite(new_ls)[lab]
    s = np.where(m, np.exp(np.nan_to_num(new_ls)[lab]), s)
    grp = np.where(m, new_g[lab], grp)
    return s, grp, rep


def fix_islands(s, col, grp, max_px=ISLAND_PX, nearer=0.4):
    """Kleine Inseln (< max_px Gegenstandspixel), die mehr als 40 % näher liegen als jede Nachbarfläche (z. B.
    Turmspitze mit 22 m auf einem Leuchtturm in 67 m): außerhalb von Masten und Takelage an die nächstgelegene
    angrenzende Gegenstands- oder Landzungenfläche hängen; liegen sie nur vor Himmel oder Meer, bleiben sie (frei
    schwebendes Detail) und werden gemeldet."""
    lab, size, own_ls, own_c, own_g, nb = seg_stats(s, col, grp, max_px)
    H, W = s.shape
    ys, xs = np.mgrid[0:H, 0:W]
    cy = np.bincount(lab.ravel(), weights=ys.ravel()) / np.maximum(size, 1)
    cx = np.bincount(lab.ravel(), weights=xs.ravel()) / np.maximum(size, 1)
    new_ls = np.full(len(size), np.nan)
    rep = []
    for c, lst in nb.items():
        if own_g[c] != 4:
            continue
        if not all(own_ls[c] - e[2] > -np.log(1 - nearer) for e in lst):
            continue
        x, y = float(cx[c]), float(cy[c])
        if any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in RIG_ZONES):
            continue
        # angrenzende Gegenstands- oder Landzungenflächen, nicht solche mit Himmelstiefe (> 1000 m)
        att = [e for e in lst if own_g[e[0]] in (1, 4) and e[2] > np.log(Z_MIN / 1000.0)]
        item = {"x": round(x), "y": round(y), "px": int(size[c]), "z_m": round(float(Z_MIN / np.exp(own_ls[c])), 1)}
        if att:
            t = max(att, key=lambda e: e[2])
            new_ls[c] = t[2]
            item["z_new_m"] = round(float(Z_MIN / np.exp(t[2])), 1)
        rep.append(item)
    m = np.isfinite(new_ls)[lab]
    s = np.where(m, np.exp(np.nan_to_num(new_ls)[lab]), s)
    return s, rep


def dilate_near(s, grp, ratio=1.25):
    """Verdeckungskanten um einen Texel nach außen schieben: Ein Pixel neben einem deutlich näheren Gegenstandspixel
    (Sprung > 25 %) übernimmt dessen Disparität. Diese Randpixel sind im Gemälde Mischfarben aus Gegenstand und
    Hintergrund; als Teil des Hintergrunds blieben sie beim Fahren als Geisterlinie stehen (Fass, Laternenpfahl),
    so wandern sie als Kantenglättung mit dem Gegenstand, und die hintere Schicht zeigt dahinter saubere Fläche."""
    so = np.where(grp == 4, s, 0.0)
    mx = filt(so, 1, np.maximum, 0.0)
    m = mx > s * ratio
    return np.where(m, mx, s), np.where(m, 4, grp), int(m.sum())


def snap_mixed(s, col, grp, r=2, ratio=1.25, share=0.35):
    """Mischfarben im zweiten Ring: Ein Pixel bis 2 px neben einem deutlich näheren Gegenstand, dessen Farbe um mehr
    als 35 % des Abstands zwischen sauberer Hintergrund- und Gegenstandsfarbe von der Hintergrundfarbe abweicht
    (dunkle Dachkante im Himmel), wandert mit dem Gegenstand. Saubere Hintergrundfarbe: Mittel der Pixel gleicher
    Tiefe im 9×9-Fenster, die selbst nicht an einen Gegenstand grenzen; Gegenstandsfarbe: Mittel der nahen Pixel."""
    H, W = s.shape
    so = np.where(grp == 4, s, 0.0)
    mx = filt(so, r, np.maximum, 0.0)
    edge = mx > s * ratio
    ys, xs = np.nonzero(edge)
    if len(ys) == 0:
        return s, grp, 0
    K = len(ys)
    sk, mk = s[ys, xs], mx[ys, xs]
    cn = np.zeros((K, 3)); nn = np.zeros(K); cf = np.zeros((K, 3)); nf = np.zeros(K)
    for dy in range(-4, 5):
        for dx in range(-4, 5):
            y2 = np.clip(ys + dy, 0, H - 1); x2 = np.clip(xs + dx, 0, W - 1)
            s2 = s[y2, x2]; c2 = col[y2, x2]
            a = (np.abs(dy) <= r) & (np.abs(dx) <= r) & (s2 > mk / 1.1)
            b = (np.abs(s2 - sk) < 0.1 * sk) & ~edge[y2, x2]
            cn += c2 * a[:, None]; nn += a; cf += c2 * b[:, None]; nf += b
    ok = (nn > 0) & (nf > 0)
    cn = cn / np.maximum(nn, 1)[:, None]; cf = cf / np.maximum(nf, 1)[:, None]
    d_bg = np.linalg.norm(col[ys, xs] - cf, axis=1); d_nf = np.linalg.norm(cn - cf, axis=1)
    m = ok & (d_bg > share * d_nf) & (d_nf > 20)
    s = s.copy(); grp = grp.copy()
    s[ys[m], xs[m]] = mk[m]; grp[ys[m], xs[m]] = 4
    return s, grp, int(m.sum())


def shift_end(x, y, s):
    """Verschiebung (dx, dy) eines Bildpunkts (Quellpixel x, y, Disparität s) von der Gemälde-Kamera bis zum Ende
    der Fahrt (CAM_END wie in main.gd)."""
    Z = Z_MIN / s
    X, Y = (x - CX) * Z / F, -(y - YH) * Z / F
    zc = Z + CAM_END[2]
    return CX + F * (X - CAM_END[0]) / zc - x, YH - F * (Y - CAM_END[1]) / zc - y


def extend_far(s, col, objm, axis, E=EXT_PX, ratio=1.03, step=0.005, rel=0.07, off=2, min_run=4):
    """Zwischenfüllung für Lücken, deren fernere Seite selbst ein Gegenstand ist (Kiste vor Haustür, Fass vor
    Mauerstein): Die fernere Fläche wird zeilenweise (axis 1) bzw. spaltenweise (axis 0) hinter die nähere
    fortgesetzt, Farbe an ihr gespiegelt (2 px vom Rand weg, Saumpixel sind Mischfarben), Tiefe der ferneren Seite.
    Nur in die Richtung, in der sich bei der Fahrt eine Lücke öffnet, und nur so breit wie diese Lücke (aus dem
    Kameramodell, ×1,25 + 2 px, höchstens E); weiter gezogen, erschiene die fernere Fläche auch dort, wo hinter dem
    nahen Gegenstand Himmel liegt (Dach hinter Ranken). Sprung: Disparität > 3 % und > 0,005 größer (ungefähr ab da
    verwirft der Shader gestreckte Dreiecke). Sprünge und Läufe werden an der 3×3-Median-Tiefe gesucht
    (einzelne Ausreißer an der Kante unterbrächen sonst die Fortsetzung); sie läuft hinter allem weiter, was
    deutlich näher liegt als die fernere Fläche. Liefert Disparität, Farbe und Abstand zum Sprung."""
    if axis == 0:
        es, ec, ed = extend_far(s.T, col.transpose(1, 0, 2), objm.T, 2, E, ratio, step, rel, off, min_run)
        return es.T, ec.transpose(1, 0, 2), ed.T
    H, W = s.shape
    sm = np.nanmedian(np.stack([sh(s, dy, dx, np.nan) for dy in (-1, 0, 1) for dx in (-1, 0, 1)]), axis=0)
    es = np.full((H, W), np.nan); ec = np.zeros((H, W, 3)); ed = np.full((H, W), np.inf)
    cont = np.zeros((H, W), bool)                        # cont[y, x]: x und x + 1 gehören zur selben Fläche
    cont[:, :-1] = (np.abs(sm[:, 1:] - sm[:, :-1]) < rel * np.maximum(sm[:, 1:], sm[:, :-1])) & objm[:, 1:] & objm[:, :-1]
    idx = np.arange(W)[None, :].repeat(H, 0)
    first = np.ones((H, W), bool); first[:, 1:] = ~cont[:, :-1]
    rs = np.maximum.accumulate(np.where(first, idx, 0), axis=1)           # Anfang des Laufs
    re = np.flip(np.minimum.accumulate(np.flip(np.where(~cont, idx, W - 1), 1), axis=1), 1)   # Ende des Laufs
    both = objm[:, :-1] & objm[:, 1:]

    def gap(y, j, sn, sf):
        """Wie weit sich die fernere Seite bis zum Ende der Fahrt von der näheren entfernt (Richtung +j)."""
        px, py = (j, y) if axis == 1 else (y, j)
        dn, df = shift_end(px, py, sn), shift_end(px, py, sf)
        k = 0 if axis == 1 else 1
        return df[k] - dn[k]

    def put(y, xs, d, src, sv):
        upd = d < ed[y, xs]
        xs, d, src = xs[upd], d[upd], src[upd]
        es[y, xs] = sv if np.isscalar(sv) else sv[upd]; ec[y, xs] = col[y, src]; ed[y, xs] = d

    def bounce(d, L):
        mm = d % (2 * L)
        return np.where(mm < L, mm, 2 * L - 1 - mm)

    def length(gp):
        return int(min(E, np.ceil(1.25 * gp) + 2))
    # ferne Seite bei j + 1 (Fortsetzung zu kleineren j hinter die nahe Fläche): Lücke, wenn die ferne Seite wegläuft
    for y, j in zip(*np.nonzero(both & (sm[:, :-1] > sm[:, 1:] * ratio) & (sm[:, :-1] - sm[:, 1:] > step))):
        sf = sm[y, j + 1]
        # die ersten Texel der ferneren Seite selbst (Tiefe und Farbe wie vorn): die vordere Schicht verwirft sie an
        # der Kante (Gitterpunkte tragen dort die nahe Tiefe), sonst stünde dort die Platte (Himmel in der Hauswand)
        xe = np.arange(j + 1, min(re[y, j + 1], j + EDGE_PX) + 1)
        put(y, xe, np.zeros(len(xe)), xe, s[y, xe])
        gp = gap(y, j, sm[y, j], sf)
        f0, f1 = j + 1 + off, re[y, j + 1]
        L = f1 - f0 + 1
        if gp <= 0.5 or L < min_run:
            continue
        xs = np.arange(max(0, j - length(gp) + 1), j + 1)[::-1]
        ok = np.cumprod((sm[y, xs] > sf * ratio) & (sm[y, xs] - sf > step) & objm[y, xs]).astype(bool)   # hinter Näherem
        xs = xs[ok]
        d = j - xs
        put(y, xs, d, f0 + bounce(d, L), sf)
    # ferne Seite bei j (Fortsetzung zu größeren j)
    for y, j in zip(*np.nonzero(both & (sm[:, 1:] > sm[:, :-1] * ratio) & (sm[:, 1:] - sm[:, :-1] > step))):
        sf = sm[y, j]
        xe = np.arange(max(rs[y, j], j - EDGE_PX + 1), j + 1)
        put(y, xe, np.zeros(len(xe)), xe, s[y, xe])
        gp = -gap(y, j, sm[y, j + 1], sf)
        f1, f0 = j - off, rs[y, j]
        L = f1 - f0 + 1
        if gp <= 0.5 or L < min_run:
            continue
        xs = np.arange(j + 1, min(W - 1, j + length(gp)) + 1)
        ok = np.cumprod((sm[y, xs] > sf * ratio) & (sm[y, xs] - sf > step) & objm[y, xs]).astype(bool)
        xs = xs[ok]
        d = xs - (j + 1)
        put(y, xs, d, f1 - bounce(d, L), sf)
    return es, ec, ed


def enc16(s, mask, lamp=None):
    """R, G: Disparität 16 bit; B: Wassermaske; A: 255 - Lampen-Nummer (0 = keine Lampe)."""
    v = np.clip(np.round(s * 65535), 0, 65535).astype(np.uint32)
    a = np.full(s.shape, 255, np.uint8) if lamp is None else (255 - lamp).astype(np.uint8)
    return np.dstack([(v >> 8).astype(np.uint8), (v & 255).astype(np.uint8), (mask * 255).astype(np.uint8), a])


# Lichtquellen im Gemälde (Mitte, Suchradius in px), an hellen warmen Flecken gemessen; Nummer = Index + 1
LAMPS = [("lantern", (555, 357), 16), ("window", (84, 428), 34), ("walllamp", (280, 436), 14),
         ("lighthouse", (1348, 230), 7)]
CHIMNEY = (219, 197)                      # Oberkante der Schornsteinmitte (Rauchaustritt)


IMPORT = """[remap]

importer="texture"
type="CompressedTexture2D"

[params]

compress/mode=0
compress/high_quality=false
compress/lossy_quality=0.7
compress/hdr_compression=1
compress/normal_map=0
compress/channel_pack=0
mipmaps/generate={mip}
mipmaps/limit=-1
roughness/mode=0
roughness/src_normal=""
process/fix_alpha_border=false
process/premult_alpha=false
process/normal_map_invert_y=false
process/hdr_as_srgb=false
process/hdr_clamp_exposure=false
process/size_limit=0
detect_3d/compress_to=0
"""


def write_import(png, mip=False):
    """Verlustfrei, ohne VRAM-Kompression (auch bei Nutzung in 3D), Mipmaps nur für Farbbilder."""
    imp = png.with_name(png.name + ".import")
    if not imp.exists():
        imp.write_text(IMPORT.format(mip="true" if mip else "false"))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    col = np.asarray(Image.open(RAW / "bg.png").convert("RGB")).astype(np.float32)
    g = np.asarray(Image.open(RAW / "depth.png").convert("L")).astype(np.float32)
    H, W = g.shape
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    A, B, fitinfo = fit_quay(g)

    # --- Regionen ------------------------------------------------------------------------------------------
    # Landzunge: rechts, oberhalb ihrer Wasserlinie (je Spalte: stärkster Helligkeitsabfall nach unten, Zeile 440–495)
    water_line = np.full(W, -1.0)
    gs = filt(g, 1, np.minimum, 255)
    for x in range(1050, W):
        c = gs[440:496, x]
        dg = c[:-4] - c[4:]
        water_line[x] = 440 + int(np.argmax(dg)) + 2
    wl = water_line.copy()
    k = 15                                   # Wasserlinie glätten (Median über 31 Spalten)
    for x in range(1050, W):
        wl[x] = np.median(water_line[max(1050, x - k):min(W, x + k + 1)])
    head = (xx >= 1050) & (yy <= wl[None, :].clip(0)) & (g >= 30) & (g < 90)
    # Turmspitze, Schornstein des Wärterhauses u. Ä.: Die KI tont sie heller (g ≥ 90, also ≤ 23 m statt 62–81 m);
    # mit eigener Tiefe lösten sie sich beim Fahren ab und schwebten über Laterne und Dach. Alles Nicht-Himmel oberhalb
    # der Wasserlinie gehört zur Landzunge (rechts von HEAD_X0; links davon liegt die Takelage des rechten Boots).
    head_zone_x = (xx >= HEAD_X0) & (yy <= wl[None, :].clip(0))
    n_head_region = int((head_zone_x & (g >= 20) & ~head).sum())
    head |= head_zone_x & (g >= 20)
    head_zone = (xx >= 1050) & (yy <= wl[None, :].clip(0)) & (yy > 200)
    far = (yy <= YH + 2) & (g < 30) & ~head
    sea = (yy > YH) & (g < SEA_G) & ~head & ~far
    obj = ~(far | sea | head)

    # --- Entfernung je Pixel --------------------------------------------------------------------------------
    # Fugen und Pinselrillen im Kai (2–4 px breite dunkle Linien) per Schließen entfernen, nur unten im Bild
    gc = filt(filt(g, 2, np.maximum, 0), 2, np.minimum, 255)
    g_obj = np.where(yy > 560, gc, g)
    Z = np.empty_like(g)
    Z[obj] = z_quay(g_obj[obj], A, B)
    # Meeresebene: Höhe HS so, dass die Wasserlinie der Boote (Zeile ~618) zu ihrer Kai-Entfernung passt
    boat_g = float(np.median(g[560:600, 760:840]))
    z_boat = float(z_quay(np.array(boat_g), A, B))
    HS = z_boat * (618 - YH) / F
    r = np.maximum(yy - YH, 1e-3)
    Z[sea] = np.minimum(HS * F / r[sea], Z_SKY)
    z_head_col = np.where(wl > YH, HS * F / np.maximum(wl - YH, 1), Z_SKY)
    Z[head] = np.broadcast_to(z_head_col[None, :], Z.shape)[head]
    Z[far] = Z_SKY
    Z = np.clip(Z, Z_MIN, Z_SKY)
    s = Z_MIN / Z                                           # normierte Disparität (1 = Z_MIN)
    water = sea.astype(np.float32)
    s_raw = s.copy()

    # --- Tiefe aufräumen ------------------------------------------------------------------------------------
    # 1. Kanten an die Farbkanten des Gemäldes rasten: Die KI-Tiefenkarte hat weiche, 1–3 px breite Übergänge
    #    (Zwischenwerte = „fliegende Pixel“, die bei der Kamerafahrt als Saum in der Luft hängen). In jedem
    #    5×5-Fenster mit großem Tiefenumfang wird das Pixel der nahen oder fernen Gruppe zugeschlagen, deren
    #    mittlere Farbe seiner eigenen näher liegt, und erhält deren mittlere Disparität.
    r = 2
    smax = filt(s, r, np.maximum, -np.inf)
    smin = filt(s, r, np.minimum, np.inf)
    zone = (smax - smin) > 0.06 * smax + 0.002
    mid = 0.5 * (smax + smin)
    acc = {k: np.zeros_like(s) for k in ("nn", "nf", "sn", "sf")}
    cn = np.zeros_like(col); cf = np.zeros_like(col)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            ss = sh(s, dy, dx, np.nan)
            cc = sh(col, dy, dx, 0)
            near = np.nan_to_num(ss, nan=-1) > mid
            farg = np.nan_to_num(ss, nan=np.inf) <= mid
            acc["nn"] += near; acc["nf"] += farg
            acc["sn"] += np.where(near, ss, 0); acc["sf"] += np.where(farg, ss, 0)
            cn += cc * near[..., None]; cf += cc * farg[..., None]
    both = zone & (acc["nn"] > 0) & (acc["nf"] > 0)
    dn = np.linalg.norm(col - cn / np.maximum(acc["nn"], 1)[..., None], axis=2)
    df = np.linalg.norm(col - cf / np.maximum(acc["nf"], 1)[..., None], axis=2)
    snapped = np.where(dn <= df, acc["sn"] / np.maximum(acc["nn"], 1), acc["sf"] / np.maximum(acc["nf"], 1))
    s = np.where(both, snapped, s)
    n_snapped = int(both.sum())
    # Restliche Zwischenwerte (fliegende Pixel): liegt ein Pixel an einer Kante deutlich zwischen Minimum und
    # Maximum seiner 3×3-Umgebung, bekommt es den näheren Extremwert (im logarithmischen Maß).
    for _ in range(2):
        mx3 = filt(s, 1, np.maximum, -np.inf); mn3 = filt(s, 1, np.minimum, np.inf)
        ls, lmx, lmn = np.log(s), np.log(mx3), np.log(mn3)
        fly = ((lmx - lmn) > 0.15) & ((lmx - ls) > 0.06) & ((ls - lmn) > 0.06)
        s = np.where(fly, np.where(lmx - ls < ls - lmn, mx3, mn3), s)
    # 2. Rauschen innerhalb der Flächen glätten (kantenerhaltende Diffusion, nur Kai und Gegenstände): Die KI
    #    zeichnet Masten, Pfähle und Fasskanten mit schwankender Helligkeit; schon ±3 Grauwerte lassen einen
    #    Mast bei 0,5 m Kamerafahrt um mehrere Pixel zittern. Lineare Rampen (Bodenebenen) bleiben erhalten.
    for _ in range(80):
        a2 = s.copy(); n2 = np.ones_like(s)
        for dy, dx in [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]:
            ss = sh(s, dy, dx, np.nan)
            ok = obj & (np.abs(np.nan_to_num(ss, nan=1e9) - s) < 0.07 * s + 0.001)
            a2 += np.where(ok, ss, 0); n2 += ok
        s = np.where(obj, a2 / n2, s)
    # 3. Säume aus Zwischenwerten an starken Sprüngen (7×7), kleine abweichende Segmente, Inseln, Kante um 1 Texel
    s_head = np.broadcast_to((Z_MIN / z_head_col)[None, :], s.shape)

    def head_fix(s, grp):
        # Landzunge: alles, was dort näher als 50 m liegt (Turmspitze, Schornstein; auch durch das Einrasten an ihre
        # 22 m geratene Nachbarpixel), bekommt die Spaltentiefe der Landzunge
        m = head_zone_x & (s > Z_MIN / 50.0)
        return np.where(m, s_head, s), np.where(m, 1, grp), m
    grp = np.where(obj, 4, np.where(sea, 2, np.where(head, 1, 0)))
    s, grp, hf = head_fix(s, grp)
    obj = grp == 4; head = grp == 1
    s, n_fly7 = resolve_flying(s, col, obj | far)     # auch Himmelspixel, die beim Einrasten Zwischenwerte bekamen
    s, grp, small_rep = fix_small(s, col, grp)
    # Salz-und-Pfeffer in Gegenständen (Kiste an der Haustür: einzelne Pixel springen zwischen 11 und 15 m; jeder
    # Sprung wird beim Fahren zu einem kleinen Loch): 3×3-Median über die Gegenstandsnachbarn, zweimal. Stufen und
    # dünne Dinge vor Himmel bleiben erhalten (Himmel zählt nicht mit).
    n_med = 0
    for _ in range(2):
        ob = grp == 4
        stk = np.stack([sh(np.where(ob, s, np.nan), dy, dx, np.nan) for dy in (-1, 0, 1) for dx in (-1, 0, 1)])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)     # Pixel ohne Gegenstandsnachbarn: NaN, bleibt
            md = np.nanmedian(stk, axis=0)
        chg = ob & np.isfinite(md) & (np.abs(np.log(np.where(np.isfinite(md), md, s) / s)) > 0.05)
        n_med += int(chg.sum())
        s = np.where(chg, md, s)
    s, island_rep = fix_islands(s, col, grp)
    # Himmelstaschen: kleine Himmelsflächen zwischen Blättern, Ranken und Dachkante (innerhalb einer Schließung der
    # Gegenstandsmaske mit 7×7) blieben beim Fahren als Punktreihe stehen, weil ihre Gemäldefarbe nicht genau zur
    # Platte passt; sie wandern mit dem nächsten Gegenstand.
    solid = (s > Z_MIN / 1000.0)
    closed = filt(filt(solid.astype(np.float32), 3, np.maximum, 0.0), 3, np.minimum, 1.0) > 0.5
    pocket = closed & ~solid & (yy < YH)
    s = np.where(pocket, filt(np.where(solid, s, 0.0), 3, np.maximum, 0.0), s)
    grp = np.where(pocket, 4, grp)
    n_pocket = int(pocket.sum())
    s, grp, n_dil = dilate_near(s, grp)
    s, grp, n_mix = snap_mixed(s, col, grp)
    s, grp, hf2 = head_fix(s, grp)
    n_head_fix = int((hf | hf2).sum())
    # Klasse an die Tiefe anpassen: Himmel-, Meer- und Landzungenpixel, die durch das Einrasten die Tiefe eines
    # Gegenstands bekommen haben (Saumpixel am Laternenpfahl), gelten als Gegenstand; sonst behielte die Platte dort
    # die Mischfarbe des Gemäldes, und beim Fahren bliebe sie als Strich stehen.
    # Meer und Landzunge: nur deutlich nähere Pixel (Sprung > 25 %) werden Gegenstand; kleinere Abweichungen (das
    # Einrasten verschiebt am Horizont, wo sich die Meeresebene von Zeile zu Zeile stark ändert, einzelne Pixel)
    # bekommen wieder ihre Ebene, sonst entstünde dort ein Fleckenband aus Wasser- und Nicht-Wasser-Pixeln.
    sea_s = np.clip(Z_MIN * np.maximum(yy - YH, 1e-3) / (HS * F), Z_MIN / Z_SKY, 1)
    plane_s = np.select([grp == 0, grp == 1, grp == 2], [np.full(s.shape, Z_MIN / Z_SKY), s_head, sea_s], s)
    lr = np.log(s / plane_s)
    recls = ((grp == 0) & (np.abs(lr) > 0.1)) | (((grp == 1) | (grp == 2)) & (lr > np.log(1.25)))
    restore = ((grp == 1) | (grp == 2)) & ~recls
    s = np.where(restore, plane_s, s)
    grp = np.where(recls, 4, grp)
    far, head, sea, obj = grp == 0, grp == 1, grp == 2, grp == 4
    water = sea.astype(np.float32)

    # --- Hintere Schicht: saubere Hintergrundplatte --------------------------------------------------------
    # Hinter jedem Gegenstand liegt in dieser Szene eine von vier Flächen: Himmel/Ferne, Landzunge, Meer, Kai.
    # Die hintere Schicht ist das Gemälde ohne Gegenstände: jede Fläche mit ihrer Tiefe aus dem Kameramodell
    # (glatt, exakte Ebenen) und mit Farben, die zeilenweise aus den sichtbaren Pixeln derselben Fläche
    # fortgesetzt werden (Himmel, Meer und Kai sind waagerecht gebändert, der Horizont bleibt scharf).
    # Wo sich bei der Kamerafahrt hinter einer Kante eine Lücke öffnet, erscheint diese Platte.
    r_ = np.maximum(yy - YH, 1e-3)
    s_sky = Z_MIN / Z_SKY
    s_plane = {
        0: np.full(s.shape, s_sky),
        1: np.broadcast_to((Z_MIN / z_head_col)[None, :], s.shape).astype(np.float64),
        2: np.clip(Z_MIN * r_ / (HS * F), s_sky, 1),
        3: np.clip(Z_MIN * r_ / (HQ * F), s_sky, 1),
    }
    quayp = obj & (yy > YH + 5) & (np.abs(s - s_plane[3]) < 0.10 * s_plane[3])
    cls = np.full(s.shape, 4, np.int16)        # 0 Himmel/Ferne, 1 Landzunge, 2 Meer, 3 Kai, 4 Gegenstand
    cls[far] = 0; cls[head] = 1; cls[sea] = 2; cls[quayp] = 3
    idx = np.arange(W)[None, :].repeat(H, 0)
    rows = np.arange(H)[:, None].repeat(W, 1)

    def nearest(valid):
        """Index des nächsten gültigen Pixels links (≤ x) und rechts (≥ x) je Zeile; -1 bzw. W wenn keins."""
        li = np.maximum.accumulate(np.where(valid, idx, -1), axis=1)
        ri = np.flip(np.minimum.accumulate(np.flip(np.where(valid, idx, W), 1), axis=1), 1)
        return li, ri

    # Fläche hinter jedem Gegenstandspixel aus der Szenengeometrie: über dem Horizont Himmel (bzw. Landzunge in
    # deren Bereich), darunter Meer bis zur Kai-Kante, unterhalb der Kai-Kante der Kai. Die Kai-Kante (Grenze Meer ->
    # Kai, je Spalte gemessen, wo sie sichtbar ist) wird unter den Gegenständen waagerecht interpoliert.
    bnd = np.full(W, np.nan)
    for x in range(W):
        c = cls[:, x]
        w_ = np.nonzero(c == 2)[0]
        if len(w_):
            y0 = int(w_.max()) + 1                            # unter dem tiefsten Wasserpixel der Spalte …
            if y0 < H - 20 and (c[y0:y0 + 20] == 3).sum() >= 14:   # … beginnt der Kai: echte Kai-Kante
                bnd[x] = y0
    # Wo die Kante verdeckt ist (links hinter dem Häuschen, rechts hinter Fässern und Kisten), gilt die Kante der
    # KI-Platte (Stützpunkte an assets/raw/plate.png abgelesen; im sichtbaren Teil weicht sie 2–7 px von der
    # gemessenen Kante ab). Ohne KI-Platte: zwei Stützpunkte rechts am Gemälde.
    anchors = (PLATE_EDGE + QUAY_EDGE_ANCHORS) if PLATE_MODE == "ai" else QUAY_EDGE_ANCHORS
    measured = np.isfinite(bnd)
    for ax, ay in anchors:
        if not measured[max(0, ax - 25):ax + 26].any():
            bnd[ax] = ay
    ok = np.isfinite(bnd)
    xs_ = np.arange(W)
    bnd_i = np.interp(xs_, xs_[ok], bnd[ok]) if ok.any() else np.full(W, H)
    geo = np.where(yy <= YH, 0, np.where(yy < bnd_i[None, :], 2, 3))
    geo = np.where(head_zone & (yy <= YH + 60), 1, geo)
    plate = np.where(cls < 4, cls, geo)
    # (Kein Meer unter der sichtbaren Kai-Kante nötig: bei der Fahrt vor und abwärts deckt der Kai das Wasser
    # dahinter zu, gerechnet und in der Aufnahme geprüft.)

    # Farben der Platte: zeilenweise aus den sichtbaren Pixeln derselben Fläche. Quellen 2 px Abstand zu jeder
    # Kante (Saumpixel der Gegenstände sind Mischfarben). Gespiegelt an der Quelle und innerhalb ihres Laufs hin und
    # her (Pinselstruktur und Wellenbänder bleiben erhalten), von beiden Seiten nach Abstand gemischt.
    bc = col.copy()
    need = plate != cls
    for c in range(4):
        m = need & (plate == c)
        if not m.any():
            continue
        src_c = cls == c
        src_c = filt(src_c.astype(np.float32), 2, np.minimum, 0) > 0.5     # 2 px vom Rand weg
        l, r2 = nearest(src_c)
        hl, hr = l >= 0, r2 < W
        # Laufgrenzen der Quellen (für das Hin-und-her-Spiegeln)
        lb = np.maximum.accumulate(np.where(~src_c, idx, -1), axis=1)
        rb = np.flip(np.minimum.accumulate(np.flip(np.where(~src_c, idx, W), 1), axis=1), 1)
        lc = np.clip(l, 0, W - 1); rc = np.clip(r2, 0, W - 1)
        run_l = np.maximum(lc - lb[rows, lc], 1); run_r = np.maximum(rb[rows, rc] - rc, 1)

        def mirror(src, run, dist, direction):
            o = dist - 1
            per = 2 * run
            mm = np.mod(o, per)
            step = np.where(mm < run, mm, per - 1 - mm)
            return np.clip(src + direction * step, 0, W - 1)

        dl = np.abs(idx - l); dr = np.abs(r2 - idx)
        ml = mirror(lc, run_l, dl, -1); mr = mirror(rc, run_r, dr, 1)
        wr = np.where(hl & hr, dl / np.maximum(dl + dr, 1), np.where(hr, 1.0, 0.0)).astype(np.float32)
        fillc = col[rows, ml] * (1 - wr[..., None]) + col[rows, mr] * wr[..., None]
        ok = m & (hl | hr)
        bc[ok] = fillc[ok]
        rest = m & ~(hl | hr)                   # keine Fläche dieser Art in der Zeile: von oben/unten
        if rest.any():
            up = np.maximum.accumulate(np.where(src_c, rows, -1), axis=0)
            dn_ = np.flip(np.minimum.accumulate(np.flip(np.where(src_c, rows, H), 0), axis=0), 0)
            src_r = np.where(up >= 0, up, np.where(dn_ < H, dn_, rows))
            bc[rest] = col[np.clip(src_r, 0, H - 1), idx][rest]
    # leicht senkrecht weichzeichnen (σ = 1,5 px), nur innerhalb gefüllter Pixel derselben Fläche
    acc_c = bc * need[..., None]; acc_n = need.astype(np.float32)
    for dy in range(1, 5):
        wgt = float(np.exp(-0.5 * (dy / 1.5) ** 2))
        for sgn in (1, -1):
            m = sh(need, sgn * dy, 0, False) & need & (sh(plate, sgn * dy, 0, -1) == plate)
            acc_c += sh(bc, sgn * dy, 0, 0) * (m * wgt)[..., None]; acc_n += m * wgt
    bc = np.where(need[..., None], acc_c / np.maximum(acc_n, 1e-6)[..., None], bc)
    bc_code = bc.copy()
    if PLATE_MODE == "ai":
        # Farben aus der KI-Platte (deckungsgleich, am Himmel und an der Landzunge gemessen: Versatz 0 px). Zum Rand
        # der verdeckten Fläche hin in AI_BLEND px in die Code-Füllung überblenden, die dort exakt ans Gemälde anschließt.
        ai = np.asarray(Image.open(RAW / "plate.png").convert("RGB")).astype(np.float32)
        # Tonwerte lokal angleichen: Die KI malt Meer und Himmel minimal anders hell. Differenz der weichgezeichneten
        # Bilder (nur sichtbare, unverdeckte Pixel, normierte Faltung, Kasten 49 px zweimal) auf die KI-Platte legen.
        valid = (~need).astype(np.float32)

        def box(a, r=24):
            c = np.cumsum(np.cumsum(np.pad(a, ((r + 1, r), (r + 1, r)) + ((0, 0),) * (a.ndim - 2), mode="edge"),
                                    0), 1)
            return (c[2 * r + 1:, 2 * r + 1:] - c[:-2 * r - 1, 2 * r + 1:] - c[2 * r + 1:, :-2 * r - 1]
                    + c[:-2 * r - 1, :-2 * r - 1]) / (2 * r + 1) ** 2

        def nblur(img_, m):
            num, den = img_ * m[..., None], m
            for _ in range(2):
                num, den = box(num), box(den)
            return num / np.maximum(den, 1e-3)[..., None], den
        bo, den = nblur(col, valid)
        ba, _ = nblur(ai, valid)
        corr = np.where((den > 0.05)[..., None], bo - ba, 0)
        ai = np.clip(ai + corr, 0, 255)
        dist = np.zeros(s.shape, np.float32)
        m = need.copy()
        for k in range(1, AI_BLEND + 1):
            m = m & sh(m, 1, 0, False) & sh(m, -1, 0, False) & sh(m, 0, 1, False) & sh(m, 0, -1, False)
            dist += m
        # Rechts (Fässer, Kisten, Eckstein der Kaimauer) hat die KI auch die Steinblöcke der Mauerecke entfernt und
        # dort Wasser gemalt; hinter den Fässern läge dann eine Wasserlücke. Dort gilt die Code-Platte.
        right = np.clip((AI_RIGHT_END - xx) / 40.0, 0, 1)
        wgt = (np.clip(dist / float(AI_BLEND), 0, 1) * right)[..., None]
        bc = np.where(need[..., None], bc_code * (1 - wgt) + ai * wgt, bc)
    bs = np.select([plate == 0, plate == 1, plate == 2, plate == 3], [s_plane[0], s_plane[1], s_plane[2], s_plane[3]])
    # Zwischenfüllung (mittlere Schicht): Ist die fernere Seite eines Sprungs selbst ein Gegenstand (Haustür hinter
    # der Kiste, Mauerstein hinter dem Fass), zeigt die Lücke beim Fahren deren Fortsetzung statt Himmel und Meer der
    # Platte (die Platte kennt weder Haus noch Mauerecke). Eigene Schicht zwischen vorderer Schicht und Platte: in
    # die Platte eingesetzt, entstünden dort neue Tiefensprünge und über sie gespannte Schlieren.
    obj_solid = obj & (s > Z_MIN / 150.0)     # Gegenstandspixel mit Himmels- oder Zwischentiefe zählen nicht
    es, ec, ed = extend_far(s, col, obj_solid, 1)
    es2, ec2, ed2 = extend_far(s, col, obj_solid, 0)
    use2 = ed2 < ed
    es = np.where(use2, es2, es); ec = np.where(use2[..., None], ec2, ec)
    ext = np.isfinite(es)
    ms = np.where(ext, es, 0.0)
    bs = np.minimum(bs, s * 0.97)            # hintere Schicht immer mindestens 3 % hinter der vorderen
    bw = (plate == 2).astype(np.float32)
    band = need
    n_plate = {name: int((need & (plate == c)).sum()) for c, name in enumerate(("far", "head", "sea", "quay"))}

    # --- Gitterpunkte ---------------------------------------------------------------------------------------
    gw, gh = W // GRID + 1, H // GRID + 1

    def grid(a, fn, fill):
        p = np.pad(a, ((2, 2), (2, 2)), mode="edge")
        m = filt(p, 2, fn, fill)[2:-2, 2:-2]               # 5×5 um jeden Pixel
        ys = np.clip(np.arange(gh) * GRID, 0, H - 1)
        xs = np.clip(np.arange(gw) * GRID, 0, W - 1)
        return m[np.ix_(ys, xs)]

    # Gitterpunkte: eigener Wert, außer das nächste Pixel der 5×5-Umgebung liegt deutlich näher (dann gehört der
    # Punkt zur Kante eines nahen Gegenstands und bekommt dessen Tiefe; so haben dünne Dinge Geometrie, ohne dass
    # einzelne Ausreißer im Inneren eines Gegenstands Beulen machen)
    fmax = grid(s, np.maximum, -np.inf)
    fctr = s[np.ix_(np.clip(np.arange(gh) * GRID, 0, H - 1), np.clip(np.arange(gw) * GRID, 0, W - 1))]
    fv = np.where(fmax > fctr * 1.12, fmax, fctr)
    bv = bs[np.ix_(np.clip(np.arange(gh) * GRID, 0, H - 1), np.clip(np.arange(gw) * GRID, 0, W - 1))]
    wv = grid(water, np.maximum, 0)
    bwv = bw[np.ix_(np.clip(np.arange(gh) * GRID, 0, H - 1), np.clip(np.arange(gw) * GRID, 0, W - 1))]
    # mittlere Schicht: eigener Wert, sonst der nächste der 5×5-Umgebung, sonst (wird ohnehin verworfen) die Platte
    mmax = grid(ms, np.maximum, 0.0)
    mctr = ms[np.ix_(np.clip(np.arange(gh) * GRID, 0, H - 1), np.clip(np.arange(gw) * GRID, 0, W - 1))]
    mv = np.where(mmax > mctr * 1.12, mmax, mctr)
    mok = (mv > 0).astype(np.float32)      # Gitterpunkt mit echter Zwischenfüllung (Kanal B; sonst Dreieck verwerfen)
    mv = np.where(mv > 0, mv, bv)

    # --- Lampen: Maske (Nummer im Alphakanal) und Lage im Raum ---------------------------------------------
    lum = col.mean(2); warm = col[..., 0] - col[..., 2]
    lamp = np.zeros(s.shape, np.int32)
    points = {}
    for i, (name, (lx, ly), rad) in enumerate(LAMPS):
        near_ = (xx - lx) ** 2 + (yy - ly) ** 2 <= rad ** 2
        m = near_ & (lum > 115) & (warm > 35)
        lamp[m] = i + 1
        zl = float(np.median(Z_MIN / s[ly - 2:ly + 3, lx - 2:lx + 3]))
        points[name] = [round((lx - CX) * zl / F, 3), round(-(ly - YH) * zl / F, 3), round(-zl, 3)]
    zc = float(np.median(Z_MIN / s[CHIMNEY[1] + 4:CHIMNEY[1] + 12, CHIMNEY[0] - 6:CHIMNEY[0] + 6]))
    points["chimney"] = [round((CHIMNEY[0] - CX) * zc / F, 3), round(-(CHIMNEY[1] - YH) * zc / F, 3), round(-zc, 3)]
    lamp_px = {name: int((lamp == i + 1).sum()) for i, (name, _, _) in enumerate(LAMPS)}
    # Sterne: kleine helle Punkte im Himmel (um mehr als 45 Helligkeitsstufen über dem Median ihrer 9×9-Umgebung),
    # Nummer 9 in der Lampenmaske; der Shader lässt sie einzeln funkeln
    loc = np.stack([sh(lum, dy, dx, np.nan) for dy in range(-4, 5) for dx in range(-4, 5)])
    med = np.nanmedian(loc, axis=0)
    star = far & (yy < 330) & (lum - med > 45)
    star = filt(star.astype(np.float32), 1, np.maximum, 0) > 0.5
    lamp[star & (lamp == 0)] = 9
    lamp_px["stars"] = int(star.sum())

    # --- Schreiben ------------------------------------------------------------------------------------------
    Image.fromarray(col.astype(np.uint8)).save(OUT / "color.png")
    Image.fromarray(enc16(s, water, lamp)).save(OUT / "front_depth.png")
    Image.fromarray(enc16(fv, wv)).save(OUT / "front_vtx.png")
    Image.fromarray(np.clip(bc, 0, 255).astype(np.uint8)).save(OUT / "back_color.png")
    Image.fromarray(np.clip(bc_code, 0, 255).astype(np.uint8)).save(OUT / "back_color_code.png")
    Image.fromarray(enc16(bs, (bw > 0.5).astype(np.float32))).save(OUT / "back_depth.png")
    Image.fromarray(enc16(bv, (bwv > 0.5).astype(np.float32))).save(OUT / "back_vtx.png")
    # außerhalb der Zwischenfüllung die Plattenfarbe (wird verworfen, aber Mipmaps und lineare Filterung mischen sonst
    # Schwarz in die Ränder: dunkle Punkte)
    Image.fromarray(np.clip(np.where(ext[..., None], ec, bc), 0, 255).astype(np.uint8)).save(OUT / "mid_color.png")
    Image.fromarray(enc16(ms, np.zeros_like(ms))).save(OUT / "mid_depth.png")
    Image.fromarray(enc16(mv, mok)).save(OUT / "mid_vtx.png")

    # Debug-Bilder
    reg = np.zeros((H, W, 3)); reg[far] = [40, 40, 120]; reg[sea] = [0, 120, 160]; reg[head] = [160, 120, 0]
    reg[obj] = [200, 200, 200]
    Image.fromarray((0.5 * reg + 0.5 * col).astype(np.uint8)).save(OUT / "debug_regions.png")
    disp = np.sqrt(np.clip(s, 0, 1))
    Image.fromarray((disp * 255).astype(np.uint8)).save(OUT / "debug_disparity.png")
    bd = col * 0.45
    bd[band] = bc[band]
    Image.fromarray(bd.astype(np.uint8)).save(OUT / "debug_band.png")

    # Bodenkontakte prüfen: Entfernung des Objekts aus der Kalibrierung gegen die Kai-/Meeresebene an seinem Fuß
    def contact(name, box, base_row, plane_h):
        x0, x1, y0, y1 = box
        z_obj = float(np.median(Z[y0:y1, x0:x1]))
        z_pl = plane_h * F / (base_row - YH)
        return {"name": name, "z_obj": round(z_obj, 2), "z_ground": round(z_pl, 2),
                "ratio": round(z_obj / z_pl, 3)}

    contacts = [
        contact("Laternenpfahl unten", (500, 515, 560, 600), 615, HQ),
        contact("Häuschen Sockel", (30, 90, 560, 600), 600, HQ),
        contact("Fass links", (1180, 1240, 650, 800), 840, HQ),
        contact("Kiste vorn", (1320, 1480, 850, 950), 975, HQ),
        contact("Boot links (Rumpf)", (760, 840, 560, 600), 618, HS),
        contact("Boot rechts (Rumpf)", (990, 1120, 560, 600), 618, HS),
    ]
    calib = {
        "image": [W, H], "f": F, "cx": CX, "yh": YH, "hq": HQ, "hs": round(HS, 4), "z_sky": Z_SKY,
        "z_min": Z_MIN, "grid": GRID, "grid_size": [gw, gh],
        "quay_fit": {"A": round(A, 3), "B": round(B, 3), **{k: v for k, v in fitinfo.items() if k == "rms"}},
        "boat_g": boat_g, "z_boat": round(z_boat, 2),
        "headland_z": [round(float(z_head_col[1060]), 1), round(float(z_head_col[W - 1]), 1)],
        "share": {"far": round(float(far.mean()), 3), "sea": round(float(sea.mean()), 3),
                  "head": round(float(head.mean()), 3), "obj": round(float(obj.mean()), 3),
                  "plate_fill": round(float(band.mean()), 4)},
        "plate_mode": PLATE_MODE, "snapped_px": n_snapped, "back_plate_px": n_plate,
        "cleanup": {"headland_fix_px": n_head_region, "headland_fix_after_cleanup_px": n_head_fix, "flying_7x7_px": n_fly7, "small_segments": small_rep, "median_px": n_med,
                    "islands": island_rep, "sky_pockets_px": n_pocket, "edge_dilated_px": n_dil, "mixed_ring2_px": n_mix, "reclassified_px": int(recls.sum()), "object_ext_px": int(ext.sum())}, "quay_edge_measured": {int(x): int(bnd[x]) for x in range(0, W, 50) if np.isfinite(bnd[x])}, "quay_edge_used": {int(x): round(float(bnd_i[x]), 1) for x in range(0, W, 50)}, "points": points, "lamp_px": lamp_px,
        "contacts": contacts,
    }
    (OUT / "calib.json").write_text(json.dumps(calib, indent=1, ensure_ascii=False))
    print(json.dumps(calib, ensure_ascii=False))
    DEMO.mkdir(parents=True, exist_ok=True)
    for f in ("color.png", "front_depth.png", "front_vtx.png", "back_color.png", "back_depth.png",
              "back_vtx.png", "mid_color.png", "mid_depth.png", "mid_vtx.png", "calib.json"):
        shutil.copy2(OUT / f, DEMO / f)
        if f.endswith(".png"):
            write_import(DEMO / f, mip=f.endswith("color.png"))


if __name__ == "__main__":
    main()
