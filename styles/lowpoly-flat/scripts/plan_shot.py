#!/usr/bin/env python3
"""Lauf und Nahaufnahme vorab rechnen (ohne Godot).

1. Simuliert den Lauf wie main.gd (_update_badger, ohne die kleinen Versätze der Drehung um den
   Standfuß): Walk mit speed_scale 2, Abbiegen zur Kamera zwischen TURN_T0 und TURN_T1, Bremsen ab
   brake_t über 0,4 s. Gibt Phase des Laufzyklus beim Umschalten auf Idle und den Endpunkt aus.
   Gesucht ist eine Durchgangsphase (≈0,3 oder ≈0,8), dann senkt die Überblendung nur den Schwungfuß ab.
2. Projiziert wichtige Punkte für die Nahaufnahme-Kamera (Godot: looking_at mit +Y oben, fov vertikal,
   Keep Height) auf 1280×720.

    .venv/bin/python styles/lowpoly-flat/scripts/plan_shot.py --pos=-1.25,1.3,5.25 --target=-1.25,1.125,-4.75 --fov 50 --scan
"""
import argparse
import math

import numpy as np

W, H = 1280, 720
V = 0.367


def ss(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def walk(brake_t, turn_deg, x0=-6.0, z0=1.2, turn0=2.2, turn1=3.2, brake_time=0.4, rate0=2.0):
    idle_t = brake_t + brake_time - 0.05
    dt = 1 / 30
    t, x, z, ph = 0.0, x0, z0, 0.0
    while t < idle_t - 1e-9:
        t += dt
        rate = rate0 * (1 - ss(brake_t, brake_t + brake_time, t))
        th = math.radians(turn_deg) * ss(turn0, turn1, t)
        x += V * rate * dt * math.cos(th)
        z += -V * rate * dt * math.sin(th)
        ph += rate * dt
    return ph % 1.0, x, z


def look_basis(pos, target):
    f = np.array(target, float) - np.array(pos, float)
    f /= np.linalg.norm(f)
    z = -f
    x = np.cross([0.0, 1.0, 0.0], z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.stack([x, y, z], axis=1)


def project(p, pos, basis, fov):
    v = basis.T @ (np.array(p, float) - np.array(pos, float))
    if v[2] >= 0:
        return None
    f = (H / 2) / math.tan(math.radians(fov) / 2)
    return (W / 2 + f * v[0] / -v[2], H / 2 - f * v[1] / -v[2])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pos", default="-1.6,1.45,4.6")
    ap.add_argument("--target", default="0.4,1.2,-4")
    ap.add_argument("--fov", type=float, default=46.0)
    ap.add_argument("--brake", type=float, default=3.2)
    ap.add_argument("--turn", type=float, default=None, help="Drehung in Grad (Standard: zur Kamera)")
    ap.add_argument("--scan", action="store_true", help="Bremszeiten 2,9–3,4 s durchprobieren")
    ap.add_argument("--x0", type=float, default=-5.0, help="Startpunkt x (main.gd START_X)")
    a = ap.parse_args()
    pos = [float(v) for v in a.pos.split(",")]
    tgt = [float(v) for v in a.target.split(",")]

    turn = a.turn
    for _ in range(4):   # Drehung zur Kamera und Endpunkt hängen voneinander ab
        _, bx, bz = walk(a.brake, turn if turn is not None else -60.0, x0=a.x0)
        if a.turn is None:
            turn = math.degrees(math.atan2(-(pos[2] - bz), pos[0] - bx))
    ph, bx, bz = walk(a.brake, turn, x0=a.x0)
    print(f"Drehung {turn:.1f}°, Bremsen ab {a.brake:.2f} s: Phase {ph:.3f}, Ende x={bx:.2f} z={bz:.2f}")
    if a.scan:
        for i in range(290, 341, 2):
            p2, x2, z2 = walk(i / 100, turn, x0=a.x0)
            print(f"  brake {i / 100:.2f}: Phase {p2:.3f}  Ende ({x2:.2f}, {z2:.2f})")

    B = look_basis(pos, tgt)
    pts = {
        "Dachs Füße": (bx, 0.0, bz), "Dachs Kopf": (bx, 1.01, bz), "Dachs Winkhand": (bx, 1.2, bz),
        "Leuchtfeuer": (10.2, 12.58, -25.6), "Leuchtturm Fuß": (10.2, 2.8, -25.6),
        "Leuchtturm Spitze": (10.2, 14.4, -25.6),
        "Laterne": (4.1, 1.79, -0.12), "Laternenpfahl Fuß": (4.6, 0.0, -0.12),
        "BoatA Bug": (2.35, -0.3, -6.1), "BoatA Heck": (-2.25, -0.3, -6.1), "BoatB": (6.75, -0.3, -6.4),
        "Kaikante x=-4": (-4.0, 0.0, -1.0), "Kaikante x=4": (4.0, 0.0, -1.0),
        "Steg Ende": (3.45, 0.0, -8.6), "Fenster Haus": (-9.2, 1.45, 0.52), "Rauch": (-9.58, 4.9, -1.35),
        "Fass 1": (-5.25, 0.45, -0.15), "Fass 2": (-4.55, 0.45, -0.62), "Kisten": (6.55, 0.5, 0.2),
        "Taurolle": (1.05, 0.1, 0.05), "Horizont (z=-900)": (0.0, -0.8, -900.0),
    }
    d = math.dist(pos, (bx, 0.5, bz))
    print(f"Abstand Kamera–Dachs {d:.2f} m, Dachs ≈ {1.01 * (H / 2) / math.tan(math.radians(a.fov) / 2) / d:.0f} px")
    for k, p in pts.items():
        s = project(p, pos, B, a.fov)
        flag = "" if s and 0 <= s[0] < W and 0 <= s[1] < H else "  (außerhalb)"
        print(f"{k:18s} " + (f"{s[0]:7.0f} {s[1]:6.0f}" if s else "hinter der Kamera") + flag)


if __name__ == "__main__":
    main()
