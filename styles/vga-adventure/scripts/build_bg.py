#!/usr/bin/env python3
"""Baut aus dem KI-Hintergrund ein echtes 256-Farben-Indexbild mit Farbzyklus-Bereichen.

    .venv/bin/python styles/vga-adventure/scripts/build_bg.py [--preview DIR]

Ablauf:
  1. assets/raw/bg.png (1536x1024) mit BOX auf 320x213 verkleinern (ein Pixel = 4,8 Quellpixel),
     gemalten Schornsteinrauch entfernen (wird in Godot animiert), Zeilen CROP_Y..CROP_Y+152 ausschneiden.
  2. Masken: Wasser (Farbzyklus), Sterne (Funkeln), Leuchtturmlampe, Laterne, Fenster, Lichtkegel.
  3. Eine Palette mit 256 Einträgen für das ganze Bild (Hintergrund, Figur, Oberfläche), siehe RANGES.
     Jeder Eintrag liegt auf dem 6-Bit-Raster des VGA-DAC (64 Stufen je Kanal, 262.144 mögliche Farben), siehe vga6.
  4. Ausgabe nach demo/art/: bg_index.png (Graustufen, Wert = Palettenindex), palette.json
     (Basisfarben + Bereiche), beam.png (Lichtkegel: Stärke, Abstand, Seite), beam_lut.png (256x5:
     Index -> aufgehellter Index in fünf Stufen, für den Lichtkegel ohne Farben außerhalb der Palette).
"""
import argparse, json, pathlib, sys
import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pixgrid import oklab, kmeans  # noqa: E402

STYLE = HERE.parent
RAW = STYLE / 'assets/raw/bg.png'
ART = STYLE / 'demo/art'
W, H_FULL, CROP_Y, H = 320, 213, 20, 152

# Palettenaufteilung (Index-Bereiche, Ende exklusiv)
RANGES = {
    'ui': (0, 12),          # Oberfläche: Schwarz, Verbfarben, Sprechtext, Cursor
    'sprite': (12, 40),     # Figur, Paket, Inventar (build_sprites.py füllt sie)
    'smoke': (40, 44),      # Rauch
    'water': (44, 92),      # 5 blaue + 3 Reflex-Tonstufen x 6 Einträge, Palettenrotation
    'water_edge': (92, 122),  # dieselben 5 blauen Tonstufen mit halbem Glitzern für den Maskenrand
    'lamp': (122, 130),     # Leuchtturmlampe: 8 Einträge, Palettenrotation
    'stars': (130, 134),    # Sterne: 4 Einträge, Palettenrotation
    'lantern': (134, 142),  # Laterne: 4 Glas + 4 Lichthof, Palettenanimation (Flackern)
    'window': (142, 146),   # Fenster: 4 Einträge, Palettenanimation
    'beam': (146, 166),     # 20 aufgehellte Töne nur für den Lichtkegel (Ziel der Aufhell-Tabelle)
    'static': (166, 256),   # 90 feste Hintergrundfarben
}
WATER_BLUE, WATER_REFL, WATER_N = 5, 3, 6

LAMP_SRC = (295, 53)             # Leuchtturmlampe in 320er Quellkoordinaten
LANTERN_SRC = (73, 99)           # Laternenglas
# Lichtkegel. Erste Fassung: 200 px lang, 3 Stufen, durchgehend gedithert -> das Kegelende las sich als breites,
# dünnes Punkteraster im Himmel. Jetzt kürzer, zum Ende spitz, 5 Stufen als flache Bänder; gedithert wird nur in
# einem schmalen Übergang zwischen zwei Stufen. Die Werte unter 'beam' in palette.json liest main.gd für den Shader.
BEAM_LEN = 130                   # Länge des Lichtkegels in Pixeln
BEAM_WIDEN = 0.09                # halbe Kegelhöhe wächst je Pixel Abstand um diesen Wert ...
BEAM_TAPER = 1.0                 # ... und schrumpft zum Ende hin: Faktor 1 - TAPER * (Abstand/Länge)^2
BEAM_EDGE_POW = 0.7              # Abfall quer zum Kegel
BEAM_FADE_POW = 1.2              # Abfall entlang des Kegels
BEAM_LIGHT = (255, 200, 120)     # Farbe des Lampenlichts
BEAM_LEVELS = (0.09, 0.18, 0.28, 0.39, 0.52)  # Aufhellstufen (Anteil des Lampenlichts, additiv)
BEAM_GAIN = 5.8                  # Stärke 1,0 im Kegel -> Stufe GAIN
BEAM_CUT = 0.0                   # unterhalb dieser Stufe kein Licht
BEAM_SOFT = 0.14                 # weiches Ende beim Drehen (Anteil der Länge)
BEAM_BAND = 0.25                 # Breite des geditherten Übergangs zwischen zwei Stufen (1,0 = durchgehend gedithert)

