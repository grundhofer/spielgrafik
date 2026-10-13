"""Geometrie der Übergangskacheln (Corner-Terrain / Dual-Grid, 16 Fälle je Terrain gegen 'leer').

Eine Anzeigekachel liegt um eine halbe Kachel versetzt über dem logischen Raster; ihre vier Ecken sind die
Mittelpunkte von vier logischen Zellen. Bit 0 = oben links, 1 = oben rechts, 2 = unten links, 3 = unten rechts.
Berechnet wird auf einem erweiterten Raster [-8, 24) (die vier logischen Zellen vollständig), damit Abstände bis
8 px exakt sind und Bänder (Schaum, Mauer, Schatten) über Kachelkanten hinweg nahtlos anschließen.
"""
import numpy as np

T = 16
EXT = 8
N = T + 2 * EXT
_xs = np.arange(N) - EXT + 0.5
X, Y = np.meshgrid(_xs, _xs)
IN_TILE = (slice(EXT, EXT + T), slice(EXT, EXT + T))

HN = {0: 1, 1: 0, 2: 3, 3: 2}   # waagrechter Nachbar-Quadrant
VN = {0: 2, 1: 3, 2: 0, 3: 1}   # senkrechter Nachbar-Quadrant
DG = {0: 3, 1: 2, 2: 1, 3: 0}
SX = {0: -1, 1: 1, 2: -1, 3: 1}
SY = {0: -1, 1: -1, 2: 1, 3: 1}


def bits(cfg):
    return [(cfg >> i) & 1 for i in range(4)]


def shape(cfg, r_convex=0.0, r_concave=0.0):
    """Bool-Feld (N x N): innen = Terrain. Rundung nur um die Kachelmitte, erreicht die Kachelkanten nie."""
    b = np.array(bits(cfg))
    c = T / 2
    q = np.where(Y < c, np.where(X < c, 0, 1), np.where(X < c, 2, 3))
    ins = b[q].astype(bool)
    for k in range(4):
        inq = q == k
        if b[k] and not b[HN[k]] and not b[VN[k]] and r_convex > 0:
            r = r_convex
        elif (not b[k]) and b[HN[k]] and b[VN[k]] and b[DG[k]] and r_concave > 0:
            r = r_concave
        else:
            continue
        cx, cy = c + SX[k] * r, c + SY[k] * r
        zone = inq & ((X - cx) * SX[k] < 0) & ((Y - cy) * SY[k] < 0) & (np.hypot(X - cx, Y - cy) > r)
        ins = np.where(zone, not b[k], ins)
    return ins


def distances(ins):
    """Vorzeichenbehafteter Abstand je Pixelmitte: innen >0 (Abstand zur nächsten Außen-Pixelmitte - 0,5),
    außen <0. Brute force über 32x32 Punkte."""
    pts = np.stack([X.ravel(), Y.ravel()], 1)
    flat = ins.ravel()
    s = np.zeros(len(pts))
    if flat.all():
        return np.full(ins.shape, 99.0)
    if not flat.any():
        return np.full(ins.shape, -99.0)
    I, O = pts[flat], pts[~flat]
    d_out = np.sqrt(((I[:, None] - O[None]) ** 2).sum(-1)).min(1)
    d_in = np.sqrt(((O[:, None] - I[None]) ** 2).sum(-1)).min(1)
    s[flat] = d_out - 0.5
    s[~flat] = -(d_in - 0.5)
    return s.reshape(ins.shape)


def pnoise(seed, cell=4, period=T):
    """Periodische Wertrausch-Fläche (period x period) mit Werten 0..1, bikubisch geglättet."""
    rng = np.random.default_rng(seed)
    g = period // cell
    lat = rng.random((g, g))
    ys = (np.arange(period) + 0.5) / cell - 0.5
    i0 = np.floor(ys).astype(int)
    f = ys - i0
    f = f * f * (3 - 2 * f)
    rows = lat[(i0 % g)][:, :] * (1 - f)[:, None] + lat[((i0 + 1) % g)] * f[:, None]
    out = rows[:, i0 % g] * (1 - f)[None] + rows[:, (i0 + 1) % g] * f[None]
    out -= out.min()
    return out / max(out.max(), 1e-9)


def ext(tile_arr):
    """16x16-periodisches Feld auf das erweiterte Raster (32x32) legen."""
    idx = (np.arange(N) - EXT) % T
    return tile_arr[np.ix_(idx, idx)]


def shifted(ins, dx, dy):
    """ins verschoben: out[y, x] = ins[y - dy, x - dx] (außerhalb: False)."""
    out = np.zeros_like(ins)
    ys = slice(max(dy, 0), N + min(dy, 0))
    xs = slice(max(dx, 0), N + min(dx, 0))
    ys2 = slice(max(-dy, 0), N + min(-dy, 0))
    xs2 = slice(max(-dx, 0), N + min(-dx, 0))
    out[ys, xs] = ins[ys2, xs2]
    return out
