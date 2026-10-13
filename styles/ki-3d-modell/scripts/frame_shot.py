#!/usr/bin/env python3
"""Bildausschnitt der festen Kamera vorab rechnen (ohne Godot): Projektion wie Godot (Euler YXZ, fov vertikal,
Keep Height, 1280×720). Gibt die Pixellage wichtiger Punkte aus und warnt, wenn ein Punkt unter dem
Drehteller-Fenster oder dem Dialogkasten (Werte aus demo/ui.gd) oder außerhalb des Bildes liegt.

    .venv/bin/python styles/ki-3d-modell/scripts/frame_shot.py            # Werte der Demo (demo/main.gd)
    .venv/bin/python styles/ki-3d-modell/scripts/frame_shot.py --cam=-0.2,1.0,5.6,-4,4,46 --heading=55
"""
import argparse, math

ap = argparse.ArgumentParser()
ap.add_argument("--cam", default="-0.5,0.95,6.0,1.5,-6,46", help="x,y,z,neigung,gieren,fov")
ap.add_argument("--stop", default="-0.55,2.65")
ap.add_argument("--heading", type=float, default=70)
ap.add_argument("--dist", type=float, default=2.5, help="Laufstrecke bis zum Halt (m): 0,734 m/s × 3,15 s + Bremsen")
ap.add_argument("--lantern", default="2.9,0.4")
ap.add_argument("--barrels", default="0.45,-0.2,1.1,-0.65")
a = ap.parse_args()
cx, cy, cz, pitch, yaw, fov = map(float, a.cam.split(","))
W, H = 1280, 720
PANEL = (18, 18, 348, 452)
BOX = (724, 566, 1262, 702)


def project(p):
    x, y, z = p[0] - cx, p[1] - cy, p[2] - cz
    ya, pi = math.radians(yaw), math.radians(pitch)
    # inverse Drehung: erst Gieren (Y), dann Neigen (X)
    x1 = x * math.cos(ya) - z * math.sin(ya)
    z1 = x * math.sin(ya) + z * math.cos(ya)
    y2 = y * math.cos(pi) + z1 * math.sin(pi)
    z2 = -y * math.sin(pi) + z1 * math.cos(pi)
    if z2 >= 0:
        return None
    f = (H / 2) / math.tan(math.radians(fov) / 2)
    return (W / 2 + f * x1 / -z2, H / 2 - f * y2 / -z2)


sx, sz = map(float, a.stop.split(","))
hd = math.radians(a.heading)
st = (sx - a.dist * math.cos(hd), sz - a.dist * math.sin(hd))
lx, lz = map(float, a.lantern.split(","))
b = list(map(float, a.barrels.split(",")))
pts = {
    "Dachs Start Fuß": (st[0], 0, st[1]), "Dachs Start Kopf": (st[0], 1.0, st[1]),
    "Dachs Halt Fuß": (sx, 0, sz), "Dachs Halt Kopf": (sx, 1.0, sz),
    "Fass A": (b[0], 0.9, b[1]), "Fass A Fuß": (b[0], 0, b[1]), "Fass B": (b[2], 0.9, b[3]),
    "Laterne Fuß": (lx, 0, lz), "Laterne oben": (lx, 2.45, lz),
    "Leuchtfeuer": (10.2, 12.58, -25.6), "Leuchtturm Fuß": (10.2, 2.8, -25.6),
    "BoatA (gedreht)": (0.05, 0.3, -6.1), "Boot (TSR, statt BoatB)": (6.75, 0.3, -6.4),
    "Schornstein": (-9.58, 4.9, -1.35), "Fenster": (-9.2, 1.45, 0.52), "Kisten": (6.55, 0.6, 0.2),
}
for k, p in pts.items():
    s = project(p)
    if s is None:
        print(f"{k:20s} hinter der Kamera")
        continue
    note = []
    if not (0 <= s[0] < W and 0 <= s[1] < H):
        note.append("außerhalb")
    for nm, r in (("Fenster", PANEL), ("Kasten", BOX)):
        if r[0] <= s[0] <= r[2] and r[1] <= s[1] <= r[3]:
            note.append("unter " + nm)
    print(f"{k:20s} {s[0]:7.1f} {s[1]:7.1f}  {' '.join(note)}")
hs = project((sx, 1.0, sz)); fs = project((sx, 0, sz))
print("Dachs am Halt etwa", round(fs[1] - hs[1]), "px hoch")