# Wasserfläche und Ausnahmen in Szenenkoordinaten (320x152), von Hand am Hintergrund nachgezeichnet
SEA = [(58, 79), (320, 79), (320, 141), (58, 141)]
NOT_WATER = {
    'felsinsel': [(85, 88), (88, 84), (93, 82), (99, 82), (104, 85), (105, 88)],
    'uferfelsen': [(58, 79), (62, 79), (66, 87), (74, 90), (82, 94), (86, 95), (99, 97), (101, 99),
                   (99, 100), (58, 100)],
    'steg': [(58, 106), (76, 106), (77, 104), (85, 104), (86, 108), (104, 108), (106, 106), (117, 106),
             (128, 101), (136, 101), (137, 104), (149, 103), (149, 141), (58, 141)],
    'boot_links': [(139, 108), (148, 106), (149, 96), (174, 96), (175, 103), (187, 105), (193, 108),
                   (193, 141), (139, 141)],
    'mast_links': [(155, 70), (160, 70), (160, 97), (155, 97)],
    'pfahl_a': [(213, 109), (224, 109), (224, 141), (213, 141)],
    'pfahl_b': [(205, 122), (213, 122), (213, 141), (205, 141)],
    'boot_rechts': [(225, 117), (232, 114), (262, 114), (266, 117), (266, 141), (225, 141)],
    'mast_rechts': [(243, 82), (247, 82), (247, 116), (243, 116)],
    'pfahl_c': [(263, 112), (273, 112), (273, 141), (263, 141)],
    'pfahl_d': [(276, 119), (285, 119), (285, 141), (276, 141)],
    'kisten_rechts': [(285, 119), (300, 119), (300, 105), (320, 105), (320, 141), (285, 141)],
    'landzunge': [(256, 79), (320, 79), (320, 87), (290, 87), (276, 86), (268, 84), (258, 84)],
}
NOT_WATER_LINES = {   # Takelage als 1-px-Linien
    'takelage_links_vorn': [(157, 75), (139, 114)],
    'takelage_links_hinten': [(158, 75), (172, 100)],
    'takelage_rechts_vorn': [(244, 87), (227, 118)],
    'takelage_rechts_hinten': [(246, 87), (262, 116)],
}

# Gemalter Schornsteinrauch (x0, y0, x1, y1 exklusiv, in 320x213): wird durch Himmel derselben Zeilen RETOUCH_DX
# Pixel weiter rechts ersetzt. Erste Fassung setzte x 11-34, Zeilen 0-40 auf den Zeilen-Median: die flache Fläche
# wurde beim Quantisieren zu einem auffällig gleichmäßigen Bayer-Rechteck, und die oberste Zeile des Topfs ging verloren.
RETOUCH = (13, 9, 32, 40)
RETOUCH_DX = 19                  # Quelle x 32..50: Himmel mit Wolkenband, ohne Sterne

BAYER4 = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) + 0.5) / 16


def vga6(c):
    """VGA-DAC: 6 Bit je Kanal. Jeden Kanal auf 64 Stufen runden und wie üblich auf 8 Bit zurückspreizen
    (v6 << 2 | v6 >> 4, damit 63 -> 255). Erste Fassung nutzte beliebige 8-Bit-Werte (nur 195 von 768 Kanalwerten
    der Palette lagen auf dem 6-Bit-Raster)."""
    v6 = np.clip(np.round(np.asarray(c, np.float64) * 63 / 255), 0, 63).astype(np.int64)
    return (v6 << 2) | (v6 >> 4)


