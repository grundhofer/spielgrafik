#!/usr/bin/env python3
"""Ink & Paint: macht aus den KI-Zeichnungen (assets/raw/sheet.png, assets/raw/boats.png) saubere Cels.

Wie in einer Kopier- und Malabteilung bekommt jede Fläche genau eine Farbe aus einem festgelegten Farbmodell:
  1. Freistellen (Alpha >= 128) und Figuren über Zusammenhangskomponenten trennen.
  2. Tusche: Pixel, deren Helligkeit L* unter der Schwelle ihres Materials liegt, werden Linie.
  3. Material je Pixel: nächste Bezugsfarbe im Lab-Raum, Helligkeit nur schwach gewichtet (Schattierung
     wechselt das Material nicht).
  4. Licht/Schatten: L* je Material innerhalb der Materialfläche weichzeichnen und an der Otsu-Schwelle teilen.
     Aus dem weichen KI-Verlauf wird so eine hart begrenzte Schattenform, die der Form folgt.
  5. Mehrheitsfilter über die Etiketten (Linie bleibt), dann Farben aus dem Farbmodell einsetzen.
  6. Farbmodell „Abend“ (Nachtfarbmodell des Zeichentricks) aus dem Tagesmodell rechnen.

Ausgabe in Quellauflösung (assets/cel/*.png, Tag und Abend) plus Etikettenbilder (assets/cel/*_labels.png)
und die Messwerte (assets/cel/cels.json). Verkleinert wird erst in build_sprites.py.

    .venv/bin/python styles/zeichentrick-cel/scripts/ink_paint.py
"""
import json, pathlib, sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from celutil import srgb_to_lab, blur_masked, mode_filter, components, black_tophat, max_filter, box  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/cel"

# Bezugsfarben der Materialien (aus k-means über die KI-Bilder abgelesen) und ob sie Licht/Schatten bekommen.
BADGER = {
    "fur_dark": ((63, 54, 53), True),
    "cream": ((248, 232, 205), True),
    "green": ((70, 83, 44), True),
    "red": ((182, 32, 34), True),
    "leather": ((108, 56, 33), True),
    "parcel": ((206, 145, 84), True),
    "brass": ((196, 150, 52), False),
    "iris": ((120, 70, 40), False),
    "white": ((255, 255, 255), False),
}
BOATS = {
    "hull_blue": ((30, 80, 110), True),
    "hull_red": ((150, 55, 40), True),
    "wood": ((125, 66, 32), True),
    "wood_dark": ((80, 40, 22), False),
    "rope": ((200, 160, 100), True),
    "sail": ((235, 222, 196), True),
    "metal": ((60, 62, 66), False),
}
INK_DAY = (30, 20, 16)
CONF, SPLIT_R, CONFUSE = 9.0, 4, 18.0  # Abstand für sichere Pixel (Lab, gewichtet), Weichzeichner für die Schattenteilung
INK_GROW = 1  # Linie in der Quelle um so viele Pixel je Seite verbreitern
INK_R, INK_T = 4, 11.0  # Top-Hat-Radius (Linien bis 8 px breit) und Mindestkontrast in L*
SPECK = 15  # Tuschekomponenten (8er-Nachbarschaft) unter so vielen Pixeln sind Sprenkel und werden ausgemalt


def lab_to_srgb(lab):
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    fy = (L + 16) / 116
    fx, fz = fy + a / 500, fy - b / 200
    e = 216 / 24389
    k = 24389 / 27
    x = np.where(fx ** 3 > e, fx ** 3, (116 * fx - 16) / k)
    y = np.where(L > k * e, fy ** 3, L / k)
    z = np.where(fz ** 3 > e, fz ** 3, (116 * fz - 16) / k)
    xyz = np.stack([x * 0.95047, y, z * 1.08883], -1)
    m = np.array([[3.2404542, -1.5371385, -0.4985314],
                  [-0.9692660, 1.8760108, 0.0415560],
                  [0.0556434, -0.2040259, 1.0572252]])
    c = xyz @ m.T
    c = np.where(c <= 0.0031308, 12.92 * c, 1.055 * np.clip(c, 0, None) ** (1 / 2.4) - 0.055)
    return np.clip(c * 255, 0, 255)


