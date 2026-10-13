#!/usr/bin/env python3
"""Bedienleiste (640×84) im Stil vorgerenderter Rollenspiel-Oberflächen: gegossene Bronze mit Fasen,
geflochtenem Zierband, Eckrosetten, Nieten, eingelassenen Feldern für Porträt, Nachrichtenprotokoll und
drei Steinknöpfe. Alles aus einem Höhenfeld berechnet und beleuchtet (Licht von links oben), ohne KI.

  .venv/bin/python styles/iso-vorgerendert/scripts/build_ui.py

Schreibt assets/ui/bar.png (Echtfarbe; die Palette setzt bake.py) und assets/ui/ui_layout.json
(Rechtecke für Godot: Porträt, Protokoll, Knöpfe).
"""
import json
import pathlib

import numpy as np
from PIL import Image

STYLE = pathlib.Path(__file__).resolve().parent.parent
OUT = STYLE / "assets" / "ui"
W, H = 640, 84
SS = 4                      # Überabtastung, danach Box-Filter

# Felder (Zielpixel, x0, y0, x1, y1 exklusiv)
PORTRAIT = (11, 12, 67, 78)          # 56×66
LOG = (80, 12, 404, 78)
BUTTONS = [(418, 12 + 23 * i, 629, 12 + 23 * i + 20) for i in range(3)]

rng = np.random.default_rng(1998)


