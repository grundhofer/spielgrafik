#!/usr/bin/env python3
"""Kamera-Transform für main.tscn aus Position, Neigung und Gieren (Godot: Basis = Ry(gieren) · Rx(neigung)).

    python3 styles/vertex-animation/scripts/cam_tf.py X,Y,Z PITCH YAW
Ausgabe im .tscn-Format (Basis zeilenweise, dann Ursprung).
"""
import math
import sys

pos = [float(v) for v in sys.argv[1].split(",")]
p, y = math.radians(float(sys.argv[2])), math.radians(float(sys.argv[3]))
cy, sy, cp, sp = math.cos(y), math.sin(y), math.cos(p), math.sin(p)
Ry = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]
Rx = [[1, 0, 0], [0, cp, -sp], [0, sp, cp]]
B = [[sum(Ry[i][k] * Rx[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
print("Transform3D(" + ", ".join(f"{v:.7g}" for row in B for v in row) + ", " + ", ".join(f"{v:g}" for v in pos) + ")")
