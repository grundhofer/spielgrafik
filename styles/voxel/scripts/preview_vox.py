#!/usr/bin/env python3
"""Schnelle Orthografie-Vorschau einer Voxel-glb (ohne Godot): zeichnet die Würfelflächen von vorn (+x),
von der Seite (+z) und von schräg oben, mit einfacher Beleuchtung je Flächenrichtung und dem gebackenen AO.

    .venv/bin/python styles/voxel/scripts/preview_vox.py demo/models/badger_voxel.glb out.png [--px 12]
"""
import argparse, pathlib, sys
import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from glb import read_glb, world_matrices

LIGHT = {(1, 0, 0): 0.80, (-1, 0, 0): 0.62, (0, 1, 0): 1.0, (0, -1, 0): 0.45, (0, 0, 1): 0.88, (0, 0, -1): 0.55}


def load_faces(path, only=None):
    j, A = read_glb(path)
    W, _ = world_matrices(j)
    quads = []
    for i, n in enumerate(j["nodes"]):
        if "mesh" not in n or (only and n["name"] not in only):
            continue
        Wm = np.eye(4) if "skin" in n else W[i]
        for p in j["meshes"][n["mesh"]]["primitives"]:
            if "COLOR_0" not in p["attributes"]:
                continue
            pos = A[p["attributes"]["POSITION"]].astype(float)
            pos = pos @ Wm[:3, :3].T + Wm[:3, 3]
            nrm = A[p["attributes"]["NORMAL"]] @ Wm[:3, :3].T
            col = A[p["attributes"]["COLOR_0"]]
            q = len(pos) // 4
            quads.append((pos.reshape(q, 4, 3), np.round(nrm.reshape(q, 4, 3)[:, 0]).astype(int),
                          col.reshape(q, 4, 4)))
    P = np.concatenate([a[0] for a in quads]); N = np.concatenate([a[1] for a in quads])
    C = np.concatenate([a[2] for a in quads])
    return P, N, C


def render(P, N, C, view, px):
    """view: (rechts, oben, zur Kamera) als Einheitsvektoren."""
    r, u, f = [np.array(v, float) for v in view]
    vis = (N @ f) > 0.5
    P, N, C = P[vis], N[vis], C[vis]
    x = P @ r; y = P @ u; z = P @ f
    x0, y0 = x.min(), y.min()
    w = int(np.ceil((x.max() - x0) * px)) + 2; h = int(np.ceil((y.max() - y0) * px)) + 2
    img = np.full((h, w, 3), (255, 0, 255), np.uint8)
    zb = np.full((h, w), -1e9)
    order = np.argsort(z.mean(1))
    for q in order:
        xs = (x[q] - x0) * px; ys = (h - 1) - (y[q] - y0) * px
        c0, c1 = int(round(xs.min())), int(round(xs.max()))
        r0, r1 = int(round(ys.min())), int(round(ys.max()))
        if c1 <= c0 or r1 <= r0:
            continue
        col = C[q, :, :3].mean(0)
        ao = C[q, :, 3].mean()
        lit = LIGHT[tuple(N[q])] * (0.45 + 0.55 * ao)
        img[r0:r1, c0:c1] = np.clip(col * lit * 255, 0, 255)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("glb"); ap.add_argument("out"); ap.add_argument("--px", type=float, default=12)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    P, N, C = load_faces(a.glb, [x for x in a.only.split(",") if x])
    views = [((0, 0, -1), (0, 1, 0), (1, 0, 0)), ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
             ((0, 0, 1), (0, 1, 0), (-1, 0, 0)), ((1, 0, 0), (0, 0, -1), (0, 1, 0))]
    ims = [render(P, N, C, v, a.px * 24) for v in views]
    h = max(i.shape[0] for i in ims)
    canvas = np.full((h, sum(i.shape[1] for i in ims) + 20 * len(ims), 3), 200, np.uint8)
    x = 0
    for im in ims:
        canvas[h - im.shape[0]:, x:x + im.shape[1]] = im
        x += im.shape[1] + 20
    Image.fromarray(canvas).save(a.out)


if __name__ == "__main__":
    main()
