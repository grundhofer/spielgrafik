"""Füllkacheln aus dem KI-Kachelblatt: auf ein echtes Raster bringen und nahtlos (periodisch 16 px) machen.

Das KI-Blatt (assets/raw/tiles.png, 8x8 KI-Kacheln) hat ein Pseudo-Raster von etwa 6,5 Bildpixeln je Kunstpixel,
also rund 24 Kunstpixel je KI-Kachel (verlangt waren 16). Die Spielkachel ist 16 px groß: aus dem Inneren jeder
KI-Kachel (20x20, Rand mit den gemalten Trennlinien weg) wird per Min-Cut eine 16x16-Kachel, die an allen vier
Seiten an sich selbst anschließt.
"""
import numpy as np
from PIL import Image

from pxlib import palette_from, snap_grid, srgb_to_oklab

T = 16
AI_CELLS = 24  # Kunstpixel je KI-Kachel (gemessen, siehe style.json)
ROWS = {"grass": 0, "sand": 1, "water": 2, "cobble": 3, "planks": 4}
NCOL = {"grass": 7, "sand": 5, "water": 6, "cobble": 7, "planks": 7}


def load_sheet(path):
    im = np.asarray(Image.open(path).convert("RGB"))
    tw = im.shape[1] / 8
    out = {}
    for name, r in ROWS.items():
        band = im[int(round(r * tw)):int(round((r + 1) * tw))]
        inner = band[10:-10]  # Palettenfarben ohne Saum der Nachbarreihe
        pal = palette_from(inner, NCOL[name], seed=3)
        idx = snap_grid(band, pal, AI_CELLS * 8, AI_CELLS, inner=0.5)
        out[name] = (pal, [idx[:, c * AI_CELLS:(c + 1) * AI_CELLS] for c in range(8)])
    return out


def _cut_path(err, wrap=True):
    """Min-Cut durch eine Fehlerfläche err[n, o] (n Schritte, o Spalten): Pfad c[n] in 0..o mit |c_i - c_i+1| <= 1.
    c = Anzahl Spalten, die vom 'linken' Teil (Fortsetzung) genommen werden. Bei wrap muss c[0] und c[n-1] passen."""
    n, o = err.shape
    # Kosten, die Schnittstelle zwischen Spalte c-1 und c zu legen: err an Spalte c (0..o) -> Rand
    cost = np.zeros((n, o + 1))
    for c in range(o + 1):
        a = err[:, c - 1] if c > 0 else 0
        b = err[:, c] if c < o else 0
        cost[:, c] = a + b
    best = None
    starts = range(o + 1) if wrap else [None]
    for s in starts:
        D = np.full((n, o + 1), np.inf)
        if s is None:
            D[0] = cost[0]
        else:
            D[0, s] = cost[0, s]
        P = np.zeros((n, o + 1), int)
        for i in range(1, n):
            for c in range(o + 1):
                lo, hi = max(0, c - 1), min(o, c + 1)
                j = lo + int(np.argmin(D[i - 1, lo:hi + 1]))
                D[i, c] = D[i - 1, j] + cost[i, c]
                P[i, c] = j
        ends = range(o + 1) if s is None else [c for c in range(o + 1) if abs(c - s) <= 1]
        for e in ends:
            if best is None or D[n - 1, e] < best[0]:
                path = [e]
                for i in range(n - 1, 0, -1):
                    path.append(P[i, path[-1]])
                best = (D[n - 1, e], path[::-1])
    return np.array(best[1])


def make_periodic(idx, pal, size=T, ov=4, x0=2, y0=2):
    """idx: Indexbild (>= size+ov+Rand). Ergebnis: size x size, periodisch, Nähte per Min-Cut."""
    lab = srgb_to_oklab(pal)
    P = idx[y0:y0 + size + ov, x0:x0 + size + ov]
    # waagrecht: Spalten 0..ov-1 aus P[:, size+x] (Fortsetzung von rechts) oder P[:, x]
    e = np.sqrt(((lab[P[:, :ov]] - lab[P[:, size:size + ov]]) ** 2).sum(-1))
    cut = _cut_path(e)
    H = P[:, :size].copy()
    for y in range(P.shape[0]):
        H[y, :cut[y]] = P[y, size:size + cut[y]]
    # senkrecht: Zeilen 0..ov-1 aus H[size+y] oder H[y]
    e = np.sqrt(((lab[H[:ov]] - lab[H[size:size + ov]]) ** 2).sum(-1)).T
    cut = _cut_path(e)
    V = H[:size].copy()
    for x in range(size):
        V[:cut[x], x] = H[size:size + cut[x], x]
    return V


def seam_error(tile, pal):
    """Mittlerer Farbabstand über die Umbruchkanten verglichen mit dem Inneren (1,0 = so glatt wie innen)."""
    lab = srgb_to_oklab(pal)[tile]
    inner = np.sqrt(((lab[:, 1:] - lab[:, :-1]) ** 2).sum(-1)).mean() + np.sqrt(((lab[1:] - lab[:-1]) ** 2).sum(-1)).mean()
    wrap = np.sqrt(((lab[:, 0] - lab[:, -1]) ** 2).sum(-1)).mean() + np.sqrt(((lab[0] - lab[-1]) ** 2).sum(-1)).mean()
    return wrap / inner


def blend_variant(base, other, seed, margin=3):
    """Variante: Inneres aus einer anderen KI-Kachel, Rand (margin px) von der Grundkachel. Die Grenze ist ein
    verrauschtes Rechteck, damit sie im Rauschen der Textur verschwindet. So passen alle Varianten an alle Kanten."""
    rng = np.random.default_rng(seed)
    m = np.zeros((T, T), bool)
    m[margin:T - margin, margin:T - margin] = True
    edge = m & ~np.pad(m, 1)[2:, 1:-1] | m & ~np.pad(m, 1)[:-2, 1:-1] | m & ~np.pad(m, 1)[1:-1, 2:] | m & ~np.pad(m, 1)[1:-1, :-2]
    m[edge & (rng.random((T, T)) < 0.5)] = False
    out = base.copy()
    out[m] = other[m]
    return out


def make_periodic_best(idx, pal, size=T):
    """Ausschnitt (x0, y0 in 1..4, Überlappung 3 oder 4) mit dem kleinsten Nahtfehler wählen.
    x0/y0 = 0 bleibt aus, weil dort die gemalten Trennlinien des KI-Blatts liegen."""
    best = None
    for ov in (3, 4):
        for x0 in range(1, idx.shape[1] - size - ov + 1):
            for y0 in range(1, idx.shape[0] - size - ov + 1):
                t = make_periodic(idx, pal, size, ov, x0, y0)
                e = seam_error(t, pal)
                if best is None or e < best[0]:
                    best = (e, t, (x0, y0, ov))
    return best
