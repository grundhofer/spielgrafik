#!/usr/bin/env python3
"""Laufweg und Bildausschnitt der festen Kamera berechnen, ohne Godot zu starten.

    .venv/bin/python styles/blender-rig/scripts/frame_shot.py                 # Werte der Demo
    .venv/bin/python styles/blender-rig/scripts/frame_shot.py --cam-abs "" --dist 3.4 --angle 8 --height 0.9

1. Laufweg wie in demo/main.gd simulieren (Tempo 0,734 m/s, Abbiegen von HEADING0 auf HEADING_END
   gleichmäßig zwischen CURVE_T0 und CURVE_T1, Bremsen und Überblenden). Ergebnis: Endpunkt des Dachses.
2. Kamera fest (--cam-abs, Standard = Demo) oder `dist` m vom Endpunkt, `angle` Grad von +Z aus gedreht (positiv = rechts vom Dachs), `height` m
   über dem Kai. Neigung und Gieren so lösen, dass die Füße am Endpunkt auf Pixel `feet` (1280×720) liegen.
   Projektion wie Godot: Basis.from_euler(pitch, yaw, 0) (YXZ), fov vertikal (Keep Height).
Ausgabe: Werte für main.gd (CAM_POS, CAM_ROT_DEG, CAM_FOV), Dachshöhe in px, Bildlage wichtiger Punkte aus
shared/3d/harbor_notes.md und des Laufwegs (Start, Bildeintritt, Ende); Warnung, wenn ein Punkt unter
dem Dialogkasten oder dem AnimationTree-Fenster liegt.
"""
import argparse
import math

ap = argparse.ArgumentParser()
ap.add_argument("--fov", type=float, default=52.0)
ap.add_argument("--angle", type=float, default=8.0)
ap.add_argument("--dist", type=float, default=4.4)
ap.add_argument("--height", type=float, default=1.1)
ap.add_argument("--feet", default="520,600")
ap.add_argument("--start-x", type=float, default=-3.5)
ap.add_argument("--start-z", type=float, default=0.8)
ap.add_argument("--heading0", type=float, default=0.0)
ap.add_argument("--heading-end", type=float, default=80.0)
ap.add_argument("--curve", default="1.5,3.1")
ap.add_argument("--brake", default="3.15,0.5")
ap.add_argument("--blend", default="3.35,3.77")
ap.add_argument("--cam-abs", default="-1.2,1.25,4.6,-3,-14",
                help="x,y,z,neigung,gieren: feste Kamera (Demo); leer = aus dist/angle/height/feet lösen")
a = ap.parse_args()

W, H = 1280, 720
BZ = 1.2
PANEL = (24, 22, 510, 222)       # ui.gd: AnimationTree-Fenster (x0, y0, x1, y1)
BOX = (612, 552, 1256, 698)      # ui.gd: Dialogkasten
POINTS = {
    "Leuchtfeuer": (10.2, 12.58, -25.6), "Leuchtturm Fuß": (10.2, 2.8, -25.6),
    "Laterne (Glas)": (4.10, 1.79, -0.12), "Laternenpfahl Fuß": (4.60, 0.0, -0.12),
    "BoatA Ruderhaus": (0.05, 0.6, -6.1), "BoatB Mast": (6.75, 2.2, -6.4), "Kisten": (6.55, 0.6, 0.2),
    "Taurolle": (1.05, 0.1, 0.05), "Fass 1": (-5.25, 0.9, -0.15), "Fass 2": (-4.55, 0.9, -0.62),
    "Schornstein": (-9.58, 4.9, -1.35), "Fenster": (-9.2, 1.45, 0.52),
}


def smoothstep(e0, e1, x):
    u = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return u * u * (3 - 2 * u)


