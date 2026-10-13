#!/usr/bin/env python3
"""KI-Sprite-Sheets zerlegen, messen, korrigieren und als Godot-SpriteFrames schreiben.

    .venv/bin/python styles/ki-spritesheet/scripts/build_sprites.py

Eingaben: assets/raw/{walk,idle,jump,wave,wave2}.png (Codex, echter Alphakanal).
Ausgaben:
  assets/sheets.json            alle Messwerte (Lage, Kopfanker, Kopfmaßstab, Fußläufe, Doppelte, Flimmern)
  demo/art/badger_<anim>.png    korrigierte Streifen (walk, idle, jump, wave), gleiche Zellgröße je Animation
  demo/art/raw_<anim>.png       „roh“: unverändert mit tools/sprites.py slice zerlegt (Vergleich im Panel)
  demo/art/thumbs_<anim>.png    Vorschaubilder aller Blattbilder für das Panel
  demo/art/anim.json            Anker, Vorschub, Fußpunkte, Bildfolgen und Status je Blattbild
  demo/badger_frames.tres       SpriteFrames (AtlasTexture je Bild, Dauer je Bild)
  demo/raw_frames.tres          SpriteFrames der rohen Fassung
  assets/sprites/               Kopien der Streifen und von anim.json
  assets/sheets/<blatt>.png     KI-Blätter auf 50 % verkleinert (Dokumentation; Originale in assets/raw/)

Korrekturen (Gegenmittel), je Blatt:
  walk  8 KI-Bilder, aber nur 4 verschiedene Posen (1≈5, 2≈6, 3≈7, 4≈8): Bilder 1–4, 6 Bilder/s. Waagerecht am
        Kopf ausgerichtet, senkrecht an der tiefsten Zeile; Vorschub je Bildwechsel aus dem Standfuß (Fußtabelle).
  idle  6 ganze KI-Bilder flimmern (Kopfgröße ±2 %, Arm und Paket wandern): ein Körper (Bild 1) + Lidteil aus
        Bild 4 (am Kopf eingepasst) + Atmen als Verschiebung des Oberkörpers um 0–2 px mit gedehntem Band.
        SpriteFrames „idle“ ist nur die Atemschleife (3 s), „blink“ das Lid je Atemstufe (main.gd setzt es ein).
  jump  Blatt ist 19 % größer gemalt als das Laufblatt: auf Kopfgröße normiert. Die vom Modell gemalte
        Sprunghöhe (trotz Prompt) wird übernommen, waagerecht Zehen beim Absprung fest, kleiner Satz nach vorn.
  wave  Bild 3 und 5 wechseln den Arm (Paket springt auf die andere Seite): aussortiert; Bilder 1, 2, 4, 6 an
        den Füßen ausgerichtet, Maßstab über die Standhöhe (Dreiviertelansicht, Kopfvergleich nicht möglich).
Danach: Stehen und Winken unterpixelgenau auf eine Sohlenkante (sole_edge), alle Zellen mit 2-px-Außenkontur in der
Konturfarbe des Hintergrunds (add_outline), Anker 2 px tiefer.
"""
import json, pathlib, shutil, subprocess, sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import kss_sheet as K  # noqa: E402

E = pathlib.Path(__file__).resolve().parents[1]
ROOT = E.parents[1]
RAW = E / "assets" / "raw"
ART = E / "demo" / "art"
TIP = 0.33            # Schnauzenspitze im oberen Drittel suchen
STAND_H = 190.0       # Standhöhe des Dachses im Bild (px), Idle-Bild 1
FPS = {"walk": 6, "idle": 6, "jump": 10, "wave": 6, "blink": 6}
RAW_FPS = {"walk": 10, "idle": 6, "jump": 10, "wave": 6}
RAW_SLICE_H = 120     # sprites.py slice --height (so würde man es naiv machen)
OUTLINE_R = 2         # Außenkontur in Bildpixeln (Hintergrund: 2–3 px dunkelbraune Konturen)
SOLE_ABOVE = 1.0      # Sohle (Deckungskante, sole_edge) 1 px über der Ankerzeile: unterste kräftige Zeile = AY - 1
GROUND_ALPHA = 128    # Bodenzeile = unterste Zeile mit kräftigem Alpha (schwache Kantenpixel zählen nicht)

# Fußtabelle des Laufblatts (abgelesen an 3-fach vergrößerten Bodenläufen, siehe assets/check/walk_feet.png):
# je Wechsel i -> i+1 welcher Bodenlauf in welchem Bild stehen bleibt und an welchem Ende (Ferse links, Zehe rechts).
# (Bild, Laufindex, Ende) -> (Bild, Laufindex, Ende); Laufindex von links nach rechts.
WALK_FEET = [
    ((0, 1, "heel"), (1, 0, "heel")),   # 1->2 nahes Bein: Ferse setzt auf, Fuß wird flach
    ((1, 0, "toe"), (2, 0, "toe")),     # 2->3 nahes Bein rollt über die Zehen ab
    ((2, 1, "heel"), (3, 0, "heel")),   # 3->4 fernes Bein: Ferse setzt auf
    ((3, 0, "toe"), (0, 0, "toe")),     # 4->1 fernes Bein rollt ab
]


def pm_resize(img, size, box):
    """Vormultipliziert mit Lanczos skalieren; box in Quellkoordinaten (Gleitkomma erlaubt)."""
    im = Image.fromarray(img, "RGBA").convert("RGBa")
    out = im.resize(size, Image.LANCZOS, box=box).convert("RGBA")
    a = np.asarray(out).copy()
    a[..., 3] = np.where(a[..., 3] < 6, 0, a[..., 3])
    a[a[..., 3] == 0, :3] = 0
    return a


