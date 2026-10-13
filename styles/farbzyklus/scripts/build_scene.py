#!/usr/bin/env python3
"""Baut aus zwei deckungsgleichen KI-Bildern (Abend, Nacht) EIN Indexbild mit 256 Paletteneinträgen und drei
Paletten (Abend, Nacht, Nacht mit Regen). Alles Bewegte ist Palettenanimation: Zyklus-Bereiche (Rotation) für
Wasserglitzern, Wellen am Kai, Rauch, Regen, Sterne und Leuchtfeuer, berechnete Einträge für Lichtkegel,
Laterne und Fenster. Das Bild selbst ändert sich zur Laufzeit nie.

    .venv/bin/python styles/farbzyklus/scripts/build_scene.py [--preview DIR]

Eingaben: assets/raw/bg_evening.png, assets/raw/bg_night.png (1536x1024, Nachtbild mit dem Abendbild als
Referenz erzeugt; gemessener Versatz 0..1 Quellpixel = unter 1/3 Zielpixel).
Ausgaben (demo/art/ und Kopie in assets/): bg_index.png (L, Wert = Palettenindex), palette.json
(drei Paletten, Zyklus-Bereiche, Lichtkegel, Flackern), Vorschauen in assets/.
"""
import argparse, json, pathlib, sys
import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fzcommon import (oklab, oklab_to_rgb, kmeans_vec, assign, hsv, dilate, distance_to, hexs,  # noqa: E402
                      BAYER4)

STYLE = HERE.parent
ART = STYLE / 'demo/art'
W, H_FULL, CROP_Y, H = 426, 284, 20, 240

# ---------------------------------------------------------------- Palettenaufteilung (Ende exklusiv)
# Reihenfolge = Priorität beim Zuweisen: was zuerst kommt, gewinnt einen Pixel.
RANGES = {
    'ui': (0, 12),          # Oberfläche: 4 feste Töne, 6 Goldtöne (Zyklus in der Titelzeile), 2 feste Goldtöne
    'sprite': (12, 30),     # Dachs (build_badger.py füllt 17 Einträge)
    'lamp': (30, 34),       # Leuchtfeuer: 4 Einträge, Rotation synchron zum Lichtkegel
    'lantern': (34, 38),    # Laterne: Glas 2 + Lichthof 2, berechnetes Flackern
    'window': (38, 40),     # Fenster (Häuschen + Haus am Leuchtturm), berechnetes Flackern
    'stars': (40, 46),      # Sterne: 2 Klassen x 3 Phasen
    'smoke': (46, 58),      # Rauch: 2 Dichtestufen x 6 Phasen
    'water': (58, 100),     # Wasser: 7 Tonstufen x 6 Phasen
    'waves': (100, 112),    # Wellen am Ufer: 2 Tonstufen x 6 Phasen
    'beam': (112, 138),     # Lichtkegel: 13 Abstandsstufen x 2 Töne (Kopien statischer Farben)
    'rain': (138, 168),     # Regen: 6 Töne x 5 Phasen (Kopien statischer Farben)
    'static': (168, 256),   # 88 feste Farben (Abend+Nacht gemeinsam per k-means in 6D)
}
WATER_T, WATER_P = 7, 6
WAVE_T, WAVE_P = 2, 6
SMOKE_T, SMOKE_P = 2, 6
RAIN_T, RAIN_P = 6, 5
COVER_THR = 0.045         # 6D-Abstand (Oklab Abend+Nacht), bis zu dem ein Pixel auf einen Zyklus-Ton umgelegt wird
BEAM_COVER_THR = 0.065    # Lichtkegel: etwas großzügiger, sonst bleibt der Kegel an der Lampe lückenhaft
STAR_C, STAR_P = 2, 3
BEAM_T = 2
BAND_N = 4                # statische Einträge, die nur das rote Band des Leuchtturms bekommt

LAMP = (379.5, 43.0)            # Mitte des Lampenglases (Szenenkoordinaten)
LAMP_BOX = (376, 40, 383, 46)   # Glas x0, y0, x1, y1 (inklusiv)
LANTERN = (88.0, 108.0)
CHIMNEY = (14.0, 37.0)          # Oberkante Schornsteintopf
SMOKE_BEND = 80                 # Endwinkel der Fahne zur Senkrechten (Wind von links), Grad
SMOKE_PUFFS = [(8.5, 3.4), (21.0, 5.2), (37.0, 7.2)]   # Ballen: Weg s entlang der Fahne, Radius (px)
HORIZON_Y = 99
QUAY_Y = 200                    # erste Pflasterzeile

# Lichtkegel: Länge links/rechts, Breite, Abstandsstufen
BEAM_LEFT, BEAM_RIGHT = 180, 44
BEAM_BIN = 20
BEAM_WIDEN = 0.05
BEAM_HALF0 = 1.8               # halbe Kegelhöhe direkt an der Lampe
BEAM_GAIN = 0.8                # Stärke des Lichts (Anteil der Lichtfarbe, additiv)
BEAM_FALLOFF = 1.3             # Abfall entlang des Kegels: (1 - d/L)^FALLOFF
BEAM_LIGHT_E = (255, 214, 150)
BEAM_LIGHT_N = (255, 226, 170)

# Grobe Bereiche (Szenenkoordinaten), Rest entscheidet die Farbe
SEA = [(44, 99), (426, 99), (426, 199), (60, 199), (60, 150), (44, 140)]
COTTAGE = [(0, 37), (22, 37), (22, 46), (50, 86), (60, 92), (60, 200), (0, 200)]
TOWER = [(372, 32), (388, 32), (388, 92), (372, 92)]
REFLECTION = [(360, 122), (402, 122), (402, 199), (360, 199)]     # Spiegelung des Leuchtturms im Wasser
# Felsen der Landzunge bis zur Wasserlinie (von Hand am 9-fach vergrößerten Abendbild nachgezogen)
HEADLAND = [(298, 112), (302, 106), (312, 104), (318, 102), (328, 98), (340, 95), (350, 90), (360, 85), (426, 80),
            (426, 120), (400, 120), (380, 119), (360, 118), (345, 117), (330, 115), (310, 114), (298, 113)]