# --- 1. Laufweg ------------------------------------------------------------------------------
c0, c1 = map(float, a.curve.split(","))
b0, bd = map(float, a.brake.split(","))
l0, l1 = map(float, a.blend.split(","))
x, z, hd = a.start_x, a.start_z, a.heading0
path = [(0.0, x, z, hd)]
dt = 1 / 30
for i in range(1, 181):
    t = i * dt
    rate = 2.0 * (1 - smoothstep(b0, b0 + bd, t))
    w = 1 - smoothstep(l0, l1, t)
    v = 0.367 * rate * w
    x += math.cos(math.radians(hd)) * v * dt
    z += math.sin(math.radians(hd)) * v * dt
    hd = a.heading0 + (a.heading_end - a.heading0) * min(max((t - c0) / (c1 - c0), 0.0), 1.0)   # gleichmäßig
    path.append((t, x, z, hd))
ex, ez = path[-1][1], path[-1][2]
print(f"Endpunkt Dachs: x = {ex:.3f}, z = {ez:.3f}, Blick {path[-1][3]:.1f}° zur Kamera hin")

# --- 2. Kamera -------------------------------------------------------------------------------
feet = tuple(map(float, a.feet.split(",")))
f = (H / 2) / math.tan(math.radians(a.fov / 2))
cam = (ex + a.dist * math.sin(math.radians(a.angle)), a.height, ez + a.dist * math.cos(math.radians(a.angle)))
pitch = yaw = 0.0


def to_cam(v):
    p, y = math.radians(pitch), math.radians(yaw)
    x_, yy, z_ = v
    x_, z_ = x_ * math.cos(y) - z_ * math.sin(y), x_ * math.sin(y) + z_ * math.cos(y)
    yy, z_ = yy * math.cos(p) + z_ * math.sin(p), -yy * math.sin(p) + z_ * math.cos(p)
    return x_, yy, z_


def project(p):
    x_, y_, z_ = to_cam([p[i] - cam[i] for i in range(3)])
    if z_ >= -0.01:
        return None
    return W / 2 + f * x_ / -z_, H / 2 - f * y_ / -z_


if a.cam_abs:
    c = [float(v) for v in a.cam_abs.split(",")]
    cam, pitch, yaw = tuple(c[:3]), c[3], c[4]
else:
    for _ in range(100):
        fx, fy = project((ex, 0, ez))
        yaw -= math.degrees(math.atan((fx - feet[0]) / f)) * 0.8
        pitch -= math.degrees(math.atan((fy - feet[1]) / f)) * 0.8

head = project((ex, 1.011, ez))
foot = project((ex, 0, ez))
print(f"CAM_POS = Vector3({cam[0]:.3f}, {cam[1]:.3f}, {cam[2]:.3f})  CAM_ROT_DEG = Vector3({pitch:.3f}, {yaw:.3f}, 0.0)"
      f"  CAM_FOV = {a.fov}  (f = {f:.1f} px)")
print(f"Dachs am Ende: Füße ({foot[0]:.0f}, {foot[1]:.0f}), Kopf y = {head[1]:.0f}, Höhe {foot[1] - head[1]:.0f} px; "
      f"Hand beim Winken etwa y = {project((ex, 1.25, ez))[1]:.0f}")
for t, x_, z_, hd in path[::15]:
    pf, ph = project((x_, 0, z_)), project((x_, 1.011, z_))
    if pf is None or ph is None:
        continue
    print(f"  t={t:4.1f}s  x={x_:6.2f} z={z_:5.2f} Blick {hd:5.1f}°  Füße px ({pf[0]:6.0f},{pf[1]:4.0f})  "
          f"Höhe {pf[1] - ph[1]:4.0f}")


def covered(p):
    for r in (PANEL, BOX):
        if r[0] <= p[0] <= r[2] and r[1] <= p[1] <= r[3]:
            return True
    return False


for k, pt in POINTS.items():
    p = project(pt)
    if p is None:
        print(f"  {k:18s} hinter der Kamera")
        continue
    flag = "" if 0 <= p[0] < W and 0 <= p[1] < H else "  (außerhalb)"
    if not flag and covered(p):
        flag = "  (unter Fenster/Kasten)"
    print(f"  {k:18s} x={p[0]:7.1f}  y={p[1]:7.1f}{flag}")
