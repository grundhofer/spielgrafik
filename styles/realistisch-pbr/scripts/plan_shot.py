#!/usr/bin/env python3
"""Bildausschnitte vorab rechnen (ohne Godot): projiziert wichtige Punkte der Szene für eine Kamera
(Godot look_at mit +Y oben, fov vertikal, Keep Height) auf 1280×720.

    .venv/bin/python styles/realistisch-pbr/scripts/plan_shot.py --pos=-3.2,1.35,4.6 --target=1.5,1.5,-6 --fov 50 --badger=-1.2,1.2
"""
import argparse
import math

import numpy as np

W, H = 1280, 720


def look_basis(pos, target):
    f = np.array(target, float) - np.array(pos, float)
    f /= np.linalg.norm(f)
    z = -f
    x = np.cross([0.0, 1.0, 0.0], z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.stack([x, y, z], axis=1)


def project(p, pos, basis, fov):
    v = basis.T @ (np.array(p, float) - np.array(pos, float))
    if v[2] >= 0:
        return None
    f = (H / 2) / math.tan(math.radians(fov) / 2)
    return (W / 2 + f * v[0] / -v[2], H / 2 - f * v[1] / -v[2])


def points(bx, bz):
    return {
        "Dachs Füße": (bx, 0.0, bz), "Dachs Kopf": (bx, 1.01, bz),
        "Leuchtfeuer": (10.2, 12.58, -25.6), "Leuchtturm Fuß": (10.2, 2.8, -25.6),
        "Laterne": (4.1, 1.79, -0.12), "Laternenpfahl Fuß": (4.6, 0.0, -0.12),
        "BoatA Bug": (2.35, -0.3, -6.1), "BoatA Heck": (-2.25, -0.3, -6.1), "BoatB": (6.75, -0.3, -6.4),
        "Kaikante x=-4": (-4.0, 0.0, -1.0), "Kaikante x=4": (4.0, 0.0, -1.0),
        "Steg Ende": (3.45, 0.0, -8.6), "Fenster Haus": (-9.2, 1.45, 0.52), "Haus Ecke rechts": (-6.6, 2.45, 0.5),
        "Rauch": (-9.58, 4.9, -1.35), "Fass 1": (-5.25, 0.45, -0.15), "Fass 2": (-4.55, 0.45, -0.62),
        "Kisten": (6.55, 0.5, 0.2), "Taurolle": (1.05, 0.1, 0.05), "Horizont (z=-900)": (0.0, -0.8, -900.0),
        "Sonne (-20°)": (-0.342 * 1000, 0.036 * 1000, -0.939 * 1000),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pos", default="-3.2,1.35,4.6")
    ap.add_argument("--target", default="1.5,1.5,-6")
    ap.add_argument("--fov", type=float, default=50.0)
    ap.add_argument("--badger", default="-1.2,1.2")
    a = ap.parse_args()
    pos = [float(v) for v in a.pos.split(",")]
    tgt = [float(v) for v in a.target.split(",")]
    bx, bz = [float(v) for v in a.badger.split(",")]
    B = look_basis(pos, tgt)
    d = math.dist(pos, (bx, 0.5, bz))
    print(f"Abstand Kamera–Dachs {d:.2f} m, Dachs ≈ {1.01 * (H / 2) / math.tan(math.radians(a.fov) / 2) / d:.0f} px")
    yaw = math.degrees(math.atan2(-(tgt[0] - pos[0]), -(tgt[2] - pos[2])))
    pitch = math.degrees(math.atan2(tgt[1] - pos[1], math.hypot(tgt[0] - pos[0], tgt[2] - pos[2])))
    print(f"Gieren {yaw:.1f}°, Neigen {pitch:.1f}°")
    for k, p in points(bx, bz).items():
        s = project(p, pos, B, a.fov)
        flag = "" if s and 0 <= s[0] < W and 0 <= s[1] < H else "  (außerhalb)"
        print(f"{k:18s} " + (f"{s[0]:7.0f} {s[1]:6.0f}" if s else "hinter der Kamera") + flag)


if __name__ == "__main__":
    main()
