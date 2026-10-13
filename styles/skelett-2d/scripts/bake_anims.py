"""Animationen walk / stop / idle für den Dachs-Rig (Teil von build_rig.py).

Alle Größen im Rig-Raum (Pixel, y nach unten, Ursprung am Boden unter der Hüfte). Ruhedrehungen aller
Knochen sind 0, eine Animation setzt also Drehwinkel relativ zur Ruhelage.

Gang: Fußbahnen im Raum der mitlaufenden Figur (Wurzel bewegt sich mit v = Schrittweg / Zyklus).
Standfuß: Knöchel fest im Weltraum (im Figurenraum mit -v), zum Ende abrollen über die Zehe.
Schwungfuß: Hermite-Bahn mit Weltgeschwindigkeit 0 an Abheben und Aufsetzen, Hub sin(pi s).
Knie und Fuß per Zwei-Gelenk-IK (Knie nach vorn). Die Hüfthöhe folgt der Schrittphase (tiefer im
Doppelstand), der Oberkörper federt nach. Alles wird mit 60 Schlüsseln/s abgetastet.
"""
import math

import numpy as np

FPS_KEYS = 60
T_WALK = 2.0 / 3.0       # Doppelschritt (20 Bilder bei 30 fps)
BETA = 0.60              # Anteil Standphase
STEP_L = 27.0            # Weg des Knöchels relativ zur Figur während der Standphase (Rig-px)
LIFT = 9.0               # Hub des Schwungfußes
ROLL = 0.12              # Abrollen über die Zehe am Ende der Standphase (Anteil Zyklus)
PSI_MAX = math.radians(20)
BOB = 1.2                # Hüftwippen
T_STOP = 0.5
T_IDLE = 2.4
DEG = math.pi / 180


def R2(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s], [s, c]])


def ang(v):
    return math.atan2(v[1], v[0])


class Rig:
    def __init__(self, bones):
        self.b = bones
        self.rest = {k: np.array(v["pos"], float) for k, v in bones.items()}
        self.tip = {k: np.array(v["tip"], float) for k, v in bones.items()}
        self.off = {k: self.rest[k] - (self.rest[v["parent"]] if v["parent"] else 0) for k, v in bones.items()}
        self.order = list(bones.keys())   # Eltern stehen vor Kindern (rig_def.BONES)

    def fk(self, pose):
        """pose: {bone: {"rot":rad, "pos":vec (nur hip), "scale":vec}} -> Weltlage (pos, rot) je Knochen."""
        W = {}
        for k in self.order:
            p = pose.get(k, {})
            par = self.b[k]["parent"]
            local_pos = np.array(p["pos"], float) if "pos" in p else self.off[k] + (0 if par else 0)
            if par is None:
                wp, wr = local_pos, p.get("rot", 0.0)
            else:
                pp, pr, ps = W[par]
                wp = pp + R2(pr) @ (ps * local_pos)
                wr = pr + p.get("rot", 0.0)
            W[k] = (wp, wr, np.array(p.get("scale", (1.0, 1.0)), float))
        return W


def hermite(s, m0, m1):
    return (s ** 3 - 2 * s ** 2 + s) * m0 + (-2 * s ** 3 + 3 * s ** 2) + (s ** 3 - s ** 2) * m1


def smooth(s):
    s = min(max(s, 0.0), 1.0)
    return s * s * (3 - 2 * s)


def bump(s):
    s = min(max(s, 0.0), 1.0)
    return math.sin(math.pi * s) ** 2


