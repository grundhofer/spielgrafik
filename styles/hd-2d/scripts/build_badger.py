#!/usr/bin/env python3
"""Dachs-Kurier für hd-2d: KI-Figurenblatt -> Pixel-Sprites (Billboards in der 3D-Szene).

    .venv/bin/python styles/hd-2d/scripts/build_badger.py [--th 60] [--preview out.png]

Eingabe: assets/raw/badger.png (gpt-image über der Blender-Posenvorlage assets/ref/pose_layout.png):
oben 8 Laufbilder (Seitenansicht nach rechts), unten 4 Vorderansichten (im Blatt: Zwinkern, Augen zu,
Winken außen, Winken innen). Ablauf:
  1. Figuren über Alpha >= 200 ausschneiden (das Blatt hat einen halbtransparenten Dunst).
  2. Gemeinsame Palette (k-means in Oklab, NCOL Farben) für alle Bilder, dazu Augenweiß und Pupille.
  3. Je Reihe ein Maßstab (Medianhöhe -> TH) und eine gemeinsame Grundlinie (die Höhenlage der Bilder bleibt
     wie gezeichnet); waagrecht je Bild an der Mütze ausgerichtet (Mitte der breitesten Spanne in den oberen
     8 % der Figur; ein erhobener Arm verschiebt den Anker so nicht).
     Je Zielpixel: deckend, wenn >= 50 % der Zelle deckend; Farbe = häufigster Index im Zellinneren, dunkle
     Linien gewinnen schon ab DARK_SHARE (sonst verschwinden Kontur, Nase, Mützenschirm).
  4. Umriss schließen (Konturfarbe an Transparenz).
  5. Augen setzen: Das Augenweiß ist im Blatt ein kleiner Bogen aus reinweißen Pixeln, der beim Verkleinern
     verschwindet. Je Auge (zusammenhängende reinweiße Fläche im Kopf) wird ein 2×2-Auge gemalt: Glanz oben
     links, Pupille in den drei übrigen Pixeln.
  6. Vorderansicht aus Teilen: Grundbild = Bild 1 (zwinkert im Blatt) mit dem offenen Auge an der Nase
     gespiegelt; Blinzeln = Grundbild mit geschlossenen Augen; Winken = Bilder 3/4, deren Unterkörper durch den
     der Grundpose ersetzt ist (Beine und Bauch flimmern sonst zwischen den Winkbildern).
Ausgaben: assets/badger_walk.png, assets/badger_front.png (Streifen, Zelle CW×CH), assets/badger.json;
Kopien nach demo/sprites/.
"""
import argparse
import json
import pathlib
import shutil
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from hd2dlib import figures, kmeans, nearest, oklab, oklab_to_rgb, outline_edge, runs  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "assets" / "raw"
NCOL = 28
DARK_SHARE = 0.34
EYE_WHITE = (246, 244, 236)
EYE_BLACK = (24, 14, 14)
LEG_ROW_FRAC = 50 / 64      # ab dieser Zeile (Anteil der Zellhöhe) Beine aus der Grundpose
ARM_BOX = (46 / 68, 34 / 64)  # Winkarm: rechts ab Spalte, oben bis Zeile (Anteile der Zelle)


def cap_x(m, f):
    """Mitte der Mütze: breiteste deckende Spanne in den obersten 8 % der Figur (gemittelt über die Zeilen)."""
    h = f["bot"] - f["top"] + 1
    xs = []
    for y in range(f["top"], f["top"] + max(3, int(0.08 * h))):
        row = m[y, f["x0"]:f["x1"]]
        if not row.any():
            continue
        best = max(runs(row, 1), key=lambda r: r[1] - r[0])
        xs.append(f["x0"] + (best[0] + best[1] - 1) / 2)
    return float(np.mean(xs))