def place(img, k, ax_s, ay_s, AX, AY, CW, CH):
    """Quellbild so skalieren (k) und verschieben, dass der Quellpunkt (ax_s, ay_s) auf Zellpunkt (AX, AY) liegt."""
    pad = int(np.ceil(max(CW, CH) / k)) + 8
    src = np.pad(img, ((pad, pad), (pad, pad), (0, 0)))
    sx0 = ax_s + pad - AX / k
    sy0 = ay_s + pad - AY / k
    return pm_resize(src, (CW, CH), (sx0, sy0, sx0 + CW / k, sy0 + CH / k))


def toe_x(cell, ay, rows=3):
    """Rechtes Ende der Bodenberührung (Zehen bei Blick nach rechts) in den untersten `rows` Zeilen über ay."""
    sub = cell[max(0, ay - rows):ay, :, 3] > 128
    xs = np.flatnonzero(sub.any(0))
    return float(xs[-1] + 1) if xs.size else None


def body_x(cell, ay, rows=24):
    """Mitte der deckenden Spalten in den untersten `rows` Zeilen (beide Füße, auch in der Dreiviertelansicht)."""
    sub = cell[max(0, ay - rows):ay, :, 3] > 128
    xs = np.flatnonzero(sub.any(0))
    return float((xs[0] + xs[-1] + 1) / 2) if xs.size else None


def lowest_strong_row(cell, thr=GROUND_ALPHA):
    ys = np.flatnonzero((cell[..., 3] > thr).any(1))
    return int(ys[-1]) if ys.size else None


def sole_edge(cell, ay, band=8):
    """Unterkante der Sohle unterpixelgenau (Bildpixel), für stehende Figuren (beide Füße flach): in den Spalten,
    die oben im Band (ay - band) deckend sind, Alpha im Band aufsummieren (Deckung = Länge in Zeilen) und das
    75. Perzentil nehmen."""
    a = cell[..., 3].astype(np.float64) / 255.0
    sub = a[ay - band:ay + 4]
    solid = sub[0] > 0.9
    if solid.sum() < 3:
        return float(lowest_strong_row(cell) + 1)
    cov = sub[:, solid].sum(0)
    return float(ay - band + np.percentile(cov, 75))


def bg_contour_color():
    """Konturfarbe des Hintergrunds: Median der sehr dunklen Pixel (hellster Kanal < 50, rund 4 % des Bildes)."""
    bg = np.asarray(Image.open(E / "assets/bg.png").convert("RGB")).astype(int)
    m = bg.max(-1) < 50
    return np.median(bg[m], 0).astype(np.float64)


def add_outline(cell, col, r=OUTLINE_R):
    """Außenkontur: Alpha mit einer Kreisscheibe (Radius r) dilatieren, in der Konturfarbe unter die Zelle legen.
    Arbeitet auf der fertig abgetasteten Zelle (Bildpixel), es wird nichts neu abgetastet."""
    a = cell[..., 3].astype(np.float64) / 255.0
    h, w = a.shape
    pad = np.pad(a, r)
    d = np.zeros_like(a)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r + 1:      # r = 2: 5×5 ohne Ecken
                d = np.maximum(d, pad[r + dy:r + dy + h, r + dx:r + dx + w])
    rgb = cell[..., :3].astype(np.float64)
    out_a = a + d * (1 - a)
    pre = rgb * a[..., None] + col[None, None] * (d * (1 - a))[..., None]
    out = np.zeros_like(cell)
    nz = out_a > 0
    out[..., :3][nz] = np.clip(np.round(pre[nz] / out_a[nz][:, None]), 0, 255).astype(np.uint8)
    out[..., 3] = np.clip(np.round(out_a * 255), 0, 255).astype(np.uint8)
    return out


def runs_at_bottom(mask, tol=3):
    ys = np.flatnonzero(mask.any(1))
    base = int(ys[-1])
    return base, K.feet(mask, band=tol)[1]


def measure_sheet(name, n, walk0):
    fr = K.split_frames(RAW / f"{name}.png", n)
    side = name in ("walk", "idle", "jump")
    anchors = K.head_anchors(fr, 0, tip_upper=TIP) if side else [(0, 0, 0)] * n
    out = []
    for i, f in enumerate(fr):
        base, runs = runs_at_bottom(f["mask"])
        hs = K.head_scale(walk0, f, lo=0.70, hi=1.08, step=0.005, tip_upper=TIP) if side else (None, None)
        out.append({
            "frame": i + 1, "x0": f["x0"], "y0": f["y0"], "w": int(f["mask"].shape[1]),
            "h": int(f["mask"].shape[0]), "bottom": base + f["y0"],
            "feet": [[a + f["x0"], b + f["x0"]] for a, b in runs],
            "head": [anchors[i][0] + f["x0"], anchors[i][1] + f["y0"]] if side else None,
            "head_ncc": anchors[i][2] if side else None,
            "head_scale": hs[0] if hs[0] is None else float(hs[0]), "head_scale_ncc": round(hs[1], 3) if hs[1] is not None else None,
            "area": int(f["mask"].sum()),
        })
    return fr, out


def pairwise_leg_diff(fr, anchors):
    """Abweichung der Beinmasken (XOR/OR) aller Bildpaare, am Kopf ausgerichtet: findet doppelte Posen."""
    can = []
    for f, a in zip(fr, anchors):
        c = np.zeros((1100, 600), bool)
        ox, oy = 400 - (a[0] - f["x0"]), 300 - (a[1] - f["y0"])
        h, w = f["mask"].shape
        c[oy:oy + h, ox:ox + w] = f["mask"]
        can.append(c[300 + 110:])
    n = len(fr)
    return [[round(float((can[i] ^ can[j]).sum() / max(1, (can[i] | can[j]).sum())), 3) for j in range(n)]
            for i in range(n)]


def flicker(frames_rgba, ignore=None):
    """Anteil der Figurpixel, die sich zwischen aufeinanderfolgenden Bildern deutlich ändern (max. Kanal > 40)."""
    vals = []
    for a, b in zip(frames_rgba, frames_rgba[1:] + frames_rgba[:1]):
        m = (a[..., 3] > 128) | (b[..., 3] > 128)
        if ignore is not None:
            m &= ~ignore
        d = np.abs(a.astype(int) - b.astype(int))
        ch = (d[..., :3].max(-1) > 40) | (d[..., 3] > 128)
        vals.append(round(float((ch & m).sum() / max(1, m.sum())), 3))
    return vals