def otsu(v):
    h, e = np.histogram(v, bins=100)
    c = (e[:-1] + e[1:]) / 2
    best, thr = -1, np.median(v)
    for i in range(5, 95):
        w0, w1 = h[:i].sum(), h[i:].sum()
        if w0 == 0 or w1 == 0:
            continue
        m0, m1 = (h[:i] * c[:i]).sum() / w0, (h[i:] * c[i:]).sum() / w1
        s = w0 * w1 * (m0 - m1) ** 2
        if s > best:
            best, thr = s, c[i]
    return thr


def components8(mask):
    """Zusammenhangskomponenten mit 8er-Nachbarschaft (Minimum-Ausbreitung). 0 = Hintergrund."""
    h, w = mask.shape
    big = h * w + 1
    lab = np.where(mask, np.arange(1, h * w + 1).reshape(h, w), big)
    while True:
        p = np.pad(lab, 1, constant_values=big)
        n = np.minimum.reduce([p[1 + dy:1 + dy + h, 1 + dx:1 + dx + w] for dy in (-1, 0, 1) for dx in (-1, 0, 1)])
        n = np.where(mask, n, big)
        if np.array_equal(n, lab):
            break
        lab = n
    return np.where(mask, lab, 0)


def fill_from_neighbours(labels, holes, alpha, r=2, iters=6):
    """Pixel in holes bekommen das häufigste Material (ohne Tusche und Leer) aus der (2r+1)²-Umgebung."""
    k = int(labels.max()) + 1
    lab = labels.copy()
    todo = holes.copy()
    for _ in range(iters):
        if not todo.any():
            break
        votes = np.stack([box(((lab == i) & ~todo).astype(np.float32), r) for i in range(k)])
        votes[:2] = 0  # Leer und Tusche stimmen nicht mit
        best = votes.argmax(0)
        ok = todo & (votes.max(0) > 0)
        lab[ok] = best[ok]
        todo &= ~ok
    lab[todo] = 1  # ohne Materialnachbarn (mitten in der Linie) bleibt es Tusche
    lab[~alpha] = 0
    return lab


def protected(labels, table):
    return np.isin(labels, [i for i, t in enumerate(table) if t[0] in ("white", "iris", "brass")])


def remove_specks(labels, alpha, limit):
    """Tuscheinseln (8er-Nachbarschaft) unter limit Pixeln mit dem umgebenden Material ausmalen."""
    ink = labels == 1
    comp = components8(ink)
    ids, cnt = np.unique(comp[ink], return_counts=True)
    speck = np.isin(comp, ids[cnt < limit]) & ink
    return fill_from_neighbours(labels, speck, alpha), int((cnt < limit).sum())


def clean_ink(labels, table, alpha, outline):
    """Vor dem Verbreitern: Silhouette schließen (optional) und Sprenkel ausmalen."""
    protect = protected(labels, table)
    stats = {}
    labels = labels.copy()
    if outline:
        # Außenkontur: Die KI lässt an Schal und Paket Lücken in der Außenlinie; jedes deckende Pixel mit einem
        # leeren 4er-Nachbarn wird Tusche (danach verbreitert INK_GROW die Linie wie überall).
        p = np.pad(alpha, 1)
        edge = alpha & ~(p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:])
        stats["outline_added_px"] = int((edge & (labels != 1) & ~protect).sum())
        labels[edge & ~protect] = 1
    labels, stats["specks_removed"] = remove_specks(labels, alpha, SPECK)
    return labels, stats