class Gait:
    def __init__(self, rig):
        self.rig = rig
        r = rig.rest
        self.side = {}
        for s in "nf":
            H, K, A = r["thigh_" + s], r["shin_" + s], r["foot_" + s]
            T = np.array(rig.b["foot_" + s]["roll"], float)
            ground = rig.b["foot_" + s]["sole"]
            self.side[s] = {"H": H, "K": K, "A": A, "T": T, "l1": np.linalg.norm(K - H),
                            "l2": np.linalg.norm(A - K), "a1": ang(K - H), "a2": ang(A - K),
                            "toe_rel": T - A, "ground": ground,
                            "ah": ground - A[1],               # Knöchelhöhe über dem Boden
                            "c": (A[0] - H[0]) + 3.0}          # Mitte der Fußbahn relativ zur Hüfte
        self.v = STEP_L / (BETA * T_WALK)

    def ik(self, s, Hw, Aw, hip_rot, foot_world):
        d = self.side[s]
        l1, l2 = d["l1"], d["l2"]
        v = Aw - Hw
        dist = float(np.linalg.norm(v))
        dmax = (l1 + l2) * 0.995
        ext = dist / (l1 + l2)
        if dist > dmax:
            v *= dmax / dist
            dist = dmax
        cosg = (l1 * l1 + dist * dist - l2 * l2) / (2 * l1 * dist)
        g = math.acos(max(-1.0, min(1.0, cosg)))
        a = ang(v) - g                       # Knie nach vorn (+x)
        Kw = Hw + l1 * np.array([math.cos(a), math.sin(a)])
        Aw2 = Hw + v
        th_w = a - d["a1"]
        sh_w = ang(Aw2 - Kw) - d["a2"]
        return {"thigh_" + s: th_w - hip_rot, "shin_" + s: sh_w - th_w, "foot_" + s: foot_world - sh_w}, ext

    def foot_walk(self, s, phi):
        """Knöchel (x relativ zur Wurzel, y) und Fußwinkel für Phase phi des jeweiligen Beins."""
        d = self.side[s]
        L, c = STEP_L, d["H"][0] + d["c"]
        gy = d["ground"] - d["ah"]
        if phi < BETA:
            u = L / 2 - L * phi / BETA
            Ax, Ay, psi = c + u, gy, 0.0
            if phi > BETA - ROLL:
                psi = PSI_MAX * smooth((phi - (BETA - ROLL)) / ROLL)
                toe = np.array([Ax, Ay]) + d["toe_rel"]
                A = toe - R2(psi) @ d["toe_rel"]
                Ax, Ay = A
            return np.array([Ax, Ay]), psi
        s_ = (phi - BETA) / (1 - BETA)
        m = -(1 - BETA) / BETA
        u = -L / 2 + L * hermite(s_, m, m)
        # Start der Schwungbahn an das Abrollende anschließen
        toe = np.array([c - L / 2, gy]) + d["toe_rel"]
        A_roll = toe - R2(PSI_MAX) @ d["toe_rel"]
        delta = A_roll - np.array([c - L / 2, gy])
        lift = LIFT * math.sin(math.pi * s_) ** 0.9
        psi = PSI_MAX * (1 - s_) ** 2 - 8 * DEG * math.sin(math.pi * s_)
        A = np.array([c + u, gy - lift]) + delta * (1 - s_) ** 2
        return A, psi


def walk_upper(phi):
    c2 = math.cos(4 * math.pi * phi)
    p = {
        "hip": {"rot": -2.0 * DEG * c2},
        "spine": {"rot": 4.0 * DEG + 2.0 * DEG * math.sin(4 * math.pi * phi - 0.6)},
        "neck": {"rot": -1.5 * DEG + 1.8 * DEG * math.sin(4 * math.pi * phi - 1.3)},
        "head": {"rot": -2.5 * DEG + 2.6 * DEG * math.sin(4 * math.pi * phi - 2.0)},
        "belly": {"scale": (1 + 0.05 * c2, 1 - 0.04 * c2)},
        "arm_f": {"rot": -22 * DEG * math.cos(2 * math.pi * phi)},
        "fore_f": {"rot": -12 * DEG - 18 * DEG * max(0.0, math.cos(2 * math.pi * phi))},
        "arm_n": {"rot": 4.5 * DEG * math.cos(2 * math.pi * phi)},
        "fore_n": {"rot": -2.0 * DEG * math.cos(2 * math.pi * phi)},
        "tail": {"rot": 12 * DEG * math.sin(4 * math.pi * phi - 1.0)},
    }
    return p


