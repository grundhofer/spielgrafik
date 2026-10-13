"""KI-Bild laden: in linearem Licht auf 320 Breite verkleinern, 144 Zeilen ausschneiden, Masken bilden.

Läuft ohne Handarbeit: Horizont, Kaikante, Himmel, Wasser, Leuchtfeuer, Laterne, Fenster und Schornstein werden
aus dem Bild bestimmt; die Suchbereiche kommen aus der Komposition, die der Prompt verlangt (HINTS, Anteile der
ganzen Bildhöhe/-breite). Jeder Wert lässt sich in einer Layout-Datei überschreiben (assets/ai_layout.json für
das Hafenbild, assets/closeup_layout.json für die Nahaufnahme; fehlt die Datei, gilt alles automatisch):

  crop_y            erste Zeile des Ausschnitts in der 320 px breiten Fassung (Standard: Mitte)
  sharpen           Unschärfemaske nach dem Verkleinern (0 = aus; Standard 0.5)
  horizon_y, water_bottom   Zeilen im Ausschnitt (Wasserband dazwischen)
  water_poly        Polygone (Bildpunkte im 320x144-Ausschnitt), ersetzen das automatische Wasserband
  water_exclude     Polygone, die trotz ähnlicher Farbe kein Wasser sind (Schatten von Booten, Steg)
  lamp / lantern    Rechteck [x0, y0, x1, y1]; darin werden helle, warme Pixel zum Animationsregister
  window            Liste von Rechtecken
  lamp_lmin, lantern_lmin, window_lmin   Helligkeitsschwelle (Oklab L) für die Rechtecke
  lamp_xy, lantern_xy, chimney_xy, feet_y, stop_x, gull_y, gull_x0
  sky_poly          Polygon des Himmels (Lichthof der Lampe)
  retouch           Rechtecke [x0, y0, x1, y1, "left"|"right"], die vor dem Dithering zeilenweise mit der Farbe
                    links bzw. rechts daneben gefüllt werden (z. B. trotz Prompt mitgemalter Rauch oder Strahl)
  green_poly        Polygone um Weste und Mütze (Nahaufnahme): daraus zwei feste grüne Register (build_assets.py),
                    sonst verteilt k-means kein Register auf das gedämpfte Grün und die Weste wird oliv-braun
  paint             Rechtecke [x0, y0, x1, y1, "rrggbb"], die nach dem Dithering das Register erhalten, das der Farbe
                    am nächsten liegt (z. B. das rote Band des Leuchtturms, das die Quantisierung sonst schwarz macht)
"""
import json
import pathlib
from collections import deque

import numpy as np
from PIL import Image, ImageDraw

from amiga import lin_to_srgb, oklab, srgb_to_lin

STYLE = pathlib.Path(__file__).resolve().parent.parent
W, H = 320, 144

# Komposition laut Prompt (assets/image_jobs.json), Anteile des ganzen Bildes (x: Breite, y: Höhe)
HINTS = {
    # sky_seed_x: Spalten über dem Horizont, in denen nur Himmel steht; water_seed_x: Spalten mit offener See
    # direkt unter dem Horizont (None = kein automatisches Wasser, nur water_poly aus der Layout-Datei)
    "bg": {"horizon": 0.50, "quay_edge": 0.64, "feet": 0.78, "lamp": (0.80, 0.26), "lantern": (0.30, 0.45),
           "window_max_x": 0.24, "chimney_max_x": 0.32, "stop_x": 0.44,
           "sky_seed_x": (0.42, 0.58), "water_seed_x": (0.30, 0.70)},
    # Nahaufnahme: der Dachs steht in der Mitte vor dem Horizont, deshalb Himmel nur von oben und kein
    # automatisches Wasser und Fenster (sonst liefe der Farbzyklus über Weste und Fell, das helle Hemd glimmte)
    "closeup": {"horizon": 0.50, "quay_edge": None, "feet": None, "lamp": (0.82, 0.30), "lantern": None,
                "window_max_x": None, "chimney_max_x": None, "stop_x": None,
                "sky_seed_x": None, "water_seed_x": None},
}


def poly_mask(polys):
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    for p in polys:
        d.polygon([tuple(v) for v in p], fill=255)
    return np.asarray(im) > 0


def bright_in(rgb, box, lmin):
    x0, y0, x1, y1 = box
    m = np.zeros((H, W), bool)
    lab = oklab(rgb[y0:y1, x0:x1].reshape(-1, 3)).reshape(y1 - y0, x1 - x0, 3)
    m[y0:y1, x0:x1] = (lab[..., 0] >= lmin) & (lab[..., 2] > 0.02)
    return m


