#!/usr/bin/env python3
"""Palette der Demo aus Probebildern bauen (deterministisch).

    .venv/bin/python styles/pixel-3d/scripts/probe.py RAW -- --no-palette
    .venv/bin/python styles/pixel-3d/scripts/probe.py MASK -- --mask
    .venv/bin/python styles/pixel-3d/scripts/build_palette.py RAW MASK

Liest jedes 6. Renderbild (dump/r*.png, 428×242, ohne Palette) und die Maske des Dachses (gleiche
Bildnummern), gewichtet Dachs-Pixel ×12 und sehr helle Pixel (Lampen, Glanz) ×4, nimmt von der Summe je
Farbe die Wurzel (--power 0.5: große Flächen wie Himmel und Pflaster verdrängen sonst seltene Farben wie
Gras, Weste und Schal) und teilt die Farben mit k-means in OKLab in N Gruppen (feste Startwerte, 30 Runden).
Die Pixel des Dachses bekommen zusätzlich eigene Gruppen (--figure-colors), damit Weste, Schal, Mütze und
Gesicht ihre gerenderten Töne behalten. Danach werden häufige Farben, die weit von jeder Palettenfarbe liegen,
einzeln ergänzt (--max-dist, --extra). Jede Gruppe wird durch ihre häufigste
tatsächlich gerenderte Farbe vertreten (nicht durch den Mittelwert): Die Toon-Stufen sind flache Farben,
der Modus trifft sie genau, Mittelwerte wären trüb. Dazu kommen die festen Farben der Oberfläche (ui.gd).
Schreibt assets/palette.png (N+7 × 1), demo/palette.png (Kopie) und assets/palette_sheet.png
(Farbfelder 24 px, 16 je Zeile).
"""
import argparse
import pathlib
import shutil

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
UI = ["120c1e", "231a38", "f2dcae", "5c4170", "f6ead2", "b4a3c4", "ffb357"]


def srgb_to_lin(c):
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def oklab(rgb):
    c = srgb_to_lin(rgb.astype(np.float64))
    l = 0.4122214708 * c[:, 0] + 0.5363325363 * c[:, 1] + 0.0514459929 * c[:, 2]
    m = 0.2119034982 * c[:, 0] + 0.6806995451 * c[:, 1] + 0.1073969566 * c[:, 2]
    s = 0.0883024619 * c[:, 0] + 0.2817188376 * c[:, 1] + 0.6299787005 * c[:, 2]
    l, m, s = np.cbrt(l), np.cbrt(m), np.cbrt(s)
    lab = np.stack([0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
                    1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
                    0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s], axis=1)
    lab[:, 0] *= 1.3   # wie palette.gdshader: Helligkeit stärker gewichten
    return lab