LEFT_ROCKS = [(80, 128), (86, 124), (96, 125), (104, 127), (112, 128), (120, 131), (124, 135), (122, 138), (80, 138)]
# Gegenstände im Wasser, die nachts ebenfalls blau sind (Bootsrümpfe, Felsen, Ufer): als Polygone ausgenommen
NOT_WATER = {
    'ufer_links': [(38, 99), (80, 99), (80, 141), (38, 141)],
    'pfahl_b1_links': [(164, 143), (173, 143), (173, 200), (164, 200)],
    'rumpf_b1': [(170, 150), (193, 150), (193, 141), (212, 141), (212, 150), (220, 150), (226, 153), (226, 166),
                 (222, 174), (215, 180), (176, 180), (170, 176)],
    'mast_b1': [(188, 111), (193, 111), (193, 150), (188, 150)],
    'mast_b1_2': [(198, 125), (203, 125), (203, 150), (198, 150)],
    'pfahl_b1_rechts': [(212, 141), (220, 141), (220, 162), (212, 162)],
    'mitte': [(225, 152), (244, 152), (244, 178), (236, 178), (236, 162), (225, 162)],
    'rumpf_b2': [(237, 160), (250, 158), (296, 160), (298, 168), (296, 178), (290, 186), (245, 187), (238, 178)],
    'pfahl_b2_a': [(267, 143), (275, 143), (275, 166), (267, 166)],
    'pfahl_b2_b': [(284, 160), (293, 160), (293, 199), (284, 199)],
}
NOT_WATER_LINES = {'takelage_1': [(188, 118), (181, 152)], 'takelage_2': [(200, 128), (208, 148)]}
WAVE_ROWS = 4                   # Wasserzeilen über der Kaikante mit Wellen
WAVE_NIGHT = 0.6                # Stärke des Wellenkamms in der Nacht- und Regenpalette (Abend = 1)
RAIN_FRONT = (280, 168, 426, 230)   # Bereich (x0, y0, x1, y1 exklusiv), in dem Regen vor dem Dachs fällt (Laufweg)
RAIN_FRONT_LIT = [1, 0, 0, 0, 0]    # Regenphasen, die auf der Figur erscheinen (nur der helle Tropfenkopf)


# Oberfläche: 0 Fläche, 1 Rahmen hell, 2 Rahmen dunkel, 3 Schrift, 4..9 Goldrampe (Zyklus, symmetrisch),
# 10 Gold fest (Auswahl), 11 Gold gedämpft (Ziffern)
UI_COLORS = [(18, 16, 44), (126, 112, 178), (6, 5, 18), (232, 220, 192),
             (128, 74, 24), (182, 118, 36), (230, 170, 60), (255, 224, 136), (230, 170, 60), (182, 118, 36),
             (250, 206, 102), (176, 132, 70)]
TIMELINE = {'night': [1.4, 3.4], 'rain': [4.0, 5.0], 'beam_period': 4.0, 'beam_angle0': 2.6}


def poly(points, w=W, h=H):
    m = Image.new('L', (w, h), 0)
    ImageDraw.Draw(m).polygon(points, fill=255)
    return np.asarray(m) > 0


def load():
    out = []
    for n in ('evening', 'night'):
        im = Image.open(STYLE / f'assets/raw/bg_{n}.png').convert('RGB').resize((W, H_FULL), Image.BOX)
        out.append(np.asarray(im).astype(np.float64)[CROP_Y:CROP_Y + H])
    return out


def local_median(lum, r=2):
    p = np.pad(lum, r, mode='edge')
    win = np.lib.stride_tricks.sliding_window_view(p, (2 * r + 1, 2 * r + 1))
    return np.median(win.reshape(lum.shape + (-1,)), -1)


