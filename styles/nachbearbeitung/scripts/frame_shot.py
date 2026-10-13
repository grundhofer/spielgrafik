#!/usr/bin/env python3
"""Bildausschnitt der Demo-Kamera vorab ausrechnen (ohne Godot).

Projiziert wichtige Punkte des Hafens (Werte aus shared/3d/harbor_notes.md) für eine Kamera mit
Position, Blickziel und vertikalem fov (Godot: Keep Height, looking_at mit +Y oben) auf 1280×720.

    .venv/bin/python styles/nachbearbeitung/scripts/frame_shot.py --pos 0.2,1.5,7 --target 3.5,3,-20 --fov 40

Totale aus shared/3d (Neigung −3°) als Blickziel 30 m voraus: --pos=-1.8,3.4,14.5 --target=-1.8,1.8278,-15.5 --fov 42
"""
import argparse
import math

import numpy as np

W, H = 1280, 720


def look_basis(pos, target):
    f = np.array(target, float) - np.array(pos, float)
    f /= np.linalg.norm(f)
    z = -f                                   # Godot: Kamera blickt entlang -Z
    x = np.cross([0.0, 1.0, 0.0], z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.stack([x, y, z], axis=1)       # Spalten = Achsen


def project(p, pos, basis, fov):
    v = basis.T @ (np.array(p, float) - np.array(pos, float))
    if v[2] >= 0:
        return None
    f = (H / 2) / math.tan(math.radians(fov) / 2)
    return (W / 2 + f * v[0] / -v[2], H / 2 - f * v[1] / -v[2])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pos", default="0.2,1.5,7")
    ap.add_argument("--target", default="3.5,3,-20")
    ap.add_argument("--fov", type=float, default=40.0)
    ap.add_argument("--badger-x", default="-6,-1.8")
    a = ap.parse_args()
    pos = [float(v) for v in a.pos.split(",")]
    tgt = [float(v) for v in a.target.split(",")]
    B = look_basis(pos, tgt)
    pts = {
        "Leuchtfeuer": (10.2, 12.58, -25.6), "Leuchtturm Fuß": (10.2, 2.8, -25.6),
        "Leuchtturm Spitze": (10.2, 14.4, -25.6),
        "Laterne": (4.1, 1.79, -0.12), "Laternenpfahl Fuß": (4.6, 0.0, -0.12),
        "Laternenpfahl Kopf": (4.6, 2.45, -0.12),
        "BoatA Bug": (2.35, -0.3, -6.1), "BoatA Heck": (-2.25, -0.3, -6.1), "BoatB": (6.75, -0.3, -6.4),
        "Kaikante x=-4": (-4.0, 0.0, -1.0), "Kaikante x=4": (4.0, 0.0, -1.0),
        "Steg Ende": (3.45, 0.0, -8.6), "Fenster Haus": (-9.2, 1.45, 0.52), "Rauch": (-9.58, 4.9, -1.35),
        "Haus First": (-8.4, 3.8, -1.0),
        "Fass 1": (-5.25, 0.45, -0.15), "Fass 2": (-4.55, 0.45, -0.62), "Kisten": (6.55, 0.5, 0.2),
        "Taurolle": (1.05, 0.1, 0.05), "Horizont fern": (0.0, -0.8, -900.0),
    }
    for bx in [float(v) for v in a.badger_x.split(",")]:
        pts[f"Dachs Füße x={bx}"] = (bx, 0.0, 1.2)
        pts[f"Dachs Kopf x={bx}"] = (bx, 1.01, 1.2)
        d = math.dist(pos, (bx, 0.5, 1.2))
        print(f"Dachs bei x={bx}: Abstand {d:.2f} m, ≈ {1.01 * (H / 2) / math.tan(math.radians(a.fov) / 2) / d:.0f} px hoch")
    for k, p in pts.items():
        s = project(p, pos, B, a.fov)
        flag = "" if s and 0 <= s[0] < W and 0 <= s[1] < H else "  (außerhalb)"
        print(f"{k:22s} " + (f"{s[0]:7.0f} {s[1]:6.0f}" if s else "hinter der Kamera") + flag)
    fwd = -B[:, 2]
    yaw = math.degrees(math.atan2(-fwd[0], -fwd[2]))
    pitch = math.degrees(math.asin(fwd[1]))
    print(f"Gieren {yaw:.2f}°, Neigung {pitch:.2f}°")


if __name__ == "__main__":
    main()
