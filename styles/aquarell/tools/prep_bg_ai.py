#!/usr/bin/env python3
"""Bereitet den KI-Hintergrund (assets/raw/bg.png aus Auftrag 1) für die Demo auf, ohne Handarbeit:

  1. optional Bereiche übermalen (mitgemalter Rauch, Lichtstrahl …; Polygone aus der Korrekturdatei)
  2. Horizont, Himmel (vom oberen Rand gewachsen, je Spalte bis zur Silhouette gefüllt) und Wasser finden
  3. warme Lichtflecken finden: Leuchtturmlampe, Fenster, Laterne; Schornstein als höchster Punkt der Hütte
  4. Ausschnitt wählen: Lampe samt Dach im Bild, Laufzeile des Dachses bei y = 572 (Bildschirm, oder "feet_y" aus
     der Korrekturdatei); reicht die Höhe bei voller Breite nicht, wird verkleinert und seitlich bleibt Papier stehen
  4b. Farbe: im Pigmentmodell entsättigen, hellste Stellen als Papierweiß aussparen (grade, Prüfung 1)
  5. ausgeben (Bildschirmkoordinaten 1280x720):
       assets/bg_ai_painted.png, assets/sky_mask_ai.png, assets/water_mask_ai.png, assets/scene_ai.json
       assets/check/bg_ai_check.png  (Masken, Punkte, Laufzeile, Dachsgröße zum Ansehen)
       assets/check/bg_ai_grid.png   (Rohbild mit Koordinatengitter in Rohbild-Pixeln, für Korrekturen)

    .venv/bin/python styles/aquarell/tools/prep_bg_ai.py [--raw assets/raw/bg.png] [--out assets]
        [--override assets/bg_ai_override.json]

Korrekturdatei (alle Angaben optional, Koordinaten in Pixeln des Rohbilds, siehe bg_ai_grid.png):
  {"horizon": 470, "lamp": [x, y], "lantern": [x, y], "window": [x, y], "chimney": [x, y], "walk_y": 900,
   "top_y": 180, "water_seed": [[x, y], …], "water_y": [y0, y1], "inpaint": [[[x, y], …], …],
   "water_tol": 0.2, "water_grad": 0.05 (nur mit water_seed: jeder Keim wächst mit eigener Farbe),
   "sky_exclude": [[[x, y], …]], "badger_height": 150 (Bildschirm-px), "stop_x": 560 (Bildschirm-px),
   "window_glow_scale": 0.7, "lantern_glow_scale": 0.5, "lamp_glow_scale": 0.45, "smoke_alpha": 0.6,
   "feet_y": 550 (Bildschirm), "grade_sat": 0.78, "grade_white_pct": 3.0}
"""
import argparse, json, pathlib

import numpy as np
from PIL import Image, ImageDraw

import aqutil
import wc

ROOT = pathlib.Path(__file__).resolve().parents[1]
FEET_Y = 572.0          # Laufzeile des Dachses auf dem Bildschirm
VIG_TOP, VIG_SIDE, VIG_BOTTOM = 22.0, 18.0, 600.0   # Standardrand der Malfläche (finish_bg.py)


def hsv(rgb):
    mx, mn = rgb.max(-1), rgb.min(-1)
    d = mx - mn
    h = np.zeros_like(mx)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    nz = d > 1e-6
    i = nz & (mx == r)
    h[i] = ((g - b)[i] / d[i]) % 6
    i = nz & (mx == g) & ~(mx == r)
    h[i] = (b - r)[i] / d[i] + 2
    i = nz & (mx == b) & ~(mx == r) & ~(mx == g)
    h[i] = (r - g)[i] / d[i] + 4
    return h * 60.0, np.where(mx > 0, d / np.maximum(mx, 1e-6), 0), mx


