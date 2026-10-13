#!/usr/bin/env python3
"""Bildausschnitt der festen Einstellungen rechnen (ohne Blender und Godot).

    .venv/bin/python styles/vorgerendert-fixkamera/scripts/frame.py [shots.json]

Liest die Einstellungen aus demo/shots.json (Position, Ziel, vertikaler Bildwinkel in Godot-Koordinaten),
baut die Kamera wie Godot (looking_at mit +Y oben, Keep Height, 320×240) und gibt die Bildlage wichtiger
Punkte aus: Dachs an Start, Halt und Kopf, Leuchtfeuer, Laterne, Fenster, Kaikante.
"""
import json
import math
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent.parent
W, H = 320, 240


def basis_looking_at(pos, target):
    f = np.array(target, float) - np.array(pos, float)
    f /= np.linalg.norm(f)
    z = -f
    x = np.cross([0.0, 1.0, 0.0], z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.stack([x, y, z], axis=1)  # Spalten = lokale Achsen


def project(shot, p):
    b = basis_looking_at(shot["pos"], shot["target"])
    v = b.T @ (np.array(p, float) - np.array(shot["pos"], float))
    f = (H / 2) / math.tan(math.radians(shot["fov"]) / 2)
    if v[2] >= 0:
        return None
    return W / 2 + f * v[0] / -v[2], H / 2 - f * v[1] / -v[2], -v[2]


def main():
    path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "demo" / "shots.json"
    data = json.loads(path.read_text())
    pts = {
        "Lampe Leuchtturm": (10.2, 12.58, -25.6), "Leuchtturm Spitze": (10.2, 14.4, -25.6),
        "Leuchtturm Fuss": (10.2, 2.8, -25.6), "Laterne": (4.1, 1.79, -0.12), "Fenster": (-9.2, 1.45, 0.52),
        "Schornstein": (-9.58, 4.9, -1.35), "BoatA": (0.05, 0.3, -6.1), "BoatB": (6.75, 0.3, -6.4),
        "Kaikante x=0": (0.0, 0.0, -1.0), "Fass1": (-5.25, 0.9, -0.15),
    }
    for p in data["path"]:
        pts[f"Dachs {p['name']} Fuss"] = (p["x"], 0.0, p["z"])
        pts[f"Dachs {p['name']} Kopf"] = (p["x"], 1.01, p["z"])
    for shot in data["shots"]:
        print(f"== {shot['name']}  pos={shot['pos']} target={shot['target']} fov={shot['fov']}")
        for k, p in pts.items():
            r = project(shot, p)
            if r is None:
                print(f"  {k:22s} hinter der Kamera")
                continue
            x, y, d = r
            inside = 0 <= x < W and 0 <= y < H
            print(f"  {k:22s} x={x:7.1f} y={y:7.1f} d={d:6.2f} m {'' if inside else '(ausserhalb)'}")
        for p in data["path"]:
            a, b = project(shot, (p["x"], 0, p["z"])), project(shot, (p["x"], 1.01, p["z"]))
            if a and b:
                print(f"  Dachshoehe bei {p['name']}: {a[1] - b[1]:.1f} px")


if __name__ == "__main__":
    main()
