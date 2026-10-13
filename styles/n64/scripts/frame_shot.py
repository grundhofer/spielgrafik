#!/usr/bin/env python3
"""Bildausschnitt der Schlusseinstellung vorab ausrechnen (ohne Godot).

    python3 styles/n64/scripts/frame_shot.py                 # Werte aus main.gd (CAM_END) prüfen
    python3 styles/n64/scripts/frame_shot.py --search        # Kandidaten suchen

Projiziert Dachs (Füße, Kopf), Laterne, Leuchtfeuer, Boote, Kisten und Häuschen in ein 320×240-Bild
(Godot: Drehung YXZ, Blick entlang −Z, vertikaler Bildwinkel fest = Keep Height).
"""
import itertools
import math
import sys

W, H = 320, 240
BOX_TOP = 160            # Oberkante des Dialogfensters (main.gd BOX_BOTTOM)

POINTS = {
    "lantern_glass": (4.10, 1.79, -0.12),
    "lantern_base": (4.60, 0.0, -0.12),
    "lamp": (10.2, 12.58, -25.6),
    "lighthouse_base": (10.2, 2.8, -25.6),
    "boatA": (0.05, -0.3, -6.1),
    "boatB": (6.75, -0.3, -6.4),
    "crates": (6.55, 0.6, 0.2),
    "cottage_win": (-9.2, 1.45, 0.52),
    "chimney": (-9.58, 4.9, -1.35),
}


def project(p, cam, yaw, pitch, fov):
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    d = [p[i] - cam[i] for i in range(3)]
    # R = Ry(yaw) * Rx(pitch); Kamerakoordinaten = R^T d
    x1 = cy * d[0] - sy * d[2]
    z1 = sy * d[0] + cy * d[2]
    y1 = d[1]
    xc = x1
    yc = cp * y1 + sp * z1
    zc = -sp * y1 + cp * z1
    if zc >= -0.01:
        return None
    f = (H / 2) / math.tan(math.radians(fov / 2))
    return (W / 2 + f * xc / -zc, H / 2 - f * yc / -zc)


def report(bx, cam, yaw, pitch, fov):
    out = {}
    out["feet"] = project((bx, 0.0, 1.2), cam, yaw, pitch, fov)
    out["head"] = project((bx, 1.01, 1.2), cam, yaw, pitch, fov)
    for k, p in POINTS.items():
        out[k] = project(p, cam, yaw, pitch, fov)
    return out


def fmt(o):
    return " ".join(f"{k}=({v[0]:.0f},{v[1]:.0f})" if v else f"{k}=hinter" for k, v in o.items())


def main():
    if "--search" in sys.argv:
        bx = float(sys.argv[sys.argv.index("--bx") + 1]) if "--bx" in sys.argv else -3.62
        res = []
        for dx, dz, hgt, fov in itertools.product([0.8, 1.2, 1.6, 2.0, 2.4], [2.2, 2.6, 3.0, 3.4],
                                                  [0.9, 1.1, 1.3, 1.5], [40, 46, 52, 58]):
            cam = (bx + dx, hgt, 1.2 + dz)
            for yaw in range(-30, 31, 2):
                for pitch in range(-14, 8, 2):
                    o = report(bx, cam, yaw, pitch, fov)
                    if None in (o["feet"], o["head"], o["lamp"], o["lantern_glass"]):
                        continue
                    fx, fy = o["feet"]
                    hx, hy = o["head"]
                    lx, ly = o["lamp"]
                    gx, gy = o["lantern_glass"]
                    hgt_px = fy - hy
                    if not (BOX_TOP - 14 <= fy <= BOX_TOP - 2 and 50 <= fx <= 110 and hgt_px >= 80):
                        continue
                    if not (150 <= lx <= 305 and 14 <= ly <= 90 and 150 <= gx <= 305 and gy < BOX_TOP - 10):
                        continue
                    if abs(lx - gx) < 40:
                        continue
                    res.append((hgt_px, cam, yaw, pitch, fov, o))
        res.sort(key=lambda r: -r[0])
        for r in res[:25]:
            print(f"h={r[0]:.0f} cam=({r[1][0]:.2f},{r[1][1]:.2f},{r[1][2]:.2f}) yaw={r[2]} pitch={r[3]} fov={r[4]}  {fmt(r[5])}")
        print(len(res), "Kandidaten")
        return
    # einzelne Einstellung: --cam x,y,z,yaw,pitch,fov --bx X
    vals = [float(v) for v in sys.argv[sys.argv.index("--cam") + 1].split(",")]
    bx = float(sys.argv[sys.argv.index("--bx") + 1])
    o = report(bx, tuple(vals[:3]), vals[3], vals[4], vals[5])
    print(fmt(o))
    print("Figurhöhe", o["feet"][1] - o["head"][1])


if __name__ == "__main__":
    main()