def fbm(h, w, scale, octaves=5, seed=0):
    r = np.random.default_rng(seed)
    out = np.zeros((h, w))
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        s = max(1, int(scale / (2 ** o)))
        gh, gw = h // s + 2, w // s + 2
        g = r.random((gh, gw))
        yy = np.linspace(0, gh - 1.001, h)
        xx = np.linspace(0, gw - 1.001, w)
        y0 = yy.astype(int)
        x0 = xx.astype(int)
        fy = (yy - y0)[:, None]
        fx = (xx - x0)[None, :]
        fy = fy * fy * (3 - 2 * fy)
        fx = fx * fx * (3 - 2 * fx)
        a = g[y0][:, x0]
        b = g[y0][:, x0 + 1]
        c = g[y0 + 1][:, x0]
        d = g[y0 + 1][:, x0 + 1]
        out += amp * ((a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy)
        tot += amp
        amp *= 0.55
    return out / tot


def rect_bevel(Hf, mask_mat, rect, depth, bevel, mat_id, inset=True):
    """Rechteck mit Fase: inset=True senkt ein (Feld), sonst hebt an (Knopf)."""
    x0, y0, x1, y1 = [v * SS for v in rect]
    b = bevel * SS
    yy, xx = np.mgrid[0:Hf.shape[0], 0:Hf.shape[1]]
    dx = np.minimum(xx - x0, x1 - 1 - xx)
    dy = np.minimum(yy - y0, y1 - 1 - yy)
    dist = np.minimum(dx, dy)
    inside = dist >= 0
    ramp = np.clip(dist / max(b, 1), 0, 1)
    if inset:
        Hf[inside] -= depth * ramp[inside]
    else:
        Hf[inside] += depth * ramp[inside]
    mask_mat[inside & (ramp >= 1)] = mat_id
    return inside, ramp


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    h, w = H * SS, W * SS
    Hf = np.zeros((h, w))
    mat = np.zeros((h, w), np.int32)          # 0 Bronze, 1 Feld (dunkles Glas), 2 Stein (Knopf), 3 Porträtgrund
    yy, xx = np.mgrid[0:h, 0:w] / SS          # Zielpixel-Koordinaten

    # Grundplatte: leicht gewölbt, gehämmert
    Hf += 1.2 * fbm(h, w, 40 * SS, 5, 1) + 0.25 * fbm(h, w, 6 * SS, 3, 2)
    # Außenrahmen: Wulst rundum (3 px), Fase zum Rand
    edge = np.minimum.reduce([xx, W - xx, yy, H - yy])
    Hf += np.where(edge < 4, 4.0 * np.sin(np.clip(edge / 4, 0, 1) * np.pi) , 0)
    # Zierband oben: zwei verflochtene Stränge (Kordel) zwischen y 1..6
    band_y = 4.5
    ph = xx / 11.0 * 2 * np.pi
    for k in (0, 1):
        cy = band_y + 2.4 * np.sin(ph + k * np.pi)
        r = np.abs(yy - cy)
        over = (np.sin(ph + k * np.pi + np.pi / 2) > 0)
        strand = np.clip(1 - r / 1.6, 0, 1)
        lift = np.where(over, 2.6, 1.6) * np.sqrt(strand)
        Hf = np.maximum(Hf, np.where(strand > 0, 2.0 + lift, Hf))
    # gleiches Band unten
    for k in (0, 1):
        cy = (H - 3.0) + 1.7 * np.sin(ph + k * np.pi)
        r = np.abs(yy - cy)
        over = (np.sin(ph + k * np.pi + np.pi / 2) > 0)
        strand = np.clip(1 - r / 1.2, 0, 1)
        lift = np.where(over, 2.6, 1.6) * np.sqrt(strand)
        Hf = np.maximum(Hf, np.where(strand > 0, 2.0 + lift, Hf))

    # Felder einsenken
    rect_bevel(Hf, mat, (PORTRAIT[0] - 3, PORTRAIT[1] - 3, PORTRAIT[2] + 3, PORTRAIT[3] + 3), 2.0, 2, 0)
    rect_bevel(Hf, mat, PORTRAIT, 4.0, 2, 3)
    rect_bevel(Hf, mat, (LOG[0] - 3, LOG[1] - 3, LOG[2] + 3, LOG[3] + 3), 2.0, 2, 0)
    rect_bevel(Hf, mat, LOG, 4.0, 2, 1)
    for b in BUTTONS:
        rect_bevel(Hf, mat, (b[0] - 2, b[1] - 2, b[2] + 2, b[3] + 2), 3.0, 1, 0)
        rect_bevel(Hf, mat, b, 3.5, 3, 2, inset=False)
    # Trennsteg zwischen Feldern: senkrechte Rippen
    for x in (73, 411):
        rib = np.clip(1 - np.abs(xx - x) / 2.0, 0, 1)
        sel = (yy > 8) & (yy < H - 8)
        Hf += np.where(sel, 2.5 * np.sqrt(rib), 0)
    # Eckrosetten: vierblättrig, mit Knopf
    for cx, cy in ((5, 5), (W - 5, 5), (5, H - 5), (W - 5, H - 5), (73, 5), (73, H - 4), (411, 5), (411, H - 4)):
        dx, dy = xx - cx, yy - cy
        rr = np.hypot(dx, dy)
        ang = np.arctan2(dy, dx)
        petal = np.clip(1 - rr / (5.5 * (0.6 + 0.4 * np.abs(np.cos(2 * ang)))), 0, 1)
        Hf = np.maximum(Hf, 3.0 + 3.0 * np.sqrt(petal) * (petal > 0) - (petal <= 0) * 99)
        knob = np.clip(1 - rr / 1.6, 0, 1)
        Hf = np.maximum(Hf, np.where(knob > 0, 6.5 + 1.5 * np.sqrt(knob), Hf))
    # Nieten entlang der Felder
    for (x0, y0, x1, y1) in (LOG,):
        for x in range(x0 + 10, x1 - 4, 40):
            for y in (y1 + 3.0,):
                rr = np.hypot(xx - x, yy - y)
                knob = np.clip(1 - rr / 1.3, 0, 1)
                Hf = np.maximum(Hf, np.where(knob > 0, 3.5 + 1.2 * np.sqrt(knob), Hf))

    # Medaillons auf den Trennstegen: Raute mit eingesetztem roten Stein (Material 4)
    for cx in (73, 411):
        cy = H / 2
        dd = np.abs(xx - cx) + np.abs(yy - cy) * 0.8
        dia = np.clip(1 - dd / 7.5, 0, 1)
        Hf = np.maximum(Hf, np.where(dia > 0, 3.0 + 4.0 * np.sqrt(dia), Hf))
        gem = np.hypot(xx - cx, (yy - cy) * 0.9)
        gm = np.clip(1 - gem / 2.6, 0, 1)
        Hf = np.where(gm > 0, 6.5 + 2.0 * np.sqrt(gm), Hf)
        mat[gm > 0] = 4
    # Normalen und Licht
    gy, gx = np.gradient(Hf * 0.9)
    n = np.dstack([-gx, -gy, np.ones_like(Hf)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    L = np.array([-0.55, -0.6, 0.58])
    L /= np.linalg.norm(L)
    diff = np.clip((n * L).sum(2), 0, 1)
    Hh = np.array([L[0], L[1], L[2] + 1.0])
    Hh /= np.linalg.norm(Hh)
    spec = np.clip((n * Hh).sum(2), 0, 1) ** 24
    cav = np.clip(0.5 + 0.35 * (Hf - np.array(Image.fromarray(Hf.astype(np.float32)).resize((w // 8, h // 8), Image.BILINEAR)
                                                .resize((w, h), Image.BILINEAR))), 0.2, 1.0)

    tex = fbm(h, w, 3 * SS, 4, 7)
    patina = fbm(h, w, 25 * SS, 4, 9)
    bronze = np.array([0.55, 0.38, 0.17])
    bronze_dark = np.array([0.16, 0.11, 0.06])
    verdigris = np.array([0.20, 0.30, 0.24])
    base = bronze[None, None] * (0.75 + 0.5 * tex[..., None])
    pv = np.clip((patina - 0.55) * 4, 0, 1)[..., None]
    base = base * (1 - 0.55 * pv) + verdigris * 0.55 * pv
    col = base * (0.25 + 0.95 * diff[..., None]) * cav[..., None] + spec[..., None] * np.array([1.0, 0.85, 0.55]) * 0.55
    # Felder
    glass = np.array([0.035, 0.03, 0.03]) * (0.8 + 0.4 * tex[..., None])
    col = np.where((mat == 1)[..., None], glass + 0.02 * diff[..., None], col)
    stone = np.array([0.30, 0.28, 0.25]) * (0.7 + 0.6 * fbm(h, w, 2 * SS, 3, 11)[..., None])
    stone_col = stone * (0.3 + 0.9 * diff[..., None]) * cav[..., None]
    col = np.where((mat == 2)[..., None], stone_col, col)
    col = np.where((mat == 3)[..., None], np.array([0.02, 0.02, 0.025]), col)
    gemc = np.array([0.55, 0.05, 0.04]) * (0.35 + 1.0 * diff[..., None]) + spec[..., None] * 0.9
    col = np.where((mat == 4)[..., None], gemc, col)
    col = np.clip(col, 0, 1)
    # Box-Filter auf Zielauflösung (linear), dann sRGB
    lin = col ** 2.2
    lin = lin.reshape(H, SS, W, SS, 3).mean((1, 3))
    srgb = lin ** (1 / 2.2)
    Image.fromarray((np.clip(srgb, 0, 1) * 255 + 0.5).astype(np.uint8)).save(OUT / "bar.png")
    json.dump({"size": [W, H], "portrait": PORTRAIT, "log": LOG, "buttons": BUTTONS},
              open(OUT / "ui_layout.json", "w"), indent=1)
    print("ok", OUT / "bar.png")


if __name__ == "__main__":
    main()
