"""Kern der Voxelisierung (nur numpy): Dreiecke -> belegte Zellen + Material je Zelle -> Würfelflächen mit
Voxel-AO je Ecke. Von voxelize_harbor.py und voxelize_badger.py benutzt.

Zellen sind ganzzahlige Indizes (i, j, k) in einem Gitter mit Ursprung g0 und Kantenlänge s; die Mitte einer
Zelle liegt bei g0 + (idx + 0,5) * s.
"""
import numpy as np

from meshutil import components

# Mitten der Strahlen minimal versetzen, damit sie nie genau auf achsenparallelen Kanten liegen
JIT = np.array([1.37e-5, 2.11e-5, 0.73e-5])


def tri_raster(T, axis, g0, s, lo, hi):
    """Schneidet Strahlen entlang `axis` durch die Zellmitten mit den Dreiecken T (n,3,3).
    Gibt (a, b, wert, dreieck) je Treffer zurück: a, b = Zellindizes der beiden anderen Achsen (global),
    wert = Koordinate auf `axis`."""
    a1, a2 = [k for k in range(3) if k != axis]
    out_a, out_b, out_v, out_t = [], [], [], []
    for ti, tri in enumerate(T):
        p = tri[:, [a1, a2]]
        mn = np.ceil((p.min(0) - g0[[a1, a2]] - JIT[[a1, a2]]) / s - 0.5).astype(int)
        mx = np.floor((p.max(0) - g0[[a1, a2]] - JIT[[a1, a2]]) / s - 0.5).astype(int)
        mn = np.maximum(mn, [lo[a1], lo[a2]])
        mx = np.minimum(mx, [hi[a1] - 1, hi[a2] - 1])
        if mx[0] < mn[0] or mx[1] < mn[1]:
            continue
        ia = np.arange(mn[0], mx[0] + 1)
        ib = np.arange(mn[1], mx[1] + 1)
        A, B = np.meshgrid(ia, ib, indexing="ij")
        A = A.ravel(); B = B.ravel()
        px = g0[a1] + (A + 0.5) * s + JIT[a1]
        py = g0[a2] + (B + 0.5) * s + JIT[a2]
        (x0, y0), (x1, y1), (x2, y2) = p
        det = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(det) < 1e-12:
            continue
        l0 = ((y1 - y2) * (px - x2) + (x2 - x1) * (py - y2)) / det
        l1 = ((y2 - y0) * (px - x2) + (x0 - x2) * (py - y2)) / det
        l2 = 1.0 - l0 - l1
        m = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
        if not m.any():
            continue
        v = l0[m] * tri[0, axis] + l1[m] * tri[1, axis] + l2[m] * tri[2, axis]
        out_a.append(A[m]); out_b.append(B[m]); out_v.append(v); out_t.append(np.full(m.sum(), ti))
    if not out_a:
        e = np.zeros(0, int)
        return e, e, np.zeros(0), e
    return np.concatenate(out_a), np.concatenate(out_b), np.concatenate(out_v), np.concatenate(out_t)