def bake(bones):
    rig = Rig(bones)
    # Sohle des fernen Fußes: aus der Ruhelage (Spitze des Fußknochens liegt auf Sohlenhöhe -> Abstand messen)
    g = Gait(rig)
    hip0 = rig.rest["hip"].copy()
    info = {"walk_cycle": T_WALK, "beta": BETA, "step_l": STEP_L, "walk_speed": g.v, "stop_time": T_STOP,
            "stop_dist": g.v * T_STOP / 2, "idle_time": T_IDLE}

    # Hüfthöhe im Gang so wählen, dass das gestreckteste Bein 97 % erreicht
    def walk_pose(phi, drop):
        up = walk_upper(phi)
        hy = hip0[1] + drop + BOB * math.cos(4 * math.pi * phi)
        up["hip"]["pos"] = (hip0[0], hy)
        W = rig.fk(up)
        ext = 0
        for s, ph in (("n", phi), ("f", (phi + 0.5) % 1.0)):
            A, psi = g.foot_walk(s, ph)
            Hw = W["thigh_" + s][0]
            rots, e = g.ik(s, Hw, A, W["hip"][1], psi)
            ext = max(ext, e)
            for k, v in rots.items():
                up.setdefault(k, {})["rot"] = v
        return up, ext

    drop = 0.0
    for _ in range(60):
        mx = max(walk_pose(i / 80, drop)[1] for i in range(80))
        if mx <= 0.94:
            break
        drop += 0.25
    info["walk_hip_drop"] = drop
    info["walk_max_ext"] = round(mx, 3)

    walk = []
    n = round(T_WALK * FPS_KEYS)
    for i in range(n + 1):
        walk.append((i / FPS_KEYS, walk_pose((i / n) % 1.0 if i < n else 0.0, drop)[0]))

    # ---- stop: beginnt bei phi = 0 (naher Fuß setzt vorn auf), endet in der Grundhaltung des Idle
    start_pose, _ = walk_pose(0.0, drop)
    v = g.v
    d_n = g.side["n"]
    d_f = g.side["f"]
    xr = lambda tau: v * (tau - tau * tau / (2 * T_STOP))
    An0, _ = g.foot_walk("n", 0.0)
    Af0, psif0 = g.foot_walk("f", 0.5)
    # Ende: naher Fuß bleibt stehen, ferner Fuß setzt 2 px hinter seine Ruhelage
    An_end = An0 - np.array([xr(T_STOP), 0])
    Af_end = np.array([d_f["A"][0] - 2.0 + 0.0, d_f["ground"] - d_f["ah"]])
    # Hüfthöhe im Stand: so hoch, dass beide Beine höchstens 96 % gestreckt sind (auch beim Einatmen)
    idle_hip_y = hip0[1]
    for _ in range(80):
        W = rig.fk({"hip": {"pos": (hip0[0], idle_hip_y - 0.8)}})
        e = max(g.ik(s, W["thigh_" + s][0], A, 0.0, 0.0)[1] for s, A in (("n", An_end), ("f", Af_end)))
        if e <= 0.96:
            break
        idle_hip_y += 0.25
    info["idle_hip_drop"] = round(idle_hip_y - hip0[1], 2)
    ext_log = {"stop": 0.0, "idle": 0.0}
    t_roll = (BETA - 0.5) * T_WALK            # Restzeit des Abrollens
    t_sw = 0.30
    stop = []
    n = round(T_STOP * FPS_KEYS)
    up0 = walk_upper(0.0)
    for i in range(n + 1):
        tau = i / FPS_KEYS
        e = smooth(tau / T_STOP)
        b = bump(tau / T_STOP)
        p = {}
        for k in ("hip", "spine", "neck", "head", "arm_f", "fore_f", "arm_n", "fore_n", "tail"):
            p[k] = {"rot": up0[k]["rot"] * (1 - e)}
        p["spine"]["rot"] += 5.0 * DEG * b
        p["neck"]["rot"] += -1.5 * DEG * b
        p["head"]["rot"] += -3.0 * DEG * b
        p["arm_f"]["rot"] += -10 * DEG * b
        p["tail"]["rot"] += 10 * DEG * math.sin(2 * math.pi * tau / T_STOP)
        p["belly"] = {"scale": (1 + 0.05 * (1 - e) + 0.04 * b, 1 - 0.04 * (1 - e) - 0.03 * b)}
        hy = (hip0[1] + drop + BOB) * (1 - e) + idle_hip_y * e + 0.8 * b
        p["hip"]["pos"] = (hip0[0], hy)
        W = rig.fk(p)
        # naher Fuß: steht (Welt), im Figurenraum mit der Wurzel zurück
        An = An0 - np.array([xr(tau), 0])
        rots, e1 = g.ik("n", W["thigh_n"][0], An, W["hip"][1], 0.0)
        ext_log["stop"] = max(ext_log["stop"], e1)
        for k, val in rots.items():
            p[k] = {"rot": val}
        # ferner Fuß: erst zu Ende abrollen, dann schwingen und flach aufsetzen
        world0 = Af0 + np.array([0.0, 0.0])            # Figurenraum zur Zeit 0 = Weltraum (Wurzel 0)
        if tau <= t_roll:
            ph = 0.5 + tau / T_WALK
            Af, psi = g.foot_walk("f", ph)
            Af = Af - np.array([xr(tau) - v * tau, 0])  # Wurzel bremst bereits: Standfuß im Weltraum halten
        else:
            s_ = min(1.0, (tau - t_roll) / t_sw)
            Ar, _ = g.foot_walk("f", BETA - 1e-6)
            Ar = Ar - np.array([xr(t_roll) - v * t_roll, 0])
            wa = Ar + np.array([xr(t_roll), 0])          # Weltlage am Abheben
            wb = Af_end + np.array([xr(T_STOP), 0])      # Weltlage am Ende
            w = wa + (wb - wa) * smooth(s_)
            w[1] -= LIFT * 0.8 * math.sin(math.pi * s_) ** 0.9
            Af = w - np.array([xr(tau), 0])
            psi = PSI_MAX * (1 - smooth(s_)) - 6 * DEG * math.sin(math.pi * s_)
        rots, e2 = g.ik("f", W["thigh_f"][0], Af, W["hip"][1], psi)
        ext_log["stop"] = max(ext_log["stop"], e2)
        for k, val in rots.items():
            p[k] = {"rot": val}
        stop.append((tau, p))

    # ---- idle: Grundhaltung + Atmen, Blick zur Laterne hinauf, Schwanzwedeln
    idle = []
    n = round(T_IDLE * FPS_KEYS)
    for i in range(n + 1):
        tau = (i / FPS_KEYS) if i < n else 0.0
        br = 0.5 - 0.5 * math.cos(2 * math.pi * 2 * tau / T_IDLE)     # zwei Atemzüge je Schleife
        look = math.sin(math.pi * tau / T_IDLE) ** 2
        p = {
            "hip": {"rot": 0.0, "pos": (hip0[0], idle_hip_y - 0.7 * br)},
            "spine": {"rot": -0.9 * DEG * br - 1.5 * DEG * look},
            "neck": {"rot": -4.5 * DEG * look},
            "head": {"rot": -10.0 * DEG * look + 0.8 * DEG * br},
            "belly": {"scale": (1 + 0.045 * br, 1 + 0.015 * br)},
            "arm_f": {"rot": 2.5 * DEG * math.sin(2 * math.pi * 2 * tau / T_IDLE)},
            "fore_f": {"rot": -1.5 * DEG * br},
            "arm_n": {"rot": -1.5 * DEG * br},
            "fore_n": {"rot": 0.0},
            "tail": {"rot": 5 * DEG * math.sin(2 * math.pi * 3 * tau / T_IDLE) * math.sin(math.pi * tau / T_IDLE)},
        }
        W = rig.fk(p)
        for s, A, psi in (("n", An_end, 0.0), ("f", Af_end, 0.0)):
            rots, e3 = g.ik(s, W["thigh_" + s][0], A, W["hip"][1], psi)
            ext_log["idle"] = max(ext_log["idle"], e3)
            for k, val in rots.items():
                p[k] = {"rot": val}
        idle.append((i / FPS_KEYS, p))

    # Stetigkeit prüfen: Ende stop == Anfang idle, Ende walk == Anfang walk == Anfang stop
    def diff(a, b):
        m = 0.0
        for k in a:
            for f in ("rot",):
                if f in a[k] and k in b and f in b[k]:
                    m = max(m, abs(a[k][f] - b[k][f]))
        return m
    info["seam_walk_loop_deg"] = round(diff(walk[0][1], walk[-1][1]) / DEG, 3)
    info["seam_walk_stop_deg"] = round(diff(walk[0][1], stop[0][1]) / DEG, 3)
    info["seam_stop_idle_deg"] = round(diff(stop[-1][1], idle[0][1]) / DEG, 3)
    info["stop_max_ext"] = round(ext_log["stop"], 3)
    info["idle_max_ext"] = round(ext_log["idle"], 3)
    info["walk_speed"] = round(g.v, 4)
    info["stop_dist"] = round(xr(T_STOP), 4)
    info["foot_n_stop_end_x"] = round(float(An_end[0]), 2)
    info["foot_f_stop_end_x"] = round(float(Af_end[0]), 2)
    return {"walk": (T_WALK, True, walk), "stop": (T_STOP, False, stop), "idle": (T_IDLE, True, idle)}, info
