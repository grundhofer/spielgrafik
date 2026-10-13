#!/usr/bin/env python3
"""Einstellung 2 (Schwenk mit dem Dachs) vorab abschätzen, ohne Godot.

    .venv/bin/python styles/einbit-3d/scripts/frame_shot.py [--cam -3.55,0.9,4.7] [--fov 46] [--feet 150,328]
    .venv/bin/python styles/einbit-3d/scripts/frame_shot.py --search

Die Kamera steht fest (Stativ) und dreht sich nur (Gieren, feste Neigung), damit das an die Blickrichtung
gekoppelte Dithermuster an der Welt haftet. Gesucht ist die Ruhelage am Ende: Füße des Dachses auf Pixel `feet`
in 640×360. Am Anfang der Einstellung (CUT_T) folgt die Kamera dem Dachs zu FOLLOW (wie main.gd). Ausgegeben
werden Schwenkwinkel, Höhe des Dachses in Pixeln und die Bildlage von Leuchtfeuer, Laterne, Booten, Fenster,
Schornstein, Fässern. Bildwinkel vertikal (Keep Height) wie Camera3D.fov.

Näherung: Der Laufplan hier dreht ideal (ohne Warten auf den Standfuß); der echte Endpunkt liegt einige
Zentimeter daneben. main.gd rechnet die Bahn deshalb selbst mit einem unsichtbaren zweiten Dachs (_plan_shot2)
und löst Neigung und Gieren daraus. Dieses Skript diente nur zur Wahl von Kamerastandort und Bildwinkel
(SHOT2_POS, SHOT2_FOV, FEET_PX in main.gd).
"""
import argparse, math

W, H = 640, 360
LOC_BOX = (8, 8, 194, 42)            # Ortsschild mit Schatten (x0, y0, x1, y1), ui.gd
DIALOG = (300, 261, 636, 356)        # Dialogkasten mit Schatten

POINTS = {
    "Leuchtfeuer": (10.2, 12.58, -25.6), "Leuchtturm Fuß": (10.2, 2.8, -25.6),
    "Laterne": (4.10, 1.79, -0.12), "Laternenpfahl Fuß": (4.60, 0.0, -0.12),
    "BoatA": (0.05, -0.3, -6.1), "BoatB Mast": (6.75, 2.2, -6.4), "Kisten": (6.55, 0.6, 0.2),
    "Fenster": (-9.2, 1.45, 0.52), "Schornstein": (-9.58, 4.9, -1.35), "Fass 1": (-5.25, 0.9, -0.15),
    "Fass 2": (-4.55, 0.9, -0.62), "Taurolle": (1.05, 0.2, 0.05), "Poller -3,4": (-3.4, 0.6, -0.7),
}

# Laufplan wie main.gd (_update_badger): Start WalkStart, 0,367 m/s × WALK_RATE, Drehen auf TURN_DEG zwischen
# TURN_T0 und TURN_T1, Bremsen ab BRAKE_T über BRAKE_TIME.
WALK = dict(x0=-6.0, z0=1.2, rate=2.0, v=0.367, turn0=2.55, turn1=3.6, turn_deg=-72.0, brake=3.46, brake_time=0.4,
            idle=3.73)
CUT_T = 2.4
FOLLOW = 0.5                          # Anteil des Gierens, mit dem die Kamera dem Dachs folgt


