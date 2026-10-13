#!/usr/bin/env python3
"""Bildausschnitte der Diorama-Demo vorab rechnen (ohne Godot).

Projektion wie Godot: Camera3D.look_at_from_position(pos, target, Vector3.UP), vertikaler Bildwinkel
(Keep Height), 1280×720. Gibt für jede Einstellung die Bildkoordinaten wichtiger Punkte aus
(Sockelecken, Leuchtfeuer, Häuschen, Dachs am Start- und Endpunkt) und die Höhe des Dachses in Pixeln.

    .venv/bin/python styles/diorama-tiltshift/scripts/frame_shots.py
"""
import math

import numpy as np

W, H = 1280, 720
SHOTS = {
    # Name: (Position, Ziel, fov)
    "wide": ((-24.0, 36.0, 40.0), (0.8, -1.0, -12.0), 32.0),
    "close": ((-1.2, 3.9, 7.4), (-3.55, 0.45, 1.15), 34.0),
}
POINTS = {
    "Sockel vorn links": (-12.85, -3.5, 3.85),
    "Sockel vorn rechts": (14.85, -3.5, 3.85),
    "Sockel hinten links": (-12.85, -3.5, -30.85),
    "Sockel hinten rechts": (14.85, -3.5, -30.85),
    "Leuchtfeuer": (10.2, 12.58, -25.6),
    "Leuchtturmspitze": (10.2, 14.4, -25.6),
    "Hügel links oben": (-12.5, 3.8, -6.0),
    "Schornstein": (-9.58, 4.9, -1.35),
    "Häuschen Ecke vorn links": (-10.45, 0.0, 0.93),
    "Laterne": (4.1, 1.79, -0.12),
    "Boot A": (0.05, -0.8, -6.1),
    "Kai vorn Mitte": (0.0, 0.0, 3.5),
    "Schild": (1.0, -3.05, 3.9),
    "Dachs Start Fuß": (-6.0, 0.0, 1.2),
    "Dachs Start Kopf": (-6.0, 1.0, 1.2),
    "Dachs Ende Fuß": (-4.08, 0.0, 1.85),
    "Dachs Ende Kopf": (-4.08, 1.0, 1.85),
}


def basis(pos, target):
    f = np.array(target, float) - np.array(pos, float)
    f /= np.linalg.norm(f)
    z = -f
    x = np.cross([0.0, 1.0, 0.0], z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.stack([x, y, z])


def project(pos, target, fov, p):
    R = basis(pos, target)
    v = R @ (np.array(p, float) - np.array(pos, float))
    if v[2] >= 0:
        return None
    t = math.tan(math.radians(fov) / 2)
    xn = v[0] / -v[2] / (t * W / H)
    yn = v[1] / -v[2] / t
    return ((xn + 1) / 2 * W, (1 - yn) / 2 * H, -v[2])


import sys
if len(sys.argv) > 1:      # eigene Einstellung: px,py,pz,tx,ty,tz,fov
    v = [float(x) for x in sys.argv[1].split(",")]
    SHOTS = {"arg": (tuple(v[0:3]), tuple(v[3:6]), v[6])}
for name, (pos, target, fov) in SHOTS.items():
    d = np.array(target) - np.array(pos)
    pitch = math.degrees(math.atan2(d[1], math.hypot(d[0], d[2])))
    yaw = math.degrees(math.atan2(-d[0], -d[2]))
    print(f"== {name}: pos {pos} target {target} fov {fov}  Neigung {pitch:.1f}°, Gier {yaw:.1f}°, "
          f"Abstand {np.linalg.norm(d):.2f} m")
    for pn, p in POINTS.items():
        r = project(pos, target, fov, p)
        if r is None:
            print(f"   {pn:26s} hinter der Kamera")
        else:
            flag = "" if 0 <= r[0] <= W and 0 <= r[1] <= H else "  (außerhalb)"
            print(f"   {pn:26s} x {r[0]:7.1f}  y {r[1]:7.1f}  Tiefe {r[2]:6.2f}{flag}")
    for tag in ("Start", "Ende"):
        a = project(pos, target, fov, POINTS[f"Dachs {tag} Fuß"])
        b = project(pos, target, fov, POINTS[f"Dachs {tag} Kopf"])
        if a and b:
            print(f"   Dachs {tag}: {a[1] - b[1]:.0f} px hoch")


def aim(pos, fov, point, want_xy, iters=30):
    """Ziel so suchen, dass point bei want_xy (Pixel) liegt (für feste Kameraposition und fov)."""
    tgt = np.array(point, float)
    for _ in range(iters):
        r = project(pos, tgt, fov, point)
        ex, ey = r[0] - want_xy[0], r[1] - want_xy[1]
        R = basis(pos, tgt)
        dist = np.linalg.norm(tgt - np.array(pos))
        k = dist * 2 * math.tan(math.radians(fov) / 2) / H
        tgt = tgt + R[0] * ex * k - R[1] * ey * k
    return tuple(round(float(x), 3) for x in tgt)