def kmeans_modes(lab, w, rgb, k, seed):
    """k-means in OKLab (k-means++ mit festem Seed, 30 Runden); je Gruppe die häufigste echte Farbe."""
    rng = np.random.default_rng(seed)
    k = min(k, len(lab))
    centers = [lab[np.argmax(w)]]
    for _ in range(1, k):
        d = np.min([((lab - c) ** 2).sum(1) for c in centers], axis=0) * w
        centers.append(lab[rng.choice(len(lab), p=d / d.sum())])
    centers = np.array(centers)
    for _ in range(30):
        d = ((lab[:, None, :] - centers[None, :, :]) ** 2).sum(2)
        lbl = d.argmin(1)
        for j in range(k):
            sel = lbl == j
            if sel.any():
                centers[j] = (lab[sel] * w[sel, None]).sum(0) / w[sel].sum()
    out = []
    for j in range(k):
        sel = np.where(lbl == j)[0]
        if len(sel):
            out.append(tuple(int(v) for v in rgb[sel[np.argmax(w[sel])]]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw")
    ap.add_argument("mask")
    ap.add_argument("--colors", type=int, default=32)
    ap.add_argument("--figure-colors", type=int, default=12)
    ap.add_argument("--step", type=int, default=6)
    ap.add_argument("--power", type=float, default=0.5)
    ap.add_argument("--max-dist", type=float, default=0.06)
    ap.add_argument("--extra", type=int, default=8)
    ap.add_argument("--min-count", type=int, default=40)
    a = ap.parse_args()
    raw, mask = pathlib.Path(a.raw) / "dump", pathlib.Path(a.mask) / "dump"
    cols, wts, masks = [], [], []
    files = sorted(raw.glob("r*.png"))[1::a.step]
    for f in files:
        img = np.asarray(Image.open(f).convert("RGB")).reshape(-1, 3)
        w = np.ones(len(img))
        mf = mask / f.name
        if mf.exists():
            mk = np.asarray(Image.open(mf).convert("L")).reshape(-1) > 128
            w[mk] *= 12.0
        bright = img.max(axis=1) > 235
        w[bright] *= 4.0
        cols.append(img)
        wts.append(w)
        masks.append(mk if mf.exists() else np.zeros(len(img), bool))
    cols = np.concatenate(cols)
    wts = np.concatenate(wts)
    mask_all = np.concatenate(masks)
    # gleiche Farben zusammenfassen
    key = cols[:, 0].astype(np.int64) << 16 | cols[:, 1].astype(np.int64) << 8 | cols[:, 2]
    uniq, inv = np.unique(key, return_inverse=True)
    w_u = np.bincount(inv, weights=wts) ** a.power   # Wurzel: große Flächen dominieren weniger
    rgb_u = np.stack([(uniq >> 16) & 255, (uniq >> 8) & 255, uniq & 255], axis=1)
    lab_u = oklab(rgb_u)
    print(f"{len(files)} Bilder, {len(uniq)} verschiedene Farben")

    pal = kmeans_modes(lab_u, w_u, rgb_u, a.colors, 20261011)

    # Figur: eigene Gruppen aus den Dachs-Pixeln (lineare Häufigkeit), damit Weste, Schal, Mütze und
    # Gesicht ihre tatsächlich gerenderten Töne behalten
    bk = cols[mask_all][:, 0].astype(np.int64) << 16 | cols[mask_all][:, 1].astype(np.int64) << 8 | cols[mask_all][:, 2]
    bu, bn = np.unique(bk, return_counts=True)
    brgb = np.stack([(bu >> 16) & 255, (bu >> 8) & 255, bu & 255], axis=1)
    for c in kmeans_modes(oklab(brgb), bn.astype(np.float64), brgb, a.figure_colors, 7):
        pl = oklab(np.array(pal))
        if np.sqrt(((oklab(np.array([c])) - pl) ** 2).sum(1)).min() > 0.02:
            pal.append(c)

    # Lücken schließen: Farben, die oft vorkommen (mindestens --min-count Pixel in den Probebildern), aber
    # weit von jeder Palettenfarbe liegen (z. B. Gras, Weste), bekommen eine eigene Farbe, die am
    # schlechtesten getroffene zuerst, bis alle innerhalb --max-dist liegen oder --extra ergänzt sind.
    count = np.bincount(inv)
    sig = np.where(count >= a.min_count)[0]
    added = []
    for _ in range(a.extra):
        pl = oklab(np.array(pal))
        d = np.sqrt(((lab_u[sig][:, None, :] - pl[None, :, :]) ** 2).sum(2)).min(1)
        i = int(np.argmax(d))
        if d[i] < a.max_dist:
            break
        c = tuple(int(v) for v in rgb_u[sig[i]])
        pal.append(c)
        added.append(("%02x%02x%02x" % c, round(float(d[i]), 3), int(count[sig[i]])))
    print("ergänzt (Farbe, Abstand, Pixel):", added)
    pl = oklab(np.array(pal))
    d = np.sqrt(((lab_u[sig][:, None, :] - pl[None, :, :]) ** 2).sum(2)).min(1)
    print(f"größter Abstand einer häufigen Farbe zur Palette: {d.max():.3f}")
    pal = sorted(set(pal), key=lambda c: (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]))
    for h in UI:
        c = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
        if c not in pal:
            pal.append(c)
    img = Image.new("RGB", (len(pal), 1))
    img.putdata(pal)
    out = ROOT / "assets" / "palette.png"
    out.parent.mkdir(exist_ok=True)
    img.save(out)
    shutil.copy(out, ROOT / "demo" / "palette.png")
    sw = 24
    rows = (len(pal) + 15) // 16
    sheet = Image.new("RGB", (16 * sw, rows * sw), (0, 0, 0))
    for i, c in enumerate(pal):
        sheet.paste(Image.new("RGB", (sw - 2, sw - 2), c), ((i % 16) * sw + 1, (i // 16) * sw + 1))
    sheet.save(ROOT / "assets" / "palette_sheet.png")
    print(f"Palette: {len(pal)} Farben -> {out}")
    print(" ".join("%02x%02x%02x" % c for c in pal))


if __name__ == "__main__":
    main()
