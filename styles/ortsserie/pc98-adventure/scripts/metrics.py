"""Messfunktionen für die Ortsserie pc98-adventure (Layout-Kopie, Palettenabstand, Detailmaß, Pixelraster).

Alle Maße arbeiten auf Oklab-Helligkeit L (0..1) bzw. Oklab-Farben; ΔE = euklidischer Oklab-Abstand × 100.
Bilder verschiedener Größe (agy 1264x848, Codex 1536x1024) werden vor dem Vergleich auf dieselbe Breite gebracht.
"""
import pathlib, sys

import numpy as np
from PIL import Image

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "styles" / "pc98-adventure" / "scripts"))
from pc98lib import oklab  # noqa: E402  (nur gelesen, nicht verändert)

COMMON_W = 632          # gemeinsame Breite für Detail- und Palettenmaße (halbe agy-Breite)


def load(path, width=None, size=None):
    im = Image.open(path).convert("RGB")
    if size:
        im = im.resize(size, Image.BOX)
    elif width:
        im = im.resize((width, round(im.height * width / im.width)), Image.BOX)
    return np.asarray(im)


def L(rgb):
    return oklab(rgb.reshape(-1, 3)).reshape(rgb.shape)[..., 0]


def corr(a, b):
    a = a.ravel() - a.mean()
    b = b.ravel() - b.mean()
    return float((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum() + 1e-12))


def _grad(l):
    gx = np.zeros_like(l)
    gy = np.zeros_like(l)
    gx[:, 1:-1] = (l[:, 2:] - l[:, :-2]) / 2
    gy[1:-1] = (l[2:] - l[:-2]) / 2
    return np.hypot(gx, gy)


