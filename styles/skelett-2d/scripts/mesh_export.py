"""Texturen, Dreiecksgitter und Knochengewichte je Teil (Teil von build_rig.py)."""
import json, math, pathlib

import numpy as np
from PIL import Image

import rig_def as R
import build_rig as B
import bake_anims
import tscn_writer

GRID = {"body": 8, "arm_n": 6, "arm_f": 6, "leg_n": 5, "leg_f": 5, "scarf_b": 6, "scarf_f": 6}
PAD = 3


def ss(e0, e1, x):
    """smoothstep, auch mit e0 > e1 (fallend)."""
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def chain(ts):
    """Teilung der Eins aus Übergangswerten a_i (0..1): w0=1-a0, w1=a0(1-a1), …"""
    ws, acc = [], np.ones_like(ts[0])
    for a in ts:
        ws.append(acc * (1 - a))
        acc = acc * a
    ws.append(acc)
    return ws


def weights_for(part, P, bones):
    """P: (n,2) Gitterpunkte im Körperraum. Gibt {bone: weights} zurück."""
    x, y = P[:, 0], P[:, 1]
    bp = {k: v["pos"] for k, v in bones.items()}
    W = {}
    if part == "body":
        yb = 226 + (x - 650) * 0.16                  # Oberkante der Schalwicklung, nach vorn abfallend
        a_head = ss(yb - 18, yb + 26, y)             # Kopf -> Hals
        a_neck = ss(318, 372, y)                     # Hals -> Rumpf
        a_spine = ss(515, 585, y)                    # Rumpf -> Hüfte
        w_head, w_neck, w_spine, w_hip = chain([a_head, a_neck, a_spine])
        # Bauch (Atmen): weicher Kreis vorn unten
        d = np.hypot(x - 915, y - 585)
        w_belly = 0.85 * (1 - ss(55, 125, d)) * ss(330, 420, y)
        # Schwanz: hinten unten
        dt = np.hypot(x - 628, y - 655)
        w_tail = (1 - ss(28, 62, dt)) * (x < 690)
        # Tasche: Kasten mit weichem Rand
        w_sat = ss(560, 575, x) * (1 - ss(690, 704, x)) * ss(496, 512, y) * (1 - ss(600, 612, y))
        rest = (1 - w_belly) * (1 - w_tail) * (1 - w_sat)
        W = {"head": w_head * rest, "neck": w_neck * rest, "spine": w_spine * rest, "hip": w_hip * rest,
             "belly": w_belly * (1 - w_tail) * (1 - w_sat), "tail": w_tail * (1 - w_sat), "satchel": w_sat}
    elif part in ("leg_n", "leg_f"):
        s = part[-1]
        H, K, A = bp["thigh_" + s], bp["shin_" + s], bp["foot_" + s]
        a_knee = ss(K[1] - R.BLEND["knee"], K[1] + R.BLEND["knee"], y)
        a_ank = ss(A[1] - R.BLEND["ankle"], A[1] + R.BLEND["ankle"], y)
        w_th, w_sh, w_ft = chain([a_knee, a_ank])
        w_hip = 0.5 * ss(H[1] - 20, H[1] - 20 - R.BLEND["hip_top"], y)
        k = 1 - w_hip
        W = {"hip": w_hip, "thigh_" + s: w_th * k, "shin_" + s: w_sh * k, "foot_" + s: w_ft * k}
    elif part in ("arm_n", "arm_f"):
        s = part[-1]
        Sh, E = bp["arm_" + s], bp["fore_" + s]
        a_el = ss(E[1] - R.BLEND["elbow"], E[1] + R.BLEND["elbow"], y)
        if s == "n":   # Paket gehört ganz zum Unterarm
            sx = B.sheet_to_body("arm_n", (1192, 0))[0]
            a_el = np.maximum(a_el, ss(sx, sx + 22, x))
        w_up, w_fo = chain([a_el])
        w_sp = 0.6 * ss(Sh[1] - 8, Sh[1] - 8 - R.BLEND["shoulder"], y)
        k = 1 - w_sp
        W = {"spine": w_sp, "arm_" + s: w_up * k, "fore_" + s: w_fo * k}
    elif part in ("scarf_b", "scarf_f"):
        c = part[-1]
        top, tip = bp[f"scarf_{c}1"], bones[f"scarf_{c}3"]["tip"]
        ax = (tip - top) / np.linalg.norm(tip - top)
        t = (P - top) @ ax
        t1 = (bp[f"scarf_{c}2"] - top) @ ax
        t2 = (bp[f"scarf_{c}3"] - top) @ ax
        bl = R.BLEND["scarf"]
        a0 = ss(-12, 30, t)
        a1 = ss(t1 - bl, t1 + bl, t)
        a2 = ss(t2 - bl, t2 + bl, t)
        w = chain([a0, a1, a2])
        W = {"neck": w[0], f"scarf_{c}1": w[1], f"scarf_{c}2": w[2], f"scarf_{c}3": w[3]}
    tot = sum(W.values())
    return {k: (v / tot).astype(np.float32) for k, v in W.items()}