def masks(E, N):
    yy, xx = np.mgrid[0:H, 0:W]
    he, se, ve = hsv(E)
    hn, sn, vn = hsv(N)
    warm_e = (he < 65) | (he > 330)
    m = {}
    sea = poly(SEA)
    # Wasser über die Nachtfarbe: gesättigtes Blau oder silbriger Mondstreifen (Nachtbild), nicht Holz/Boot/Stein
    blue_n = (hn >= 200) & (hn <= 262) & ((sn > 0.48) | ((vn > 0.45) & (sn > 0.22)))
    # Spiegelung des Leuchtturms: nachts warm, trotzdem Wasser
    refl = poly(REFLECTION) & (vn > 0.08)
    nw = Image.new('L', (W, H), 0)
    dr = ImageDraw.Draw(nw)
    for pts in list(NOT_WATER.values()) + [HEADLAND, LEFT_ROCKS]:
        dr.polygon(pts, fill=255)
    for pts in NOT_WATER_LINES.values():
        dr.line(pts, fill=255, width=1)
    not_water = np.asarray(nw) > 0
    sea &= ~not_water
    water = sea & (blue_n | refl)
    # einzelne Wasserpixel in Gegenständen und Gegenstandspixel im Wasser bereinigen (Mehrheit 3x3)
    for _ in range(2):
        p = np.pad(water, 1)
        cnt = sum(p[1 + dy:1 + dy + H, 1 + dx:1 + dx + W].astype(int) for dy in (-1, 0, 1) for dx in (-1, 0, 1))
        water = sea & ((water & (cnt >= 3)) | (~water & (cnt >= 7) & blue_n) | refl)
    m['not_water'] = not_water
    m['sea'] = sea
    m['water_all'] = water
    # Ufer für die Wellen: nur Felsen der Landzunge, Uferfelsen links und die Kaikante (nicht Pfähle und Boote)
    shore = (poly(HEADLAND) | poly(LEFT_ROCKS)) & ~water
    dist = distance_to(shore, 6)
    # Brandung nur an der Wasserlinie: Ufer liegt in derselben Spalte 1-3 Zeilen darüber. Ohne diese Bedingung
    # lief die Welle auch links und oben um die Spitze der Landzunge und stand nachts als heller Haken im Wasser.
    below_shore = np.zeros_like(shore)
    for d in range(1, 4):
        below_shore[d:] |= shore[:-d]
    near_quay = (yy >= QUAY_Y - WAVE_ROWS) & (yy < QUAY_Y)
    m['waves'] = water & (((dist <= 2) & below_shore) | near_quay) & (yy >= HORIZON_Y + 6)
    m['wave_dist'] = np.where(near_quay, QUAY_Y - yy, dist)
    m['water'] = water & ~m['waves']
    # Leuchtfeuer: helle, warme Pixel im Glas
    x0, y0, x1, y1 = LAMP_BOX
    box = (xx >= x0) & (xx <= x1) & (yy >= y0) & (yy <= y1)
    m['lamp'] = box & (ve > 0.55) & warm_e
    # Laterne: Glas (sehr hell) und Lichthof (warm, nah, heller als in der Umgebung)
    d = np.hypot(xx - LANTERN[0], (yy - LANTERN[1]) * 0.8)
    m['lantern_core'] = (d <= 6.5) & warm_e & (ve > 0.78)
    m['lantern_halo'] = (d <= 11) & ~m['lantern_core'] & warm_e & (ve > 0.42) & (np.abs(xx - 74.5) > 4)
    # Fenster: Häuschen links und Haus am Leuchtturm
    win1 = (xx >= 16) & (xx <= 28) & (yy >= 98) & (yy <= 121)
    win2 = (xx >= 388) & (xx <= 394) & (yy >= 78) & (yy <= 86)
    m['window'] = (win1 | win2) & warm_e & (ve > 0.6) & (se > 0.35)
    # Sterne: einzelne helle Pixel im oberen Himmel, in einem der beiden Bilder
    lum_e = E @ np.array([0.299, 0.587, 0.114])
    lum_n = N @ np.array([0.299, 0.587, 0.114])
    sky_top = (yy < 34) & ~poly(COTTAGE)
    # Wolkenränder sind warm oder gesättigt, Sterne weißlich
    warm_any = warm_e & (se > 0.3) | ((hn < 65) | (hn > 300)) & (sn > 0.3)
    def pointlike(lum):
        # heller als die Umgebung und höchstens 2 weitere Kandidaten im 5x5-Feld (keine Wolkenkanten)
        c = sky_top & (lum > local_median(lum, 3) + 26) & ~warm_any
        p = np.pad(c, 2)
        cnt = sum(p[2 + dy:2 + dy + H, 2 + dx:2 + dx + W].astype(int) for dy in range(-2, 3) for dx in range(-2, 3))
        return c & (cnt <= 3)
    st_e = pointlike(lum_e)
    st_n = pointlike(lum_n)
    m['stars'] = st_e | st_n
    m['star_class'] = np.where(st_e, 0, 1)      # 0: schon abends sichtbar, 1: erst nachts
    m['cottage'] = poly(COTTAGE)
    m['tower'] = poly(TOWER)
    # Rotes Band des Leuchtturms: abends karmin bis violett, nachts violett; der Himmel daneben ist abends ebenso
    # rot, nachts aber blau (Farbton 220-235) und fällt dadurch heraus. Bekommt eigene statische Einträge, sonst
    # mittelt die gemeinsame 6D-Quantisierung das Band zu Braungrau (zu wenige Pixel für einen eigenen Eintrag).
    m['band'] = m['tower'] & ((he >= 290) | (he <= 5)) & (hn >= 262) & (hn <= 352) & (se > 0.25)
    # dazu die sonnenbeschienene linke Kante des Bands: in beiden Bildern kräftig rot (die weiße Wand darunter und
    # darüber ist abends orange, Farbton um 25, und fällt heraus)
    m['band'] |= m['tower'] & ((he >= 350) | (he <= 15)) & (se > 0.7) & ((hn >= 340) | (hn <= 15)) & (sn > 0.4)
    for k in ('lamp', 'lantern_core', 'lantern_halo', 'window', 'stars'):
        for w in ('water', 'waves'):
            m[w] &= ~m[k]
    return m


def smoke_path():
    """Mittellinie der Fahne ab dem Topf: steigt erst fast senkrecht und biegt dann mit dem Wind nach rechts
    (Winkel zur Senkrechten wächst bis SMOKE_BEND). Punkte (x, y, Weg s) im Abstand 0,25 px."""
    ds, pts = 0.25, []
    x, y = CHIMNEY[0], CHIMNEY[1] - 0.5
    for i in range(int(70 / ds)):
        s = i * ds
        th = np.radians(SMOKE_BEND) * min(1.0, s / 36.0) ** 1.3
        pts.append((x, y, s))
        x += np.sin(th) * ds
        y -= np.cos(th) * ds
    return np.array(pts)


# Ein Ballen = Hauptkreis + vier kleinere Kreise (Blumenkohl-Umriss): (dx, dy, Radius) in Einheiten des Radius
PUFF_LOBES = [(0.0, 0.0, 1.0), (-0.6, -0.2, 0.6), (0.35, -0.55, 0.62), (0.7, 0.2, 0.52), (-0.15, 0.5, 0.55)]