def downscale(im, w=W):
    """BOX in linearem Licht: erst auf das Vierfache (Lanczos), dann je 4x4 mitteln. Höhe aus dem gemessenen
    Seitenverhältnis (agy liefert z. B. 1264x848 statt 1536x1024)."""
    h = round(w * im.height / im.width)
    big = np.asarray(im.resize((w * 4, h * 4), Image.LANCZOS), dtype=np.float64)
    return lin_to_srgb(srgb_to_lin(big).reshape(h, 4, w, 4, 3).mean((1, 3)))


def sharpen(rgb, amount):
    """Unschärfemaske (3x3-Kern): holt die beim Verkleinern verlorene Kantenschärfe zurück, damit das Dithering
    nicht zu Pixelbrei wird. Ränder wiederholt."""
    if amount <= 0:
        return rgb
    p = np.pad(rgb, ((1, 1), (1, 1), (0, 0)), mode="edge")
    k = np.array([[1, 2, 1], [2, 4, 2], [1, 2, 1]], dtype=np.float64) / 16.0
    blur = sum(k[dy, dx] * p[dy:dy + rgb.shape[0], dx:dx + rgb.shape[1]] for dy in range(3) for dx in range(3))
    return np.clip(rgb + amount * (rgb - blur), 0, 255)


def flood(lab, seeds, tol, allowed):
    """Flutfüllung mit Schrittschwelle: Nachbarpixel gehören dazu, wenn ihr Oklab-Abstand zum Vorgänger < tol ist
    (folgt weichen Verläufen wie dem Himmel, stoppt an Kanten)."""
    h, w = allowed.shape
    right = np.sqrt(((lab[:, 1:] - lab[:, :-1]) ** 2).sum(-1)) < tol
    down = np.sqrt(((lab[1:] - lab[:-1]) ** 2).sum(-1)) < tol
    m = np.zeros((h, w), bool)
    q = deque()
    for y, x in seeds:
        if allowed[y, x] and not m[y, x]:
            m[y, x] = True
            q.append((y, x))
    while q:
        y, x = q.popleft()
        for yy, xx, ok in ((y, x + 1, x + 1 < w and right[y, x]), (y, x - 1, x > 0 and right[y, x - 1]),
                           (y + 1, x, y + 1 < h and down[y, x]), (y - 1, x, y > 0 and down[y - 1, x])):
            if ok and allowed[yy, xx] and not m[yy, xx]:
                m[yy, xx] = True
                q.append((yy, xx))
    return m


def close_holes(m, n=2):
    """Kleine Löcher (Sterne, Wolkenkanten) schließen: n-mal dehnen, n-mal schrumpfen (4er-Nachbarschaft)."""
    def grow(a):
        b = a.copy()
        b[1:] |= a[:-1]; b[:-1] |= a[1:]; b[:, 1:] |= a[:, :-1]; b[:, :-1] |= a[:, 1:]
        return b
    def shrink(a):
        return ~grow(~a)
    out = m
    for _ in range(n):
        out = grow(out)
    for _ in range(n):
        out = shrink(out)
    return out | m


def components(mask):
    """Zusammenhängende Flächen (8er-Nachbarschaft): Liste von (ys, xs)."""
    seen = np.zeros_like(mask)
    out = []
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        q = deque([(y0, x0)])
        seen[y0, x0] = True
        ys, xs = [], []
        while q:
            y, x = q.popleft()
            ys.append(y); xs.append(x)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < mask.shape[0] and 0 <= xx < mask.shape[1] and mask[yy, xx] and not seen[yy, xx]:
                        seen[yy, xx] = True
                        q.append((yy, xx))
        out.append((np.array(ys), np.array(xs)))
    return out


def edge_row(lab, y_lo, y_hi, x_lo, x_hi):
    """Zeile mit der stärksten waagrechten Kante (Median der Zeilendifferenz über die Spalten x_lo..x_hi).
    Gibt die erste Zeile unterhalb der Kante zurück."""
    y_lo, y_hi = max(1, y_lo), min(lab.shape[0] - 1, y_hi)
    if y_hi <= y_lo:
        return None
    d = np.sqrt(((lab[y_lo:y_hi + 1, x_lo:x_hi] - lab[y_lo - 1:y_hi, x_lo:x_hi]) ** 2).sum(-1))
    return int(y_lo + np.argmax(np.median(d, 1)))


def warm_lights(lab, lmin=0.78, bmin=0.035):
    return (lab[..., 0] >= lmin) & (lab[..., 2] >= bmin)