def find_horizon(lum, H):
    """Zeile im Band 30–75 %, in der es über viele Spalten nach unten am stärksten dunkler wird (heller Himmel über
    dunklerem Wasser). Waagerechte Kanten, unter denen es heller wird (Kaikante), zählen nicht."""
    b = wc.blur(lum, max(1.5, H / 300))
    s = max(2, int(H / 200))
    d = np.zeros_like(b)
    d[s:-s] = b[2 * s:] - b[:-2 * s]
    prof = np.percentile(d, 30, axis=1)
    prof = wc.blur(prof[:, None], 1.5)[:, 0]
    y0, y1 = int(0.30 * H), int(0.75 * H)
    return float(y0 + int(np.argmin(prof[y0:y1])))


def gradient(rgb, sigma):
    b = wc.blur(rgb, sigma)
    gx = np.zeros(b.shape[:2])
    gy = np.zeros(b.shape[:2])
    gx[:, 1:-1] = np.abs(b[:, 2:] - b[:, :-2]).sum(-1) / 2
    gy[1:-1] = np.abs(b[2:] - b[:-2]).sum(-1) / 2
    return gx + gy


def grade(rgb, k, sat=0.78, white_pct=3.0, seed=11):
    """Prüfung 1 (Hintergrund zu bunt und ohne Papierweiß): im Pigmentmodell die Buntheit dämpfen (Dichten je Kanal
    zum Mittel hin) und die hellsten Stellen (Lichtband, Spiegelung, Fenster, Lampen, weiße Flächen) als ausgespartes
    Papier stehen lassen: hart begrenzt, Rand mit Rauschen verbogen, wie mit Maskierflüssigkeit gespart."""
    D = wc.density(np.clip(rgb, 1e-4, 1))
    Dm = D.mean(-1, keepdims=True)
    D = Dm + (D - Dm) * sat
    lin = wc.s2l(rgb)
    lum = (lin * [0.2126, 0.7152, 0.0722]).sum(-1)
    ls = wc.blur(lum, 1.2 * k)
    n = wc.value_noise(rgb.shape[0], rgb.shape[1], 6 * k, seed, 3)
    lv = ls * (0.94 + 0.12 * n)
    t = np.percentile(lv, 100 - white_pct)
    m = wc.blur((lv > t).astype(np.float64), 0.7 * k)
    D = D * (1 - 0.82 * m)[..., None]
    out = wc.l2s(wc.s2l(wc.PAPER) * np.exp(-D))
    return out, float((m > 0.5).mean())


def blur_xy(a, sx, sy):
    """Weichzeichnen mit getrennten Radien je Achse (drei Kastenfilter)."""
    out = a.astype(np.float64)
    rx, ry = max(1, int(round(sx * 0.93))), max(1, int(round(sy * 0.93)))
    for _ in range(3):
        out = wc._box(wc._box(out, ry, 0), rx, 1)
    return out


def silhouette(obj, horizon, gap):
    """Je Spalte: wie weit reichen Gegenstände vom Horizont lückenlos (Lücken bis gap Zeilen) nach oben?
    Gibt die oberste Zeile je Spalte zurück (= horizon, wo am Horizont freier Himmel ist)."""
    h, w = obj.shape
    y0 = int(min(h - 1, horizon))
    top = np.full(w, y0 + 1)
    alive = np.ones(w, bool)
    gp = np.zeros(w, int)
    for y in range(y0, -1, -1):
        o = obj[y]
        gp = np.where(o, 0, gp + 1)
        alive &= gp <= gap
        top = np.where(alive & o, y, top)
    return top


def grow(seed, allowed):
    """Bereichswachstum (4-Nachbarschaft) über erlaubte Pixel: abwechselnd ganze erlaubte Zeilen- und
    Spaltenstücke füllen, die schon einen Treffer enthalten, bis sich nichts mehr ändert."""
    m = seed & allowed
    for _ in range(500):
        prev = int(m.sum())
        for axis in (1, 0):
            A = allowed if axis == 1 else allowed.T
            M = m if axis == 1 else m.T
            key = np.cumsum(~A, axis=1) + np.arange(A.shape[0])[:, None] * (A.shape[1] + 1)
            hit = np.zeros(int(key.max()) + 1, bool)
            hit[key[M]] = True
            M2 = hit[key] & A
            m = M2 if axis == 1 else M2.T
        if int(m.sum()) == prev:
            break
    return m