def smooth_ink(labels, table, alpha, stats):
    """Nach dem Verbreitern: Tuschemaske weichzeichnen (3x3-Kasten, zweimal) und bei 0,5 neu schwellen. Rundet
    Treppenstufen und nimmt einzelne Pixelnasen weg; außerhalb der Figur zählt als Tusche, damit die Außenlinie
    nicht dünner wird. Geschützte Farben (Glanzpunkt, Iris, Messing) bleiben."""
    protect = protected(labels, table)
    ink = (labels == 1) | ~alpha
    v = box(box(ink.astype(np.float32), 1) / 9.0, 1) / 9.0
    new = (v >= 0.5) & alpha & ~protect
    removed = (labels == 1) & ~new
    stats["smooth_removed_px"] = int(removed.sum())
    stats["smooth_added_px"] = int((new & (labels != 1)).sum())
    labels = labels.copy()
    labels[new] = 1
    labels = fill_from_neighbours(labels, removed & alpha, alpha)
    labels, stats["specks_after_smooth"] = remove_specks(labels, alpha, SPECK)
    return labels


def paint(rgba, mats, fixed_split=None, outline=False):
    """Gibt (Etiketten, Tabelle) zurück. Etikett 0 = leer, 1 = Tusche, dann je Material Licht/Schatten."""
    alpha = rgba[..., 3] >= 128
    lab = srgb_to_lab(rgba[..., :3].astype(np.float64))
    names = list(mats)
    ref = srgb_to_lab(np.array([mats[n][0] for n in names], np.float64))
    w = np.array([0.35, 1.0, 1.0])  # L* schwach gewichten
    d = (((lab[:, :, None, :] - ref[None, None]) * w) ** 2).sum(-1)
    mat = d.argmin(-1)
    conf = np.sqrt(d.min(-1)) < CONF
    # Tusche: schmale dunkle Linien über ein Black-Top-Hat (Schließen minus Bild, Fenster 9x9) finden, dazu
    # alles fast Schwarze (Nase, Pupillen). Die Schwelle wächst mit der Helligkeit der Umgebung, damit
    # Schattenstufen auf hellen Flächen nicht zur Linie werden.
    L = np.where(alpha, lab[..., 0], 100.0)
    closed = L + black_tophat(L, INK_R)
    th = closed - L
    chroma = np.hypot(lab[..., 1], lab[..., 2])
    ink = alpha & (((th > np.maximum(INK_T, 0.42 * closed)) & (L < 60) & (chroma < 18)) | (L < 9))
    fill = alpha & ~ink
    # Ausmalen je umrandeter Fläche: In jeder von Tusche umschlossenen Fläche bekommen Pixel eines leicht
    # verwechselbaren Materials (Abstand der Bezugsfarben < CONFUSE) das Mehrheitsmaterial der Fläche. So wird ein
    # rotbrauner Rumpf nicht fleckig zu Holz, ohne dass sich Flächen über Lücken in der Linie vermischen.
    regions = components(fill)
    rd = np.sqrt((((ref[:, None] - ref[None]) * w) ** 2).sum(-1))
    n_reg = regions.max()
    flat_r, flat_m = regions[fill], mat[fill]
    counts = np.zeros((n_reg + 1, len(names)), np.int64)
    np.add.at(counts, (flat_r, flat_m), 1)
    major = counts.argmax(1)
    area = counts.sum(1)
    swap = (area[flat_r] >= 150) & (rd[flat_m, major[flat_r]] < CONFUSE) & (flat_m != major[flat_r])
    flat_m = np.where(swap, major[flat_r], flat_m)
    mat = mat.copy()
    mat[fill] = flat_m
    labels = np.zeros(alpha.shape, np.int32)
    labels[ink] = 1
    table = [("empty", None, None), ("ink", None, None)]
    splits = {}
    for i, n in enumerate(names):
        m = fill & (mat == i)
        li, sh = len(table), len(table) + 1
        table += [(n, "light", None), (n, "shadow", None)]
        if not m.any():
            continue
        if mats[n][1] and m.sum() > 400:
            Ls = blur_masked(lab[..., 0], m, SPLIT_R)
            thr = fixed_split.get(n) if fixed_split and n in fixed_split else otsu(Ls[m])
            splits[n] = float(thr)
            labels[m & (Ls >= thr)] = li
            labels[m & (Ls < thr)] = sh
        else:
            labels[m] = li
    k = len(table)
    # Mehrheitsfilter nur für unsichere Pixel (Kantenglättung der KI zwischen zwei Flächen); Linie, Hintergrund
    # und Pixel nahe an einer Bezugsfarbe (Glanzpunkte, Knöpfe, Iris) bleiben.
    keep = (labels == 1) | ~alpha | conf
    labels = mode_filter(labels, k, 2, keep=keep, iters=2)
    labels[~alpha] = 0
    labels, ink_stats = clean_ink(labels, table, alpha, outline)
    # Linie um INK_GROW Pixel verbreitern (Kreuz-Nachbarschaft): Die KI zeichnet für die Spielgröße zu dünn
    # (Median 2 px in der Quelle, also 1 px im Spiel). Glanzpunkte, Iris und Knöpfe werden nicht überdeckt.
    protect = np.isin(labels, [i for i, t in enumerate(table) if t[0] in ("white", "iris", "brass")])
    for _ in range(INK_GROW):
        ink_m = labels == 1
        grown = ink_m.copy()
        grown[1:] |= ink_m[:-1]
        grown[:-1] |= ink_m[1:]
        grown[:, 1:] |= ink_m[:, :-1]
        grown[:, :-1] |= ink_m[:, 1:]
        labels[grown & alpha & ~protect] = 1
    labels = smooth_ink(labels, table, alpha, ink_stats)
    return labels, table, splits, lab, ink_stats


