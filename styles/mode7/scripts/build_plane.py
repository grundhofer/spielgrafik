"""Baut die Mode-7-Ebene: Kachelsatz (höchstens 256 Kacheln à 8×8, 8 Bit je Texel) und Kachelkarte 128×128.

Aufruf: .venv/bin/python styles/mode7/scripts/build_plane.py

Die Karte entsteht wie bei einem Kachel-Editor aus Regeln je Kachel, nicht aus einem großen Bild:
  - offenes Wasser: ein nahtloses 32×32-Muster (16 Kacheln), Kachel 0 = eigene Kachel für alles außerhalb
    der Karte (M7SEL: außerhalb Kachel 0)
  - Kai (Pflaster, Kanten, Mauerschatten im Wasser) und Steg (Planken, Balken, Pfähle) auf dem Kachelraster
  - Felsufer und Felsen im Wasser: Eckentypen je Kachel (Wasser/Fels/Gras) wie Autotiles, Grenze aus
    bilinear interpolierten Ecken plus Rauschen, das zu den Kachelkanten hin verschwindet (Nachbarn passen)
Gleiche Kacheln werden zusammengelegt. Ausgabe:
  demo/art/m7_map.png     128×128, L8: Kachelnummer
  demo/art/m7_tiles.png   128×128, L8: 16×16 Kacheln, CGRAM-Index je Texel
  assets/m7_map_preview.png, assets/m7_tiles_sheet.png, demo/data/plane.json (Zählwerte)
"""
import json
import math
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import palette as P                                  # noqa: E402
from layout import JETTY, PILE_STEP, QUAY, ROCK_BAND, land_field   # noqa: E402
from m7lib import MAP, STYLE, TPM, X_MIN, Y_MAX      # noqa: E402

T = 8
NT = MAP // T
I = P.idx
rng = np.random.default_rng(7)


def u_of(x):
    return int(round((x - X_MIN) * TPM))


def v_of(y):
    return int(round((Y_MAX - y) * TPM))


QU0, QU1 = u_of(QUAY["x0"]), u_of(QUAY["x1"])       # Kai: u in [QU0, QU1)
QV0 = v_of(QUAY["y1"])                               # Kai: v >= QV0 (Nordkante)
JU0, JU1 = u_of(JETTY["x0"]), u_of(JETTY["x1"])
JV0, JV1 = v_of(JETTY["y1"]), v_of(JETTY["y0"])     # Steg: v in [JV0, JV1)
for n, val in dict(QU0=QU0, QU1=QU1, QV0=QV0, JU0=JU0, JU1=JU1, JV0=JV0, JV1=JV1).items():
    assert val % T == 0, f"{n}={val} liegt nicht auf dem Kachelraster"
assert JU0 == QU1, "Steg muss an der Kaikante beginnen"