def parity_votes(T, g0, s, lo, hi):
    """Innen-Test der Zellmitten für eine geschlossene (oder fast geschlossene) Komponente:
    Parität entlang aller drei Achsen; Spalten mit ungerader Trefferzahl enthalten sich.
    Gibt bool-Feld (Form hi-lo) zurück: innen nach Mehrheit."""
    shape = tuple(hi - lo)
    ins = np.zeros(shape, np.int8)
    known = np.zeros(shape, np.int8)
    for axis in range(3):
        a1, a2 = [k for k in range(3) if k != axis]
        A, B, V, _ = tri_raster(T, axis, g0, s, lo, hi)
        if len(A) == 0:
            continue
        key = (A - lo[a1]) * shape[a2] + (B - lo[a2])
        order = np.lexsort((V, key))
        key, V = key[order], V[order]
        uk, start, cnt = np.unique(key, return_index=True, return_counts=True)
        ins_ax = np.zeros(shape, bool)
        known_ax = np.zeros(shape, bool)
        for k, st, c in zip(uk, start, cnt):
            ia, ib = divmod(int(k), shape[a2])
            idx = [slice(None)] * 3
            idx[a1] = ia; idx[a2] = ib
            if c % 2:
                continue
            known_ax[tuple(idx)] = True
            col = np.zeros(shape[axis], bool)
            for q in range(st, st + c, 2):
                c0 = int(np.ceil((V[q] - g0[axis] - JIT[axis]) / s - 0.5)) - lo[axis]
                c1 = int(np.floor((V[q + 1] - g0[axis] - JIT[axis]) / s - 0.5)) - lo[axis]
                c0 = max(c0, 0); c1 = min(c1, shape[axis] - 1)
                if c1 >= c0:
                    col[c0:c1 + 1] = True
            ins_ax[tuple(idx)] = col
        # Spalten ohne Treffer sind sicher außen
        known_ax2 = known_ax.copy()
        hitcols = np.zeros([shape[a1], shape[a2]], bool)
        hitcols[(uk // shape[a2]).astype(int), (uk % shape[a2]).astype(int)] = True
        nohit = ~hitcols
        nohit_full = np.expand_dims(nohit, axis)
        known_ax2 |= np.broadcast_to(nohit_full, shape)
        ins += ins_ax
        known += known_ax2
    return (ins * 2 > known) & (ins > 0)


def winding_inside(T, g0, s, lo, hi, chunk=60):
    """Verallgemeinerte Windungszahl (Summe der Raumwinkel / 4 pi) an allen Zellmitten des Teilgitters.
    Robust gegen überlappende Teile und kleine Öffnungen; innen, wenn > 0,5."""
    shape = tuple(hi - lo)
    idx = np.indices(shape).reshape(3, -1).T
    P = g0 + (idx + lo + 0.5) * s + JIT
    w = np.zeros(len(P))
    T = T.astype(np.float64)
    for a in range(0, len(P), chunk):
        p = P[a:a + chunk, None, None, :]
        R = T[None] - p                                   # (c, n, 3, 3)
        A_, B_, C_ = R[:, :, 0], R[:, :, 1], R[:, :, 2]
        la, lb, lc = (np.linalg.norm(X, axis=-1) for X in (A_, B_, C_))
        num = (A_ * np.cross(B_, C_)).sum(-1)
        den = la * lb * lc + (A_ * B_).sum(-1) * lc + (B_ * C_).sum(-1) * la + (C_ * A_).sum(-1) * lb
        w[a:a + chunk] = (2.0 * np.arctan2(num, den)).sum(1) / (4 * np.pi)
    return (w > 0.5).reshape(shape)


def sample_triangles(T, step):
    """Gleichmäßige Punkte auf den Dreiecken (Abstand <= step). Gibt Punkte und Dreiecksindex zurück."""
    pts, tid = [], []
    for ti, tri in enumerate(T):
        e = max(np.linalg.norm(tri[1] - tri[0]), np.linalg.norm(tri[2] - tri[1]), np.linalg.norm(tri[0] - tri[2]))
        n = max(1, int(np.ceil(e / step)))
        i, j = np.meshgrid(np.arange(n + 1), np.arange(n + 1), indexing="ij")
        m = (i + j) <= n
        u = (i[m] + 1 / 3) / (n + 1); v = (j[m] + 1 / 3) / (n + 1)
        p = tri[0] + np.outer(u, tri[1] - tri[0]) + np.outer(v, tri[2] - tri[0])
        pts.append(p); tid.append(np.full(len(p), ti))
    return np.concatenate(pts), np.concatenate(tid)


def tri_normals(T):
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    return n / np.maximum(ln, 1e-12)


def dilate6(b):
    o = b.copy()
    o[1:] |= b[:-1]; o[:-1] |= b[1:]
    o[:, 1:] |= b[:, :-1]; o[:, :-1] |= b[:, 1:]
    o[:, :, 1:] |= b[:, :, :-1]; o[:, :, :-1] |= b[:, :, 1:]
    return o


def dilate26(b):
    o = b.copy()
    for ax in range(3):
        p = o.copy()
        sl1 = [slice(None)] * 3; sl2 = [slice(None)] * 3
        sl1[ax] = slice(1, None); sl2[ax] = slice(None, -1)
        p[tuple(sl1)] |= o[tuple(sl2)]
        p[tuple(sl2)] |= o[tuple(sl1)]
        o = p
    return o


def fill_materials(solid, mat, max_iter=40):
    """Zellen in solid ohne Material (mat < 0) erben das Material eines Nachbarn (Wellenfront)."""
    mat = mat.copy()
    for _ in range(max_iter):
        miss = solid & (mat < 0)
        if not miss.any():
            break
        for ax in range(3):
            for sh in (1, -1):
                nb = np.roll(mat, sh, axis=ax)
                # Ränder nicht umlaufen lassen
                sl = [slice(None)] * 3
                sl[ax] = 0 if sh == 1 else -1
                nb[tuple(sl)] = -1
                take = miss & (mat < 0) & (nb >= 0)
                mat[take] = nb[take]
    return mat


def voxelize_solid(T, M, g0, s, weights, heightfield=False, bottom=None, comp_small=1.0, close_gaps=False,
                   thin_ratio=0.6):
    """T: (n,3,3) Dreiecke in Gitterkoordinaten (Welt), M: Materialindex je Dreieck.
    Gibt (lo, solid[bool], mat[int16]) im Teilgitter lo..hi zurück."""
    allp = T.reshape(-1, 3)
    lo = np.floor((allp.min(0) - g0) / s).astype(int) - 1
    hi = np.ceil((allp.max(0) - g0) / s).astype(int) + 2
    if bottom is not None:
        lo[1] = min(lo[1], int(np.floor((bottom - g0[1]) / s)))
    shape = tuple(hi - lo)
    solid = np.zeros(shape, bool)
    thinmat = np.full(shape, -1, np.int16)
    N = tri_normals(T)

    if heightfield:
        A, B, V, TI = tri_raster(T, 1, g0, s, lo, hi)
        key = (A - lo[0]) * shape[2] + (B - lo[2])
        order = np.lexsort((V, key))
        key, V, TI = key[order], V[order], TI[order]
        last = np.r_[key[1:] != key[:-1], True]
        key, V, TI = key[last], V[last], TI[last]
        ia, ib = key // shape[2], key % shape[2]
        top = np.floor((V - g0[1] - JIT[1]) / s - 0.5).astype(int) - lo[1]
        top2 = np.full((shape[0], shape[2]), -1, int)
        tm2 = np.full((shape[0], shape[2]), -1, np.int16)
        top2[ia, ib] = top
        tm2[ia, ib] = M[TI]
        if close_gaps:
            # Fugen schließen: Spalten, die niedriger als beide Nachbarn (x oder z) liegen, anheben; das
            # Material der Fuge bleibt (dunkle Fuge in ebener Fläche statt eines Grabens)
            for _ in range(2):
                for ax in (0, 1):
                    a_ = np.roll(top2, 1, axis=ax); b_ = np.roll(top2, -1, axis=ax)
                    m_ = np.minimum(a_, b_)
                    raise_ = (m_ > top2) & (top2 >= 0) & (m_ - top2 <= 2)
                    top2 = np.where(raise_, m_, top2)
        for a in range(shape[0]):
            for b in np.nonzero(top2[a] >= 0)[0]:
                solid[a, :top2[a, b] + 1, b] = True
        topmat = np.full(shape, -1, np.int16)
        aa, bb = np.nonzero(top2 >= 0)
        topmat[aa, top2[aa, bb], bb] = tm2[aa, bb]
        comp = np.zeros(len(T), int)
    else:
        P, PT = sample_triangles(T, s / 3)
        comp, closed = components(T)
        order = np.argsort([-np.ptp(T[comp == c].reshape(-1, 3), axis=0).max() for c in range(len(closed))])
        solid |= winding_inside(T, g0, s, lo, hi)
        for c in order:
            sel = np.nonzero(comp == c)[0]
            ins = np.zeros(shape, bool)
            pm = np.isin(PT, sel)
            cells = np.floor((P[pm] - g0) / s).astype(int) - lo
            # dünne Teile (Bretter, Bootswände, Geländer, Ohren): ganze Oberfläche als Hülle (sonst Löcher);
            # Dicke geschätzt als 2 V / A (Platte der Dicke d: d, Würfel der Kante L: L/3)
            tt = T[sel]
            area = 0.5 * np.linalg.norm(np.cross(tt[:, 1] - tt[:, 0], tt[:, 2] - tt[:, 0]), axis=1).sum()
            vol = abs(np.einsum("ij,ij->i", tt[:, 0], np.cross(tt[:, 1], tt[:, 2])).sum() / 6.0)
            thin = (not closed[c]) or (2 * vol / max(area, 1e-9) < thin_ratio * s)
            if thin:
                add = np.ones(len(cells), bool)
            else:
                # dicke Teile: nur Punkte ergänzen, die weder in noch neben dem bisherigen Körper liegen
                near = dilate26(solid)
                add = ~near[cells[:, 0], cells[:, 1], cells[:, 2]]
            ins[cells[add, 0], cells[add, 1], cells[add, 2]] = True
            thinmat[cells[add, 0], cells[add, 1], cells[add, 2]] = M[PT[pm][add]]
            solid |= ins
        topmat = None

    # Material: Abstimmung der leicht nach innen versetzten Oberflächenpunkte
    if heightfield:
        P, PT = sample_triangles(T, s / 3)
    ext = {}
    if not heightfield:
        for c in np.unique(comp):
            ext[c] = np.ptp(T[comp == c].reshape(-1, 3), axis=0)
    thick = np.array([ext[c].min() if c in ext else s for c in comp])
    big = np.array([ext[c].max() if c in ext else 99.0 for c in comp])
    shift = np.minimum(0.3 * s, 0.45 * thick)[PT]
    Q = P - N[PT] * shift[:, None]
    cells = np.floor((Q - g0) / s).astype(int) - lo
    okc = np.all((cells >= 0) & (cells < shape), axis=1)
    cells, PT2 = cells[okc], PT[okc]
    inside = solid[cells[:, 0], cells[:, 1], cells[:, 2]]
    cells, PT2 = cells[inside], PT2[inside]
    nmat = int(M.max()) + 1
    w = np.array([weights.get(int(m), 1.0) for m in range(nmat)])[M[PT2]]
    w = w * np.where(big[PT2] < comp_small, 3.0, 1.0)
    flat = np.ravel_multi_index(cells.T, shape).astype(np.int64)
    key = flat * nmat + M[PT2]
    uk, inv = np.unique(key, return_inverse=True)
    ws = np.bincount(inv.ravel(), w)
    kc, km = uk // nmat, uk % nmat
    o = np.lexsort((ws, kc))
    kc, km = kc[o], km[o]
    last = np.r_[kc[1:] != kc[:-1], True]
    mat = np.full(int(np.prod(shape)), -1, np.int16)
    mat[kc[last]] = km[last]
    mat = mat.reshape(shape)
    if topmat is not None:
        mat = np.where(topmat >= 0, topmat, mat)
    mat = np.where((mat < 0) & (thinmat >= 0), thinmat, mat)
    mat = fill_materials(solid, mat)
    if (solid & (mat < 0)).any():
        vals, cnt = np.unique(mat[solid & (mat >= 0)], return_counts=True)
        mat[solid & (mat < 0)] = vals[cnt.argmax()] if len(vals) else int(np.bincount(M).argmax())
    mat[~solid] = -1
    return lo, solid, mat


FACE_DIRS = [  # Normale, zwei Tangenten (u, v) so, dass u x v = Normale
    (np.array([1, 0, 0]), np.array([0, 1, 0]), np.array([0, 0, 1])),
    (np.array([-1, 0, 0]), np.array([0, 0, 1]), np.array([0, 1, 0])),
    (np.array([0, 1, 0]), np.array([0, 0, 1]), np.array([1, 0, 0])),
    (np.array([0, -1, 0]), np.array([1, 0, 0]), np.array([0, 0, 1])),
    (np.array([0, 0, 1]), np.array([1, 0, 0]), np.array([0, 1, 0])),
    (np.array([0, 0, -1]), np.array([0, 1, 0]), np.array([1, 0, 0])),
]


def build_faces(cells, occ, occ_lo, g0, s, skip_dirs=(), keep=None):
    """cells: (n,3) globale Zellindizes eines Objekts. occ: bool-Belegung (für Sichtbarkeit und AO) mit
    Ursprung occ_lo. Gibt je Fläche: Zelle, Richtung, 4 Eckpunkte (Welt), AO je Ecke (0..3)."""
    shp = np.array(occ.shape)

    def occ_at(idx):
        r = idx - occ_lo
        ok = np.all((r >= 0) & (r < shp), axis=1)
        o = np.zeros(len(idx), bool)
        o[ok] = occ[r[ok, 0], r[ok, 1], r[ok, 2]]
        return o

    out = []
    for d, (n, u, v) in enumerate(FACE_DIRS):
        if d in skip_dirs:
            continue
        nb = cells + n
        vis = ~occ_at(nb)
        if keep is not None:
            vis &= keep(cells, d)
        c = cells[vis]
        if len(c) == 0:
            continue
        L = c + n
        # Ecken in Reihenfolge (-u,-v), (+u,-v), (+u,+v), (-u,+v)
        ao = []
        for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            s1 = occ_at(L + su * u)
            s2 = occ_at(L + sv * v)
            cc = occ_at(L + su * u + sv * v)
            a = np.where(s1 & s2, 0, 3 - (s1.astype(int) + s2 + cc))
            ao.append(a)
        ao = np.stack(ao, 1)
        center = g0 + (c + 0.5) * s
        corners = []
        for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            corners.append(center + 0.5 * s * (n + su * u + sv * v))
        out.append((c, np.full(len(c), d), np.stack(corners, 1), ao))
    if not out:
        return None
    return (np.concatenate([o[0] for o in out]), np.concatenate([o[1] for o in out]),
            np.concatenate([o[2] for o in out]), np.concatenate([o[3] for o in out]))


def faces_to_arrays(dirs, corners, ao, colors):
    """Flächen -> Vertex- und Indexarrays (4 Punkte je Fläche, Diagonale nach AO gedreht).
    colors: (n,3) uint8 sRGB je Fläche. AO 0..3 landet im Alphakanal (0, 85, 170, 255)."""
    n = len(dirs)
    pos = corners.reshape(-1, 3).astype(np.float32)
    nrm = np.repeat(np.array([f[0] for f in FACE_DIRS], np.float32)[dirs], 4, axis=0)
    col = np.zeros((n, 4, 4), np.uint8)
    col[:, :, :3] = colors[:, None, :]
    col[:, :, 3] = (ao * 85).astype(np.uint8)
    uv = np.tile(np.array([[0, 0], [255, 0], [255, 255], [0, 255]], np.uint8), (n, 1))   # normalisiert 0..1
    base = (np.arange(n) * 4)[:, None]
    flip = (ao[:, 0] + ao[:, 2]) < (ao[:, 1] + ao[:, 3])
    tri_a = np.array([0, 1, 2, 0, 2, 3])
    tri_b = np.array([1, 2, 3, 1, 3, 0])
    idx = np.where(flip[:, None], base + tri_b, base + tri_a).astype(np.uint32).reshape(-1)
    return pos, nrm, col.reshape(-1, 4), uv, idx


def line_hits(orig, dirs, T, tmin, tmax, chunk=200000):
    """Schneidet Geraden orig + t*dirs (t in [tmin, tmax]) mit den Dreiecken T.
    Gibt je Gerade (t des äußersten Treffers mit Dreiecksnormale in Richtung dirs-Gegenrichtung, Dreieck)
    zurück; kein Treffer -> (nan, -1). 'Äußerst' = größtes t entlang der Flächennormale n = -dirs."""
    n = len(orig)
    best_t = np.full(n, np.nan)
    best_i = np.full(n, -1)
    v0 = T[:, 0]; e1 = T[:, 1] - v0; e2 = T[:, 2] - v0
    tn = np.cross(e1, e2)
    per = max(1, chunk // max(len(T), 1))
    for a in range(0, n, per):
        o = orig[a:a + per, None, :]; d = dirs[a:a + per, None, :]
        p = np.cross(d, e2[None])
        det = (e1[None] * p).sum(-1)
        ok = np.abs(det) > 1e-12
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        tv = o - v0[None]
        u = (tv * p).sum(-1) * inv
        q = np.cross(tv, e1[None])
        v = (d * q).sum(-1) * inv
        t = (e2[None] * q).sum(-1) * inv
        front = ((tn[None] * d).sum(-1)) < 0          # Dreieck zeigt zur Fläche hin (Außenseite)
        hit = ok & (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1 + 1e-6) & (t >= tmin) & (t <= tmax) & front
        tt = np.where(hit, t, np.inf)
        # äußerster Treffer = kleinstes t (die Gerade läuft von außen nach innen)
        k = tt.argmin(1)
        tk = tt[np.arange(len(k)), k]
        good = np.isfinite(tk)
        best_t[a:a + per][good] = tk[good]
        best_i[a:a + per][good] = k[good]
    return best_t, best_i


def face_materials(fcell, fdir, g0, s, T, M, reach_out=0.6, reach_in=1.0):
    """Material, das man von außen auf einer Würfelfläche sieht: Gerade durch die Flächenmitte entlang der
    Normale, von reach_out*s außen nach innen bis reach_in*s innen; äußerste nach außen gewandte Fläche."""
    nrm = np.array([f[0] for f in FACE_DIRS], float)[fdir]
    center = g0 + (fcell + 0.5) * s + 0.5 * s * nrm
    orig = center + nrm * reach_out * s
    t, i = line_hits(orig, -nrm, T, 0.0, (reach_out + reach_in) * s)
    out = np.where(i >= 0, M[np.maximum(i, 0)], -1)
    return out


def voxel_materials_from_faces(cells, mat, fcell, fmat, weights, nmat):
    """Material je Voxel = gewichtete Mehrheit der von außen gesehenen Materialien seiner Flächen;
    Voxel ohne Treffer behalten mat."""
    lo = cells.min(0); dims = cells.max(0) - lo + 1
    kc = np.ravel_multi_index((cells - lo).T, dims)
    kf = np.ravel_multi_index((fcell - lo).T, dims)
    order = np.argsort(kc)
    row = order[np.searchsorted(kc[order], kf)]
    ok = fmat >= 0
    w = np.array([weights.get(k, 1.0) for k in range(nmat)])[fmat[ok]]
    votes = np.zeros((len(cells), nmat))
    np.add.at(votes, (row[ok], fmat[ok]), w)
    out = mat.copy()
    has = votes.sum(1) > 0
    out[has] = votes[has].argmax(1)
    return out