def skyline_fill(sky, min_run):
    """Je Spalte: Himmel bis zur ersten Zeile, ab der min_run Zeilen lang kein Himmel folgt (Sterne, Blüten im
    Himmel füllen sich so)."""
    h, w = sky.shape
    out = np.zeros_like(sky)
    line = np.zeros(w, int)
    notsky = ~sky
    # Lauflänge "kein Himmel" ab jeder Zeile nach unten
    run = np.zeros((h + 1, w), int)
    for y in range(h - 1, -1, -1):
        run[y] = np.where(notsky[y], run[y + 1] + 1, 0)
    for x in range(w):
        ys = np.nonzero(run[:, x] >= min_run)[0]
        y = int(ys[0]) if len(ys) else h
        line[x] = y
        out[:y, x] = True
    return out & (np.arange(h)[:, None] < h), line


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(ROOT / "assets/raw/bg.png"))
    ap.add_argument("--out", default=str(ROOT / "assets"))
    ap.add_argument("--override", default=str(ROOT / "assets/bg_ai_override.json"))
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    (out / "check").mkdir(parents=True, exist_ok=True)
    ov = json.loads(pathlib.Path(a.override).read_text()) if pathlib.Path(a.override).exists() else {}
    feet_y_s = float(ov.get("feet_y") or FEET_Y)          # Laufzeile auf dem Bildschirm (Prüfung 1: 572 lag am Rand)
    src_im = Image.open(a.raw).convert("RGB")
    W, H = src_im.size
    k = W / 1280.0                                   # Rohbild-px je Bezugspixel
    rgb = np.asarray(src_im).astype(np.float64) / 255.0
    notes = []
    if ov.get("inpaint"):
        hole = aqutil.polygon_mask(W, H, ov["inpaint"])
        rgb = aqutil.fill_region(rgb, hole)
        notes.append(f"{len(ov['inpaint'])} Bereich(e) übermalt")
    lum = (rgb * [0.299, 0.587, 0.114]).sum(-1)

    # --- Horizont und Himmel ---------------------------------------------------------------------------------
    horizon = float(ov.get("horizon") or find_horizon(lum, H))
    yy = np.arange(H)[:, None] * np.ones((1, W))
    g = gradient(rgb, 3.0 * k)
    # Schwelle an die Textur des Himmels angepasst (Blüten, Körnung): 1,8-fach das 80. Perzentil oben im Bild
    thr = float(np.clip(1.8 * np.percentile(g[: int(0.1 * H)], 80), 0.012, 0.06))
    allowed = (g < thr) & (yy < horizon + 2)
    if ov.get("sky_exclude"):
        allowed &= ~aqutil.polygon_mask(W, H, ov["sky_exclude"])
    seed = np.zeros((H, W), bool)
    seed[:max(3, int(0.03 * H))] = True                 # obere Zeilen (ein gemalter Rand oben stört so nicht)
    sky_raw = grow(seed, allowed)
    # Himmelsfarbe als weiches Modell (quer stark, senkrecht wenig geglättet) aus den sicheren Himmelspixeln;
    # was deutlich davon abweicht und vom Horizont aus zusammenhängend nach oben reicht, ist Gegenstand
    # (Hütte, Leuchtturm, Masten). Wolken und Sterne hängen nicht am Horizont und bleiben Himmel.
    bl = wc.blur(rgb, 2.0 * k)
    base = sky_raw.copy()
    for _ in range(2):
        wgt = base.astype(np.float64)
        den = blur_xy(wgt, 60 * k, 8 * k)
        model = blur_xy(rgb * wgt[..., None], 60 * k, 8 * k) / np.maximum(den, 1e-6)[..., None]
        rowm = (rgb * wgt[..., None]).sum(1) / np.maximum(wgt.sum(1), 1)[:, None]
        for y in range(1, H):                                  # Zeilen ohne Himmel: Wert der Zeile darüber
            if wgt[y].sum() < 1:
                rowm[y] = rowm[y - 1]
        model = np.where(den[..., None] > 0.05, model, rowm[:, None, :])
        dev = np.sqrt(((bl - model) ** 2).sum(-1))
        obj = (dev > 0.09) & (yy < horizon + 2)
        top_obj = silhouette(obj, horizon + 1, max(3, int(6 * k)))
        sky = yy < top_obj[None, :]
        base = sky & (dev < 0.09)
    skyline = top_obj

    # --- Laufzeile, Wasser -----------------------------------------------------------------------------------
    walk_y = float(ov.get("walk_y") or 0.885 * H)
    wy0, wy1 = ov.get("water_y") or [horizon, walk_y - 0.06 * H]
    # Spalten mit freiem Blick aufs Meer: die niedrigsten Silhouetten (ein Lichtband am Horizont hebt sonst alle an)
    open_cols = np.nonzero(skyline >= min(horizon - 4 * k, np.percentile(skyline, 70) - 2 * k))[0]
    seeds = ov.get("water_seed") or [[int(x), int(horizon + 10 * k)] for x in open_cols[::max(1, int(30 * k))]]
    water = np.zeros((H, W), bool)
    if seeds:
        bl2 = wc.blur(rgb, 2.0 * k)
        cols = np.array([bl2[int(sy), int(sx)] for sx, sy in seeds])
        med = np.median(cols, 0)
        keep = np.sqrt(((cols - med) ** 2).sum(-1)) < 0.12
        seeds = [sd for sd, kk in zip(seeds, keep) if kk]
        dist = np.sqrt(((bl2 - med) ** 2).sum(-1))
        band = (yy >= horizon) & (yy < horizon + 30 * k)
        thr_w = float(np.clip(2.5 * np.percentile(g[band & (dist < 0.12)], 80) if (band & (dist < 0.12)).any() else 0.04,
                              0.015, 0.08))
        if ov.get("water_seed"):
            # von Hand gesetzte Keime: jeder wächst mit seiner eigenen Farbe (Wasser mit orangem Lichtband und
            # blauen Stellen hat keine gemeinsame Farbe); Gradientenschwelle optional aus der Korrekturdatei
            thr_w = float(ov.get("water_grad") or thr_w)
            tol = float(ov.get("water_tol") or 0.2)
            seeds = ov["water_seed"]
            for sx, sy in seeds:
                d_i = np.sqrt(((bl2 - bl2[int(sy), int(sx)]) ** 2).sum(-1))
                allowed_i = (g < thr_w) & (yy >= wy0) & (yy <= wy1) & (d_i < tol)
                s2 = np.zeros((H, W), bool)
                s2[int(sy) - 1:int(sy) + 2, int(sx) - 1:int(sx) + 2] = True
                water |= grow(s2, allowed_i)
        else:
            allowed_w = (g < thr_w) & (yy >= wy0) & (yy <= wy1) & (dist < 0.25)
            s2 = np.zeros((H, W), bool)
            for sx, sy in seeds:
                s2[int(sy) - 1:int(sy) + 2, int(sx) - 1:int(sx) + 2] = True
            water = grow(s2, allowed_w)
        water = wc.blur(water.astype(float), 3 * k) > 0.5            # schließen
    if not water.any():
        notes.append("keine Wassermaske gefunden (water_seed setzen)")

    # --- Lichtflecken -----------------------------------------------------------------------------------------
    sm = 2 if W > 900 else 1                                           # auf halber Größe suchen
    small = np.asarray(src_im.resize((W // sm, H // sm), Image.BOX)).astype(np.float64) / 255.0
    hh, ss, vv = hsv(small)
    loc = vv - wc.blur(vv, 30 / sm * k)
    warm = (hh >= 15) & (hh <= 65) & (ss >= 0.2) & (vv >= 0.7) & (loc >= 0.06)
    water_s = np.asarray(Image.fromarray(water.astype(np.uint8) * 255).resize(warm.shape[::-1])) > 0
    warm &= ~aqutil.dilate(water_s, 3)
    # benachbarte Flecken zusammenfassen (Fensterkreuz teilt ein Fenster in Scheiben)
    lab, comps = aqutil.components(aqutil.dilate(warm, max(1.0, 4 * k / sm)))
    cand = []
    debug = bool(__import__("os").environ.get("AQ_DEBUG"))
    for c in comps:
        bw, bh = (c["x1"] - c["x0"] + 1) * sm, (c["y1"] - c["y0"] + 1) * sm
        x, y = c["cx"] * sm, c["cy"] * sm
        if c["area"] * sm * sm < 4 * k * k or bw > 0.06 * W or bh > 0.10 * H or y > walk_y - 0.04 * H:
            continue
        if abs(y - horizon) < 0.02 * H and bw > 0.02 * W:
            continue                                                   # Stück vom Lichtband am Horizont
        m = (lab == c["id"]) & warm
        c["area"] = int(m.sum())
        cand.append({"x": x, "y": y, "w": bw, "h": bh, "area": c["area"] * sm * sm,
                     "loc": float(loc[m].max()), "v": float(vv[m].max()),
                     "fill": c["area"] / max(1, (c["x1"] - c["x0"] + 1) * (c["y1"] - c["y0"] + 1))})
        if debug:
            print("   Kandidat", {kk: round(v, 2) for kk, v in cand[-1].items()})
    # Zuordnung nach der im Prompt verlangten Komposition: Hütte am linken Rand, Leuchtturm bei etwa drei Vierteln
    # der Breite (Lampe deutlich über dem Horizont), Laterne etwas rechts der Mitte am hinteren Kairand.
    found = {}
    lamp_c = [c for c in cand if 0.5 * W < c["x"] < 0.97 * W and 0.03 * H < c["y"] < horizon - 0.08 * H]
    if lamp_c:
        found["lamp"] = max(lamp_c, key=lambda c: c["loc"] * c["v"] * (0.5 + c["fill"]))
    rest = [c for c in cand if c is not found.get("lamp")]
    win_c = [c for c in rest if c["x"] < 0.38 * W and horizon - 0.25 * H < c["y"] < walk_y - 0.06 * H]
    if win_c:
        found["window"] = max(win_c, key=lambda c: c["area"] * c["loc"])
    rest = [c for c in rest if c is not found.get("window")]
    lan_c = [c for c in rest if 0.38 * W < c["x"] < 0.92 * W and horizon - 0.15 * H < c["y"] < walk_y - 0.06 * H]
    if lan_c:
        found["lantern"] = max(lan_c, key=lambda c: c["loc"] * c["v"] * np.sqrt(c["area"]))
    pts, src = {}, {}
    fallback = {"lamp": (0.75 * W, horizon - 0.22 * H), "window": (0.10 * W, horizon + 0.02 * H),
                "lantern": (0.58 * W, horizon - 0.03 * H)}
    for name in ("lamp", "window", "lantern"):
        if ov.get(name):
            pts[name], src[name] = tuple(map(float, ov[name])), "Korrektur"
        elif name in found:
            pts[name], src[name] = (found[name]["x"], found[name]["y"]), "automatisch"
        else:
            pts[name], src[name] = fallback[name], "GERATEN"
            notes.append(f"{name}: nicht gefunden, geraten – in der Korrekturdatei setzen")
    # Schornstein: höchster breiterer Punkt der Silhouette links (dünne Masten durch Öffnen entfernt)
    if ov.get("chimney"):
        pts["chimney"], src["chimney"] = tuple(map(float, ov["chimney"])), "Korrektur"
    else:
        solid = aqutil.erode(~sky, 3 * k)
        line2 = np.array([int(np.argmax(solid[:, x])) if solid[:, x].any() else H for x in range(W)])
        wx = pts["window"][0]
        xa, xb = int(max(0, wx - 0.15 * W)), int(min(0.45 * W, wx + 0.22 * W))
        if xb > xa and line2[xa:xb].min() < horizon:
            xm = xa + int(np.argmin(line2[xa:xb]))
            ym = line2[xm]
            run = np.nonzero(np.abs(line2[xa:xb] - ym) <= 2 * k)[0] + xa
            run = run[np.abs(run - xm) < 0.04 * W]
            pts["chimney"], src["chimney"] = (float(run.mean()), float(ym + 2 * k)), "automatisch"
        else:
            pts["chimney"], src["chimney"] = (wx, horizon - 0.2 * H), "GERATEN"
            notes.append("chimney: nicht gefunden, geraten – in der Korrekturdatei setzen")

    # --- Ausschnitt und Maßstab ---------------------------------------------------------------------------------
    top_y = float(ov.get("top_y") or (pts["lamp"][1] - 0.075 * H))
    s_full = 1280.0 / W
    s_need = (feet_y_s - (VIG_TOP + 14)) / max(1.0, walk_y - top_y)
    s = min(s_full, s_need)
    if s < 0.8 * s_full:
        s = 0.8 * s_full
        notes.append("Lampe passt nicht ganz ins Bild (Maßstab auf 80 % begrenzt) – top_y/walk_y prüfen")
    ox = (1280.0 - W * s) / 2.0
    oy = feet_y_s - walk_y * s
    side = VIG_SIDE + max(0.0, ox)
    top = max(VIG_TOP, oy + 14)
    bottom = min(VIG_BOTTOM, oy + H * s - 16)
    if oy > 0:
        notes.append(f"Bild reicht oben nicht bis zum Rand (oy={oy:.0f}): Papier über dem Himmel")
    if bottom < feet_y_s + 20:
        notes.append("unter der Laufzeile bleibt zu wenig Bild – walk_y prüfen")

    def scr(p):
        return [round(p[0] * s + ox, 1), round(p[1] * s + oy, 1)]

    def place(arr, fill):
        """Rohbild-Array (H, W[, C]) auf die 1280x720-Fläche setzen."""
        im = Image.fromarray(arr)
        im = im.resize((max(1, round(W * s)), max(1, round(H * s))), Image.LANCZOS)
        canvas = Image.new(im.mode, (1280, 720), fill)
        canvas.paste(im, (round(ox), round(oy)))
        return canvas

    paper = tuple(int(c * 255) for c in wc.PAPER)
    graded, white_share = grade(rgb, k, float(ov.get("grade_sat", 0.78)), float(ov.get("grade_white_pct", 3.0)))
    notes_grade = f"Sättigung ×{ov.get('grade_sat', 0.78)}, Papierweiß {white_share:.1%}"
    painted = place((graded * 255 + 0.5).clip(0, 255).astype(np.uint8), paper)
    painted.save(out / "bg_ai_painted.png")
    sky_s = place((wc.blur(sky.astype(float), 1.0 * k) * 255).astype(np.uint8), 0)
    water_s = place((wc.blur(water.astype(float), 1.5 * k) * 255).astype(np.uint8), 0)
    sky_s.save(out / "sky_mask_ai.png")
    water_s.save(out / "water_mask_ai.png")

    hz = horizon * s + oy
    rows = np.nonzero((np.asarray(water_s) > 128).mean(1) > 0.02)[0]
    water_band = [float(rows.min()), float(rows.max())] if len(rows) else [hz, hz + 80]
    badger_h = float(ov.get("badger_height") or np.clip(0.69 * (feet_y_s - hz), 120, 200))
    sky_top = top + 20
    sky_bot = max(sky_top + 60, hz - 40)
    cy = lambda f: round(sky_top + f * (sky_bot - sky_top), 1)
    win = found.get("window")
    lan = found.get("lantern")
    scene = {
        "variant": "ai",
        "lamp": scr(pts["lamp"]), "lantern": scr(pts["lantern"]), "chimney": scr(pts["chimney"]),
        "window": scr(pts["window"]),
        "window_glow_scale": float(ov.get("window_glow_scale") or round(float(np.clip(
            (win["w"] * s if win and src["window"] == "automatisch" else 50) / 70, 0.3, 1.2)), 2)),
        "lantern_glow_scale": float(ov.get("lantern_glow_scale") or round(float(np.clip(
            (lan["w"] * s if lan and src["lantern"] == "automatisch" else 24) / 40, 0.35, 0.9)), 2)),
        "lamp_glow_scale": float(ov.get("lamp_glow_scale") or 1.0),
        "smoke_alpha": float(ov.get("smoke_alpha") or 0.5),
        "feet_y": feet_y_s, "horizon_y": round(hz, 1), "top": round(top, 1), "side": round(side, 1),
        "bottom": round(bottom, 1), "badger_height": round(badger_h, 1),
        "stop_x": float(ov.get("stop_x") or 560.0), "water_band": water_band,
        "clouds": [[0, 200.0, cy(0.05), 9.0, 0.55], [2, 760.0, cy(0.3), 7.0, 0.5], [1, 1100.0, cy(0.0), 10.0, 0.45],
                   [3, 480.0, cy(0.75), 4.5, 0.4], [4, 1000.0, cy(0.9), 4.0, 0.35]],
        "gulls": [[-40.0, cy(0.55), 58.0, 0.8, 0.0], [300.0, cy(0.25), 44.0, 0.6, 0.45]],
        "place": {"scale": round(s, 5), "ox": round(ox, 2), "oy": round(oy, 2), "raw_size": [W, H]},
        "sources": src, "notes": notes + [notes_grade],
    }
    (out / "scene_ai.json").write_text(json.dumps(scene, indent=1, ensure_ascii=False))

    # --- Prüfbilder -----------------------------------------------------------------------------------------------
    chk = np.asarray(painted).astype(np.float64) / 255
    sk = np.asarray(sky_s)[..., None] / 255.0
    wa = np.asarray(water_s)[..., None] / 255.0
    chk = chk * (1 - 0.3 * sk) + np.array([1.0, 0.2, 0.9]) * 0.3 * sk
    chk = chk * (1 - 0.4 * wa) + np.array([0.1, 0.9, 0.4]) * 0.4 * wa
    im = Image.fromarray((chk * 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    d.rectangle([side, top, 1280 - side, bottom], outline=(90, 90, 90))
    d.line([(0, feet_y_s), (1280, feet_y_s)], fill=(255, 0, 0), width=1)
    d.line([(0, hz), (1280, hz)], fill=(0, 0, 255), width=1)
    for name, col in (("lamp", (255, 220, 0)), ("window", (255, 120, 0)), ("lantern", (255, 0, 160)),
                      ("chimney", (0, 0, 0))):
        x, y = scr(pts[name])
        d.ellipse([x - 7, y - 7, x + 7, y + 7], outline=col, width=2)
        d.text((x + 9, y - 6), f"{name} ({src[name]})", fill=col)
    sx = scene["stop_x"]
    d.rectangle([sx - badger_h * 0.3, feet_y_s - badger_h, sx + badger_h * 0.3, feet_y_s], outline=(200, 0, 0))
    d.text((sx - 40, feet_y_s - badger_h - 14), "Dachs (Stopp)", fill=(200, 0, 0))
    for i, t in enumerate(notes):
        d.text((24, 30 + 14 * i), t, fill=(160, 0, 0))
    im.save(out / "check/bg_ai_check.png")
    grid = src_im.copy()
    d = ImageDraw.Draw(grid)
    step = 50 if W < 1400 else 100
    for x in range(0, W, step):
        d.line([(x, 0), (x, H)], fill=(255, 255, 255) if x % (step * 2) else (255, 0, 0), width=1)
        d.text((x + 2, 2), str(x), fill=(255, 0, 0))
    for y in range(0, H, step):
        d.line([(0, y), (W, y)], fill=(255, 255, 255) if y % (step * 2) else (255, 0, 0), width=1)
        d.text((2, y + 2), str(y), fill=(255, 0, 0))
    grid.save(out / "check/bg_ai_grid.png")
    print(f"ok: {W}x{H}, Horizont {horizon:.0f}, Maßstab {s:.3f} (voll {s_full:.3f}), Himmel {sky.mean():.1%}, "
          f"Wasser {water.mean():.1%}, Dachs {badger_h:.0f} px")
    for name in ("lamp", "window", "lantern", "chimney"):
        print(f"   {name:8s} roh {tuple(round(v) for v in pts[name])} -> {scr(pts[name])}  ({src[name]})")
    for t in notes:
        print("   HINWEIS:", t)


if __name__ == "__main__":
    main()
