#!/usr/bin/env python3
"""Asset-Aufbereitung für den Eintrag anime-visual-novel (nur Pillow + NumPy).

Aufruf aus dem Projektordner:
    .venv/bin/python styles/anime-visual-novel/tools/prep.py [sprite] [bg]        (ohne Argument: beides)
    .venv/bin/python styles/anime-visual-novel/tools/prep.py --raw DIR --test      (Probelauf mit Testbildern)

Eingaben aus assets/raw/ (Ziele der Bildaufträge in assets/image_jobs.json):
  sheet.png (+ sheet.keyed-src.png)   Auftrag 1: Figur zweimal, links neutral (A0), rechts freudig (A1)
  faces.png (+ faces.keyed-src.png)   Auftrag 3: Bearbeitung von Auftrag 1, links Augen zu + Mund offen (B0),
                                      rechts überrascht (B1)
  bg.png                              Auftrag 2: Hintergrund
Ausgaben: assets/badger_<fassung>.png, assets/bg.png, assets/sprite_report.json und Kopien in demo/art/ samt
demo/art/sprite.json und demo/art/layout.json. Mit --test nur demo/art/ (dazu demo/art/TESTBILDER.txt) und
die Prüfbilder; assets/ bleibt unberührt. Prüfbilder: assets/raw/debug/ bzw. <raw>/debug/.

sprite  VN-Baukasten wie bei geschichteten Standbildern: Körper immer aus A0, aus den anderen Bildern nur
        Gesichtsteile. Ablauf:
        1. Freistellen aus dem Magenta-Original (*.keyed-src.png) mit eigener Kantenreinigung (Farbsaum
           herausrechnen, Magenta-Stich im Randstreifen entfernen); fehlt es, das Alpha aus <name>.png.
        2. Blatt an der Lücke zwischen den Figuren teilen (Spaltendeckung), Figuren freischneiden.
        3. Ausrichten auf A0: Maßstab aus der Figurenhöhe (bei A1 zusätzlich ±1 % gesucht), Verschiebung per
           Suche (ganzzahlig, dann Parabel-Feinwert) über Kopf bzw. Figur ohne Gesichtsfeld; dann einmal affin
           mit vormultipliziertem Alpha neu abgetastet. B1 wird auf das ausgerichtete A1 gelegt (gleiche Herkunft).
        4. Gesichtsfeld aus A0 gemessen: Kopf = Silhouette über dem Schal (rote Zeilen), Mützenschirm = letzte
           Zeile vor dem hellen Stirnstreifen, Gesichtsfeld = Kopf ohne Ohren, vom Schirm bis knapp unter den
           Schalrand (ein offener Mund reicht oft bis in den Schal).
        5. Masken: Teile aus gleicher Herkunft (B0 auf A0, B1 auf A1) aus der Differenz (Schwelle, Öffnen,
           Löcher füllen, wachsen, weich), getrennt in Augen (oben) und Mund (unten) an der größten Zeilenlücke.
           Teile aus anderer Herkunft (A1/B1 auf A0) als Ellipse ins Gesichtsfeld, Augen = obere, Mund = untere
           Hälfte an derselben Trennlinie.
        6. Fassungen nach CONFIG["sprite"]["variants"] zusammensetzen, gemeinsam zuschneiden, mit
           vormultipliziertem Alpha auf Anzeigegröße verkleinern (1:1 in Godot, keine Filterung zur Laufzeit).
           Außerhalb der Masken sind alle Fassungen mit demselben Körper bitgleich.
bg      Hintergrund auf 1280 Breite skalieren, 720 Zeilen ausschneiden, Lichtquellen (Lampe, Fenster, Laterne),
        Horizont, Glitzerstellen und Sterne messen. Werte in tools/prep_config.json überschreiben die Messung.

Alle Zahlen lassen sich in tools/prep_config.json überschreiben (gleiche Struktur wie DEFAULTS).
"""
import argparse, copy, json, pathlib, shutil, sys

import numpy as np
from PIL import Image, ImageDraw

SD = pathlib.Path(__file__).resolve().parent.parent
ROOT = SD.parent.parent
ASSETS, ART = SD / "assets", SD / "demo" / "art"
CFG_FILE = SD / "tools" / "prep_config.json"
SCREEN = (1280, 720)
TEXTBOX_Y = 518          # Oberkante von Namensfeld/Textfenster in main.tscn (dort ist nichts mehr zu sehen)

DEFAULTS = {
    "key": {"tol": 70, "soft": 50, "despill": 2},
    "sprite": {
        "display_h": 760,       # Figurenhöhe (Mütze bis Füße) im Bild; Füße liegen unter dem Bildrand
        "center_x": 600,        # Mitte der Figur im Bild
        "top_y": 72,            # Oberkante der Mütze im Bild
        "max_upscale": 1.05,    # größerer Maßstab wird begrenzt (weiche Linien)
        "search": 16,           # Suchradius der Ausrichtung in Quellpixeln
        "face_box": None,       # [x0, y0, x1, y1] in A0-Koordinaten, überschreibt die Messung
        "split_y": None,        # Trennzeile Augen/Mund in A0-Koordinaten, überschreibt die Messung
        "diff_thr": 0.14,       # Schwelle der Differenzmaske (0..1, max. Kanal, vormultipliziert)
        "grow": 5,              # Masken wachsen um so viele Quellpixel
        "feather": 2.5,         # weicher Rand (Gauß-Sigma) der Differenzmasken
        "ellipse_feather": 7.0, # weicher Rand der Ellipsenmasken
        "min_part": 40,         # kleinere Differenzflecken werden verworfen (Pixel)
        # {"eyes": [x0, y0, x1, y1], "mouth": [...]} in A0-Koordinaten: Masken für alle Quellen (jede Herkunft)
        # aus der Differenz zum Körper, nur in diesen Rechtecken (überschreibt Trennzeile und Ellipsen)
        "regions": None,
        # Fassung: Körper (Feld) + Schichten [Quelle, Teil]; Teil = eyes | mouth | face
        "variants": {
            "neutral": {"body": "A0", "layers": []},
            "blink": {"body": "A0", "layers": [["B0", "eyes"]]},
            "talk": {"body": "A0", "layers": [["B0", "mouth"]]},
            "happy": {"body": "A0", "layers": [["A1", "face"]]},
            "happy_closed": {"body": "A0", "layers": [["A1", "eyes"]]},
            "surprised": {"body": "A0", "layers": [["B1", "face"]]},
        },
    },
    "bg": {
        "crop_y": None,          # obere Zeile des Ausschnitts im auf 1280 skalierten Bild (None: 30 % des Überstands)
        "lights": {},            # z. B. {"lamp": [1070, 140], "chimney": [70, 200]} überschreibt die Messung
        "window_r": None,
        "horizon": None,
        "beam_len": 560,
        "glints": 24,
        "stars": 10,             # Anzahl für die Messung oder Liste [[x, y], …] als Vorgabe
        "far_gulls": [[150, 170, 20, 0.3, 0.0], [930, 120, -14, 0.24, 0.5]],
        "choices": {"x": 800, "y": 360, "w": 420, "h": 50, "step": 50},
        # Retusche im Rohbild vor dem Skalieren: [[x0, y0, x1, y1], …] (Rohbild-Koordinaten, x1/y1 exklusiv).
        # Jede Spalte wird zwischen der Zeile über und unter dem Rechteck senkrecht überblendet (z. B.
        # Pseudo-Schrift auf einem Bootsrumpf mit waagerechten Planken).
        "retouch": [],
    },
}
LINEAGE = {"A0": "A0", "A1": "A1", "B0": "A0", "B1": "A1"}
MAGENTA = np.array([255.0, 0.0, 255.0], np.float32)


