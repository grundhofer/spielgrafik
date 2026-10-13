#!/usr/bin/env python3
"""Bildausschnitt der Nahaufnahme vorab rechnen (ohne Godot): projiziert wichtige Punkte der Szene mit
einer Godot-Kamera (looking_at, fov vertikal = Keep Height, 1280×720) und gibt Pixelkoordinaten aus.
Auch die Himmelsrichtungen (Azimut, Höhe) von Bildpunkten, damit Wolken, Mond und Möwen im
Himmels-Shader an die richtige Stelle kommen.

    python3 styles/moebius-linien/scripts/frame_shot.py [--pos x,y,z --target x,y,z --fov 42]
"""
import argparse, math

W, H = 1280, 720
# Endpunkt des Dachses aus einem Lauf mit --measure (pos, rot -55°)
BADGER = (-3.037, 0.0, 1.377)
POINTS = {
    "Dachs Füße": BADGER,
    "Dachs Kopf": (BADGER[0], 1.011, BADGER[2]),
    "Leuchtturm Spitze": (10.2, 14.4, -25.6),
    "Leuchtfeuer": (10.2, 12.58, -25.6),
    "Leuchtturm Fuß": (10.2, 2.8, -25.6),
    "Boot A Ruderhaus": (0.05, 0.5, -6.1),
    "Boot A Wasserlinie": (0.05, -0.8, -6.1),
    "Boot B Mastspitze": (6.75, 2.2, -6.4),
    "Laterne": (4.1, 1.79, -0.12),
    "Kisten": (6.55, 0.6, 0.2),
    "Häuschen Ecke vorn rechts": (-6.6, 2.45, 0.5),
    "Schornstein": (-9.58, 4.9, -1.35),
    "Steg Ende": (3.45, 0.0, -8.6),
    "Kaikante (x=0)": (0.0, 0.0, -1.0),
}


def sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def norm(a):
    l = math.sqrt(sum(x * x for x in a))
    return [x / l for x in a]


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def basis(pos, target):
    f = norm(sub(target, pos))            # Blickrichtung (-Z der Kamera)
    r = norm(cross(f, [0.0, 1.0, 0.0]))   # +X
    u = cross(r, f)                       # +Y
    return f, r, u


def project(p, pos, target, fov):
    f, r, u = basis(pos, target)
    d = sub(p, pos)
    z = dot(d, f)
    if z <= 0:
        return None
    t = math.tan(math.radians(fov) / 2.0)
    x = dot(d, r) / (z * t * W / H)
    y = dot(d, u) / (z * t)
    return (W / 2 * (1 + x), H / 2 * (1 - y), z)


def sky_dir(px, py, pos, target, fov):
    f, r, u = basis(pos, target)
    t = math.tan(math.radians(fov) / 2.0)
    x = (px / (W / 2) - 1) * t * W / H
    y = (1 - py / (H / 2)) * t
    d = norm([f[i] + r[i] * x + u[i] * y for i in range(3)])
    el = math.degrees(math.asin(d[1]))
    az = math.degrees(math.atan2(d[0], -d[2]))
    return az * math.cos(math.radians(el)), el, az


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pos", default="-2.2,0.62,5.0")
    ap.add_argument("--target", default="-1.4,1.3,-6.0")
    ap.add_argument("--fov", type=float, default=42.0)
    ap.add_argument("--main", action="store_true", help="Hauptkamera aus shared/3d")
    a = ap.parse_args()
    pos = [float(v) for v in a.pos.split(",")]
    target = [float(v) for v in a.target.split(",")]
    if a.main:
        pos = [-1.8, 3.4, 14.5]
        target = [-1.8, 3.4 - math.sin(math.radians(3)), 14.5 - math.cos(math.radians(3))]
    for name, p in POINTS.items():
        s = project(p, pos, target, a.fov)
        print(f"{name:28s}" + (" hinter der Kamera" if s is None else f" x {s[0]:7.1f}  y {s[1]:6.1f}  z {s[2]:5.1f} m"))
    fe = project(POINTS["Dachs Füße"], pos, target, a.fov)
    he = project(POINTS["Dachs Kopf"], pos, target, a.fov)
    if fe and he:
        print(f"Dachs {fe[1] - he[1]:.0f} px hoch")
    # Horizont: Richtung waagerecht nach vorn
    f, _, _ = basis(pos, target)
    hz = project([pos[0] + 1000 * f[0], pos[1], pos[2] + 1000 * f[2]], pos, target, a.fov)
    print(f"Horizont y {hz[1]:.0f} (Himmel {100 * hz[1] / H:.0f} % des Bildes)")
    print("Himmelskoordinaten (x = Azimut·cos(Höhe), Höhe) der Bildecken und -mitten:")
    for py in (0, 180, 360):
        row = []
        for px in (0, 320, 640, 960, 1280):
            x, el, _ = sky_dir(px, py, pos, target, a.fov)
            row.append(f"({x:6.1f},{el:5.1f})")
        print(f"  y {py:3d}: " + " ".join(row))


if __name__ == "__main__":
    main()