def build_part(name, part, bones):
    p = R.PARTS[name]
    rgba = part["rgba"]
    h, w = rgba.shape[:2]
    tw, th = max(1, round(w * R.S)), max(1, round(h * R.S))
    tex = B.premul_resize(rgba, (tw, th))
    tex = np.pad(tex, ((PAD, PAD), (PAD, PAD), (0, 0)))
    # Maßstab exakt: Texturpixel u -> Blatt x = origin + (u - PAD) * (w / tw)
    fx, fy = w / tw, h / th
    TH, TW = tex.shape[:2]
    alpha = tex[..., 3] > 2
    C = GRID[name]
    nx, ny = math.ceil(TW / C), math.ceil(TH / C)
    keep = np.zeros((ny, nx), bool)
    for j in range(ny):
        for i in range(nx):
            x0, y0 = max(i * C - 1, 0), max(j * C - 1, 0)
            keep[j, i] = alpha[y0:(j + 1) * C + 1, x0:(i + 1) * C + 1].any()
    vid = -np.ones((ny + 1, nx + 1), int)
    uv, tris = [], []
    for j in range(ny):
        for i in range(nx):
            if not keep[j, i]:
                continue
            ids = []
            for (jj, ii) in ((j, i), (j, i + 1), (j + 1, i + 1), (j + 1, i)):
                if vid[jj, ii] < 0:
                    vid[jj, ii] = len(uv)
                    uv.append((min(ii * C, TW), min(jj * C, TH)))
                ids.append(int(vid[jj, ii]))
            a, b, c, d = ids
            # Diagonale abwechselnd, damit die Verformung nicht in eine Richtung kippt
            if (i + j) % 2 == 0:
                tris += [(a, b, c), (a, c, d)]
            else:
                tris += [(a, b, d), (b, c, d)]
    uv = np.array(uv, float)
    sheet = np.stack([part["origin"][0] + (uv[:, 0] - PAD) * fx, part["origin"][1] + (uv[:, 1] - PAD) * fy], 1)
    body = np.array([B.sheet_to_body(name, s) for s in sheet])
    rig = B.body_to_rig(body)
    W = weights_for(name, body, bones)
    return {"tex": tex, "uv": uv, "pos": rig, "tris": tris, "weights": W, "draw": p["draw"]}


def export(parts, bones):
    ART.mkdir(parents=True, exist_ok=True)
    meshes = {}
    for name in R.PARTS:
        m = build_part(name, parts[name], bones)
        Image.fromarray(m["tex"], "RGBA").save(ART / f"badger_{name}.png")
        Image.fromarray(m["tex"], "RGBA").save(B.HERE / "assets" / f"badger_{name}.png")
        meshes[name] = m
        print(f"{name}: Textur {m['tex'].shape[1]}x{m['tex'].shape[0]}, {len(m['uv'])} Punkte, {len(m['tris'])} Dreiecke, "
              f"Knochen {sorted(m['weights'])}")
    rig_bones = {}
    for name, b in bones.items():
        rig_bones[name] = {"parent": b["parent"], "pos": B.body_to_rig(b["pos"]).tolist(),
                           "tip": B.body_to_rig(b["tip"]).tolist()}
    for s, (part, sy) in R.SOLE_SHEET.items():
        anc = R.PARTS[part]
        rig_bones["foot_" + s]["sole"] = float(B.body_to_rig(B.sheet_to_body(part, (anc["anchor_sheet"][0], sy)))[1])
        rp = R.ROLL_PIVOT[s]
        rig_bones["foot_" + s]["roll"] = B.body_to_rig(B.sheet_to_body(rp[0], rp[1])).tolist()
    anims, info = bake_anims.bake(rig_bones)
    tscn_writer.write(B.HERE / "demo" / "badger.tscn", rig_bones, meshes, anims,
                      {k: info[k] for k in ("walk_speed", "walk_cycle", "stop_time", "stop_dist", "idle_time")})
    summary = {
        "scale": R.S, "origin_body": R.ORIGIN, "height_px": round(float(-B.body_to_rig((0, 40))[1]), 1),
        "bones": {k: {"parent": v["parent"], "pos": [round(c, 2) for c in v["pos"]]} for k, v in rig_bones.items()},
        "parts": {k: {"verts": len(m["uv"]), "tris": len(m["tris"]), "bones": sorted(m["weights"]),
                      "texture": f"assets/badger_{k}.png"} for k, m in meshes.items()},
        "anim": info,
    }
    (B.HERE / "assets" / "rig.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    print(json.dumps(info, ensure_ascii=False))


ART = B.ART