def reduce_fig(lbl, m, f, ox, oy, scale, cw, ch, dark):
    idx = np.full((ch, cw), -1, np.int64)
    inset = 0.15
    for v in range(ch):
        fy0, fy1 = oy + v * scale, oy + (v + 1) * scale
        if fy1 <= 0 or fy0 >= lbl.shape[0]:
            continue
        for u in range(cw):
            fx0, fx1 = ox + u * scale, ox + (u + 1) * scale
            a0, a1 = max(0, int(round(fy0))), min(lbl.shape[0], int(round(fy1)))
            b0, b1 = max(f["x0"] - 2, int(round(fx0))), min(f["x1"] + 2, int(round(fx1)))
            if a1 <= a0 or b1 <= b0 or m[a0:a1, b0:b1].mean() < 0.5:
                continue
            y0 = int(np.floor(fy0 + inset * scale)); y1 = max(y0 + 1, int(np.ceil(fy1 - inset * scale)))
            x0 = int(np.floor(fx0 + inset * scale)); x1 = max(x0 + 1, int(np.ceil(fx1 - inset * scale)))
            mm = m[y0:y1, x0:x1]
            if not mm.any():
                mm, y0, y1, x0, x1 = m[a0:a1, b0:b1], a0, a1, b0, b1
            ll = lbl[y0:y1, x0:x1][mm]
            bc = np.bincount(ll, minlength=NCOL)
            dk = bc * dark
            idx[v, u] = int(np.argmax(dk)) if dk.sum() >= DARK_SHARE * len(ll) else int(np.argmax(bc))
    return idx


def components(mask):
    """4er-Zusammenhangskomponenten (kleine Masken), Liste von (ys, xs)."""
    seen = np.zeros_like(mask)
    out = []
    for y, x in zip(*np.nonzero(mask)):
        if seen[y, x]:
            continue
        stack, pts = [(y, x)], []
        seen[y, x] = True
        while stack:
            cy, cx = stack.pop()
            pts.append((cy, cx))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1] and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        out.append((np.array([p[0] for p in pts]), np.array([p[1] for p in pts])))
    return out


def close_outline(idx, outline_c, L):
    out = idx.copy()
    edge = outline_edge(idx >= 0)
    fix = edge & (L[np.clip(idx, 0, None)] >= 0.25)
    out[fix] = outline_c
    return out


def to_rgba(idx, pal):
    a = idx >= 0
    c = pal[np.clip(idx, 0, None)].copy()
    c[~a] = 0
    return np.dstack([c, a.astype(np.uint8) * 255])


def strip(frames, pal):
    return np.concatenate([to_rgba(f, pal) for f in frames], axis=1)


POSE = ROOT / "assets" / "ref" / "pose"
LEG_CUT = 53         # ab dieser Zeile werden die KI-Beine entfernt (darüber nur, wo das 3D-Bein liegt)
LEG_TOP = 47         # ab dieser Zeile dürfen 3D-Beine gezeichnet werden