# Kostümteile als Bezugsfarben (grob aus dem Referenzblatt), für den Farbvergleich zwischen den Blättern
MATERIALS = {"schal": (165, 35, 35), "weste": (75, 90, 45), "muetze": (80, 95, 50), "hemd": (235, 225, 200),
             "fell": (70, 68, 72), "bauch": (240, 235, 220), "tasche": (120, 65, 35), "paket": (200, 160, 110)}


def oklab(rgb):
    c = np.clip(rgb, 0, 255) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]])
    m2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]])
    return np.cbrt(c @ m1.T) @ m2.T


def material_colors(img):
    """Mittlere Oklab-Farbe und Flächenanteil je Kostümteil (Pixel nahe der Bezugsfarbe, deckend)."""
    m = img[..., 3] > 200
    lab = oklab(img[..., :3][m].astype(float))
    names = list(MATERIALS)
    ref = oklab(np.array([MATERIALS[n] for n in names], float))
    d = ((lab[:, None, :] - ref[None]) ** 2).sum(-1)
    k, ok = d.argmin(1), d.min(1) < 0.012
    out = {}
    for i, n in enumerate(names):
        sel = (k == i) & ok
        out[n] = {"share": round(float(sel.mean()), 3),
                  "oklab": [round(float(v), 3) for v in lab[sel].mean(0)] if sel.any() else None}
    return out


