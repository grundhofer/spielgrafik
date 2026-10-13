#!/usr/bin/env python3
"""Bildausschnitt rechnen, bevor Godot läuft: projiziert wichtige Punkte des Hafens (shared/3d) und des
Dachses für eine Kamera wie in demo/main.gd (rotation_degrees YXZ, fov vertikal, Keep Height, 1280×720).

    .venv/bin/python styles/neon-synthwave/scripts/plan_shot.py --pos -0.3 1.0 6.9 --rot -0.5 0 --fov 44 --badger 0.4
"""
import argparse
import math

W, H = 1280, 720

POINTS = {
    "Leuchtfeuer": (10.2, 12.58, -25.6),
    "Leuchtturm-Spitze": (10.2, 14.4, -25.6),
    "Leuchtturm-Fuss": (10.2, 2.8, -25.6),
    "Laterne": (4.1, 1.79, -0.12),
    "Laternenpfahl-Fuss": (4.6, 0.0, -0.12),
    "Fenster": (-9.2, 1.45, 0.52),
    "Haus-Ecke rechts vorn": (-6.6, 0.0, 0.5),
    "Schornstein": (-9.58, 4.9, -1.35),
    "Fass 1": (-5.25, 0.45, -0.15),
    "Kisten": (6.55, 0.3, 0.2),
    "Taurolle": (1.05, 0.1, 0.05),
    "Boot A": (0.05, -0.8, -6.1),
    "Boot B": (6.75, -0.8, -6.4),
    "Kaikante Mitte": (0.0, 0.1, -1.0),
}


def rot_matrix(pitch_deg, yaw_deg):
    # Godot YXZ: R = Ry(yaw) * Rx(pitch)
    p, y = math.radians(pitch_deg), math.radians(yaw_deg)
    ry = [[math.cos(y), 0, math.sin(y)], [0, 1, 0], [-math.sin(y), 0, math.cos(y)]]
    rx = [[1, 0, 0], [0, math.cos(p), -math.sin(p)], [0, math.sin(p), math.cos(p)]]
    return [[sum(ry[i][k] * rx[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def project(pt, pos, rot, fov):
    r = rot_matrix(*rot)
    d = [pt[i] - pos[i] for i in range(3)]
    v = [sum(r[k][i] * d[k] for k in range(3)) for i in range(3)]  # R^T d
    th = math.tan(math.radians(fov) / 2)
    if v[2] >= -1e-6:
        return None
    nx = v[0] / (-v[2] * th * W / H)
    ny = v[1] / (-v[2] * th)
    return (nx * 0.5 + 0.5) * W, (0.5 - ny * 0.5) * H, -v[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pos", type=float, nargs=3, required=True)
    ap.add_argument("--rot", type=float, nargs=2, default=(0.0, 0.0), help="pitch yaw in Grad")
    ap.add_argument("--fov", type=float, default=42.0)
    ap.add_argument("--badger", type=float, nargs="*", default=[], help="x-Lagen des Dachses auf z = 1.2")
    ap.add_argument("--bz", type=float, default=1.2, help="z des Laufwegs")
    ap.add_argument("--sun", type=float, nargs=2, default=None, help="Azimut Höhe der Sonne in rad")
    a = ap.parse_args()
    for name, pt in POINTS.items():
        p = project(pt, a.pos, a.rot, a.fov)
        print(f"{name:24s} " + ("hinter der Kamera" if p is None else f"x {p[0]:7.1f}  y {p[1]:6.1f}  d {p[2]:6.1f} m"))
    for bx in a.badger:
        feet = project((bx, 0.0, a.bz), a.pos, a.rot, a.fov)
        head = project((bx, 1.011, a.bz), a.pos, a.rot, a.fov)
        print(f"Dachs x={bx:5.2f}: Füße y {feet[1]:6.1f}, Kopf y {head[1]:6.1f}, Höhe {feet[1] - head[1]:5.1f} px, "
              f"Bild-x {feet[0]:6.1f}")
    hz = project((a.pos[0], a.pos[1], a.pos[2] - 1e5), a.pos, a.rot, a.fov)
    print(f"Horizont y {hz[1]:.1f}")
    if a.sun:
        az, el = a.sun
        d = (math.sin(az) * math.cos(el), math.sin(el), -math.cos(az) * math.cos(el))
        s = project(tuple(a.pos[i] + d[i] * 1e5 for i in range(3)), a.pos, a.rot, a.fov)
        print(f"Sonnenmitte x {s[0]:.1f} y {s[1]:.1f}")


if __name__ == "__main__":
    main()