def pick_light(comps, lab, xy, radius, max_area):
    """Hellste kleine warme Fläche nahe der erwarteten Lage."""
    best, score = None, -1.0
    for ys, xs in comps:
        if len(ys) > max_area:
            continue
        d = np.hypot(xs.mean() - xy[0], ys.mean() - xy[1])
        if d > radius:
            continue
        s = float(lab[ys, xs, 0].mean()) - d / (radius * 8.0)
        if s > score:
            best, score = (ys, xs), s
    return best


def load_ai(name="bg.png", layout=None, kind="bg", report=None):
    """Gibt (rgb 144x320x3 sRGB, masks) zurück. report: dict, in das die ermittelten Werte geschrieben werden."""
    lay_path = pathlib.Path(layout) if layout else STYLE / "assets" / ("ai_layout.json" if kind == "bg"
                                                                         else "closeup_layout.json")
    cfg = json.loads(lay_path.read_text()) if lay_path.exists() else {}
    hint = HINTS[kind]
    src = pathlib.Path(name) if pathlib.Path(name).is_absolute() else STYLE / "assets/raw" / name
    im = Image.open(src).convert("RGB")
    full = downscale(im)
    fh = full.shape[0]
    y0 = int(cfg.get("crop_y", round((fh - H) / 2)))
    y0 = max(0, min(fh - H, y0))
    rgb = sharpen(full[y0:y0 + H].copy(), float(cfg.get("sharpen", 0.5)))
    for x0, ya, x1, yb, side in cfg.get("retouch", []):
        s = x0 - 1 if side == "left" else x1
        for y in range(ya, yb):
            rgb[y, x0:x1] = rgb[y, s]
    lab = oklab(rgb.reshape(-1, 3)).reshape(H, W, 3)

    def row(frac):
        return None if frac is None else int(round(frac * fh - y0))

    # Horizont: stärkste waagrechte Kante in der Bildmitte nahe der erwarteten Zeile
    hz_hint = row(hint["horizon"])
    horizon = int(cfg.get("horizon_y", edge_row(lab, hz_hint - 12, hz_hint + 12, int(W * 0.35), int(W * 0.65))))
    # Himmel: Flutfüllung von der obersten Zeile und vom mittleren Streifen über dem Horizont (dort steht laut
    # Prompt nur Himmel), nur oberhalb des Horizonts; Sterne als Löcher schließen. Zwei Saatbereiche, damit auch
    # Himmel aus flachen Farbbändern mit harten Stufen ganz erfasst wird.
    if "sky_poly" in cfg:
        sky = poly_mask(cfg["sky_poly"])
    else:
        allowed = np.zeros((H, W), bool)
        allowed[:horizon] = True
        seeds = [(0, x) for x in range(W)]
        if hint["sky_seed_x"]:
            a, b = hint["sky_seed_x"]
            seeds += [(y, x) for y in range(horizon) for x in range(int(W * a), int(W * b))]
        sky = close_holes(flood(lab, seeds, 0.035, allowed), 2) & allowed
    # Wasser: Band zwischen Horizont und Kaikante, nur Pixel nahe der Zeilenfarbe (Boote, Steg, Felsen fallen raus)
    if "water_poly" in cfg:
        water = poly_mask(cfg["water_poly"])
        wb = int(cfg.get("water_bottom", np.flatnonzero(water.any(1)).max() + 1 if water.any() else horizon))
    elif not hint["water_seed_x"]:
        water = np.zeros((H, W), bool)
        wb = horizon
    else:
        qe = row(hint["quay_edge"])
        if "water_bottom" in cfg:
            wb = int(cfg["water_bottom"])
        elif qe is not None:
            wb = edge_row(lab, qe - 10, qe + 10, int(W * 0.15), int(W * 0.75)) or qe
        else:
            wb = H
        # erlaubt: Pixel nahe der Zeilenfarbe; Wasser = davon, was mit der offenen See in der Bildmitte unter dem
        # Horizont zusammenhängt (helle Hauswände links mit ähnlicher Farbe bleiben so draußen)
        near = np.zeros((H, W), bool)
        for y in range(horizon + 1, wb):
            med = np.median(lab[y], 0)
            near[y] = np.sqrt(((lab[y] - med) ** 2).sum(-1)) < 0.12
        a, b = hint["water_seed_x"]
        seeds = [(y, x) for y in range(horizon + 1, min(wb, horizon + 4)) for x in range(int(W * a), int(W * b))]
        water = flood(lab, seeds, 0.08, near)
    if cfg.get("water_exclude"):
        water &= ~poly_mask(cfg["water_exclude"])
    water &= ~sky

    # Lichter: helle, warme kleine Flächen
    comps = components(warm_lights(lab) & ~sky)
    def from_comp(c):
        m = np.zeros((H, W), bool)
        if c is not None:
            m[c] = True
        return m
    if "lamp" in cfg:
        lamp = bright_in(rgb, cfg["lamp"], cfg.get("lamp_lmin", 0.8))
    else:
        lx, ly = hint["lamp"][0] * W, row(hint["lamp"][1])
        lamp = from_comp(pick_light(comps, lab, (lx, ly), 45, 40))
    lantern = np.zeros((H, W), bool)
    if "lantern" in cfg:
        lantern = bright_in(rgb, cfg["lantern"], cfg.get("lantern_lmin", 0.75))
    elif hint["lantern"]:
        lx, ly = hint["lantern"][0] * W, row(hint["lantern"][1])
        lantern = from_comp(pick_light(comps, lab, (lx, ly), 36, 60))
    window = np.zeros((H, W), bool)
    if "window" in cfg:
        for box in cfg["window"]:
            window |= bright_in(rgb, box, cfg.get("window_lmin", 0.7))
    elif hint["window_max_x"]:
        for ys, xs in comps:
            if xs.mean() < hint["window_max_x"] * W and 3 <= len(ys) <= 120 and ys.mean() > 8:
                window[ys, xs] = True
    window &= ~lamp & ~lantern

    def centre(m, default):
        if not m.any():
            return [float(v) for v in default]
        ys, xs = np.nonzero(m)
        return [float(xs.mean()), float(ys.mean())]

    masks = {"water": water, "lamp": lamp, "lantern": lantern, "window": window, "sky": sky}
    lamp_hint = (hint["lamp"][0] * W, row(hint["lamp"][1]))
    masks["lamp_xy"] = cfg.get("lamp_xy", centre(lamp, lamp_hint))
    lt = hint["lantern"] or (0.3, 0.45)
    masks["lantern_xy"] = cfg.get("lantern_xy", centre(lantern, (lt[0] * W, row(lt[1]))))
    # Schornstein: schmale Spitze der oberen Kontur links (erste Nicht-Himmel-Zeile je Spalte)
    if "chimney_xy" in cfg:
        masks["chimney_xy"] = cfg["chimney_xy"]
    elif hint["chimney_max_x"]:
        top = np.array([np.argmax(~sky[:, x]) if (~sky[:, x]).any() else H for x in range(W)])
        xmax = int(hint["chimney_max_x"] * W)
        best, bx = 0, None
        for x in range(2, xmax):
            if top[x] > horizon - 25:
                continue
            nb = np.median(top[max(0, x - 9):x + 10])
            prot = nb - top[x]
            if prot > best:
                best, bx = prot, x
        if bx is None:
            bx = int(np.argmin(top[:xmax]))
        xs = [x for x in range(max(0, bx - 6), min(xmax, bx + 7)) if top[x] <= top[bx] + 1]
        masks["chimney_xy"] = [float(np.mean(xs)), float(top[bx]) - 1.0]
    else:
        masks["chimney_xy"] = [-50.0, -50.0]
    masks["feet_y"] = cfg.get("feet_y", (row(hint["feet"]) - 0.5) if hint["feet"] else H - 10)
    masks["stop_x"] = cfg.get("stop_x", int(round(hint["stop_x"] * W)) if hint["stop_x"] else W // 2)
    masks["gull_y"] = cfg.get("gull_y", max(6, int(horizon * 0.4)))
    masks["gull_x0"] = cfg.get("gull_x0", 300)
    masks["paint"] = cfg.get("paint", [])
    masks["green"] = poly_mask(cfg["green_poly"]) if cfg.get("green_poly") else np.zeros((H, W), bool)
    if report is not None:
        root = STYLE.parents[1]   # Projektordner: keine absoluten Pfade in den Bericht schreiben
        rel = src.resolve().relative_to(root).as_posix() if src.resolve().is_relative_to(root) else src.name
        report.update({"source": rel, "source_size": [im.width, im.height], "scaled_height": fh,
                       "crop_y": y0, "horizon_y": horizon, "water_bottom": int(wb),
                       "pixels": {k: int(masks[k].sum()) for k in ("water", "lamp", "lantern", "window", "sky")},
                       **{k: masks[k] for k in ("lamp_xy", "lantern_xy", "chimney_xy", "feet_y", "stop_x", "gull_y")}})
    return rgb, masks