def main():
    ART.mkdir(parents=True, exist_ok=True)
    (E / "assets" / "check").mkdir(parents=True, exist_ok=True)
    W, wm = None, None
    W = K.split_frames(RAW / "walk.png", 8)
    data = {}
    frames = {}
    for name, n in (("walk", 8), ("idle", 6), ("jump", 6), ("wave", 6), ("wave2", 6)):
        fr, meas = measure_sheet(name, n, W[0])
        frames[name] = fr
        data[name] = {"frames": meas}
        print(name, "Kopfmaßstab", [m["head_scale"] for m in meas], "Unterkante", [m["bottom"] for m in meas])

    # ---------------- Farben je Kostümteil (Bild 1 jedes Blatts und das Referenzblatt)
    master = np.asarray(Image.open(ROOT / "shared/badger/master_sheet_alpha.png").convert("RGBA"))
    cols = {"master_sheet": material_colors(master)}
    for name in ("walk", "idle", "jump", "wave", "wave2"):
        cols[name] = material_colors(frames[name][0]["img"])
    base = cols["walk"]
    dev = {"dL": 0.0, "dab": 0.0}
    for name in ("idle", "jump", "wave", "wave2"):
        for mat, v in cols[name].items():
            if v["oklab"] and base[mat]["oklab"]:
                dev["dL"] = max(dev["dL"], abs(v["oklab"][0] - base[mat]["oklab"][0]))
                dev["dab"] = max(dev["dab"], abs(v["oklab"][1] - base[mat]["oklab"][1]),
                                 abs(v["oklab"][2] - base[mat]["oklab"][2]))
    data["colors"] = {"by_sheet_frame1": cols, "max_dev_vs_walk": {k_: round(v, 3) for k_, v in dev.items()}}
    print("Farbabweichung gegen das Laufblatt (Oklab, Bild 1 je Blatt):", data["colors"]["max_dev_vs_walk"])

    # ---------------- Maßstab je Blatt
    def med(name, idx=None):
        v = [m["head_scale"] for m in data[name]["frames"] if m["head_scale_ncc"] and m["head_scale_ncc"] > 0.6]
        if idx is not None:
            v = [data[name]["frames"][i]["head_scale"] for i in idx]
        return float(np.median(v))
    s = {"walk": med("walk"), "idle": med("idle"), "jump": med("jump")}
    stand_idle = data["idle"]["frames"][0]["h"] * s["idle"]
    s["wave"] = stand_idle / data["wave2"]["frames"][0]["h"]
    G = STAND_H / stand_idle
    k = {a: G * s[a] for a in s}
    data["scale"] = {"sheet_vs_walk": {a: round(v, 4) for a, v in s.items()}, "display_per_walk_px": round(G, 4),
                     "display_per_sheet_px": {a: round(v, 4) for a, v in k.items()},
                     "note": "Kopfmaßstab: Faktor, mit dem das Blatt skaliert werden muss, damit der Kopf dem Kopf "
                             "von Laufbild 1 gleicht (NCC über den Kopfausschnitt, Schritt 0,005). Winkblatt: über die "
                             "Standhöhe gegen Idle-Bild 1 (Dreiviertelansicht)."}
    print("Maßstab", data["scale"])

    # ---------------- Doppelte Posen im Laufblatt
    wa = [(m["head"][0], m["head"][1]) for m in data["walk"]["frames"]]
    data["walk"]["leg_diff"] = pairwise_leg_diff(W, wa)

    anims = {}

    # ---------------- walk: Bilder 1-4, Kopfanker waagerecht, Unterkante senkrecht
    use = [0, 1, 2, 3]
    kw = k["walk"]
    meas = data["walk"]["frames"]
    AX, AY, CW, CH = 200, 380, 400, 400
    cells = []
    kws = []
    for i in use:
        f, m = W[i], meas[i]
        hx = m["head"][0] - f["x0"]
        bot = m["bottom"] - f["y0"] + 1          # Unterkante der tiefsten Zeile
        kf = G * m["head_scale"]                  # Kopfgröße je Bild angleichen (KI malt ±2 % verschieden)
        kws.append(kf)
        cells.append(place(f["img"], kf, hx, bot, AX, AY, CW, CH))
    # Fußtabelle -> Vorschub (Quell-px am Kopf ausgerichtet -> Bild-px)

    def foot_rel(fi, ri, end):
        m = meas[fi]
        r = m["feet"][ri]
        x = r[0] if end == "heel" else r[1]
        return x - m["head"][0]
    adv_src = [foot_rel(*a) - foot_rel(*b) for a, b in WALK_FEET]
    adv = [round(foot_rel(*a) * kws[use.index(a[0])] - foot_rel(*b) * kws[use.index(b[0])], 2) for a, b in WALK_FEET]
    # Fußpunkt (Zellkoordinate) je Bild: Mitte der Bodenläufe
    foot_x = []
    for i in use:
        m = meas[i]
        xs = [(r[0] + r[1]) / 2 for r in m["feet"]]
        stand = {0: 1, 1: 0, 2: 1, 3: 0}[i]   # Standfuß laut Fußtabelle
        foot_x.append(round(AX + ((m["feet"][stand][0] + m["feet"][stand][1]) / 2 - m["head"][0]) * kws[i], 2))
    anims["walk"] = {"cells": cells, "anchor": [AX, AY], "size": [CW, CH], "src": ["walk", [i + 1 for i in use]],
                     "seq": [[0, 1], [1, 1], [2, 1], [3, 1]], "advance": adv, "advance_src": adv_src,
                     "stand_foot_x": foot_x}
    print("walk Vorschub (Bild-px)", adv, "Summe", round(sum(adv), 1))

    # ---------------- idle: Körper aus Bild 1, Lid aus Bild 4, Atem per Bandverschiebung
    I = frames["idle"]
    mi = data["idle"]["frames"]
    ki = k["idle"]
    base_f = I[0]
    b_tip = K.snout_tip(base_f["mask"], TIP)
    # Bild 4 an Bild 1 einpassen: Maßstab r und Versatz über NCC des Kopfausschnitts
    best = (1.0, 0, 0, -2)
    for r in np.arange(0.96, 1.081, 0.005):
        f4 = K.scaled(I[3], r)
        a = K.head_anchors([base_f, f4], 0, search=10, tip_upper=TIP)[1]
        if a[2] > best[3]:
            best = (float(r), a[0], a[1], a[2])
    r4, ax4, ay4, c4 = best
    f4 = K.scaled(I[3], r4)
    # Lidteil: Ellipse um das Auge (relativ zur Schnauzenspitze von Bild 1), weich auslaufend
    eye = (b_tip[0] - 60, b_tip[1] - 15)
    h, w = base_f["mask"].shape
    yy, xx = np.mgrid[0:h, 0:w]
    dist = ((xx - eye[0]) / 24.0) ** 2 + ((yy - eye[1]) / 15.0) ** 2
    wgt = np.clip((1.25 - dist) / 0.5, 0, 1)[..., None]
    shift_x, shift_y = ax4 - b_tip[0], ay4 - b_tip[1]
    src4 = np.zeros_like(base_f["img"])
    H4, W4 = f4["img"].shape[:2]
    for y in range(h):
        sy = y + shift_y
        if 0 <= sy < H4:
            x0 = max(0, -shift_x)
            x1 = min(w, W4 - shift_x)
            if x1 > x0:
                src4[y, x0:x1] = f4["img"][sy, x0 + shift_x:x1 + shift_x]
    blink = base_f["img"].astype(np.float64)
    blink = (blink * (1 - wgt) + src4.astype(np.float64) * wgt).astype(np.uint8)
    blink[..., 3] = base_f["img"][..., 3]
    data["idle"]["blink_fit"] = {"scale": round(r4, 3), "dx": shift_x, "dy": shift_y, "ncc": c4,
                                 "eye_src": [int(eye[0] + base_f["x0"]), int(eye[1] + base_f["y0"])]}
    mb = mi[0]
    feet0 = mb["feet"][0]
    fx_src = (feet0[0] + feet0[1]) / 2 - base_f["x0"]
    bot = mb["bottom"] - base_f["y0"] + 1
    AXi, AYi, CWi, CHi = 200, 380, 400, 400
    plain = place(base_f["img"], ki, fx_src, bot, AXi, AYi, CWi, CHi)
    closed = place(blink, ki, fx_src, bot, AXi, AYi, CWi, CHi)
    # Atem: Zeilen über dem Band um d px nach oben, Band [y_top, y_bot] gedehnt (Füße und Beine unverändert)
    ys = np.flatnonzero(plain[..., 3].any(1))
    top_y, bot_y = ys[0], ys[-1]
    hh = bot_y - top_y
    band = (int(top_y + 0.40 * hh), int(top_y + 0.66 * hh))

    def breathe(img, d):
        if d == 0:
            return img.copy()
        out = np.zeros_like(img)
        y0, y1 = band
        out[y1:] = img[y1:]
        out[:y0 - d] = img[d:y0]
        seg = Image.fromarray(img[y0:y1], "RGBA").convert("RGBa")
        seg = np.asarray(seg.resize((img.shape[1], y1 - y0 + d), Image.BICUBIC).convert("RGBA"))
        out[y0 - d:y1] = seg
        return out
    idle_cells = [breathe(plain, 0), breathe(plain, 1), breathe(plain, 2),
                  breathe(closed, 0), breathe(closed, 1), breathe(closed, 2)]
    # Atemschleife allein (3,0 s bei 6 Bildern/s): ausgeatmet halten, einatmen, eingeatmet, ausatmen.
    # Das Blinzeln ist eine eigene Animation (je Atemstufe ein Bild mit Lid); main.gd blendet es mit einem
    # RandomNumberGenerator (feste seed) in unregelmäßigen Abständen von 3–5 s ein.
    anims["idle"] = {"cells": idle_cells, "anchor": [AXi, AYi], "size": [CWi, CHi],
                     "src": ["idle", [1, 1, 1, 4, 4, 4]],
                     "seq": [[0, 7], [1, 3], [2, 5], [1, 3]], "band": band,
                     "names": ["atem0", "atem1", "atem2", "blinzeln0", "blinzeln1", "blinzeln2"],
                     "extra": {"blink": {"seq": [[3, 1], [4, 1], [5, 1]], "loop": False}},
                     "remake": lambda c, dy: breathe(place(base_f["img"] if c < 3 else blink, ki, fx_src, bot,
                                                           AXi, AYi + dy, CWi, CHi), c % 3)}

    # ---------------- jump: alle 6 Bilder; Höhe wie gemalt, waagerecht Zehen beim Absprung fest
    J = frames["jump"]
    mj = data["jump"]["frames"]
    kj = k["jump"]
    AXj, AYj, CWj, CHj = 200, 380, 400, 400
    LAND = 8.0                                     # Landung 8 Bild-px weiter vorn als der Absprung (kleiner Satz)
    kf = [G * (m["head_scale"] if m["head_ncc"] > 0.6 else s["jump"]) for m in mj]
    feet_c = lambda m: (m["feet"][0][0] + m["feet"][-1][1]) / 2
    loc = lambda f, x: x - f["x0"]
    ground = mj[0]["bottom"] + 1
    lift = [0.0 if i in (0, 1, 5) else float(ground - (m["bottom"] + 1)) for i, m in enumerate(mj)]
    # Bild 1: Kopf auf AXj
    anchor_x = [None] * 6                          # (Quellpunkt lokal, Zell-x)
    anchor_x[0] = (loc(J[0], mj[0]["head"][0]), AXj)
    toe1_cell = AXj + (mj[0]["feet"][0][1] - mj[0]["head"][0]) * kf[0]
    # Bild 2: Kopf geneigt, Kopfabgleich unsicher -> an der Zehenspitze festhalten (steht noch am Boden)
    anchor_x[1] = (loc(J[1], mj[1]["feet"][0][1]), toe1_cell)
    tip2 = K.snout_tip(J[1]["mask"], TIP)[0]
    head_cell = [0.0] * 6
    head_cell[0] = AXj
    head_cell[1] = toe1_cell + (tip2 - loc(J[1], mj[1]["feet"][0][1])) * kf[1]
    # Bild 6: Füße LAND px vor den Füßen von Bild 1
    feet1_cell = AXj + (feet_c(mj[0]) - mj[0]["head"][0]) * kf[0]
    anchor_x[5] = (loc(J[5], feet_c(mj[5])), feet1_cell + LAND)
    head_cell[5] = feet1_cell + LAND + (mj[5]["head"][0] - feet_c(mj[5])) * kf[5]
    for i in (2, 3, 4):
        head_cell[i] = head_cell[1] + (head_cell[5] - head_cell[1]) * (i - 1) / 4
        anchor_x[i] = (loc(J[i], mj[i]["head"][0]), head_cell[i])
    jcells, jfoot = [], []
    for i, (f, m) in enumerate(zip(J, mj)):
        if i in (2, 3, 4):   # Flugbilder: Kopf gleichmäßig zwischen Absprung (korrigiert) und Landung
            head_cell[i] = head_cell[1] + (head_cell[5] - head_cell[1]) * (i - 1) / 4
            anchor_x[i] = (loc(J[i], mj[i]["head"][0]), head_cell[i])
        ax_s, ax_c = anchor_x[i]
        ay_s = m["bottom"] - f["y0"] + 1
        jcells.append(place(f["img"], kf[i], ax_s, ay_s, ax_c, AYj - lift[i] * kf[i], CWj, CHj))
        if i == 1:
            # Zehen des Absprungs genau auf die Zehen der Hocke legen (im Bildmaßstab nachgemessen)
            corr = toe_x(jcells[0], AYj) - toe_x(jcells[1], AYj)
            anchor_x[1] = (ax_s, ax_c + corr)
            head_cell[1] += corr
            jcells[1] = place(f["img"], kf[i], ax_s, ay_s, ax_c + corr, AYj, CWj, CHj)
            data["jump"]["toe_correction_px"] = corr
        jfoot.append(round(anchor_x[i][1] + (feet_c(m) - f["x0"] - ax_s) * kf[i], 2))
    data["jump"]["placement"] = {"head_cell_x": [round(v, 2) for v in head_cell],
                                 "lift_src": lift, "lift_px": [round(l * q, 2) for l, q in zip(lift, kf)],
                                 "scale": [round(v, 4) for v in kf], "land_forward_px": LAND}
    anims["jump"] = {"cells": jcells, "anchor": [AXj, AYj], "size": [CWj, CHj], "src": ["jump", [1, 2, 3, 4, 5, 6]],
                     "seq": [[0, 2], [1, 1], [2, 1], [3, 1], [4, 1], [5, 2]]}

    # ---------------- wave: Blatt 2, Bilder 1, 2, 4, 6 (3 und 5 wechseln den Arm), an den Füßen ausgerichtet
    V = frames["wave2"]
    mv = data["wave2"]["frames"]
    kv = k["wave"]
    # Füße: Unterkante + Mitte der Bodenläufe; feiner per NCC des Beinbereichs gegen Bild 1
    use_v = [0, 1, 3, 5]
    ref = V[0]
    rh, rw = ref["mask"].shape
    leg0 = int(rh * 0.78)
    G0 = K.gray(ref["img"])
    fits = []
    for i in use_v:
        f = V[i]
        g = K.gray(f["img"])
        best = (0, 0, -2)
        # Bild i so verschieben, dass seine Beine auf denen von Bild 1 liegen (Unterkanten bündig als Start)
        dyb = (mv[i]["bottom"] - f["y0"]) - (mv[0]["bottom"] - ref["y0"])
        for dx in range(-30, 31):
            for dy in range(dyb - 3, dyb + 4):
                a = G0[leg0:rh]
                am = ref["mask"][leg0:rh]
                ys0, ys1 = leg0 + dy, rh + dy
                if ys0 < 0 or ys1 > g.shape[0]:
                    continue
                x0 = max(0, dx)
                x1 = min(rw, g.shape[1] + dx) if dx < 0 else min(rw + dx, g.shape[1])
                bb = np.zeros_like(a)
                src = g[ys0:ys1]
                lo, hi = max(0, -dx), min(rw, g.shape[1] - dx)
                bb[:, lo:hi] = src[:, lo + dx:hi + dx]
                av = a[am]
                bv = bb[am]
                av = (av - av.mean()) / (av.std() + 1e-6)
                bv = (bv - bv.mean()) / (bv.std() + 1e-6)
                c = float((av * bv).mean())
                if c > best[2]:
                    best = (dx, dy, c)
        fits.append(best)
    AXv, AYv, CWv, CHv = 200, 380, 400, 400
    vcells = []
    feet_v = mv[0]["feet"][0]
    fx0 = (feet_v[0] + feet_v[1]) / 2 - ref["x0"]
    by0 = mv[0]["bottom"] - ref["y0"] + 1
    for (i, fit) in zip(use_v, fits):
        f = V[i]
        vcells.append(place(f["img"], kv, fx0 + fit[0], by0 + fit[1], AXv, AYv, CWv, CHv))
    data["wave2"]["leg_fit"] = [{"frame": i + 1, "dx": d[0], "dy": d[1], "ncc": round(d[2], 3)}
                                for i, d in zip(use_v, fits)]
    anims["wave"] = {"cells": vcells, "anchor": [AXv, AYv], "size": [CWv, CHv], "src": ["wave2", [1, 2, 4, 6]],
                     "seq": [[0, 1], [1, 1], [2, 1], [3, 1], [2, 1], [3, 1], [2, 1], [3, 1], [1, 1], [0, 1]],
                     "remake": lambda c, dy: place(V[use_v[c]]["img"], kv, fx0 + fits[c][0], by0 + fits[c][1],
                                                   AXv, AYv + dy, CWv, CHv)}

    # ---------------- Flimmern messen (korrigiert gegen ganze KI-Bilder, gleiche Ausrichtung)
    whole_idle = [place(I[i]["img"], ki, (mi[i]["feet"][0][0] + mi[i]["feet"][0][1]) / 2 - I[i]["x0"],
                        mi[i]["bottom"] - I[i]["y0"] + 1, AXi, AYi, CWi, CHi) for i in range(6)]
    data["idle"]["flicker_whole_frames"] = flicker(whole_idle)
    data["idle"]["flicker_built"] = flicker([idle_cells[i] for i in (0, 1, 2, 1)])
    data["wave2"]["flicker_used"] = flicker(vcells)

    # ---------------- Stehen und Winken: Sohle unterpixelgenau angleichen (vorher saß Winkbild 6 rund 0,45 px tiefer
    # als 1, 2 und 4 und wippte im Wechsel um 1 px). Laufen und Springen behalten ihre Ausrichtung an der
    # tiefsten Zeile (dort hält sie den Standfuß auf ±1 px; ein Angleichen der Sohle verschob die weichen
    # Zehenspitzen um bis zu 3 px). Dann die Außenkontur in der Konturfarbe des Hintergrunds für alle Zellen;
    # der Anker wandert um OUTLINE_R nach unten, damit die Kontur unter den Füßen auf dem Boden steht (wie bei
    # Fässern und Kisten im Hintergrund)
    contour = bg_contour_color()
    data["outline"] = {"radius_px": OUTLINE_R, "color": [int(v) for v in contour], "ground_alpha": GROUND_ALPHA}
    for name, a in anims.items():
        ay = int(round(a["anchor"][1]))
        on_ground = range(len(a["cells"])) if name in ("idle", "wave") else ()
        remake = a.pop("remake", None)
        shifts, before, after = [], [], []
        for i, c in enumerate(a["cells"]):
            dy = 0.0
            if i in on_ground:
                # Sohle unterpixelgenau auf die Ankerzeile legen: neu abtasten mit verschobener Lage (eine Abtastung)
                e0 = sole_edge(c, ay)
                before.append(round(e0 - ay, 2))
                target = ay - SOLE_ABOVE
                for _ in range(3):
                    e = sole_edge(c, ay)
                    if abs(e - target) < 0.05:
                        break
                    dy += target - e
                    c = remake(i, dy)
                after.append(round(sole_edge(c, ay) - ay, 2))
                low = lowest_strong_row(c)
                if low != ay - 1:
                    print(f"WARNUNG: {name} Zelle {i}: unterste kräftige Zeile {low - ay + 1:+d} gegen die Ankerzeile")
            shifts.append(round(dy, 2))
            a["cells"][i] = add_outline(c, contour)
        a["ground_shift"] = shifts
        a["sole_edge_before"] = before
        a["sole_edge_after"] = after
        a["anchor"] = [a["anchor"][0], a["anchor"][1] + OUTLINE_R]
        print(name, "Sohle vorher", before, "verschoben", shifts, "nachher", after)

    # ---------------- Zellen auf die gemeinsame Hülle je Animation beschneiden (2 px Rand), Anker mitführen
    for name, a in anims.items():
        al = np.stack([c[..., 3] > 0 for c in a["cells"]]).any(0)
        ys, xs = np.flatnonzero(al.any(1)), np.flatnonzero(al.any(0))
        x0, x1 = int(max(0, xs[0] - 2)), int(min(al.shape[1], xs[-1] + 3))
        y0, y1 = int(max(0, ys[0] - 2)), int(min(al.shape[0], ys[-1] + 3))
        a["cells"] = [c[y0:y1, x0:x1].copy() for c in a["cells"]]
        a["anchor"] = [round(a["anchor"][0] - x0, 2), round(a["anchor"][1] - y0, 2)]
        a["size"] = [int(x1 - x0), int(y1 - y0)]
        if "stand_foot_x" in a:
            a["stand_foot_x"] = [round(v - x0, 2) for v in a["stand_foot_x"]]
        # Fußpunkt je Zelle: Mitte der deckenden Pixel in den untersten 8 Zeilen über der Ankerzeile
        a["foot_x"] = []
        for c in a["cells"]:
            ay = int(round(a["anchor"][1]))
            sub = c[max(0, ay - 8):ay, :, 3] > 128
            xs2 = np.flatnonzero(sub.any(0))
            a["foot_x"].append(round(float((xs2[0] + xs2[-1] + 1) / 2), 1) if xs2.size else None)
        ayc = int(round(a["anchor"][1]))
        a["toe_x"] = [toe_x(c, ayc) for c in a["cells"]]
        a["body_x"] = [body_x(c, ayc) for c in a["cells"]]
        # Schnauzenspitze je Zelle (nur Seitenansichten), für die Hilfslinien im Panel
        a["snout"] = [list(map(int, K.snout_tip(c[..., 3] > 128, TIP))) if name != "wave" else None
                      for c in a["cells"]]
        # Abstand der tiefsten Figurzeile über der Ankerzeile (Sprunghöhe, für den Schatten)
        a["gap"] = []
        for c in a["cells"]:
            ys3 = np.flatnonzero((c[..., 3] > 128).any(1))
            a["gap"].append(round(float(a["anchor"][1] - (ys3[-1] + 1)), 1))
        if "band" in a:
            a["band"] = [int(a["band"][0] - y0), int(a["band"][1] - y0)]

    # ---------------- Streifen schreiben
    meta = {"display_scale": data["scale"], "anims": {}}
    for name, a in anims.items():
        CWa, CHa = a["size"]
        strip = np.zeros((CHa, CWa * len(a["cells"]), 4), np.uint8)
        for i, c in enumerate(a["cells"]):
            strip[:, i * CWa:(i + 1) * CWa] = c
        Image.fromarray(strip, "RGBA").save(ART / f"badger_{name}.png")
        meta["anims"][name] = {kk: v for kk, v in a.items() if kk != "cells"}
        meta["anims"][name]["fps"] = FPS[name]
        meta["anims"][name]["count"] = len(a["cells"])
        # Kontrolle: Zellränder dürfen keine Figurpixel enthalten (sonst ist die Zelle zu klein)
        for i, c in enumerate(a["cells"]):
            edge = np.concatenate([c[0, :, 3], c[-1, :, 3], c[:, 0, 3], c[:, -1, 3]])
            if edge.max() > 8:
                print(f"WARNUNG: {name} Bild {i + 1} berührt den Zellrand")

    # ---------------- rohe Fassung: tools/sprites.py slice, wie man es ohne Messung tun würde
    raw_meta = {}
    for name, sheet, n in (("walk", "walk", 8), ("idle", "idle", 6), ("jump", "jump", 6), ("wave", "wave2", 6)):
        out = ART / f"raw_{name}.png"
        r = subprocess.run([sys.executable, str(ROOT / "tools/sprites.py"), "slice", str(RAW / f"{sheet}.png"),
                            str(out), "--frames", str(n), "--height", str(RAW_SLICE_H)],
                           capture_output=True, text=True, cwd=ROOT)
        if r.returncode:
            raise SystemExit(r.stderr)
        j = json.loads(out.with_suffix(".json").read_text())
        out.with_suffix(".json").unlink()
        j["source"] = f"assets/raw/{sheet}.png"
        j["fps"] = RAW_FPS[name]
        j["sheet"] = sheet
        j["slice_log"] = [l for l in r.stdout.splitlines() if l.startswith("geteilt") or l.startswith("WARNUNG")]
        # Schnauzenspitze je Bild (Seitenansichten) und Figurhöhe: zeigt Zittern und Größensprünge der rohen Fassung
        st = np.asarray(Image.open(out).convert("RGBA"))
        tips, heights = [], []
        for i in range(j["count"]):
            c = st[:, i * j["frame_w"]:(i + 1) * j["frame_w"]]
            m = c[..., 3] > 128
            ys = np.flatnonzero(m.any(1))
            heights.append(int(ys[-1] - ys[0] + 1))
            tips.append(list(K.snout_tip(m, TIP)) if sheet != "wave2" else None)
        j["snout"] = tips
        j["heights"] = heights
        raw_meta[name] = j
    meta["raw"] = raw_meta

    # ---------------- Vorschaubilder aller Blattbilder (Panel), Status je Bild
    TH = 64
    status = {
        "walk": ["ok", "ok", "ok", "ok", "doppelt", "doppelt", "doppelt", "doppelt"],
        "idle": ["koerper", "atem", "atem", "lid", "atem", "atem"],
        "jump": ["ok"] * 6,
        "wave": ["ok", "ok", "seite", "ok", "seite", "ok"],
    }
    thumbs = {}
    for name, sheet in (("walk", "walk"), ("idle", "idle"), ("jump", "jump"), ("wave", "wave2")):
        fr = frames[sheet]
        ks = TH / max(f["mask"].shape[0] for f in fr)
        ims = []
        for f in fr:
            h, w = f["mask"].shape
            ims.append(pm_resize(f["img"], (max(1, round(w * ks)), max(1, round(h * ks))), (0, 0, w, h)))
        tw = sum(i.shape[1] for i in ims) + 2 * (len(ims) - 1)
        strip = np.zeros((TH, tw, 4), np.uint8)
        x = 0
        rects = []
        for im in ims:
            strip[TH - im.shape[0]:, x:x + im.shape[1]] = im
            rects.append([x, 0, im.shape[1], TH])
            x += im.shape[1] + 2
        Image.fromarray(strip, "RGBA").save(ART / f"thumbs_{name}.png")
        thumbs[name] = {"rects": rects, "status": status[name]}
    meta["thumbs"] = thumbs
    # Erklärzeilen für das Panel aus den Messwerten (Blattbefund, Gegenmittel)
    ld = data["walk"]["leg_diff"]
    dup = [ld[i][i + 4] for i in range(4)]
    near = min(ld[i][j] for i in range(4) for j in range(4) if i != j)
    fw = data["idle"]["flicker_whole_frames"]
    pct = lambda v: f"{round(v * 100)}"
    meta["notes"] = {
        "walk": ["8 Bilder, nur 4 Posen: 5–8 wiederholen 1–4",
                 "Kopfanker statt Schwerpunkt, Vorschub aus dem Standfuß"],
        "idle": [f"6 ganze Bilder: {pct(min(fw))}–{pct(max(fw))} % der Figurpixel wechseln",
                 "1 Körper + Lid aus Bild 4 alle 3–5 s + Atmen 0–2 px per Code"],
        "jump": [f"Blatt {pct(1 / s['jump'] - 1)} % größer gemalt, Sprunghöhe eingezeichnet",
                 "auf Kopfgröße normiert, gemalte Höhe behalten"],
        "wave": ["Bild 3 und 5: Paket und Winkarm wechseln die Seite",
                 "aussortiert, Bilder 1, 2, 4, 6 an den Füßen ausgerichtet"],
    }
    meta["walk_dup_legdiff"] = dup
    meta["walk_min_other_legdiff"] = near
    (ART / "anim.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))

    # ---------------- SpriteFrames schreiben
    write_frames(E / "demo" / "badger_frames.tres", "badger", anims, meta)
    write_raw_frames(E / "demo" / "raw_frames.tres", raw_meta)

    # Kopien der verarbeiteten Assets nach assets/sprites/ (die Demo nutzt demo/art/), KI-Blätter verkleinert
    # nach assets/sheets/ (Originale liegen in assets/raw/, nicht im Git)
    sp = E / "assets" / "sprites"
    sp.mkdir(parents=True, exist_ok=True)
    for f in sorted(ART.glob("badger_*.png")) + sorted(ART.glob("raw_*.png")) + [ART / "anim.json"]:
        shutil.copy2(f, sp / f.name)
    sh = E / "assets" / "sheets"
    sh.mkdir(parents=True, exist_ok=True)
    for name in ("walk", "idle", "jump", "wave", "wave2"):
        im = np.asarray(Image.open(RAW / f"{name}.png").convert("RGBA"))
        ys = np.flatnonzero((im[..., 3] > 24).any(1))
        y0, y1 = max(0, ys[0] - 12), min(im.shape[0], ys[-1] + 13)
        crop = im[y0:y1]
        Image.fromarray(pm_resize(crop, (crop.shape[1] // 2, (y1 - y0) // 2), (0, 0, crop.shape[1], y1 - y0)),
                        "RGBA").save(sh / f"{name}.png", optimize=True)

    data["flicker_note"] = ("Anteil der Figurpixel, die sich zwischen aufeinanderfolgenden Bildern um mehr als 40 "
                            "Tonwerte ändern (gleiche Ausrichtung an den Füßen, Bildmaßstab).")
    (E / "assets" / "sheets.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print("Flimmern idle ganz", data["idle"]["flicker_whole_frames"], "gebaut", data["idle"]["flicker_built"])
    print("Flimmern wave (1,2,4,6)", data["wave2"]["flicker_used"])
    print("Lid eingepasst", data["idle"]["blink_fit"])
    print("Winkblatt Beinabgleich", data["wave2"]["leg_fit"])


def write_frames(path, prefix, anims, meta):
    lines = []
    subs = []
    ext = []
    for n, (name, a) in enumerate(anims.items(), start=1):
        ext.append(f'[ext_resource type="Texture2D" path="res://art/{prefix}_{name}.png" id="{n}_{name}"]')
        CW, CH = a["size"]
        for i in range(len(a["cells"])):
            subs.append(f'[sub_resource type="AtlasTexture" id="{name}_{i}"]\natlas = ExtResource("{n}_{name}")\n'
                        f'region = Rect2({i * CW}, 0, {CW}, {CH})\n')
    lines.append(f'[gd_resource type="SpriteFrames" format=3]\n')
    lines += ext
    lines.append("")
    lines += subs
    lines.append("[resource]")
    entries = []
    for name, a in anims.items():
        fr = ", ".join(f'{{\n"duration": {float(d):.1f},\n"texture": SubResource("{name}_{i}")\n}}'
                       for i, d in a["seq"])
        loop = "false" if name in ("jump", "wave") else "true"
        entries.append(f'{{\n"frames": [{fr}],\n"loop": {loop},\n"name": &"{name}",\n"speed": {float(FPS[name]):.1f}\n}}')
        # weitere Animationen aus demselben Streifen (idle: "blink" mit den Lid-Zellen)
        for xname, x in a.get("extra", {}).items():
            fr = ", ".join(f'{{\n"duration": {float(d):.1f},\n"texture": SubResource("{name}_{i}")\n}}'
                           for i, d in x["seq"])
            entries.append(f'{{\n"frames": [{fr}],\n"loop": {"true" if x["loop"] else "false"},\n'
                           f'"name": &"{xname}",\n"speed": {float(FPS[xname]):.1f}\n}}')
    lines.append("animations = [" + ", ".join(entries) + "]")
    path.write_text("\n".join(lines) + "\n")


def write_raw_frames(path, raw_meta):
    ext, subs, entries = [], [], []
    for n, (name, j) in enumerate(raw_meta.items(), start=1):
        ext.append(f'[ext_resource type="Texture2D" path="res://art/raw_{name}.png" id="{n}_{name}"]')
        for i in range(j["count"]):
            subs.append(f'[sub_resource type="AtlasTexture" id="{name}_{i}"]\natlas = ExtResource("{n}_{name}")\n'
                        f'region = Rect2({i * j["frame_w"]}, 0, {j["frame_w"]}, {j["frame_h"]})\n')
        fr = ", ".join(f'{{\n"duration": 1.0,\n"texture": SubResource("{name}_{i}")\n}}' for i in range(j["count"]))
        entries.append(f'{{\n"frames": [{fr}],\n"loop": true,\n"name": &"{name}",\n"speed": {float(j["fps"]):.1f}\n}}')
    text = '[gd_resource type="SpriteFrames" format=3]\n\n' + "\n".join(ext) + "\n\n" + "\n".join(subs) + \
        "\n[resource]\nanimations = [" + ", ".join(entries) + "]\n"
    path.write_text(text)


if __name__ == "__main__":
    main()