def deep_merge(a, b):
    out = copy.deepcopy(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict) and k != "variants":
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_cfg():
    if CFG_FILE.exists():
        return deep_merge(DEFAULTS, json.loads(CFG_FILE.read_text()))
    return copy.deepcopy(DEFAULTS)


def rel(p):
    try:
        return pathlib.Path(p).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


def save_png(arr_or_im, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    im = arr_or_im if isinstance(arr_or_im, Image.Image) else to_img(arr_or_im)
    im.save(path, optimize=True)
    print(f"  {rel(path)}  {im.size[0]}x{im.size[1]}")


# --- kleine Bildwerkzeuge -------------------------------------------------------------------------

def gauss(a, sigma):
    """Separabler Gauß auf 2D-float (Pillow kann Modus F nicht weichzeichnen)."""
    if sigma <= 0:
        return a
    r = max(1, int(3 * sigma))
    x = np.arange(-r, r + 1, dtype=np.float32)
    k = np.exp(-x * x / (2 * sigma * sigma))
    k /= k.sum()
    p = np.pad(a, r, mode="edge")
    p = np.apply_along_axis(lambda v: np.convolve(v, k, mode="valid"), 1, p)
    p = np.apply_along_axis(lambda v: np.convolve(v, k, mode="valid"), 0, p)
    return p


def dilate(m, r):
    if r <= 0:
        return m
    out = m.copy()
    for _ in range(r):
        g = out.copy()
        g[1:] |= out[:-1]; g[:-1] |= out[1:]; g[:, 1:] |= out[:, :-1]; g[:, :-1] |= out[:, 1:]
        out = g
    return out


def erode(m, r):
    return ~dilate(~m, r)


def fill_holes(m):
    """Löcher (vom Rand aus nicht erreichbare Nullflächen) füllen."""
    im = Image.fromarray(np.pad(m, 1).astype(np.uint8) * 255).copy()  # fromarray-Bilder füllt floodfill nicht
    ImageDraw.floodfill(im, (0, 0), 128)
    a = np.asarray(im)[1:-1, 1:-1]
    return a != 128


def premul(a):
    return np.concatenate([a[..., :3] * a[..., 3:4], a[..., 3:4]], -1)


def unpremul(p):
    al = p[..., 3:4]
    rgb = np.where(al > 1e-4, p[..., :3] / np.maximum(al, 1e-4), 0.0)
    return np.concatenate([rgb.clip(0, 1), al.clip(0, 1)], -1)


def to_img(arr):
    return Image.fromarray((arr * 255).round().clip(0, 255).astype(np.uint8), "RGBA")


def warp(arr, s, tx, ty, size):
    """Affine Abbildung x' = s*x + t (vormultipliziert, bikubisch) auf eine Fläche size=(w, h)."""
    p = premul(arr)
    data = (1 / s, 0, -tx / s, 0, 1 / s, -ty / s)
    ch = [np.asarray(Image.fromarray(np.ascontiguousarray(p[..., i]), "F")
                     .transform(size, Image.AFFINE, data, resample=Image.BICUBIC)) for i in range(4)]
    return unpremul(np.stack(ch, -1).clip(0, 1))


def resize(arr, size):
    p = premul(arr)
    ch = [np.asarray(Image.fromarray(np.ascontiguousarray(p[..., i]), "F").resize(size, Image.LANCZOS))
          for i in range(4)]
    return unpremul(np.stack(ch, -1).clip(0, 1))


def bbox(alpha, thr=0.5):
    ys, xs = np.where(alpha > thr)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def runs(flags, min_gap=1):
    idx = np.flatnonzero(flags)
    if idx.size == 0:
        return []
    out, s, p = [], idx[0], idx[0]
    for i in idx[1:]:
        if i - p > min_gap:
            out.append((int(s), int(p) + 1))
            s = i
        p = i
    out.append((int(s), int(p) + 1))
    return out


# --- Freistellen ----------------------------------------------------------------------------------

def key_magenta(rgb, kc):
    """rgb: HxWx3 uint8 auf Magenta -> RGBA float 0..1 (Saum entmischt, Magenta-Stich im Rand entfernt)."""
    im = rgb.astype(np.float32)
    dist = np.sqrt(((im - MAGENTA) ** 2).sum(-1))
    alpha = np.clip((dist - kc["tol"]) / max(1, kc["soft"]), 0, 1)
    out = im.copy()
    semi = (alpha > 0) & (alpha < 1)
    a3 = alpha[semi][:, None]
    out[semi] = np.clip((im[semi] - MAGENTA * (1 - a3)) / np.maximum(a3, 0.05), 0, 255)
    band = dilate(alpha < 1, int(kc["despill"])) & (alpha > 0)
    excess = np.clip(np.minimum(out[..., 0], out[..., 2]) - out[..., 1], 0, None) * band
    out[..., 0] -= excess
    out[..., 2] -= excess
    return np.concatenate([out / 255.0, alpha[..., None]], -1).astype(np.float32)


def load_keyed(raw, name, kc):
    src = raw / f"{name}.keyed-src.png"
    if src.exists():
        arr = key_magenta(np.asarray(Image.open(src).convert("RGB")), kc)
        how = f"{src.name} (eigenes Freistellen)"
    elif (raw / f"{name}.png").exists():
        arr = np.asarray(Image.open(raw / f"{name}.png").convert("RGBA")).astype(np.float32) / 255.0
        # Codex liefert die Figur mit Alpha 250–254 statt 255 (Hintergrund scheint ~1 % durch) und einen kaum
        # sichtbaren Schein mit Alpha 1–2 um die Figur: auf voll deckend bzw. ganz transparent setzen.
        al = arr[..., 3]
        al[al >= 250 / 255 - 1e-6] = 1.0
        al[al <= 2 / 255 + 1e-6] = 0.0
        n = al.size
        how = (f"{name}.png (Alpha wie geliefert, >= 250 -> 255, <= 2 -> 0: {100 * (al == 0).sum() / n:.1f} %"
               f" transparent, {100 * (al == 1).sum() / n:.1f} % deckend,"
               f" {100 * ((al > 0) & (al < 1)).sum() / n:.1f} % dazwischen)")
    else:
        return None, None
    return arr, how


# --- Figuren --------------------------------------------------------------------------------------

def split_panels(arr):
    """Blatt in linke/rechte Figur teilen. Gibt [(Figur-RGBA, x-Versatz im Blatt), …] und die Schnittspalte."""
    solid = arr[..., 3] > 0.5
    cov = solid.sum(0)
    W = arr.shape[1]
    lo, hi = int(W * 0.3), int(W * 0.7)
    gaps = [(a + lo, b + lo) for a, b in runs(cov[lo:hi] < 3)]
    if gaps:
        a, b = min(gaps, key=lambda g: abs((g[0] + g[1]) / 2 - W / 2))
        cut = (a + b) // 2
    else:
        lo2, hi2 = int(W * 0.35), int(W * 0.65)
        cut = lo2 + int(np.argmin(cov[lo2:hi2]))
        print(f"  WARNUNG: keine Lücke zwischen den Figuren, Schnitt an der dünnsten Spalte x={cut}")
    out = []
    for x0, x1 in ((0, cut), (cut, W)):
        part = arr[:, x0:x1].copy()
        s = part[..., 3] > 0.5
        cols = np.flatnonzero(s.sum(0) >= 3)
        rows = np.flatnonzero(s.sum(1) >= 3)
        bx0, bx1, by0, by1 = cols[0], cols[-1] + 1, rows[0], rows[-1] + 1
        # nur die Figur behalten (Krümel außerhalb des Rechtecks verwerfen)
        keep = np.zeros(s.shape, bool)
        keep[by0:by1, bx0:bx1] = True
        part[~keep] = 0
        out.append((part, x0))
    return out, cut


def pad(arr, p):
    return np.pad(arr, ((p, p), (p, p), (0, 0)))


def geometry(a0, cfg):
    """Kopf, Mützenschirm, Schal und Gesichtsfeld der neutralen Figur (Koordinaten der A0-Fläche)."""
    rgb, al = a0[..., :3], a0[..., 3]
    solid = al > 0.5
    x0, top, x1, bot = bbox(al)
    h = bot - top
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    red = solid & (r > 0.45) & (g < 0.32) & (b < 0.36) & (r - g > 0.22)
    width = np.maximum(solid.sum(1), 1)
    scarf_rows = np.flatnonzero((red.sum(1) / width > 0.12) & (np.arange(len(width)) > top + 0.12 * h))
    scarf_top = int(scarf_rows[0]) if scarf_rows.size else int(top + 0.30 * h)
    head = solid[top:scarf_top]
    cols = np.flatnonzero(head.sum(0) > 0)
    hx0, hx1 = int(cols[0]), int(cols[-1]) + 1
    hh = scarf_top - top
    hw = hx1 - hx0
    # Mützenschirm: Unter dem Schirm beginnt der helle Mittelstreifen der Stirn (Dachszeichnung). Erste Zeile
    # ab 10 % Kopfhöhe, in der ein schmaler Mittelstreifen drei Zeilen lang überwiegend hell ist.
    cx = (hx0 + hx1) // 2
    strip = slice(cx - max(3, int(0.06 * hw)), cx + max(3, int(0.06 * hw)) + 1)
    lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    light = ((lum[:, strip] > 0.62) & solid[:, strip]).mean(1) > 0.6
    cap_bottom, cap_found = top + int(0.3 * hh), False
    for y in range(top + int(0.1 * hh), top + int(0.7 * hh)):
        if light[y:y + 3].all():
            cap_bottom, cap_found = y, True
            break
    # Gesichtsfeld: ohne Ohren (17 % je Seite), vom Schirm bis unter den Schalrand (offener Mund ragt hinein)
    fb = [int(hx0 + 0.17 * hw), int(cap_bottom - 0.02 * hh), int(hx1 - 0.17 * hw), int(scarf_top + 0.12 * hh)]
    if cfg.get("face_box"):
        fb = [int(v) for v in cfg["face_box"]]
    return {"figure": [x0, top, x1, bot], "height": h, "head": [hx0, top, hx1, scarf_top],
            "cap_bottom": cap_bottom, "scarf_top": scarf_top, "face_box": fb,
            "measured": {"scarf": bool(scarf_rows.size), "cap": cap_found}}


def cost(ref_p, mov_p, region, dx, dy):
    """Mittlere Abweichung (vormultipliziert) im Bereich region, wenn mov um (dx, dy) verschoben wird."""
    m = np.roll(np.roll(mov_p, dy, 0), dx, 1)
    return float(np.abs(m - ref_p).sum(-1)[region].mean())


def register(mov, ref, region, search, scales=(0.0,)):
    """Legt mov auf ref (gleiche Fläche wie ref). Gibt (ausgerichtet, Parameter)."""
    H, W = ref.shape[:2]
    bm, br = bbox(mov[..., 3]), bbox(ref[..., 3])
    s0 = (br[3] - br[1]) / (bm[3] - bm[1])
    ref_p = premul(ref)[::2, ::2]
    reg2 = region[::2, ::2]
    best = None
    for ds in scales:
        s = s0 * (1 + ds)
        tx0 = (br[0] + br[2]) / 2 - s * (bm[0] + bm[2]) / 2
        ty0 = br[1] - s * bm[1]
        w = warp(mov, s, tx0, ty0, (W, H))
        wp = premul(w)[::2, ::2]
        r2 = max(1, search // 2)
        grid = {}
        for dy in range(-r2, r2 + 1):
            for dx in range(-r2, r2 + 1):
                grid[(dx, dy)] = cost(ref_p, wp, reg2, dx, dy)
        (dx, dy), c = min(grid.items(), key=lambda kv: kv[1])
        if best is None or c < best[0]:
            best = (c, s, tx0 + 2 * dx, ty0 + 2 * dy)
    c, s, tx, ty = best
    # Feinsuche in voller Auflösung: ganzzahlig ±2, dann Parabel je Achse
    w = warp(mov, s, tx, ty, (W, H))
    ref_f, w_f = premul(ref), premul(w)
    grid = {(dx, dy): cost(ref_f, w_f, region, dx, dy) for dx in range(-2, 3) for dy in range(-2, 3)}
    (dx, dy), c = min(grid.items(), key=lambda kv: kv[1])

    def para(cm, c0, cp):
        d = cm - 2 * c0 + cp
        return 0.0 if d <= 1e-9 else float(np.clip(0.5 * (cm - cp) / d, -0.5, 0.5))
    fx = para(grid.get((dx - 1, dy), c), c, grid.get((dx + 1, dy), c)) if abs(dx) < 2 else 0.0
    fy = para(grid.get((dx, dy - 1), c), c, grid.get((dx, dy + 1), c)) if abs(dy) < 2 else 0.0
    tx, ty = tx + dx + fx, ty + dy + fy
    out = warp(mov, s, tx, ty, (W, H))
    resid = float(np.abs(premul(out) - ref_f).sum(-1)[region].mean())
    return out, {"scale": round(s, 5), "tx": round(tx, 2), "ty": round(ty, 2), "residual": round(resid, 4)}


def diff_parts(src, base, geo, cfg):
    """Differenzmaske (gleiche Herkunft) im Gesichtsfeld, getrennt in Augen und Mund."""
    x0, y0, x1, y1 = geo["face_box"]
    hh = geo["head"][3] - geo["head"][1]
    m = int(0.12 * hh)
    d = np.abs(premul(src)[..., :3] - premul(base)[..., :3]).max(-1)
    d = gauss(d, 1.2)
    raw = d > cfg["diff_thr"]
    box = np.zeros(raw.shape, bool)
    box[max(0, y0 - m):y1 + m, max(0, x0 - m):x1 + m] = True
    raw &= box
    raw = dilate(erode(raw, 1), 1)
    prof = raw.sum(1)
    rr = [r for r in runs(prof > 0, min_gap=3) if prof[r[0]:r[1]].sum() >= cfg["min_part"]]
    if cfg.get("split_y") is not None:
        split, how = int(cfg["split_y"]), "Vorgabe"
    elif len(rr) >= 2:
        split, how = (rr[-2][1] + rr[-1][0]) // 2, "Zeilenlücke"
    else:
        split, how = int(y0 + 0.58 * (y1 - y0)), "Anteil 58 % (keine Lücke gefunden)"
    rows = np.arange(raw.shape[0])[:, None]
    parts = {}
    for name, sel in (("eyes", rows < split), ("mouth", rows >= split)):
        p = raw & sel
        if p.sum() < cfg["min_part"]:
            parts[name] = None
            continue
        p = fill_holes(dilate(p, int(cfg["grow"])))
        p &= sel if name == "eyes" else (rows >= split - int(cfg["grow"]))
        parts[name] = gauss(p.astype(np.float32), cfg["feather"]).clip(0, 1)
    face = fill_holes(dilate(raw, int(cfg["grow"])))
    parts["face"] = gauss(face.astype(np.float32), cfg["feather"]).clip(0, 1) if face.any() else None
    info = {"split_y": split, "split_from": how, "runs": rr, "changed_px": int(raw.sum())}
    return parts, info


def region_parts(src, base, regions, cfg):
    """Differenzmaske (beliebige Herkunft, auf base ausgerichtet) nur in den Rechtecken regions["eyes"/"mouth"].
    Kleine Flecken (Linienzittern der KI-Bearbeitung) fallen weg; die Maskenkante liegt dort, wo beide Bilder
    übereinstimmen, deshalb keine sichtbare Naht."""
    d = gauss(np.abs(premul(src)[..., :3] - premul(base)[..., :3]).max(-1), 1.2)
    raw = dilate(erode(d > cfg["diff_thr"], 1), 1)
    parts, info, union = {}, {}, np.zeros(raw.shape, bool)
    for name in ("eyes", "mouth"):
        x0, y0, x1, y1 = [int(v) for v in regions[name]]
        sel = np.zeros(raw.shape, bool)
        sel[y0:y1, x0:x1] = True
        p = np.zeros(raw.shape, bool)
        for ys, xs in components(raw & sel):
            if len(ys) >= cfg["min_part"]:
                p[ys, xs] = True
        info[name] = int(p.sum())
        if not p.any():
            parts[name] = None
            continue
        p = fill_holes(dilate(p, int(cfg["grow"]))) & sel
        union |= p
        parts[name] = gauss(p.astype(np.float32), cfg["feather"]).clip(0, 1)
    parts["face"] = gauss(union.astype(np.float32), cfg["feather"]).clip(0, 1) if union.any() else None
    return parts, {"changed_px": info, "regions": regions}


def ellipse_parts(shape, geo, split, cfg):
    x0, y0, x1, y1 = geo["face_box"]
    im = Image.new("L", (shape[1], shape[0]), 0)
    ImageDraw.Draw(im).ellipse([x0, y0, x1, y1], fill=255)
    e = np.asarray(im) > 127
    rows = np.arange(shape[0])[:, None]
    out = {}
    for name, sel in (("face", np.ones_like(e)), ("eyes", rows < split), ("mouth", rows >= split)):
        out[name] = gauss((e & sel).astype(np.float32), cfg["ellipse_feather"]).clip(0, 1)
    return out


def sprite(raw, test, dbg_dir):
    cfg_all = load_cfg()
    cfg, kc = cfg_all["sprite"], cfg_all["key"]
    print("Figur")
    sheet, how_s = load_keyed(raw, "sheet", kc)
    if sheet is None:
        print("  sheet fehlt – übersprungen")
        return None
    faces, how_f = load_keyed(raw, "faces", kc)
    if faces is not None and faces.shape[:2] != sheet.shape[:2]:
        print(f"  faces {faces.shape[1]}x{faces.shape[0]} -> {sheet.shape[1]}x{sheet.shape[0]}")
        faces = resize(faces, (sheet.shape[1], sheet.shape[0]))
    report = {"sheet": how_s, "faces": how_f, "source_size": [sheet.shape[1], sheet.shape[0]]}
    ((A0, _), (A1, _)), report["sheet_cut"] = split_panels(sheet)
    P = 48
    A0 = pad(A0, P)
    H, W = A0.shape[:2]
    fig = {"A0": A0}
    geo = geometry(A0, cfg)
    report["geometry"] = geo
    fb = geo["face_box"]
    hh = geo["head"][3] - geo["head"][1]
    noface = np.ones((H, W), bool)
    m = int(0.10 * hh)
    noface[max(0, fb[1] - m):fb[3] + m, max(0, fb[0] - m):fb[2] + m] = False
    head_region = np.zeros((H, W), bool)
    head_region[max(0, geo["head"][1] - 8):geo["scarf_top"] + int(0.15 * hh),
                max(0, geo["head"][0] - 8):geo["head"][2] + 8] = True
    solid0 = dilate(A0[..., 3] > 0.05, 4)
    reg = {}
    a1 = pad(A1, P)
    fig["A1"], reg["A1"] = register(a1, A0, head_region & noface & dilate(solid0, 6), cfg["search"],
                                    scales=(-0.01, -0.005, 0.0, 0.005, 0.01))
    if faces is not None:
        (B0, _), (B1, _) = split_panels(faces)[0]
        fig["B0"], reg["B0"] = register(pad(B0, P), A0, solid0 & noface, cfg["search"])
        solid1 = dilate(fig["A1"][..., 3] > 0.05, 4)
        fig["B1"], reg["B1"] = register(pad(B1, P), fig["A1"], solid1 & noface, cfg["search"])
    report["registration"] = reg
    for k, v in reg.items():
        print(f"  {k} -> {'A1' if k == 'B1' else 'A0'}: Maßstab {v['scale']}, Versatz {v['tx']:+.2f}/{v['ty']:+.2f},"
              f" Restfehler {v['residual']}")
    # Masken
    masks, mask_info = {}, {}
    if "B0" in fig:
        masks["B0"], mask_info["B0"] = diff_parts(fig["B0"], A0, geo, cfg)
    split = mask_info.get("B0", {}).get("split_y") or cfg.get("split_y") or int(fb[1] + 0.58 * (fb[3] - fb[1]))
    if "B1" in fig:
        masks["B1"], mask_info["B1"] = diff_parts(fig["B1"], fig["A1"], geo, dict(cfg, split_y=split))
    ell = ellipse_parts((H, W), geo, split, cfg)
    report["masks"] = {k: {kk: vv for kk, vv in v.items()} for k, v in mask_info.items()}
    report["split_y"] = split
    regions = cfg.get("regions")
    reg_masks = {}
    if regions:
        geo["regions"] = regions
        report["masks"]["regions"] = {}
    # Fassungen
    out, used = {}, {}
    for name, spec in cfg["variants"].items():
        body = spec["body"]
        if body not in fig:
            print(f"  {name}: Körper {body} fehlt – übersprungen")
            continue
        comp = premul(fig[body])
        ok, desc = True, []
        for src, part in spec.get("layers", []):
            if src not in fig:
                ok = False
                desc.append(f"{src} fehlt")
                break
            same = LINEAGE[src] == LINEAGE[body]
            if regions:
                if (src, body) not in reg_masks:
                    reg_masks[(src, body)], ri = region_parts(fig[src], fig[body], regions, cfg)
                    report["masks"]["regions"][f"{src}->{body}"] = ri["changed_px"]
                    print(f"  Maske {src} -> {body} (Bereiche): {ri['changed_px']}")
                mk = reg_masks[(src, body)].get(part)
            else:
                mk = masks.get(src, {}).get(part) if same else ell[part]
            if mk is None:
                ok = False
                desc.append(f"{src}/{part}: keine Änderung gefunden")
                break
            comp = comp * (1 - mk[..., None]) + premul(fig[src]) * mk[..., None]
            desc.append(f"{src}/{part} ({'Bereich' if regions else 'Differenz' if same else 'Ellipse'})")
        if not ok:
            print(f"  {name}: übersprungen ({'; '.join(desc)})")
            continue
        out[name] = unpremul(comp)
        used[name] = desc
        print(f"  {name}: {body}" + (" + " + ", ".join(desc) if desc else ""))
    # gemeinsamer Zuschnitt und Anzeigegröße
    ua = np.zeros((H, W), bool)
    for v in out.values():
        ua |= v[..., 3] > 0.01
    cx0, cy0, cx1, cy1 = bbox(ua.astype(np.float32))
    cx0, cy0, cx1, cy1 = max(0, cx0 - 6), max(0, cy0 - 6), min(W, cx1 + 6), min(H, cy1 + 6)
    k = cfg["display_h"] / geo["height"]
    if k > cfg["max_upscale"]:
        print(f"  WARNUNG: Maßstab {k:.3f} > {cfg['max_upscale']}, begrenzt (Figur kleiner als display_h)")
        k = cfg["max_upscale"]
    size = (round((cx1 - cx0) * k), round((cy1 - cy0) * k))
    gx0, gy0, gx1, _ = geo["figure"]
    pos = [round(cfg["center_x"] - ((gx0 + gx1) / 2 - cx0) * k), round(cfg["top_y"] - (gy0 - cy0) * k)]

    def disp(box):
        return [round((box[0] - cx0) * k), round((box[1] - cy0) * k), round((box[2] - cx0) * k),
                round((box[3] - cy0) * k)]
    smalls = {}
    for name, v in out.items():
        smalls[name] = resize(v[cy0:cy1, cx0:cx1], size)
    # Prüfung: außerhalb der Masken bitgleich zur Fassung mit gleichem Körper (in Anzeigegröße)
    changed = {}
    for name, v in smalls.items():
        ref = smalls.get("neutral") if cfg["variants"][name]["body"] == "A0" else None
        if ref is None or name == "neutral":
            continue
        dd = np.abs((v * 255).round() - (ref * 255).round()).max(-1) > 0
        ys, xs = np.where(dd)
        changed[name] = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1] if xs.size else None
    report.update({"variants": used, "display_scale": round(k, 4), "crop": [cx0, cy0, cx1, cy1],
                   "display_size": list(size), "display_pos": pos, "face_box_display": disp(fb),
                   "head_display": disp(geo["head"]), "changed_box_display": changed})
    # schreiben
    names = list(smalls)
    for name, v in smalls.items():
        im = to_img(v)
        if not test:
            save_png(im, ASSETS / f"badger_{name}.png")
        save_png(im, ART / f"badger_{name}.png")
    # nicht mehr erzeugte Fassungen entfernen, damit demo/art/ und sprite.json übereinstimmen
    for d in ([ART] if test else [ART, ASSETS]):
        for f in d.glob("badger_*.png"):
            if f.stem[len("badger_"):] not in names:
                f.unlink()
                f.with_name(f.name + ".import").unlink(missing_ok=True)
                print(f"  entfernt: {rel(f)}")
    hd = disp(geo["head"])
    sj = {"pos": pos, "size": list(size), "variants": names, "face_box": disp(fb), "head": hd,
          "emote": [hd[2] - round(0.05 * (hd[2] - hd[0])), hd[1] + round(0.3 * (hd[3] - hd[1]))],  # Ohrhöhe: Striche bleiben beim Hüpfer im Bild
          "test_images": bool(test)}
    if regions:   # Bereiche der Gesichtsteile (Anzeigekoordinaten); measure.py erlaubt Änderungen nur in Kopf + Bereichen
        sj["regions"] = {k: disp(v) for k, v in regions.items()}
    (ART / "sprite.json").write_text(json.dumps(sj, indent=1) + "\n")
    print(f"  demo/art/sprite.json: Lage {pos}, Größe {size[0]}x{size[1]}, Maßstab {k:.3f}, Fassungen {names}")
    if not test:
        (ASSETS / "sprite_report.json").write_text(json.dumps(report, indent=1) + "\n")
    debug_sprite(dbg_dir, fig, out, masks, ell, geo, split, report, reg_masks)
    return sj


def debug_sprite(dbg_dir, fig, out, masks, ell, geo, split, report, reg_masks=None):
    """Prüfbild: Köpfe aller Fassungen in Quellauflösung, Masken rot, Gesichtsfeld und Trennlinie."""
    dbg_dir.mkdir(parents=True, exist_ok=True)
    hx0, hy0, hx1, hy1 = geo["head"]
    hh = hy1 - hy0
    box = (hx0 - 10, hy0 - 10, hx1 + 10, hy1 + int(0.25 * hh))
    tiles = []

    def tile(arr, label, mask=None):
        im = Image.new("RGBA", (box[2] - box[0], box[3] - box[1]), (70, 70, 90, 255))
        im.alpha_composite(to_img(arr[box[1]:box[3], box[0]:box[2]]))
        if mask is not None:
            red = Image.new("RGBA", im.size, (255, 0, 0, 0))
            red.putalpha(Image.fromarray((mask[box[1]:box[3], box[0]:box[2]] * 140).astype(np.uint8)))
            im.alpha_composite(red)
        d = ImageDraw.Draw(im)
        fb = geo["face_box"]
        if geo.get("regions"):
            for r in geo["regions"].values():
                d.rectangle([r[0] - box[0], r[1] - box[1], r[2] - box[0], r[3] - box[1]], outline=(0, 255, 255, 255))
        else:
            d.rectangle([fb[0] - box[0], fb[1] - box[1], fb[2] - box[0], fb[3] - box[1]], outline=(0, 255, 255, 255))
            d.line([0, split - box[1], im.width, split - box[1]], fill=(255, 255, 0, 255))
        d.rectangle([0, 0, 8 * len(label) + 6, 14], fill=(0, 0, 0, 255))
        d.text((3, 1), label, fill=(255, 255, 255, 255))
        tiles.append(im)
    for k in ("A0", "A1", "B0", "B1"):
        if k in fig:
            tile(fig[k], k)
    for name, arr in out.items():
        tile(arr, name)
    if reg_masks:
        for (src, body), parts in reg_masks.items():
            if parts.get("face") is not None:
                tile(fig[body], f"{src}>{body} mask", parts["face"])
    else:
        if "B0" in masks:
            for part in ("eyes", "mouth"):
                if masks["B0"].get(part) is not None:
                    tile(fig["A0"], f"B0 {part}", masks["B0"][part])
        tile(fig["A0"], "Ellipse face", ell["face"])
    cols = 4
    tw, th = tiles[0].size
    sheet = Image.new("RGBA", (cols * (tw + 4), ((len(tiles) + cols - 1) // cols) * (th + 4)), (20, 20, 30, 255))
    for i, t in enumerate(tiles):
        sheet.alpha_composite(t, ((i % cols) * (tw + 4), (i // cols) * (th + 4)))
    p = dbg_dir / "sprite_debug.png"
    sheet.convert("RGB").save(p)
    # Säume prüfen: neutrale Ganzfigur vor hell und dunkel (halbe Größe) und die rechte obere Kopfkante
    # (Ohr, Mützenrand) doppelt vergrößert vor hell und dunkel
    arr = out.get("neutral", next(iter(out.values())))
    img = to_img(arr)
    zoom = (hx1 - int(0.45 * (hx1 - hx0)), hy0 - 12, hx1 + 12, hy0 + int(0.55 * hh))
    parts = []
    for bgc in ((235, 225, 210, 255), (25, 25, 45, 255)):
        im = Image.new("RGBA", img.size, bgc)
        im.alpha_composite(img)
        parts.append(im.resize((img.width // 2, img.height // 2), Image.LANCZOS))
    for bgc in ((235, 225, 210, 255), (25, 25, 45, 255)):
        im = Image.new("RGBA", img.size, bgc)
        im.alpha_composite(img)
        z = im.crop(zoom)
        parts.append(z.resize((z.width * 2, z.height * 2), Image.NEAREST))
    strip = Image.new("RGB", (sum(p_.width for p_ in parts), max(p_.height for p_ in parts)), (0, 0, 0))
    x = 0
    for p_ in parts:
        strip.paste(p_.convert("RGB"), (x, 0))
        x += p_.width
    strip.save(dbg_dir / "sprite_full.jpg", quality=90)
    print(f"  Prüfbilder: {rel(p)}, {rel(dbg_dir / 'sprite_full.jpg')}")


# --- Hintergrund ----------------------------------------------------------------------------------

def components(mask):
    """Zusammenhängende Flächen (4er-Nachbarschaft) als Liste von (ys, xs)."""
    lab = np.zeros(mask.shape, np.int32)
    out = []
    H, W = mask.shape
    for y, x in zip(*np.nonzero(mask)):
        if lab[y, x]:
            continue
        n = len(out) + 1
        stack, ys, xs = [(y, x)], [], []
        lab[y, x] = n
        while stack:
            cy, cx = stack.pop()
            ys.append(cy); xs.append(cx)
            for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not lab[ny, nx]:
                    lab[ny, nx] = n
                    stack.append((ny, nx))
        out.append((np.array(ys), np.array(xs)))
    return out


def peaks(score, allowed, n, min_d):
    s = np.where(allowed, score, -1e9)
    out = []
    for idx in np.argsort(s, axis=None)[::-1][:400000]:
        y, x = divmod(int(idx), s.shape[1])
        if s[y, x] < -1e8:
            break
        if all((x - px) ** 2 + (y - py) ** 2 >= min_d ** 2 for px, py in out):
            out.append((x, y))
        if len(out) >= n:
            break
    return out


def lamp_near(lights, H, W):
    """Maske um die schon gefundene Leuchtturmlampe (gehört nicht zu Fenster/Laterne)."""
    m = np.zeros((H, W), bool)
    if "lamp" in lights:
        x, y = lights["lamp"]
        m[max(0, y - 40):y + 40, max(0, x - 40):x + 40] = True
    return m


def point_like(lum, x, y, r=4, margin=15.0):
    """Stern statt Linie: die Mitte ist um margin heller als alle 8 Punkte im Abstand r."""
    H, W = lum.shape
    if not (r <= x < W - r and r <= y < H - r):
        return False
    ring = [lum[y + dy, x + dx] for dx, dy in ((r, 0), (-r, 0), (0, r), (0, -r), (r, r), (-r, -r), (r, -r), (-r, r))]
    if lum[y, x] - max(ring) <= margin:
        return False
    # ruhiger Himmel ringsum (11x11 ohne die Mitte 5x5): keine Linien, Wolkenkanten oder Dachfirste
    win = lum[max(0, y - 5):y + 6, max(0, x - 5):x + 6].copy()
    cy, cx = min(5, y), min(5, x)
    win[max(0, cy - 2):cy + 3, max(0, cx - 2):cx + 3] = np.nan
    return float(np.nanstd(win)) < 8.0


def bg(raw, test, dbg_dir):
    cfg = load_cfg()["bg"]
    p = raw / "bg.png"
    print("Hintergrund")
    if not p.exists():
        print("  bg.png fehlt – übersprungen")
        return None
    im = Image.open(p).convert("RGB")
    if cfg["retouch"]:
        ra = np.asarray(im).astype(np.float32).copy()
        for x0, y0, x1, y1 in cfg["retouch"]:
            top, bot = ra[y0 - 2:y0].mean(0), ra[y1:y1 + 2].mean(0)       # je Spalte: 2 Zeilen über/unter
            w = ((np.arange(y0, y1) - y0 + 1) / (y1 - y0 + 1))[:, None, None]
            ra[y0:y1, x0:x1] = (top[None] * (1 - w) + bot[None] * w)[:, x0:x1]
            print(f"  Retusche {x0},{y0}–{x1},{y1} (senkrecht überblendet)")
        im = Image.fromarray(ra.round().clip(0, 255).astype(np.uint8), "RGB")
    s = max(SCREEN[0] / im.width, SCREEN[1] / im.height)
    sw, sh = round(im.width * s), round(im.height * s)
    sc = im.resize((sw, sh), Image.LANCZOS)
    extra = sh - SCREEN[1]
    cy = cfg["crop_y"] if cfg["crop_y"] is not None else round(0.3 * extra)
    cx = (sw - SCREEN[0]) // 2
    crop = sc.crop((cx, cy, cx + SCREEN[0], cy + SCREEN[1]))
    print(f"  {im.width}x{im.height} -> {sw}x{sh}, Ausschnitt ab x={cx}, y={cy}")
    if not test:
        save_png(crop, ASSETS / "bg.png")
    save_png(crop, ART / "bg.png")
    a = np.asarray(crop).astype(np.float32)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    lum = a @ np.array([0.299, 0.587, 0.114], np.float32)
    W, H = SCREEN
    yy, xx = np.mgrid[0:H, 0:W]
    near = gauss(lum, 2.0)
    wide = gauss(lum, 14.0)
    spot = near - wide
    # Sprite-Rechteck (aus sprite.json), dort sind Lichter und Glitzern verdeckt
    sj = json.loads((ART / "sprite.json").read_text()) if (ART / "sprite.json").exists() else None
    hidden = np.zeros((H, W), bool)
    if sj:
        x0, y0 = sj["pos"]
        hidden[max(0, y0):, max(0, x0):x0 + sj["size"][0]] = True
    lights, found = {}, {}
    # Lampe: hellster kleiner Fleck im rechten oberen Bereich
    lamp_ok = (xx > 0.6 * W) & (yy > 0.03 * H) & (yy < 0.55 * H)
    lp = peaks(spot + 0.5 * near, lamp_ok, 1, 10)
    if lp:
        lights["lamp"] = [int(v) for v in lp[0]]; found["lamp"] = "gemessen"
    # Warme Lichter (Fenster, Laterne): nur kompakte warm-helle Flächen zählen, nicht Himmelsbänder am Horizont
    warm = (R > 185) & (R - B > 55) & (G > 100) & (yy > 0.15 * H) & (yy < 0.85 * H) & ~lamp_near(lights, H, W)
    cands = []
    # Scheiben eines Fensters bzw. Teile einer Laterne verbinden (3 px), dann je Fläche messen
    for ys, xs in components(dilate(warm, 3)):
        m = np.zeros((H, W), bool)
        m[ys, xs] = True
        m &= warm
        ys, xs = np.nonzero(m)
        n = len(ys)
        if n < 12:
            continue
        bw, bh = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
        if not (n <= 0.012 * W * H and bw <= 0.12 * W and bh <= 0.2 * H):
            continue
        # Lichtquelle statt Himmelsstück: deutlich heller als der Median eines Rings von 8–20 px (dünne
        # dunkle Linien wie Masten zählen im Median nicht)
        ring = dilate(m, 20) & ~dilate(m, 8)
        contrast = float(lum[ys, xs].mean() - np.median(lum[ring]))
        if contrast > 45:
            cands.append({"x": float(xs.mean()), "y": float(ys.mean()), "n": n, "contrast": round(contrast, 1)})
    found["light_candidates"] = [[int(c["x"]), int(c["y"]), c["n"], c["contrast"]] for c in cands]
    wr = 50
    # Fenster: größte Fläche im linken Drittel (Häuschen am linken Rand laut Prompt)
    left = [c for c in cands if c["x"] < 0.3 * W]
    if left:
        win = max(left, key=lambda c: c["n"])
        lights["window"] = [int(win["x"]), int(win["y"])]; found["window"] = "gemessen"
        wr = int(max(24, min(90, 1.6 * np.sqrt(win["n"]))))
        cands = [c for c in cands if c is not win and np.hypot(c["x"] - win["x"], c["y"] - win["y"]) > 1.5 * wr]
    # Laterne: übrige Fläche, die der Lage im Prompt (20 % Breite, Mitte) am nächsten liegt
    cands = [c for c in cands if c["x"] < 0.75 * W]
    if cands:
        lan = min(cands, key=lambda c: np.hypot(c["x"] - 0.2 * W, c["y"] - 0.5 * H))
        lights["lantern"] = [int(lan["x"]), int(lan["y"])]; found["lantern"] = "gemessen (nächste zur Prompt-Lage)"
    for k, v in (("window", [110, 380]), ("lantern", [250, 330]), ("lamp", [1075, 140])):
        if k not in lights:
            lights[k] = v; found[k] = "Standard (nicht gefunden)"
    # Schornstein: nicht messbar; über dem Fenster, sofern nicht vorgegeben
    lights["chimney"] = [max(20, lights["window"][0] - 20), max(30, lights["window"][1] - int(0.25 * H))]
    found["chimney"] = "geschätzt über dem Fenster"
    for k, v in cfg["lights"].items():
        lights[k] = list(v); found[k] = "Vorgabe prep_config.json"
    # Horizont: stärkste waagerechte Kante im mittleren Band (Spalten ohne Leuchtturm und Häuschen)
    if cfg["horizon"] is not None:
        horizon, found["horizon"] = int(cfg["horizon"]), "Vorgabe"
    else:
        gy = np.abs(np.diff(gauss(lum, 1.5), axis=0))[:, int(0.25 * W):int(0.62 * W)].mean(1)
        band = slice(int(0.3 * H), int(0.75 * H))
        horizon = int(np.argmax(gy[band]) + band.start)
        found["horizon"] = "gemessen"
    # Wasser: Farbe wie die Meeresfläche direkt unter dem Horizont (Mitte des Bildes), weichgezeichnet verglichen
    probe = a[horizon + 4:horizon + 24, int(0.3 * W):int(0.6 * W)].reshape(-1, 3)
    sea = np.median(probe, 0) if probe.size else np.array([90.0, 110.0, 140.0])
    soft = np.stack([gauss(a[..., i], 3.0) for i in range(3)], -1)
    sea_like = (np.sqrt(((soft - sea) ** 2).sum(-1)) < 38) & (yy > horizon + 2)
    # nur Meeresfläche, die bis an den Horizont reicht (Felsen, Mauern ähnlicher Farbe fallen weg)
    # Saat: alle meerfarbenen Pixel knapp unter dem Horizont (Pfosten und Boote teilen das Meer in Stücke)
    fim = Image.fromarray(sea_like.astype(np.uint8) * 255).copy()
    for sy, sx in np.argwhere(sea_like[horizon + 3:horizon + 9]):
        if fim.getpixel((int(sx), int(sy) + horizon + 3)) == 255:
            ImageDraw.floodfill(fim, (int(sx), int(sy) + horizon + 3), 128)
    connected = np.asarray(fim) == 128
    water = connected & (yy < TEXTBOX_Y - 8) & ~hidden
    found["water_px"] = int(water.sum())
    # Glitzern: helle Stellen auf dem Wasser (über der Umgebung), Mindestabstand 26 px
    rng = np.random.default_rng(1010)
    glints = []
    if water.any():
        gl = peaks((lum - wide) * 0.6 + lum * 0.4, erode(water, 2), cfg["glints"], 26)
        for x, y in gl:
            r, g, b = a[y, x]
            depth = (y - horizon) / max(1, TEXTBOX_Y - horizon)
            glints.append([int(x), int(y), round(float(rng.uniform(0.16, 0.28)) * (0.75 + 0.5 * depth), 3),
                           round(float(np.clip((r - b) / 120.0, 0, 1)), 2)])
    # Sterne: punktförmige helle Stellen (in allen 8 Richtungen dunkler) im dunklen Himmel; zu wenige ->
    # feste Zufallsorte im dunklen Himmel. Nicht hinter Figur und Ortskarte.
    sky = (yy < 0.7 * horizon) & (wide < 130) & ~hidden & ~((xx < 450) & (yy < 110))
    st = [(x, y) for x, y in peaks(lum - wide, sky, 60, 40)
          if point_like(lum, x, y) and a[y, x].min() > 150][:cfg["stars"] if isinstance(cfg["stars"], int) else 0]  # Sterne sind fast weiß
    stars = [[int(x), int(y), round(float(rng.uniform(0.12, 0.2)), 3)] for x, y in st]
    found["stars"] = f"{len(stars)} gemessen"
    dark = sky & (wide < 110)
    if isinstance(cfg["stars"], list):   # Vorgabe [[x, y], …] (Wolken und Dächer sind oft dunkel genug für die Suche)
        stars = [[int(x), int(y), round(float(rng.uniform(0.12, 0.2)), 3)] for x, y in cfg["stars"]]
        found["stars"] = f"{len(stars)} Vorgabe prep_config.json"
    elif len(stars) < 5 and dark.any():
        ys, xs = np.nonzero(dark)
        for i in rng.choice(len(ys), min(8 - len(stars), len(ys)), replace=False):
            stars.append([int(xs[i]), int(ys[i]), round(float(rng.uniform(0.1, 0.16)), 3)])
        found["stars"] += f", {len(stars) - len(st)} ergänzt (dunkler Himmel, Seed 1010)"
    layout = dict(lights)
    layout.update({"window_r": cfg["window_r"] or wr, "beam_len": cfg["beam_len"], "horizon": horizon,
                   "glints": glints, "stars": stars, "far_gulls": cfg["far_gulls"], "choices": cfg["choices"],
                   "measured": found, "source": [im.width, im.height], "crop_y": cy, "test_images": bool(test)})
    (ART / "layout.json").write_text(json.dumps(layout, indent=1) + "\n")
    print(f"  demo/art/layout.json: " + ", ".join(f"{k} {lights[k]} ({found[k]})" for k in
                                                   ("lamp", "window", "lantern", "chimney")))
    print(f"  Horizont y={horizon}, {len(glints)} Glitzerstellen, Sterne: {found['stars']}")
    # Prüfbild mit Markierungen
    dbg_dir.mkdir(parents=True, exist_ok=True)
    mk = crop.convert("RGBA")
    d = ImageDraw.Draw(mk)
    for k, (x, y) in lights.items():
        d.ellipse([x - 9, y - 9, x + 9, y + 9], outline=(0, 255, 255, 255), width=2)
        d.text((x + 11, y - 6), k, fill=(0, 255, 255, 255))
    d.line([0, horizon, W, horizon], fill=(255, 255, 0, 255))
    for x, y, *_ in glints:
        d.ellipse([x - 3, y - 3, x + 3, y + 3], outline=(255, 255, 255, 255))
    for x, y, _ in stars:
        d.rectangle([x - 3, y - 3, x + 3, y + 3], outline=(255, 120, 255, 255))
    if sj:
        x0, y0 = sj["pos"]
        d.rectangle([x0, y0, x0 + sj["size"][0], H - 1], outline=(255, 80, 80, 255))
    d.line([0, TEXTBOX_Y, W, TEXTBOX_Y], fill=(255, 80, 80, 255))
    mk.convert("RGB").save(dbg_dir / "bg_marks.jpg", quality=90)
    print(f"  Prüfbild: {rel(dbg_dir / 'bg_marks.jpg')}")
    return layout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("steps", nargs="*", default=["sprite", "bg"])
    ap.add_argument("--raw", default=str(ASSETS / "raw"), help="Ordner mit den Rohbildern")
    ap.add_argument("--test", action="store_true", help="nur demo/art/ schreiben (Testbilder)")
    ap.add_argument("--config", help="andere Konfigurationsdatei statt tools/prep_config.json")
    a = ap.parse_args()
    if a.config:
        global CFG_FILE
        CFG_FILE = pathlib.Path(a.config).resolve()
    raw = pathlib.Path(a.raw).resolve()
    dbg = raw / "debug"
    ART.mkdir(parents=True, exist_ok=True)
    marker = ART / "TESTBILDER.txt"
    for step in a.steps:
        {"sprite": sprite, "bg": bg}[step](raw, a.test, dbg)
    if a.test:
        marker.write_text("demo/art/ enthält Testbilder (prep.py --test), keine Ergebnisse. Quelle: "
                          f"{rel(raw)}\n")
    elif marker.exists() and set(a.steps) >= {"sprite", "bg"}:
        marker.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
