#!/usr/bin/env python3
"""Bildausschnitt der Nahaufnahme vorab ausrechnen (ohne Godot).

Projiziert wichtige Punkte der Szene für eine Kamera mit Position, Blickziel und vertikalem fov
(Godot: Keep Height, looking_at mit +Y oben) auf 1280×720 und gibt die Pixel aus.

    .venv/bin/python styles/toon-cel/scripts/frame_close.py --pos 0,1.2,5 --target -1,1.3,-3 --fov 40 --badger-x -2.6
"""
import argparse, math
import numpy as np

W, H = 1280, 720


def look_basis(pos, target):
    f = np.array(target, float) - np.array(pos, float)
    f /= np.linalg.norm(f)
    z = -f                                  # Godot: Kamera blickt entlang -Z
    x = np.cross([0.0, 1.0, 0.0], z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.stack([x, y, z], axis=1)      # Spalten = Achsen


def project(p, pos, basis, fov):
    v = basis.T @ (np.array(p, float) - np.array(pos, float))
    if v[2] >= 0:
        return None
    f = (H / 2) / math.tan(math.radians(fov) / 2)
    return (W / 2 + f * v[0] / -v[2], H / 2 - f * v[1] / -v[2])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pos", default="0,1.2,5")
    ap.add_argument("--target", default="-1,1.3,-3")
    ap.add_argument("--fov", type=float, default=40.0)
    ap.add_argument("--badger-x", type=float, default=-2.6)
    a = ap.parse_args()
    pos = [float(v) for v in a.pos.split(",")]
    tgt = [float(v) for v in a.target.split(",")]
    B = look_basis(pos, tgt)
    bx = a.badger_x
    pts = {
        "Dachs Füße": (bx, 0.0, 1.2), "Dachs Kopf": (bx, 1.01, 1.2),
        "Leuchtfeuer": (10.2, 12.58, -25.6), "Leuchtturm Fuß": (10.2, 2.8, -25.6),
        "Leuchtturm Spitze": (10.2, 14.4, -25.6),
        "Laterne": (4.1, 1.79, -0.12), "Laternenpfahl Fuß": (4.6, 0.0, -0.12),
        "BoatA Bug": (2.35, -0.3, -6.1), "BoatA Heck": (-2.25, -0.3, -6.1), "BoatB": (6.75, -0.3, -6.4),
        "Kaikante x=-4": (-4.0, 0.0, -1.0), "Kaikante x=4": (4.0, 0.0, -1.0),
        "Steg Ende": (3.45, 0.0, -8.6), "Fenster Haus": (-9.2, 1.45, 0.52), "Rauch": (-9.58, 4.9, -1.35),
        "Fass 1": (-5.25, 0.45, -0.15), "Kisten": (6.55, 0.5, 0.2), "Taurolle": (1.05, 0.1, 0.05),
    }
    d = math.dist(pos, (bx, 0.5, 1.2))
    print(f"Abstand Kamera–Dachs {d:.2f} m, Dachs ≈ {1.01 * (H / 2) / math.tan(math.radians(a.fov) / 2) / d:.0f} px")
    for k, p in pts.items():
        s = project(p, pos, B, a.fov)
        flag = "" if s and 0 <= s[0] < W and 0 <= s[1] < H else "  (außerhalb)"
        print(f"{k:18s} " + (f"{s[0]:7.0f} {s[1]:6.0f}" if s else "hinter der Kamera") + flag)
    fwd = -B[:, 2]
    yaw = math.degrees(math.atan2(-fwd[0], -fwd[2]))
    pitch = math.degrees(math.asin(fwd[1]))
    to_cam = np.array(pos) - np.array([bx, 0, 1.2])
    turn = math.degrees(math.atan2(-to_cam[2], to_cam[0]))
    print(f"Gieren {yaw:.1f}°, Neigung {pitch:.1f}°, Drehung des Dachses zur Kamera {turn:.0f}°")


if __name__ == "__main__":
    main()
