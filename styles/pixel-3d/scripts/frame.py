#!/usr/bin/env python3
"""Bildausschnitt der Pixel-3D-Demo ausrechnen, ohne Godot zu starten.

    .venv/bin/python styles/pixel-3d/scripts/frame.py                 # Werte der Demo (main.gd)
    .venv/bin/python styles/pixel-3d/scripts/frame.py --cam=-0.7,1.35,6.1 --fov=54   # andere Kamera

Kamera wie in main.gd: feste Position, Gieren yaw, Neigung pitch, Bildwinkel fov (vertikal, für die
Renderhöhe RH), Projektion FRUSTUM. Der Schwenk ist eine Objektivverschiebung (frustum_offset) um
`shift` Renderpixel nach rechts; der Bildinhalt wandert dabei um genau so viele Pixel nach links.
Ausgegeben wird die Bildlage (in Pixeln des sichtbaren 426×240-Bildes) von Dachs, Laterne,
Leuchtturm, Häuschen, Booten am Anfang (Schwenk SHIFT0) und am Ende (SHIFT1) der Fahrt.
Positionen aus shared/3d/harbor_notes.md (Godot-Koordinaten).
"""
import argparse
import math

RW, RH = 428, 242              # Renderauflösung (1 px Rand für den Restversatz)
VW, VH = 426.667, 240          # sichtbar: 1280×720 / 3
DIALOG_TOP = 192               # Dialogkasten ab Zeile 192 (ui.gd: BOX)
BZ = 1.2                       # Laufweg z

POINTS = {
    "Laterne Glas": (4.10, 1.79, -0.12), "Laternenpfahl Fuß": (4.60, 0.0, -0.12),
    "Laternenpfahl Kopf": (4.60, 2.45, -0.12),
    "Leuchtfeuer": (10.2, 12.58, -25.6), "Leuchtturm Spitze": (10.2, 14.4, -25.6),
    "Leuchtturm Fuß": (10.2, 2.8, -25.6),
    "BoatA Ruderhaus": (0.05, 0.5, -6.1), "BoatB Mast": (6.75, 2.2, -6.4), "Kisten": (6.55, 0.6, 0.2),
    "Fass 1": (-5.25, 0.9, -0.15), "Fass 2": (-4.55, 0.9, -0.62),
    "Häuschen Fenster": (-9.2, 1.45, 0.52), "Häuschen Ecke rechts": (-6.6, 2.45, 0.5),
    "Schornstein": (-9.58, 4.9, -1.35), "Taurolle": (1.05, 0.3, 0.05),
}


def cam_space(p, cam, yaw, pitch):
    """Welt -> Kamera (Godot: Basis.from_euler(Vector3(pitch, yaw, 0)), Reihenfolge YXZ)."""
    y, pt = math.radians(yaw), math.radians(pitch)
    x, yy, z = (p[i] - cam[i] for i in range(3))
    x, z = x * math.cos(y) - z * math.sin(y), x * math.sin(y) + z * math.cos(y)
    yy, z = yy * math.cos(pt) + z * math.sin(pt), -yy * math.sin(pt) + z * math.cos(pt)
    return x, yy, z


def project(p, cam, yaw, pitch, fov, shift, vshift=0.0):
    """Pixel im sichtbaren Bild (0..426, 0..240), wie main.gd: sichtbar = Render − (⅓, 1) bei Restversatz 0."""
    f = (RH / 2) / math.tan(math.radians(fov / 2))
    x, y, z = cam_space(p, cam, yaw, pitch)
    if z >= -0.01:
        return None
    rx = RW / 2 + f * x / -z - shift
    ry = RH / 2 - f * y / -z + vshift
    return rx - 1.0 / 3.0, ry - 1.0


def report(a, cam, label, shift, bx, turned=False):
    print(f"--- {label}: Schwenk {shift:.0f} px, Dachs bei x = {bx:.2f}")
    pr = lambda p: project(p, cam, a.yaw, a.pitch, a.fov, shift, a.vshift)
    feet, head = pr((bx, 0, BZ)), pr((bx, 1.01, BZ))
    if feet and head:
        print(f"  Dachs: Füße ({feet[0]:6.1f},{feet[1]:6.1f}), Kopf y {head[1]:6.1f}, Höhe {feet[1] - head[1]:5.1f} px")
    for k, p in POINTS.items():
        q = pr(p)
        flag = ""
        if q is None:
            flag = "hinter der Kamera"
        elif not (0 <= q[0] <= VW and 0 <= q[1] <= VH):
            flag = "außerhalb"
        elif q[1] > DIALOG_TOP:
            flag = "unter dem Dialogkasten"
        print(f"  {k:22s} " + (f"({q[0]:6.1f},{q[1]:6.1f}) {flag}" if q else flag))
    hz = pr((cam[0], cam[1], cam[2] - 5000.0))
    print(f"  Horizont in Zeile {hz[1]:.1f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cam", default="-0.9,1.5,6.5")
    ap.add_argument("--yaw", type=float, default=0.0)
    ap.add_argument("--pitch", type=float, default=-1.8)
    ap.add_argument("--fov", type=float, default=52.0)
    ap.add_argument("--vshift", type=float, default=0.0)
    ap.add_argument("--shift0", type=float, default=-61.4)
    ap.add_argument("--shift1", type=float, default=12.0)
    ap.add_argument("--bx0", type=float, default=-4.9)
    ap.add_argument("--bx1", type=float, default=-2.66)
    a = ap.parse_args()
    cam = tuple(map(float, a.cam.split(",")))
    f = (RH / 2) / math.tan(math.radians(a.fov / 2))
    print(f"f = {f:.2f} px; Pixelgröße in 6 m Abstand: {6 / f * 100:.2f} cm")
    report(a, cam, "Anfang", a.shift0, a.bx0)
    report(a, cam, "Ende", a.shift1, a.bx1)


if __name__ == "__main__":
    main()