def colour_model(labels, table, lab, alpha):
    """Tagesmodell: Lichtfarbe = Median der KI-Farbe im Lichtteil, Schatten = dunkler und kühler."""
    model = {}
    for idx, (n, tone, _) in enumerate(table):
        if n in ("empty", "ink") or tone != "light":
            continue
        m = (labels == idx) & alpha
        if not m.any():
            m = (labels == idx + 1) & alpha
        if not m.any():
            continue
        light = np.median(lab[m], axis=0)
        # Schattenstufe: helle Farben weniger stark abdunkeln, alle etwas kühler (Richtung Blauviolett)
        f = 0.80 if light[0] > 60 else 0.72
        shadow = light * np.array([f, 1.0, 0.92]) + np.array([0, 3.0, -7.0])
        model[n] = {"light": lab_to_srgb(light).round().astype(int).tolist(),
                    "shadow": lab_to_srgb(shadow).round().astype(int).tolist(),
                    "light_lab": light.round(1).tolist()}
    return model


def dusk(model, ink):
    """Abendfarbmodell: dunkler, etwas entsättigt und zum Blauviolett der Szene verschoben."""
    out = {}
    for n, c in model.items():
        o = {}
        for t in ("light", "shadow"):
            lab = srgb_to_lab(np.array(c[t], np.float64))
            lab = lab * np.array([0.86, 0.82, 0.82]) + np.array([0, 3.0, -7.0])
            o[t] = lab_to_srgb(lab).round().astype(int).tolist()
        out[n] = o
    lab = srgb_to_lab(np.array(ink, np.float64)) * np.array([1, 0.6, 0.6]) + np.array([0, 2.0, -5.0])
    return out, lab_to_srgb(lab).round().astype(int).tolist()


def render(labels, table, model, ink):
    h, w = labels.shape
    pal = np.zeros((len(table), 4), np.uint8)
    pal[1] = (*ink, 255)
    for idx, (n, tone, _) in enumerate(table):
        if n in model and tone:
            pal[idx] = (*model[n][tone], 255)
    return pal[labels]


def cel_metrics(img, labels):
    """Sprenkel (Tuschekomponenten <= 12 px, 8er-Nachbarschaft) und Flachanteil (Figurpixel, deren 3x3-Umgebung
    exakt dieselbe Farbe hat) im fertigen Blatt."""
    a = img[..., 3] >= 128
    ink = labels == 1
    comp = components8(ink)
    ids, cnt = np.unique(comp[ink], return_counts=True)
    key = img[..., 0].astype(np.int64) * 65536 + img[..., 1].astype(np.int64) * 256 + img[..., 2]
    key = np.where(a, key, -1)
    p = np.pad(key, 1, constant_values=-2)
    h, w = key.shape
    same = np.ones_like(a)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            same &= p[1 + dy:1 + dy + h, 1 + dx:1 + dx + w] == key
    return {"ink_components": int(len(ids)), "specks_le12": int((cnt <= 12).sum()),
            "flat_share": round(float(same[a].mean()), 3), "colours": int(len(np.unique(key[a])))}


