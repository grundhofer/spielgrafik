#!/usr/bin/env python3
"""Lasiert einen KI-Figurenbogen in Quellauflösung neu als transparentes Aquarell (Prüfung 1: Codex malt die Figur
deckend mit Fell-, Filz- und Strickstruktur und weicher, rundplastischer Schattierung, auch mit ausdrücklichem
Verbot und Stilreferenz).

Vorgehen je Bogen (alle Figuren auf einmal, damit Farben und Schwellen in allen Bildern gleich sind):
  1. Material je Pixel: Farbgruppen (k-means in Lab) werden über ihre Farbe den Kostümteilen zugeordnet (Fell dunkel,
     Fell/Hemd hell, Grün, Rot, Leder, Paket, Messing); danach Mehrheitsentscheid in der Umgebung (aus Fellhaaren
     und Strickmaschen werden ruhige Flächen).
  2. Je Material eine flache Lasur in der hellen Eigenfarbe und höchstens eine zweite, hart begrenzte Lasur für die
     Schattenseite. Die Schattenform kommt aus der stark geglätteten Helligkeit des KI-Bildes (eine Schwelle je
     Material, Rand mit Rauschen verbogen): aus dem weichen 3D-Verlauf wird eine Kante, keine Höhenlinien.
  3. Papierweiß: helles Fell und Hemd bleiben fast Papier, die hellsten Stellen jedes Materials werden ausgehoben.
  4. Trockenränder: Jede Lasur bekommt innen an ihrer Kante mehr Pigment; an manchen Materialgrenzen bleibt ein
     schmaler Spalt Papier stehen. Leichte Wolkigkeit innerhalb der Lasur und Granulation (dunkle Farben stärker).
  5. Augen, Nase, Mund und Knöpfe bleiben aus dem KI-Bild (starke dunkle Einzelheiten und Messing), damit das
     Gesicht lesbar bleibt (der verworfene Filterversuch hatte sie verwischt).

Pigmentmodell aus wc.py: Dichten addieren, Ergebnis = Papier × exp(−Summe). Alpha bleibt unverändert.

    from reglaze import reglaze;  rgb2 = reglaze(rgb, alpha, cell=(307, 512), seed=3)
    .venv/bin/python styles/aquarell/tools/reglaze.py IN.png OUT.png --cell 307x512   (Probe, ganzer Bogen)
"""
import argparse

import numpy as np
from PIL import Image

import wc

MATS = ["dark", "light", "green", "red", "leather", "parcel", "brass"]


def rgb2lab(rgb01):
    lin = wc.s2l(rgb01)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = lin @ M.T / np.array([0.9505, 1.0, 1.089])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    L = 116 * f[..., 1] - 16
    A = 500 * (f[..., 0] - f[..., 1])
    B = 200 * (f[..., 1] - f[..., 2])
    return np.dstack([L, A, B])


def material_of(lab):
    """Kostümteil einer Farbe (Lab), nach Farbton und Helligkeit."""
    L, A, B = lab
    C = np.hypot(A, B)
    h = np.degrees(np.arctan2(B, A)) % 360
    if L > 58 and C < 30:
        return "light"
    if C > 38 and (h < 45 or h > 340) and A > 30:
        return "red"
    if 80 < h < 135 and C > 35 and L > 50:
        return "brass"
    if h > 95 and h < 200 and C > 9:
        return "green"
    if L > 52 and 40 <= h <= 95 and C > 22:
        return "parcel"
    if C > 20 and 20 <= h <= 80:
        return "leather"
    return "dark"


def kmeans(x, k, seed, iters=25):
    rng = np.random.default_rng(seed)
    c = x[rng.choice(len(x), k, replace=False)]
    for _ in range(iters):
        lab_ = ((x[:, None] - c[None]) ** 2).sum(-1).argmin(1)
        c = np.array([x[lab_ == i].mean(0) if (lab_ == i).any() else c[i] for i in range(k)])
    return c


def tile(noise_fn, h, w, cell):
    """Rauschen je Layoutzelle gleich (Bilder eines Bogens bekommen an derselben Figurstelle dasselbe Korn)."""
    cw, ch = cell
    t = noise_fn(ch, cw)
    reps = (int(np.ceil(h / ch)), int(np.ceil(w / cw)))
    return np.tile(t, reps)[:h, :w]


def head_zone(a, cell, frac=0.30):
    """1 im oberen Anteil frac jeder Figur (je Layoutzelle die oberste deckende Zeile bis frac der Figurenhöhe)."""
    H, W = a.shape
    cw, ch = cell
    out = np.zeros((H, W))
    for y0 in range(0, H, ch):
        for x0 in range(0, W, cw):
            m = a[y0:y0 + ch, x0:x0 + cw] > 0.5
            rows = np.nonzero(m.any(1))[0]
            if len(rows) < 10:
                continue
            top, bot = rows.min(), rows.max()
            out[y0 + top:y0 + top + int(frac * (bot - top + 1)), x0:x0 + cw] = 1
    return wc.blur(out, 3.0)


