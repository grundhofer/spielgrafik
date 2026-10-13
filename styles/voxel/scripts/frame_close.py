#!/usr/bin/env python3
"""Bildausschnitt der Nahaufnahme vorab ausrechnen (ohne Godot); Projektion wie in Godot (Keep Height,
looking_at mit +Y oben) auf 1280x720. Aufbau nach styles/toon-cel/scripts/frame_close.py.

    .venv/bin/python styles/voxel/scripts/frame_close.py --pos -1.4,2.3,6.0 --target 0.8,0.2,-4 --fov 44
"""
import argparse, math
import numpy as np

W, H = 1280, 720
BADGER = (-2.933, 0.0, 1.595)         # Endpunkt des Laufs (gemessen mit --measure)
FACING = -74.0                        # rotation.y am Ende (TURN_DEG in main.gd)


def look_basis(pos, target):
    f = np.array(target, float) - np.array(pos, float)
    f /= np.linalg.norm(f)
    z = -f
    x = np.cross([0.0, 1.0, 0.0], z); x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.stack([x, y, z], axis=1)


def project(p, pos, basis, fov):
    v = basis.T @ (np.array(p, float) - np.array(pos, float))
    if v[2] >= 0:
        return None
    f = (H / 2) / math.tan(math.radians(fov) / 2)
    return (W / 2 + f * v[0] / -v[2], H / 2 - f * v[1] / -v[2])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pos", default="-1.4,2.3,6.0")
    ap.add_argument("--target", default="0.8,0.2,-4")
    ap.add_argument("--fov", type=float, default=44.0)
    a = ap.parse_args()
    pos = [float(v) for v in a.pos.split(",")]
    tgt = [float(v) for v in a.target.split(",")]
    B = look_basis(pos, tgt)
    bx, by, bz = BADGER
    pts = {
        "Dachs Füße": (bx, 0.0, bz), "Dachs Kopf": (bx, 1.01, bz),
        "Leuchtfeuer": (10.2, 12.58, -25.6), "Leuchtturm Fuß": (10.2, 2.8, -25.6),
        "Leuchtturm Spitze": (10.2, 14.4, -25.6),
        "Laterne": (4.1, 1.79, -0.12), "Laternenpfahl Fuß": (4.6, 0.0, -0.12),
        "BoatA Bug": (2.35, -0.3, -6.1), "BoatA Heck": (-2.25, -0.3, -6.1), "BoatA Haus": (0.0, 1.3, -6.1),
        "BoatB": (6.75, -0.3, -6.4), "Kaikante x=-4": (-4.0, 0.0, -1.0), "Kaikante x=4": (4.0, 0.0, -1.0),
        "Steg Ende": (3.45, 0.0, -8.6), "Fenster Haus": (-9.2, 1.45, 0.52), "Rauch": (-9.58, 4.9, -1.35),
        "Fass 1": (-5.25, 0.9, -0.15), "Fass 2": (-4.55, 0.9, -0.62), "Kisten": (6.55, 0.5, 0.2),
        "Taurolle": (1.05, 0.1, 0.05), "Horizont (z=-900)": (0.0, -0.8, -900.0),
    }
    d = math.dist(pos, (bx, 0.5, bz))
    print(f"Abstand Kamera-Dachs {d:.2f} m")
    for k, p in pts.items():
        s = project(p, pos, B, a.fov)
        flag = "" if s and 0 <= s[0] < W and 0 <= s[1] < H else "  (außerhalb)"
        print(f"{k:18s} " + (f"{s[0]:7.0f} {s[1]:6.0f}" if s else "hinter der Kamera") + flag)
    fwd = -B[:, 2]
    print(f"Gieren {math.degrees(math.atan2(-fwd[0], -fwd[2])):.1f}°, Neigung {math.degrees(math.asin(fwd[1])):.1f}°")
    to_cam = np.array(pos) - np.array(BADGER)
    print(f"Blickrichtung des Dachses zur Kamera: rotation.y {math.degrees(math.atan2(-to_cam[2], to_cam[0])):.0f}° (gesetzt {FACING:.0f}°)")


if __name__ == "__main__":
    main()