def process(src, mats, prefix, min_area, cells=None, outline=False):
    rgba = np.array(Image.open(src).convert("RGBA"))
    alpha = rgba[..., 3] >= 128
    labels, table, splits, lab, ink_stats = paint(rgba, mats, outline=outline)
    model = colour_model(labels, table, lab, alpha)
    dmodel, dink = dusk(model, INK_DAY)
    day = render(labels, table, model, INK_DAY)
    eve = render(labels, table, dmodel, dink)
    OUT.mkdir(parents=True, exist_ok=True)
    Image.fromarray(day).save(OUT / f"{prefix}_day.png")
    Image.fromarray(eve).save(OUT / f"{prefix}_dusk.png")
    Image.fromarray(labels.astype(np.uint8)).save(OUT / f"{prefix}_labels.png")
    # Figuren trennen (auf halber Auflösung, dann zurück)
    small = alpha[::2, ::2]
    comp = components(small)
    comp = np.kron(comp, np.ones((2, 2), comp.dtype))[:alpha.shape[0], :alpha.shape[1]]
    comp[~alpha] = 0
    # Pixel, die auf halber Auflösung fehlten (dünne Linien am Rand), vom Nachbarn übernehmen
    for _ in range(4):
        hole = alpha & (comp == 0)
        if not hole.any():
            break
        comp = np.where(hole, max_filter(comp, 1), comp)
    alpha = alpha & (comp > 0)
    ids, counts = np.unique(comp[comp > 0], return_counts=True)
    big = [i for i, c in zip(ids, counts) if c >= min_area]
    ys, xs = np.mgrid[:alpha.shape[0], :alpha.shape[1]]
    cent = {i: (xs[comp == i].mean(), ys[comp == i].mean()) for i in big}
    # kleine Teile der nächsten großen Komponente zuordnen
    for i, c in zip(ids, counts):
        if c >= min_area:
            continue
        cx, cy = xs[comp == i].mean(), ys[comp == i].mean()
        j = min(big, key=lambda b: (cent[b][0] - cx) ** 2 + (cent[b][1] - cy) ** 2)
        comp[comp == i] = j
    figs = []
    for i in big:
        m = comp == i
        yy, xx = np.where(m)
        figs.append({"id": int(i), "bbox": [int(xx.min()), int(yy.min()), int(xx.max()) + 1, int(yy.max()) + 1],
                     "cx": float(cent[i][0]), "cy": float(cent[i][1]), "area": int(m.sum())})
    Image.fromarray(comp.astype(np.uint16)).save(OUT / f"{prefix}_comp.png")
    stats = {"ink_clean": ink_stats, "metrics_dusk": cel_metrics(eve, labels),
             "table": [list(t[:2]) for t in table], "splits": splits, "model_day": model,
             "model_dusk": dmodel, "ink_day": list(INK_DAY), "ink_dusk": dink, "figures": figs,
             "ink_share": float((labels == 1).sum() / max(alpha.sum(), 1))}
    return stats


def main():
    res = {}
    res["sheet"] = process(ROOT / "assets/raw/sheet.png", BADGER, "sheet", 3000, outline=True)
    res["boats"] = process(ROOT / "assets/raw/boats.png", BOATS, "boats", 3000)
    (OUT / "cels.json").write_text(json.dumps(res, indent=1))
    for k, v in res.items():
        print(k, "Figuren", len(v["figures"]), "Tusche-Anteil %.3f" % v["ink_share"], "Schwellen", v["splits"])
        print("  Linie gesäubert", v["ink_clean"], "Messung", v["metrics_dusk"])
        for n, c in v["model_day"].items():
            print("  ", n, c["light"], c["shadow"], "Abend", v["model_dusk"][n]["light"], v["model_dusk"][n]["shadow"])


if __name__ == "__main__":
    main()