def smoke_field():
    """Rauchfahne als Feld: Dichte 0..1, Schatten 0/1 und Weg s entlang der Fahne (für die Phase). Wind nach
    rechts. Drei Ballen mit wachsendem Radius entlang der gebogenen Mittellinie, dazwischen ein schmaler Faden.
    Innen rechts unten liegt je Ballen ein dunklerer Kern (Schattenseite), Rand und Oberseite sind heller.
    Der Umriss ist fest; die Phase läuft entlang s, damit wandern Verdichtungen per Palettenrotation nach oben."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    pts = smoke_path()
    dens = np.zeros((H, W))
    shade = np.full((H, W), -1.0)
    s_map = np.zeros((H, W))
    reg = (yy < CHIMNEY[1]) & (xx < 110)
    ys, xs = np.nonzero(reg)
    d2 = (xs[:, None] - pts[None, :, 0]) ** 2 + (ys[:, None] - pts[None, :, 1]) ** 2
    near = d2.argmin(1)
    dpath = np.sqrt(d2[np.arange(len(near)), near])
    s = pts[near, 2]
    s_map[ys, xs] = s
    # Faden zwischen den Ballen: dünn und schwach, endet am letzten Ballen
    last = SMOKE_PUFFS[-1][0]
    d = np.clip(1 - dpath / (1.0 + 0.04 * s), 0, 1) * 0.35 * (s <= last)
    sh = np.full(len(ys), -1.0)
    for k, (c, r) in enumerate(SMOKE_PUFFS):
        px, py = np.interp(c, pts[:, 2], pts[:, 0]), np.interp(c, pts[:, 2], pts[:, 1])
        dk = np.zeros(len(ys))
        for lx, ly, lr in PUFF_LOBES:
            dc = np.hypot(xs - (px + lx * r), ys - (py + ly * r)) / (lr * r)
            dk = np.maximum(dk, np.clip(1 - dc, 0, 1) ** 0.6)
        dk *= 1 - 0.15 * k                          # oben etwas dünner
        # Schattenseite: rechts unten im Inneren des Ballens (Licht von links oben)
        side = ((ys - py) + 0.5 * (xs - px)) / r
        better = dk > d
        sh = np.where(better, np.where(dk > 0.3, side, -1.0), sh)
        d = np.maximum(d, dk)
    dens[ys, xs] = d
    shade[ys, xs] = sh
    dens[yy > CHIMNEY[1] - 1] = 0
    return dens, shade, s_map


def beam_field(m):
    """Lichtkegel links und rechts der Lampe: Stärke (0..1), Abstand und Seite."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    dx, dy = xx - LAMP[0], yy - LAMP[1]
    dist = np.abs(dx)
    left = dx < 0
    L = np.where(left, BEAM_LEFT, BEAM_RIGHT)
    u = np.clip(dist / L, 0, 1)
    half = np.maximum(0.7, BEAM_HALF0 + BEAM_WIDEN * dist * (1.0 - 0.9 * u ** 2))
    edge = np.clip(1.0 - np.abs(dy) / half, 0, 1) ** 0.6
    strength = edge * (dist <= L)
    x0, y0, x1, y1 = LAMP_BOX
    beside_glass = (yy >= y0) & (yy <= y1) & ((xx < x0) | (xx > x1))
    block = m['tower'] & ~beside_glass
    strength[block | m['lamp'] | m['cottage']] = 0
    strength[dist < 1] = 0
    return strength, dist, left


def quantize_static(F, mask, cent, Lmap):
    """Nächster Eintrag in 6D, sparsames geordnetes Dithering nur in ruhigen Verläufen zwischen nahen Einträgen."""
    Hh, Ww = mask.shape
    idx = np.zeros((Hh, Ww), np.int32)
    ys, xs = np.nonzero(mask)
    f = F[ys, xs]
    d = ((f[:, None, :] - cent[None]) ** 2).sum(-1)
    order = np.argsort(d, 1)
    c1, c2 = order[:, 0], order[:, 1]
    p1, p2 = cent[c1], cent[c2]
    seg = p2 - p1
    t = np.clip(((f - p1) * seg).sum(-1) / np.maximum((seg ** 2).sum(-1), 1e-9), 0, 1)
    gap = np.sqrt((seg ** 2).sum(-1))
    p = np.pad(Lmap, 1, mode='edge')
    win = np.lib.stride_tricks.sliding_window_view(p, (3, 3)).reshape(Hh, Ww, 9)
    calm = (win.std(-1) < 0.016)[ys, xs]
    th = BAYER4[ys % 4, xs % 4]
    use2 = calm & (gap < 0.07) & (t > th)
    idx[ys, xs] = np.where(use2, c2, c1)
    return idx


def cover_tones(cand, idx, pal_feat, T, thr, weight=None):
    """Wählt gierig T statische Einträge, die möglichst viele Kandidatenpixel abdecken (6D-Abstand <= thr), und
    gibt (gewählte Einträge, Zuordnung je Kandidatenpixel: Platz 0..T-1 oder -1) zurück. weight: Gewicht je Pixel
    (z. B. 1/Größe der Bildzone, damit Himmel, Meer und Kai gleichermaßen Regen bekommen)."""
    ids = idx[cand]
    u, inv = np.unique(ids, return_inverse=True)
    c = np.bincount(inv, weights=None if weight is None else weight[cand], minlength=len(u))
    fu = pal_feat[u]
    near = np.sqrt(((fu[:, None] - fu[None]) ** 2).sum(-1)) <= thr     # near[a, b]: Pixel mit u[a] passt zu u[b]
    chosen = []
    left = np.ones(len(u), bool)
    for _ in range(T):
        gain = (near & left[:, None]).T @ c                             # je Kandidat b: abgedeckte Pixel
        b = int(np.argmax(gain))
        if gain[b] <= 0:
            break
        chosen.append(b)
        left &= ~near[:, b]
    slot = np.full(len(u), -1)
    best = np.full(len(u), np.inf)
    for k, b in enumerate(chosen):
        d = np.sqrt(((fu - fu[b]) ** 2).sum(-1))
        ok = (d <= thr) & (d < best)
        slot[ok] = k; best[ok] = d[ok]
    lut = dict(zip(u.tolist(), slot.tolist()))
    return [int(u[b]) for b in chosen], np.array([lut[i] for i in ids.tolist()])


def feat(E, N):
    return np.concatenate([oklab(E), oklab(N)], -1)