def hsv(rgb):
    r, g, b = [rgb[..., i] / 255.0 for i in range(3)]
    mx, mn = np.maximum(np.maximum(r, g), b), np.minimum(np.minimum(r, g), b)
    d = mx - mn + 1e-9
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    s = np.where(mx > 0, (mx - mn) / (mx + 1e-9), 0)
    return h, s, mx


def poly(points, dy=0):
    m = Image.new('L', (W, H), 0)
    ImageDraw.Draw(m).polygon([(x, y - dy) for x, y in points], fill=255)
    return np.asarray(m) > 0


def load_scene():
    im = Image.open(RAW).convert('RGB').resize((W, H_FULL), Image.BOX)
    a = np.asarray(im).astype(np.float64).copy()
    # Gemalten Rauch über dem Schornstein durch Himmel derselben Zeilen weiter rechts ersetzen (gleiche Textur)
    x0, y0, x1, y1 = RETOUCH
    a[y0:y1, x0:x1] = a[y0:y1, x0 + RETOUCH_DX:x1 + RETOUCH_DX]
    return a[CROP_Y:CROP_Y + H]


def local_median(lum, r=2):
    p = np.pad(lum, r, mode='edge')
    win = np.lib.stride_tricks.sliding_window_view(p, (2 * r + 1, 2 * r + 1))
    return np.median(win.reshape(lum.shape + (-1,)), -1)


def make_masks(a):
    h, s, v = hsv(a)
    yy, xx = np.mgrid[0:H, 0:W]
    sy = yy + CROP_Y
    lum = a @ np.array([0.299, 0.587, 0.114])
    warm = (h < 65) | (h > 330)
    m = {}
    # Wasser: die ganze Wasserfläche (SEA) über die Farbton-Klassifikation; ausgenommen werden nur
    # Gegenstände und ihre Schatten über gezeichnete Polygone/Linien (um 1 px erweitert).
    region = poly(SEA)
    region &= ~not_water()
    # bläulich bis violett-rosa (Himmelsspiegelung), aber nicht Holz, Bootsrumpf oder Weiß
    blue = (h >= 195) & (h <= 345) & (s > 0.12)
    refl = region & warm & (v > 0.42) & (((xx >= 180) & (xx <= 222) & (yy <= 106)) |
                                         ((xx >= 286) & (xx <= 303) & (yy <= 126)) |
                                         ((yy <= 86) & (xx >= 104) & (xx <= 270)))
    m['water'] = (region & blue) | refl
    m['refl'] = refl
    # Lampe: helle, warme Pixel im Laternenraum des Leuchtturms
    lx, ly = LAMP_SRC
    m['lamp'] = (abs(xx - lx) <= 4) & (abs(sy - ly) <= 3) & warm & (v > 0.5)
    # Laterne: Glas (sehr hell) und Lichthof (warm, nah)
    tx, ty = LANTERN_SRC
    d = np.hypot(xx - tx, sy - ty)
    m['lantern_core'] = (d <= 4.5) & warm & (v > 0.75)
    m['lantern_halo'] = (d <= 9) & warm & (v > 0.45) & ~m['lantern_core']
    # Fenster des Häuschens
    m['window'] = (xx >= 20) & (xx <= 38) & (sy >= 90) & (sy <= 112) & warm & (v > 0.55) & (s > 0.35)
    # Sterne: einzelne helle Pixel im oberen Himmel
    sky_top = (sy < 48) & ~((xx < 36) & (sy > 36)) & ~((xx > 286) & (sy > 42))
    m['stars'] = sky_top & (lum > local_median(lum) + 18)
    # Häuschen + Schornstein (Vordergrund, der Lichtkegel liegt dahinter)
    cottage = poly([(0, 49), (13, 49), (13, 38), (33, 38), (33, 58), (52, 84), (64, 92), (64, 213), (0, 213)], CROP_Y)
    m['cottage'] = cottage
    for k in ('lamp', 'lantern_core', 'lantern_halo', 'window', 'stars'):
        m['water'] &= ~m[k]
    m['refl'] &= m['water']
    # Rand: blaue Wasserpixel mit einem Nicht-Wasser-Nachbarn (8er-Nachbarschaft) glitzern schwächer
    wpad = np.pad(m['water'], 1, constant_values=False)
    allnb = np.ones_like(m['water'])
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            allnb &= wpad[1 + dy:1 + dy + H, 1 + dx:1 + dx + W]
    m['water_edge'] = m['water'] & ~m['refl'] & ~allnb
    return m


