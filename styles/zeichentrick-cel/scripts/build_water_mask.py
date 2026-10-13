#!/usr/bin/env python3
"""Wassermaske für den Glitzer (assets/water_mask.png, RGB, 1280x720) aus dem Hintergrund assets/bg.png.

    .venv/bin/python styles/zeichentrick-cel/scripts/build_water_mask.py

Die Glitzerstriche (Effekt-Cels in demo/main.gd) dürfen nur auf Wasser liegen, nie auf Steg, Pfählen,
Laternenpfahl, Felsen oder Kai. Auswahl über den Farbton, dazu ein grobes Wasserband als Rahmen:
  R = blaues Wasser: Farbton 200–232°, Sättigung > 0,5, Helligkeit > 0,25
  G = oranger Widerschein der Sonne: Farbton < 40° oder > 330°, Sättigung > 0,35, Helligkeit > 0,42, nur in der
      Lichtbahn unter der Sonne
Holz ist braun und dunkel (Farbton 13–22°, Helligkeit < 0,5) bzw. grau-violett (Pfähle im Schatten, Sättigung < 0,25)
und fällt dadurch heraus; die Fässer haben blaue Reifen und werden als Rechteck ausgenommen. Kleine Löcher in der
Wasserfläche (dunkle Wellentäler, < HOLE px, ohne Verbindung zum Rand des Bands) gelten als Wasser. Danach wird die
Wasserfläche um MARGIN px geschrumpft (Abstand zu Holz, Felsen und Ufer) und von kleinen Inseln befreit.
Warme Flächen, die höher als breit sind, sind kein Widerschein, sondern die sonnenbeschienene Kante eines Pfahls; sie
fallen aus der Orange-Maske. Masken liegen in R und G, nicht im Alphakanal (Godots Import überschreibt sonst die Farbe).
Messwerte und eine Kontrollansicht: assets/water_mask.json, assets/water_mask_check.png.
"""
import json, pathlib, sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from celutil import components, min_filter  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
BAND = (290, 372, 1100, 552)       # x0, y0, x1, y1: Wasser zwischen Kimm und Kaikante (Ausschnitt 1280x720)
SUN = (596, 372, 790, 548)         # Lichtbahn unter der Sonne
EXCLUDE = [(990, 466, 1100, 552)]  # Fässer (blaue Reifen)
MARGIN = 2
MIN_AREA = 40
HOLE = 300


def hsv(rgb):
    r, g, b = [rgb[..., i] / 255.0 for i in range(3)]
    mx, mn = np.maximum(np.maximum(r, g), b), np.minimum(np.minimum(r, g), b)
    d = mx - mn
    h = np.zeros_like(mx)
    m = d > 1e-6
    rr, gg, bb = mx == r, (mx == g) & (mx != r), (mx == b) & (mx != r) & (mx != g)
    h = np.where(m & rr, ((g - b) / np.maximum(d, 1e-6)) % 6, h)
    h = np.where(m & gg, (b - r) / np.maximum(d, 1e-6) + 2, h)
    h = np.where(m & bb, (r - g) / np.maximum(d, 1e-6) + 4, h)
    return h * 60.0, np.where(mx > 0, d / np.maximum(mx, 1e-6), 0), mx


def fill_holes(m, band):
    """Löcher in m innerhalb des Bands, die kleiner als HOLE sind und den Rand des Bands nicht berühren."""
    holes = band & ~m
    comp = components(holes)
    ids, counts = np.unique(comp[holes], return_counts=True)
    edge = set(np.unique(np.concatenate([comp[BAND[1], :], comp[BAND[3] - 1, :], comp[:, BAND[0]], comp[:, BAND[2] - 1]])))
    fill = [i for i, c in zip(ids, counts) if c < HOLE and i not in edge]
    return m | np.isin(comp, fill)


def streaks_only(m):
    """Nur waagerechte Streifen behalten (Breite >= 1,5 x Höhe): senkrechte warme Kanten gehören zu Pfählen."""
    comp = components(m)
    keep = np.zeros_like(m)
    for i in np.unique(comp[m]):
        ys, xs = np.where(comp == i)
        if xs.max() - xs.min() + 1 >= 1.5 * (ys.max() - ys.min() + 1):
            keep |= comp == i
    return keep


def clean(m):
    comp = components(m)
    ids, counts = np.unique(comp[m], return_counts=True)
    small = ids[counts < MIN_AREA]
    return m & ~np.isin(comp, small)


def main():
    rgb = np.array(Image.open(ROOT / "assets/bg.png").convert("RGB")).astype(np.float64)
    H, S, V = hsv(rgb)
    h, w = H.shape
    ys, xs = np.mgrid[:h, :w]
    band = (xs >= BAND[0]) & (xs < BAND[2]) & (ys >= BAND[1]) & (ys < BAND[3])
    for x0, y0, x1, y1 in EXCLUDE:
        band &= ~((xs >= x0) & (xs < x1) & (ys >= y0) & (ys < y1))
    sun = (xs >= SUN[0]) & (xs < SUN[2]) & (ys >= SUN[1]) & (ys < SUN[3])
    blue = band & (H >= 200) & (H <= 232) & (S > 0.5) & (V > 0.25)
    orange = streaks_only(sun & band & ((H < 40) | (H > 330)) & (S > 0.35) & (V > 0.42))
    water = fill_holes(blue | orange, band)
    water = clean(min_filter(water.astype(np.uint8), MARGIN).astype(bool))
    orange_c = water & orange
    blue_c = water & ~orange_c
    out = np.zeros((h, w, 3), np.uint8)
    out[..., 0] = blue_c * 255
    out[..., 1] = orange_c * 255
    Image.fromarray(out).save(ROOT / "assets/water_mask.png")
    chk = (rgb * 0.45).astype(np.uint8)
    chk[blue_c] = (90, 160, 255)
    chk[orange_c] = (255, 190, 90)
    Image.fromarray(chk).save(ROOT / "assets/water_mask_check.png")
    stats = {"band": BAND, "sun": SUN, "exclude": EXCLUDE, "margin_px": MARGIN, "hole_px": HOLE, "blue_px": int(blue_c.sum()), "orange_px": int(orange_c.sum())}
    (ROOT / "assets/water_mask.json").write_text(json.dumps(stats, indent=1))
    print("ok", stats)


if __name__ == "__main__":
    main()
