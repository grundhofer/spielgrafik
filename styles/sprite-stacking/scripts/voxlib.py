"""Hilfsfunktionen für die Schichtblätter: Filter, Normalen, Umgebungsverdeckung, Eigenschatten, Packen.

Koordinaten: Volumen als [Z, Y, X] (Schicht, Zeile, Spalte). x = Osten, y = Süden (Bildzeile), z = oben.
Eine Schicht ist LAYER_H Rasterweiten hoch (alle Modelle haben dasselbe Verhältnis, siehe blender/voxel_jobs.json).
"""
import numpy as np

LAYER_H = 0.75


def box1(a, r, axis):
    """Mittelwert über 2r+1 Nachbarn entlang einer Achse, außen mit 0 aufgefüllt."""
    if r <= 0:
        return a
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad), axis=axis, dtype=np.float32)
    n = a.shape[axis]
    hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return (hi - lo) / (2 * r + 1)


def blur3(a, r=1, rz=None):
    rz = r if rz is None else rz
    return box1(box1(box1(a.astype(np.float32), rz, 0), r, 1), r, 2)


def normals(occ, r=1, rz=1):
    """Normale aus dem geglätteten Belegungsfeld; Höhe in Weltmaß (Schicht = LAYER_H)."""
    b = blur3(occ, r, rz)
    gz, gy, gx = np.gradient(b)
    n = np.stack([-gx, -gy, -gz / LAYER_H], axis=-1)
    ln = np.linalg.norm(n, axis=-1, keepdims=True)
    up = np.zeros_like(n)
    up[..., 2] = 1
    n = np.where(ln > 1e-4, n / np.maximum(ln, 1e-6), up)
    return n.astype(np.float32)


def occlusion(occ, r=2, depth=3):
    """Anteil belegter Voxel in einem Kasten über und neben dem Voxel -> 1 = frei, 0 = zugebaut."""
    o = occ.astype(np.float32)
    b = box1(box1(o, r, 1), r, 2)            # Nachbarschaft in der Ebene
    acc = np.zeros_like(o)
    for k in range(1, depth + 1):            # Schichten darüber
        acc[:-k] += b[k:]
    acc /= depth
    side = box1(box1(o, 1, 1), 1, 2)         # direkte Nachbarn in derselben Schicht
    return np.clip(1.0 - 0.75 * acc - 0.35 * np.clip(side - 0.5, 0, 1), 0, 1)


def exposed(occ):
    """Sichtbar aus jeder Drehrichtung: nicht alle neun Voxel der Schicht darüber belegt."""
    o = occ.astype(np.float32)
    above = np.zeros_like(o)
    above[:-1] = box1(box1(o, 1, 1), 1, 2)[1:]
    return occ & (above < 0.999)


def self_shadow(occ, sun_local, steps=90):
    """Voxel, deren Strahl zur Sonne ein anderes Voxel desselben Modells trifft (nur für fest stehende Modelle)."""
    nz, ny, nx = occ.shape
    z, y, x = np.nonzero(exposed(occ))
    d = np.array([sun_local[0], sun_local[1], sun_local[2] / LAYER_H], np.float32)
    d /= np.abs(d).max()
    p = np.stack([x + 0.5, y + 0.5, z + 0.5], 1).astype(np.float32)
    hit = np.zeros(len(z), bool)
    for k in range(2, steps):
        q = p + d * (k * 0.5)
        qi = np.floor(q).astype(int)
        ok = (qi[:, 0] >= 0) & (qi[:, 0] < nx) & (qi[:, 1] >= 0) & (qi[:, 1] < ny) & (qi[:, 2] >= 0) & (qi[:, 2] < nz)
        if not ok.any():
            break
        h = np.zeros(len(z), bool)
        h[ok] = occ[qi[ok, 2], qi[ok, 1], qi[ok, 0]]
        hit |= h
    out = np.zeros(occ.shape, bool)
    out[z, y, x] = hit
    return out


def hash3(x, y, z, seed=0):
    """Ganzzahliger Hash -> [0, 1)."""
    h = (np.asarray(x, np.int64) * 73856093) ^ (np.asarray(y, np.int64) * 19349663) ^ \
        (np.asarray(z, np.int64) * 83492791) ^ (seed * 2654435761)
    h = (h ^ (h >> 13)) * 1274126177
    h = h ^ (h >> 16)
    return (h & 0xFFFF).astype(np.float32) / 65536.0


def shelf_pack(sizes, width):
    """Rechtecke (w, h) zeilenweise packen; liefert Positionen und Gesamthöhe."""
    order = sorted(range(len(sizes)), key=lambda i: -sizes[i][1])
    pos = [None] * len(sizes)
    x = y = row_h = 0
    for i in order:
        w, h = sizes[i]
        if x + w > width:
            x, y, row_h = 0, y + row_h + 1, 0
        pos[i] = (x, y)
        x += w + 1
        row_h = max(row_h, h)
    return pos, y + row_h