def not_water():
    """Gegenstände im Wasser (Boote, Masten, Pfähle, Steg, Felsen) samt Schatten, um 1 px erweitert."""
    im = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(im)
    for pts in NOT_WATER.values():
        d.polygon(pts, fill=255)
    for pts in NOT_WATER_LINES.values():
        d.line(pts, fill=255, width=1)
    msk = np.asarray(im) > 0
    pad = np.pad(msk, 1)
    grown = msk.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            grown |= pad[1 + dy:1 + dy + H, 1 + dx:1 + dx + W]
    return grown


def beam_texture(a, m):
    """R: Stärke im Kegel (Mitte hell, Rand weich), G: Abstand zur Lampe 0..1, B: Seite (0 links, 255 rechts)."""
    yy, xx = np.mgrid[0:H, 0:W]
    lx, ly = LAMP_SRC[0], LAMP_SRC[1] - CROP_Y
    dx, dy = xx - lx, yy - ly
    dist = np.abs(dx).astype(np.float64)
    u = np.clip(dist / BEAM_LEN, 0, 1)
    # halbe Kegelhöhe wächst mit dem Abstand und zieht sich zum Ende wieder zusammen (Spitze statt Kante)
    half = np.maximum(0.6, 1.0 + BEAM_WIDEN * dist * (1.0 - BEAM_TAPER * u ** 2))
    across = np.abs(dy) / half
    edge = np.clip(1.0 - across, 0, 1) ** BEAM_EDGE_POW
    fade = (1.0 - u) ** BEAM_FADE_POW
    strength = edge * fade
    # nur Himmel/Wolken/Fernes: nicht über Häuschen, Lampe, Turm. In den Zeilen des Lampenglases setzt der Kegel
    # direkt am Glasrand an (Glas x 292..297, nicht mittig zu LAMP_SRC). Erste Fassung sperrte |dx| <= 5 in allen
    # Zeilen: der Strahl begann links 2 px und rechts 3 px neben dem Glas und schwebte losgelöst im Himmel.
    gcols = np.flatnonzero(m['lamp'].any(0))
    grows = np.flatnonzero(m['lamp'].any(1))
    beside_glass = (yy >= grows.min()) & (yy <= grows.max()) & ((xx < gcols.min()) | (xx > gcols.max()))
    tower = (np.abs(dx) <= 5) & (yy >= ly - 4) & ~beside_glass
    strength[m['cottage'] | m['lamp'] | m['stars'] | tower] = 0
    strength[dist < 3] = 0
    # kleiner Hof um die Lampe (Seite 128 = Blitz zur Kamera)
    halo_d = np.hypot(dx, dy * 1.2)
    halo = np.clip(1 - halo_d / 7.0, 0, 1) * (~m['lamp']) * (~tower)
    side = np.where(dx < 0, 0, 255).astype(np.float64)
    use_halo = halo > strength
    r = np.where(use_halo, halo, strength)
    g = np.where(use_halo, 0, np.clip(dist / BEAM_LEN, 0, 1))
    b = np.where(use_halo, 128, side)
    return np.dstack([r * 255, g * 255, b]).round().astype(np.uint8)


