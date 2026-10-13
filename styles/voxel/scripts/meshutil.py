"""Hilfen für die Voxelisierung: Dreiecke je Objekt, Zusammenhangskomponenten, Geschlossenheit."""
import numpy as np


def weld(v, eps=1e-5):
    """Punkte mit gleicher Position zusammenlegen -> (Index je Punkt, Anzahl eindeutiger Punkte)."""
    q = np.round(v / eps).astype(np.int64)
    _, inv = np.unique(q, axis=0, return_inverse=True)
    return inv.reshape(-1), inv.max() + 1


def components(tris_v):
    """tris_v: (n,3,3) Dreiecke. Gibt Komponentennummer je Dreieck und je Komponente 'geschlossen' zurück."""
    n = len(tris_v)
    vid, nv = weld(tris_v.reshape(-1, 3))
    f = vid.reshape(n, 3)
    # Union-Find über Punkte
    par = np.arange(nv)

    def find(a):
        r = a
        while par[r] != r:
            r = par[r]
        while par[a] != r:
            par[a], a = r, par[a]
        return r

    for a, b, c in f:
        ra, rb, rc = find(a), find(b), find(c)
        par[rb] = ra
        par[find(rc)] = ra
    roots = np.array([find(i) for i in range(nv)])
    comp_of_tri = roots[f[:, 0]]
    uniq, comp_of_tri = np.unique(comp_of_tri, return_inverse=True)
    closed = []
    for ci in range(len(uniq)):
        ff = f[comp_of_tri == ci]
        e = np.sort(np.concatenate([ff[:, [0, 1]], ff[:, [1, 2]], ff[:, [2, 0]]]), axis=1)
        _, cnt = np.unique(e, axis=0, return_counts=True)
        closed.append(bool(np.all(cnt == 2)))
    return comp_of_tri, closed
