#!/usr/bin/env python3
"""Bildausschnitt der festen Nahaufnahme (Einstellung 2) berechnen, ohne Godot zu starten.

    .venv/bin/python styles/ps1-lowpoly/scripts/frame_closeup.py [--fov 80] [--angle -12] [--dist 2.8] \
        [--height 0.5] [--feet 84,156]
    .venv/bin/python styles/ps1-lowpoly/scripts/frame_closeup.py --search     # Kandidaten auflisten

Die Kamera steht `dist` m vom Dachs entfernt, `angle` Grad von +Z aus gedreht (negativ = links vom Dachs,
also Richtung Häuschen), `height` m über dem Kai. Neigung und Gieren werden so gelöst, dass die Füße des
Dachses auf Pixel `feet` (320×240) liegen. Ausgegeben werden Kameraversatz, Neigung, Gieren (Werte für
main.gd: CU_OFFSET, CU_PITCH, CU_YAW, CU_FOV) und die Bildlage von Dachs, Laterne, Leuchtturm und weiteren
Teilen. Bildwinkel horizontal (Keep Width) wie in main.tscn.

Bedingungen (Prüfung "ok"): Laternenpfahl ganz im Bild (Fuß bis Laterne, nicht unter Orts- oder
Dialogfenster), Leuchtfeuer im Bild und nicht hinter dem Kopf des Dachses, Dachs 60–80 px hoch.
Positionen aus shared/3d/harbor_notes.md (Godot-Koordinaten); der Dachs steht nach dem Bremsen bei x = -3,58.
Die Standardwerte sind die der Demo (main.gd: CU_OFFSET, CU_PITCH, CU_YAW, CU_FOV). Mit --search lassen sich
Winkel, Abstand und Fußposition durchprobieren; 0,5 m Kamerahöhe hält den Horizont tief genug, dass der
Leuchtturm ganz unter dem Ortsfenster bleibt.
"""
import argparse
import math

ap = argparse.ArgumentParser()
ap.add_argument("--fov", type=float, default=80.0)
ap.add_argument("--angle", type=float, default=-12.0)
ap.add_argument("--dist", type=float, default=2.8)
ap.add_argument("--height", type=float, default=0.5)
ap.add_argument("--feet", default="84,156")
ap.add_argument("--badger-x", type=float, default=-3.58)
ap.add_argument("--search", action="store_true")
a = ap.parse_args()

W, H = 320, 240
LOC_BOX = (8, 8, 190, 27)          # Ortsfenster (x0, y0, x1, y1), ui.gd
DIALOG_TOP = 168                   # Dialogfenster ab Zeile 168
BZ = 1.2                           # Laufweg z

POINTS = {
    "Laterne (Glas)": (4.10, 1.79, -0.12), "Laternenpfahl Fuß": (4.60, 0.0, -0.12),
    "Laternenpfahl Kopf": (4.60, 2.45, -0.12),
    "Leuchtfeuer": (10.2, 12.58, -25.6), "Leuchtturm Spitze": (10.2, 14.4, -25.6), "Leuchtturm Fuß": (10.2, 2.8, -25.6),
    "BoatA Ruderhaus": (0.05, 0.5, -6.1), "BoatB Mast": (6.75, 2.2, -6.4), "Kisten": (6.55, 0.6, 0.2),
    "Poller (-3,4)": (-3.4, 0.6, -0.7), "Fass 2": (-4.55, 0.9, -0.62), "Schornstein": (-9.58, 4.9, -1.35),
}


def rot(pitch, yaw, v):
    """Weltvektor in Kamerakoordinaten (Godot: Basis.from_euler(pitch, yaw, 0), Reihenfolge YXZ)."""
    p, y = math.radians(pitch), math.radians(yaw)
    x, yy, z = v
    x, z = x * math.cos(y) - z * math.sin(y), x * math.sin(y) + z * math.cos(y)       # inverse Gieren
    yy, z = yy * math.cos(p) + z * math.sin(p), -yy * math.sin(p) + z * math.cos(p)   # inverse Neigung
    return x, yy, z


