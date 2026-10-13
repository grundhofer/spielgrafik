#!/usr/bin/env python3
"""Bildausschnitt vorab rechnen: projiziert wichtige Punkte des Hafens für eine Kamera (Position, Blickziel,
vertikaler fov, Keep Height) auf 1280×720, wie Godot es mit Camera3D.look_at_from_position tut.

    .venv/bin/python styles/handpainted-3d/scripts/plan_shot.py --cam -1.5,2.4,9 --look -3.5,1.4,-2 --fov 40

Punkte in Godot-Koordinaten aus shared/3d/harbor_notes.md und badger_notes.md.
"""
import argparse
import math

import numpy as np

W, H = 1280, 720
POINTS = {
    "Häuschen Ecke vorn links unten": (-10.2, 0.0, 0.5),
    "Häuschen Ecke vorn rechts unten": (-6.6, 0.0, 0.5),
    "Häuschen Traufe vorn rechts": (-6.6, 2.45, 0.5),
    "Häuschen First rechts": (-6.6, 3.8, -1.0),
    "Schornstein oben": (-9.58, 4.9, -1.35),
    "Fenster vorn": (-9.2, 1.45, 0.52),
    "Fass 1": (-5.25, 0.9, -0.15),
    "Fass 2": (-4.55, 0.9, -0.62),
    "Poller links": (-3.4, 0.5, -0.7),
    "Taurolle": (1.05, 0.2, 0.05),
    "Boot A": (0.05, 0.4, -6.1),
    "Boot B": (6.75, 0.4, -6.4),
    "Steg vorn": (3.45, 0.04, -0.45),
    "Laterne": (4.1, 1.79, -0.12),
    "Laternenpfahl oben": (4.6, 2.45, -0.12),
    "Kisten": (6.55, 0.6, 0.2),
    "Leuchtfeuer": (10.2, 12.58, -25.6),
    "Leuchtturm Fuß": (10.2, 2.8, -25.6),
    "Horizont (Meer 900 m)": (0.0, -0.8, -900.0),
}


def basis(cam, look):
    f = np.array(look, float) - np.array(cam, float)
    f /= np.linalg.norm(f)
    r = np.cross(f, [0.0, 1.0, 0.0])
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    return r, u, f


def project(p, cam, look, fov):
    r, u, f = basis(cam, look)
    d = np.array(p, float) - np.array(cam, float)
    z = d @ f
    if z <= 0.01:
        return None
    t = math.tan(math.radians(fov) / 2)
    x = (d @ r) / (z * t * W / H)
    y = (d @ u) / (z * t)
    return (W / 2 * (1 + x), H / 2 * (1 - y), z)


def badger(x, z, cam, look, fov):
    a = project((x, 0.0, z), cam, look, fov)
    b = project((x, 1.011, z), cam, look, fov)
    return a, b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cam", required=True)
    ap.add_argument("--look", required=True)
    ap.add_argument("--fov", type=float, default=40.0)
    ap.add_argument("--badger", default="-6,-3,-1.5", help="x-Positionen des Dachses auf z = 1,2")
    ap.add_argument("--bz", type=float, default=1.2)
    a = ap.parse_args()
    cam = [float(v) for v in a.cam.split(",")]
    look = [float(v) for v in a.look.split(",")]
    r, u, f = basis(cam, look)
    pitch = math.degrees(math.asin(f[1]))
    yaw = math.degrees(math.atan2(-f[0], -f[2]))
    print(f"Kamera {cam} Blick {look} fov {a.fov}: Neigung {pitch:.1f}°, Gieren {yaw:.1f}°")
    for k, p in POINTS.items():
        q = project(p, cam, look, a.fov)
        s = "hinter der Kamera" if q is None else f"({q[0]:7.1f} | {q[1]:6.1f})  Abstand {q[2]:6.1f} m" + \
            ("" if 0 <= q[0] <= W and 0 <= q[1] <= H else "  AUSSERHALB")
        print(f"  {k:32s} {s}")
    for x in [float(v) for v in a.badger.split(",")]:
        fo, he = badger(x, a.bz, cam, look, a.fov)
        print(f"  Dachs x={x:5.2f}: Füße ({fo[0]:6.1f} | {fo[1]:6.1f}), Kopf y {he[1]:6.1f}, Höhe {fo[1]-he[1]:5.1f} px")


if __name__ == "__main__":
    main()