def norm_blur(v, m, sigma):
    return wc.blur(v * m, sigma) / np.maximum(wc.blur(m.astype(np.float64), sigma), 1e-4)


def reglaze(rgb, a, cell=(307, 512), seed=3, smooth=2.2, shade_sigma=24.0, info=None):
    """rgb 0..255 (H, W, 3), a 0..1 (H, W). Gibt neues rgb 0..255 zurück (Alpha unverändert)."""
    H, W = a.shape
    rgb01 = np.clip(rgb / 255.0, 0, 1)
    lab = rgb2lab(rgb01)
    inside = a > 0.5
    # --- 1. Material ---------------------------------------------------------------------------------------------
    px = lab[inside]
    rng = np.random.default_rng(seed)
    sample = px[rng.choice(len(px), min(30000, len(px)), replace=False)] * np.array([0.6, 1.0, 1.0])
    cents = kmeans(sample, 16, seed) / np.array([0.6, 1.0, 1.0])
    cmat = np.array([MATS.index(material_of(c)) for c in cents])
    best = np.full((H, W), np.inf)
    raw = np.zeros((H, W), np.int64)
    for c, m in zip(cents, cmat):
        dist = (((lab - c) * np.array([0.6, 1.0, 1.0])) ** 2).sum(-1)
        upd = dist < best
        best[upd] = dist[upd]
        raw[upd] = m
    votes = np.stack([wc.blur(((raw == i) & inside).astype(np.float64), smooth) for i in range(len(MATS))], -1)
    mat = votes.argmax(-1)
    mat[~inside] = -1
    if info is not None:
        info["clusters"] = [{"lab": [round(float(v), 1) for v in c], "mat": MATS[m]} for c, m in zip(cents, cmat)]
        info["share"] = {m: round(float((mat == i).sum() / max(1, inside.sum())), 3) for i, m in enumerate(MATS)}

    # --- Rauschen (je Zelle gleich) ------------------------------------------------------------------------------
    n_edge = tile(lambda h, w: wc.value_noise(h, w, 10, seed + 1, 3), H, W, cell)
    n_cloud = tile(lambda h, w: wc.value_noise(h, w, 46, seed + 2, 3), H, W, cell)
    n_gran = tile(lambda h, w: wc.value_noise(h, w, 2.5, seed + 3, 2), H, W, cell)
    n_gap = tile(lambda h, w: wc.value_noise(h, w, 18, seed + 4, 2), H, W, cell)

    lum = lab[..., 0]
    D = np.zeros((H, W, 3))
    paper_lin = wc.s2l(wc.PAPER)
    params = {   # Schattenanteil, Glanzanteil, Dichte der hellen Lasur relativ, Glanz-Faktor, Granulation, Rand
        "dark":    (0.40, 0.08, 0.85, 0.55, 0.16, 0.55),
        "light":   (0.30, 0.25, 0.45, 0.00, 0.05, 0.70),
        "green":   (0.38, 0.07, 1.00, 0.50, 0.14, 0.55),
        "red":     (0.38, 0.07, 1.00, 0.55, 0.10, 0.50),
        "leather": (0.40, 0.06, 1.00, 0.55, 0.12, 0.50),
        "parcel":  (0.35, 0.10, 0.90, 0.40, 0.08, 0.55),
    }
    shade_mask = np.zeros((H, W), bool)
    head_z = head_zone(a, cell, frac=0.30)
    for i, m in enumerate(MATS):
        if m == "brass":
            continue
        M = mat == i
        if M.sum() < 50:
            continue
        Mf = M.astype(np.float64)
        sh_q, hi_q, light_k, hi_k, gran, rim_k = params[m]
        # Schattenform: große Helligkeitsform des KI-Bildes (stark geglättet) plus dessen tiefe Schlagschatten
        # (wenig geglättet, nur das dunkelste Zehntel); Rand mit Rauschen verbogen, kleine Inseln per Mehrheit weg
        ls = norm_blur(lum, Mf, shade_sigma)
        ls = ls + (n_edge - 0.5) * 0.9 * ls[M].std()
        t_sh = np.percentile(ls[M], 100 * sh_q)
        lc = norm_blur(lum, Mf, 4.0)
        t_cast = np.percentile(lc[M], 10)
        sh = M & ((ls < t_sh) | (lc < t_cast))
        sh = M & (wc.blur(sh.astype(np.float64), 4.0) > 0.5)
        if m == "dark":                                    # Gesicht: dunkle Streifen ohne Schattenlasur, sonst
            sh &= head_z < 0.5                             # verschwinden die Augen bei Figurengröße im Dunkel
        lh = norm_blur(lum, Mf, 6.0) + (n_edge - 0.5) * 0.6 * ls[M].std()
        t_hi = np.percentile(lh[M], 100 * (1 - hi_q))
        hi = M & (wc.blur((M & (lh > t_hi)).astype(np.float64), 3.0) > 0.5)
        cols = rgb01[M]
        lv = lum[M]
        light_col = cols[lv >= np.percentile(lv, 45)].mean(0)
        dark_col = cols[lv <= np.percentile(lv, 22)].mean(0)
        d_light = wc.density(light_col) * light_k
        d_dark = np.maximum(wc.density(dark_col) - wc.density(light_col), 0)
        if m == "light":                                   # Schatten auf hellem Fell und Hemd: kühle Lasur
            d_dark = np.maximum(d_dark, 0.0) * 0.8 + np.array([0.10, 0.10, 0.06])
        # Lasur 1: Eigenfarbe, flach mit leichter Wolkigkeit, Trockenrand innen an der Kante
        wash = Mf * (0.88 + 0.24 * n_cloud)
        wash = wash * (1 + rim_k * wc.inner_edge(Mf, 2.6) / 0.9)
        # ausgehobene Lichter
        hif = wc.blur(hi.astype(np.float64), 0.8)
        wash = wash * (1 - (1 - hi_k) * hif)
        D += wash[..., None] * d_light[None, None, :]
        # Lasur 2: Schatten, hart begrenzt, eigener Trockenrand
        shf = wc.blur(sh.astype(np.float64), 0.7)
        glaze = shf * (0.9 + 0.2 * n_cloud) * (1 + rim_k * wc.inner_edge(shf, 2.2) / 0.9)
        D += glaze[..., None] * d_dark[None, None, :]
        shade_mask |= sh
        # Granulation (Pigment setzt sich in die Papiertäler)
        D[M] *= (1 + gran * (n_gran[M] - 0.5) * 2)[:, None]
        if info is not None:
            info.setdefault("mats", {})[m] = {"light": [int(v * 255) for v in light_col],
                                              "dark": [int(v * 255) for v in dark_col]}

    # --- Papierspalt an manchen Materialgrenzen ------------------------------------------------------------------
    mm = np.where(inside, mat, -1)
    border = np.zeros((H, W), bool)
    for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (-1, -1)):
        sh_ = np.roll(np.roll(mm, dy, 0), dx, 1)
        border |= (sh_ != mm) & (sh_ >= 0) & (mm >= 0)
    gap = border & (n_gap > 0.62)
    gapf = wc.blur(gap.astype(np.float64), 0.6)
    D *= (1 - 0.85 * gapf)[..., None]

    # --- Messing und starke dunkle Einzelheiten aus dem KI-Bild ---------------------------------------------------
    D0 = -np.log(np.clip(wc.s2l(rgb01) / paper_lin, 1e-4, 1.0))
    d0 = D0.mean(-1)
    hp = d0 - norm_blur(d0, inside.astype(np.float64), 3.0)
    head = head_zone(a, cell, frac=0.30)
    feat = inside & (hp > np.where(head > 0.5, 0.55, 0.9))
    Cc = np.hypot(lab[..., 1], lab[..., 2])
    hh = np.degrees(np.arctan2(lab[..., 2], lab[..., 1])) % 360
    brass = inside & (Cc > 47) & (hh > 70) & (hh < 100)          # Messingknöpfe (zu klein für eine Farbgruppe)
    keep = wc.blur((feat | brass).astype(np.float64), 0.8)
    keep = np.clip(keep * 1.5, 0, 1)
    D = D * (1 - keep[..., None]) + np.maximum(D, D0) * keep[..., None]
    # Gesicht: im Kopfbereich jeder Figur die feinen Einzelheiten des KI-Bildes (Augen samt Glanzpunkt, Nasenspiegel,
    # Mundlinie) als vorzeichenbehaftete Hochpass-Dichte zurückgeben; in dunklem Fell sind die Augen sonst weg.
    hp3 = D0 - np.stack([norm_blur(D0[..., c], inside.astype(np.float64), 2.5) for c in range(3)], -1)
    strength = wc.smoothstep(0.12, 0.35, np.abs(hp3).mean(-1)) * head
    D = np.maximum(D + hp3 * strength[..., None], 0)
    # sehr dunkle Stellen im Kopf (Pupillen, Nase) in voller Tiefe
    darkest = wc.blur((head > 0.5) & inside & (lum < 20), 0.8)
    darkest = np.clip(darkest * 1.6, 0, 1)
    D = D * (1 - darkest[..., None]) + np.maximum(D, D0) * darkest[..., None]
    if info is not None:
        info["feature_share"] = round(float(feat.sum() / max(1, inside.sum())), 4)
    out = paper_lin * np.exp(-D)
    out = wc.l2s(out) * 255.0
    return np.where(inside[..., None] | (a[..., None] > 0), out, rgb)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--cell", default="307x512")
    ap.add_argument("--seed", type=int, default=3)
    a_ = ap.parse_args()
    im = np.asarray(Image.open(a_.inp).convert("RGBA")).astype(np.float64)
    cw, ch = (int(v) for v in a_.cell.split("x"))
    info = {}
    rgb = reglaze(im[..., :3], im[..., 3] / 255.0, (cw, ch), a_.seed, info=info)
    Image.fromarray(np.dstack([np.clip(rgb, 0, 255), im[..., 3]]).astype(np.uint8), "RGBA").save(a_.out)
    import json
    print(json.dumps(info, ensure_ascii=False))


if __name__ == "__main__":
    main()
