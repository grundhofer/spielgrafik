#!/usr/bin/env python3
"""Bildausschnitt der festen Kamera vorab ausrechnen (ohne Godot).

Projiziert wichtige Punkte der Hafenszene für eine Kamera mit Position, Blickziel und vertikalem fov
(Godot: Keep Height, looking_at mit +Y oben) auf 1280×720 und gibt die Pixel aus. Nach dem Vorbild
von styles/toon-cel/scripts/frame_close.py, um Punkte für diesen Eintrag erweitert.

    .venv/bin/python styles/gemaltes-3d/scripts/plan_shot.py --pos -2.4,1.55,6.6 --target 1.2,2.3,-8 --fov 44 \
        --badger -1.6,1.6
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


POINTS = {
    "Leuchtfeuer": (10.2, 12.58, -25.6), "Leuchtturm Fuß": (10.2, 2.8, -25.6),
    "Leuchtturm Spitze": (10.2, 14.4, -25.6),
    "Laterne": (4.1, 1.79, -0.12), "Laternenpfahl Fuß": (4.6, 0.0, -0.12), "Laternenpfahl Kopf": (4.6, 2.45, -0.12),
    "BoatA Bug": (2.35, -0.3, -6.1), "BoatA Heck": (-2.25, -0.3, -6.1), "BoatA Ruderhaus": (0.05, 0.5, -6.1),
    "BoatB Mitte": (6.75, -0.3, -6.4), "BoatB Mast": (6.75, 2.2, -6.4),
    "Kaikante x=-6": (-6.0, 0.0, -1.0), "Kaikante x=0": (0.0, 0.0, -1.0), "Kaikante x=6": (6.0, 0.0, -1.0),
    "Steg Anfang": (3.45, 0.0, -1.0), "Steg Ende": (3.45, 0.0, -8.6),
    "Haus Ecke rechts vorn": (-6.6, 0.0, 0.5), "Haus Ecke rechts Traufe": (-6.6, 2.45, 0.5),
    "Haus First": (-8.4, 3.8, -1.0), "Fenster Haus": (-9.2, 1.45, 0.52), "Rauch": (-9.58, 4.9, -1.35),
    "Rauch +2 m": (-8.6, 6.9, -1.35),
    "Fass 1": (-5.25, 0.45, -0.15), "Fass 2": (-4.55, 0.45, -0.62), "Kisten": (6.55, 0.5, 0.2),
    "Taurolle": (1.05, 0.1, 0.05), "Horizont (Mitte)": (0.0, -0.8, -900.0),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pos", default="-2.4,1.55,6.6")
    ap.add_argument("--target", default="1.2,2.3,-8")
    ap.add_argument("--fov", type=float, default=44.0)
    ap.add_argument("--badger", default="-1.6,1.6", help="Haltepunkt x,z")
    ap.add_argument("--start", default="-6.0,1.6", help="Startpunkt x,z")
    a = ap.parse_args()
    pos = [float(v) for v in a.pos.split(",")]
    tgt = [float(v) for v in a.target.split(",")]
    bx, bz = (float(v) for v in a.badger.split(","))
    sx, sz = (float(v) for v in a.start.split(","))
    B = look_basis(pos, tgt)
    pts = dict(POINTS)
    pts["Dachs Füße"] = (bx, 0.0, bz)
    pts["Dachs Kopf"] = (bx, 1.01, bz)
    pts["Start Füße"] = (sx, 0.0, sz)
    pts["Start Kopf"] = (sx, 1.01, sz)
    for k, p in pts.items():
        s = project(p, pos, B, a.fov)
        flag = "" if s and 0 <= s[0] < W and 0 <= s[1] < H else "  (außerhalb)"
        print(f"{k:24s} " + (f"{s[0]:7.0f} {s[1]:6.0f}" if s else "hinter der Kamera") + flag)
    f0 = project(pts["Dachs Füße"], pos, B, a.fov)
    h0 = project(pts["Dachs Kopf"], pos, B, a.fov)
    print(f"Dachs am Haltepunkt {f0[1] - h0[1]:.0f} px hoch")
    fwd = -B[:, 2]
    yaw = math.degrees(math.atan2(-fwd[0], -fwd[2]))
    pitch = math.degrees(math.asin(fwd[1]))
    to_cam = np.array(pos) - np.array([bx, 0, bz])
    turn = math.degrees(math.atan2(-to_cam[2], to_cam[0]))
    print(f"Gieren {yaw:.1f}°, Neigung {pitch:.1f}°, Drehung des Dachses zur Kamera {turn:.0f}° "
          f"(rotation.y; 0 = nach +X)")


if __name__ == "__main__":
    main()