# ---------------------------------------------------------------------------------------------
# Muster
# ---------------------------------------------------------------------------------------------
def water_macro(size=32, seed=3):
    """Nahtloses Wassermuster: Grundton, wenige größere dunklere/hellere Flecken, kurze Wellenstriche
    (Kamm hell, Tal dunkel), einzelne Glitzertexel (Palettenanimation)."""
    r = np.random.default_rng(seed)
    m = np.full((size, size), I("w_base"), np.uint8)
    # weiche Flecken (2–3 Texel hoch, breit) für Tiefe
    for _ in range(7):
        x, y = r.integers(0, size, 2)
        L = int(r.integers(5, 11))
        col = I("w_deep") if r.random() < 0.6 else I("w_mid")
        for k in range(L):
            m[y % size, (x + k) % size] = col
            if 1 < k < L - 2:
                m[(y + 1) % size, (x + k) % size] = col
    occupied = np.zeros((size, size), bool)
    glints = []
    tries = 0
    placed = 0
    while placed < 16 and tries < 4000:
        tries += 1
        x, y = (int(v) for v in r.integers(0, size, 2))
        L = int(r.integers(3, 8))
        cells = [((y + dy) % size, (x + dx) % size) for dy in (-1, 0, 1, 2) for dx in range(-1, L + 1)]
        if any(occupied[c] for c in cells):
            continue
        for c in cells:
            occupied[c] = True
        for k in range(L):
            m[y % size, (x + k) % size] = I("w_light")
        for k in range(1, L - 1):
            m[(y + 1) % size, (x + k) % size] = I("w_deep")
        if L >= 5:
            m[y % size, (x + 1) % size] = I("w_hi")
        if placed % 2 == 0:
            glints.append((y % size, (x + L // 2) % size))
        placed += 1
    for k, (y, x) in enumerate(glints):
        m[y, x] = I(f"glint{k % 4}")
    return m


def far_tile():
    """Kachel 0: offenes Meer außerhalb der Karte, kachelt mit sich selbst."""
    m = np.full((T, T), I("w_base"), np.uint8)
    m[2, 1:5] = I("w_light")
    m[3, 2:4] = I("w_deep")
    m[6, 5:8] = I("w_mid")
    m[2, 3] = I("glint1")
    return m


def paving_macro(w=32, h=16, seed=5):
    """Pflaster aus Reihen rechteckiger Steine (4 Texel tief), Fugen 1 Texel, Licht von oben links."""
    r = np.random.default_rng(seed)
    m = np.full((h, w), I("p_joint"), np.uint8)
    rows = h // 4
    for ry in range(rows):
        y0 = ry * 4
        x = int(r.integers(0, 6))
        start = x
        widths = []
        while sum(widths) < w:
            widths.append(int(r.integers(5, 9)))
        # letzte Breite so kürzen, dass die Reihe genau umläuft
        over = sum(widths) - w
        widths[-1] -= over
        if widths[-1] < 3:
            widths[-2] += widths[-1]
            widths.pop()
        for wd in widths:
            tone = r.choice([I("p_base"), I("p_base"), I("p_light"), I("p_dark")])
            for dy in range(3):
                for dx in range(wd - 1):
                    xx = (x + dx) % w
                    m[y0 + dy, xx] = tone
            # Kante oben hell, unten rechts dunkel
            for dx in range(wd - 1):
                m[y0, (x + dx) % w] = I("p_hi") if tone != I("p_dark") else I("p_light")
            m[y0 + 2, (x + wd - 2) % w] = I("p_dark")
            if r.random() < 0.5:
                m[y0 + 1, (x + int(r.integers(1, max(2, wd - 2)))) % w] = I("p_dark")
            x += wd
    return m


def plank_tile(row, var, pile=None):
    """Steg-Kachel. row: 0 = Nordrand, 1 = Mitte, 2 = Südrand. Planken quer zum Steg (in v), Periode 4.
    var: Tonfolge der beiden Planken. pile: Texel-x eines Pfahls am Rand (oder None)."""
    tones = [I("j_base"), I("j_light"), I("j_base"), I("j_dark"), I("j_light"), I("j_base")]
    m = np.zeros((T, T), np.uint8)
    for x in range(T):
        p = x // 4
        if x % 4 == 3:
            m[:, x] = I("j_gap")
            continue
        tone = tones[(var * 2 + p) % len(tones)]
        m[:, x] = tone
        if x % 4 == 0:
            m[:, x] = I("j_hi") if tone != I("j_dark") else I("j_base")       # Licht auf der Plankenkante
    # Maserung: einzelne dunkle Texel
    for x in range(T):
        if x % 4 != 3 and (x * 7 + row * 3 + var * 5) % 9 == 0:
            m[(x * 3 + var + row) % T, x] = I("j_dark")
    if row == 0:
        m[0, :] = I("j_dark")
        m[1, :] = np.where(m[1, :] == I("j_gap"), I("j_dark"), I("j_light"))
    if row == 2:
        m[7, :] = I("j_dark")
        m[6, :] = np.where(m[6, :] == I("j_gap"), I("j_gap"), m[6, :])
    if pile is not None:
        y0 = 0 if row == 0 else 5
        for dy in range(3):
            for dx in range(3):
                m[y0 + dy, pile + dx] = I("j_pile")
        m[y0 + 1, pile + 1] = I("j_cut")
    return m


def rock_texture(seed):
    r = np.random.default_rng(seed)
    m = np.full((T, T), I("r_base"), np.uint8)
    for _ in range(3):
        cx, cy = r.integers(0, T, 2)
        rad = r.uniform(1.6, 2.8)
        for y in range(T):
            for x in range(T):
                d = math.hypot(x - cx, y - cy)
                if d < rad:
                    m[y, x] = I("r_mid")
                    if (x - cx) + (y - cy) < -rad * 0.55:
                        m[y, x] = I("r_light")
                    if (x - cx) + (y - cy) > rad * 0.7:
                        m[y, x] = I("r_dark")
    if r.random() < 0.6:
        x, y = r.integers(1, T - 1, 2)
        m[y, x] = I("r_hi")
    return m


def grass_texture(seed):
    r = np.random.default_rng(seed)
    m = np.full((T, T), I("g_base"), np.uint8)
    for _ in range(6):
        x, y = r.integers(0, T, 2)
        m[y, x] = I("g_mid")
        if x + 1 < T:
            m[y, x + 1] = I("g_light") if r.random() < 0.5 else I("g_mid")
    for _ in range(3):
        x, y = r.integers(0, T, 2)
        m[y, x] = I("g_dark")
    if r.random() < 0.5:
        x, y = r.integers(0, T, 2)
        m[y, x] = I("g_hi")
    return m


ROCK_TEX = [rock_texture(s) for s in (11, 12, 13)]
GRASS_TEX = [grass_texture(s) for s in (21, 22, 23)]
WATER = water_macro()
PAVING = paving_macro()


def bump(n):
    """Rauschen je Texel einer Kachel, zu den Kanten hin 0 (damit Nachbarkacheln passen)."""
    r = np.random.default_rng(n)
    g = r.uniform(-1, 1, (4, 4))
    big = np.kron(g, np.ones((2, 2)))
    yy, xx = np.mgrid[0:T, 0:T] + 0.5
    win = np.sin(np.pi * xx / T) * np.sin(np.pi * yy / T)
    return big * win


def corner_tile(c, kind_lo, kind_hi, seed):
    """Gemischte Kachel aus Eckwerten c = (c00, c10, c01, c11) in {0,1} (1 = höheres Gelände).
    kind_lo/kind_hi: 'water'/'rock'/'grass'."""
    c00, c10, c01, c11 = (1.0 if v else -1.0 for v in c)
    yy, xx = np.mgrid[0:T, 0:T] + 0.5
    fx, fy = xx / T, yy / T
    f = c00 * (1 - fx) * (1 - fy) + c10 * fx * (1 - fy) + c01 * (1 - fx) * fy + c11 * fx * fy
    f = f + 0.8 * bump(seed)
    hi = f > 0
    m = np.zeros((T, T), np.uint8)
    tex_hi = ROCK_TEX[seed % 3] if kind_hi == "rock" else GRASS_TEX[seed % 3]
    m[hi] = tex_hi[hi]
    lo = ~hi
    if kind_lo == "water":
        m[lo] = I("w_base")
        m[lo & (f > -0.8)] = I("w_shallow")
        m[lo & (f > -0.6)] = I("w_shallow2")
        m[lo & (f > -0.42)] = I("foam1")
        m[lo & (f > -0.2)] = I("foam2")
        dots = (xx.astype(int) * 3 + yy.astype(int) * 5 + seed) % 4 == 0
        m[lo & (f > -0.2) & dots] = I("foam3")
        # Uferkante: dunkler Fels direkt an der Wasserlinie
        if kind_hi == "rock":
            edge = hi & (f < 0.3)
            m[edge] = I("r_dark")
    else:   # Fels unten, Gras oben
        m[lo] = ROCK_TEX[(seed + 1) % 3][lo]
        edge = hi & (f < 0.28)
        m[edge] = I("g_dark")
    return m


# ---------------------------------------------------------------------------------------------
# Karte zusammensetzen
# ---------------------------------------------------------------------------------------------
def build():
    tiles = []            # Liste von 8×8-Arrays
    index = {}            # bytes -> Kachelnummer
    usage = {}

    def tid(arr, label):
        key = arr.tobytes()
        if key not in index:
            index[key] = len(tiles)
            tiles.append(arr.copy())
            usage[index[key]] = label
        return index[key]

    tid(far_tile(), "far")    # Kachel 0
    tmap = np.zeros((NT, NT), np.int32)

    # Eckentypen für das freie Gelände: 0 Wasser, 1 Fels, 2 Gras
    cu = X_MIN + np.arange(NT + 1) * T / TPM
    cv = Y_MAX - np.arange(NT + 1) * T / TPM
    PX, PY = np.meshgrid(cu, cv)
    lf = land_field(PX, PY)
    corner = np.where(lf > ROCK_BAND, 2, np.where(lf > 0, 1, 0))

    def quay_tile(tx, ty):
        u0, v0 = tx * T, ty * T
        return QU0 <= u0 < QU1 and v0 >= QV0

    def jetty_tile(tx, ty):
        u0, v0 = tx * T, ty * T
        return JU0 <= u0 < JU1 and JV0 <= v0 < JV1

    pile_us = set()
    k = 0
    while JU0 + int(round(k * PILE_STEP * TPM)) < JU1:
        pile_us.add(JU0 + int(round(k * PILE_STEP * TPM)) + 3)
        k += 1
    pile_us.add(JU1 - 4)

    def water_px(u, v):
        return WATER[v % 32, u % 32]

    for ty in range(NT):
        for tx in range(NT):
            u0, v0 = tx * T, ty * T
            if quay_tile(tx, ty):
                m = np.array([[PAVING[(v0 + y) % 16, (u0 + x) % 32] for x in range(T)] for y in range(T)],
                             np.uint8)
                lab = "quay"
                if u0 == QU1 - T:          # Ostkante (Kantensteine)
                    m[:, 4:] = I("k_top")
                    m[:, 4] = I("k_hi")
                    m[:, 3] = I("p_joint")
                    if (ty % 2) == 0:
                        m[0, 4:] = I("p_joint")
                    lab = "quay_edge_e"
                if v0 == QV0:              # Nordkante
                    m[:4, :] = I("k_top")
                    m[0, :] = I("k_hi")
                    m[4, :] = I("p_joint")
                    if tx % 2 == 0:
                        m[:4, 0] = I("p_joint")
                    if u0 == QU1 - T:
                        m[:4, 4:] = I("k_top")
                        m[0, 4:] = I("k_hi")
                        m[:, 4] = np.where(np.arange(T) < 4, I("k_top"), I("k_hi"))
                    lab = "quay_edge_n"
                if u0 == QU0:              # Westkante zum Gras: niedrige Mauer
                    m[:, 0] = I("wall_dark")
                    m[:, 1] = I("wall_top")
                    lab = "quay_edge_w"
                tmap[ty, tx] = tid(m, lab)
                continue
            if jetty_tile(tx, ty):
                row = (v0 - JV0) // T
                pile = None
                if row in (0, 2):
                    for pu in pile_us:
                        if u0 <= pu - 1 and pu + 1 < u0 + T:
                            pile = pu - 1 - u0
                m = plank_tile(row, (tx % 3), pile)
                if u0 == JU1 - T:          # Stegende: Querbalken
                    m[:, 6] = I("j_dark")
                    m[:, 7] = I("j_gap")
                if u0 == JU0:              # Anschluss an die Kaikante
                    m[:, 0] = I("j_gap")
                tmap[ty, tx] = tid(m, "jetty")
                continue
            # Wasser neben Kai und Steg: Mauer- bzw. Stegschatten, sonst Wassermuster
            c = corner[ty:ty + 2, tx:tx + 2]
            vals = (int(c[0, 0]), int(c[0, 1]), int(c[1, 0]), int(c[1, 1]))
            if max(vals) == 0:
                m = np.array([[water_px(u0 + x, v0 + y) for x in range(T)] for y in range(T)], np.uint8)
                lab = "water"
                if u0 == QU1 and v0 >= QV0 and not (JV0 <= v0 < JV1):     # östlich der Kaikante
                    m[:, 0:3] = I("w_shadow")
                    m[:, 3] = np.where(np.arange(T) % 3 == 0, I("foam1"), I("w_deep"))
                    lab = "quay_shadow_e"
                if v0 == QV0 - T and QU0 <= u0 < QU1 + T:                # nördlich der Kaikante
                    m[5:, :] = I("w_deep")
                    m[6:, :] = I("w_shadow")
                    m[5, :] = np.where(np.arange(T) % 3 == 1, I("foam1"), I("w_deep"))
                    if u0 == QU1:
                        m[:, 0:3] = np.where(np.arange(T)[:, None] >= 5, I("w_shadow"), I("w_deep"))
                    lab = "quay_shadow_n"
                if JU0 <= u0 < JU1 + T and (v0 == JV0 - T or v0 == JV1):  # Wasser neben dem Steg
                    north = v0 == JV0 - T
                    rows = [7, 6] if north else [0, 1, 2]
                    for y in rows:
                        m[y, :] = I("w_shadow")
                    if north:
                        m[5, :] = np.where(np.arange(T) % 4 == 2, I("w_light"), m[5, :])
                    else:
                        m[3, :] = np.where(np.arange(T) % 4 == 1, I("w_light"), I("w_deep"))
                    for pu in pile_us:                                     # Pfahl reicht ins Wasser
                        if u0 <= pu - 1 and pu + 1 < u0 + T:
                            ys = [7] if north else [0]
                            for y in ys:
                                m[y, pu - 1 - u0:pu + 2 - u0] = I("j_pile")
                    if u0 >= JU1:
                        m[:, :] = np.array([[water_px(u0 + x, v0 + y) for x in range(T)] for y in range(T)])
                        m[(7 if north else 0), 0:2] = I("w_shadow")
                    lab = "jetty_shadow"
                if u0 == JU1 and JV0 <= v0 < JV1:                         # östlich vom Stegende
                    m[:, 0:2] = I("w_shadow")
                    m[:, 2] = np.where(np.arange(T) % 3 == 0, I("w_light"), I("w_deep"))
                    lab = "jetty_shadow"
                tmap[ty, tx] = tid(m, lab)
                continue
            mn, mx = min(vals), max(vals)
            seed = (tx * 7 + ty * 13) % 97
            if mn == mx:                   # ganz Fels oder ganz Gras
                tex = ROCK_TEX if mx == 1 else GRASS_TEX
                tmap[ty, tx] = tid(tex[(tx * 5 + ty * 3) % 3], "rock" if mx == 1 else "grass")
                continue
            if mn == 0:                    # Wasser/Land: Gras an der Wasserkante wird zu Fels
                bits = tuple(1 if v > 0 else 0 for v in vals)
                m = corner_tile(bits, "water", "rock", seed % 6)
                lab = "shore"
            else:                          # Fels/Gras
                bits = tuple(1 if v == 2 else 0 for v in vals)
                m = corner_tile(bits, "rock", "grass", seed % 6)
                lab = "rock_grass"
            tmap[ty, tx] = tid(m, lab)
    return tiles, tmap, usage


def main():
    tiles, tmap, usage = build()
    n = len(tiles)
    print(f"Kacheln: {n} (Grenze 256)")
    if n > 256:
        sys.exit("zu viele Kacheln")
    counts = {}
    for t, lab in usage.items():
        counts[lab] = counts.get(lab, 0) + 1
    print("je Art:", counts)
    used = sorted({int(v) for t in tiles for v in np.unique(t)})
    print(f"Farben auf der Ebene: {len(used)} (CGRAM {min(used)}..{max(used)})")
    assert all(64 <= c < 128 for c in used)
    sheet = np.zeros((128, 128), np.uint8)
    for k, t in enumerate(tiles):
        sheet[(k // 16) * T:(k // 16) * T + T, (k % 16) * T:(k % 16) * T + T] = t
    art = STYLE / "demo/art"
    art.mkdir(parents=True, exist_ok=True)
    Image.fromarray(sheet, "L").save(art / "m7_tiles.png")
    Image.fromarray(tmap.astype(np.uint8), "L").save(art / "m7_map.png")
    tab = P.write_cgram()
    lut = np.array([P.rgb8(c) for c in tab], np.uint8)
    tiles_arr = np.stack(tiles + [np.zeros((T, T), np.uint8)] * (256 - n))
    full = tiles_arr[tmap][:, :, :, :].transpose(0, 2, 1, 3).reshape(MAP, MAP)
    Image.fromarray(lut[full]).save(STYLE / "assets/m7_map_preview.png")
    Image.fromarray(lut[sheet]).resize((512, 512), Image.NEAREST).save(STYLE / "assets/m7_tiles_sheet.png")
    np.save(STYLE / "assets/m7_tiles.npy", tiles_arr)
    (STYLE / "demo/data/plane.json").write_text(json.dumps({
        "tiles": n, "per_kind": counts, "colors": len(used), "map": [128, 128],
        "texel_m": 1 / TPM, "quay_u": [QU0, QU1], "quay_v0": QV0, "jetty_u": [JU0, JU1], "jetty_v": [JV0, JV1],
    }, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
