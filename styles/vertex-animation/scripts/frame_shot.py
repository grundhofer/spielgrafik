#!/usr/bin/env python3
"""Bildausschnitt der Demo-Kamera ausrechnen, ohne Godot zu starten.

    python3 styles/vertex-animation/scripts/frame_shot.py [--pos -0.5,2.3,8.0] [--pitch -4] [--yaw -10] [--fov 42]

Projektion wie Godot: Camera3D mit rotation (pitch, yaw, 0) in YXZ-Reihenfolge, fov vertikal (Keep Height),
1280×720. Ausgegeben wird die Bildlage der wichtigen Punkte (Positionen aus shared/3d/harbor_notes.md und den
Zusatzteilen dieses Eintrags, siehe demo/main.gd). Die Standardwerte sind die der Demo (main.tscn → Camera).
"""
import argparse, math

ap = argparse.ArgumentParser()
ap.add_argument("--pos", default="-1.8,3.4,10.5")
ap.add_argument("--pitch", type=float, default=-6.5)
ap.add_argument("--yaw", type=float, default=-12.0)
ap.add_argument("--fov", type=float, default=45.0)
a = ap.parse_args()
W, H = 1280, 720
cam = [float(v) for v in a.pos.split(",")]
f = (H / 2) / math.tan(math.radians(a.fov / 2))

POINTS = {
    "Leuchtturm Spitze": (10.2, 14.4, -25.6), "Leuchtfeuer": (10.2, 12.58, -25.6), "Leuchtturm Fuß": (10.2, 2.8, -25.6),
    "BoatA Bug (+x)": (2.65, -0.4, -6.1), "BoatA Heck": (-2.3, -0.4, -6.1), "BoatA Ruderhaus oben": (-0.2, 1.7, -6.1),
    "BoatB Bug": (8.79, -0.4, -6.4), "BoatB Heck": (4.45, -0.4, -6.4), "BoatB Mast oben": (6.14, 2.06, -6.28),
    "Steg Ende": (3.45, 0.0, -8.6), "Steg Anfang": (3.45, 0.0, -0.5),
    "Laterne": (4.10, 1.79, -0.12), "Kisten oben": (6.55, 1.2, 0.2), "Kisten Fuß rechts": (7.79, 0.0, 0.74),
    "Poller x=1": (1.0, 0.6, -0.7), "Poller x=-3": (-3.0, 0.6, -0.7), "Fass 2": (-4.55, 0.9, -0.62),
    "Häuschen Fenster": (-6.57, 1.45, -0.5), "Kaikante x=-3": (-3.0, 0.1, -1.0),
    "Fahnenmast Fuß": (-0.35, 0.0, -0.2), "Fahnenmast Spitze": (-0.35, 4.6, -0.2), "Fahne Ende": (1.1, 3.9, 0.15),
    "Netz links oben": (-6.0, 1.95, 0.7), "Netz rechts unten": (-4.2, 0.4, 0.7),
    "Treibfass 1": (-3.4, -0.8, -4.9), "Treibfass 2": (-3.0, -0.8, -11.0), "Boje": (5.4, -0.8, -13.0),
    "Möwen Mitte": (2.5, 8.2, -15.5),
    "Dachs Start Fuß": (-4.5, 0.0, 2.2), "Dachs Halt Fuß": (-2.4, 0.0, 2.2), "Dachs Halt Kopf": (-2.4, 1.01, 2.2),
}


def rot(v):
    p, y = math.radians(a.pitch), math.radians(a.yaw)
    x, yy, z = v
    x, z = x * math.cos(y) - z * math.sin(y), x * math.sin(y) + z * math.cos(y)
    yy, z = yy * math.cos(p) + z * math.sin(p), -yy * math.sin(p) + z * math.cos(p)
    return x, yy, z


def project(p):
    x, y, z = rot([p[i] - cam[i] for i in range(3)])
    if z >= -0.01:
        return None
    return W / 2 + f * x / -z, H / 2 - f * y / -z, -z


for k, p in POINTS.items():
    r = project(p)
    if r is None:
        print(f"{k:24s} hinter der Kamera")
        continue
    x, y, d = r
    flag = "" if 0 <= x <= W and 0 <= y <= H else "  AUSSERHALB"
    print(f"{k:24s} ({x:7.1f}, {y:6.1f})  {d:5.1f} m{flag}")
hb = project(POINTS["Dachs Halt Kopf"])[1] - project(POINTS["Dachs Halt Fuß"])[1]
print(f"Dachs am Halt: {abs(hb):.0f} px hoch")
# Horizont (Blickrichtung waagrecht in großer Entfernung)
print("Horizont y:", round(project((cam[0] - 1000 * math.sin(math.radians(a.yaw)), cam[1], cam[2] - 1000 * math.cos(math.radians(a.yaw))))[1], 1))
