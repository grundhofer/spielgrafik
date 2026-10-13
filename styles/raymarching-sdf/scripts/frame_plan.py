#!/usr/bin/env python3
"""Bildausschnitt rechnen, bevor Godot läuft (PIPELINE.md → Blender: „Bildausschnitt vorher rechnen“).

    .venv/bin/python styles/raymarching-sdf/scripts/frame_plan.py

Kameramodell wie im Shader (harbor_sdf.gdshader → fragment()): Look-at mit Weltachse +Y oben,
vertikaler Bildwinkel fov, Bildpunkte in der internen Auflösung 640×360 (y nach unten).
Gibt für die Kameras aus main.gd die Bildlage der wichtigsten Punkte aus und die Größe des Dachses
(Textkasten der Halbnahen: x 250–626, y 258–348 in 640×360).
"""
import math, sys

W, H = 640, 360

# Wichtige Punkte (Godot-Weltkoordinaten, aus shared/3d/harbor_notes.md)
POINTS = {
    "Laterne": (4.10, 1.79, -0.12),
    "Leuchtfeuer": (10.20, 12.58, -25.60),
    "Leuchtturm Fuss": (10.20, 2.80, -25.60),
    "Fenster Haeuschen": (-9.20, 1.45, 0.52),
    "Schornstein": (-9.58, 4.90, -1.35),
    "Boot A": (0.05, -0.30, -6.10),
    "Boot B": (6.75, -0.30, -6.40),
    "Kisten": (6.55, 0.60, 0.20),
    "Taurolle": (1.05, 0.10, 0.05),
    "Steg Ende": (3.45, 0.04, -8.60),
}


def norm(v):
    l = math.sqrt(sum(c * c for c in v))
    return tuple(c / l for c in v)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def project(cam, tgt, fov, p):
    f = norm(tuple(t - c for t, c in zip(tgt, cam)))
    r = norm(cross(f, (0, 1, 0)))
    u = cross(r, f)
    v = tuple(a - b for a, b in zip(p, cam))
    z = dot(v, f)
    if z <= 0:
        return None
    th = math.tan(math.radians(fov) / 2)
    x = dot(v, r) / z / th / (W / H)
    y = dot(v, u) / z / th
    return ((x * 0.5 + 0.5) * W, (0.5 - y * 0.5) * H, z)


def report(name, cam, tgt, fov, badger=None):
    print(f"== {name}: cam {cam} -> {tgt}, fov {fov}")
    for k, p in POINTS.items():
        q = project(cam, tgt, fov, p)
        print(f"   {k:18s}" + (" hinter der Kamera" if q is None else f" x={q[0]:6.1f} y={q[1]:6.1f}  ({q[2]:5.1f} m)"))
    if badger:
        bx, bz = badger
        foot = project(cam, tgt, fov, (bx, 0.0, bz))
        head = project(cam, tgt, fov, (bx, 1.01, bz))
        print(f"   Dachs bei x={bx}: Fuesse y={foot[1]:.1f}, Kopf y={head[1]:.1f}, Hoehe {foot[1] - head[1]:.1f} px "
              f"(x={foot[0]:.1f}), bei 720 p: {2 * (foot[1] - head[1]):.0f} px")


if __name__ == "__main__":
    # Kameras wie in main.gd: Totale aus shared/3d (CAM_TOT_*) und Halbnahe am Ende der Fahrt (CAM_NEAR_*).
    # Die Halbnahe wurde mit einer Rastersuche über Position, Ziel und fov gewählt: Dachs (Halt bei x = 0,7)
    # links bei x ≈ 190 mit etwa 110 px Höhe, Leuchtfeuer rechts oben, Laternenpfahl rechts neben dem
    # Leuchtturm statt davor, Ruderhaus von Boot A nicht hinter dem Kopf, Laterne über dem Textkasten.
    report("Totale (shared/3d)", (-1.8, 3.4, 14.5), (-1.8, 2.8759, 4.5137), 42.0, (-1.2, 1.2))
    report("Halbnahe (Ende der Fahrt)", (2.4, 1.0, 5.5), (1.0, 2.4, -8.0), 44.0, (0.7, 1.2))