def quantize_static(a, mask, pal):
    """Nächste Palettenfarbe in Oklab, sparsames geordnetes Dithering nur in ruhigen Verläufen."""
    lab = oklab(a.reshape(-1, 3)).reshape(H, W, 3)
    plab = oklab(pal)
    d = ((lab[:, :, None, :] - plab[None, None]) ** 2).sum(-1)
    order = np.argsort(d, -1)
    c1, c2 = order[..., 0], order[..., 1]
    p1, p2 = plab[c1], plab[c2]
    seg = p2 - p1
    t = np.clip(((lab - p1) * seg).sum(-1) / np.maximum((seg ** 2).sum(-1), 1e-9), 0, 1)
    gap = np.sqrt((seg ** 2).sum(-1))
    # ruhige Bereiche: geringe lokale Helligkeitsstreuung
    L = lab[..., 0]
    p = np.pad(L, 1, mode='edge')
    win = np.lib.stride_tricks.sliding_window_view(p, (3, 3)).reshape(H, W, 9)
    calm = win.std(-1) < 0.012
    th = np.tile(BAYER4, (H // 4 + 1, W // 4 + 1))[:H, :W]
    use2 = calm & (gap < 0.045) & (t > th)
    idx = np.where(use2, c2, c1)
    return idx


def tone_entries(base, offsets):
    """Einträge einer Tonstufe: Grundfarbe mit Helligkeitsversatz in Oklab-L (für Glitzer)."""
    out = []
    for off in offsets:
        c = np.clip(base * (1 + off * 2.2) + off * 60, 0, 255)
        out.append(c)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview')
    a_ = ap.parse_args()
    ART.mkdir(parents=True, exist_ok=True)
    a = load_scene()
    m = make_masks(a)
    pal = np.zeros((256, 3))
    idx = np.full((H, W), -1, np.int32)
    groups = {}

    # --- Wasser: 5 blaue + 3 Reflex-Tonstufen, je 6 Einträge; Phase je Pixel aus x und Zeilenversatz.
    # Randpixel (Nachbar ist kein Wasser) bekommen dieselben blauen Grundtöne mit halbem Glitzern,
    # damit das Glitzern zu Booten, Pfählen und Schatten hin ausläuft statt an einer Kante abzubrechen.
    w0 = RANGES['water'][0]
    e0 = RANGES['water_edge'][0]
    blue_m = m['water'] & ~m['refl']
    tb = kmeans(a[blue_m], WATER_BLUE, seed=5)
    tb = tb[np.argsort(oklab(tb)[:, 0])]
    tr = kmeans(a[m['refl']], WATER_REFL, seed=6)
    tr = tr[np.argsort(oklab(tr)[:, 0])]
    tones = np.concatenate([tb, tr])
    rng = np.random.default_rng(11)
    rowoff = rng.integers(0, WATER_N, H)
    rowlen = rng.integers(2, 5, H)
    yy, xx = np.mgrid[0:H, 0:W]
    phase = ((xx // rowlen[:, None]) + rowoff[:, None]) % WATER_N
    tl = oklab(tones)
    for k, msk in ((0, blue_m), (WATER_BLUE, m['refl'])):
        ntone = WATER_BLUE if k == 0 else WATER_REFL
        sub = oklab(a[msk])
        tt = np.argmin(((sub[:, None] - tl[None, k:k + ntone]) ** 2).sum(-1), 1) + k
        base = np.where(m['water_edge'][msk], e0, w0)
        idx[msk] = base + tt * WATER_N + phase[msk]
    water_offsets = {'blue': [0, 0, 0, 0.04, 0.09, 0.04], 'refl': [0, -0.06, -0.10, -0.04, 0.05, 0.10],
                     'edge': [0, 0, 0, 0.02, 0.045, 0.02]}
    for t in range(WATER_BLUE + WATER_REFL):
        offs = water_offsets['blue' if t < WATER_BLUE else 'refl']
        for j, c in enumerate(tone_entries(tones[t], offs)):
            pal[w0 + t * WATER_N + j] = c
    for t in range(WATER_BLUE):
        for j, c in enumerate(tone_entries(tones[t], water_offsets['edge'])):
            pal[e0 + t * WATER_N + j] = c
    groups['water'] = {'start': w0, 'tones': WATER_BLUE + WATER_REFL, 'len': WATER_N,
                       'mode': 'rotate', 'steps_per_second': 7.5}
    groups['water_edge'] = {'start': e0, 'tones': WATER_BLUE, 'len': WATER_N,
                            'mode': 'rotate', 'steps_per_second': 7.5}

    # --- Lampe: 8 Einträge nach Spalte, ein heller Fleck läuft durch (Drehlinse)
    l0 = RANGES['lamp'][0]
    lx = LAMP_SRC[0]
    idx[m['lamp']] = l0 + (xx[m['lamp']] - (lx - 4)) % 8
    lamp_base = np.array([255, 214, 120])
    lamp_prof = [0.55, 0.62, 0.75, 0.92, 1.0, 0.92, 0.75, 0.62]
    for j in range(8):
        pal[l0 + j] = np.clip(lamp_base * lamp_prof[j] + (40 if j == 4 else 0), 0, 255)
    groups['lamp'] = {'start': l0, 'len': 8, 'mode': 'rotate_synced_to_beam'}

    # --- Sterne: 4 Einträge, zufällige Phase je Stern
    s0 = RANGES['stars'][0]
    sp = rng.integers(0, 4, int(m['stars'].sum()))
    idx[m['stars']] = s0 + sp
    star_mean = a[m['stars']].mean(0) if m['stars'].any() else np.array([200, 200, 230])
    for j, f in enumerate([1.0, 0.8, 0.55, 0.8]):
        pal[s0 + j] = np.clip(star_mean * f + (30 if j == 0 else 0), 0, 255)
    groups['stars'] = {'start': s0, 'len': 4, 'mode': 'rotate', 'steps_per_second': 3}

    # --- Laterne: Glas 4 Tonstufen, Lichthof 4 Tonstufen (Flackern über Palettenwerte)
    t0 = RANGES['lantern'][0]
    for k, key in ((0, 'lantern_core'), (4, 'lantern_halo')):
        if m[key].sum() >= 4:
            tc = kmeans(a[m[key]], 4, seed=7 + k)
            sub = oklab(a[m[key]])
            tt = np.argmin(((sub[:, None] - oklab(tc)[None]) ** 2).sum(-1), 1)
            idx[m[key]] = t0 + k + tt
            pal[t0 + k:t0 + k + 4] = tc
    groups['lantern'] = {'start': t0, 'core': 4, 'halo': 4, 'mode': 'flicker'}

    # --- Fenster
    f0 = RANGES['window'][0]
    if m['window'].sum() >= 4:
        tc = kmeans(a[m['window']], 4, seed=9)
        sub = oklab(a[m['window']])
        idx[m['window']] = f0 + np.argmin(((sub[:, None] - oklab(tc)[None]) ** 2).sum(-1), 1)
        pal[f0:f0 + 4] = tc
    groups['window'] = {'start': f0, 'len': 4, 'mode': 'flicker_soft'}

    # --- Statische Farben
    st0, st1 = RANGES['static']
    rest = idx < 0
    spal = kmeans(a[rest], st1 - st0, iters=14, seed=1)
    spal = vga6(spal)                     # DAC-Raster vor dem Quantisieren, damit das Dithering die echten Farben sieht
    spal = spal[np.lexsort((oklab(spal)[:, 0],))]
    pal[st0:st1] = spal
    q = quantize_static(a, rest, spal)
    idx[rest] = st0 + q[rest]

    # --- Rauch (4 Töne zwischen hellem Grau und Himmel): Lichtkante, Körper, Unterkante, Zerfall.
    # Erste Fassung (138,128,162)…(72,66,118) hatte zu wenig Abstand zwischen Lichtkante und Körper.
    s0r = RANGES['smoke'][0]
    for j, c in enumerate([(160, 150, 184), (124, 114, 156), (94, 86, 138), (70, 64, 118)]):
        pal[s0r + j] = c

    # --- Lichtkegel: Textur + Aufhell-Tabellen (Index -> hellerer Index), 5 Stufen.
    # Die Zielfarben der Pixel im Kegel werden zu 20 eigenen Paletteneinträgen zusammengefasst,
    # damit das Licht nicht auf schmutzige Grautöne der statischen Palette fällt.
    beam = beam_texture(a, m)
    Image.fromarray(beam, 'RGB').save(ART / 'beam.png')
    b0, b1 = RANGES['beam']
    light = np.array(BEAM_LIGHT, float)   # warmes Lampenlicht, additiv wie Licht im Dunst
    levels = BEAM_LEVELS
    inbeam = beam[..., 0] > 0
    used, cnt = np.unique(idx[inbeam], return_counts=True)
    used_static = [(i, c) for i, c in zip(used, cnt) if st0 <= i < st1]
    targets, weights = [], []
    for i, c in used_static:
        for k in levels:
            targets.append(np.clip(pal[i] + light * k, 0, 255))
            weights.append(c)
    targets = np.array(targets)
    rep_t = np.repeat(targets, np.maximum(1, np.array(weights) // 4), 0)
    btones = kmeans(rep_t, b1 - b0, iters=16, seed=8)
    pal[b0:b1] = btones
    pal = vga6(pal).astype(np.float64)    # alle Einträge auf das DAC-Raster, bevor die Aufhell-Tabelle sucht
    cand = np.concatenate([np.arange(b0, b1), np.arange(st0, st1)])
    cl = oklab(pal[cand])
    lut = np.tile(np.arange(256), (len(levels), 1))
    for level, k in enumerate(levels):
        for i in range(st0, st1):
            lit = np.clip(pal[i] + light * k, 0, 255)
            lut[level, i] = cand[int(np.argmin(((cl - oklab(lit[None])[0]) ** 2).sum(-1)))]
    Image.fromarray(lut.astype(np.uint8), 'L').save(ART / 'beam_lut.png')

    assert (idx >= 0).all() and idx.max() < 256
    Image.fromarray(idx.astype(np.uint8), 'L').save(ART / 'bg_index.png')
    pal_u8 = vga6(pal).astype(np.uint8)
    assert (vga6(pal_u8) == pal_u8).all()
    meta = {'size': [W, H], 'crop_y': CROP_Y, 'ranges': RANGES, 'groups': groups,
            'lamp': [LAMP_SRC[0], LAMP_SRC[1] - CROP_Y], 'lantern': [LANTERN_SRC[0], LANTERN_SRC[1] - CROP_Y],
            'beam_len': BEAM_LEN,
            'beam': {'levels': len(BEAM_LEVELS), 'gain': BEAM_GAIN, 'cut': BEAM_CUT, 'soft': BEAM_SOFT,
                     'band': BEAM_BAND,
                     'light': list(BEAM_LEVELS)},
            'palette': ['%02x%02x%02x' % tuple(c) for c in pal_u8]}
    old = ART / 'palette.json'
    if old.exists():
        # von build_sprites.py gesetzte Einträge (Oberfläche, Figur) erhalten
        prev = json.loads(old.read_text())
        for r in ('ui', 'sprite'):
            s, e = RANGES[r]
            meta['palette'][s:e] = prev['palette'][s:e]
        meta['sprite_colors'] = prev.get('sprite_colors')
        meta['ui_colors'] = prev.get('ui_colors')
    old.write_text(json.dumps(meta, indent=1))
    counts = {k: int((idx >= s) .__and__(idx < e).sum()) for k, (s, e) in RANGES.items()}
    print('Pixel je Bereich:', counts)
    # Arbeitskopien und Ansichten in assets/
    ast = STYLE / 'assets'
    for f in ('bg_index.png', 'beam.png', 'beam_lut.png', 'palette.json'):
        (ast / f).write_bytes((ART / f).read_bytes())
    Image.fromarray(pal_u8[idx]).save(ast / 'bg_preview.png')
    if a_.preview:
        pv = pathlib.Path(a_.preview)
        rgb = pal_u8[idx]
        Image.fromarray(rgb).resize((W * 3, H * 3), Image.NEAREST).save(pv / 'bg_quant.png')
        ov = rgb.copy()
        for key, col in (('water', (0, 255, 255)), ('water_edge', (0, 120, 255)), ('refl', (255, 0, 255)),
                         ('lamp', (255, 0, 0)),
                         ('lantern_core', (255, 0, 0)), ('lantern_halo', (0, 255, 0)), ('window', (0, 255, 0)),
                         ('stars', (255, 255, 0))):
            ov[m[key]] = (ov[m[key]] * 0.3 + np.array(col) * 0.7).astype(np.uint8)
        bb = beam[..., 0:1] / 255.0
        ov = (ov * (1 - bb * 0.6) + np.array([255, 255, 255]) * bb * 0.6).astype(np.uint8)
        Image.fromarray(ov).resize((W * 3, H * 3), Image.NEAREST).save(pv / 'bg_masks.png')
        print('Farben im Bild:', len(np.unique(idx)))


if __name__ == '__main__':
    main()