def ss(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def walk_plan(t_end, w=WALK):
    dt = 1 / 30
    t, x, z, ph = 0.0, w["x0"], w["z0"], 0.0
    while t < t_end - 1e-9 and t < w["idle"] - 1e-9:
        t += dt
        rate = w["rate"] * (1 - ss(w["brake"], w["brake"] + w["brake_time"], t))
        th = math.radians(w["turn_deg"]) * ss(w["turn0"], w["turn1"], t)
        x += w["v"] * rate * dt * math.cos(th)
        z += -w["v"] * rate * dt * math.sin(th)
        ph += rate * dt
    return x, z, ph % 1.0


def cam_basis(yaw, pitch):
    """Godot Basis.from_euler(pitch, yaw, 0) (YXZ): Spalten = Achsen x, y, z der Kamera in Weltkoordinaten."""
    cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
    x = (cy, 0.0, -sy)
    y = (sy * sp, cp, cy * sp)
    z = (sy * cp, -sp, cy * cp)
    return x, y, z


def project(cam, yaw, pitch, f, p):
    bx, by, bz = cam_basis(yaw, pitch)
    d = [p[i] - cam[i] for i in range(3)]
    cx = sum(d[i] * bx[i] for i in range(3))
    cy = sum(d[i] * by[i] for i in range(3))
    cz = sum(d[i] * bz[i] for i in range(3))
    if cz >= -0.01:
        return None
    return W / 2 + f * cx / -cz, H / 2 - f * cy / -cz


def aim(cam, pitch, f, target, u):
    """Gierwinkel, bei dem target auf Bildspalte u liegt (feste Neigung)."""
    yaw = 0.0
    for _ in range(80):
        p = project(cam, yaw, pitch, f, target)
        if p is None:
            yaw += 0.3
            continue
        yaw -= math.atan((p[0] - u) / f) * 0.9
    return yaw


def solve(cam, fov, feet):
    f = (H / 2) / math.tan(math.radians(fov) / 2)
    xe, ze, _ = walk_plan(6.0)
    pitch, yaw = 0.0, 0.0
    for _ in range(60):
        yaw = aim(cam, pitch, f, (xe, 0.0, ze), feet[0])
        p = project(cam, yaw, pitch, f, (xe, 0.0, ze))
        pitch -= math.atan((p[1] - feet[1]) / f) * 0.9
    return f, yaw, pitch, (xe, ze)


def report(cam, fov, feet, verbose=True):
    f, yaw_end, pitch, (xe, ze) = solve(cam, fov, feet)
    xs, zs, _ = walk_plan(CUT_T)
    yaw_start = yaw_end + FOLLOW * (aim(cam, pitch, f, (xs, 0.0, zs), feet[0]) - yaw_end)
    foot = project(cam, yaw_end, pitch, f, (xe, 0.0, ze))
    head = project(cam, yaw_end, pitch, f, (xe, 1.011, ze))
    tall = foot[1] - head[1]
    pts = {k: project(cam, yaw_end, pitch, f, p) for k, p in POINTS.items()}
    pts_start = {k: project(cam, yaw_start, pitch, f, p) for k, p in POINTS.items()}
    pan = math.degrees(yaw_start - yaw_end)
    if verbose:
        print(f"Kamera {cam}, fov {fov}, f = {f:.1f} px; Neigung {math.degrees(pitch):.2f}°, Gieren Ende "
              f"{math.degrees(yaw_end):.2f}°, Anfang {math.degrees(yaw_start):.2f}° (Schwenk {pan:.1f}°)")
        print(f"  Dachs: Anfang ({xs:.2f} | {zs:.2f}), Ende ({xe:.2f} | {ze:.2f}); {tall:.1f} px hoch, Füße {foot[0]:.0f},{foot[1]:.0f}"
              f", Kopf {head[1]:.0f}")
        for k in POINTS:
            p, q = pts[k], pts_start[k]
            ps = f"({p[0]:6.1f},{p[1]:6.1f})" if p else "  hinter der Kamera "
            qs = f"({q[0]:6.1f},{q[1]:6.1f})" if q else "  hinter der Kamera "
            print(f"  {k:18s} Ende {ps}   Anfang {qs}")
    return dict(f=f, yaw_end=yaw_end, yaw_start=yaw_start, pitch=pitch, tall=tall, pts=pts, pts_start=pts_start,
                pan=pan, foot=foot, head=head)


def inside(p, box=(4, 4, W - 4, H - 4)):
    return p is not None and box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cam", default="-3.55,0.9,4.7")
    ap.add_argument("--fov", type=float, default=46.0)
    ap.add_argument("--feet", default="150,328")
    ap.add_argument("--search", action="store_true")
    a = ap.parse_args()
    feet = tuple(map(float, a.feet.split(",")))
    if a.search:
        print("cam                 fov  tall  pan   Leuchtfeuer    Laterne        BoatA          Fenster(Anfang)  Fass2")
        for cx in (-3.6, -3.3, -3.0, -2.7, -2.4):
            for cz in (4.5, 5.0, 5.5, 6.0):
                for cy in (1.0, 1.2, 1.4):
                    for fov in (38.0, 42.0, 46.0):
                        r = report((cx, cy, cz), fov, feet, verbose=False)
                        lh, la, ba, fe = r["pts"]["Leuchtfeuer"], r["pts"]["Laterne"], r["pts"]["BoatA"], r["pts_start"]["Fenster"]
                        b2 = r["pts"]["Fass 2"]
                        if not (inside(lh, (300, 22, 580, 110)) and 105 <= r["tall"] <= 170 and b2 and b2[0] < feet[0] - 75
                                and ba and ba[1] < 236):
                            continue
                        fmt = lambda p: f"({p[0]:5.0f},{p[1]:5.0f})" if p else "     –      "
                        print(f"({cx:5.1f},{cy:4.1f},{cz:4.1f}) {fov:4.0f} {r['tall']:5.0f} {r['pan']:5.1f}  "
                              f"{fmt(lh)} {fmt(la)} {fmt(ba)} {fmt(fe)} {fmt(b2)}")
    else:
        report(tuple(map(float, a.cam.split(","))), a.fov, feet)
