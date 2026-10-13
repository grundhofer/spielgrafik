#!/usr/bin/env python3
"""Bildausschnitt der Knete-Demo vorab rechnen (Projektion wie Godot: YXZ-Euler, fov vertikal, Keep Height).

    .venv/bin/python styles/knete/scripts/frame_shot.py --pos -0.6 0.9 5.15 --rot 6 -10 0 --fov 42

Gibt für die wichtigen Punkte der Szene die Bildposition in 1280x720 aus (x, y in px; außerhalb = '--').
Gewählt (main.tscn): Position (-0.6, 0.9, 5.15), rotation_degrees (6, -10, 0), fov 42. Der Laufweg liegt in der
Demo auf z = 0,95 (Plattenreihe zwischen zwei Fugen), nicht auf z = 1,2 wie in shared/3d.
"""
import argparse, math
import numpy as np

W, H = 1280, 720

POINTS = {
    "Dachs Fuß x=-2.75": (-2.75, 0.0, 0.95), "Dachs Kopf x=-2.75": (-2.75, 1.01, 0.95),
    "Dachs Fuß x=-2": (-2.0, 0.0, 0.95), "Dachs Kopf x=-2": (-2.0, 1.01, 0.95),
    "Dachs Fuß x=-0.93": (-0.93, 0.0, 0.83), "Dachs Kopf x=-0.93": (-0.93, 1.01, 0.83),
    "Leuchtturm Fuß": (10.2, 2.8, -25.6), "Leuchtturm Lampe": (10.2, 12.58, -25.6), "Leuchtturm Spitze": (10.2, 14.4, -25.6),
    "Laterne": (4.1, 1.79, -0.12), "Laternenpfahl Fuß": (4.6, 0.0, -0.12), "Laternenpfahl Spitze": (4.6, 2.51, -0.12),
    "Boot A links": (-2.34, 0.0, -6.1), "Boot A rechts": (2.76, 0.0, -6.1), "Boot A Dach": (0.6, 1.7, -6.1),
    "Boot B Mast": (6.75, 2.06, -6.4), "Boot B links": (4.34, -0.4, -6.4),
    "Häuschen rechts vorn": (-6.35, 0.0, 0.93), "Häuschen Traufe rechts": (-6.35, 2.45, 0.93), "Schornstein": (-9.58, 4.9, -1.35),
    "Fässer": (-4.55, 0.9, -0.62), "Kisten": (6.55, 1.2, 0.2), "Taurolle": (1.05, 0.07, 0.2),
    "Kaikante x=0": (0.0, 0.0, -1.0), "Horizont (Prospekt z=-60, y=-0.8)": (0.0, -0.8, -60.0),
}


def basis(rot_deg):
    rx, ry, rz = (math.radians(v) for v in rot_deg)
    def Rx(a): return np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    def Ry(a): return np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]])
    def Rz(a): return np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
    return Ry(ry) @ Rx(rx) @ Rz(rz)   # Godot: YXZ-Reihenfolge (erst Z, dann X, dann Y)


def project(p, pos, rot, fov):
    B = basis(rot)
    v = B.T @ (np.array(p, float) - np.array(pos, float))   # Kameraraum, Blick entlang -Z
    if v[2] >= -0.01:
        return None
    f = (H / 2) / math.tan(math.radians(fov) / 2)
    return (W / 2 + f * v[0] / -v[2], H / 2 - f * v[1] / -v[2], -v[2])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pos", type=float, nargs=3, required=True)
    ap.add_argument("--rot", type=float, nargs=3, default=[0, 0, 0], help="rotation_degrees x y z")
    ap.add_argument("--fov", type=float, default=42.0)
    a = ap.parse_args()
    for name, p in POINTS.items():
        r = project(p, a.pos, a.rot, a.fov)
        if r is None:
            print(f"{name:34s} hinter der Kamera")
            continue
        inside = 0 <= r[0] <= W and 0 <= r[1] <= H
        print(f"{name:34s} x={r[0]:7.1f} y={r[1]:7.1f} d={r[2]:5.1f} m {'' if inside else '--'}")
    # Dachsgröße an x=-2 und x=0
    for x in (-2.75, -2.0, -0.93):
        a1 = project((x, 0, 0.95), a.pos, a.rot, a.fov); a2 = project((x, 1.01, 0.95), a.pos, a.rot, a.fov)
        if a1 and a2:
            print(f"Dachshöhe bei x={x:4.1f}: {a1[1] - a2[1]:.0f} px")


if __name__ == "__main__":
    main()