def brighten(rgb, amt, toward=None):
    """Heller in Oklab (amt in L-Einheiten); optional zur Farbe toward hin mischen (Anteil = amt*2)."""
    lab = oklab(np.asarray(rgb, np.float64)[None])[0]
    lab = lab.copy()
    lab[0] = np.clip(lab[0] + amt, 0, 1)
    out = oklab_to_rgb(lab[None])[0]
    if toward is not None and amt > 0:
        k = min(1.0, amt * 2.0)
        out = out * (1 - k) + np.asarray(toward, np.float64) * k
    return np.clip(out, 0, 255)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview')
    args = ap.parse_args()
    ART.mkdir(parents=True, exist_ok=True)
    E, N = load()
    m = masks(E, N)
    F = feat(E, N)
    yy, xx = np.mgrid[0:H, 0:W]
    idx = np.full((H, W), -1, np.int32)
    PE = np.zeros((256, 3)); PN = np.zeros((256, 3)); PR = np.zeros((256, 3))
    ranges = []          # Rotationsbereiche: {name, start, len, rate, dir}
    rng = np.random.default_rng(7)

    def set3(i, ce, cn, cr=None):
        PE[i] = ce; PN[i] = cn; PR[i] = cn if cr is None else cr

    # ---------------- Oberfläche: feste Töne (in allen drei Paletten gleich) + Goldrampe als Zyklus für den Titel
    u0 = RANGES['ui'][0]
    for i, c in enumerate(UI_COLORS):
        set3(u0 + i, c, c, c)
    ranges.append({'name': 'ui_gold', 'start': u0 + 4, 'len': 6, 'rate': 10.0, 'dir': 1})

    # ---------------- Leuchtfeuer: 4 Einträge nach Spalte, ein heller Fleck läuft durch (Drehlinse)
    l0 = RANGES['lamp'][0]
    lm = m['lamp']
    idx[lm] = l0 + (xx[lm] - LAMP_BOX[0]) % 4
    base_e = E[lm].mean(0); base_n = N[lm].mean(0)
    for j, f in enumerate([1.0, 0.82, 0.68, 0.82]):
        set3(l0 + j, np.clip(base_e * f + (30 if j == 0 else 0), 0, 255),
             np.clip(base_n * f + (40 if j == 0 else 0), 0, 255))
    ranges.append({'name': 'lamp', 'start': l0, 'len': 4, 'rate': 'beam', 'dir': 1})

    # ---------------- Laterne: Glas 2 Töne, Lichthof 2 Töne (Flackern berechnet)
    t0 = RANGES['lantern'][0]
    for k, key in ((0, 'lantern_core'), (2, 'lantern_halo')):
        mk = m[key]
        cent, lbl = kmeans_vec(F[mk], 2, seed=3 + k)
        order = np.argsort(cent[:, 0])
        rank = np.empty(2, int); rank[order] = np.arange(2)
        idx[mk] = t0 + k + rank[lbl]
        for j in range(2):
            sel = rank[lbl] == j
            set3(t0 + k + j, E[mk][sel].mean(0), N[mk][sel].mean(0))
    # ---------------- Fenster
    f0 = RANGES['window'][0]
    mk = m['window']
    cent, lbl = kmeans_vec(F[mk], 2, seed=9)
    rank = np.argsort(np.argsort(cent[:, 0]))
    idx[mk] = f0 + rank[lbl]
    for j in range(2):
        sel = rank[lbl] == j
        set3(f0 + j, E[mk][sel].mean(0), N[mk][sel].mean(0))

    # ---------------- Sterne: Klasse 0 (abends schon da), Klasse 1 (erst nachts); 3 Phasen funkeln
    s0 = RANGES['stars'][0]
    sm = m['stars']
    ph = rng.integers(0, STAR_P, sm.sum())
    cls = m['star_class'][sm]
    idx[sm] = s0 + cls * STAR_P + ph
    sky_e = np.median(E[(yy < 30) & ~sm & ~m['cottage']], 0)
    sky_n = np.median(N[(yy < 30) & ~sm & ~m['cottage']], 0)
    for c in range(STAR_C):
        sel = cls == c
        ce = E[sm][sel].mean(0) if c == 0 else sky_e
        cn = N[sm][sel].mean(0)
        for j, f in enumerate([1.0, 0.72, 0.5]):
            e = sky_e + (ce - sky_e) * f + (np.array([40, 40, 30]) if (j == 0 and c == 0) else 0)
            n = sky_n + (cn - sky_n) * f + (np.array([50, 50, 40]) if j == 0 else 0)
            # Regen: Wolkendecke, Sterne aus
            set3(s0 + c * STAR_P + j, np.clip(e, 0, 255), np.clip(n, 0, 255), sky_n * 0.92)
    ranges.append({'name': 'stars0', 'start': s0, 'len': STAR_P, 'rate': 2.5, 'dir': 1})
    ranges.append({'name': 'stars1', 'start': s0 + STAR_P, 'len': STAR_P, 'rate': 2.0, 'dir': -1})

    # ---------------- Wasser: Tonstufen (Abend+Nacht gemeinsam), Phase je Pixel aus Strichlänge und Zeilenversatz
    w0 = RANGES['water'][0]
    wm = m['water']
    cent, lbl = kmeans_vec(F[wm], WATER_T, seed=5)
    order = np.argsort(cent[:, 0] + cent[:, 3])
    rank = np.argsort(order)
    tone = rank[lbl]
    rowlen = rng.integers(2, 6, H)
    rowoff = rng.integers(0, WATER_P, H)
    rowdir = np.where(rng.random(H) < 0.5, 1, -1)
    phase = (rowdir[:, None] * ((xx + rowoff[:, None] * 3) // rowlen[:, None]) + rowoff[:, None]) % WATER_P
    idx[wm] = w0 + tone * WATER_P + phase[wm]
    prof = [0.0, 0.0, -0.03, 0.0, 0.06, 0.13]
    prof_rain = [0.07, -0.03, 0.0, 0.12, -0.02, 0.04]     # Regen: unruhige Oberfläche, Tropfen schlagen auf
    for k in range(WATER_T):
        sel = tone == k
        be, bn = E[wm][sel].mean(0), N[wm][sel].mean(0)
        for j, a in enumerate(prof):
            set3(w0 + k * WATER_P + j, brighten(be, a * 1.0), brighten(bn, a * 0.9),
                 brighten(bn * 0.9, prof_rain[j], np.array([150, 165, 205]) if prof_rain[j] > 0.1 else None))
    for k in range(WATER_T):
        ranges.append({'name': f'water{k}', 'start': w0 + k * WATER_P, 'len': WATER_P, 'rate': 7.5, 'dir': 1})

    # ---------------- Wellen am Ufer: Phase aus dem Abstand zum Ufer -> helle Linie läuft auf das Ufer zu
    v0 = RANGES['waves'][0]
    vm = m['waves']
    cent, lbl = kmeans_vec(F[vm], WAVE_T, seed=6)
    rank = np.argsort(np.argsort(cent[:, 0] + cent[:, 3]))
    tone = rank[lbl]
    wob = np.round(1.2 * np.sin(xx / 5.0 + 0.7 * np.sin(xx / 13.0))).astype(int)
    vph = (m['wave_dist'] + wob) % WAVE_P
    idx[vm] = v0 + tone * WAVE_P + vph[vm]
    wprof = [0.16, 0.07, 0.0, -0.02, 0.0, 0.03]
    foam_e, foam_n = np.array([235, 200, 225]), np.array([170, 190, 240])
    for k in range(WAVE_T):
        sel = tone == k
        be, bn = E[vm][sel].mean(0), N[vm][sel].mean(0)
        for j, a in enumerate(wprof):
            # nachts schwächer: der Kamm soll eine Linie im Wasser bleiben, kein heller Umriss
            set3(v0 + k * WAVE_P + j, brighten(be, a, foam_e if a > 0.1 else None),
                 brighten(bn, a * WAVE_NIGHT, foam_n if a > 0.1 else None))
        # Phase = Abstand zum Ufer; rückwärts drehen, damit der Kamm zu kleineren Abständen (aufs Ufer zu) läuft
        ranges.append({'name': f'waves{k}', 'start': v0 + k * WAVE_P, 'len': WAVE_P, 'rate': 6.0, 'dir': -1})

    # ---------------- Rauch: Fahne aus dem Schornstein, Dichte in 2 Stufen, Phase entlang der Fahne
    r0 = RANGES['smoke'][0]
    dens, shade, spath = smoke_field()
    th = BAYER4[yy % 4, xx % 4]
    free = idx < 0
    smk = free & (((dens > 0.06) & (dens > th * 0.4)) | (dens > 0.3))
    lvl = np.where(shade > -0.05 + (th - 0.5) * 0.5, 1, 0)   # heller Rand / dunkler Kern, gedithert
    sph = (np.floor(spath / 3.0).astype(int)) % SMOKE_P
    idx[smk] = r0 + lvl[smk] * SMOKE_P + sph[smk]
    # Rand heller und dünner, Kern dichter und grauer (dunkler als der Rand, heller als der Himmel dahinter)
    smoke_e = [np.array([218, 198, 222]), np.array([96, 80, 116])]
    smoke_n = [np.array([150, 156, 192]), np.array([84, 88, 120])]
    alpha = [0.5, 0.6]
    puff = [1.0, 0.92, 0.76, 0.62, 0.62, 0.76]
    for k in range(SMOKE_T):
        sel = smk & (lvl == k)
        be, bn = E[sel].mean(0), N[sel].mean(0)
        for j, p in enumerate(puff):
            a = alpha[k] * p
            set3(r0 + k * SMOKE_P + j, be * (1 - a) + smoke_e[k] * a, bn * (1 - a) + smoke_n[k] * a,
                 bn * (1 - a * 0.7) + smoke_n[k] * a * 0.7)
        # Phase s wächst nach oben; vorwärts drehen, damit die Verdichtung zu größerem s (nach oben) wandert
        ranges.append({'name': f'smoke{k}', 'start': r0 + k * SMOKE_P, 'len': SMOKE_P, 'rate': 5.0, 'dir': 1})
    m['smoke'] = smk

    # ---------------- Statische Farben (k-means in 6D über alle übrigen Pixel)
    st0, st1 = RANGES['static']
    rest = idx < 0
    Lmap = (oklab(E)[..., 0] + oklab(N)[..., 0]) / 2
    # Rotes Band: BAND_N eigene Einträge (eigenes k-means nur über die Bandpixel), der Rest teilt sich die übrigen
    band = rest & m['band']
    cent_main, _ = kmeans_vec(F[rest & ~band], st1 - st0 - BAND_N, iters=18, seed=1)
    cent_band, _ = kmeans_vec(F[band], BAND_N, iters=18, seed=2)
    cent = np.concatenate([cent_main, cent_band])
    is_band = np.r_[np.zeros(len(cent_main), bool), np.ones(BAND_N, bool)]
    order = np.argsort(cent[:, 0])
    cent, is_band = cent[order], is_band[order]
    ids_main, ids_band = np.flatnonzero(~is_band), np.flatnonzero(is_band)
    q = quantize_static(F, rest & ~band, cent[~is_band], Lmap)
    idx[rest & ~band] = st0 + ids_main[q[rest & ~band]]
    qb = quantize_static(F, band, cent[is_band], Lmap)
    idx[band] = st0 + ids_band[qb[band]]
    print('Band: %d Pixel auf Einträge %s' % (band.sum(), (st0 + ids_band).tolist()))
    # Palettenfarbe = Mittel der zugeordneten Pixel (in RGB, beide Bilder)
    for j in range(st1 - st0):
        sel = rest & (idx == st0 + j)
        if sel.any():
            set3(st0 + j, E[sel].mean(0), N[sel].mean(0))
        else:
            set3(st0 + j, oklab_to_rgb(cent[j, :3][None])[0], oklab_to_rgb(cent[j, 3:][None])[0])
    # Regen-Palette: statische Farben unter der Wolkendecke etwas dunkler und kühler (nur Himmel/Wasser/Stein)
    static_ids = np.arange(st0, st1)
    for i in static_ids:
        n = PN[i]
        lab = oklab(n[None])[0]
        if lab[0] < 0.62:          # Lichter (Fenster, Laterne) bleiben
            PR[i] = np.clip(n * 0.86 + np.array([4, 6, 12]), 0, 255)

    # ---------------- Lichtkegel: nur Pixel, deren statischer Eintrag einer der häufigsten 2 je Stufe ist
    b0 = RANGES['beam'][0]
    idx_before = idx.copy()        # zum Messen: Umlegen auf Zyklus-Töne darf ohne Regen/Licht kaum auffallen
    strength, bdist, bleft = beam_field(m)
    nb_left = int(np.ceil(BEAM_LEFT / BEAM_BIN)); nb_right = int(np.ceil(BEAM_RIGHT / BEAM_BIN))
    halo_r = np.hypot(xx - LAMP[0], (yy - LAMP[1]) * 1.3)
    # Stufe: 0 = Hof um die Lampe, 1..nb_left links, nb_left+1.. rechts; Stufengrenzen gedithert
    frac = bdist / BEAM_BIN + (th - 0.5) * 0.9
    binl = np.clip(np.floor(frac).astype(int), 0, nb_left - 1)
    binr = np.clip(np.floor(frac).astype(int), 0, nb_right - 1)
    bins = np.where(bleft, 1 + binl, 1 + nb_left + binr)
    halo = (halo_r <= 5.5) & (th < 1.15 - halo_r / 5.5) & ~m['lamp'] & ~(m['tower'] & (yy > LAMP_BOX[3] + 1))
    bins = np.where(halo, 0, bins)
    member = ((strength > th * 0.9 + 0.05) | halo) & (idx >= st0)
    nbins = 1 + nb_left + nb_right
    assert nbins * BEAM_T <= RANGES['beam'][1] - b0, nbins
    pal_feat = np.concatenate([oklab(PE), oklab(PN)], -1)
    beam_bins = []
    covered = 0; total = 0
    for b in range(nbins):
        cand = member & (bins == b)
        total += int(cand.sum())
        side = 'halo' if b == 0 else ('left' if b <= nb_left else 'right')
        d0 = 0 if b == 0 else ((b - 1) * BEAM_BIN if side == 'left' else (b - 1 - nb_left) * BEAM_BIN)
        if not cand.any():
            beam_bins.append({'bin': b, 'side': side, 'd': d0, 'tones': [], 'start': b0 + b * BEAM_T, 'n': 0})
            continue
        top, slot = cover_tones(cand, idx, pal_feat, BEAM_T, BEAM_COVER_THR)
        ys, xs = np.nonzero(cand)
        for k, sid in enumerate(top):
            e = b0 + b * BEAM_T + k
            sel = slot == k
            covered += int(sel.sum())
            idx[ys[sel], xs[sel]] = e
            set3(e, PE[sid], PN[sid], PR[sid])
        beam_bins.append({'bin': b, 'side': side, 'd': d0 + BEAM_BIN / 2 if b else 0, 'tones': top,
                          'start': b0 + b * BEAM_T, 'n': len(top)})
    print(f'Lichtkegel: {covered} von {total} Kegelpixeln belegt ({covered / max(total, 1):.0%})')

    # ---------------- Regen: schräge Bahnen; ein Bahnpixel wird Regen-Eintrag, wenn sein statischer Eintrag einer
    # der RAIN_T häufigsten in den Bahnen ist (Kopie der statischen Farbe -> ohne Regen exakt gleiches Bild)
    a0 = RANGES['rain'][0]
    slope = 0.28                 # x-Versatz je Zeile (Wind von links)
    spacing = 4
    seg = 5                      # Pixel je Tropfenabschnitt entlang der Bahn
    track_off = rng.integers(0, 10 ** 6, 400)
    tx = np.floor(xx - yy * slope).astype(int)
    on_track = (tx % spacing) == 0
    tid = (tx // spacing) % 400
    # Bahnen in Abschnitten von 3 Tropfen unterbrechen (40 % fallen weg), damit kein gleichmäßiges Raster entsteht
    chunk = ((yy // (seg * RAIN_P * 3)) * 7919 + tid * 104729) % 1000
    keep = chunk < 700
    rain_zone = on_track & (idx >= st0) & keep
    zone = np.select([yy < 40, yy < HORIZON_Y, yy < QUAY_Y], [0, 1, 2], 3)
    zsize = np.array([max(1, (rain_zone & (zone == z)).sum()) for z in range(4)])
    top, slot = cover_tones(rain_zone, idx, pal_feat, RAIN_T, COVER_THR, weight=1.0 / zsize[zone])
    rph = ((yy // seg) + track_off[tid]) % RAIN_P
    rain_tones = top
    ys, xs = np.nonzero(rain_zone)
    rain_px = int((slot >= 0).sum())
    drop_n = np.array([150, 165, 205]); drop_l = [0.7, 0.32, 0, 0, 0]
    for k, sid in enumerate(top):
        sel = slot == k
        idx[ys[sel], xs[sel]] = a0 + k * RAIN_P + rph[ys[sel], xs[sel]]
        for j in range(RAIN_P):
            e = a0 + k * RAIN_P + j
            lit = PR[sid] + (drop_n - PR[sid]) * drop_l[j]
            set3(e, PE[sid], PN[sid], lit)
        ranges.append({'name': f'rain{k}', 'start': a0 + k * RAIN_P, 'len': RAIN_P, 'rate': 30.0, 'dir': 1})
    print(f'Regen: {rain_px} Pixel auf Bahnen ({rain_px / rain_zone.sum():.0%} der Bahnpixel)')
    # Regen vor der Figur: Bahnkarte (R = Regen-Eintrag, G = 255 auf einer Bahn) mit denselben Bahnen und Phasen wie
    # im Hintergrund, auch dort, wo der Hintergrund keine Regenpixel hat (Wasser). Der Shader des Dachses legt auf
    # seine eigenen Pixel den Regen-Eintrag, wenn dieser gerade den hellen Tropfenkopf zeigt (Deckkraft schreibt
    # cycler.gd in den Alphakanal der Palette, mal Regenstärke). Tropfen laufen so hinter und vor der Figur weiter.
    fx0, fy0, fx1, fy1 = RAIN_FRONT
    is_rain = (idx >= a0) & (idx < RANGES['rain'][1])
    kq = int(np.bincount((idx[is_rain & (zone == 3)] - a0) // RAIN_P, minlength=RAIN_T).argmax())
    tone = np.where(is_rain, (idx - a0) // RAIN_P, kq)
    fsel = on_track & keep & (xx >= fx0) & (xx < fx1) & (yy >= fy0) & (yy < fy1)
    front = np.zeros((H, W, 3), np.uint8)
    front[fsel, 0] = (a0 + tone * RAIN_P + rph)[fsel]
    front[fsel, 1] = 255
    assert (front[fsel & is_rain, 0] == idx[fsel & is_rain]).all()
    Image.fromarray(front, 'RGB').save(ART / 'rain_front.png')
    print(f'Regen vor der Figur: {int(fsel.sum())} Bahnpixel im Bereich {RAIN_FRONT}')

    assert (idx >= 0).all() and idx.max() < 256
    moved = idx != idx_before
    for nm, P in (('Abend', PE), ('Nacht', PN)):
        de = np.sqrt(((oklab(P[idx][moved]) - oklab(P[idx_before][moved])) ** 2).sum(-1))
        print(f'Umgelegte Pixel ({nm}, ohne Regen/Licht): {moved.sum()}, Oklab-Abstand mittel {de.mean():.4f}, '
              f'max {de.max():.4f}, Anteil exakt {np.mean(de < 1e-6):.0%}')
    # ---------------- Ausgabe
    PE8, PN8, PR8 = [np.clip(np.round(p), 0, 255).astype(np.uint8) for p in (PE, PN, PR)]
    Image.fromarray(idx.astype(np.uint8), 'L').save(ART / 'bg_index.png')
    meta = {
        'size': [W, H], 'crop_y': CROP_Y, 'ranges_alloc': RANGES,
        'palettes': {'evening': [hexs(c) for c in PE8], 'night': [hexs(c) for c in PN8],
                     'rain': [hexs(c) for c in PR8]},
        'cycles': ranges,
        'lamp': list(LAMP), 'lantern': list(LANTERN),
        'beam': {'bins': beam_bins, 'left': BEAM_LEFT, 'right': BEAM_RIGHT, 'bin_len': BEAM_BIN,
                 'light_evening': list(BEAM_LIGHT_E), 'light_night': list(BEAM_LIGHT_N),
                 'gain': BEAM_GAIN, 'falloff': BEAM_FALLOFF,
                 'lamp': list(range(*RANGES['lamp']))},
        'flicker': {'lantern_core': [t0, t0 + 1], 'lantern_halo': [t0 + 2, t0 + 3], 'window': [f0, f0 + 1]},
        'rain_tones': rain_tones,
        'rain_front': {'start': a0, 'end': RANGES['rain'][1], 'phase_len': RAIN_P, 'lit': RAIN_FRONT_LIT,
                       'rect': list(RAIN_FRONT)},
        'timeline': TIMELINE,
        'ui': {'fill': 0, 'light': 1, 'dark': 2, 'text': 3, 'gold_ramp': [4, 6], 'gold': 10, 'gold_dim': 11},
    }
    old = ART / 'palette.json'
    if old.exists():
        prev = json.loads(old.read_text())
        for r in ('sprite',):
            s, e = RANGES[r]
            for p in ('evening', 'night', 'rain'):
                meta['palettes'][p][s:e] = prev['palettes'][p][s:e]
        if 'sprite' in prev:
            meta['sprite'] = prev['sprite']
        for p in ('evening', 'night', 'rain'):     # Oberfläche kommt immer aus diesem Skript
            s_, e_ = RANGES['ui']
            meta['palettes'][p][s_:e_] = [hexs(c) for c in UI_COLORS]
    old.write_text(json.dumps(meta, indent=1))
    counts = {k: int(((idx >= s) & (idx < e)).sum()) for k, (s, e) in RANGES.items()}
    print('Pixel je Bereich:', counts)
    ast = STYLE / 'assets'
    for f in ('bg_index.png', 'palette.json'):
        (ast / f).write_bytes((ART / f).read_bytes())
    Image.fromarray(PE8[idx]).save(ast / 'bg_preview_evening.png')
    Image.fromarray(PN8[idx]).save(ast / 'bg_preview_night.png')
    # Abweichung zur Vorlage (Oklab, ohne Zyklusbereiche gemessen)
    le, ln = oklab(PE8[idx].astype(float)), oklab(PN8[idx].astype(float))
    stat = idx >= st0
    print('mittlere Abweichung Oklab Abend %.4f Nacht %.4f' % (
        np.sqrt(((le - oklab(E)) ** 2).sum(-1))[stat].mean(), np.sqrt(((ln - oklab(N)) ** 2).sum(-1))[stat].mean()))
    # Maskenansicht (immer): Wasser, Wellen, Lampe, Laterne, Fenster, Sterne, Rauch, Lichtkegel, Regenbahnen
    ov = PE8[idx].astype(float) * 0.35
    cols = {'water': (0, 200, 255), 'waves': (255, 255, 255), 'lamp': (255, 0, 0), 'lantern_core': (255, 0, 0),
            'lantern_halo': (255, 160, 0), 'window': (0, 255, 0), 'stars': (255, 255, 0), 'smoke': (255, 0, 255)}
    for k, c in cols.items():
        ov[m[k]] = np.array(c) * 0.8
    bm = (idx >= b0) & (idx < RANGES['beam'][1])
    ov[bm] = (255, 255, 160)
    rm = (idx >= a0) & (idx < RANGES['rain'][1])
    ov[rm] = ov[rm] * 0.4 + np.array((120, 255, 120)) * 0.6
    Image.fromarray(ov.astype(np.uint8)).save(ast / 'cycle_masks.png')
    if args.preview:
        pv = pathlib.Path(args.preview); pv.mkdir(parents=True, exist_ok=True)
        for name, P in (('e', PE8), ('n', PN8), ('r', PR8)):
            Image.fromarray(P[idx]).resize((W * 3, H * 3), Image.NEAREST).save(pv / f'quant_{name}.png')
        Image.fromarray(ov.astype(np.uint8)).resize((W * 3, H * 3), Image.NEAREST).save(pv / 'masks.png')
        print('Farben im Bild:', len(np.unique(idx)))


if __name__ == '__main__':
    main()