def legs_from_3d(walk, xf, m, figs, L, outline_c, CW, CH):
    """Beine der Laufbilder aus dem Blender-Rig (assets/ref/pose/id_walk_*.png: nahes Bein grün, fernes blau,
    Körper schwarz) statt aus dem KI-Blatt. Die KI-Beine folgen der Posenvorlage nur ungefähr: Der Standfuß
    wanderte in der ersten Hälfte des Zyklus nach vorn statt zurück (gemessen bis -2 px je Bild), ein fester
    Standfuß war mit keinem Vorschub möglich. Das Rig läuft auf der Stelle mit 4,6 cm Rücklauf je Bild.

    Abbildung Sprite -> KI-Blatt (wie beim Verkleinern) -> Posenblatt (KI ist um S größer, an Mütze und
    Oberkante ausgerichtet) -> Einzelrender (480 px, ortho 1,30 m). Je Sprite-Pixel entscheidet die Mehrheit im
    Fußabdruck der Zelle. Farben: Beinrampe aus den KI-Beinen (drei häufigste Töne unter der Kontur),
    nahes Bein hell/mittel nach der Helligkeit des schattierten Renders, fernes Bein eine Stufe dunkler,
    Kontur an Transparenz und zwischen nahem und fernem Bein.
    """
    from compose_layout_info import layout_figures   # noqa: E402  (eigenes Hilfsmodul)
    lay = layout_figures()
    S = np.median([f["bot"] - f["top"] + 1 for f in figs]) / np.median([g["h"] for g in lay[:8]])
    PXM = 480 / 1.30
    SC = 250 / (1.011 * PXM)
    ORY = 240 + 0.55 * np.cos(np.radians(15.0)) * PXM
    # Beinrampe aus den KI-Beinen (Zeilen >= 55, ohne Kontur)
    vals = np.concatenate([w[55:][(w[55:] >= 0)] for w in walk])
    vals = vals[vals != outline_c]
    common = [int(c) for c in np.bincount(vals).argsort()[::-1][:3]]
    ramp = sorted(common, key=lambda c: L[c])          # dunkel, mittel, hell
    out, info, masks = [], [], []
    for k, (w, t, f, g) in enumerate(zip(walk, xf, figs, lay[:8])):
        idr = np.asarray(Image.open(POSE / f"id_walk_{k:02d}.png").convert("RGBA")).astype(np.int64)
        shd = np.asarray(Image.open(POSE / f"walk_{k:02d}.png").convert("L")).astype(np.float64)
        near = (idr[..., 3] > 128) & (idr[..., 1] > 128) & (idr[..., 0] < 100)
        far = (idr[..., 3] > 128) & (idr[..., 2] > 128) & (idr[..., 0] < 100) & ~near
        body = (idr[..., 3] > 128) & ~near & ~far
        res = w.copy()
        cls = np.zeros((CH, CW), np.int64)             # 0 leer, 1 nah, 2 fern, 3 Körper
        lum = np.zeros((CH, CW))
        for v in range(LEG_TOP, CH):
            for u in range(CW):
                xa = t["ox"] + (u + 0.5) * t["scale"]
                ya = t["oy"] + (v + 0.5) * t["scale"]
                xl = g["cap"] + (xa - t["cap"]) / S
                yl = g["top"] + (ya - f["top"]) / S
                xr = 240 + (xl - g["origin"][0]) / SC
                yr = ORY + (yl - g["origin"][1]) / SC
                hw = 0.5 * t["scale"] / S / SC
                x0, x1 = int(round(xr - hw)), int(round(xr + hw))
                y0, y1 = int(round(yr - hw)), int(round(yr + hw))
                if x1 <= 0 or y1 <= 0 or x0 >= 480 or y0 >= 480:
                    continue
                x0, y0 = max(x0, 0), max(y0, 0)
                cnt = [near[y0:y1, x0:x1].sum(), far[y0:y1, x0:x1].sum(), body[y0:y1, x0:x1].sum()]
                tot = (y1 - y0) * (x1 - x0)
                if max(cnt) < 0.4 * tot:
                    continue
                c = int(np.argmax(cnt)) + 1
                cls[v, u] = c
                if c in (1, 2):
                    mm = near[y0:y1, x0:x1] if c == 1 else far[y0:y1, x0:x1]
                    lum[v, u] = shd[y0:y1, x0:x1][mm].mean()
        legs = (cls == 1) | (cls == 2)
        for v in range(LEG_TOP, CH):
            for u in range(CW):
                if v >= LEG_CUT and cls[v, u] != 3:
                    res[v, u] = -1
                if legs[v, u] and (v >= LEG_CUT or res[v, u] < 0 or L[res[v, u]] < 0.45):
                    if cls[v, u] == 1:
                        res[v, u] = ramp[2] if lum[v, u] > 105 else ramp[1]
                    else:
                        res[v, u] = ramp[1] if lum[v, u] > 120 else ramp[0]
        # Kontur: Beinpixel an Transparenz, und fernes Bein an nahem Bein
        op = res >= 0
        for v in range(LEG_TOP, CH):
            for u in range(CW):
                if not legs[v, u]:
                    continue
                nb = [(v + dv, u + du) for dv, du in ((1, 0), (-1, 0), (0, 1), (0, -1))]
                edge = any(not (0 <= a < CH and 0 <= b < CW) or not op[a, b] for a, b in nb)
                sep = cls[v, u] == 2 and any(0 <= a < CH and 0 <= b < CW and cls[a, b] == 1 for a, b in nb)
                if edge or sep:
                    res[v, u] = outline_c
        out.append(res)
        mask = np.zeros((CH, CW), np.int64)          # Messbild: 1 Körper, 2 nahes Bein, 3 fernes Bein
        mask[res >= 0] = 1
        mask[legs & (res >= 0) & (cls == 1)] = 2
        mask[legs & (res >= 0) & (cls == 2)] = 3
        masks.append(mask)
        rows = np.flatnonzero((res >= 0).any(1))
        info.append({"bottom": int(rows[-1]), "near_px": int((cls == 1).sum()), "far_px": int((cls == 2).sum())})
    cols = np.array([[0, 0, 0, 0], [255, 255, 255, 255], [0, 255, 0, 255], [0, 0, 255, 255]], np.uint8)
    strip_m = np.concatenate([cols[mk] for mk in masks], axis=1)
    Image.fromarray(strip_m, "RGBA").save(ROOT / "assets" / "badger_walk_legs.png")
    shutil.copy(ROOT / "assets" / "badger_walk_legs.png", ROOT / "demo" / "sprites" / "badger_walk_legs.png")
    return out, {"S": round(float(S), 4), "ramp": ramp, "frames": info}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--th", type=int, default=60, help="Figurenhöhe (Vorderansicht) in Sprite-Pixeln")
    ap.add_argument("--preview", default="")
    ap.add_argument("--ai-legs", action="store_true", help="Beine aus dem KI-Blatt lassen (Vergleich)")
    a = ap.parse_args()
    TH = a.th
    CW, CH = int(round(TH * 1.15)) // 2 * 2, TH + 4
    AX = CW // 2
    BASE = CH - 2

    sheet = np.asarray(Image.open(RAW / "badger.png").convert("RGBA"))
    m = sheet[..., 3] >= 200
    figs = figures(m)
    assert len(figs) == 12, len(figs)
    rgb = sheet[..., :3].astype(np.int64)
    lab_all = oklab(rgb[m])
    rng = np.random.default_rng(5)
    cent = kmeans(lab_all[rng.choice(len(lab_all), 80000, replace=False)], NCOL, iters=25, seed=5)
    lbl = np.zeros(m.shape, np.int64)
    lbl[m] = nearest(lab_all, cent)
    WHITE_C, BLACK_C = NCOL, NCOL + 1
    cent = np.vstack([cent, oklab(np.array([EYE_WHITE, EYE_BLACK]))])
    pal = np.clip(np.round(oklab_to_rgb(cent)), 0, 255).astype(np.uint8)
    L = cent[:, 0]
    dark = L[:NCOL] < 0.25
    outline_c = int(np.argmin(L[:NCOL]))
    pure_white = m & (rgb.min(2) > 225)

    meta = {"th": TH, "cell": [CW, CH], "anchor_x": AX, "baseline": BASE, "palette": len(pal), "rows": {},
            "eyes": []}
    frames, eyes, xf = [], [], []
    for r in (0, 1):
        fr = [f for f in figs if f["row"] == r]
        h = float(np.median([f["bot"] - f["top"] + 1 for f in fr]))
        scale = h / TH
        base_src = max(f["bot"] for f in fr)
        meta["rows"][r] = {"src_height": h, "scale": round(scale, 3), "base_src": base_src}
        for f in fr:
            hx = cap_x(m, f)
            ox = hx - (AX + 0.5) * scale
            oy = (base_src + 1) - (BASE + 1) * scale
            idx = reduce_fig(lbl, m, f, ox, oy, scale, CW, CH, dark)
            idx = close_outline(idx, outline_c, L)
            xf.append({"f": f, "ox": ox, "oy": oy, "scale": scale, "cap": hx})
            # Augen aus dem reinweißen Augenbogen im Kopf (obere 36 % der Figur)
            y_head = f["top"] + int(0.36 * (f["bot"] - f["top"]))
            sub = pure_white[f["top"]:y_head, f["x0"]:f["x1"]]
            pts = []      # (Anzahl, x, y) je Bogenstück; Stücke eines Auges liegen dicht beieinander
            for ys, xs in components(sub):
                if len(ys) >= 3:
                    pts.append([len(ys), f["x0"] + xs.mean(), f["top"] + ys.mean()])
            groups = []
            for p in pts:
                for g in groups:
                    if np.hypot(g[1] / g[0] - p[1], g[2] / g[0] - p[2]) < 2.5 * scale:
                        g[0] += p[0]; g[1] += p[0] * p[1]; g[2] += p[0] * p[2]
                        break
                else:
                    groups.append([p[0], p[0] * p[1], p[0] * p[2]])
            fe = []
            for n, sx, sy in groups:
                if n < 6:
                    continue
                fe.append((int(np.floor((sx / n - ox) / scale)), int(np.floor((sy / n - oy) / scale))))
            eyes.append(fe)
            frames.append(idx)
    meta["eyes"] = eyes

    def paint_eye(idx, u, v):
        idx[v, u] = WHITE_C
        idx[v, u + 1] = BLACK_C
        idx[v + 1, u] = BLACK_C
        idx[v + 1, u + 1] = BLACK_C

    for idx, fe in zip(frames, eyes):
        for u, v in fe:
            paint_eye(idx, u, v)
    walk, front = frames[:8], frames[8:]
    if not a.ai_legs:
        walk, legs_meta = legs_from_3d(walk, xf[:8], m, figs[:8], L, outline_c, CW, CH)
        meta["legs"] = legs_meta

    # Vorderansicht aus Teilen
    base = front[0].copy()
    e_open = eyes[8]
    assert len(e_open) == 1, e_open       # Bild 1 zwinkert: nur ein offenes Auge
    # Spiegelachse: Mitte der Nase (dunkelster Bereich unter den Augen, Mitte der Zelle)
    u0, v0 = e_open[0]
    axis = AX - 0.5                        # Kappe liegt mittig; Nase sitzt auf der Achse
    nose_rows = range(v0 + 2, v0 + 6)
    darks = [(u) for vv in nose_rows for u in range(CW) if base[vv, u] >= 0 and L[base[vv, u]] < 0.2
             and abs(u - axis) < 4]
    if darks:
        axis = (min(darks) + max(darks)) / 2
    u1 = int(round(2 * axis - (u0 + 1)))   # 2×2-Auge spiegeln: linke Spalte des Spiegelbilds
    # geschlossenes Auge (Zwinkerstrich) im Fenster um das Spiegelauge durch Fell des Augenstreifs ersetzen
    stripe = base[v0 + 1, u0 - 1]
    for vv in range(v0 - 1, v0 + 3):
        for uu in range(u1 - 1, u1 + 3):
            if base[vv, uu] >= 0 and L[base[vv, uu]] < 0.45 and base[vv, uu] != outline_c:
                base[vv, uu] = stripe
    paint_eye(base, u1, v0)
    eyes_base = [(u0, v0), (u1, v0)]
    blink = base.copy()
    for u, v in eyes_base:
        blink[v, u] = stripe
        blink[v, u + 1] = stripe
        blink[v + 1, u] = BLACK_C
        blink[v + 1, u + 1] = BLACK_C
    # Winken: Bild 3 als Winkpose mit den Beinen der Grundpose (gleiche Fußzeilen in allen Stehbildern);
    # Bild 4 = Bild 3, nur der Kasten mit dem erhobenen Arm aus Bild 4 (sonst flimmert der ganze Körper,
    # weil sich die beiden KI-Bilder in 10-25 Pixeln je Zeile unterscheiden).
    legs = LEG_ROW_FRAC and int(round(CH * LEG_ROW_FRAC))
    wave_a = front[2].copy()
    wave_a[legs:] = base[legs:]
    wave_b = wave_a.copy()
    au, av = int(round(CW * ARM_BOX[0])), int(round(CH * ARM_BOX[1]))
    wave_b[:av, au:] = front[3][:av, au:]
    # Atmen wie bei klassischen Feldsprites: Oberkörper (über den Beinen) 1 px tiefer, Beine fest.
    # Für Blinzeln im Atemtakt ein eigenes Bild, sonst springt der Körper, wenn beides zusammenfällt.
    def breathe(src):
        out_ = src.copy()
        out_[1:legs] = src[0:legs - 1]
        out_[0] = -1
        return out_
    front_out = [base, blink, wave_a, wave_b, breathe(base), breathe(blink)]
    meta["front_leg_row"] = legs
    meta["front_arm_box"] = [au, av]
    meta["front_frames"] = ["stehen", "blinzeln", "winken_aussen", "winken_innen", "atmen", "atmen_blinzeln"]
    meta["front_eyes"] = eyes_base
    meta["front_axis"] = axis

    out_a = ROOT / "assets"
    out_d = ROOT / "demo" / "sprites"
    out_d.mkdir(parents=True, exist_ok=True)
    Image.fromarray(strip(walk, pal), "RGBA").save(out_a / "badger_walk.png")
    Image.fromarray(strip(front_out, pal), "RGBA").save(out_a / "badger_front.png")
    meta["palette_rgb"] = pal.tolist()
    (out_a / "badger.json").write_text(json.dumps(meta, indent=1))
    for n in ("badger_walk.png", "badger_front.png", "badger.json"):
        shutil.copy(out_a / n, out_d / n)
    if a.preview:
        rows = [strip(walk, pal), strip(front_out, pal), strip(front[:4], pal)]
        w = max(s.shape[1] for s in rows)
        canvas = np.zeros(((CH + 4) * len(rows), w, 3), np.uint8)
        canvas[...] = (60, 70, 90)
        for k, s in enumerate(rows):
            y0 = k * (CH + 4)
            al = s[..., 3:4] / 255.0
            canvas[y0:y0 + CH, :s.shape[1]] = (s[..., :3] * al + canvas[y0:y0 + CH, :s.shape[1]] * (1 - al)).astype(np.uint8)
        im = Image.fromarray(canvas, "RGB")
        im.resize((im.width * 4, im.height * 4), Image.NEAREST).save(a.preview)
    print(json.dumps({k: v for k, v in meta.items() if k not in ("palette_rgb",)}))


if __name__ == "__main__":
    main()