def solve(fov, angle, dist, height, feet, bx):
    f = 160 / math.tan(math.radians(fov / 2))
    cam = (bx + dist * math.sin(math.radians(angle)), height, BZ + dist * math.cos(math.radians(angle)))

    def project(p):
        x, y, z = rot(pitch, yaw, [p[i] - cam[i] for i in range(3)])
        if z >= -0.01:
            return None
        return 160 + f * x / -z, 120 - f * y / -z

    pitch = yaw = 0.0
    for _ in range(60):
        fx, fy = project((bx, 0, BZ))
        yaw -= math.degrees(math.atan((fx - feet[0]) / f))
        pitch -= math.degrees(math.atan((fy - feet[1]) / f))
    return cam, pitch, yaw, f, project


def inside(p, margin=4):
    if p is None:
        return False
    x, y = p
    if not (margin <= x <= W - margin and margin <= y <= DIALOG_TOP - 2):
        return False
    return not (LOC_BOX[0] - 2 <= x <= LOC_BOX[2] + 2 and LOC_BOX[1] - 2 <= y <= LOC_BOX[3] + 2)


def evaluate(fov, angle, dist, height, feet, bx):
    cam, pitch, yaw, f, project = solve(fov, angle, dist, height, feet, bx)
    pts = {k: project(p) for k, p in POINTS.items()}
    head = project((bx, 1.01, BZ))
    pts["Dachs Kopf"] = head
    pts["Dachs Füße"] = project((bx, 0, BZ))
    tall = pts["Dachs Füße"][1] - head[1]
    lantern_ok = all(inside(pts[k]) for k in ("Laterne (Glas)", "Laternenpfahl Fuß", "Laternenpfahl Kopf"))
    lamp = pts["Leuchtfeuer"]
    lamp_ok = inside(lamp) and abs(lamp[0] - head[0]) > 30
    ok = lantern_ok and lamp_ok and 60 <= tall <= 80
    return dict(cam=cam, pitch=pitch, yaw=yaw, f=f, pts=pts, tall=tall, lantern_ok=lantern_ok, lamp_ok=lamp_ok,
                ok=ok, horizon=120 + f * math.tan(math.radians(pitch)))


feet = tuple(map(float, a.feet.split(",")))
if a.search:
    print("angle  dist  height  feet      Dachs px  Laterne(x,y)   Leuchtfeuer(x,y)  ok")
    for angle in range(-40, 11, 4):
        for dist in (2.4, 2.7, 3.0):
            for fx in (70, 82, 96):
                r = evaluate(a.fov, angle, dist, a.height, (fx, feet[1]), a.badger_x)
                if r["lantern_ok"]:
                    la, lh = r["pts"]["Laterne (Glas)"], r["pts"]["Leuchtfeuer"]
                    lh_s = f"({lh[0]:5.0f},{lh[1]:5.0f})" if lh else "   –"
                    print(f"{angle:5d} {dist:5.1f} {a.height:6.2f}  {fx:3.0f},{feet[1]:3.0f}   {r['tall']:6.1f}"
                          f"   ({la[0]:5.0f},{la[1]:5.0f})  {lh_s}       {'ok' if r['ok'] else '-'}")
else:
    r = evaluate(a.fov, a.angle, a.dist, a.height, feet, a.badger_x)
    cam = r["cam"]
    print(f"CU_OFFSET = ({cam[0] - a.badger_x:.3f}, {cam[1]:.3f}, {cam[2] - BZ:.3f})  CU_PITCH = {r['pitch']:.2f}"
          f"  CU_YAW = {r['yaw']:.2f}  CU_FOV = {a.fov}  Horizont in Zeile {r['horizon']:.1f}  f = {r['f']:.1f}")
    print(f"  Dachs {r['tall']:.1f} px hoch; Laternenpfahl ganz im Bild: {r['lantern_ok']}; "
          f"Leuchtfeuer im Bild, neben dem Kopf: {r['lamp_ok']}")
    for k, p in r["pts"].items():
        print(f"  {k:20s} " + (f"x={p[0]:6.1f}  y={p[1]:6.1f}" if p else "hinter der Kamera"))
