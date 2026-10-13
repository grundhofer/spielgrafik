#!/usr/bin/env python3
"""Passt die Projektion des Eingabebilds auf das TripoSR-Mesh an (für das Backen der Vorderansicht).

TripoSR rekonstruiert im Kamerarahmen des Eingabebilds: Kamera auf +X, Blick nach -X, oben +Z, rechts +Y.
Modell: u = cx + k * y / (D - x),  v = cy - k * z / (D - x)  (Pixel im quadratischen input_rgba.png).
Gesucht werden D (Perspektive), k (Maßstab) und cx, cy so, dass die Silhouette des Meshes den Alphakanal des
Eingabebilds deckt (IoU). Ein fester Bildwinkel (1,9 m / 40°, die Standardwerte von TripoSR.render) passte nur
bei Fass und Dachs (IoU 0,91 bzw. 0,88), bei Laterne und Boot nicht (0,53 bzw. 0,64): das Mesh liegt dort kleiner
und verschoben im Bild. Ergebnis je Ordner: proj.json.

    tsr/venv/bin/python -I scripts/fit_projection.py work/tsr/barrel [work/tsr/badger_front ...]
"""
import json, sys, pathlib
import numpy as np
import trimesh
from PIL import Image
from scipy import ndimage

S = 512


def raster(u, v, faces):
    m = np.zeros((S, S), bool)
    P = [np.stack([u, v], 1)]
    for a, b in ((0, 1), (1, 2), (2, 0)):
        P.append((P[0][faces[:, a]] + P[0][faces[:, b]]) / 2)
    P = np.concatenate(P).astype(int)
    ok = (P[:, 0] >= 0) & (P[:, 0] < S) & (P[:, 1] >= 0) & (P[:, 1] < S)
    m[P[ok, 1], P[ok, 0]] = True
    return ndimage.binary_fill_holes(ndimage.binary_closing(m, iterations=2))


def iou(a, b):
    return float((a & b).sum() / max((a | b).sum(), 1))


def bbox(m):
    ys, xs = np.where(m)
    return xs.min(), xs.max(), ys.min(), ys.max()


def fit(V, F, gt):
    gx0, gx1, gy0, gy1 = bbox(gt)
    best = None
    for D in np.arange(1.5, 2.55, 0.1):
        u0, v0 = V[:, 1] / (D - V[:, 0]), -V[:, 2] / (D - V[:, 0])
        mu0, mu1, mv0, mv1 = u0.min(), u0.max(), v0.min(), v0.max()
        k = 0.5 * ((gx1 - gx0) / (mu1 - mu0) + (gy1 - gy0) / (mv1 - mv0))
        for dk in (0.97, 0.985, 1.0, 1.015, 1.03):
            kk = k * dk
            cx = 0.5 * (gx0 + gx1) - kk * 0.5 * (mu0 + mu1)
            cy = 0.5 * (gy0 + gy1) - kk * 0.5 * (mv0 + mv1)
            for ox in (-3, 0, 3):
                for oy in (-3, 0, 3):
                    m = raster(cx + ox + kk * u0, cy + oy + kk * v0, F)
                    s = iou(m, gt)
                    if best is None or s > best[0]:
                        best = (s, float(D), float(kk), float(cx + ox), float(cy + oy))
    return best


def main():
    for d in map(pathlib.Path, sys.argv[1:]):
        mesh = trimesh.load(d / "mesh.ply", process=False)
        V, F = np.asarray(mesh.vertices), np.asarray(mesh.faces)
        a = np.array(Image.open(d / "input_rgba.png"))[..., 3]
        gt = np.array(Image.fromarray(a).resize((S, S), Image.BILINEAR)) > 127
        # Vergleich: Standardkamera 1,9 m / 40°
        t = np.tan(np.radians(20))
        dep = 1.9 - V[:, 0]
        m0 = raster((0.5 + 0.5 * V[:, 1] / (dep * t)) * S, (0.5 - 0.5 * V[:, 2] / (dep * t)) * S, F)
        s, D, k, cx, cy = fit(V, F, gt)
        out = {"D": round(D, 3), "k_norm": k / S, "cx_norm": cx / S, "cy_norm": cy / S, "iou": round(s, 4),
               "iou_default_1.9m_40deg": round(iou(m0, gt), 4),
               "model": "u = cx + k*y/(D-x), v = cy - k*z/(D-x), normiert auf die Bildbreite des quadratischen Eingabebilds"}
        (d / "proj.json").write_text(json.dumps(out, indent=1))
        print(d.name, {k_: out[k_] for k_ in ("D", "iou", "iou_default_1.9m_40deg")})


main()