def _box(a, fy, fx):
    h, w = a.shape[0] // fy * fy, a.shape[1] // fx * fx
    return a[:h, :w].reshape(h // fy, fy, w // fx, fx).mean((1, 3))


def layout_similarity(pa, pb):
    """Ähnlichkeit des Bildaufbaus: Korrelation der Graustufen (96x64) und der Kantenbilder (Gradient auf 192x128,
    auf 48x32 gemittelt). Hoch = gleiche Hell-Dunkel-Verteilung bzw. Kanten an denselben Stellen."""
    ga = L(load(pa, size=(96, 64)))
    gb = L(load(pb, size=(96, 64)))
    ea = _box(_grad(L(load(pa, size=(192, 128)))), 4, 4)
    eb = _box(_grad(L(load(pb, size=(192, 128)))), 4, 4)
    return {"gray_corr": round(corr(ga, gb), 3), "edge_corr": round(corr(ea, eb), 3)}


def kmeans(lab, k=12, iters=25, seed=0):
    rng = np.random.default_rng(seed)
    # k-means++-Start
    cent = [lab[rng.integers(len(lab))]]
    for _ in range(k - 1):
        d = np.min(((lab[:, None] - np.array(cent)[None]) ** 2).sum(-1), 1)
        cent.append(lab[rng.choice(len(lab), p=d / d.sum())])
    cent = np.array(cent)
    for _ in range(iters):
        lbl = ((lab[:, None] - cent[None]) ** 2).sum(-1).argmin(1)
        for j in range(k):
            m = lbl == j
            if m.any():
                cent[j] = lab[m].mean(0)
    lbl = ((lab[:, None] - cent[None]) ** 2).sum(-1).argmin(1)
    w = np.bincount(lbl, minlength=k) / len(lbl)
    return cent, w


def palette_of(path, k=12, n=20000, seed=0):
    rgb = load(path, width=COMMON_W).reshape(-1, 3)
    rng = np.random.default_rng(seed)
    lab = oklab(rgb[rng.choice(len(rgb), min(n, len(rgb)), replace=False)])
    return kmeans(lab, k, seed=seed)


def palette_distance(pal_a, pal_b):
    """Abstand zweier k-means-Paletten: jede Farbe von b zur nächsten von a (nach Anteil gewichtet) und umgekehrt,
    Mittel beider Richtungen. ΔE in Oklab × 100."""
    (ca, wa), (cb, wb) = pal_a, pal_b
    d = np.sqrt(((cb[:, None] - ca[None]) ** 2).sum(-1)) * 100
    ab = float((d.min(1) * wb).sum())
    ba = float((d.min(0) * wa).sum())
    return {"dE_matched": round((ab + ba) / 2, 2), "dE_new_to_anchor": round(ab, 2),
            "dE_anchor_to_new": round(ba, 2), "dE_max_new_color": round(float(d.min(1).max()), 1)}


def detail(path):
    """Detailmaß auf 632 px Breite: mittlere Gradientenenergie der Helligkeit (×100) und Kantendichte
    (Anteil Pixel mit Gradient > 0,04)."""
    g = _grad(L(load(path, width=COMMON_W)))
    return {"grad_energy": round(float(g.mean() * 100), 3), "edge_density": round(float((g > 0.04).mean()), 4)}


def pixel_style(path, width=1264):
    """Pixel-Art-Merkmale in voller agy-Auflösung: Periode des Pseudo-Pixelrasters (stärkste Periode 2–10 px der
    Spaltenunterschiede, mit Deutlichkeit = Spitze / Median) und Anteil flacher Flächen (3x3-Spannweite von L < 0,01)."""
    l = L(load(path, width=width))
    sig = np.abs(np.diff(l, axis=1)).mean(0)
    sig = sig - sig.mean()
    p = np.abs(np.fft.rfft(sig)) ** 2
    f = np.fft.rfftfreq(len(sig))
    band = (f > 1 / 10) & (f < 1 / 2)
    j = np.flatnonzero(band)[p[band].argmax()]
    pad = np.pad(l, 1, mode="edge")
    win = np.stack([pad[dy:dy + l.shape[0], dx:dx + l.shape[1]] for dy in range(3) for dx in range(3)])
    flat = (win.max(0) - win.min(0)) < 0.01
    return {"pixel_period_px": round(float(1 / f[j]), 2), "pixel_period_clarity": round(float(p[j] / np.median(p[band])), 1),
            "flat_share": round(float(flat.mean()), 3)}


def calm_zone(path):
    """Ruhe der Porträt-/Textzone: Gradientenenergie im unteren Mittelfeld (x 30–70 %, y 55–94 %) im Verhältnis
    zum ganzen Bild (< 1 = ruhiger als der Schnitt)."""
    g = _grad(L(load(path, width=COMMON_W)))
    h, w = g.shape
    z = g[int(h * 0.55):int(h * 0.94), int(w * 0.30):int(w * 0.70)]
    return round(float(z.mean() / g.mean()), 3)


def tile_copy(pa, pb, grid=(3, 2), size=(96, 64)):
    """Layout-Kopie in Teilflächen: Bild in grid Kacheln (Spalten, Zeilen); je Kachel Korrelation der Graustufen
    und mittlerer Helligkeitsabstand |ΔL|. Eine kopierte Fläche hat hohe Korrelation UND kleinen Abstand
    (Schwelle hier: r ≥ 0,9 und |ΔL| ≤ 0,03)."""
    ga = L(load(pa, size=size))
    gb = L(load(pb, size=size))
    cw, ch = size[0] // grid[0], size[1] // grid[1]
    tiles = []
    for j in range(grid[1]):
        for i in range(grid[0]):
            a = ga[j * ch:(j + 1) * ch, i * cw:(i + 1) * cw]
            b = gb[j * ch:(j + 1) * ch, i * cw:(i + 1) * cw]
            tiles.append({"tile": f"{['links', 'mitte', 'rechts'][i]}-{['oben', 'unten'][j]}",
                          "r": round(corr(a, b), 3), "dL": round(float(np.abs(a - b).mean()), 3)})
    copied = [t["tile"] for t in tiles if t["r"] >= 0.9 and t["dL"] <= 0.03]
    best = max(tiles, key=lambda t: t["r"] - 10 * t["dL"])
    return {"copied_tiles": copied, "closest_tile": best, "tiles": tiles}
