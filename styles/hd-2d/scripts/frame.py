#!/usr/bin/env python3
"""Bildausschnitt der HD-2D-Kamera vor dem Godot-Lauf ausrechnen (Muster: styles/ps1-lowpoly/scripts/frame_closeup.py).

Projektion wie Godot: Camera3D mit Euler YXZ (rotation_degrees = (pitch, yaw, 0)), fov vertikal, Keep Height,
1280×720. Gibt für Anfangs- und Endstellung der Kamerafahrt die Bildlage wichtiger Punkte aus und die
Figurenhöhe in Pixeln, außerdem die Größe eines Sprite-Pixels in Bildschirmpixeln.

    .venv/bin/python styles/hd-2d/scripts/frame.py [--pos x,y,z] [--pitch -16] [--fov 30] [--pan 3.0]
"""
import argparse
import math

import numpy as np

W, H = 1280, 720
POINTS = {
    "Dachs Fuß (Start)": (-5.6, 0.0, 1.2),
    "Dachs Kopf (Start)": (-5.6, 1.05, 1.2),
    "Dachs Fuß (Halt)": (-1.3, 0.0, 1.2),
    "Dachs Kopf (Halt)": (-1.3, 1.05, 1.2),
    "Häuschen First links": (-10.2, 3.8, -1.0),
    "Häuschen Ecke rechts unten": (-6.6, 0.0, 0.5),
    "Schornstein oben": (-9.58, 4.9, -1.35),
    "Fenster": (-9.2, 1.45, 0.52),
    "Fässer": (-4.9, 0.9, -0.4),
    "Taurolle": (1.05, 0.0, 0.05),
    "Laterne": (4.1, 1.79, -0.12),
    "Laternenpfahl Fuß": (4.6, 0.0, -0.12),
    "Kisten": (6.55, 1.2, 0.2),
    "Boot A": (0.05, -0.8, -6.1),
    "Boot B": (6.75, -0.8, -6.4),
    "Stegende": (3.45, 0.0, -8.6),
    "Leuchtturm Lampe": (10.2, 12.58, -25.6),
    "Leuchtturm Spitze": (10.2, 14.4, -25.6),
    "Leuchtturm Fuß": (10.2, 2.8, -25.6),
    "Kaivorderkante Mitte": (-1.0, 0.0, 8.0),
    "Horizont (900 m)": (0.0, -0.8, -900.0),
}


def basis(pitch, yaw):
    p, y = math.radians(pitch), math.radians(yaw)
    rx = np.array([[1, 0, 0], [0, math.cos(p), -math.sin(p)], [0, math.sin(p), math.cos(p)]])
    ry = np.array([[math.cos(y), 0, math.sin(y)], [0, 1, 0], [-math.sin(y), 0, math.cos(y)]])
    return ry @ rx      # YXZ: erst Y, dann X (Godot)


def project(pt, pos, pitch, yaw, fov):
    b = basis(pitch, yaw)
    v = b.T @ (np.array(pt, float) - np.array(pos, float))     # Kameraraum, Blick nach -Z
    if v[2] >= -0.01:
        return None
    f = (H / 2) / math.tan(math.radians(fov) / 2)
    return W / 2 + f * v[0] / -v[2], H / 2 - f * v[1] / -v[2], -v[2]


def report(pos, pitch, yaw, fov, label):
    print(f"--- {label}: pos={tuple(round(c, 3) for c in pos)} pitch={pitch} yaw={yaw} fov={fov}")
    for name, pt in POINTS.items():
        r = project(pt, pos, pitch, yaw, fov)
        if r is None:
            print(f"  {name:28s} hinter der Kamera")
            continue
        x, y, d = r
        flag = "" if 0 <= x <= W and 0 <= y <= H else "  (außerhalb)"
        print(f"  {name:28s} x={x:7.1f} y={y:7.1f} Tiefe={d:6.2f}{flag}")
    for k in ("Start", "Halt"):
        a = project(POINTS[f"Dachs Fuß ({k})"], pos, pitch, yaw, fov)
        b = project(POINTS[f"Dachs Kopf ({k})"], pos, pitch, yaw, fov)
        if a and b:
            print(f"  Dachs {k}: {a[1] - b[1]:.1f} px hoch (1,05 m), Tiefe {a[2]:.2f} m")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pos", default="-3.6,5.2,13.0")
    ap.add_argument("--pitch", type=float, default=-16.0)
    ap.add_argument("--yaw", type=float, default=0.0)
    ap.add_argument("--fov", type=float, default=30.0)
    ap.add_argument("--pan", type=float, default=3.0, help="Fahrt in x (m)")
    ap.add_argument("--yaw-end", type=float, default=None)
    ap.add_argument("--sprite-px-m", type=float, default=44.0, help="Sprite-Pixel je Meter")
    a = ap.parse_args()
    pos = [float(c) for c in a.pos.split(",")]
    report(pos, a.pitch, a.yaw, a.fov, "Anfang")
    end = [pos[0] + a.pan, pos[1], pos[2]]
    report(end, a.pitch, a.yaw if a.yaw_end is None else a.yaw_end, a.fov, "Ende")
    # Sprite-Pixel in Bildschirmpixeln an der Tiefe des Laufwegs
    d = project(POINTS["Dachs Fuß (Halt)"], pos, a.pitch, a.yaw, a.fov)[2]
    f = (H / 2) / math.tan(math.radians(a.fov) / 2)
    print(f"Ein Sprite-Pixel ({1 / a.sprite_px_m * 100:.2f} cm) auf Tiefe {d:.2f} m = {f / d / a.sprite_px_m:.2f} px")


if __name__ == "__main__":
    main()
